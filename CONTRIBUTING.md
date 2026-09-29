# Working on this repo

Two contributors. The git history is marked, so keep it clean and readable.

## Branches

- `main` holds working, reviewed code only. **No direct commits to `main`.**
- Every piece of work gets a feature branch off the latest `main`:

  | Prefix   | Use for                     | Example                    |
  |----------|-----------------------------|----------------------------|
  | `feat/`  | new functionality           | `feat/distilbert-training` |
  | `data/`  | data pipeline / splits      | `data/dedup-and-splits`    |
  | `fix/`   | bug fixes                   | `fix/api-empty-body`       |
  | `docs/`  | README, handover briefs     | `docs/api-contract`        |

- When the work is finished and tested, merge it into `main` with a merge commit, then push:
  ```bash
  git switch main
  git pull
  git merge --no-ff <branch>
  git push
  ```
  `--no-ff` keeps a merge commit, so each piece of work stays visible as its own branch in
  the history. Don't squash, so both authors stay visible. Pull requests are optional.
  Open one if you want the other person to review first.
- Delete the branch after it is merged.

## Commits

- Small and focused: one logical change per commit.
- Message format: `<area>: <what changed, imperative>`, for example
  `data: deduplicate emails before splitting`, `api: add /explain endpoint`.
- Put the "why" in the commit body when it isn't obvious.

## The notebook (avoiding merge conflicts)

`notebooks/itri625_phishing.ipynb` is owned by Kyle. `.ipynb` files are JSON and
merge badly, so:

- Teammate code (EDA, TF-IDF baseline) goes in `src/` modules or a separate
  notebook (`notebooks/eda.ipynb`). Kyle imports or pulls it into the main notebook.
- **Commit the notebook with its outputs.** Figures and metrics must be visible in the
  committed file (-10 marks otherwise). Do not use `nbstripout` or clear outputs.

## Never commit

Raw data, processed splits, model weights, `.venv/`, `kaggle.json`. `.gitignore`
already excludes them. Check `git status` before every commit.
