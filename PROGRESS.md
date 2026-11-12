# K8sGenBench — Project Progress

Last updated: 2026-11-08

## ROADMAP TO END-TO-END COMPLETION (senior-engineer plan, 2026-11-08)

Phases below are sequential; each should be checkpointed (committed to this
file) before moving to the next, so the project survives a session break.

- **Phase R1 — Evaluation pipeline, D1+D4 (static, fast, no deploy).**
  Built `evaluation/eval_runner.py`: parse → kubeconform → server dry-run
  (D1), reuse each project's existing `requirements.py` (D4). Ran against
  all 18 pilot LLM configs + 2 human baselines. **Pipeline core DONE
  (2026-11-08); one audit item left (see last bullet).**
  - Pipeline bugs found and fixed (all were pipeline bugs, not model
    defects — no model output was edited):
    1. Uniform `server_ok=False (1/N)` on production configs = namespace
       still Terminating from the previous run. Fixed: blocking delete + poll.
    2. P07 D4 2/26 vs 26/26 = requirements.py scored the exact production
       registry path (`us-central1-docker.pkg.dev/...`), which is NOT in
       docs_bundle/. Fixed: those checks are now `oracle=True` (diagnostic);
       added scored `component_present` checks (service name IS in the
       bundle, as `<name>.Dockerfile`).
    3. One uninstalled CRD (ServiceMonitor) aborted a whole batched dry-run.
       Fixed: dry-run applies each object individually; per-object
       accept/reject + error kept in results JSON.
  - Results (all 20 configs parse and pass kubeconform):

    | Config | dry-run accepted | D4 |
    |---|---|---|
    | human P05 | 11/11 | 11/12 |
    | human P07 | 35/35 | 11/11 |
    | claude P05 neu / prod | 8/8, 9/9 | 11/12, 12/12 |
    | claude P07 neu / prod | 24/24, 40/40 | 11/11, 11/11 |
    | deepseek P05 neu / prod | 8/8, **12/13** | 11/12, 12/12 |
    | deepseek P07 neu / prod | 25/25, 36/36 | 11/11, 11/11 |
    | gemini P05 neu / prod | 8/8, 8/8 | 11/12, 11/12 |
    | gemini P07 neu / prod | 23/23, 23/23 | 11/11, 11/11 |
    | gpt P05 neu / prod | 8/8, 10/10 | 12/12, 12/12 |
    | gpt P07 neu / prod | 24/24, 29/29 | 11/11, 11/11 |
    | qwen P05 neu / prod | 9/9, 9/9 | 12/12, 12/12 |

  - Real findings (kept, scored as-is):
    - deepseek P05 production ships a `ServiceMonitor` (Prometheus Operator
      CRD) without the CRD being part of the app → rejected on a plain
      cluster. Legitimate D1 defect.
    - Every P05 D4 miss is the same check, R12-web-external (web must be
      reachable from outside the cluster; grounded in the bundled README
      "web app will be running on port 8080 of your docker host"). The
      **human** manifest also fails it (ClusterIP + port-forward). Kept
      scored — it is documented in the bundle — and will be discussed as a
      human-intent difference (demo app vs. exposed service).
  - Known weakness: P07 D4 is at ceiling (11/11 for everyone) because most
    of its facts are oracle-only. D4 will discriminate on other projects;
    P07's signal will come from D2/D3/D5/D6. Disclose in Results.
  - **TODO before R7:** audit the other 10 projects' requirements.py for
    the same oracle-fairness bug as P07 (scored checks on facts not
    recoverable from docs_bundle/).
  - Oracle-fairness audit of the other 10 projects DONE (2026-11-08):
    P08 sock-shop (service ports 80/8079 only in unbundled Dockerfiles/
    images) and P10 k8s-dashboard (image names not in bundle) had scored
    checks on un-recoverable facts → made oracle, with scored weaker
    counterparts (Service hostname on any port; component present by its
    documented name). reqlib gained a `Component` selector. Other 8
    projects clean. Judgement call kept: well-known DB/broker default
    ports (5432/6379/3306/5672) stay scored (in Threats to Validity).
    Human scored D4 now: P01 10/11, P02 13/13, P03 3/3, P04 11/12,
    P06 8/8, P08 27/27, P09 19/19, P10 7/7, P11 13/13, P12 3/4 — the
    misses (P01/P12 external exposure, P04 DB persistence) are real.
- **Phase R2 — D2/D3 static scanners. DONE on pilot (2026-11-08).**
  All 20 configs scanned, no tool errors; `evaluation/flatten.py` →
  `evaluation/results/results.csv`. Sanity checks: claude P07 neutral
  checklist 0.8% is real (bare manifest, untagged images, no probes/
  resources); 4 models' P05 neutral outputs are different files that
  converged on the same minimal structure (identical scores) — a finding.
  Pipeline fix: secrets check counted a non-credential value in a Secret
  (deepseek `REDIS_ADDR: redis-cart:6379`); now only credential-named keys
  count, others recorded as `nonsensitive_secret_literals`. Pilot has
  0 real hardcoded secrets. Prompt effect visible already: production
  variant raises checklist (e.g. claude P05 10%→62.5%) and Polaris. `evaluation/d2d3.py`, wired into eval_runner.py:
  - D2: Kubescape (NSA+MITRE; compliance %, failed controls by severity,
    per-resource failed control IDs for the Kubescape-Trivy κ later),
    Trivy config (FAIL by severity + IDs), PSS (each pod-bearing object
    dry-run into namespaces labelled enforce+warn=restricted / baseline →
    highest level passed), hardcoded-secret check (Secret literals,
    secret-named env literals, token regexes; placeholders ignored).
  - D3: kube-score (non-skipped critical/warning), Polaris score,
    KubeLinter (all checks + Zhang et al.'s 6 smells, density per KLOC),
    10-item checklist (per-workload, N/A rules in Methodology).
  - Rule sets pinned offline (tools/scanner-artifacts/, versions.lock).
  - Spot-check on claude P05 production matched the manifest by hand.
  - Rahman et al. 11-category mapping deferred to R9 (raw finding IDs
    are stored, so it's a pure post-processing step).
- **Phase R3 — D5 real deploy. BUILT; cluster rebuilt 1+3 + mirror
  (verified: fake ghcr.io ref served from mirror, real refs fall back
  upstream); human P05 validated (Ready 11s, smoke pass); pilot runtime
  batch RUNNING (`evaluation/pilot_runtime_run.log`).** `evaluation/d5d6.py`
  (`eval_runner.py ... --runtime [--reuse-static]`). Per-object apply,
  300s Ready wait, failure-reason classification, smoke.json via the
  existing smoke.py (now also matches by documented component name).
  **Image decision (senior call):** all images served from a local
  registry mirror (tools/setup_cluster.py: kind 1+3 workers + containerd
  `_default` mirror → k8sgen-registry, fallback upstream). For P07/P10
  only (image path is an oracle fact), a reference that is not pullable
  as written but whose basename names a documented component is served
  the canonical image under the model's own reference
  (datasets/<P>/image_aliases.json). Manifests never edited; per-image
  `as_written_pullable` + `served` recorded (ledger:
  evaluation/mirror_ledger.json). Without this every model except GPT
  would fail P07 D5 on ImagePullBackOff for a fact it was never given.
- **Phase R4 — D6 fault injection. BUILT, not yet run** (same module).
  In-cluster ~5 Hz curl prober; F1 force pod-delete, F2 `crictl stop
  --timeout 0`; 3x each; recovery from pod Ready lastTransitionTime;
  availability over [kill, recovery+5s]; all times on the cluster clock.
  - Runtime cost estimate: ~3-8 min per config → informs R6 scope.
  - Pipeline fixes on first run: availability read from wrong namespace
    (fixed); F2 victim now = Ready pod with fewest restarts, so with >1
    replica each rep hits a fresh pod. For single-replica targets reps 2-3
    include kubelet CrashLoopBackOff (≈10s, 20s) — genuine K8s behaviour,
    disclose in Results (human P05 F2: 1.1s / 14.5s / 26.7s).
  - Fix 2 (2026-11-08): human P07 came up 10/12 (emailservice +
    recommendationservice killed by their 1s liveness probes) because
    images were still being pulled INSIDE the Ready window while 12 services
    cold-started at once. Design requires pre-pulled images → added
    prepull(): every image `crictl pull`ed onto all 4 nodes before the clock
    starts (also fixes digest-pinned busybox, which kind-load couldn't
    handle). Human P07 now 12/12 Ready in 49s, smoke pass; D6 availability
    0-26% is real (single-replica frontend, 12-30s to readiness).
  - Batch re-started with pre-pull for all 19 remaining configs (earlier
    3 results discarded: measured without pre-pull).
  - Fix 3 (2026-11-09, found mid-batch): EVERY LLM P07 config failed D5
    on the same pod, frontend (CrashLoopBackOff). Root cause, reproduced
    with standalone pods: the frontend binary (v0.10.1 and v0.10.7 both
    tested) panics in mustMapEnv unless SHOPPING_ASSISTANT_SERVICE_ADDR is
    set. That variable exists only in source code, NOT in docs_bundle/, so
    it is an unrecoverable fact (same reasoning as the image-path oracle).
    Fix: new `datasets/P07_online-boutique/runtime_shims.json` + d5d6
    `apply_shims()` injects it at deploy time only where missing (no-op
    for human; files on disk untouched; recorded as `d5.shims_applied`).
    The 6 P07 LLM configs measured before the fix (claude/deepseek/gemini
    x neutral/production) will be re-run after the batch; list saved.
  - Fix 4: a namespace delete that hung 900s in cleanup threw away
    gemini P07 neutral's finished result. Cleanup timeouts are now a
    warning and the result is kept.
  - Pilot runtime so far (P05, emojivoto): all human + LLM configs
    deploy, smoke passes, and D6 recovers on all reps. DeepSeek P05
    production: 1 object rejected at apply (apply_ok=False) but the app
    still runs.
  - Main batch finished 2026-11-09. Shim validated: GPT P07 neutral 12/12
    Ready 53s, production 22/22 Ready 30s, smoke pass on both. Qwen P05
    x2 all pass. The 6 pre-fix P07 configs are now re-running
    (log: evaluation/pilot_p07_rerun.log).
  - Re-run results so far: claude P07 neutral 12/12 Ready but smoke
    HTTP 500 (diagnose live next); claude P07 production 21/23
    CrashLoopBackOff (diagnose next); deepseek P07 neutral PASS (23/23,
    smoke ok, D6 ~97%); gemini P07 neutral PASS (12/12, smoke ok).
  - Fix 5 (2026-11-09): deepseek P07 production was 22/22 Ready but smoke
    HTTP 000 / D6 0% because its own default-deny NetworkPolicy admits the
    frontend only from namespace `ingress-nginx` — the prober in d5-<id>
    was blocked. That is hardening, not breakage. New
    `smoke.client_placement()`: both probers (D5 smoke, D6) now run where
    the config's OWN NetworkPolicies admit a client to the entry Service
    (namespace peer preferred, else pod-label peer; no policy -> unchanged;
    no permitting rule -> blocked, honestly). Recorded as
    `d5.client_placement`. Offline check: only the 2 configs with
    NetworkPolicies change placement. deepseek+claude P07 production to be
    re-run.
  - Gemini P07 production re-run: PASS (12/12, smoke ok).
  - Fix 6 (2026-11-09): live diagnosis of claude P07 (both variants):
    Node.js currencyservice + paymentservice crash at start-up because the
    Google Cloud Profiler is on unless DISABLE_PROFILER is set ("Project ID
    must be specified"); the frontend's HTTP 500 was the knock-on effect
    (currencyservice connection refused). DISABLE_PROFILER is NOT in
    docs_bundle/ (it only shows a profiler exists), so same rule as Fix 3:
    added to runtime_shims.json for those 2 services only. NOTE FOR
    DISCUSSION: deepseek/gemini/gpt all set DISABLE_PROFILER unprompted
    (undocumented fact -> likely memorised; contamination evidence), and
    NO model set SHOPPING_ASSISTANT_SERVICE_ADDR (newer feature -> not
    memorised). `d5.shims_applied` records this per config.
  - Fix 7: D5 had counted claude P07 neutral "12/12 Ready" at an instant
    when crash-looping pods happened to be up. Ready now requires every
    workload at desired Ready continuously for READY_STABLE_S=20s;
    time-to-Ready = start of that window.
  - Clean pilot re-run of ALL 20 configs on the final pipeline started
    (log: evaluation/pilot_runtime_final.log), so the pilot dataset is
    measured by one consistent pipeline.
  - 2026-11-09: batch interrupted after 8/20 by a Docker/laptop restart
    (cluster survived; mirror verified). Done and all PASS: human P05,
    human P07, claude P05 x2, claude P07 x2 (production now 23/23 Ready
    + smoke ok -> Fix 6 confirmed), deepseek P05 x2. Remaining 12 resumed
    into the same log.
  - 16/20 done at 15:33, all PASS except deepseek P07 production, which
    is a GENUINE model error (verified, not pipeline): Fix 5 now lets the
    prober reach the frontend (via ingress-nginx), but the frontend
    returns HTTP 500 because the config's own `allow-internal-grpc`
    policy admits pods labelled app.kubernetes.io/part-of=online-boutique
    while no pod carries that label -> default-deny blocks every
    service-to-service call. Good Discussion example: hardening that is
    internally inconsistent breaks the app while improving D2 scores.
- **Phase R5 — Pilot evaluation review.** Once D1-D6 run end-to-end on the
  18 pilot configs + 2 human baselines, review for pipeline bugs (fix the
  pipeline, not the outputs) before scaling up.
- **Phase R5 — DONE 2026-11-09.** All 20 pilot configs measured on the
  final pipeline (evaluation/results/results.csv, 20 rows). 19/20 Ready +
  smoke pass; only deepseek P07 production fails (genuine, own
  NetworkPolicy). 7 pipeline fixes total (see above).
- **Phase R6 — DECIDED 2026-11-09: 7 projects** P02, P03, P04, P05, P07,
  P08, P10 (covers all 4 classes; production intent via P03 + P10) x 5
  models x 2 variants x k=3 = 210 LLM configs + 7 human. P01 excluded
  (runtime N/A); P06, P09, P11, P12 held in reserve. Manual web relay
  load: 42 prompts each for GPT and DeepSeek. Next: human baselines for
  P02/P03/P04/P08/P10 through the real pipeline (cluster recreated per
  project), which also validates P10 runtime.
- **Phase R7 prep — DONE 2026-11-09.** `generation/relay.py` (export /
  import / status) + `generation/relay/HOW_TO_RELAY.md`. 14 paste-ready
  prompts in `generation/relay/prompts/`; replies go in
  `generation/relay/inbox/{deepseek,gpt}/<P>__<variant>__s<k>.txt`.
  38 replies needed per model (P05/P07 s1 exist from pilot). User will
  supply them. Also fixed `extract_yaml` to join ALL yaml blocks (it kept
  only the first; pilot unaffected — every pilot reply had 1 block).
- **Phase R7 — IN PROGRESS (2026-11-09).**
  - Human baselines (real pipeline, cluster recreated per project):
    P02 n8n PASS (13/13 D4, Ready 20s, smoke ok, D6 avail 0-10% =
    single replica); P03 grafana PASS (3/3, Ready 84s, smoke ok, avail
    20-49%); P04/P08/P10 running (evaluation/human_baselines_run.log).
  - Gemini + Qwen API generation for full scope running
    (generation/api_gen_run.log; skips existing, quota failures retried
    on a later day).
  - Claude: same protocol as pilot (fresh Sonnet subagent, reads ONLY
    the one prompt file, writes ONLY manifest.yaml, no tools/web). Test
    OK; batches 1-2 done (P02, P04, P05 s2-3, P07 s2-3, P08: 30 outputs,
    all parse, no fences). Batch 3 done -> **Claude COMPLETE 42/42**
    (7 projects x 2 variants x 3), all parse, records written via
    generation/claude_records.py. Regenerated P05/P07 s1 now match their
    siblings (P05 prod 18 vs 19/19; P07 prod 43 vs 42/42).
  - Consistency fix: pilot Claude s1 for P05/P07 used an earlier protocol
    (object counts differ, e.g. P05 production 9 vs 19/19 for s2/s3), so
    all 4 were archived to outputs_archive/claude_pilot_s1/ and
    regenerated with the current protocol -> all 3 samples per cell come
    from one protocol.
  - Human P04 PASS (11/12 D4, Ready 13s, smoke ok).
  - 2026-11-09 ~16:45 Docker Desktop engine hung (API 500); user
    restarted it. Human P08 had recorded "no_workloads 0/0" and P10 never
    ran. Root cause of the bogus P08 result (Fix 8): d5d6.kjson() turned
    any kubectl/API error into an empty list. Now retries 3x and raises
    an INFRA error (no record written) instead. P08 + P10 re-running
    (evaluation/human_baselines_run2.log).
  - SECURITY (Fix 9): Gemini errors printed the request URL including the
    API key into generation/api_gen_run.log. Key redacted from the log
    (22 lines; no other file contained it); generate.py now sends the key
    in the x-goog-api-key header, never the URL. Consider rotating the key.
  - API generation so far: Gemini 20/42 (daily quota 20 -> continue next
    days), Qwen 15/42 (429 rate limits retriable; 413 "payload too large"
    on large projects = permanent feasibility gap, as predicted).
  - DeepSeek relay: 4/38 imported (P02 neutral s1-s3, production s1).
    Note in inbox/deepseek/NOTES.txt: s2 had a follow-up question asked
    after the reply; only the first reply used.
  - DeepSeek + GPT: user relaying (38 each).
- (original R6 text) **Phase R6 — Scope decision.** Decide full run size: all 12 projects x
  5 models x 2 variants x 3 samples (the original plan, now minus Llama），
  or the instructor's suggested 4-5 project subset. (`tools/kind-cluster.yaml`
  already reverted to 1+3 workers on 2026-11-08 as part of R3.)
- **Phase R7 — Full generation run.** Scale the generation pipeline
  (API calls for Gemini/Qwen/GPT-if-API, subagents for Claude, manual
  relay for DeepSeek/GPT-web) to the decided scope.
- **Phase R8 — Full evaluation run.** Same pipeline as R1-R4, full scope.
- **Phase R9 — Statistical analysis.** Implement the §8 analysis plan
  (Kruskal-Wallis/Dunn, Wilcoxon/McNemar, Cliff's δ, Spearman, Cohen's κ)
  against `evaluation/results/results.csv`.
- **Phase R10 — Paper completion.** Results, Discussion, Conclusion
  sections; wire in Threats to Validity (already drafted, held back for
  numbering reasons — see §8 below); final Overleaf sync.

## Overall status

(Updated 2026-11-11.) Scope: 7 projects x 5 models x 2 variants x 3 samples, plus 7 human configs.

| Part | Status |
|---|---|
| Dataset, pipeline D1-D6, pilot | done (12 fixes so far, latest Fix 12) |
| Human baselines | done, 7/7 scored |
| Generation | claude 42/42, deepseek 42/42, gemini 33/42 (9 left, next quota day), qwen 18 of 30 feasible (retries running; P03/P07 are infeasible on the free tier), gpt 4/42 (friend relaying 38) |
| R8 evaluation | running: 11 of ~200 LLM configs scored |
| R9 statistics | evaluation/stats.py built and tested; waiting for data |
| Paper | Intro, Lit Review, Methodology, Threats written; Results, Discussion, Conclusion and the final abstract still to write |

```
[#############-------] ~65% end-to-end (generation ~70%, evaluation ~6% and running, paper 4 of 7 sections)
```

## 1. Dataset construction (12 real projects) — DONE

- All 12 projects restructured: docs_bundle/, human/, requirements.py, smoke.json
  at top level; fact_sheet.md, provenance.md, redaction_log.md, meta.json moved
  into internal/.
- P01 swapped from WordPress (inconsistent with other projects, no own
  Dockerfile/compose) to Zabbix (zabbix/zabbix-docker) — same-repo-publishes-
  everything, consistent with the other 11.
- SPEC_GUIDE.md fully updated (file paths, oracle flag convention, review
  checklist).

Projects: P01_zabbix, P02_n8n, P03_grafana, P04_voting-app, P05_emojivoto,
P06_wordsmith, P07_online-boutique, P08_sock-shop, P09_teastore,
P10_k8s-dashboard, P11_kube-state-metrics, P12_headlamp.

## 2. Benchmark design (D1–D6 methodology) — DONE

6 dimensions defined and documented: D1 correctness, D2 security, D3 static
reliability, D4 requirement satisfaction, D5 real deployment + smoke test,
D6 resilience/fault-injection.

## 3. D5/D6 live deploy validation on kind cluster — IN PROGRESS (7–8 / 12)

Cluster: kind-k8sgen, now 1 control-plane + 1 worker (shrunk from 1+3 to cut
local resource usage).

| Project | Status |
|---|---|
| P02 n8n | PASS |
| P03 grafana | PASS (tested earlier this session) |
| P04 voting-app | PASS (tested earlier this session) |
| P05 emojivoto | PASS |
| P06 wordsmith | PASS (tested earlier this session) |
| P07 online-boutique | PASS (READY, 12 workloads) |
| P01 zabbix | D1–D4 only — D5/D6 blocked by a kubelet/containerd bug on this
  cluster's k8s v1.37.0 (double-mounted Secret), documented as an environment
  limitation in internal/meta.json and the design doc's Threats to Validity |
| P08 sock-shop | PASS (READY after 399s, 14 workloads) — earlier failures were
  transient (Docker engine instability during disk cleanup, then one stale
  API-server read right after cluster recreation), not a manifest issue. |
| P09 teastore | not started |
| P10 k8s-dashboard | not started |
| P11 kube-state-metrics | not started |
| P12 headlamp | not started |

## 4. Spec review by team — NOT STARTED

Nabeed/Talha haven't reviewed the 12 projects against the SPEC_GUIDE.md
checklist yet.

## 5. LLM generation pipeline — PILOT RUN COMPLETE for 4 of 5 models (Qwen capped on large projects)

Built `generation/` (prompts, models.yaml, generate.py). Ran the Phase 4
pilot (2 contrasting projects: P05_emojivoto small, P07_online-boutique
large, x 2 prompt variants x 1 sample):

| Slot | Pilot coverage | Status | Notes |
|---|---|---|---|
| Gemini | 4/4 (both projects, both variants) | working | `gemini-3.6-flash` (flash, not the Pro flagship the design doc assumed). **Hard cap: 20 requests/day free tier**, resets daily — online-boutique retried successfully 4 days after the first attempt. Full-run share (72 generations) still needs 4+ days minimum or a paid key. |
| Qwen | 2/4 (small project only) | working (small projects only) | Via Groq (free), not OpenRouter. **Hard cap: 1,000 output tokens/minute** — rejects max_tokens=8192 outright for larger projects (confirmed failing on online-boutique, not transient/retriable). Needs a paid tier or OpenRouter for big projects. |
| Claude | 4/4 (both projects, both variants) | working | No Anthropic API key — generated via fresh, isolated Claude Code subagents (no fork, docs_bundle only) as a stand-in. Documented as a methodology deviation (different harness/system prompt than a bare API call; reported honestly as "Claude Sonnet 5.5", not Opus) — **disclosed in the paper, not hidden.** |
| GPT | 4/4 (both projects, both variants) | working (pilot complete) | First piloted on `gpt-oss-120b`/Groq, which hit the same hard cap as Qwen (8,000 tokens/minute, failed on online-boutique) — that data is archived in `generation/outputs_archive/gpt-oss-120b_pilot/`, not used. Re-sourced from a friend's paid ChatGPT Pro account via manual web-chat relay (fresh chat per prompt, browsing/tools off) — all 4 prompts done 2026-11-08. Two disclosed caveats specific to this slot: the friend used ChatGPT's "default model" rather than deliberately picking a named flagship, so the exact model version is unconfirmed (recorded as `"ChatGPT (web, default model on Pro account)"`, not guessed); and the sessions were operated by a third party, not the researcher, so adherence to the no-browsing/fresh-chat conditions is trust-based. |
| Llama | 0/4 | **DROPPED** | Extensive search (2026-11-08): not on Groq, not on OpenRouter's free tier, and GitHub Models (which did carry Llama) was **retired 2026-07-30**. Tried HuggingChat next (same manual-web-chat pattern as DeepSeek) — signed in, selected `meta-llama/Llama-3.3-70B-Instruct`, but the first test message hit an immediate account-wide "message limit reached" wall. Also checked Kimi/Moonshot as a substitute (user's suggestion) — no free API route anywhere either (Groq deprecated it, OpenRouter's live `/models` endpoint confirmed no $0 variant currently, Moonshot's own API is prepaid-only), and it would hit the same HuggingChat wall regardless. **Decision (senior-engineer call, user deferred):** not creating a second HF account to route around the rate limit — that's evading a platform's abuse protection, not legitimate free-tier sourcing. Dropping Llama from the study; proceeding with 5 of 6 slots, consistent with the instructor's own "4-5 models is enough" guidance. |
| DeepSeek | 4/4 (both projects, both variants) | working (pilot complete) | No free API route exists. Automated browser access (Playwright) was blocked by anti-bot detection (403, then a CAPTCHA) — abandoned by agreement, not worked around. Sourced via **manual web chat relay**: user pastes each prompt into a fresh, logged-in `chat.deepseek.com` session (DeepThink off, Search off, new chat per prompt) and relays the response back. |

**Pipeline health check:** all 18 saved generations (4 models × 2 projects
× 2 variants, plus 2 for Qwen) parse as valid multi-doc YAML with no
extraction errors (verified via `yaml.safe_load_all` across every
`manifest.yaml`); document counts scale sensibly (8–10 for emojivoto,
23–40 for online-boutique, production variants consistently richer than
neutral for every model). The generation pipeline itself is sound — any
defects in individual outputs (e.g. DeepSeek's online-boutique neutral
manifest using bare `image: adservice:latest` with no registry, or its
production manifest using `grpc:` probes without evidence the services
implement gRPC health checking; ChatGPT's online-boutique outputs
deploying to the `default` namespace in the neutral variant) are genuine
model behavior for the benchmark to score, not pipeline bugs to fix, per
the design doc's "fix the pipeline, not the outputs" principle.

**Pilot scope is now effectively done.** 4 of 5 models (Gemini, Claude,
GPT, DeepSeek) have full 4/4 pilot coverage; Qwen is capped at 2/4 by a
free-tier limit that cannot be fixed without a paid tier. Next step is
either reviewing these 18 outputs together before committing to a full
run, or proceeding straight to a real evaluation-pipeline test run against
this pilot data.

Llama's drop and the Qwen/GPT large-project token-cap limitation both
need to be reflected as explicit Threats to Validity bullets in the
design doc / paper (not yet done). Gemini's daily cap and DeepSeek's
manual-relay approach also don't scale well past the pilot (12 projects
× 2 variants × 3 samples = up to 72 round-trips each) — worth revisiting
before Phase 6 if the project stays at full 12-project scope.

**Unresolved disagreement (flagged, not yet re-confirmed with user):**
the instructor's relayed guidance was to not mention subagent/substitution
methodology in the report, just list model names. I pushed back on this
(non-disclosure is a bigger academic-integrity risk than disclosure) and
the user agreed in-session, but I'm proceeding on my own judgment to
document every substitution (Claude-via-subagent, GPT-via-gpt-oss-120b,
DeepSeek/Llama-via-manual-web-chat) transparently in `models.yaml`/metadata
and will write them up in the paper's Methodology/Limitations section
regardless. This hasn't been revisited with the instructor directly.

## 6. Evaluation run — PILOT IN PROGRESS (D1+D4 done; D2/D3 next)

`evaluation/eval_runner.py <source> <project> [<variant> <k>]` writes
`evaluation/results/<source>__<project>[__<variant>__s<k>].json`.
Pilot: 18 LLM + 2 human configs evaluated on D1+D4 (see Phase R1 above).
Full run (~444 evaluations) waits on Phase R6 scope decision.

## 7. Statistical analysis — NOT STARTED

## 8. Paper — 3 of ~7 sections wired in, 1 more drafted but not yet wired

- paper/sections/01_introduction.tex — drafted; updated to say "five LLMs"
  (Llama dropped) without the backstory, per explicit instruction — the
  substitution story lives only in Methodology/Threats to Validity.
- paper/sections/02_literature_review.tex — drafted; same "five LLMs" fix.
- paper/sections/03_methodology.tex — drafted and wired into main.tex
  (dataset, fairness design, generation procedure, full K8sGenBench D1-D6,
  evaluation pipeline/environment, statistical analysis plan).
  2026-11-08 corrections to match the built pipeline: D3 smells now cite
  zhang2024genaismells (MSR'24, the actual source of the 6 smells; was
  wrongly zhang2026k8sconfigdefects); smoke test is in-cluster client pod,
  not port-forward; added per-object dry-run, D4 oracle split, checklist
  N/A rules, local registry mirror + image-alias rule. 06_threats.tex got
  a "Recoverability of facts" paragraph.
- paper/sections/06_threats.tex — drafted (model-sourcing substitutions in
  full, contamination, kind-vs-production, model drift, tool disagreement,
  redaction judgement calls, human/LLM asymmetry, Zabbix D5/D6 N/A) but
  **NOT yet wired into main.tex** — it's numbered 6 in the Introduction's
  own stated outline (after Results=4, Discussion=5), neither of which
  exist yet since there are no experimental results. Wiring it in now
  would misnumber it as Section 4 and contradict the Introduction.
- Results, Discussion, Conclusion — not started (need real evaluation
  data first).

## METHODOLOGY FLAG — RESOLVED 2026-11-08 (cluster recreated 1+3 via tools/setup_cluster.py)

The design doc (§7) specifies the kind cluster as 1 control-plane + 3 workers,
specifically so configs with 3-way pod anti-affinity/topology-spread (D3
checklist item 9) can actually schedule. Today's cluster was shrunk to 1
control-plane + 1 worker to cut local resource usage during ad-hoc
dataset-verification deploy checks (human baselines only, not the real
evaluation). This is fine for that use, but the cluster MUST be recreated
with 3 workers (`tools/kind-cluster.yaml`) before Phase 6 (the real 444-config
evaluation run) — otherwise any config that correctly uses 3-way
anti-affinity will fail to schedule and get wrongly scored as a D5 deploy
failure, biasing results against well-written configs.

## Known open issues

- P08 sock-shop — RESOLVED, now passing (was transient Docker engine
  instability during disk cleanup).
- Local disk space was critically low this session (27GB free); cleaned up
  to ~56GB via cache clears, dead downloads, and disabling hibernation.
  `C:\workspace\edgefirm` (34GB) and `C:\workspace\my projects` (20GB) are
  other projects taking space on this machine, untouched — worth a look if
  more room is needed later.

## 2026-11-09 update
- DeepSeek relay: P03_grafana neutral s1 imported (5 objects). 7/38 done.
- Human baseline re-run for P08/P10 was interrupted when the Docker engine stopped responding (the API returned 500). The cause was RAM: the WSL VM had grown to 15.8 GB with no cap, leaving 2.1 GB free. Fix 8 worked as intended: the INFRA error meant nothing was recorded.
- The old bogus P08 "no_workloads 0/0" result (from before Fix 8) was moved to evaluation/results_archive/.
- Added C:\Users\DELL\.wslconfig with memory=14GB and swap=8GB, so Docker/kind can no longer starve Windows. It takes effect after `wsl --shutdown`.
- TODO: re-run human P08 and P10 once Docker is back.

## 2026-11-09 (cont.): Fix 10, kind open-files limit (root cause of the Docker crashes)
- Symptom: every run of the human sock-shop baseline (P08) took the Docker engine down (API 500, kubectl TLS handshake timeouts). The earlier "no_workloads 0/0" P08 result had the same cause.
- Diagnosis (watchdog run): `mysqld --verbose --help` from sock-shop's catalogue-db went from 0 to 5.7 GB in 10 s, with one node at 9 GB. kind's containerd runs with LimitNOFILE=infinity, so containers inherit an open-files limit of about 1e9, and old MySQL sizes its tables from that limit.
- Fix: tools/setup_cluster.py adds a containerd drop-in on every node setting LimitNOFILE=1048576 (Docker's default), then restarts containerd. Verified that a pod now reports `ulimit -n` = 1048576 and that sock-shop is stable at 3.3 GB for 7 minutes, with all pods Running. The fix is an environment setting and applies identically to every config. Needs a Methodology/Threats sentence.
- Safety net: tools/mem_guard.sh runs beside every batch and deletes the cluster if the kind nodes exceed 10 GB. The config then fails as INFRA, so nothing is recorded and the laptop survives.
- WSL cap: C:\Users\DELL\.wslconfig is set to memory=14GB.
- DeepSeek relay: 20/38 done (P02, P03, P04 complete; P05 neutral complete).
- Human P08 and P10 baselines are re-running (evaluation/human_baselines_run4.log).

### 2026-11-09 relay note: DeepSeek P07 production s2 == s3
- In two fresh DeepSeek web chats, the P07 production prompt produced the same 33-object manifest (parsed objects identical; s3 taken from DeepSeek's own download, 1071 lines). Both are kept as samples. Report this as low sampling diversity for DeepSeek web in the paper's variance/threats discussion.
- An earlier s3 paste was a different, truncated reply (gcr.io v0.10.0 images, cut off at a NetworkPolicy `metadata:`). The user confirmed the downloaded file is the real s3 output, so that paste is archived as relay/archive/P07_online-boutique__production__s3__truncated_unattributed.txt and is not scored.

### 2026-11-09 19:28 human P08 baseline (run4): smoke 4/5, not yet valid
- D5: apply OK, 14/14 ready in 237 s. Smoke: home, catalogue, tags and login passed; `cart-read` (GET /cart) returned HTTP 500 for the whole 300 s retry window.
- D6 recovered on all 6 injections. Fix 10 held: nodes at about 2.5 GB, mem_guard never fired.
- A human reference config must pass its own smoke checks, so this is not acceptable as is. Either the cart-read check is wrong (for example, an anonymous /cart call fails in upstream front-end 0.3.12) or carts is broken in our environment.
- TODO after P10 finishes: deploy human P08 by hand, run curl /cart with and without the login cookie, and read the carts and front-end logs. Then fix the check spec if the check is wrong, or the environment if that's the cause, and re-run human P08. Do NOT score any P08 config until this is resolved.

### 2026-11-09 19:52 human P08 cart-read failure: root cause found, check validated
- Cause: upstream complete-demo.yaml uses the unpinned `image: mongo` for carts-db and orders-db. On 2026-11-09 that resolves to MongoDB **9.0.4**. The 2017 carts driver sends the legacy OP_QUERY wire protocol, which MongoDB removed in 5.1+, so carts returns 500 ("Unsupported OP_QUERY command: find", error 352). /health still says OK.
- Check validated: in a manual deploy, setting carts-db to `mongo:3.4` made front-end /cart return 200 within about 20 s. The smoke spec is correct and stays unchanged.
- Decision: keep the human baseline exactly as published (it's the upstream reference). P08 human = smoke 4/5 (cart-read failed). This is a real finding for the paper: an unpinned tag drifting over time breaks the expert config. Ironically, all 6 DeepSeek P08 samples pin `mongo:3.4`. The earlier "do not score P08" blocker is lifted.
- Also seen: carts (Spring Boot, 300m CPU limit) takes about 345 s to start and has no readiness probe, so it reports Ready long before it listens.
- Threats/reproducibility: record that results depend on the date `:latest`/untagged images were mirrored (mongo resolved to 9.0.4). Mention it in Methodology.
- Diagnostic deploy cleaned up (sock-shop namespace deleted); mem_guard never fired.
- Human baselines run4 done: P08 (D5 4/5 smoke, D6 6/6), P10 (smoke OK, D6 6/6). results.csv has 25 rows.

### 2026-11-09 ~20:15 DeepSeek relay COMPLETE: 42/42 manifests
- 7 projects x 2 variants x 3 samples; every outputs/deepseek/*/*/s*/manifest.yaml is present and parses.
- Defect notes for the Discussion, from triage at import time (to be confirmed by R8):
  - P07 prod: s2 is identical to s3 (low sampling diversity). An allow-intra-namespace NetworkPolicy cancels out the narrower ones.
  - P08: hostPath docker.sock in 4 of 6 samples (all 3 neutral, prod s1 with type: Socket, which fails to mount on kind); wrong 8080 ports in neutral s3 and prod s1/s2; a broken user-sim command in neutral s3 and prod s1; all 6 pin mongo:3.4, while the human config's unpinned mongo is now broken.
  - P10: neutral s1 is missing the kubernetes-dashboard-certs Secret (pod stuck in ContainerCreating); neutral s2 has an egress NetworkPolicy blocking the API server (no DNS, no 6443) and a cluster-wide secrets read; prod s1 has a cluster-takeover ClusterRole (secrets CRUD, pods/exec, RBAC write); prod s2 sets KUBERNETES_SERVICE_HOST to status.hostIP and will crash; prod s3 looks the best.
- Next: R8 full evaluation of deepseek (42 configs) under mem_guard, then Gemini/Qwen completion and the GPT relay.

### 2026-11-09 GPT relay package created
- generation/relay/ChatGPT_prompts_for_relay.zip: 38 numbered prompts (each checked byte-for-byte against relay/prompts), plus README_FIRST.txt (Temporary Chat, default model, no tools, one new chat per file) and replies/NOTES.txt.
- Replies come back as replies/NN__<project>__<variant>__s<k>.txt. On import, strip the "NN__" prefix and place the files in relay/inbox/gpt/.

### 2026-11-11 Gemini batch: 33/42 now (+13 today)
- Batch ran 09:21-09:32: P07 neutral s3, production s2/s3; all 6 P03; P08 neutral s1-s3, production s2. Stopped on a 429 (daily quota) at P10 neutral s1.
- All 33 manifests parse except P07 production s3. That one is a valid truncated result: finishReason=MAX_TOKENS, 2,886 thinking + 5,898 output tokens against max_tokens=8192, so the YAML is cut mid-file. It is kept and scored as is.
  - Paper (Methodology/Threats): with Gemini's thinking models, thinking tokens count against the shared 8192 output budget, so the effective YAML budget is smaller than for non-thinking models.
- P07 neutral s2 crashed (KeyError 'parts'): the reply had no text parts, most likely the same MAX_TOKENS case with the whole budget spent on thinking. Nothing was saved, so the sample is re-run tomorrow as its first recorded attempt (disclose in Threats).
  - Fix 11: generate.py call_gemini now records a reply with no text as empty output (raw and finishReason saved) instead of crashing.
- P08 production s1 and s3: 503 errors persisted after 3 retries, so these are transport failures, not content. Re-run tomorrow.
- Remaining for Gemini (9): P07 neutral s2, P08 production s1/s3, all 6 P10. One batch tomorrow (2026-11-12) finishes it.

### 2026-11-11 12:49 Phase R8 started: Claude + DeepSeek (84 configs)
- Driver: evaluation/r8_batch.sh. It recreates the cluster per project, skips configs that already have a result JSON (so it can resume), times out each config after 40 min, and exits cleanly when evaluation/.r8_stop exists. Log: evaluation/r8_run.log.
- mem_guard 10000 MB runs alongside (evaluation/mem_guard.log). An INFRA failure writes no record, so the config is retried on the next run.
- Project order: P02, P04, P05, P08, P10, P07, P03 (small projects first).
- The 18 pilot LLM result JSONs were moved to evaluation/results_archive/pilot_pre_R8/. The pipeline was fixed after the pilot, and the Claude P05/P07 s1 manifests were regenerated, so all LLM configs are re-scored in R8. The 7 human results (final pipeline) are kept.
- Restart: attempt 1 (log kept as evaluation/r8_run_attempt1.log) produced no results. A wait command of mine wrongly touched evaluation/.mem_guard_stop, so the guard stopped at 12:50 while the batch kept running. The session was then interrupted and Docker restarted. R8 was restarted with the guard confirmed running first. Rule from now on: only touch .mem_guard_stop after the batch has exited.
- R8 finding (Discussion): claude P02 production s1. Static checks are clean (16/16 objects, D4 13/13), but D5 fails with CrashLoopBackOff on postgres:18. The container sets `capabilities: drop: [ALL]` with no runAsUser, so the root entrypoint likely cannot chown the data dir or switch to the postgres user. This is a hardening-breaks-runtime trade-off induced by the production prompt; all 3 neutral samples deployed and passed smoke. (Cause inferred from the manifest; the pod logs went with the namespace teardown.)

### 2026-11-11 Paper: Methodology/Threats brought in line with the decided scope
- Intro and Methodology now say seven projects (they said twelve) and list the four classes. The cluster add-on class is new; selection is explained as 7 of 12 prepared candidates.
- Methodology extraction now says "every fenced YAML block, joined" (it said "first block"; the code was changed in R7). Also added the containerd open-files cap (Fix 10) and that image tags are resolved at evaluation time.
- Threats:
  - Contamination paragraph corrected. The claim "deliberately includes several less-popular repos" was false for the 7; only P02 and P05 have fewer than 2k stars.
  - Qwen now says missing cells for the two largest prompts.
  - The Zabbix paragraph became "Project selection" (exclusion; scope fixed after the P05/P07 pilot, before the full run).
  - New paragraphs: web-interface sampling control (DeepSeek P07 production s2 == s3), reasoning tokens vs the 8192 budget (Gemini, including the P07 neutral s2 re-run, to be done 2026-11-12), and image tag drift (human P08 mongo).
- 06_threats.tex is now \input in main.tex. overleaf_files/ and overleaf_upload.zip were rebuilt. There is no local LaTeX, so compile on Overleaf to check.
- Still placeholder: the abstract ("results not yet available"). Results and Discussion are still to write (after R8/R9).

### 2026-11-11 Fix 12: D6 pod_delete recovery never detected for StatefulSet pods
- Symptom: deepseek P02 production s1 (n8n as a StatefulSet) showed pod_delete recovery_ok=False on all 3 reps while availability was 96%.
- Cause: d5d6.one_fault matched replacement pods by NAME (`name not in before`). A StatefulSet recreates the pod under the same name (n8n-0), so it never counted as "new" and the window ran the full 180 s. This was a pipeline bug, not a config defect.
- Fix: match by metadata.uid. It took effect from the next config process (around 16:20).
- Affected: deepseek P02 production s1 for sure, plus possibly production s2, which started at 16:08 on the old code. No human or pilot result had pod_delete False.
- TODO after the batch finishes: delete every result JSON with pod_delete recovery_ok=False whose victim belongs to a StatefulSet and was evaluated before the fix, then re-run r8_batch.sh. It only re-does the missing configs.
- Methodology wording ("replacement pod" from live pod state) is unchanged; the code now matches it.

### 2026-11-11 R9 stats script: evaluation/stats.py
- Implements paper §3.6. Outputs to evaluation/analysis/: report.md, configs.csv, summary_{neutral,production}.csv.
  - Descriptives per source and variant.
  - RQ1: Kruskal-Wallis plus Dunn (Holm), χ²/Fisher vs human (Holm), Cliff's δ; also run per human-intent stratum.
  - RQ3: Kruskal-Wallis across models; consistency as across-sample SD and agreement.
  - RQ5: paired Wilcoxon and exact McNemar.
  - RQ4: Spearman / point-biserial (Holm).
- No new dependencies: Dunn, Holm, Cliff's δ and McNemar are implemented with scipy.
- Two robustness additions (reviewer-proofing; add to §3.6 when writing Results):
  1. Project-level RQ1: the mean over the 3 samples, paired with the human config of the same project, Wilcoxon, n ≤ 7. This addresses pseudo-replication, since the samples are nested in projects.
  2. "Balanced" repeats of RQ1/RQ3 restricted to the projects every source covers. This addresses the project-mix confound: Qwen has no P03/P07.
- Not yet implemented: the Cohen's κ for Kubescape vs Trivy on overlapping checks (it needs per-check output and a mapping of matching checks). TODO before writing Results.
- Tested on the 17 configs so far; it runs end to end.
- stats.py now also computes Cohen's κ (Kubescape vs Trivy) from the saved raw scanner output. Unit: (config, concept); "fails anywhere".
  - 5 title-verified overlapping pairs: C-0016/KSV-0001 privilege escalation, C-0013/KSV-0012 root, C-0017/KSV-0014 read-only root fs, C-0270/KSV-0011 CPU limit, C-0271/KSV-0018 memory limit.
  - privileged, hostPath, hostNetwork and hostPort are CANDIDATE pairs. The report prints their Trivy titles once observed (P08 docker.sock should trigger hostPath), so they can be verified and added.
  - On 17 configs: overall κ=0.78. The memory limit pair is lowest (κ=0.43): Trivy flags it in 5 configs where Kubescape passes. This is a likely Discussion point; check whether it comes from init/sidecar containers.
- Qwen retries running (P02 neutral s2, s3 and production s3 OK so far).
- R8 finding: deepseek P02 production s2 is CrashLoopBackOff (postgres StatefulSet 0/1, so n8n is 0/1). Postgres runs with runAsUser 999 and runAsNonRoot, and PGDATA sits at the volume mount root (/var/lib/postgresql/data, no subPath). initdb must chmod 0700 a directory it doesn't own, so it fails. This is a second production-prompt hardening-breaks-runtime case on P02 (cf. claude production s1).
  - Threats note: kind's local-path provisioner ignores fsGroup, while many CSI drivers honor it. Here the chmod-by-non-owner would fail anyway, but say in Threats that storage-permission behavior is environment-specific.
  - D6 did not run (not deployed), so this result is not affected by Fix 12.

### 2026-11-11 16:40 Fixes 13-15, R8 restarted (attempt 3)
- **Fix 13 (my driver bug):** r8_batch.sh used `set -- $c` inside the loop, which overwrote "$@" (the model list). From the second project on, only "deepseek" was iterated, so claude P04+ would have been silently skipped. The batch was caught at P04 ("6 configs" instead of 12) and stopped. Changed to `read -r m v k`. No results were lost; the P02 results are all valid.
- **Fix 14 (D1 scoring):** the parse step used yaml.safe_load_all, which silently accepts duplicate mapping keys (the last value wins). YAML 1.2 and kubectl reject them. eval_runner now uses a StrictLoader that raises on a duplicate key.
  - Impact, checked over all generated manifests: only 2 change from parse OK to FAIL, and neither was scored yet. One is deepseek P02 production s3: an unfenced reply with 12 objects but a single `---`, so the objects merge (relayed text kept as is). The other is qwen P05 production s2, where a container has two `image:` keys. No human config is affected.
  - Methodology D1 wording should say "parsed with PyYAML, rejecting duplicate keys as YAML 1.2 and kubectl do".
- **Fix 15:** d2d3.kubescape treats an empty output file as ran=False instead of crashing on json.load. This crashed the deepseek P02 production s3 eval; that config will now fail D1 before reaching the scanners.
- R8 attempt 2 log: evaluation/r8_run_attempt2.log. Attempt 3 resumes at deepseek P02 production s3 and then P04 (12 configs).

### 2026-11-11 16:35 Gemini COMPLETE 42/42 (second key) + Fix 16
- The last 9 were generated with GEMINI_API_KEY_2 (user-supplied key from a second Google project; same model gemini-3.6-flash, same parameters). generate.py takes GEMINI_KEY_VAR to pick the key; the default is unchanged. Two intermittent 403s were transient: a probe right after (16-token output, not saved) returned 200, and the retries succeeded. The key never appears in api_gen_run.log (checked: 0 occurrences).
- **Finding (memorisation):** 3 Gemini P10 (Kubernetes Dashboard) replies came back EMPTY with finishReason=RECITATION, meaning Google's filter stopped output that reproduces training data: neutral s2, neutral s3, production s2. The official Dashboard manifest is widely published, so this is direct contamination evidence. It goes in the Discussion and is already in Threats.
  - Per the design (no retry on content), they are scored as returned: D1 parse failures.
- Gemini non-clean outputs: P07 production s3 MAX_TOKENS (truncated) plus the 3 RECITATION above. The other 38 are STOP and parse.
- **Fix 16 (D1):** an empty reply used to count as "parse OK, 0 docs" and ran into the scanners. Now a reply parses only if it yields at least one document and every document is a mapping; prose that parses as a YAML scalar also fails.
  - Impact, checked on all manifests: only the 3 RECITATION replies change. No scored result and no human config changes.
- eval_runner now records gen_finish_reason (Gemini finishReason / Groq finish_reason; None for web relays), and flatten and stats report it ("Generations not ended by the model" table).
- Generation status: claude 42, deepseek 42, gemini 42, qwen in progress, gpt 4/42 (relay pending).
- R8 finding: claude P04 production s1 shows the SAME pattern as claude P02 production s1. postgres:15-alpine has `capabilities: drop: [ALL]` and no runAsUser (fsGroup 70 only), so the db StatefulSet is CrashLoopBackOff 0/1 (8/9 replicas Ready, smoke fails). Running tally of the theme "production prompt -> hardening breaks the stateful component": claude P02 production s1, deepseek P02 production s2, claude P04 production s1. All neutral samples deployed so far. Key Discussion theme, and an RQ4 angle: static scores (Kubescape/Polaris) go up while runtime fails.

### 2026-11-11 Qwen COMPLETE: 30/30 feasible (P03 and P07 x 6 each = 12 infeasible on the Groq free tier, 413/token cap)
- All retries were transport 429s (rate limit) and eventually succeeded; no retry on content.
- Non-clean: P04 production s2 finish_reason=length (truncated, kept as returned). P05 production s2 has a duplicate `image:` key and fails D1 under Fix 14.
- Generation is now done for 4 of 5 models: claude 42, deepseek 42, gemini 42, qwen 30 (+12 infeasible). Only GPT (38 via the friend's relay) is outstanding.
- R8 finding: claude P04 production s3 has the same root cause. The db StatefulSet (postgres:15-alpine, drop ALL, no runAsUser) is CrashLoopBackOff, and result and worker crash as a consequence (they need the db). Tally: 4 configs (claude P02 production s1, claude P04 production s1 and s3, deepseek P02 production s2). Claude's production prompt adds `drop: [ALL]` to postgres in 3 of 6 samples so far, and none of its neutral samples do this.

### 2026-11-11 Figures: evaluation/figures.py → paper/figures/
- fig_dimensions_{neutral,production}.pdf/.png: 8 headline metrics (D1-D6), one row per source. Dot = median or proportion; bar = IQR or 95% Wilson CI.
- fig_prompt_effect.pdf: RQ5 dumbbell, neutral (open dot) → production (filled dot) per model.
- Replaced the radar chart promised in Methodology (radar area depends on axis order and scaling; reviewer bait). The Methodology sentence was updated with the reason.
- Colors: reference categorical slots 1-5 in fixed order for claude, deepseek, gemini, gpt, qwen; human is neutral gray. Validated with the dataviz validator (light): all checks pass, worst adjacent CVD dE 9.1. Contrast < 3:1 for 3 slots is mitigated by text labels on every row (identity is never color-alone).
- Re-run order after data changes: python evaluation/stats.py, then python evaluation/figures.py.
- R8 finding: deepseek P04 production s3 has the same root cause (postgres:15-alpine, drop ALL, no runAsUser; db 0/1). It also sets fsGroup 999, which is Debian postgres's GID, while the alpine image's postgres user is UID/GID 70. Tally: 5 configs (claude P02 production s1, claude P04 production s1 and s3, deepseek P02 production s2, deepseek P04 production s3). All are production-prompt configs; every neutral sample deployed. P02 and P04 are done; P05 has started.
- Threats: added the kind local-path / fsGroup caveat. It claims "the failures observed in this study have causes that do not depend on this". That is true for the 5 postgres failures so far (a root entrypoint without CHOWN/SETUID, or chmod by a non-owner, fails regardless of fsGroup). **VERIFY before submission:** re-check every D5 CrashLoopBackOff after R8 for an fsGroup-dependent cause, and soften the sentence if any exists.

### 2026-11-11 18:35 Fix 17: smoke/D6 client placement ignored named ports
- Symptom: deepseek P05 production s3 was Ready but smoke failed 4/4 with HTTP 000 and placement "no permitting ingress rule". Its own allow-web-ingress policy DOES admit clients from namespace ingress-nginx on port 8080.
- Cause: smoke.client_placement compared the Service's targetPort literally with NetworkPolicy ports. Here the targetPort is the NAME "http" and the policy port is the NUMBER 8080. Kubernetes treats both as the same container port; our code did not, so it found no permitting rule and probed from a blocked namespace.
- Fix: resolve the name and number via the containers behind the Service, and accept a policy port matching either.
- Impact: re-computed placement for every scored result; 10 change.
  - 7 had "any source" rules, so they were reachable anyway and smoke outcomes are unchanged.
  - 2 crashed regardless (claude P02 production s1, deepseek P04 production s3).
  - deepseek P05 production s3 was genuinely mis-scored, on both smoke and D6 availability (the prober was blocked).
- Decision: re-run all 10 plus the Fix 12 config (list: evaluation/r8_rerun_list.txt) after the main batch, so every result comes from the final pipeline. The fix is live for all configs from P08 on.
- Methodology already describes the intended behavior ("placed where the configuration's own NetworkPolicies admit a client"); the code now matches it.
- R8 finding: claude P08 neutral s1 is Ready 13/15 but smoke PASSES (the core shop works). Two auxiliary failures, both genuine:
  1. queue-master mounts hostPath /var/run/docker.sock with `type: Socket`. That socket doesn't exist on containerd nodes (kind, and most clusters since dockershim was removed in 1.24), so the pod can't mount the volume.
  2. user-sim (a 60 s load-test run) is a Deployment, so it exits and gets restarted into CrashLoopBackOff; it should be a Job.
  - The recorded reason is CrashLoopBackOff (user-sim). Discussion: "Ready" (all workloads) and "smoke" (user-facing function) can disagree. Report both, which we do. Also re-check the docker.sock theme across models for P08.
- R8 finding (Discussion theme: literal compose translation): claude P08 neutral s2 is Ready 13/14 with smoke passing; only queue-master is stuck in ContainerCreating on the docker.sock hostPath. The source: docs_bundle/docker-compose.yml:115 mounts /var/run/docker.sock for queue-master, and the HUMAN Kubernetes manifest does NOT. So the models carry a Docker-era host coupling from compose into Kubernetes. It is a security risk (Docker socket = host root; should show in D2 as a hostPath finding) and broken on containerd nodes. Seen so far in claude neutral s1 and s2, plus deepseek (neutral s1-s3, production s1, per import triage).

### 2026-11-11 19:10 R8 queued end-to-end: evaluation/r8_chain.sh (log: evaluation/r8_chain.log)
- Waits for the current claude+deepseek batch to print "R8 batch done". Then it deletes the 11 results in r8_rerun_list.txt and re-runs them (log r8_run_reruns.log), then runs gemini + qwen together, sharing one cluster per project (log r8_run_gemini_qwen.log).
- The mem_guard keeps running throughout. To stop everything cleanly: `touch evaluation/.r8_stop`. The batches exit between configs and the chain won't start the next stage. Stop mem_guard only after that, with `touch evaluation/.mem_guard_stop`.
- If the first batch dies without "R8 batch done" (e.g. a cluster setup failure), the chain just waits. Check r8_run.log and re-run r8_batch.sh by hand; it resumes.
- After R8: GPT (38 configs) once the relay replies arrive, then stats.py, figures.py, and the Results section.
- R8 finding: claude P08 production s1 is Ready 15/22 and smoke 3/5 (login and cart fail). carts, orders, shipping and queue-master (Spring Boot JVMs) never become Ready. Their livenessProbe has initialDelaySeconds 90, period 10 and the default failureThreshold 3, so kubelet kills the container at about 120 s. These JVMs need well over 120 s under a 500m CPU limit (the human carts took about 345 s at 300m), so they restart-loop forever. A genuine defect: a liveness probe without a startupProbe on a slow-starting JVM. Added -Xmx128m may slow them further.
  - Caveat for Threats/Discussion: JVM start time depends on hardware, so on much faster nodes they might clear 120 s. Classify as "probe timing vs startup" and mention the sensitivity.
  - Related fairness point: the human P08 config has NO readiness probes, so it counts as Ready (237 s) before carts actually listens. "Ready" rewards configs without probes; the smoke test is the honest functional check. Say this in the Discussion when comparing D5 Ready to smoke.
- Instrumentation (not a scoring change): d5d6.diagnostics() runs when D5 is not Ready, before namespace teardown. It records per-pod restarts, last exit code/reason (e.g. OOMKilled, 137) and Warning event counts (e.g. "Unhealthy: Liveness probe failed", FailedMount), stored in d5.diagnostics. Errors are caught, so it can never fail a measurement. Live from deepseek P08 onward.
  - It gives direct evidence for failure classification in the Discussion (e.g. confirms the claude P08 production liveness kill loop on the re-runs and the deepseek samples).
  - claude P08 production s1-s3: all 3 show the same 15/22 NotReady(probe) failure (carts, orders, shipping, queue-master). The cause is inferred from the manifest (liveness 90 s + 3x10 s vs slow JVM start); there is no event evidence because they ran before this instrumentation. Optional: re-run one with diagnostics to confirm before writing it up.

### 2026-11-11 20:10 Fix 19: D6 gate widened to "Ready OR smoke passes" (method change, disclosed)
- Evidence from the new diagnostics (deepseek P08 neutral s2): user-sim (weaveworksdemos/load-test:0.1.1) crash-loops with exit 139 (SIGSEGV, 5 restarts). It is an upstream image crash, not just a "run once and exit".
- user-sim is in docs_bundle/docker-compose.yml but NOT in the human manifest, so every LLM P08 config that faithfully includes it fails "all workloads Ready", even though the shop works (smoke 5/5). Under the old gate (D6 only if fully Ready), D6 would be missing for essentially all LLM P08 configs. A reviewer would object, since D6 targets the entry service.
- Change: D6 now runs if ready_ok OR smoke_ok; d6.gate records "ready" or "smoke_only".
  - stats.py adds strict sensitivity metrics: "D6 mean availability, fully-Ready only" and "D6 all recovered, fully-Ready only".
  - Methodology (pipeline paragraph and D6 paragraph) updated with the reason.
- Scores are unchanged: D5 Ready is still reported strictly. This only stops discarding measurable D6 data.
- 5 configs gain D6 and were added to r8_rerun_list.txt (now 17): claude P08 neutral s1-s3, deepseek P08 neutral s1-s2. The fix is live for configs started after 20:10.
- Discussion: "compose-faithful translation imports components the maintainers dropped (user-sim, docker.sock)". D5 Ready vs smoke divergence on P08.
- R8: deepseek P08 neutral s3 has smoke 1/5. The home page is 200, but catalogue and tags are 500, login 401 and cart 500. This confirms the import triage: backend Services on 8080 while the front-end calls :80, so a genuine wiring defect. user-sim fails with StartError (exit 128): its command is broken (also flagged at import). Not Ready and smoke fails, so D6 is correctly skipped.

### 2026-11-12 09:30 R8 resumed (attempt 4) + GPT sourcing decision pending
- Overnight: the laptop slept or shut down around 20:31 during deepseek P08 production s1, so Docker went down and the batch, chain and guard all stopped. 45/84 configs were scored, nothing lost (log kept as r8_run_attempt3.log). Docker was restarted, then mem_guard first, then r8_batch (claude deepseek) and r8_chain (17 re-runs, then gemini+qwen).
- **Keep the laptop awake** (power settings: never sleep while plugged in) until R8 is done, ~12 h.
- GPT: the friend is unavailable. The user proposed Playwright automation of ChatGPT web on their own login. I advised against it:
  1. OpenAI ToU prohibits automated/programmatic extraction of output.
  2. It contradicts Threats ("automated browser access ... abandoned ... rather than circumvented", for DeepSeek).
  3. A different account means a possibly different default model, so the GPT slot would be mixed.
  - Recommended: the OpenAI API (about $1-3 for 42 generations; exact model ID, temperature 0.2, max_tokens 8192, same as the other API models; regenerate all 42, archive the friend's 4 pilot samples). Fallback: the user's own manual relay (same method as DeepSeek). Awaiting the user's choice.
- 2026-11-12 GPT via the OpenAI API: code ready, waiting for the key.
  - generate.py has call_openai (Chat Completions; max_completion_tokens=8192; temperature 0.2). If the model rejects a non-default temperature (reasoning models), it re-sends once without and request.json records temperature=None, so the deviation is recorded, not hidden. timeout=600.
  - Pricing (third-party sources disagree; OpenAI's page was not reachable): flagship GPT-6 Astra about $10/$50 per 1M in/out tokens; GPT-6.1 Sol about $2/$10. Our 42 gens are ~0.33M input and ≤0.34M output tokens, so Astra costs ~$10-20. Recommended credit: $25.
  - Steps once OPENAI_API_KEY is in .env:
    1. GET /v1/models to confirm the exact flagship ID (don't trust blogs).
    2. Archive outputs/gpt (the friend's 4 web pilot samples) to outputs_archive/gpt_web_pilot/.
    3. models.yaml gpt: provider openai, model_id <exact id>, pinned_on 2026-11-12.
    4. Generate all 42 (one test call first), check parse/finish_reason, then evaluate in R8.
    5. Update Threats: remove the third-party/unconfirmed-default-model caveats and note the temperature if not applied.
- 2026-11-12 09:40 GPT decision: the user's friend will send the 38 relay replies today (zip ChatGPT_prompts_for_relay.zip, same account as the 4 pilot samples, so the GPT slot stays consistent). The Playwright automation attempt was dropped after 2 login attempts (the browser was closed before login both times; no prompt was ever sent and no CAPTCHA was observed). Its Chrome profile in the home dir (it may hold cookies) was deleted. generation/gpt_browser.py and call_openai are kept but unused. Nothing goes in the paper about browser automation for GPT, since none was used.
- R8 alive (09:37): mem_guard, r8_batch and r8_chain all running; deepseek P08 production s1 in progress.
- 2026-11-12 Contamination indicator implemented (stats.py contamination() → analysis/contamination.csv plus a report section). It was promised in Threats but did not exist yet.
  - Jaccard over normalised key paths ("struct") and over path=value pairs ("value"), for each config vs the human manifest.
  - The peer control is the mean Jaccard to the OTHER models' configs for the same project and variant; excess_value = human minus peer. The Threats text was updated to describe the control.
  - Early signal (claude+deepseek only, so a 1-peer control): claude P05 emojivoto has value-level similarity 0.60 to human vs 0.41 to peers (excess +0.19). Every other pair is ≤ +0.06. Re-check once gemini/qwen/gpt are in, and read it next to Gemini's RECITATION blocks on P10.
- 2026-11-12 RQ2 implemented (it was promised in Methodology but missing from stats.py):
  - (a) Rahman et al. 11 categories, detected with their own SLI-KUBE rules (TOSEM 2023, Table 3, read from papers/2023_Rahman...pdf), output to analysis/rq2_rahman.csv plus a report table. Judgement calls are written into Methodology D2: http://localhost is not "insecure HTTP"; hard-coded secret = a literal value under a user/password/passwd/token/secret key, in env or a Secret.
  - (b) KubeLinter smells vs Zhang et al. 2024, Table 2 (ChatGPT, n=95). The anti-affinity row's density/proportion are swapped in the PDF text; verified 4/1.49 KLOC = 2.7 and 4/95 = 4.2%. Density is the comparable unit (ours is a whole config, theirs often a single-object file). Neutral prompt only.
  - Sanity on 52 configs: docker.sock = 25% of claude and deepseek neutral (exactly the P08 samples), 0% human. Hard-coded secrets 57-75% for all sources. The production prompt nearly removes absent-limit and absent-securityContext.
- R8 + diagnostics (first evidence-backed classification): deepseek P08 production s1 is Ready 13/14, smoke 1/5.
  - carts, orders, shipping: exit 137 OOMKilled (memory limits too low for the JVMs; restarts 1-3).
  - queue-master: FailedMount ×10 on docker-sock (`type: Socket`).
  - smoke: catalogue, tags, login and cart fail (wrong Service ports, cf. import triage).
  - **CORRECTION RISK:** the claude P08 production s1-s3 failures were attributed to liveness kills from the manifest alone. They may be OOMKilled instead (Claude set -Xmx128m with 500Mi limits). Do NOT write either cause until the instrumented re-run of claude P08 production s1 (on the re-run list) shows the events.
- R8 + diagnostics: deepseek P08 production s2 is Ready 8/14, smoke 1/5. Readiness probes fail on 6 services (18-33 events each). The Go services (catalogue, payment, user) restart with exit 0 "Completed", i.e. kubelet probe kills with a graceful SIGTERM exit; the JVMs exit 137. Consistent with import triage (wrong ports, so probes miss). queue-master: OOMKilled. Cause class: probe/port mismatch, unlike s1 (OOM): different causes within one model and project.
- 2026-11-12 Scope integrity: the user (relaying the supervisor) asked to claim 12 tested projects and "replicate/simulate" results for the 5 untested ones. DECLINED: that is fabrication. Proceeding with Option A: 7 projects, reported as they are (already justified in Methodology/Threats), plus an explicitly labelled generalisation argument in the Discussion. Option B stays open: real D1-D4 static evaluation of the other 5 projects with API models, so the paper could truthfully say "all 12 statically, 7 at runtime".
- R8: deepseek P08 production s3 is Ready 9/15, smoke 3/5 (catalogue and tags fail). catalogue-db-0 (MySQL) crashes with exit 1 ×5, readiness fails on the JVMs, queue-master is OOMKilled. Import triage had called it "the best sample", so static reading ≠ runtime (Discussion/RQ4 example). P08 is complete: 0/12 claude+deepseek configs fully Ready, while human was Ready 14/14 (smoke 4/5 because of mongo drift). P10 started 10:31.

### 2026-11-12 11:20 Fix 20: per-check smoke prober placement
- claude P10 production s1 is Ready 4/4 and D6 is excellent (98-100% availability, 2 replicas), but smoke fails 2/4.
  - (a) scraper-healthz gets HTTP 000: the config's allow-scraper-from-dashboard admits only pods labelled k8s-app=kubernetes-dashboard, and our single prober was placed for the dashboard entry service. This is a pipeline artifact.
  - (b) dashboard-reaches-scraper returns "connected": false. This is genuine: the dashboard can reach the scraper by policy but isn't wired to it.
- Fix: smoke.run_smoke computes client_placement per check target. If a target admits a different client, it starts a short-lived "smoke-prober-N" there (creating or labelling the namespace if needed), then deletes it with --wait before the next check, because a prober wearing app labels could be selected by the app's Service. Each result records its prober.
- Impact over all scored results: only that one check changes, and the overall smoke verdict stays False because of (b). Added to r8_rerun_list.txt (18 unique). Methodology D5 text updated.
- Fix 20 follow-up: claude P10 production s2 (started 10:51, before the fix) has the same artifact. scraper-healthz is HTTP 000 because the scraper admits only dashboard pods; dashboard-reaches-scraper PASSES here, so correct placement likely flips smoke to True. Added to the re-run list (19 unique). TODO before the chain's re-run stage: re-run the per-check placement impact scan over ALL results evaluated before 11:20, in case anything else finished after the first scan.

### 2026-11-12 11:45 Fix 21: prober pods comply with the PSS "restricted" profile
- claude P10 production s3: the per-check prober (Fix 20) was correctly placed in the config's namespace, but that namespace enforces PSS restricted, so our plain `kubectl run` curl pod was rejected and the check read "HTTP none". Smoke False is an artifact here: the other 3 checks pass, including dashboard-reaches-scraper.
- Fix: smoke.prober_overrides() gives the smoke and D6 probers runAsNonRoot, uid 100 (curlimages' curl_user), seccomp RuntimeDefault, allowPrivilegeEscalation false, drop ALL. Live-tested in a temp restricted namespace: admitted, uid=100, curl → 200.
- Scan of all scored results for "HTTP none" (prober never started) found only this config. Added to the re-run list (20 unique). Methodology updated.

### 2026-11-12 12:10 Fix 22: kubeconform schema cache (network slowness → timeouts)
- deepseek P10 neutral s2, s3 and production s1 crashed: subprocess.TimeoutExpired, kubeconform at 180 s. GitHub raw was answering in ~20 s per schema file, and kubeconform re-downloads every schema each run.
- Fix: kubeconform `-cache tools/scanner-artifacts/kubeconform-cache`, timeout 600 s. The cache was warmed with every manifest (20 schemas, 494 s on this link). The cached files now pin the exact schemas used: include them in the replication package.
- The 3 crashed configs wrote no results, so the chain's second claude+deepseek pass (r8_run_reruns.log) evaluates them automatically. No scoring change: kubeconform logic is identical, only where schemas come from.
- R8 + diagnostics: deepseek P10 production s2 is Ready 1/2, smoke False. The dashboard is CrashLoopBackOff (exit 2, 5 restarts, 16 BackOff events), confirming the import-triage prediction (KUBERNETES_SERVICE_HOST=status.hostIP, so the API server is unreachable).
- R8 finding (Discussion: single-token slip cascades): deepseek P10 production s3, rated "best/closest to official" at import triage. Role rules[3].resourceNames has unquoted `- http:heapster:` (manifest line 85), which YAML parses as a mapping. kubeconform flags it invalid, the API server rejects the Role (17/18), so the dashboard has no RBAC: CrashLoopBackOff, Ready 1/2, smoke 1/4, D6 skipped. The official manifest quotes these names. Static triage by eye missed it; the validators caught it. A good RQ4/D1 example. P10 is complete; P07 started 11:41.
- 2026-11-12 12:35: claude P07 production s1 has been stuck in D5 prepull since 12:05. It is pulling us-central1-docker.pkg.dev/.../adservice:v0.10.3 (a newer tag than the one mirrored), and the network measured ~365 KB/s. Measurements are unaffected (prepull happens before deploy timing), but R8 is network-bound for new image tags. If it exceeds the 40-min per-config limit it is re-evaluated in the chain's second pass; Docker keeps pulled layers, so the retry is faster. Asked the user for a faster connection if possible.

### 2026-11-12 13:00 Fix 23: transient pull failures can no longer be scored as "unpullable", plus image pre-warm
- claude P07 production s1 failed: `docker pull adservice:v0.10.3` hit its 1800 s limit on a ~365 KB/s link (no record written; retried in the second pass).
- **Latent scoring risk found:** d5d6.docker_pull returned False on ANY non-timeout failure (dropped connection, TLS timeout). provision() then recorded the image as "not pullable as written" and aliased it or marked it unavailable, so a network glitch would have been scored as a config defect.
  - Fix: False only on a definitive registry answer (manifest unknown, not found, unauthorized, denied, invalid reference, name unknown), or on "no such host" while Docker Hub is reachable. Transient failures are retried 3x and then raised as INFRA (no record).
  - Re-verified definitive cases: ghcr.io/online-boutique/frontend:latest → False (5 s); a bare non-existent name → False (6 s).
  - Audited the existing ledger: all 33 not-as-written entries are genuinely non-existent refs (retired gcr.io/*:latest, bare names, invented ghcr.io/online-boutique). No past result is affected.
- evaluation/prewarm_images.py: provisions every not-yet-mirrored image of the not-yet-evaluated configs via the same d5d6.provision() (log: evaluation/prewarm.log), outside any per-config deadline, in the order P07, P03, P08. 31 refs: the 11 Online Boutique v0.10.3 images, 6 Grafana tags, postgres:16-alpine, the renderer, and 13 qwen `weaveworks/*` names (likely invented; the real org is weaveworksdemos). Runs alongside the batch; Docker de-duplicates concurrent layer downloads.

### 2026-11-12 22:30 Session restart + host sleep (Fix 24)
- The laptop slept ~12:40-19:10. Docker stopped the kind node containers while `kind get clusters` still listed k8sgen, so the batch's cluster_up passed and 18 configs crashed in a row (ValueError in cluster_now: empty `docker exec date` from a stopped control plane). Every deepseek P07 and all claude+deepseek P03 failed, with no results written, so nothing is mis-scored.
- Main pass ended 21:21 with 24 FAILED in total (18 dead cluster, 3 kubeconform pre-cache, 3 pull timeouts). The chain then deleted the 20 re-run results and started the re-runs. claude P02 production s1 re-run hit the 40-min limit (exit 124, cause unclear, retried in the sweep); production s2 OK.
- Fix 24: r8_batch.sh cluster_up also requires a running control-plane container and a `kubectl get nodes` answer, otherwise it recreates the cluster. The file was replaced atomically (bash was executing it).
- Added a sweep waiter: after "chain: all done" it runs `r8_batch.sh claude deepseek gemini qwen` (log r8_run_sweep.log) to pick up every config still missing a result.
- Prewarm finished: 19 refs pulled and mirrored; 12 unavailable, all qwen `weaveworks/*` (the real org is weaveworksdemos). These are definitive not-found answers, so a genuine Qwen defect.
- Clocks checked after the sleep: host, kind node and registry are in sync. Disk: 76 GB free.

### 2026-11-12 23:00 R10 started in parallel with R8: Results + Discussion drafted; tables auto-generated
- evaluation/tables.py writes paper/tables/*.tex from analysis/: overview per variant (D1-D6 per source), D5 failure classes, Rahman categories. Every Results number comes from code.
  - Pipeline after any data change: `python evaluation/stats.py && python evaluation/figures.py && python evaluation/tables.py && python paper/build_overleaf.py`, then zip.
- paper/sections/04_results.tex: RQ1-RQ5 structure, tables and figures included. Values that depend on the final run are `% TODO-FINAL` comments (never typed from memory). grep TODO-FINAL before submission.
- paper/sections/05_discussion.tex covers 7 themes, each grounded in diagnosed R8 failures: hardening breaks the workload (postgres caps), literal compose translation (docker.sock, user-sim), what static reading misses (unquoted http:heapster:, OOM limits), Ready ≠ working, memorisation (Gemini RECITATION, contamination excess), generalisation (labelled as an expectation, per Option A), implications. Counts are TODO-FINAL.
- main.tex adds booktabs and inputs 04 and 05 (order: 01, 02, 03, 04, 05, 06).
- build_overleaf.py now inlines nested \input (sections → tables), skips commented lines, and copies figures/*.pdf. The overleaf_upload.zip was rebuilt (8 files). Not compiled locally (no TeX).
- Grafana suggestion from the user: declined for the paper figures (journals need vector, code-generated figures; Grafana is time-series dashboards with PNG export, plus RAM contention with R8). Offered a Grafana results dashboard for the viva/presentation after R8 instead.
- Remaining R10: Conclusion, final abstract, fill TODO-FINAL after R8 + GPT.
- 2026-11-12 23:15:
  - paper/sections/07_conclusion.tex drafted (3 findings, implications, future work; 2 TODO-FINAL) and wired into main.tex after Threats. The bundle was rebuilt.
  - README.md (replication package) written: layout, requirements, the 4-command regeneration of all numbers/tables/figures from stored results, re-running evaluation and generation, notes on image-tag resolution and PROGRESS.md as the log. All commands verified to exist (--locked, --recreate, relay import).
  - tools/versions.lock now pins the kubeconform schema cache.
  - TODO-FINAL count: 20 (results 12, discussion 6, conclusion 2).

### 2026-11-12 23:40 GitHub repository
- https://github.com/nabeedjamshedali/k8sgenbench (PRIVATE; created via the API with the user's stored Git Credential Manager login; the token was never printed). Branch main, initial commit aa16219, 2,259 files. No co-author trailer, per the user.
- Excluded via .gitignore (verified before the push):
  - .env;
  - datasets/.cache/ (490 MB of upstream clones, re-fetchable);
  - tools/bin/ (703 MB of binaries, reinstallable);
  - papers/* except our own index, bib and verification (third-party PDFs, plus a personal employment letter that must never be pushed);
  - generation/.tmp_hf_profile/ and any *_profile/ or .tmp_*/ (browser profiles may hold cookies);
  - LaTeX build outputs and runtime stop files.
- Secret scan before the push: none of the .env key values appear in any tracked file; regex hits were only Trivy's own example rule files.
- core.autocrlf=false in this repo, so files stay byte-identical (prompt hashes, manifests).
- From now on: commit and push after each milestone (plain commit messages, no co-author lines).
