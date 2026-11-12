# Reference Verification Record

**Date:** 2026-09-26
**Scope:** all 41 references cited in `paper/overleaf_files/main.tex` (Introduction and Literature Review)
**Result:** 41/41 verified; no fabricated or unverifiable reference.

## Method
| Evidence | Source | Rule |
|---|---|---|
| DOI | Crossref API (`api.crossref.org/works/<doi>`) | title similarity > 0.85, first author and year must match |
| DOI not in Crossref | DOI handle system (`doi.org/api/handles/<doi>`) | must resolve to the publisher's article page |
| arXiv ID | arXiv abstract page metadata (`citation_title`, `citation_author`) | title and first author must match |
| Conference papers without a DOI | official proceedings pages (NeurIPS, MLSys, PMLR) | title and author list must match |
| "Accepted at …" venue claims | the authors' own arXiv comments / journal-ref field | the claim must appear there |
| Tools and standards | official website | HTTP 200 |
| Numbers quoted in the text | full text of the downloaded PDF | the exact number must appear |

## Results

**DOI via Crossref (17 references):** rahman2023k8smisconfig, rahman2019sevensins, shamim2020xicommandments, zhang2026k8sconfigdefects, minna2025helm, ghorab2025k8sllm, kapetanidou2025k8sscanning, lanciano2023declarative, pujar2023ansiblewisdom, zhang2026iacgen, jana2026terraformer, hassan2026itab, ye2025llmsecconfig, zhang2024genaismells, pearce2022asleep, fu2025copilotweaknesses, khoury2023chatgptsecure. All matched (title similarity 0.99–1.00).

**DOI via the DOI handle system:** jcomsec2026aivshumank8s. DOI 10.22108/jcs.2026.148046.1195 resolves to https://jcomsec.ui.ac.ir/article_30574.html, and the PDF is in `papers/`.

**arXiv (16 IDs):** all titles and first authors match arXiv. These include malul2024genkubesec, sgancohen2025kubeguard, kozachok2026k8sdistillation, ding2026fdebench, krieger2026k8sscanners, santosvargas2026secureterraform, ghorab2026inthewild, shaikh2026kutie and bhatt2023cyberseceval.

**Official proceedings:**
- xu2024cloudevalyaml: MLSys 2024 proceedings. The author order was corrected to match the official record.
- kon2024iaceval: NeurIPS 2024 Datasets and Benchmarks proceedings.
- vero2025baxbench: PMLR vol. 267 (ICML 2025), `vero25a`.

**Venue claims confirmed by the authors' arXiv entries:**
- SBSeg 2026 (2608.02672)
- AIware 2026 (2609.27030, journal-ref)
- LLMSec @ ESORICS 2026 (2607.25995)

**Tools and standards (HTTP 200):** kubeconform, Kubescape, kube-score, Polaris, KubeLinter, Checkov, Trivy, CIS Benchmark, OWASP K8s Top 10, Pod Security Standards. For the NSA/CISA Hardening Guide, the official PDF blocks automated requests, so it was verified through the CISA announcement page instead.

**Quoted numbers:** 58 numbers and phrases checked against the source PDFs, and all were found. Examples: 1,051/2,039/13.9% (Rahman 2023), 35.8% (Zhang 2024), 5,138 (Minna 2025), 0.515 (CloudEval-YAML), 20.8–30.2%/8.4% (IaCGen) and 94.3%/40.2% (LLMSecConfig).

## Rule for later sections
Every new reference must pass the same checks before it goes into `references.bib`. The scripts are `tools/verify_refs.py` and `tools/verify_claims.py`; rerun them before each submission.
