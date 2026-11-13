# Removing Kaggle-derived data from the whole git history (prepared, not run)

Run this **before the repository is made public again**. Nothing in this file has been executed.

## Why

DATA-1 untracked the files below, but they remain in earlier commits, so anyone who can read the repository can still recover them. Kaggle's competition rules do not allow redistributing the data.

Paths to remove from every commit:

```
dashboard/data/fact_actuals.csv
dashboard/data/fact_forecast.csv
dashboard/Dashboard_screenshots.pdf
outputs/forecasts/                                   (all files; they carry the actual sales)
outputs/archive/rossmann_sample_v1/rossmann_statistical.csv.gz
```

Also delete the local branch `backup-before-rewrite` (it holds the old history; it is not on GitHub).

## Preconditions

- The repository is private and nobody else has cloned it. All work is committed and pushed.
- Python with pip is available (git-filter-repo is not installed on this machine): `pip install git-filter-repo`.
- Copy the ignored data files out of the working folder first (`outputs/forecasts/`, `dashboard/data/fact_*.csv`); a fresh clone will not contain them.

## 1. Backup (mirror clone)

```
cd "F:\_Arden (MSc Data Science)\6- Final Project\Calude Code"
git clone --mirror https://github.com/Farid89-data/Hybrid-ARIMA-LSTM-retail-sales-forecasting-with-BI-integration.git backup_mirror.git
```

Keep `backup_mirror.git` until the check in step 5 has passed. It still contains the data, so never upload it.

## 2. Work in a fresh clone

git filter-repo refuses to run on a repository that is not a fresh clone.

```
git clone https://github.com/Farid89-data/Hybrid-ARIMA-LSTM-retail-sales-forecasting-with-BI-integration.git clean_repo
cd clean_repo
git fetch origin audit-fixes main
```

## 3. Rewrite the history

```
git filter-repo --invert-paths ^
  --path dashboard/data/fact_actuals.csv ^
  --path dashboard/data/fact_forecast.csv ^
  --path dashboard/Dashboard_screenshots.pdf ^
  --path outputs/forecasts/ ^
  --path outputs/archive/rossmann_sample_v1/rossmann_statistical.csv.gz
```

(In Git Bash use `\` instead of `^` at the line ends.) This rewrites every branch and tag and removes the `origin` remote.

## 4. Check the rewritten clone before pushing

```
git rev-list --objects --all | findstr /i "fact_actuals fact_forecast outputs/forecasts Dashboard_screenshots rossmann_statistical.csv.gz"
git log --all --oneline -- outputs/forecasts dashboard/data/fact_actuals.csv dashboard/data/fact_forecast.csv
git count-objects -vH
```

The first two commands must print nothing. Then restore the ignored files from your copy, create a virtual environment and run `pytest -q` (71 tests) to confirm the code still works.

## 5. Force-push

```
git remote add origin https://github.com/Farid89-data/Hybrid-ARIMA-LSTM-retail-sales-forecasting-with-BI-integration.git
git fetch origin
git push --force-with-lease origin audit-fixes
git push --force-with-lease origin main
```

`--force-with-lease` refuses to overwrite commits that someone else pushed after your fetch. If the push says "stale info", fetch again and repeat. Do not use plain `--force`. Add `git push --force-with-lease origin --tags` only after tags exist.

## 6. Fresh-clone verification

```
cd ..
git clone https://github.com/Farid89-data/Hybrid-ARIMA-LSTM-retail-sales-forecasting-with-BI-integration.git verify_repo
cd verify_repo
git rev-list --objects --all | findstr /i "fact_actuals fact_forecast outputs/forecasts Dashboard_screenshots"
git log --all --oneline | find /c /v ""
```

The first command must print nothing. Also search for other raw data: `git rev-list --objects --all | findstr /i ".csv .gz .pkl .parquet"` should list only the small tables, the experiment log and the dimension tables.

## 7. Finish

- Replace your working folder with a fresh clone of the cleaned repository (or run `git fetch origin` and `git reset --hard origin/audit-fixes`), then put the ignored data files back.
- Delete the local branch `backup-before-rewrite` and, once step 6 has passed, the mirror backup.
- Ask GitHub support to run garbage collection on the repository and to clear cached views and `refs/pull/*` if any pull request existed, because GitHub can keep unreachable objects for a while.
- Then merge `audit-fixes` into `main`, create the tag `v1.0-submission` and make the repository public.

## Consequences

- **New commit hashes.** Every commit from the first one that touched these files onwards gets a new hash. Old hashes in your notes and in `reports/review_queue.md` (for example `bd1641b`, `0cfb220`, the A1-1 evidence) will no longer exist. The review queue should be read before the cleanup if you need those hashes. The dissertation text does not cite hashes. The `git_commit` column of `EXPERIMENT_LOG.csv` holds hashes that will point to nothing; the dates and run IDs stay valid.
- **Tags.** Tags made before the rewrite point to old commits. Create `v1.0-submission` after the cleanup and the merge.
- **Links.** Links to a specific commit or file at a commit break. The repository URL cited in the dissertation does not change.
- **Other copies.** Existing clones, forks and the mirror backup keep the old history. Pull requests, if any, are closed or lose their commits.
- **Unrelated history is unchanged** apart from the new hashes: code, tests, the report sources and the other tables stay.
- **Alternative without history.** Create a new repository with one commit of the current files. This is simpler and certain, but the URL changes (the reference `negahbani2026` and the text must then be updated) and the history is lost.
