#!/bin/bash
# Resume R8 after an interruption without re-deleting finished reruns: batch skips configs with a result JSON.
cd "$(dirname "$0")/.."
MODELS="claude deepseek gemini qwen gpt"
echo "$(date +%T) resume: start ($MODELS)" >> evaluation/r8_chain.log
bash evaluation/r8_batch.sh $MODELS >> evaluation/r8_run_resume.log 2>&1
[ -f evaluation/.r8_stop ] && { echo "$(date +%T) resume: stop file" >> evaluation/r8_chain.log; exit 0; }
echo "$(date +%T) resume: sweep start" >> evaluation/r8_chain.log
bash evaluation/r8_batch.sh $MODELS > evaluation/r8_run_sweep.log 2>&1
echo "$(date +%T) chain: all done (final, $MODELS)" >> evaluation/r8_chain.log
