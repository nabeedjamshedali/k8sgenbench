# Dataset authoring guide and review checklist

Each project lives in `datasets/Pxx_<slug>/`. `P04_voting-app/` is the reference example.

## Why there is no spec.md anymore

An earlier version of this dataset gave every LLM a `spec.md` that the research team compiled
from the repository. That still risked a bias confound: the compiler's wording and selection could
vary by project, and because an LLM (Claude) helped compile it, a reviewer could reasonably suspect
the comparison secretly favoured that model family. So the compiled spec is gone. Every LLM now
receives the project's own documentation, copied verbatim, with Kubernetes-specific content
redacted. No sentence given to a model is written by us or by any LLM.

## Files

Each project folder is split so that "what a model sees" and "what runs the benchmark" are
visually separate from "internal reference material that defends a check if it's challenged":

| File | Content | Given to the LLMs? |
|---|---|---|
| `docs_bundle/` | The project's own README, Dockerfile(s), docker-compose file(s), `.env.example` — copied verbatim at the pinned commit, Kubernetes content redacted | **Yes — this is the only project-specific model input** |
| `human/` | The maintainers' manifests at the pinned commit, unmodified | No |
| `requirements.py` | D4 checks, each traceable to a file included in `docs_bundle/` | No (runs against every generated config) |
| `smoke.json` | D5 functional checks and the D6 probe target | No (runs against every deployed config) |
| `internal/fact_sheet.md` | Internal reference listing the application's requirements (renamed from the old `spec.md`) | No |
| `internal/provenance.md` | Source file and line for every fact in `fact_sheet.md` | No |
| `internal/redaction_log.md` | Every redaction made to `docs_bundle/`: file, lines, one-line reason | No |
| `internal/meta.json` | Repository, commit, licence, class, intent label with quoted evidence, `docs_bundle_files`, reviewer | No |

`docs_bundle/`, `human/`, `requirements.py` and `smoke.json` are the benchmark's working parts.
Everything under `internal/` is reference material: it justifies and audits the other four, but
nothing in it is ever read by a model or by the evaluation pipeline.

## Building `docs_bundle/`

Use `datasets/build_docs_bundle.py <project>`. It takes the same kind of file list `deploy_check.py`
uses, copies each file from the cache unmodified, then runs the redaction passes in
`datasets/common/redact.py` and writes `internal/redaction_log.md`. Nothing in the bundle is
written by a person or a model — a file is included whole or excluded whole, except for the
specific redactions below.

### What gets redacted, and why

Within an included file, remove only content that hands over a human implementation decision:
1. **Embedded Kubernetes manifests** — a fenced code block containing `apiVersion:` or a `kind:` of
   a Kubernetes resource. Replaced with `[Kubernetes manifest removed from this bundle]`.
2. **"Run on Kubernetes" / install sections** whose content is deployment commands
   (`kubectl apply|create -f ...`, NodePort numbers, replica counts, Service types). Replaced with
   `[Kubernetes deployment instructions removed from this bundle]`.
3. **Individual facts elsewhere** that match the project's "excluded facts" list (e.g. a NodePort
   mentioned in prose). Struck in place with `[redacted]`, not the whole paragraph.

Everything else stays exactly as written, including facts the model needs (ports, env vars,
dependencies, persistence). `internal/redaction_log.md` records every redaction with file, line
range and a one-line reason, so a reviewer can confirm nothing else was touched.

## Rules for `internal/fact_sheet.md`

Same content rule the old `spec.md` had — it exists to justify `requirements.py` and `smoke.json`
and to brief the reviewer, never to be shown to a model:
1. the application's purpose;
2. each component's image (exactly as the project publishes it) and role;
3. the ports each component listens on;
4. required and important optional environment variables, with their meaning and any value that other components depend on;
5. dependencies between components, including hostnames that are fixed in application code;
6. persistence needs (which path holds data that must survive restarts);
7. which components must be reachable from outside the cluster;
8. health endpoints, if the application exposes them;
9. permissions the application needs from the Kubernetes API, if any, described in terms of what the application does (for example "lists and watches pods in all namespaces").

It must **not** contain decisions taken in the human manifests: replica counts, probe settings, resource requests or limits, securityContext, Service types, NodePort numbers, update strategy, PDB/HPA, labels, object names (except hostnames fixed in code), or RBAC rules copied from the manifests.

## Provenance rule

Every fact in `internal/fact_sheet.md` must cite a **non-manifest** source in the repository at the pinned commit, and that source file must actually be present, unredacted, in `docs_bundle/`. A fact that appears only in the human Kubernetes YAML is left out of both and listed under "Excluded facts". Upstream defaults (for example PostgreSQL listening on 5432) may be cited as the image's documented default.

## Rules for `requirements.py`

- Each check corresponds to a sentence in `internal/fact_sheet.md`; nothing else is checked.
- Components are found by image (`datasets/common/reqlib.py`), never by object name, except hostnames the code requires.
- The checks are run unchanged on the human manifests and on every LLM output.

### The `oracle` flag

Some facts a project's own maintainers hardcode (an exact env var name, a Secret/ConfigMap name,
an RBAC rule, a seed file's content) live only in application source code that is deliberately not
part of `docs_bundle/` — bundling full source would stop being a realistic developer-facing input.
A model has no way to discover such a fact, so grading it on that check would not measure its
Kubernetes-generation ability, only whether it happened to guess a name it was never given.

Every `Checker` method and `check()` itself take an `oracle=False` kwarg. Mark a check
`oracle=True` only when its expected value is confirmed absent from that project's finalized
`docs_bundle/` (grep for it before tagging, don't assume). Oracle checks still run — they are
useful diagnostically, and some fail interestingly even for the human manifest — but they are
excluded from the primary "% requirements met" D4 score reported in the paper.

Self-consistency checks (e.g. "does the Service name the model put in an env var actually match a
Service the model itself created") are never oracle, regardless of how obscure the hostname is:
the model controls both sides of the comparison, so no hidden fact is required to pass.

If an oracle candidate turns out to be a near-universal convention (e.g. the official Postgres
image's `POSTGRES_PASSWORD`, or a port repeated across every sibling Dockerfile in the same
bundle), it is left untagged — that knowledge is reasonably already in a general-purpose model's
training data, not something specific to the project under test.

## Rules for `smoke.json`

- HTTP checks name a target by image and container port; the runner finds the Service that routes to it.
- At least one check should exercise real functionality (for example, store data and read it back), not only a landing page.
- `d6_target` is the user-facing endpoint probed during fault injection.

## Intent label

- `production`: the maintainers present the manifest as the supported way to install the software for real use.
- `demo`: the maintainers call it an example, tutorial, demo or sample, or say it is not for production.
- The label must be supported by a verbatim quote with file and line in `internal/meta.json`.

## Review checklist (second group member)

For each project, tick every item, then set `spec_reviewed_by` in `internal/meta.json` to your name.

- [ ] Every file in `docs_bundle/` is an unmodified copy of a file in the repository at the pinned commit (diff it against the cache).
- [ ] Every redaction in `internal/redaction_log.md` actually removes implementation content, and nothing else was changed.
- [ ] `docs_bundle/` contains no fenced block with `apiVersion:`, no `kubectl apply/create -f`, no NodePort number, no replica count, no Service type.
- [ ] Every sentence in `internal/fact_sheet.md` has a row in `internal/provenance.md`, and the cited file is present (unredacted at that point) in `docs_bundle/`.
- [ ] `internal/fact_sheet.md` contains no replica count, probe setting, resource value, securityContext, Service type, NodePort, label or object name taken from `human/`.
- [ ] Each check in `requirements.py` corresponds to a sentence in `internal/fact_sheet.md`.
- [ ] The intent label in `internal/meta.json` matches the quoted evidence.
