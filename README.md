# Weekly Reports

Auto-generated weekly cross-project activity reports, produced by a scheduled
**GitHub Actions** workflow (`.github/workflows/weekly-report.yml`).

- Runs every **Monday 05:00 UTC** (≈ 11pm Sunday America/Denver) on GitHub's
  servers — no local machine required.
- `scripts/generate_report.py` queries the GitHub REST API (no cloning, no AI)
  for commit / PR / issue activity over the past 7 days across a fixed list of
  projects, and writes `reports/YYYY-Www.md`.
- Run it on demand anytime from the repo's **Actions** tab → *Weekly Activity
  Report* → **Run workflow**.
- **Add or remove projects** by editing `repos.txt` (one repo name per line) —
  editable directly in GitHub's web UI, no code changes needed.
