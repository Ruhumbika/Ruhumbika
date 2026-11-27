"""Render GitHub's contribution calendar as two self-contained SVG images."""

from datetime import date
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "readme"
PALETTES = {
    "dark": ("#101b26", "#2c4455", "#e9f8fa", "#b6ceda", "#1c303e",
             "#1b544b", "#247e69", "#43b899", "#8af3cf", "#f9c983"),
    "light": ("#f1f7f7", "#b7c9cf", "#183042", "#385568", "#dce8eb",
              "#b5dfd0", "#70bea5", "#2d9277", "#11634f", "#9e4e12"),
}
LEVELS = {name: i for i, name in enumerate(
    ("NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE")
)}
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date weekday contributionLevel } }
      }
    }
  }
}
"""


def fetch_calendar():
    request = Request(
        "https://api.github.com/graphql",
        data=json.dumps({
            "query": QUERY, "variables": {"login": os.environ["PROFILE_LOGIN"]},
        }).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
            "Content-Type": "application/json",
            "User-Agent": "profile-contribution-svg",
        },
    )
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get("errors") or not payload.get("data", {}).get("user"):
        raise RuntimeError("GitHub did not return a contribution calendar.")
    calendar = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    if not calendar["weeks"]:
        raise RuntimeError("GitHub returned an empty contribution calendar.")
    return calendar


def render(calendar, palette):
    bg, border, ink, muted, *colors, sweep = palette
    pending = calendar is None
    detail = ("GitHub activity will appear after the first refresh."
              if pending else f'{calendar["totalContributions"]:,} contributions in the past year')
    svg = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="229" viewBox="0 0 1000 229" role="img" aria-labelledby="title desc">
  <title id="title">GitHub contribution calendar</title>
  <desc id="desc">{detail} Animated scan across weekly contribution cells.</desc>
  <style>
    .title {{ font: 700 22px system-ui, sans-serif; }}
    .caption {{ font: 14px system-ui, sans-serif; }}
    .label {{ font: 12px ui-monospace, monospace; }}
    .scan {{ opacity: 0; animation: scan 13s linear infinite; }}
    .wake {{ opacity: 0; animation: wake 13s linear infinite; }}
    @keyframes scan {{ 0% {{ opacity: 0; }} 4%, 84% {{ opacity: .86; }} 92%, 100% {{ opacity: 0; transform: translateX(var(--span, 877px)); }} }}
    @keyframes wake {{ 0%, 100% {{ opacity: 0; }} 3% {{ opacity: .85; }} 11% {{ opacity: 0; }} }}
    @media (prefers-reduced-motion: reduce) {{ .scan, .wake {{ animation: none; }} }}
  </style>
  <rect x=".5" y=".5" width="999" height="228" rx="14" fill="{bg}" stroke="{border}"/>
  <text x="27" y="37" class="title" fill="{ink}">Contribution calendar</text>
  <text x="27" y="61" class="caption" fill="{muted}">{detail}</text>''']
    if pending:
        svg.append(f'  <rect x="27" y="84" width="946" height="118" rx="10" fill="{colors[0]}"/>')
    else:
        weeks = calendar["weeks"]
        step = min(17, 898 / len(weeks))
        width = step - 4
        last_month = None
        label_x = -100
        highlights = []
        for col, week in enumerate(weeks):
            x = 61 + col * step
            for day in week["contributionDays"]:
                month = date.fromisoformat(day["date"]).month
                if month != last_month and x - label_x >= 51 and x < 946:
                    svg.append(f'  <text x="{x:.1f}" y="86" class="label" fill="{muted}">{MONTHS[month-1]}</text>')
                    label_x = x
                    last_month = month
                level = LEVELS[day["contributionLevel"]]
                y = 96 + day["weekday"] * 14
                svg.append(f'  <rect x="{x:.1f}" y="{y}" width="{width:.1f}" height="11" rx="2" fill="{colors[level]}"/>')
                if level >= 3:
                    delay = 12 * col / max(len(weeks) - 1, 1) - .22
                    highlights.append(
                        f'  <rect class="wake" style="animation-delay:{delay:.2f}s" '
                        f'x="{x:.1f}" y="{y}" width="{width:.1f}" height="11" rx="2" '
                        f'fill="none" stroke="{sweep}"/>'
                    )
        svg.extend(highlights)
        span = (len(weeks) - 1) * step + width
        svg.append(f'  <path class="scan" style="--span:{span:.1f}px" d="M61 94v100" stroke="{sweep}" stroke-width="2"/>')
        svg.append(f'  <text x="821" y="209" class="label" fill="{muted}">Less</text>')
        svg.extend(f'  <rect x="{859 + 15*i}" y="199" width="11" height="11" rx="2" fill="{c}"/>' for i, c in enumerate(colors))
        svg.append(f'  <text x="939" y="209" class="label" fill="{muted}">More</text>')
    return "\n".join([*svg, "</svg>", ""])


if __name__ == "__main__":
    data = fetch_calendar()
    for theme, colors in PALETTES.items():
        (ASSETS / f"contributions-{theme}.svg").write_text(render(data, colors), encoding="utf-8")
