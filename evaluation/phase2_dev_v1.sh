#!/usr/bin/env bash
# waits for the human baseline runs of the new projects, then evaluates Claude's dev replies and runs the API queue
cd "$(dirname "$0")/.." || exit 1
until [ -f evaluation/results/human__P09_teastore.json ]; do sleep 30; done
cd generation
for p in P04_voting-app P02_n8n P08_sock-shop P10_k8s-dashboard; do
  [ -f "../evaluation/results/claude__${p}__guided_r0__s1.json" ] && continue
  echo "=== $(date '+%F %T') claude $p s1 r0"
  python repair_loop.py ingest claude "$p" 1 0 "outputs/claude/$p/guided_r0/s1/reply.md"
done
cd ..
bash evaluation/phase2_queue.sh evaluation/phase2_dev_v1.txt
