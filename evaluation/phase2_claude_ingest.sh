#!/usr/bin/env bash
# Ingests Claude replies ("project round" per line) written by subagents; each evaluation waits for the cluster lock.
# Usage: bash evaluation/phase2_claude_ingest.sh <list.txt> >> evaluation/phase2_run.log 2>&1
Q="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
cd "$(dirname "$0")/../generation" || exit 1
tr -d '\r' < "$Q" | while read -r project rnd; do
  [ -z "$project" ] && continue
  echo "=== $(date '+%F %T') claude $project s1 r$rnd (ingest)"
  python repair_loop.py ingest claude "$project" 1 "$rnd" "outputs/claude/$project/guided_r$rnd/s1/reply.md" \
    || echo "FAILED: claude $project s1 r$rnd (exit $?)"
done
echo "=== $(date '+%F %T') ingest done: $1"
