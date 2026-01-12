#!/bin/bash
cd ~/TravelLand
while true; do
  # Check if there are any changes to commit
  if git diff --quiet && git diff --staged --quiet; then
    echo "$(date): No changes to commit"
  else
    # Run pre-commit checks
    if ./pre-commit-check.sh > /tmp/precommit.log 2>&1; then
      git add -A
      git commit -m "Auto-save $(date +%H:%M:%S)" 2>/dev/null
      echo "$(date): ✅ Changes committed successfully"
    else
      echo "$(date): ❌ Pre-commit checks failed, skipping commit"
      cat /tmp/precommit.log
    fi
  fi
  sleep 2700
done