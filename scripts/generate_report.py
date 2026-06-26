#!/usr/bin/env python3
"""Generate a weekly cross-project activity report from the GitHub REST API.

No cloning, no AI. Reads commit/PR/issue activity for a fixed list of repos
over the past N days and writes a structured markdown report to reports/.
Auth: reads GITHUB_TOKEN from the environment (provided automatically on
GitHub Actions runners).
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

OWNER = "thomas-tahk"
DAYS = 7
API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO_LIST_FILE = Path(__file__).resolve().parent.parent / "repos.txt"


def load_repos():
    """Read the project list from repos.txt (one name per line, # = comment)."""
    if not REPO_LIST_FILE.exists():
        print(f"  ! {REPO_LIST_FILE.name} not found; no projects to report.")
        return []
    repos = []
    for line in REPO_LIST_FILE.read_text().splitlines():
        name = line.split("#", 1)[0].strip()
        if name:
            repos.append(name)
    return repos


def gh(path, params=None):
    """GET the GitHub API and return parsed JSON, or [] on any error."""
    url = f"{API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as err:
        print(f"  ! {path} -> HTTP {err.code}")
        return []
    except Exception as err:  # noqa: BLE001 - never let one repo break the run
        print(f"  ! {path} -> {err}")
        return []


def repo_activity(repo, since):
    info = gh(f"/repos/{OWNER}/{repo}")
    default_branch = info.get("default_branch") if isinstance(info, dict) else None

    branches = gh(f"/repos/{OWNER}/{repo}/branches", {"per_page": 100})
    names = [b["name"] for b in branches] if isinstance(branches, list) else []
    if not names and default_branch:
        names = [default_branch]

    seen = {}
    for branch in names:
        commits = gh(f"/repos/{OWNER}/{repo}/commits",
                     {"sha": branch, "since": since, "per_page": 100})
        if not isinstance(commits, list):
            continue
        for c in commits:
            sha = c.get("sha")
            if not sha or sha in seen:
                continue
            commit = c.get("commit", {})
            subject = (commit.get("message", "") or "").splitlines()
            seen[sha] = {
                "sha": sha[:7],
                "date": commit.get("author", {}).get("date", "")[:10],
                "subject": subject[0] if subject else "",
                "branch": branch,
            }
    commits = sorted(seen.values(), key=lambda x: x["date"], reverse=True)

    prs_raw = gh(f"/repos/{OWNER}/{repo}/pulls", {"state": "open", "per_page": 100})
    prs = [{"number": p["number"], "title": p["title"]}
           for p in prs_raw] if isinstance(prs_raw, list) else []

    issues_raw = gh(f"/repos/{OWNER}/{repo}/issues", {"state": "open", "per_page": 100})
    issues = [{"number": i["number"], "title": i["title"]}
              for i in issues_raw
              if isinstance(i, dict) and "pull_request" not in i] \
        if isinstance(issues_raw, list) else []

    return {"repo": repo, "default_branch": default_branch,
            "commits": commits, "prs": prs, "issues": issues}


def build_report(data, now, start):
    label = now.strftime("%G-W%V")
    date_range = f"{start.strftime('%b %d')} – {now.strftime('%b %d, %Y')}"
    active = sorted((d for d in data if d["commits"]),
                    key=lambda d: len(d["commits"]), reverse=True)
    stale = [d["repo"] for d in data if not d["commits"]]
    total = sum(len(d["commits"]) for d in data)

    out = [f"# Weekly Activity Report — {date_range} ({label})", ""]
    out.append(f"_{total} commits across {len(active)} active project(s) "
               f"in the last {DAYS} days._")
    out += ["", "## Highlights", ""]
    if active:
        out += [f"- **{d['repo']}** — {len(d['commits'])} commit(s)"
                for d in active[:6]]
    else:
        out.append("- No commit activity across tracked projects this week.")

    out += ["", "## Active Projects"]
    if not active:
        out += ["", "None this week."]
    for d in active:
        out += ["", f"### {d['repo']} — {len(d['commits'])} commit(s)"]
        for c in d["commits"]:
            tag = "" if c["branch"] == d["default_branch"] else f" `({c['branch']})`"
            out.append(f"- {c['date']} `{c['sha']}`{tag} {c['subject']}")
        if d["prs"]:
            out.append("- Open PRs: " + ", ".join(
                f"#{p['number']} {p['title']}" for p in d["prs"]))
        if d["issues"]:
            out.append("- Open issues: " + ", ".join(
                f"#{i['number']} {i['title']}" for i in d["issues"]))

    out += ["", "## Flags", ""]
    out.append("**Stale (no commits this week):** "
               + (", ".join(stale) if stale else "none"))
    out.append("")
    attention = []
    for d in data:
        bits = []
        if d["prs"]:
            bits.append(f"{len(d['prs'])} PR(s)")
        if d["issues"]:
            bits.append(f"{len(d['issues'])} issue(s)")
        if bits:
            attention.append(f"{d['repo']} ({', '.join(bits)})")
    out.append("**Open items / needs attention:** "
               + (", ".join(attention) if attention else "none"))
    out += ["", f"_Generated {now.strftime('%Y-%m-%d %H:%M UTC')} "
            f"by the weekly-report GitHub Action._"]
    return label, "\n".join(out) + "\n"


def main():
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=DAYS)
    since = start.strftime("%Y-%m-%dT%H:%M:%SZ")

    repos = load_repos()
    print(f"Reporting on {len(repos)} project(s) from {REPO_LIST_FILE.name}")
    data = []
    for repo in repos:
        print(f"- {repo}")
        data.append(repo_activity(repo, since))

    label, report = build_report(data, now, start)
    os.makedirs("reports", exist_ok=True)
    path = f"reports/{label}.md"
    with open(path, "w") as f:
        f.write(report)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
