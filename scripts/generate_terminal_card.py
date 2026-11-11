"""Generate a neofetch-style terminal card SVG for the GitHub profile README.

Usage:
    GITHUB_TOKEN=... python scripts/generate_terminal_card.py dist/terminal.svg

Only the standard library is used so the workflow needs no install step.
Public, non-fork repositories are counted; private activity is not shown.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.request
from html import escape
from pathlib import Path

USER = "Termnix-IT"
EXCLUDED_LANGUAGES = {"HTML", "CSS", "SCSS"}

QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    repositories(ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false, first: 100) {
      totalCount
      nodes {
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

# Palette shared with the rest of the README (header / snake colors).
BG = "#0f172a"
BAR = "#1e293b"
FG = "#e2e8f0"
MUTED = "#64748b"
BLUE = "#93c5fd"
GREEN = "#22c55e"
ACCENT = "#60a5fa"

# Pixel-art "T" with a small network branch, drawn as rectangles so the shape
# does not depend on which monospace font the viewer has.
LOGO = [
    "################",
    "################",
    "################",
    "......####......",
    "......####......",
    "......####......",
    "......####...##.",
    "......#######.#.",
    "......####...##.",
    "......####......",
    "......####......",
    "..##..####......",
    "..#.#######.....",
    "..##..####......",
    "......####......",
    "......####......",
]
LOGO_COLORS = ["#22c55e", "#34d399", "#2dd4bf", "#38bdf8", "#60a5fa", "#3b82f6", "#1d4ed8", "#1d4ed8"]


def fetch(token: str) -> dict:
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-terminal-card"},
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        payload = json.load(res)
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    return payload["data"]["user"]


def summarize(user: dict, today: dt.date) -> dict:
    repos = user["repositories"]

    sizes: dict[str, int] = {}
    colors: dict[str, str] = {}
    for repo in repos["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            if name in EXCLUDED_LANGUAGES:
                continue
            sizes[name] = sizes.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or MUTED
    total = sum(sizes.values()) or 1
    top = sorted(sizes.items(), key=lambda kv: kv[1], reverse=True)[:5]
    languages = [(name, size / total, colors[name]) for name, size in top]

    calendar = user["contributionsCollection"]["contributionCalendar"]
    counts = {
        d["date"]: d["contributionCount"]
        for w in calendar["weeks"]
        for d in w["contributionDays"]
    }
    # Today may simply not have commits yet; start counting from yesterday then.
    day = today if counts.get(today.isoformat(), 0) > 0 else today - dt.timedelta(days=1)
    streak = 0
    while counts.get(day.isoformat(), 0) > 0:
        streak += 1
        day -= dt.timedelta(days=1)

    created = dt.date.fromisoformat(user["createdAt"][:10])
    return {
        "repos": repos["totalCount"],
        "contributions": calendar["totalContributions"],
        "streak": streak,
        "account_days": (today - created).days,
        "languages": languages,
    }


def render(s: dict, today: dt.date) -> str:
    width, line_h, char_w = 820, 22, 9.0
    pad_x, top = 24, 64
    info_x = pad_x + 20 * char_w

    info = [
        ("title", "termnix@github"),
        ("rule", "-" * 14),
        ("OS", "Home Lab (Ubuntu Server) + Windows 11"),
        ("Host", f"github.com/{USER}"),
        ("Uptime", f"{s['account_days']} days on GitHub · {s['streak']}-day streak"),
        ("Shell", "PowerShell 7 / Bash"),
        ("Terminal", "WezTerm / oterm (self-made)"),
        ("Packages", f"{s['repos']} public repos"),
        ("Commits", f"{s['contributions']} contributions in the last year"),
        ("Focus", "AI-driven dev · Network · Servers · Games"),
        ("Langs", ""),
    ]

    height = top + (len(info) + 3) * line_h + 24
    out: list[str] = []
    add = out.append
    add(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="neofetch style profile card for {USER}">'
    )
    add(
        "<style>text{font-family:Consolas,'Cascadia Mono','DejaVu Sans Mono',Menlo,monospace;"
        f"font-size:15px;fill:{FG};white-space:pre}}.m{{fill:{MUTED}}}.b{{fill:{BLUE};font-weight:700}}"
        f".g{{fill:{GREEN};font-weight:700}}</style>"
    )
    add(f'<rect width="{width}" height="{height}" rx="12" fill="{BG}"/>')
    add(f'<path d="M0 12a12 12 0 0 1 12-12h{width - 24}a12 12 0 0 1 12 12v22H0z" fill="{BAR}"/>')
    for i, c in enumerate(["#ef4444", "#f59e0b", GREEN]):
        add(f'<circle cx="{22 + i * 20}" cy="17" r="6" fill="{c}"/>')
    add(f'<text x="{width / 2}" y="22" text-anchor="middle" class="m" style="font-size:13px">termnix@homelab: ~</text>')

    def fade(delay: float) -> str:
        return f'<animate attributeName="opacity" from="0" to="1" begin="{delay:.2f}s" dur="0.15s" fill="freeze"/>'

    prompt = (
        '<tspan class="g">termnix@homelab</tspan><tspan class="m">:</tspan>'
        '<tspan class="b">~</tspan><tspan class="m">$ </tspan>'
    )

    # Prompt line with a typing effect: each character fades in one after another,
    # so the effect works whatever the viewer's monospace font width is.
    cmd = "neofetch"
    typed = "".join(
        f'<tspan opacity="0">{escape(ch)}{fade(0.5 + i * 0.12)}</tspan>' for i, ch in enumerate(cmd)
    )
    add(f'<text x="{pad_x}" y="{top - 14}">{prompt}{typed}</text>')

    reveal = 0.5 + len(cmd) * 0.12 + 0.3  # output appears after the command is "typed"

    y0 = top + 14
    cell = 10
    logo_top = y0 - 14
    for r, row in enumerate(LOGO):
        color = LOGO_COLORS[r * len(LOGO_COLORS) // len(LOGO)]
        cells = "".join(
            f'<rect x="{pad_x + c * cell}" y="{logo_top + r * cell}" width="{cell - 1}" height="{cell - 1}"/>'
            for c, ch in enumerate(row)
            if ch == "#"
        )
        add(f'<g fill="{color}" opacity="0">{fade(reveal + r * 0.04)}{cells}</g>')

    for i, (key, value) in enumerate(info):
        y = y0 + i * line_h
        delay = reveal + 0.3 + i * 0.12
        if key == "title":
            body = f'<tspan class="g">termnix</tspan><tspan class="m">@</tspan><tspan class="g">github</tspan>'
        elif key == "rule":
            body = f'<tspan class="m">{value}</tspan>'
        elif key == "Langs":
            body = f'<tspan class="b">{key}</tspan><tspan class="m">: </tspan>'
        else:
            body = f'<tspan class="b">{key}</tspan><tspan class="m">: </tspan>{escape(value)}'
        add(f'<text x="{info_x}" y="{y}" opacity="0">{body}{fade(delay)}</text>')

    # Language bar and legend under the "Langs" label.
    lang_row = len(info) - 1
    bar_y = y0 + lang_row * line_h - 11
    bar_x = info_x + 7 * char_w
    bar_w = width - bar_x - pad_x
    delay = reveal + 0.3 + lang_row * 0.12
    add(f'<g opacity="0">{fade(delay)}')
    add(f'<clipPath id="bar"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="12" rx="6"/></clipPath>')
    add('<g clip-path="url(#bar)">')
    x = bar_x
    for name, ratio, color in s["languages"]:
        w = bar_w * ratio
        add(f'<rect x="{x:.1f}" y="{bar_y}" width="{w + 0.5:.1f}" height="12" fill="{color}"/>')
        x += w
    add(f'<rect x="{x:.1f}" y="{bar_y}" width="{max(bar_x + bar_w - x, 0):.1f}" height="12" fill="{BAR}"/>')
    add("</g>")
    lx = info_x
    ly = bar_y + 12 + line_h
    for name, ratio, color in s["languages"]:
        label = f"{name} {ratio * 100:.0f}%"
        add(f'<circle cx="{lx + 5}" cy="{ly - 5}" r="5" fill="{color}"/>')
        add(f'<text x="{lx + 14}" y="{ly}" style="font-size:13px">{escape(label)}</text>')
        lx += 14 + len(label) * 8 + 18
    add("</g>")

    # Classic neofetch color blocks.
    blocks_y = ly + line_h - 4
    blocks = ["#0f172a", "#ef4444", GREEN, "#f59e0b", "#3b82f6", "#a855f7", "#06b6d4", FG]
    add(f'<g opacity="0">{fade(delay + 0.15)}')
    for i, c in enumerate(blocks):
        add(f'<rect x="{info_x + i * 26}" y="{blocks_y}" width="24" height="14" fill="{c}" stroke="{BAR}"/>')
    add("</g>")

    # Final prompt with a blinking cursor.
    end_y = height - 22
    add(f'<g opacity="0">{fade(delay + 0.4)}')
    add(f'<text x="{pad_x}" y="{end_y}">{prompt}<tspan class="g">█'
        '<animate attributeName="opacity" values="1;1;0;0" dur="1.1s" repeatCount="indefinite"/></tspan></text>')
    add(f'<text x="{width - pad_x}" y="{end_y}" text-anchor="end" class="m" style="font-size:12px">updated {today.isoformat()}</text>')
    add("</g>")
    add("</svg>")
    return "\n".join(out)


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN is required", file=sys.stderr)
        return 1
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "dist/terminal.svg")
    today = dt.datetime.now(dt.timezone.utc).date()
    stats = summarize(fetch(token), today)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(stats, today), encoding="utf-8")
    print(f"wrote {out}: {json.dumps({k: v for k, v in stats.items() if k != 'languages'})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
