#!/bin/bash
# Runs after the current claude+deepseek batch: (1) re-run the configs listed in r8_rerun_list.txt on the final
# pipeline, (2) evaluate gemini and qwen. Each stage logs to its own file. Stops early if evaluation/.r8_stop exists.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
until grep -q "R8 batch done\|stop file found" evaluation/r8_run.log 2>/dev/null; do sleep 60; done
[ -f evaluation/.r8_stop ] && { echo "stop file present, chain not started"; exit 0; }

echo "$(date +%T) chain: deleting rerun results"
grep -v '^#' evaluation/r8_rerun_list.txt | while read -r n; do
  [ -n "$n" ] && rm -f "evaluation/results/$n.json" && rm -rf "evaluation/results/raw/$n" && echo "  removed $n"
done
bash evaluation/r8_batch.sh claude deepseek > evaluation/r8_run_reruns.log 2>&1
[ -f evaluation/.r8_stop ] && exit 0
bash evaluation/r8_batch.sh gemini qwen > evaluation/r8_run_gemini_qwen.log 2>&1
echo "$(date +%T) chain: all done"
