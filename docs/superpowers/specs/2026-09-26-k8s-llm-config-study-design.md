# Design Spec — Reliability and Security Analysis of LLM-Generated Kubernetes Configurations

**Date:** 2026-09-26 (revised 2026-10-18: fairness of the human comparison, two prompt variants, RQ5)
**Status:** Approved
**Deliverable:** CEP research paper (course template, Overleaf) backed by real experiments
**Next milestone:** Dataset (12 projects, specs, requirement checks)

---

## 1. Goal

Produce empirical evidence on how Kubernetes (K8s) configurations **generated from scratch by LLMs** compare with **human-written configurations of the same real projects**, and how LLMs compare with each other. The LLMs are the subjects under test. Deterministic tools and runtime experiments are the measuring instruments.

### Research gap (from `papers/LITERATURE_INDEX.md`)
- **Zhang et al. (MSR 2024):** 98 ChatGPT manifests collected from DevGPT in 2023. Prompts were uncontrolled, and the study used one model, one tool (KubeLinter) and static analysis only. Its future work explicitly asks for "a comparative evaluation of generative AI techniques".
- **Tabibpour & Dakhilalian (JCS 2026):** compares humans with that 2023 ChatGPT corpus. The corpora are unmatched, one tool is used, and nothing is executed. Its limitations list newer models, more tools and deployment-based validation as future work.
- **CloudEval-YAML, IaC-Eval, IaCGen, FDE-Bench:** curated tasks with no human baseline from real projects, and no security or recovery evaluation.
- **GenKubeSec, LLMSecConfig, KubeGuard, KuTIE:** use LLMs to *detect, repair or harden* manifests, not to generate them.

**Our contribution:** the first *project-matched* comparison of human-written manifests against 6 current LLMs, using identical controlled specs and a 6-dimension benchmark that runs from schema validity through security, reliability and requirement satisfaction to real deployment and pod-kill recovery.

### 1.1 Fairness of the human comparison

The human developers and the LLMs did not work under identical conditions.

| | Human developer | LLM |
|---|---|---|
| Goal | often a demo, tutorial or local setup | whatever our prompt asks for |
| Process | iterative: reviews, fixes and incidents over time | a single attempt with no feedback |
| Context | the full repository and team knowledge | the project's own `docs_bundle/` only |

The goal difference favours the LLM if we ask it for "production-ready" output. The process and context differences favour the human. The design therefore controls for these differences instead of ignoring them:

1. **Framing.** The human manifest is a **real-world reference point** ("what projects actually ship"), not an opponent in a controlled race. The paper never claims that LLMs are better or worse than human engineers in general. Claims are always of the form "compared with the manifests shipped by these projects".
2. **Matched goal.** The human comparison (RQ1) uses the **neutral** prompt, which, like the human's situation, carries no extra push towards production hardening. The production prompt is analysed separately (RQ5).
3. **Intent stratification.** Each human manifest is labelled `production` or `demo` from the repository's own wording (README, docs and directory names), with the evidence quoted in `meta.json`. RQ1 is reported separately per label.
4. **No compiled spec; the project's own documents instead.** An earlier design gave each LLM a `spec.md` that the research team compiled from the repository. That still risks a confound: the compiler's wording and selection could differ by chance from one project to the next, and because the team used an LLM (Claude) to help compile it, a reviewer could reasonably suspect the comparison secretly favours that model family. The design therefore drops the compiled spec. Each LLM instead receives a `docs_bundle/`: the project's own README, Dockerfile(s) and `docker-compose.yml`/`.env.example` **copied verbatim** at the pinned commit, with only Kubernetes-specific content redacted (§4.4). No sentence in the bundle is written by us or by any LLM; every word is the maintainers'. A `fact_sheet.md` (renamed from the old `spec.md`) and `provenance.md` remain as internal documents — they justify `requirements.py` and `smoke.json` and are not shown to any model.
5. **The LLM-vs-LLM comparison (RQ3, RQ5) is fully controlled:** identical docs bundle, prompt, parameters and pipeline.
6. **Reporting.** The asymmetry and these mitigations are stated in Threats to Validity.

**Optional (only if time allows):** a *human-from-docs* baseline, where group members write manifests for 3–4 projects using only the project's `docs_bundle/` and the neutral prompt, under the same conditions as the LLMs.

---

## 2. Research Questions

| RQ | Question | Answered by |
|---|---|---|
| **RQ1** | How do LLM-generated K8s configurations compare with the human-written configurations shipped by the same projects in correctness, security, reliability, requirement satisfaction and runtime behaviour? | D1–D6, Human vs each model, **neutral prompt**, stratified by human manifest intent (production/demo) |
| **RQ2** | Which errors and misconfigurations occur most frequently in LLM-generated configurations? | Finding taxonomy (Rahman et al.'s 11 categories), plus KubeLinter's 6 smells compared with Zhang et al.'s 2023 numbers |
| **RQ3** | How do LLMs differ from one another in the type and frequency of problems, and how consistent is each model across repeated samples? | Per-model distributions; intra-model variance across 3 samples |
| **RQ4** | How reliably do LLM configurations deploy and recover in a real cluster compared with human configurations, and do static findings predict runtime outcomes? | D5, D6; correlation between static scores and runtime success |
| **RQ5** | Does explicitly asking for production-ready output change the security and reliability of LLM-generated configurations? | Paired comparison, neutral vs production prompt, for the same model, project and sample index |

---

## 3. Scope

**In scope:** dataset of 12 projects; generation with 6 LLMs × 2 prompt variants × 3 samples; automated evaluation pipeline; statistical analysis; figures; LaTeX paper.

**Out of scope (YAGNI):**
- web UI or dashboard;
- automatic YAML repair or iterative regeneration;
- agentic/tool-using generation;
- Helm charts and Kustomize overlays as *generation targets*. Human baselines that use Kustomize are rendered to plain YAML first.

**Optional (only if time allows):** the human-from-spec baseline (§1.1).

---

## 4. Dataset

### 4.1 Selection criteria
A project is included only if **all** of these hold:
1. The official repository contains **plain K8s YAML written by the maintainers** (or Kustomize that renders to it).
2. **All container images are public** and pullable without credentials. This is required for D5 and D6.
3. The app is runnable on the local **kind** cluster (see §7) with no cloud-specific dependencies (after documented substitutions).
4. The license permits redistribution of the manifests in our artefact, or we store only the commit SHA and a fetch script.
5. The selection covers a **complexity mix**: at least 3 projects from each class in §4.2 (stateful/database-backed, multi-service, large microservice systems), and **both manifest intents** (production and demo). The aim is at least 4 production-intent projects, so that the production stratum of RQ1 is not empty.
6. It includes at least 3 **less-popular** repositories, to reduce the risk of training-data contamination.
7. **It is a real application, not a toy** (instructor requirement). "Hello-world" or single-container demo apps are excluded. Every project must have at least one of the following: two or more cooperating components, persistent state (a database or volume), or real application functionality (e.g., a CMS, an e-commerce shop or a workflow engine).

### 4.2 Candidate pool (each must be verified against §4.1 during the dataset phase; final 12 chosen from these)

Toy apps (e.g., `hello-app`) were removed from the pool per criterion 7.

| Class | Candidates |
|---|---|
| Stateful / database-backed apps | kubernetes/examples WordPress + MySQL; n8n + PostgreSQL (n8n-io/n8n-kubernetes-hosting); Keycloak (keycloak-quickstarts K8s manifests); Grafana (official K8s install manifest with PVC); kubernetes/examples Cassandra StatefulSet |
| Multi-service apps | dockersamples/example-voting-app `k8s-specifications` (5 components incl. Redis + Postgres); kubernetes/examples Guestbook (PHP + Redis leader/follower); linkerd/emojivoto (3 gRPC services); istio Bookinfo (4 polyglot services, plain `bookinfo.yaml`, no mesh); dockersamples/k8s-wordsmith-demo (Java API + Go web + Postgres) |
| Large microservice systems | GoogleCloudPlatform/microservices-demo (Online Boutique, 11 services); Sock Shop `complete-demo.yaml`; DescartesResearch TeaStore (7 services) |
| Production-grade single service (max 1) | stefanprodan/podinfo (probes, metrics and config used as the Flux/Flagger reference app). Include only if it's needed to cover the stateless class. |

### 4.3 Per-project layout
```
datasets/P01_<name>/
  meta.json         # repo URL, commit SHA, license, class, popularity (stars), fetch date,
                    # manifest_intent (production|demo) + quoted evidence, spec_reviewed_by,
                    # docs_bundle_files (list of source paths included)
  docs_bundle/      # the project's own README, Dockerfile(s), compose file(s), .env.example —
                    # copied verbatim at the pinned commit, Kubernetes content redacted (§4.4).
                    # This is the ONLY project-specific input any LLM receives.
  redaction_log.md  # every redaction made to docs_bundle/: file, lines, one-line reason
  fact_sheet.md     # internal reference (renamed from the old `spec.md`); NOT given to LLMs
  provenance.md     # source file/line in the repo for every fact in fact_sheet.md; NOT given to LLMs
  requirements.py   # D4 assertions, each traceable to a file included in docs_bundle/
  human/            # original manifests at pinned SHA (rendered to plain YAML if Kustomize)
  smoke.json        # which Service/port/path to hit for the D5 functional smoke test
```

### 4.4 Docs-bundle rules (no baseline leakage)
`docs_bundle/` is built, not written: it holds unmodified copies of the project's own non-manifest
files (README/docs, Dockerfile, docker-compose, `.env.example`) at the pinned commit. Nobody writes
prose for it; a file is either included whole or excluded whole, except for the redactions below.

**Redaction rule.** Within an included file, remove only content that hands over a human
implementation decision:
- any embedded Kubernetes manifest (a fenced block containing `apiVersion:` or a `kind:` of a
  Kubernetes resource) — replaced with a one-line placeholder;
- any "Run on Kubernetes" / install section whose content is deployment commands
  (`kubectl apply|create -f ...`, NodePort numbers, replica counts, Service types) — replaced with
  a one-line placeholder;
- an individual sentence or number elsewhere that states a fact already on the "excluded facts"
  list below (e.g. a NodePort value mentioned in prose) — struck in place, not the whole paragraph.

Every redaction is logged in `redaction_log.md` with the file, the line range and a one-line reason,
so a reviewer can confirm nothing else was removed.

**Excluded facts** (must not survive redaction into `docs_bundle/`, and must not appear in
`fact_sheet.md` either): replica counts, probe settings, resource values, securityContext, Service
types, update strategy, PDB/HPA, labels or object names — i.e. anything that is a decision taken in
the human YAML and documented nowhere else.

`fact_sheet.md` keeps the same content rule the old `spec.md` had — application purpose, each
component's image and tag, ports, required environment variables, dependencies, persistence needs,
external reachability, health endpoint if any — but it now exists only to justify `requirements.py`
and `smoke.json` and to brief the reviewer; it is never shown to a model. Every fact in it must be
traceable to a file that is actually present, unredacted, in `docs_bundle/` (`provenance.md` records
the file and line). A fact found only in the human K8s YAML is excluded from both.

Every project's `docs_bundle/` and `fact_sheet.md` are reviewed by a second group member against
this checklist and signed off in `meta.json` (`spec_reviewed_by`).

---

## 5. Generation

### 5.1 Models (5, originally planned as 6 — see the free-tier access substitutions bullet
under Threats to Validity, §9, for the substitution story and the dropped Llama slot)

| Slot | Provider (as planned) | Actual access (2026-11-08) |
|---|---|---|
| GPT | OpenAI flagship, OpenAI API | ChatGPT Pro web UI, manual relay (piloted on `gpt-oss-120b`/Groq first) |
| Claude | Anthropic flagship, Anthropic API | Claude Code subagent (no API key) |
| Gemini | Google flagship, Gemini API | Gemini API, flash tier (`gemini-3.6-flash`) |
| ~~Open-1~~ | ~~Llama, Groq / OpenRouter~~ | **dropped — no working free route found** |
| Open-2 | Qwen coder model, OpenRouter | Groq (free), small projects only |
| Open-3 | DeepSeek chat model, DeepSeek API / OpenRouter | DeepSeek web chat, manual relay |

Exact model IDs are **pinned in `generation/models.yaml` at run time** and reported in the paper along with the generation dates.

**Terminology:** the paper calls Open-1/2/3 **open-weight** models, not "open-source". Their weights are public (DeepSeek-V3/R1 under MIT, Qwen under Apache-2.0, Llama under the Llama Community License), but their training data and code are not fully released.

### 5.2 Prompt
- **System prompt (fixed):** "You are an experienced DevOps engineer. Respond with Kubernetes YAML manifests only."
- **User prompt: two fixed variants.** They differ only in the final instruction sentence. Both
  concatenate the files in `docs_bundle/` (each preceded by its filename, in a fixed order) in
  place of a written specification:
  - **`neutral`** (matches the human condition; used for RQ1–RQ4): the project's `docs_bundle/`,
    then *"Write Kubernetes manifests to deploy this application. Output all manifests in a single
    YAML code block."*
  - **`production`** (used for RQ5): the project's `docs_bundle/`, then *"Write production-ready
    Kubernetes manifests to deploy this application. Output all manifests in a single YAML code
    block."*
- The instruction sentences are identical for every model and project and are stored at
  `generation/prompts/{neutral,production}.md`; the bundle content varies only by project, never by
  model.

### 5.3 Parameters
- 3 independent samples per (model, project, prompt variant).
- Temperature 0.2 and max output tokens 8,192.
- If a model does not accept `temperature` (e.g., reasoning models), use the provider default and record the deviation.
- No retries on content. Retries happen **only** on transport errors (HTTP 429/5xx), with backoff.

### 5.4 Totals
As originally planned: 12 projects × 6 models × 2 prompt variants × 3 samples = **432 LLM
configurations**, plus **12 human** = **444 evaluated configurations**, at an estimated API cost
of about $10–20 (roughly 2 million tokens in total).

**Actual, as of 2026-11-08** (see the free-tier substitutions bullet under Threats to Validity,
§9): 5 models, not 6 (Llama dropped). Project scope (full 12 vs. a reduced subset) has not yet
been finalized — the instructor suggested 4-5 projects may be sufficient to answer RQ1-RQ5, with
results "replicated" to the remaining projects qualitatively rather than exhaustively evaluated.
This decision, and its effect on the totals above, is tracked in `PROGRESS.md` and still pending.

### 5.5 Stored per generation (`generation/outputs/<model>/<project>/<variant>/s<k>/`)
- `request.json`: model ID, parameters, prompt hash, timestamp
- `response_raw.json`: full provider response, including usage and latency
- `manifest.yaml`: YAML extracted from the code block. The extraction rule is deterministic: the first fenced YAML block, else the whole text. Nothing else is modified.
- `extraction.json`: extraction status and notes

---

## 6. Benchmark — K8sGenBench (6 dimensions)

**Principles:** deterministic tools only, with no LLM-as-judge. Two tools per dimension wherever possible. Tool versions and the K8s version are pinned.

| # | Dimension | Instruments | Metrics |
|---|---|---|---|
| **D1** | Correctness | PyYAML parse → **kubeconform** (strict, pinned K8s version schemas) → **`kubectl apply --dry-run=server`** on kind | parse rate, schema pass rate, API-acceptance rate, error taxonomy |
| **D2** | Security | **Kubescape** (NSA-CISA and MITRE frameworks); **Trivy config**; **Pod Security Standards** checked by server dry-run into namespaces labelled `enforce=baseline` / `enforce=restricted`; hardcoded-secret regex check | findings per config by severity; Kubescape compliance %; highest PSS level passed; findings mapped to Rahman et al.'s 11 categories |
| **D3** | Reliability (static) | **kube-score**; **Polaris**; **KubeLinter** (including Zhang et al.'s 6 smells); **Reliability Controls Checklist** (below) | kube-score critical/warning counts; Polaris score; KubeLinter smell density/proportion; checklist coverage % |
| **D4** | Requirement satisfaction | per-project `requirements.py` assertions derived from `fact_sheet.md` | % requirements met |
| **D5** | Runtime deployment | kind cluster, fresh namespace per config | apply success; time-to-Ready; Ready/expected replicas; functional smoke test (HTTP 200 via port-forward); failure reason (CrashLoopBackOff, ImagePullBackOff, Pending, probe failure, timeout) |
| **D6** | Resilience | two fault types, each repeated 3× per config, with a 5 Hz HTTP prober pod **inside the cluster** calling the Service. **F1 pod-delete:** force-delete a Ready pod (Chaos Mesh "pod-kill" semantics), so the Deployment must replace it. **F2 container-crash:** stop the container at node level (`crictl stop --timeout 0`), so the kubelet must restart it and probes govern traffic. The victim is always a Ready, non-terminating pod. Recovery means a new or restarted pod is Ready and serving, measured from live pod state rather than Deployment status. The availability window runs from the kill to recovery + 5 s. | recovery success; recovery time (s); availability during recovery (% successful probes) |

**Reliability Controls Checklist (D3), applied to each workload.** Each item scores 1 or 0, or N/A where it doesn't apply:
1. replicas ≥ 2 (stateless workloads)
2. readinessProbe
3. livenessProbe
4. CPU request
5. memory request
6. memory limit
7. explicit rolling-update strategy
8. PodDisruptionBudget
9. anti-affinity or topologySpreadConstraints
10. pinned image tag (not `latest` or missing)

**Secondary measures:**
- structural similarity to the human YAML (Jaccard over normalised key paths), used as a contamination indicator;
- lines of YAML and number of resources by kind;
- tokens and latency.

**Composite score:** none. Dimensions are reported separately, and a normalised per-model radar chart is used for visual summary only.

---

## 7. Evaluation Pipeline

```
manifest.yaml ─► D1 parse ─► D1 kubeconform ─► D2/D3 static scanners ─► D4 requirements
                                                                              │
                        D1 server dry-run (+PSS) ◄────────────────────────────┘
                                │
                                ▼
                        D5 deploy on kind ─► D5 smoke test ─► D6 pod-kill ×3 ─► result.json
```

**Stage-gating rules (failures are data, never dropped):**
- Parse failure: every later stage is recorded as `SKIPPED(parse_error)`.
- Schema failure: static scanners and D4 **still run** (they work on text). Deployment is still attempted, and its failure reason is recorded.
- Deploy failure: D6 is recorded as `SKIPPED(not_deployed)`.

**Isolation:**
- one namespace per config, deleted after the run;
- the cluster is recreated between projects;
- images are pre-pulled into kind so that network speed doesn't skew time-to-Ready (this is documented).

**Cluster:** kind (chosen over minikube for fast create/delete, a pinned node image and cheap multi-node clusters). It uses **1 control-plane node and 3 worker nodes**, so that configurations with required pod anti-affinity or topology spread across up to 3 replicas can schedule. A single-node cluster would wrongly fail these good reliability practices. The node image version is pinned in `tools/versions.lock`.

**kind-specific handling:**
- A `LoadBalancer` Service counts as valid-but-pending, not as a failure.
- An Ingress is recorded as created, but it isn't exercised; the smoke test uses port-forward to the Service.
- PVCs use kind's default local-path StorageClass. A manifest that requests a non-existent StorageClass fails honestly, and the reason is recorded.

**Timeouts:** 300 s to Ready, and 180 s for recovery.

**Output:** `evaluation/results/<source>/<project>/s<k>/result.json`, plus the raw tool outputs alongside it, and a flat `evaluation/results/results.csv`.

### 7.1 Result record (per config)
```
project_id, project_class, human_intent (production|demo), source (human|<model>), model_id,
prompt_variant (neutral|production|n/a for human), sample_k,
d1_parse_ok, d1_schema_ok, d1_schema_errors, d1_server_ok, d1_server_errors,
d2_kubescape_{critical,high,medium,low}, d2_kubescape_compliance, d2_trivy_{critical,high,medium,low},
d2_pss_level (restricted|baseline|none), d2_secrets_found, d2_categories[],
d3_kubescore_{critical,warning}, d3_polaris_score, d3_kubelinter_smells{}, d3_checklist_pct,
d4_requirements_met, d4_requirements_total,
d5_apply_ok, d5_ready_ok, d5_time_to_ready_s, d5_ready_replicas, d5_expected_replicas, d5_smoke_ok, d5_failure_reason,
d6_{pod_delete,container_crash}_{recovery_ok,recovery_time_s,availability_pct}[3],
sim_to_human, loc, resource_counts{}, tokens_in, tokens_out, latency_s,
tool_versions{}, k8s_version, timestamps{}
```

---

## 8. Analysis

- **RQ1/RQ3 tests** (RQ1 uses neutral-prompt outputs only, reported overall and per human-intent stratum):
  - Kruskal–Wallis across sources, with Dunn post-hoc (Holm-corrected), for continuous metrics;
  - Fisher's exact / χ² for pass rates;
  - Cliff's δ for effect size.
- **RQ5:** paired neutral-vs-production differences per (model, project, sample index). Wilcoxon signed-rank for continuous metrics, McNemar for pass/fail, reported overall and per model.
- **RQ2:** frequency tables of finding categories per source, and KubeLinter smell proportion/density in the same format as Zhang et al. (2024) for a direct 2023 vs 2026 comparison.
- **RQ3 consistency:** for each (model, project), the variance of key metrics across the 3 samples.
- **RQ4:** point-biserial / Spearman correlation between static scores (D2/D3) and runtime outcomes (D5/D6).
- **Tool agreement:** Cohen's κ between Kubescape and Trivy on overlapping checks.
- **Figures:**
  - per-model radar (D1–D6);
  - heatmap of finding category × source;
  - stacked bar of deployment failure reasons;
  - box plot of recovery time;
  - scatter of similarity-to-human vs quality.

---

## 9. Paper Structure (course template)

1. **Abstract:** importance → gap → objective → method → key findings → implications
2. **Introduction:** topic → background → research problem → objectives and RQs → methodology → contributions → paper outline
3. **Background:** K8s objects, security and reliability controls, LLM code generation
4. **Literature Review:** themes (a) LLM config/IaC generation, (b) security of LLM code, (c) K8s misconfigurations and tools, (d) LLMs for K8s security. Ends with a comparison table of prior work vs this study.
5. **Methodology:** dataset, specs, generation, K8sGenBench, pipeline, environment
6. **Results:** RQ1–RQ5
7. **Discussion:** implications and recommendations for practitioners
8. **Threats to Validity:**
   - training-data contamination
   - kind vs production clusters
   - model drift
   - tool false positives
   - redaction judgement calls in `docs_bundle/` (what counts as "Kubernetes-specific" content)
   - asymmetric conditions between humans and LLMs (goal, process, context) and the mitigations in §1.1
   - one project's (Zabbix) D5/D6 real-deployment results are not-applicable: the human manifest
     legitimately mounts the same Secret twice (two volumes, different `items` key-remappings),
     which triggers a kubelet/containerd bug specific to this test cluster's k8s version, isolated
     with standalone repro pods and documented in `datasets/P01_zabbix/internal/meta.json`; D1-D4
     (no live cluster required) are unaffected
   - **free-tier access substitutions (2026-11-08):** budget constraints meant no model was sourced
     via a paid flagship API except where noted. Actual sourcing per slot, with exact model IDs and
     dates in `generation/models.yaml`:
     - **Claude:** generated via isolated Claude Code subagents (fresh context, no fork, given only
       `docs_bundle/` and the fixed prompt) rather than a bare Anthropic API call. The subagent runs
       under Claude Code's own harness/system prompt layered on top of the study's prompt; reported
       as the actual tier that ran (Claude Sonnet 5.5), not assumed to be Opus.
     - **GPT:** first piloted on OpenAI's own open-weight `gpt-oss-120b` via Groq's free API (not the
       flagship ChatGPT-tier model); this hit a hard free-tier cap (8,000 tokens/minute combined
       prompt+output) that fails outright on larger projects (preserved for the record in
       `generation/outputs_archive/gpt-oss-120b_pilot/`, not used as the slot's data). The GPT slot
       was then re-sourced from a paid ChatGPT Pro account (volunteered by a friend of the user) via
       manual web-chat relay -- fresh chat per prompt, browsing/tools off -- the same disclosed
       pattern as DeepSeek below. Two further caveats specific to this slot: the exact model version
       is not confirmed (reported only as "ChatGPT's default model" by the person operating it, not
       a deliberately selected named flagship), and the sessions were operated by a third party, not
       the researcher directly, so adherence to the stated conditions is trust-based.
     - **DeepSeek:** no free API route exists (DeepSeek's platform requires a payment method for any
       API credit). Sourced via manual web-chat relay at chat.deepseek.com: a fresh, logged-in session
       per prompt (DeepThink off, Search off), with the response pasted back and stored. Automated
       browser access was attempted first and abandoned after hitting anti-bot blocks (HTTP 403, then
       an image CAPTCHA) rather than worked around.
     - **Gemini:** downgraded from the assumed Pro flagship to `gemini-3.6-flash` (the Pro-tier models
       available to this key return 404 or a $0 free quota). This free-tier key also caps at 20
       requests/day, requiring the full run to be spread across multiple days or paid.
     - **Qwen:** sourced via Groq (free) rather than OpenRouter as originally planned; same model
       family requirement met at zero cost, but this free-tier key caps output at 1,000 tokens/minute,
       which fails outright (not transient) on projects needing more YAML than that.
     - **Llama (originally "Open-1" in §5.1) was dropped from the study entirely.** No free API route
       exists anywhere as of 2026-11-08 (not on Groq, not on OpenRouter's free tier; GitHub Models,
       which did carry Llama, was retired 2026-07-30). The manual-web-chat fallback (HuggingChat) was
       also tried and blocked by an account-wide free-tier message cap on the very first test message.
       A Kimi/Moonshot substitute was considered and also found to have no working free route anywhere
       (Groq deprecated it; OpenRouter's live model catalog has no $0 variant; Moonshot's own API is
       prepaid-only). Creating a second/throwaway account specifically to route around either
       platform's rate limit was rejected as evading abuse protection rather than legitimate free-tier
       sourcing. The study proceeds with 5 of the originally planned 6 model slots.
9. **Conclusion and Future Work** (including repository-context generation and a human-from-docs baseline)

LaTeX sources live in `paper/` and are synced to the group's existing Overleaf project. Citations come from `papers/references.bib`.

---

## 10. Repository Layout
```
docs/superpowers/{specs,plans}/
papers/                 # literature (done)
datasets/Pxx_<name>/    # §4.3
generation/             # providers, prompt template, models.yaml, outputs/
evaluation/             # d1_..d6_ runners, pipeline.py, results/
analysis/               # stats.py, figures.py → paper/figures/
paper/                  # LaTeX
tools/                  # pinned tool install script + versions.lock
```

**Stack:**
- Python 3.12 (in a venv; the system Python is 3.14, so check it for library compatibility)
- `httpx` or official SDKs, `pyyaml`, `pandas`, `scipy`, `scikit-posthocs`, `matplotlib`
- Docker Desktop, kind, kubectl, kubeconform, Kubescape, Trivy, kube-score, Polaris CLI, KubeLinter

API keys are read from a `.env` file that is never committed or logged.

---

## 11. Phases and Milestones

| # | Phase | Output |
|---|---|---|
| 0 | Literature (done) | `papers/`, index, `.bib` |
| 1 | Intro + Literature Review (LaTeX) (done) | `paper/sections/01_introduction.tex`, `02_literature_review.tex` → Overleaf |
| 2 | Environment (done) | tools installed and pinned; kind cluster smoke-tested (`tools/smoke/`) |
| 3 | **Dataset** | 12 projects verified; intent labelled; specs with provenance, peer-reviewed; `requirements.py` per project |
| 4 | Pilot | 2 projects × 6 models × 2 variants × 1 sample through the full pipeline; fix the pipeline, **not** the outputs |
| 5 | Full generation | 432 LLM configs |
| 6 | Full evaluation | 444 result records |
| 7 | Analysis | tables and figures |
| 8 | Paper completion | Methodology, Results, Discussion, Threats, Abstract |

---

## 12. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Training-data contamination (popular repos) | Similarity metric; less-popular projects included; reported as a threat to validity |
| A human baseline fails on kind for environmental reasons | Documented substitutions (e.g., StorageClass) applied **identically** to all sources; noted in the paper |
| Online Boutique / Sock Shop too heavy for the laptop | Run heavy projects alone; drop to the next candidate if they still don't fit, and record why |
| API model deprecation mid-study | Pin IDs; complete all generation within one week; archive raw responses |
| Scanner disagreement | Two scanners per dimension; report Cohen's κ |
| Spec authoring bias | Checklist-based peer review; provenance for every fact; specs published in the artefact |
| Human and LLM worked under different conditions | Neutral prompt for RQ1, intent stratification, "reference point" framing, the production prompt isolated in RQ5 (§1.1) |
| Too few production-intent human manifests | Selection criterion 5 requires at least 4. If that can't be met, report the production stratum descriptively only |
