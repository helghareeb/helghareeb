"""Draw the profile's stats and top-languages cards as SVG files.

Run daily by .github/workflows/cards.yml, so the profile never depends on a
shared card server. Only public repositories and public activity are counted.

    GITHUB_TOKEN=... python scripts/cards.py helghareeb cards/
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from html import escape
from pathlib import Path

API = "https://api.github.com/graphql"

QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    name
    login
    followers { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestReviewContributions
      totalRepositoriesWithContributedCommits
    }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC,
                 first: 100, after: $after) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

# Tokyo Night, as the old cards used.
BG, TITLE, TEXT, ICON, MUTED = "#1a1b27", "#70a5fd", "#38bdae", "#bf91f3", "#a9b1d6"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"


def fetch(login, token):
    repos, after, user = [], None, None
    while True:
        body = json.dumps({"query": QUERY, "variables": {"login": login, "after": after}}).encode()
        req = urllib.request.Request(API, body, {"Authorization": f"bearer {token}",
                                                 "Content-Type": "application/json",
                                                 "User-Agent": "profile-cards"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
        if data.get("errors"):
            raise SystemExit(f"GitHub API error: {data['errors']}")
        user = data["data"]["user"]
        page = user["repositories"]
        repos += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return user, repos
        after = page["pageInfo"]["endCursor"]


def card(width, height, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="t">
  <title id="t">{escape(title)}</title>
  <style>
    .title {{ font: 600 18px {FONT}; fill: {TITLE}; }}
    .label {{ font: 600 14px {FONT}; fill: {TEXT}; }}
    .value {{ font: 700 14px {FONT}; fill: {MUTED}; }}
    .small {{ font: 400 11px {FONT}; fill: {MUTED}; opacity: 0.7; }}
  </style>
  <rect x="0.5" y="0.5" rx="4.5" width="{width - 1}" height="{height - 1}" fill="{BG}"/>
  <text x="25" y="35" class="title">{escape(title)}</text>
{body}
</svg>
"""


def stats_card(user, repos, today):
    c = user["contributionsCollection"]
    rows = [
        ("Total stars", sum(r["stargazerCount"] for r in repos)),
        ("Public repositories", user["repositories"]["totalCount"]),
        (f"Commits in the last year", c["totalCommitContributions"]),
        ("Pull requests", user["pullRequests"]["totalCount"]),
        ("Issues", user["issues"]["totalCount"]),
        ("Contributed to (last year)", c["totalRepositoriesWithContributedCommits"]),
    ]
    body = []
    for i, (label, value) in enumerate(rows):
        y = 70 + i * 25
        body.append(f'  <circle cx="31" cy="{y - 5}" r="4" fill="{ICON}"/>')
        body.append(f'  <text x="45" y="{y}" class="label">{escape(label)}:</text>')
        body.append(f'  <text x="300" y="{y}" class="value">{value:,}</text>')
    body.append(f'  <text x="25" y="{70 + len(rows) * 25 + 2}" class="small">Updated {today}</text>')
    name = user["name"] or user["login"]
    return card(400, 70 + len(rows) * 25 + 15, f"{name}'s GitHub Stats", "\n".join(body))


def langs_card(repos, today, top=8):
    sizes, colors = {}, {}
    for r in repos:
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            sizes[n] = sizes.get(n, 0) + e["size"]
            colors[n] = e["node"]["color"] or "#858585"
    total = sum(sizes.values()) or 1
    langs = sorted(sizes.items(), key=lambda kv: -kv[1])[:top]
    width, bar = 420, 370
    body, x = [], 25
    body.append(f'  <mask id="m"><rect x="25" y="55" width="{bar}" height="8" rx="4" fill="#fff"/></mask>')
    shown = sum(s for _, s in langs)
    for name, size in langs:
        w = bar * size / shown
        body.append(f'  <rect mask="url(#m)" x="{x:.2f}" y="55" width="{w:.2f}" height="8" fill="{colors[name]}"/>')
        x += w
    for i, (name, size) in enumerate(langs):
        col, row = i % 2, i // 2
        cx, cy = 25 + col * 200, 90 + row * 25
        body.append(f'  <circle cx="{cx + 5}" cy="{cy - 4}" r="5" fill="{colors[name]}"/>')
        body.append(f'  <text x="{cx + 15}" y="{cy}" class="label">{escape(name)}'
                    f' <tspan class="value">{100 * size / total:.1f}%</tspan></text>')
    height = 90 + ((len(langs) + 1) // 2) * 25 + 10
    body.append(f'  <text x="25" y="{height - 12}" class="small">Public repositories · updated {today}</text>')
    return card(width, height + 5, "Most Used Languages", "\n".join(body))


def main():
    login, out = sys.argv[1], Path(sys.argv[2])
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("set GITHUB_TOKEN")
    user, repos = fetch(login, token)
    today = datetime.now(timezone.utc).strftime("%d %b %Y")
    out.mkdir(parents=True, exist_ok=True)
    (out / "stats.svg").write_text(stats_card(user, repos, today), encoding="utf-8")
    (out / "langs.svg").write_text(langs_card(repos, today), encoding="utf-8")
    print(f"{len(repos)} public repositories; cards written to {out}")


if __name__ == "__main__":
    main()
