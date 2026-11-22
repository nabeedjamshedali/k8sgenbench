"""Build docs_bundle/ and redaction_log.md for a project: the project's own README, Dockerfile(s)
and compose file(s), copied verbatim from the cache and redacted of Kubernetes-specific content.

This is the ONLY project-specific input any LLM receives (see datasets/SPEC_GUIDE.md).

Usage: python datasets/build_docs_bundle.py <project>
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "common"))
from redact import redact

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache")

# folder -> list of (cache-relative path, published name under docs_bundle/, extra redaction
# patterns as [(regex, reason), ...] for project-specific facts found during review)
BUNDLES = {
    "P02_n8n": ("n8n", [
        ("README.md", "README.md", []),
        ("kubernetes/README.md", "kubernetes-README.md", []),
        ("docker-compose/withPostgres/docker-compose.yml", "docker-compose-withPostgres.yml", []),
        ("docker-compose/withPostgres/.env", "withPostgres.env", []),
        ("docker-compose/withPostgres/init-data.sh", "init-data.sh", []),
    ]),
    "P03_grafana": ("grafana", [
        ("docs/sources/setup-grafana/installation/kubernetes/index.md", "README.md", []),
        ("conf/defaults.ini", "defaults.ini", []),
        ("Dockerfile", "Dockerfile", []),
    ]),
    "P04_voting-app": ("voting-app", [
        ("README.md", "README.md", []),
        ("docker-compose.yml", "docker-compose.yml", []),
        ("docker-compose.images.yml", "docker-compose.images.yml", []),
        ("vote/Dockerfile", "vote.Dockerfile", []),
        ("result/Dockerfile", "result.Dockerfile", []),
        ("worker/Dockerfile", "worker.Dockerfile", []),
    ]),
    "P05_emojivoto": ("emojivoto", [
        ("README.md", "README.md", []),
        ("docker-compose.yml", "docker-compose.yml", []),
        ("Dockerfile-multi-arch", "Dockerfile-multi-arch", []),
    ]),
    "P06_wordsmith": ("wordsmith", [
        ("README.md", "README.md", []),
        ("docker-compose.yml", "docker-compose.yml",
         [(r"replicas:\s*5", "excluded fact: api replica count (also in README, excluded per the no-replica-count rule)")]),
        ("api/Dockerfile", "api.Dockerfile", []),
        ("web/Dockerfile", "web.Dockerfile", []),
    ]),
    "P07_online-boutique": ("online-boutique", [
        ("README.md", "README.md", []),
        ("src/frontend/Dockerfile", "frontend.Dockerfile", []),
        ("src/adservice/Dockerfile", "adservice.Dockerfile", []),
        ("src/cartservice/src/Dockerfile", "cartservice.Dockerfile", []),
        ("src/checkoutservice/Dockerfile", "checkoutservice.Dockerfile", []),
        ("src/currencyservice/Dockerfile", "currencyservice.Dockerfile", []),
        ("src/emailservice/Dockerfile", "emailservice.Dockerfile", []),
        ("src/loadgenerator/Dockerfile", "loadgenerator.Dockerfile", []),
        ("src/paymentservice/Dockerfile", "paymentservice.Dockerfile", []),
        ("src/productcatalogservice/Dockerfile", "productcatalogservice.Dockerfile", []),
        ("src/recommendationservice/Dockerfile", "recommendationservice.Dockerfile", []),
        ("src/shippingservice/Dockerfile", "shippingservice.Dockerfile", []),
    ]),
    "P08_sock-shop": ("sock-shop", [
        ("README.md", "README.md", []),
        ("deploy/docker-compose/docker-compose.yml", "docker-compose.yml", []),
    ]),
    "P09_teastore": ("teastore", [
        ("README.md", "README.md", []),
        ("GET_STARTED.md", "GET_STARTED.md", []),
        ("examples/docker/docker-compose_default.yaml", "docker-compose_default.yaml", []),
    ]),
    "P10_k8s-dashboard": ("dashboard", [
        ("README.md", "README.md", []),
        ("docs/common/dashboard-arguments.md", "dashboard-arguments.md", []),
        ("docs/user/integrations.md", "integrations.md", []),
    ]),
    "P12_headlamp": ("headlamp", [
        ("README.md", "README.md", []),
        ("docs/installation/in-cluster/index.md", "in-cluster-install.md", []),
        ("Dockerfile", "Dockerfile", []),
    ]),
}


def build(project):
    cache_dir, files = BUNDLES[project]
    out_dir = os.path.join(HERE, project, "docs_bundle")
    internal_dir = os.path.join(HERE, project, "internal")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(internal_dir, exist_ok=True)
    log_lines = [f"# Redaction log: {project}\n",
                 "Every redaction made to docs_bundle/, so a reviewer can confirm nothing else was changed.\n"]
    included = []
    for rel, published, extra in files:
        src = os.path.join(CACHE, cache_dir, rel)
        if not os.path.exists(src):
            print(f"  MISSING: {rel}")
            continue
        text = open(src, encoding="utf-8", errors="replace").read()
        redacted, hits = redact(text, extra)
        dest = os.path.join(out_dir, published)
        open(dest, "w", encoding="utf-8").write(redacted)
        included.append(rel)
        log_lines.append(f"\n## {rel} -> docs_bundle/{published}\n")
        if hits:
            for reason, snippet in hits:
                one_line = " ".join(snippet.split())[:200]
                log_lines.append(f"- **{reason}**: `{one_line}`\n")
        else:
            log_lines.append("- no redactions\n")
    open(os.path.join(internal_dir, "redaction_log.md"), "w", encoding="utf-8").write("".join(log_lines))
    print(f"{project}: {len(included)} file(s) -> {out_dir}")
    for f in included:
        print(f"  {f}")


if __name__ == "__main__":
    for name in sys.argv[1:] or BUNDLES:
        build(name)
