#!/bin/bash
# Commit and push this project to GitHub.
# Usage (PyCharm terminal):  bash push_to_github.sh "what changed"
set -e
cd "$(dirname "$0")"
msg="${1:-Update $(date +%Y-%m-%d)}"
git add -A
if git diff --cached --name-only | grep -E '(\.env$|\.parquet$|\.venv|person_scan_checkpoint|dewey-anthropic-output|historical_outputs|missing_archive_outputs|job_postings/snapshots)'; then
  echo "STOPPED: the files above must not go to GitHub. Nothing was pushed."
  git reset -q
  exit 1
fi
if git diff --cached --quiet; then
  echo "Nothing new to commit."
else
  git commit -q -m "$msg"
fi
git push origin main && echo "PUSHED"
