# Text for GitHub Support (Option A)

Send at https://support.github.com (Contact support, then a repository or "Remove cached data" topic). Attach nothing; the hashes below are enough.

---

**Subject:** Please remove cached pull request refs and unreachable data after a history rewrite, and refresh the contributors list

**Repository:** Farid89-data/Hybrid-ARIMA-LSTM-retail-sales-forecasting-with-BI-integration

Hello,

On 13 November 2026 I rewrote the history of this repository twice with `git filter-repo` and force-pushed `main` and `audit-fixes` each time. The rewrites removed (1) commit-message trailers that named a co-author, (2) data files derived from Kaggle competition data that I may not redistribute, and (3) the directory `docbuild/chapters/` (unpublished dissertation text). The current `main` is 59a4fe36e45b708f956e526737388f7d2d2ae7db and `audit-fixes` is 6deacc85047bc37fba020204ccd93d07d10ca65b. A fresh clone shows no trace of those paths and one author.

These refs still hold the old history and cannot be changed by me:
- `refs/pull/1/head` (pull request #1), commit 779fc8dafdf8d0e080bcbd889636539062bf0bb9
- `refs/pull/2/head` (pull request #2), merged, whose commits contain `docbuild/chapters/`
- `refs/pull/3/head` (pull request #3), merged, whose commits contain `docbuild/chapters/`

Pre-rewrite tips: `main` 61c01c3a49880cd74508f5573eda7f9a187bc967; `audit-fixes` f187d224993b85f32a192d3184978e76bc831ace.

Could you please:
1. remove `refs/pull/1/head`, `refs/pull/2/head` and `refs/pull/3/head` (or the cached commits of those pull requests), and any other unreachable commits and cached views that hold the old history, and run garbage collection, so that the old commits are no longer retrievable by hash;
2. refresh the contributors list and graph so that they match the current history (one contributor);
3. confirm when this is done.

Thank you.
Farid Negahbani

---

# Option B (not run): delete and recreate the repository

Do this only if GitHub Support cannot clear the pull request refs, or the contributors page still shows another name after Option A.

1. Backup: `git clone --mirror https://github.com/Farid89-data/Hybrid-ARIMA-LSTM-retail-sales-forecasting-with-BI-integration.git backup_before_recreate.git` (keep it outside the repository).
2. What will be lost: pull requests #1 to #3 and their discussion, the Actions run history and badges history, stars and watchers (none to be assumed), any Pages settings, branch protection rules and repository settings (description, topics, secrets). Issues: none are known; check first.
3. Note the description, topics and visibility from the repository page.
4. `gh repo delete Farid89-data/Hybrid-ARIMA-LSTM-retail-sales-forecasting-with-BI-integration --yes` (needs the `delete_repo` scope).
5. `gh repo create Farid89-data/Hybrid-ARIMA-LSTM-retail-sales-forecasting-with-BI-integration --public --description "<same description>"` (use `--private` if the visibility was private).
6. From the clean local repository: `git remote set-url origin <url>`, `git push origin main audit-fixes`, and `git push origin --tags` once tags exist.
7. Re-enable GitHub Pages and branch protection if they were used; re-add topics.
8. Check that the URL opens, the Actions run is green and the contributors list shows only Farid Negahbani.
