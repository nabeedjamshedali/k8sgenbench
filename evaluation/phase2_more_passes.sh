#!/usr/bin/env bash
# Extra passes over the API-model lists after phase2_chains.sh has finished. Free-tier limits (Groq 429, Gemini
# 429/503) fail items within a minute, so a pass can end with many items still open; every step skips finished work
# and resumes open loops, so later passes only redo what is missing. Waits 45 minutes between passes.
# Usage: bash evaluation/phase2_more_passes.sh   (from the repository root)
cd "$(dirname "$0")/.." || exit 1
while ps -ef | grep -v grep | grep -q "phase2_chains.sh"; do sleep 60; done
for pass in 1 2 3 4 5 6 7 8 9 10; do
  echo "=== $(date '+%F %T') extra pass $pass" >> evaluation/phase2_test_run.log
  bash evaluation/phase2_baselines.sh evaluation/phase2_test_baselines.txt >> evaluation/phase2_baselines.log 2>&1
  bash evaluation/phase2_queue.sh evaluation/phase2_test_guided.txt >> evaluation/phase2_test_run.log 2>&1
  [ -f evaluation/results/gemini__P08_sock-shop__guided_r0__s1.json ] || \
    bash evaluation/phase2_queue.sh evaluation/phase2_dev_v2_retry3.txt >> evaluation/phase2_run.log 2>&1
  sleep 2700
done
echo "=== $(date '+%F %T') extra passes done" >> evaluation/phase2_test_run.log
