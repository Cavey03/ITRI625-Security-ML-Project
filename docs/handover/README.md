# Handover briefs

Each brief is a self-contained task: what to build, its inputs and outputs, and a
checklist that defines "done". Work on the named branch and merge it into `main` when done
(see [CONTRIBUTING.md](../../CONTRIBUTING.md)).

| Priority | Brief | Branch | Status |
|---|---|---|---|
| **1** | [TF-IDF baseline](02_tfidf_baseline.md) | `feat/tfidf-baseline` | ready: the notebook's comparison section is waiting for it |
| 2 | [EDA](01_eda.md) | `feat/eda` | ready |
| 3 | [Sample emails + user documentation](03_samples_and_docs.md) | `docs/samples`, `docs/user-guide` | ready |

**New here? Read [START_HERE.md](START_HERE.md) first.** It covers setup, data, the git workflow and the order of work.

Shared references: [API contract](../api_contract.md) · [desktop app spec](../app_spec.md) ·
label convention `0 = legitimate, 1 = phishing`.

**No task here blocks Kyle's milestones.** Kyle's data pipeline does its own leakage
checks, and the baseline predictions are only needed for the comparison plots in
Milestone 7. If a brief is unclear or seems wrong, ask before working around it.
