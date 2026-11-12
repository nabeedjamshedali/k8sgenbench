"""List every D5 configuration that is not (Ready and smoke-OK) with its diagnostics, for root-cause triage.

Usage: python evaluation/triage_d5.py [results_dir] > evaluation/analysis/d5_triage.txt
"""
import glob
import json
import os
import sys

os.chdir(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "results"))
for f in sorted(glob.glob("*.json")):
    d5 = json.load(open(f, encoding="utf-8")).get("d5") or {}
    if not d5.get("ran") or (d5.get("ready_ok") and d5.get("smoke_ok")):
        continue
    dg = d5.get("diagnostics") or {}
    smoke = d5.get("smoke") or []
    print(f"\n## {f[:-5]}  apply={d5.get('apply_ok')} ready={d5.get('ready_ok')} "
          f"smoke={sum(c['passed'] for c in smoke)}/{len(smoke)} reason={d5.get('failure_reason')} "
          f"prepull_failed={len(d5.get('prepull_failed') or [])}")
    if not d5.get("apply_ok"):
        print("   apply_errors:", str(d5.get("apply_errors"))[:300])
    for c in smoke:
        if not c["passed"]:
            print("   smoke", c["name"], "->", str(c.get("detail"))[:80])
    for p in dg.get("pods") or []:
        if p.get("restarts") or p.get("last_reason"):
            print("   pod", {k: p.get(k) for k in ("pod", "restarts", "last_exit", "last_reason")},
                  "| log:", str(p.get("last_log") or "")[-200:].replace("\n", " / "))
    for e, n in list((dg.get("warning_events") or {}).items())[:4]:
        print("   event x%d" % n, e[:160])
