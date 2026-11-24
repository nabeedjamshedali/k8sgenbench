#!/usr/bin/env bash
# Runs the remaining phase-2 work as two chains (one for the API models, one for Claude), each strictly sequential so
# that Gemini calls do not collide; both share the cluster lock. Every step skips what already has a result, so the
# script can simply be started again after an interruption.
# Usage: bash evaluation/phase2_chains.sh   (from the repository root)
cd "$(dirname "$0")/.." || exit 1
api() {
  for pass in 1 2; do
    bash evaluation/phase2_baselines.sh evaluation/phase2_test_baselines.txt >> evaluation/phase2_baselines.log 2>&1
    bash evaluation/phase2_queue.sh evaluation/phase2_test_guided.txt >> evaluation/phase2_test_run.log 2>&1
    [ -f evaluation/results/gemini__P08_sock-shop__guided_r0__s1.json ] || \
      bash evaluation/phase2_queue.sh evaluation/phase2_dev_v2_retry3.txt >> evaluation/phase2_run.log 2>&1
  done
  echo "=== $(date '+%F %T') api chain done" >> evaluation/phase2_test_run.log
}
claude() {
  for l in a b c; do
    bash evaluation/phase2_baselines.sh evaluation/phase2_claude_baselines_$l.txt >> evaluation/phase2_claude_baselines.log 2>&1
  done
  for l in a b c; do
    bash evaluation/phase2_claude_ingest.sh evaluation/phase2_claude_test_$l.txt >> evaluation/phase2_claude_test.log 2>&1
  done
  echo "=== $(date '+%F %T') claude chain done" >> evaluation/phase2_claude_test.log
}
api &
claude &
wait
