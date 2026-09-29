# Handover briefs

Each brief is a self-contained task: what to build, its inputs and outputs, and a
checklist that defines "done". Work on the named branch and merge through a pull request
(see [CONTRIBUTING.md](../../CONTRIBUTING.md)).

| # | Brief | Branch | Can start |
|---|---|---|---|
| 1 | [EDA](01_eda.md) | `feat/eda` | now (raw data) |
| 2 | [TF-IDF baseline](02_tfidf_baseline.md) | `feat/tfidf-baseline` | code now; run after Milestone 4 splits |
| 3 | [Sample emails + user documentation](03_samples_and_docs.md) | `docs/samples`, `docs/user-guide` | samples now; guide once the desktop app exists |

Shared references: [API contract](../api_contract.md) · [desktop app spec](../app_spec.md) ·
label convention `0 = legitimate, 1 = phishing`.

**No task here blocks Kyle's milestones.** Kyle's data pipeline does its own leakage
checks, and the baseline predictions are only needed for the comparison plots in
Milestone 7. If a brief is unclear or seems wrong, ask before working around it.
