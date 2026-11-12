"""Flatten evaluation/results/*.json into evaluation/results/results.csv (design doc §7.1 record).

Usage: python evaluation/flatten.py
"""
import csv
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS = os.path.join(HERE, "results")


def meta(project):
    f = os.path.join(ROOT, "datasets", project, "internal", "meta.json")
    return json.load(open(f, encoding="utf-8")) if os.path.exists(f) else {}


def g(d, *path, default=None):
    for p in path:
        if not isinstance(d, dict) or p not in d:
            return default
        d = d[p]
    return d


def row(r):
    m = meta(r["project"])
    d1k, d1s = r.get("d1_kubeconform", {}), r.get("d1_server_dry_run", {})
    d2, d3, d4 = r.get("d2", {}), r.get("d3", {}), r.get("d4", {})
    d5, d6 = r.get("d5", {}), r.get("d6", {})
    out = {
        "project_id": r["project"], "project_class": m.get("class"), "human_intent": m.get("manifest_intent"),
        "source": r["source"], "prompt_variant": r.get("prompt_variant") or "n/a", "sample_k": r.get("sample_k"),
        "gen_finish_reason": r.get("gen_finish_reason"),
        "d1_parse_ok": r.get("d1_parse_ok"), "d1_schema_ok": d1k.get("valid"),
        "d1_server_ok": d1s.get("server_ok"), "d1_objects_total": d1s.get("objects_total"),
        "d1_objects_accepted": d1s.get("objects_accepted"),
        "d2_kubescape_compliance": g(d2, "kubescape", "compliance"),
        "d2_kubescape_nsa": g(d2, "kubescape", "frameworks", "NSA"),
        "d2_kubescape_mitre": g(d2, "kubescape", "frameworks", "MITRE"),
        "d2_pss_level": g(d2, "pss", "level"), "d2_secrets_found": g(d2, "secrets", "count"),
        "d3_kubescore_critical": g(d3, "kube_score", "critical"), "d3_kubescore_warning": g(d3, "kube_score", "warning"),
        "d3_polaris_score": g(d3, "polaris", "score"),
        "d3_kubelinter_total": g(d3, "kube_linter", "total"),
        "d3_zhang_smells": g(d3, "kube_linter", "zhang_total"),
        "d3_zhang_density_kloc": g(d3, "kube_linter", "zhang_density_per_kloc"),
        "d3_zhang_any": g(d3, "kube_linter", "zhang_any"),
        "d3_checklist_pct": g(d3, "checklist", "pct"),
        "d4_requirements_met": d4.get("requirements_met"), "d4_requirements_total": d4.get("requirements_total"),
        "d4_pct": d4.get("pct"),
        "d5_ran": d5.get("ran", False), "d5_apply_ok": d5.get("apply_ok"), "d5_ready_ok": d5.get("ready_ok"),
        "d5_time_to_ready_s": d5.get("time_to_ready_s"), "d5_ready_replicas": d5.get("ready_replicas"),
        "d5_expected_replicas": d5.get("expected_replicas"), "d5_smoke_ok": d5.get("smoke_ok"),
        "d5_failure_reason": d5.get("failure_reason"),
        "d5_images_aliased": sum(1 for i in d5.get("images", []) if str(i.get("served")).startswith("alias:")) if d5.get("ran") else None,
        "d6_gate": d6.get("gate") or ("ready" if d6.get("ran") else None),
        "loc": r.get("loc"),
    }
    for sev in ("critical", "high", "medium", "low"):
        out[f"d2_kubescape_{sev}"] = g(d2, "kubescape", "failed_controls_by_severity", sev)
        out[f"d2_trivy_{sev}"] = g(d2, "trivy", "by_severity", sev)
    for s, n in (g(d3, "kube_linter", "zhang_smells") or {}).items():
        out[f"d3_smell_{s}"] = n
    for fault in ("pod_delete", "container_crash"):
        reps = d6.get(fault) or []
        for i in range(3):
            x = reps[i] if i < len(reps) else {}
            out[f"d6_{fault}_recovery_ok_{i + 1}"] = x.get("recovery_ok")
            out[f"d6_{fault}_recovery_time_s_{i + 1}"] = x.get("recovery_time_s")
            out[f"d6_{fault}_availability_pct_{i + 1}"] = x.get("availability_pct")
    return out


def main():
    rows = [row(json.load(open(f, encoding="utf-8"))) for f in sorted(glob.glob(os.path.join(RESULTS, "*.json")))]
    if not rows:
        print("no results")
        return
    cols = list(dict.fromkeys(k for r in rows for k in r))
    path = os.path.join(RESULTS, "results.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rows -> {path}")


if __name__ == "__main__":
    main()
