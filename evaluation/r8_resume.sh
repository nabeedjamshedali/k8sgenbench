#!/bin/bash
# Resume R8 after an interruption without re-deleting finished reruns: batch skips configs with a result JSON.
cd "$(dirname "$0")/.."
echo "$(date +%T) resume: start" >> evaluation/r8_chain.log
bash evaluation/r8_batch.sh claude deepseek gemini qwen > evaluation/r8_run_resume.log 2>&1
[ -f evaluation/.r8_stop ] && { echo "$(date +%T) resume: stop file" >> evaluation/r8_chain.log; exit 0; }
echo "$(date +%T) resume: sweep start" >> evaluation/r8_chain.log
bash evaluation/r8_batch.sh claude deepseek gemini qwen > evaluation/r8_run_sweep.log 2>&1
echo "$(date +%T) chain: all done (resume + sweep)" >> evaluation/r8_chain.log
