#!/usr/bin/env bash
# Runs repair_loop.py `run` for each "model project k" line of a queue file, one after another.
# Usage: bash evaluation/phase2_queue.sh <queue.txt> >> evaluation/phase2_run.log 2>&1
Q="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
cd "$(dirname "$0")/../generation" || exit 1
# tr drops the carriage returns of a queue file saved with CRLF line ends
tr -d '\r' < "$Q" | while read -r model project k; do
  [ -z "$model" ] || [ "${model:0:1}" = "#" ] && continue
  echo "=== $(date '+%F %T') $model $project s$k"
  python repair_loop.py run "$model" "$project" "$k" || echo "FAILED: $model $project s$k (exit $?)"
done
echo "=== $(date '+%F %T') queue done: $1"
