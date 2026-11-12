"""Pre-populate the registry mirror with every image the not-yet-evaluated configurations reference, outside any
per-config deadline (on a slow link, first-time pulls exceed the batch's 40-min limit). Uses d5d6.provision(), the
exact logic D5 uses (pull as written, else the documented alias, ledger record), so measurements are unchanged.

Usage: python evaluation/prewarm_images.py      (order: P07, P03, P08, then everything else)
"""
import glob
import json
import os
import sys

import yaml

import d5d6

HERE = os.path.dirname(os.path.abspath(__file__))
ORDER = ["P07_online-boutique", "P03_grafana", "P08_sock-shop"]


def refs_by_project():
    led = json.load(open(d5d6.LEDGER)) if os.path.exists(d5d6.LEDGER) else {}
    out = {}
    for f in glob.glob(os.path.join(HERE, "..", "generation", "outputs", "*", "*", "*", "s*", "manifest.yaml")):
        m, p, v, s = f.replace("\\", "/").split("/")[-5:-1]
        if m == "gpt" or os.path.exists(os.path.join(HERE, "results", f"{m}__{p}__{v}__{s}.json")):
            continue
        try:
            docs = [d for d in yaml.safe_load_all(open(f, encoding="utf-8")) if isinstance(d, dict)]
        except Exception:
            continue
        for d in docs:
            spec = d.get("spec") or {}
            pss = [spec] if d.get("kind") == "Pod" else [
                (spec.get("template") or {}).get("spec"),
                (((spec.get("jobTemplate") or {}).get("spec") or {}).get("template") or {}).get("spec")]
            for ps in pss:
                for c in ((ps or {}).get("containers") or []) + ((ps or {}).get("initContainers") or []):
                    img = c.get("image")
                    if not img:
                        continue
                    _, path, tag, digest = d5d6.split_ref(img)
                    if not digest and f"{path}:{tag}" not in led:
                        out.setdefault(p, set()).add(img)
    return out


def main():
    todo = refs_by_project()
    projects = [p for p in ORDER if p in todo] + sorted(p for p in todo if p not in ORDER)
    for p in projects:
        aliases = d5d6.load_aliases(p)
        for ref in sorted(todo[p]):
            try:
                rec = d5d6.provision(ref, aliases)
                print(f"{p}  {ref}  -> {rec['served']} (as written pullable: {rec['as_written_pullable']})", flush=True)
            except Exception as e:  # transient network: leave it for D5 to retry
                print(f"{p}  {ref}  -> SKIPPED ({str(e)[:120]})", flush=True)
    print("prewarm done", flush=True)


if __name__ == "__main__":
    sys.exit(main())
