#!/usr/bin/env bash
# Ingests Claude replies written by subagents; each evaluation waits for the cluster lock.
# One "project round" (sample 1) or "project sample round" per line.
# Usage: bash evaluation/phase2_claude_ingest.sh <list.txt> >> evaluation/phase2_claude_run.log 2>&1
Q="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
source "$(dirname "$0")/wait_disk.sh"
cd "$(dirname "$0")/../generation" || exit 1
tr -d '\r' < "$Q" | while read -r project a b; do
  [ -z "$project" ] && continue
  wait_disk
  if [ -z "$b" ]; then k=1; rnd=$a; else k=$a; rnd=$b; fi
  # a re-run after an interruption skips what is already evaluated
  [ -f "../evaluation/results/claude__${project}__guided_r${rnd}__s${k}.json" ] && continue
  echo "=== $(date '+%F %T') claude $project s$k r$rnd (ingest)"
  python repair_loop.py ingest claude "$project" "$k" "$rnd" "outputs/claude/$project/guided_r$rnd/s$k/reply.md" \
    || echo "FAILED: claude $project s$k r$rnd (exit $?)"
done
echo "=== $(date '+%F %T') ingest done: $1"
