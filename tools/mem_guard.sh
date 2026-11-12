#!/bin/bash
# Laptop safety net for evaluation batches: every 10 s, sum the kind nodes' memory; above LIMIT_MB,
# delete the cluster. The running config then fails with an INFRA error (nothing is recorded) instead of
# the Docker engine dying. Exits when STOP_FILE appears.
# Usage: bash tools/mem_guard.sh [LIMIT_MB] &   ...   touch evaluation/.mem_guard_stop
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LIMIT_MB=${1:-10000}
STOP_FILE="$ROOT/evaluation/.mem_guard_stop"
rm -f "$STOP_FILE"
while [ ! -f "$STOP_FILE" ]; do
  tot=$(timeout 30 docker stats --no-stream --format '{{.Name}} {{.MemUsage}}' 2>/dev/null | awk '
    $1 ~ /^k8sgen-(control-plane|worker)/ { v=$2; if (v ~ /GiB/) {sub("GiB","",v); s+=v*1024} else {sub("MiB","",v); s+=v} }
    END { print int(s) }')
  if [ "${tot:-0}" -gt "$LIMIT_MB" ]; then
    echo "$(date +%T) mem_guard: kind nodes at ${tot} MB > ${LIMIT_MB} MB -> deleting cluster"
    timeout 300 "$ROOT/tools/bin/kind.exe" delete cluster --name k8sgen
  fi
  sleep 10
done
echo "$(date +%T) mem_guard: stopped"
