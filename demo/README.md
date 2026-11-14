# K8sGenBench demo

A small web app for showing how the study works: pick a project, compare its shipped (human) manifest with an
LLM-generated one, re-run the evaluation pipeline live, and print a comparison report.

## Start

```
python demo/app.py
```

It opens http://localhost:8800 in the browser. No extra packages are needed beyond those the study already uses.

## What it shows

- **Recorded**: the stored study results in `evaluation/results/` (all six dimensions), shown instantly, with the
  root cause from `evaluation/d5_root_causes.csv` for configurations that failed.
- **Run live**: re-runs the same pipeline on the selected configuration and streams each stage. Without the
  cluster it runs the static checks (parse, schema, Kubescape, Trivy, kube-score, Polaris, KubeLinter,
  requirements). With the cluster and "include deployment" ticked, it also deploys, runs the smoke test and
  injects pod failures (D5/D6, 3-8 minutes). Live results go to `demo/runs/` and never replace the study's results;
  the page shows them next to the recorded ones.
- **Report**: a side-by-side page for the two selected configurations; "Save as PDF / print" uses the browser.

## Deployment checks (D5/D6)

Start Docker Desktop, then create the cluster (a few minutes):

```
python tools/setup_cluster.py
```

The badge at the top of the page shows whether the cluster is running.

## Suggested demonstration

1. Project **Voting App**. Left: Human. Right: Claude, production prompt, sample 1.
2. The generated configuration scores higher on the scanners (Kubescape 91.3 against 72.7 for the human manifest),
   yet it does not work: its root cause shows the hardening (all capabilities dropped) stops PostgreSQL from starting.
   This is the paper's main finding in one example.
3. Switch Right to Claude, neutral prompt, sample 1: lower scores, but it deploys and passes the smoke test.
4. Click **Run live: right** to show that the pipeline reproduces the recorded numbers.
5. Click **Report** and save it as a PDF.
