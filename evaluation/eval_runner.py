"""K8sGenBench evaluation runner — Phase R1: D1 (correctness) + D4 (requirement satisfaction).

D2 (security), D3 (static reliability), D5 (deploy) and D6 (resilience) are added in later phases
(see PROGRESS.md, Phase R2-R4). This script only ever reads manifest files and runs read-only /
dry-run / throwaway-namespace operations; it never deploys a real workload.

Usage: python evaluation/eval_runner.py <source> <project> [<variant> <sample_k>]
  source   "human" or a model slot name (gemini|qwen|claude|gpt|deepseek)
  project  e.g. P05_emojivoto
  variant  neutral|production (omit for source=human)
  sample_k e.g. 1 (omit for source=human)
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import uuid

import yaml

import d2d3
import d5d6

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATASETS = os.path.join(ROOT, "datasets")
GEN_OUTPUTS = os.path.join(ROOT, "generation", "outputs")
BIN = os.path.join(ROOT, "tools", "bin")
CTX = "kind-k8sgen"
K8S_VERSION = "1.37.0"
RESULTS_DIR = os.path.join(HERE, "results")


def run(args, timeout=180, input=None):
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                          errors="ignore", timeout=timeout, input=input)


def kubectl(*args, **kw):
    return run([os.path.join(BIN, "kubectl.exe"), "--context", CTX, *args], **kw)


class StrictLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys, as YAML 1.2 and kubectl do. PyYAML's default keeps the last
    value silently, which turns several objects written without `---` separators into one garbled object."""


def _no_duplicate_keys(loader, node, deep=False):
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(None, None, f"duplicate key {key!r}", key_node.start_mark)
        seen.add(key)
    return loader.construct_mapping(node, deep)


StrictLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_keys)


def load_docs_for_source(source, project, variant=None, sample_k=None):
    """Returns (docs, manifest_text, source_dir)."""
    if source == "human":
        human_dir = os.path.join(DATASETS, project, "human")
        rendered = os.path.join(human_dir, "rendered.yaml")
        if os.path.exists(rendered):
            files = [rendered]
        else:
            files = sorted(
                os.path.join(human_dir, f) for f in os.listdir(human_dir)
                if f.endswith((".yaml", ".yml")) and f not in ("kustomization.yaml", "kustomization.yml")
            )
        text = "\n---\n".join(open(f, encoding="utf-8").read() for f in files)
        source_dir = human_dir
    else:
        sample_dir = os.path.join(GEN_OUTPUTS, source, project, variant, f"s{sample_k}")
        manifest = os.path.join(sample_dir, "manifest.yaml")
        text = open(manifest, encoding="utf-8").read()
        source_dir = sample_dir
    try:
        docs = [d for d in yaml.load_all(text, Loader=StrictLoader) if d]
        parse_error = None
        # an empty reply (e.g. a provider-blocked one) or prose parsed as a YAML scalar is not a configuration
        if not docs:
            parse_error = "no YAML documents in response"
        elif not all(isinstance(d, dict) for d in docs):
            parse_error = "document is not a mapping (prose or a bare value, not a Kubernetes object)"
    except yaml.YAMLError as e:
        docs = []
        parse_error = str(e)
    return docs, text, source_dir, parse_error


KUBECONFORM_CACHE = os.path.join(ROOT, "tools", "scanner-artifacts", "kubeconform-cache")


def d1_kubeconform(text):
    # Schemas are cached locally: each is downloaded once (a slow link once timed kubeconform out at 180 s) and the
    # exact schema files used are kept with the scanner artifacts.
    os.makedirs(KUBECONFORM_CACHE, exist_ok=True)
    r = run([os.path.join(BIN, "kubeconform.exe"), "-output", "json", "-summary", "-cache", KUBECONFORM_CACHE,
             "-ignore-missing-schemas", "-kubernetes-version", K8S_VERSION, "-"],
            input=text, timeout=600)
    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError):
        return {"ran": False, "raw_stdout": r.stdout[-2000:], "raw_stderr": r.stderr[-2000:]}
    summary = data.get("summary", {})
    statuses = [res.get("status") for res in data.get("resources", [])]
    return {
        "ran": True,
        "valid": summary.get("invalid", 0) == 0 and summary.get("errors", 0) == 0,
        "summary": summary,
        "statuses": statuses,
        "details": [res for res in data.get("resources", []) if res.get("status") not in ("valid", "skipped")],
    }


def d1_server_dry_run(docs, run_id):
    """Create any namespaces the manifest needs (for real, so NamespaceLifecycle admission
    doesn't reject the dry-run), apply everything else with --dry-run=server, then clean up.
    Mirrors the explicit/implicit namespace split in datasets/deploy_check.py."""
    if not docs:
        return {"ran": False, "reason": "no parseable documents"}

    throwaway_ns = f"d1-{run_id}"
    declared_ns = sorted({d["metadata"]["name"] for d in docs
                          if isinstance(d, dict) and d.get("kind") == "Namespace"
                          and d.get("metadata", {}).get("name")})
    explicit = [d for d in docs if isinstance(d, dict) and d.get("kind") != "Namespace"
               and d.get("metadata", {}).get("namespace")]
    implicit = [d for d in docs if d not in explicit
               and not (isinstance(d, dict) and d.get("kind") == "Namespace")]
    referenced_ns = sorted({d["metadata"]["namespace"] for d in explicit} - set(declared_ns))

    created = []
    try:
        kubectl("create", "namespace", throwaway_ns)
        created.append(throwaway_ns)
        for ns in declared_ns:
            kubectl("create", "namespace", ns)
            created.append(ns)
        for ns in referenced_ns:
            # explicit namespace referenced but never declared by a Namespace object in the
            # manifest itself (a real gap the manifest has) -- create it anyway so the dry-run
            # can still evaluate the rest of the objects, and record it as a finding.
            kubectl("create", "namespace", ns)
            created.append(ns)

        # Apply one object at a time: a single object kubectl can't resolve (e.g. a CRD type like
        # ServiceMonitor that isn't installed on this cluster) must not mask whether every OTHER
        # object in the same manifest was independently valid. Slower than one batched apply, but
        # gives correct per-object accept/reject accounting and a real per-object error taxonomy.
        errors = []
        per_object = []
        accepted = 0
        total = 0

        def apply_one(doc, ns_flag):
            nonlocal accepted, total
            total += 1
            r = kubectl("apply", "--dry-run=server", *ns_flag, "-f", "-", input=yaml.safe_dump(doc))
            ok = r.returncode == 0
            if ok:
                accepted += 1
            else:
                err = r.stderr.strip()
                errors.append(err)
            per_object.append({
                "kind": doc.get("kind"), "name": doc.get("metadata", {}).get("name"),
                "accepted": ok, "error": None if ok else r.stderr.strip()[-500:],
            })

        for d in [dd for dd in docs if dd.get("kind") == "Namespace"]:
            apply_one(d, [])
        for d in explicit:
            apply_one(d, [])
        for d in implicit:
            apply_one(d, ["-n", throwaway_ns])

        return {
            "ran": True,
            "server_ok": not errors,
            "objects_total": total,
            "objects_accepted": accepted,
            "errors": [e[-1000:] for e in errors],
            "per_object": per_object,
            "implicit_namespace_refs_undeclared": referenced_ns,
        }
    finally:
        for ns in created:
            kubectl("delete", "namespace", ns, "--ignore-not-found")
        # kubectl delete namespace waits for the finalizer to run, but the apiserver can still
        # report the namespace as present for a moment after that call returns; poll briefly so
        # the NEXT eval_runner invocation (which may reuse the same manifest-declared namespace
        # name, e.g. "emojivoto") never collides with a namespace still in Terminating state.
        deadline = time.time() + 30
        while time.time() < deadline:
            remaining = [ns for ns in created
                        if kubectl("get", "namespace", ns).returncode == 0]
            if not remaining:
                break
            time.sleep(1)


PSS_VIOLATION = re.compile(r"(would violate|violates) PodSecurity", re.I)


def d2_pss(docs, run_id):
    """Highest Pod Security Standard every pod-bearing object satisfies. Each object is dry-run
    (namespace stripped) into a namespace labelled enforce+warn=<level>: Pods are rejected and
    workload templates produce a 'would violate PodSecurity' warning on violation."""
    pod_docs = [d for d in docs if isinstance(d, dict) and d.get("kind") in d2d3.POD_KINDS]
    if not pod_docs:
        return {"ran": False, "reason": "no pod-bearing objects"}
    per_level = {}
    for level in ("restricted", "baseline"):
        ns = f"pss-{level}-{run_id}"
        kubectl("create", "namespace", ns)
        try:
            kubectl("label", "namespace", ns, f"pod-security.kubernetes.io/enforce={level}",
                    f"pod-security.kubernetes.io/warn={level}", "--overwrite")
            violations = []
            for d in pod_docs:
                doc = json.loads(json.dumps(d))
                doc.setdefault("metadata", {}).pop("namespace", None)
                r = kubectl("apply", "--dry-run=server", "-n", ns, "-f", "-", input=yaml.safe_dump(doc))
                msg = r.stdout + r.stderr
                if PSS_VIOLATION.search(msg):
                    violations.append({"kind": d.get("kind"), "name": d["metadata"].get("name"),
                                       "detail": msg.strip()[-500:]})
            per_level[level] = violations
        finally:
            kubectl("delete", "namespace", ns, "--ignore-not-found", "--wait=false")
    level = "restricted" if not per_level["restricted"] else "baseline" if not per_level["baseline"] else "none"
    return {"ran": True, "level": level, "n_objects": len(pod_docs),
            "violations": {k: v for k, v in per_level.items()}}


def d4_requirements(docs, project):
    req_path = os.path.join(DATASETS, project, "requirements.py")
    if not os.path.exists(req_path):
        return {"ran": False, "reason": "no requirements.py for this project"}
    sys.path.insert(0, os.path.join(DATASETS, project))
    sys.path.insert(0, os.path.join(DATASETS, "common"))
    mod_name = f"requirements_{project}"
    spec = importlib.util.spec_from_file_location(mod_name, req_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    results = mod.check(docs)
    scored = [r for r in results if not r.get("oracle")]
    met = sum(1 for r in scored if r["passed"])
    return {
        "ran": True,
        "results": results,
        "requirements_met": met,
        "requirements_total": len(scored),
        "pct": round(100 * met / len(scored), 1) if scored else None,
    }


def out_name_for(source, project, variant=None, sample_k=None):
    return f"{source}__{project}" + (f"__{variant}__s{sample_k}" if variant else "")


def finish_reason(sample_dir):
    """Provider stop reason of the generation (Gemini finishReason, OpenAI-style finish_reason), or None for
    web-relayed replies. Lets blocked (RECITATION/SAFETY) and truncated (MAX_TOKENS/length) replies be reported."""
    try:
        raw = json.load(open(os.path.join(sample_dir, "response_raw.json"), encoding="utf-8"))["raw"]
    except (OSError, KeyError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    if raw.get("candidates"):
        return raw["candidates"][0].get("finishReason")
    if raw.get("choices"):
        return raw["choices"][0].get("finish_reason")
    return None


def evaluate(source, project, variant=None, sample_k=None, runtime=False):
    run_id = uuid.uuid4().hex[:8]
    raw_dir = os.path.join(RESULTS_DIR, "raw", out_name_for(source, project, variant, sample_k))
    docs, text, source_dir, parse_error = load_docs_for_source(source, project, variant, sample_k)

    record = {
        "project": project,
        "source": source,
        "prompt_variant": variant if source != "human" else None,
        "sample_k": sample_k if source != "human" else None,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    record["gen_finish_reason"] = finish_reason(source_dir) if source != "human" else None
    record["d1_parse_ok"] = parse_error is None
    record["d1_parse_error"] = parse_error
    record["d1_n_documents"] = len(docs)

    if parse_error is None:
        record["d1_kubeconform"] = d1_kubeconform(text)
        record["d1_server_dry_run"] = d1_server_dry_run(docs, run_id)
        static = d2d3.run_static(docs, text, raw_dir)
        record["loc"] = static["loc"]
        record["resource_counts"] = static["resource_counts"]
        record["d2"] = static["d2"]
        record["d2"]["pss"] = d2_pss(docs, run_id)
        record["d3"] = static["d3"]
        record["d4"] = d4_requirements(docs, project)
        if runtime:
            record["d5"], record["d6"] = d5d6.run_runtime(docs, project, run_id)
    else:
        for k in ("d1_kubeconform", "d1_server_dry_run", "d2", "d3", "d4", "d5", "d6"):
            record[k] = {"ran": False, "reason": "SKIPPED(parse_error)"}

    return record


def main():
    runtime = "--runtime" in sys.argv
    static_cached = "--reuse-static" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    source, project = args[0], args[1]
    variant = args[2] if len(args) > 2 else None
    sample_k = args[3] if len(args) > 3 else None

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_name = out_name_for(source, project, variant, sample_k)
    out_path = os.path.join(RESULTS_DIR, out_name + ".json")
    if static_cached and runtime and os.path.exists(out_path):
        # add D5/D6 to an existing static (D1-D4) record without re-running the static stages
        record = json.load(open(out_path, encoding="utf-8"))
        docs = load_docs_for_source(source, project, variant, sample_k)[0]
        if record["d1_parse_ok"]:
            record["d5"], record["d6"] = d5d6.run_runtime(docs, project, uuid.uuid4().hex[:8])
    else:
        record = evaluate(source, project, variant, sample_k, runtime)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

    kc = record["d1_kubeconform"]
    dr = record["d1_server_dry_run"]
    d4 = record["d4"]
    print(f"{out_name}: parse={'OK' if record['d1_parse_ok'] else 'FAIL'} "
          f"docs={record['d1_n_documents']} "
          f"kubeconform_valid={kc.get('valid')} "
          f"server_ok={dr.get('server_ok')} ({dr.get('objects_accepted')}/{dr.get('objects_total')}) "
          f"d4={d4.get('requirements_met')}/{d4.get('requirements_total')}")
    if record["d1_parse_ok"]:
        d2, d3 = record["d2"], record["d3"]
        print(f"    D2 kubescape={d2['kubescape'].get('compliance')} trivy={d2['trivy'].get('by_severity')} "
              f"pss={d2['pss'].get('level')} secrets={d2['secrets']['count']}")
        print(f"    D3 kube-score crit/warn={d3['kube_score'].get('critical')}/{d3['kube_score'].get('warning')} "
              f"polaris={d3['polaris'].get('score')} zhang={d3['kube_linter'].get('zhang_total')} "
              f"checklist={d3['checklist'].get('pct')}%")
    if record.get("d5", {}).get("ran"):
        d5, d6 = record["d5"], record["d6"]
        aliased = sum(1 for i in d5["images"] if str(i["served"]).startswith("alias:"))
        print(f"    D5 apply_ok={d5['apply_ok']} ready={d5.get('ready_ok')} ({d5.get('ready_replicas')}/"
              f"{d5.get('expected_replicas')}) t={d5.get('time_to_ready_s')}s smoke={d5.get('smoke_ok')} "
              f"reason={d5.get('failure_reason')} aliased_images={aliased}")
        if d6.get("ran"):
            for f in ("pod_delete", "container_crash"):
                print(f"    D6 {f}: " + "; ".join(
                    f"ok={x.get('recovery_ok')} t={x.get('recovery_time_s')} avail={x.get('availability_pct')}"
                    for x in d6[f]))
        else:
            print(f"    D6 {d6.get('reason')}")


if __name__ == "__main__":
    main()
