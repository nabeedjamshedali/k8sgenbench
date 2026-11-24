#!/usr/bin/env bash
# Sourced by the phase-2 queue scripts before each item: waits (checking every 10 min) while C: has less free space
# than the evaluator needs, instead of letting every item abort on d5d6's disk guard.
wait_disk() {
  local need=${MIN_FREE_GB:-16} free
  while :; do
    free=$(powershell -NoProfile -Command "[math]::Floor((Get-PSDrive C).Free/1GB)" | tr -d '\r')
    [ "${free:-0}" -ge "$need" ] && return 0
    echo "=== $(date '+%F %T') waiting: only ${free} GB free on C: (need ${need})"
    sleep 600
  done
}
