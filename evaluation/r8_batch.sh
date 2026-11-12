#!/bin/bash
# Phase R8 driver: full D1-D6 evaluation for the given model slots, one project at a time.
# The cluster is recreated per project; a config whose result JSON already exists is skipped,
# so the batch can be stopped and resumed. Run tools/mem_guard.sh alongside it.
# Usage: bash evaluation/r8_batch.sh claude deepseek
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="/c/Users/DELL/AppData/Local/Programs/Python/Python314/python.exe"
KIND="$ROOT/tools/bin/kind.exe"
PROJECTS="P02_n8n P04_voting-app P05_emojivoto P08_sock-shop P10_k8s-dashboard P07_online-boutique P03_grafana"
STOP_FILE="$ROOT/evaluation/.r8_stop"
rm -f "$STOP_FILE"
cd "$ROOT"

# Listed is not enough: after a host sleep Docker can leave the node containers stopped while kind still lists the
# cluster (every config then crashed reading the control-plane clock). Require a running control plane that answers.
cluster_up() {
  "$KIND" get clusters 2>/dev/null | grep -qx k8sgen || return 1
  [ "$(docker inspect -f '{{.State.Running}}' k8sgen-control-plane 2>/dev/null)" = "true" ] || return 1
  timeout 60 "$ROOT/tools/bin/kubectl.exe" --context kind-k8sgen get nodes >/dev/null 2>&1
}

for p in $PROJECTS; do
  todo=()
  for m in "$@"; do for v in neutral production; do for k in 1 2 3; do
    [ -f "generation/outputs/$m/$p/$v/s$k/manifest.yaml" ] || continue
    [ -f "evaluation/results/${m}__${p}__${v}__s${k}.json" ] && continue
    todo+=("$m $v $k")
  done; done; done
  [ ${#todo[@]} -eq 0 ] && continue
  echo "##### $p recreate $(date +%T) (${#todo[@]} configs)"
  "$PY" tools/setup_cluster.py --recreate || { echo "cluster setup FAILED for $p"; exit 1; }
  for c in "${todo[@]}"; do
    [ -f "$STOP_FILE" ] && { echo "stop file found, exiting $(date +%T)"; exit 0; }
    read -r m v k <<< "$c"   # not `set --`: that would overwrite "$@", the model list for later projects
    if ! cluster_up; then
      echo "cluster missing (mem_guard?) $(date +%T): recreating"
      "$PY" tools/setup_cluster.py --recreate || exit 1
    fi
    echo "== $m $p $v s$k $(date +%T)"
    (cd evaluation && timeout 2400 "$PY" eval_runner.py "$m" "$p" "$v" "$k" --runtime) \
      || echo "   eval FAILED (exit $?) for $m $p $v s$k"
  done
done
echo "R8 batch done $(date +%T)"
