#!/usr/bin/env bash
# Retries one model/project run after provider outages: up to N attempts, WAIT seconds apart, stopping once round 0
# has a result. Usage: bash evaluation/phase2_retry_later.sh <model> <project> [attempts] [wait_s] >> evaluation/phase2_run.log 2>&1
model=$1; project=$2; attempts=${3:-4}; wait_s=${4:-2700}
cd "$(dirname "$0")/../generation" || exit 1
for i in $(seq 1 "$attempts"); do
  sleep "$wait_s"
  [ -f "../evaluation/results/${model}__${project}__guided_r0__s1.json" ] && break
  echo "=== $(date '+%F %T') $model $project s1 (retry-later attempt $i/$attempts)"
  python repair_loop.py run "$model" "$project" 1 && break || echo "FAILED: $model $project s1 (exit $?)"
done
echo "=== $(date '+%F %T') retry-later done: $model $project"
