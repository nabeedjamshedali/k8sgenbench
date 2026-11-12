"""Redact Kubernetes-specific content from a project's own docs before it is given to any LLM.

Removes exactly what hands over a human implementation decision (an embedded manifest, or
deployment instructions), nothing else. Every redaction is reported so it can be logged.
"""
import re

K8S_KIND_RE = re.compile(
    r"^\s*kind:\s*(Deployment|StatefulSet|DaemonSet|Service|Ingress|ConfigMap|Secret|"
    r"PersistentVolumeClaim|PersistentVolume|Namespace|Job|CronJob|HorizontalPodAutoscaler|"
    r"PodDisruptionBudget|ServiceAccount|Role|RoleBinding|ClusterRole|ClusterRoleBinding)\s*$",
    re.MULTILINE | re.IGNORECASE,
)
FENCE_DELIM_RE = re.compile(r"^(```+)\s*(\S*)\s*$")
KUBECTL_MANIFEST_RE = re.compile(
    r"^.*\bkubectl\s+(apply|create|delete|replace|edit|patch|scale|rollout|expose)\b.*$",
    re.MULTILINE | re.IGNORECASE,
)
KUBECTL_ANY_RE = re.compile(
    r"\bkubectl\s+(apply|create|delete|replace|edit|patch|scale|rollout|expose|get)\b", re.IGNORECASE
)
KUBECTL_OUTPUT_TABLE_RE = re.compile(
    r"^\s*NAME\s+.*\b(TYPE|CLUSTER-IP|EXTERNAL-IP|READY|STATUS|RESTARTS|PORT\(S\))\b",
    re.MULTILINE | re.IGNORECASE,
)
K8S_HEADING_RE = re.compile(
    r"^(#{1,6})\s*(.*(?:kubernetes|k8s).*)$", re.MULTILINE | re.IGNORECASE
)
DEPLOYMENT_SECTION_TRIGGER = re.compile(
    "|".join(p.pattern for p in (KUBECTL_ANY_RE, KUBECTL_OUTPUT_TABLE_RE)), re.IGNORECASE | re.MULTILINE
)

MANIFEST_PLACEHOLDER = "[Kubernetes manifest removed from this bundle]"
SECTION_PLACEHOLDER = "[Kubernetes deployment instructions removed from this bundle]"


def redact_fenced_manifests(text):
    """Replace fenced code blocks that embed a Kubernetes manifest with a placeholder.

    Scanned line by line (not with a single regex across the whole document): a fence can open
    with any info string (```yaml, ```bash, ```prometheus, bare ```, ...), and a single regex that
    only recognised a `yaml` tag was previously treating an unrelated ```bash opening elsewhere in
    the file as this block's *closing* delimiter, silently merging blocks and losing the match.
    """
    lines = text.split("\n")
    out, hits = [], []
    in_fence, fence_len, open_line, body = False, 0, None, []
    for line in lines:
        m = FENCE_DELIM_RE.match(line)
        if not in_fence and m:
            in_fence, fence_len, open_line, body = True, len(m.group(1)), line, []
            out.append(line)
        elif in_fence and m and len(m.group(1)) >= fence_len:
            joined = "\n".join(body)
            if "apiVersion:" in joined or K8S_KIND_RE.search(joined):
                hits.append(joined)
                out.append(MANIFEST_PLACEHOLDER)
            else:
                out.extend(body)
            out.append(line)
            in_fence = False
        elif in_fence:
            body.append(line)
        else:
            out.append(line)
    if in_fence:  # unterminated fence: emit what we buffered rather than dropping it
        out.append(open_line)
        out.extend(body)
    return "\n".join(out), hits


def redact_kubectl_lines(text):
    """Replace standalone lines that apply/create/delete a manifest with a placeholder."""
    hits = [m.group(0) for m in KUBECTL_MANIFEST_RE.finditer(text)]
    return KUBECTL_MANIFEST_RE.sub(SECTION_PLACEHOLDER, text), hits


def redact_k8s_sections(text):
    """Replace the body of any deployment-walkthrough section with a placeholder.

    A section is redacted if its heading mentions Kubernetes/K8s, OR its own body (not counting
    any subsections, which are each checked independently) contains a manifest-affecting `kubectl`
    command (apply/create/delete/replace/edit/patch/scale/rollout/expose/get) or a `kubectl get`
    output table (NAME/TYPE/CLUSTER-IP/READY/...). The content trigger matters: some tutorials
    (e.g. the Kubernetes docs' own WordPress+MySQL page) walk through `kubectl apply`/`kubectl get
    services` with live output under a heading like "Apply and Verify" that never says the word
    "Kubernetes". Read-only diagnostic verbs (`top`, `logs`, `describe`, `exec`, ...) are
    deliberately excluded: they reveal nothing about Service types, replica counts or NodePorts,
    and including them cost real prose (P10's only mention of the metrics-scraper sidecar was lost
    to an adjacent, unrelated `kubectl top pod` tip before this was narrowed).

    Deliberately scoped to the SMALLEST triggered unit (a heading's own body, stopping at its
    first subheading), never expanded to swallow whole subtrees: a page whose own purpose is a
    Kubernetes install guide (e.g. Grafana's or the Dashboard's official docs) is titled
    "Kubernetes" at the top level, and expanding the match to the end-of-document would redact
    every fact on the page, not just the deployment instructions.
    """
    lines = text.split("\n")
    all_heads = [(i, len(m.group(1))) for i, line in enumerate(lines)
                 for m in [re.match(r"^(#{1,6})\s", line)] if m]
    if not all_heads:
        return text, []
    removed = []
    out = list(lines)
    for idx, (i, _level) in enumerate(all_heads):
        end = all_heads[idx + 1][0] if idx + 1 < len(all_heads) else len(lines)
        body = "\n".join(lines[i + 1:end])
        if body.strip() == SECTION_PLACEHOLDER:
            continue
        triggered = K8S_HEADING_RE.match(lines[i]) or DEPLOYMENT_SECTION_TRIGGER.search(body)
        if triggered and body.strip():
            removed.append(body.strip())
            out[i + 1:end] = [SECTION_PLACEHOLDER] + [None] * (end - i - 2)
    out = [l for l in out if l is not None]
    return "\n".join(out), removed


def redact(text, extra_patterns=()):
    """Run all redaction passes. `extra_patterns` is a list of (regex, reason) for project-specific
    facts (e.g. a NodePort mentioned in prose) found during review; each match is replaced with
    "[redacted]" and reported.
    """
    log = []
    text, hits = redact_fenced_manifests(text)
    log += [("embedded Kubernetes manifest", h) for h in hits]
    text, hits = redact_k8s_sections(text)
    log += [("Kubernetes-headed section", h) for h in hits]
    text, hits = redact_kubectl_lines(text)
    log += [("kubectl apply/create/delete line (outside a Kubernetes-headed section)", h) for h in hits]
    for pattern, reason in extra_patterns:
        hits = re.findall(pattern, text)
        if hits:
            text = re.sub(pattern, "[redacted]", text)
            log += [(reason, h if isinstance(h, str) else str(h)) for h in hits]
    return text, log
