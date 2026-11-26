#!/usr/bin/env bash
# Claude P06 Wordsmith re-run with the corrected docs bundle (db.words.sql added 2026-11-26): baselines, then guided r0.
cd "$(dirname "$0")/.." || exit 1
bash evaluation/phase2_baselines.sh evaluation/phase2_claude_P06_rerun_baselines.txt >> evaluation/phase2_claude_baselines.log 2>&1
bash evaluation/phase2_claude_ingest.sh evaluation/phase2_claude_P06_rerun_test.txt >> evaluation/phase2_claude_test.log 2>&1
echo "=== $(date '+%F %T') claude P06 rerun done" >> evaluation/phase2_claude_test.log
