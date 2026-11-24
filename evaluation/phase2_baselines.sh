#!/usr/bin/env bash
# Neutral/production baselines for the new test projects: generate (skipped when the output exists), then evaluate
# under the cluster lock (skipped when the result exists). One "model project variant k" per line.
# Usage: bash evaluation/phase2_baselines.sh <list.txt> >> evaluation/phase2_baselines.log 2>&1
Q="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
source "$(dirname "$0")/wait_disk.sh"
cd "$(dirname "$0")/.." || exit 1
tr -d '\r' < "$Q" | while read -r m p v k; do
  [ -z "$m" ] && continue
  wait_disk
  echo "=== $(date '+%F %T') $m $p $v s$k"
  if [ ! -f "generation/outputs/$m/$p/$v/s$k/extraction.json" ]; then
    python generation/generate.py "$m" "$p" "$v" "$k" || { echo "FAILED generate: $m $p $v s$k"; continue; }
  fi
  [ -f "evaluation/results/${m}__${p}__${v}__s${k}.json" ] && continue
  python evaluation/locked_eval.py "$m" "$p" "$v" "$k" || echo "FAILED eval: $m $p $v s$k"
done
echo "=== $(date '+%F %T') baselines done: $1"
