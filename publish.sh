#!/usr/bin/env bash
# Regenerate site data and push to GitHub (commits only if something changed).
set -euo pipefail
cd "$(dirname "$0")"
python3 export_site.py
git add docs state.json backtest.json backtest.png 2>/dev/null || true
if git diff --cached --quiet; then
  echo "No changes to publish."
else
  git commit -q -m "Update paper-trading data $(TZ=America/Chicago date '+%Y-%m-%d %H:%M %Z')"
  git push -q origin main
  echo "Published."
fi
