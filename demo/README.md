# K8sGenBench demo

A small web app that shows what the study found and how it was measured: the headline numbers, every model under
both prompts, a check-by-check comparison of a project's shipped (human) manifest with an LLM-generated one, a live
re-run of the evaluation pipeline, and a printable report.

## Start

```
python demo/app.py
```

It opens http://localhost:8800 in the browser. No extra packages are needed beyond those the study already uses.

## What the page shows

1. **What we found**: 198 generated configurations, 92.9% valid files, only 59.6% working on a real cluster, and the
   production prompt raising the security score while fewer configurations work. Computed from `evaluation/results/`.
2. **Every model, both prompts**: share of configurations that work and median security score (Kubescape) per model
   and prompt, with the human manifests as reference. Click a cell to compare one of its configurations with the
   human manifest of the selected project.
3. **Compare two configurations**: one aligned table (Check | Left | Right) grouped by dimension D1-D6, with a
   plain-English sentence on top, the better score highlighted in green, a "?" explanation on every check, and, for
   failed configurations, the root cause from `evaluation/d5_root_causes.csv` in plain words. The two manifests are
   under "Show the two manifests".
4. **Re-run live**: runs the same pipeline on the selected configuration now and reports how many values reproduced
   the recorded result. Without the cluster it runs the static checks (D1-D4, a few seconds). With the cluster and
   "include deployment" ticked, it also deploys, runs the smoke test and injects pod failures (D5/D6, 3-8 minutes).
   Live results go to `demo/runs/` (cleared at every start) and never replace the study's results.
5. **Open printable report**: summary, method, the comparison and a glossary; "Save as PDF / print" uses the browser.

## Deployment checks (D5/D6)

Start Docker Desktop, then create the cluster (a few minutes):

```
python tools/setup_cluster.py
```

The badge in section 4 shows whether the cluster is running.

## Suggested demonstration

1. The page opens on **Voting App**, Human vs Claude, production prompt, sample 1.
2. The sentence on top says it: Claude's configuration has the higher security score (91.3 vs 72.7), yet it does not
   work, because the hardening (all capabilities dropped) stops PostgreSQL from starting. This is the paper's main
   finding in one example.
3. Click the Claude / neutral cell in section 2: lower scores, but it deploys and passes the smoke test.
4. Click **Re-run right** to show that the pipeline reproduces the recorded numbers.
5. Click **Open printable report** and save it as a PDF.
