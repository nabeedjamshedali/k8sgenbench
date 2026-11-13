#!/bin/bash
# Overnight supervisor: every 60 s, if R8 is unfinished and its driver or mem_guard is gone, restart it.
# Exits when r8_chain.log reports "all done (resume" or evaluation/.r8_stop exists.
cd "$(dirname "$0")/.."
log=evaluation/r8_supervisor.log
while true; do
  grep -q "all done (final" evaluation/r8_chain.log 2>/dev/null && { echo "$(date +%T) supervisor: R8 complete, exiting" >> $log; exit 0; }
  [ -f evaluation/.r8_stop ] && { echo "$(date +%T) supervisor: stop file, exiting" >> $log; exit 0; }
  if docker info >/dev/null 2>&1; then
    if ! ps -ef | grep -v grep | grep -q "tools/mem_guard.sh"; then
      echo "$(date +%T) supervisor: mem_guard missing -> restart" >> $log
      nohup bash tools/mem_guard.sh 10000 >> evaluation/mem_guard.log 2>&1 &
    fi
    if ! ps -ef | grep -v grep | grep -q "r8_resume.sh"; then
      echo "$(date +%T) supervisor: r8_resume missing -> restart" >> $log
      nohup bash evaluation/r8_resume.sh > /dev/null 2>&1 &
    fi
  else
    echo "$(date +%T) supervisor: docker not answering, waiting" >> $log
  fi
  sleep 60
done
