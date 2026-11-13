#!/bin/bash
# Started at Windows sign-in (Startup folder launcher). Waits for Docker, then starts the R8 supervisor
# unless one is already running or R8 has finished. Remove the launcher after R8:
#   %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\k8sgenbench_r8.vbs
cd "$(dirname "$0")/.."
log=evaluation/r8_supervisor.log
grep -q "all done (final" evaluation/r8_chain.log 2>/dev/null && { echo "$(date +%T) autostart: R8 already complete" >> $log; exit 0; }
for i in $(seq 1 180); do
  docker info >/dev/null 2>&1 && break
  # Docker Desktop does not always start at sign-in: launch it after ~1 min, and again every 10 min
  if [ $((i % 60)) -eq 6 ]; then
    echo "$(date +%T) autostart: docker not answering -> launching Docker Desktop" >> $log
    "/c/Program Files/Docker/Docker/Docker Desktop.exe" >/dev/null 2>&1 &
  fi
  sleep 10
done
if ps -ef | awk '$0 ~ /bash evaluation\/r8_supervisor.sh/ && $0 !~ /awk/' | grep -q .; then
  echo "$(date +%T) autostart: supervisor already running" >> $log; exit 0
fi
echo "$(date +%T) autostart: starting supervisor after sign-in" >> $log
echo "$(date +%T) resumed by autostart after sign-in" >> evaluation/r8_chain.log
nohup bash evaluation/r8_supervisor.sh > /dev/null 2>&1 &
