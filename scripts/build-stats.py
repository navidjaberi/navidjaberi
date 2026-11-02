"""Rebuild the stats tiles and the activity heatmap from live GitHub data.

Run by .github/workflows/stats.yml every day. Needs GITHUB_TOKEN in the environment.
"""
import datetime, json, os, pathlib, urllib.request

USER = "navidjaberi"
ASSETS = pathlib.Path(__file__).resolve().parent.parent / "assets"

THEMES = {
    "light": dict(t="#1f2328", m="#59636e", sk="#e8ebef", bg="#f6f8fa", line="#d0d7de",
                  green="#1f9d6b", blue="#0969da", amber="#bf7a00"),
    "dark": dict(t="#e6edf3", m="#8b949e", sk="#21262d", bg="#161b22", line="#30363d",
                 green="#42b883", blue="#35a0ff", amber="#f5a524"),
}
FONT = "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "font-family:ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,monospace"


def fetch_json(url, body=None, token=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None)
    req.add_header("User-Agent", USER)
    if token:
        req.add_header("Authorization", f"bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.load(res)


def contributions(token):
    query = """query($login:String!){user(login:$login){contributionsCollection{
      contributionCalendar{totalContributions weeks{contributionDays{date contributionCount contributionLevel}}}}}}"""
    data = fetch_json("https://api.github.com/graphql",
                      {"query": query, "variables": {"login": USER}}, token)
    return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def stats_svg(p, total):
    tiles = [  # value, label, tag, color
        ("25 ms", "server response (was 2.25 s)", "GOLFAM", "amber"),
        ("1,400+", "tests, 100% line coverage", "LOADING KIT", "green"),
        ("50+", "employees on my CRM daily", "DONGI", "blue"),
        (str(total), "contributions this year", "GITHUB", "green"),
    ]
    label = "; ".join(f"{v} {l} ({tag.title()})" for v, l, tag, _ in tiles)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 130" width="1000" height="130" role="img" aria-label="{label}">',
           f"<style>text{{{FONT}}} .mono{{{MONO}}} @keyframes fadeIn{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}"
           f" .tile{{opacity:0;animation:fadeIn .6s ease forwards}} @media (prefers-reduced-motion:reduce){{.tile{{opacity:1;animation:none}}}}</style>"]
    for i, (value, text, tag, color) in enumerate(tiles):
        x, c = i * 254, p[color]
        out.append(f'<g class="tile" style="animation-delay:{i * .15:.2f}s">'
                   f'<rect x="{x + .5}" y=".5" width="237" height="129" rx="14" fill="{p["bg"]}" stroke="{p["line"]}"/>'
                   f'<rect x="{x + 20}" y="22" width="28" height="4" rx="2" fill="{c}"/>'
                   f'<text x="{x + 218}" y="28" text-anchor="end" class="mono" font-size="10.5" letter-spacing="1" fill="{p["m"]}">{tag}</text>'
                   f'<text x="{x + 20}" y="78" font-size="40" font-weight="700" fill="{c}" letter-spacing="-1">{value}</text>'
                   f'<text x="{x + 20}" y="106" font-size="14" fill="{p["m"]}">{text}</text></g>')
    out.append("</svg>")
    return "\n".join(out)


LEVELS = {"NONE": 0, "FIRST_QUARTILE": .3, "SECOND_QUARTILE": .55, "THIRD_QUARTILE": .8, "FOURTH_QUARTILE": 1}


def activity_svg(p, cal):
    weeks = cal["weeks"]
    days = [d for w in weeks for d in w["contributionDays"]]
    recent = sum(d["contributionCount"] for d in days[-56:])
    x0, y0, step, size = 176, 74, 14.5, 11.5
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 214" width="1000" height="214" role="img" '
           f'aria-label="GitHub activity: {cal["totalContributions"]} contributions in the last year, {recent} in the last 8 weeks">',
           f"<style>text{{{FONT}}} .mono{{{MONO}}} @keyframes pop{{from{{opacity:0}}to{{opacity:1}}}}"
           f" .c{{opacity:0;animation:pop .4s ease forwards}} @media (prefers-reduced-motion:reduce){{.c{{opacity:1;animation:none}}}}</style>",
           f'<rect x=".5" y=".5" width="999" height="213" rx="16" fill="{p["bg"]}" stroke="{p["line"]}"/>',
           f'<text x="24" y="30" class="mono" font-size="12" fill="{p["m"]}">// github activity, last 12 months</text>',
           f'<text x="24" y="112" font-size="40" font-weight="700" letter-spacing="-1" fill="{p["green"]}">{cal["totalContributions"]}</text>',
           f'<text x="24" y="136" font-size="13.5" fill="{p["m"]}">contributions</text>',
           f'<text x="24" y="170" class="mono" font-size="12" fill="{p["amber"]}">{recent} in the last</text>',
           f'<text x="24" y="186" class="mono" font-size="12" fill="{p["amber"]}">8 weeks ↑</text>']
    last_month = None
    for wi, week in enumerate(weeks):
        x = x0 + wi * step
        first = datetime.date.fromisoformat(week["contributionDays"][0]["date"])
        if first.month != last_month and wi < len(weeks) - 2:
            if last_month is not None or first.day <= 7:
                out.append(f'<text x="{x}" y="{y0 - 10}" class="mono" font-size="10.5" fill="{p["m"]}">{first.strftime("%b")}</text>')
            last_month = first.month
        cells = []
        for d in week["contributionDays"]:
            row = datetime.date.fromisoformat(d["date"]).isoweekday() % 7  # Sunday first, like GitHub
            level = LEVELS.get(d["contributionLevel"], 0)
            fill = f'fill="{p["green"]}" fill-opacity="{level}"' if level else f'fill="{p["sk"]}"'
            cells.append(f'<rect x="{x}" y="{y0 + row * step}" width="{size}" height="{size}" rx="3" {fill}><title>{d["date"]}: {d["contributionCount"]}</title></rect>')
        out.append(f'<g class="c" style="animation-delay:{wi * .015:.3f}s">{"".join(cells)}</g>')
    end = x0 + len(weeks) * step - (step - size)  # right edge of the grid
    ly = y0 + 7 * step + 12
    out.append(f'<text x="{end}" y="{ly + 10}" text-anchor="end" class="mono" font-size="10.5" fill="{p["m"]}">more</text>')
    for i, level in enumerate((1, .8, .55, .3, 0)):
        fill = f'fill="{p["green"]}" fill-opacity="{level}"' if level else f'fill="{p["sk"]}"'
        out.append(f'<rect x="{end - 36 - size - i * step:.1f}" y="{ly}" width="{size}" height="{size}" rx="3" {fill}/>')
    out.append(f'<text x="{end - 36 - size - 4 * step - 8:.1f}" y="{ly + 10}" text-anchor="end" class="mono" font-size="10.5" fill="{p["m"]}">less</text>')
    out.append("</svg>")
    return "\n".join(out)


def main():
    token = os.environ["GITHUB_TOKEN"]
    cal = contributions(token)
    for theme, p in THEMES.items():
        (ASSETS / f"stats-{theme}.svg").write_text(stats_svg(p, cal["totalContributions"]))
        (ASSETS / f"activity-{theme}.svg").write_text(activity_svg(p, cal))
    print(f"contributions={cal['totalContributions']}")


if __name__ == "__main__":
    main()
