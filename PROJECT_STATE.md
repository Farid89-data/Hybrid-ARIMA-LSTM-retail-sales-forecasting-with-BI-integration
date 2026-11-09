# Project State

**Read this file first at the start of every session**, then `DECISIONS_LOG.md`, `EXPERIMENT_LOG.csv` and `..\Refrence\reference_ledger.csv`.

| Field | Value |
|---|---|
| Project | A Hybrid ARIMA-LSTM Framework for Retail Sales Forecasting with Business Intelligence Integration (COM7014) |
| Current phase | **Experiments running; report drafted except result-dependent sections** |
| Last updated | 9 November 2026 (late evening) |

## Gate A answers (9 Nov 2026)

Literature through scholarly APIs (OpenAlex, Crossref) with publisher verification; Kaggle files supplied by the student in `Dataset\` (no other downloads); handbook format with the template's look; ethics approved including participants (study not yet run); report to replace everything after the title page.

## Completed

| Area | Item | Output |
|---|---|---|
| Data | Integrity check of all nine Kaggle files; checksums | `outputs/data_check/`; `data/checksums.sha256` |
| Data | Prepared panels (M5: 10 stores; Rossmann: 20 sampled stores) and EDA | `outputs/interim/*_prepared.pkl`; `outputs/figures/eda_*` |
| Literature | 47 verified journal articles (2023-2026) and 2 dataset pages; reading notes; second-pass verification | `..\Refrence\` |
| Literature | Zotero exports: CSL-JSON, BibTeX, RIS, Zotero RDF | `..\Refrence\references.*` |
| Code | Package `src/`, scripts, 32 unit tests (all passed on 10 Nov 2026) | `src/`, `scripts/`, `tests/` |
| Report | Chapters 1-3 drafted and fact-checked; Chapter 4 non-result sections; appendices A-G drafted | `docbuild/chapters/` |
| Dashboard | Data dictionary, Power Query, DAX, build guide, page specification, accessibility checklist, test plan, wireframes, star schema | `dashboard/`; `outputs/figures/dash_*` |
| Repository | requirements (pinned), environment.yml, CI workflow, LICENSE (MIT), CITATION.cff, data README | repository root |

## Running / pending

| Item | Status |
|---|---|
| Rossmann statistical stage | Running (checkpointed per store) |
| Rossmann neural stage (ffnn, lstm, hyb_d, hyb_z, hyb_ms) | Pending |
| M5 statistical and neural stages | Pending |
| Evaluation (`scripts/run_evaluation.py`), report tables, dashboard export, notebooks | Pending results |
| Chapter 4 results sections, Chapter 5, abstract, Appendices H and I | Pending results |
| Word build with field update and PDF export; citation audit; QA report; viva pack | Pending |
| User study | Approved, not conducted (needs real participants) |

## Open issues for the student

| # | Issue |
|---|---|
| 1 | Arden Harvard guide not supplied: reference format is provisional (comment in the document) |
| 2 | Arden generative-AI policy not supplied: Appendix A must be checked and completed by the student |
| 3 | Word-count policy not supplied |
| 4 | Title page kept unchanged as instructed; it still reads "(Project Proposal)" and "1767" words |
| 5 | Exception Register for pre-2023 sources not approved: no pre-2023 source is cited (SUS original source pending) |
| 6 | Dashboard `.pbix` must be assembled in Power BI Desktop and the functional tests run |
| 7 | LICENSE and CITATION.cff use the Git identity (Farid Negahbani); confirm |
