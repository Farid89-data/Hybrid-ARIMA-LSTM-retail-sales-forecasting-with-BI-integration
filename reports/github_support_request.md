# Text for GitHub Support

Send at https://support.github.com (Contact support, then a repository or "Remove cached data" / contributors topic). Send it while the repository is private. Attach nothing; the hashes below are enough.

---

**Subject:** Please refresh the contributors list and remove cached/unreachable data from a private repository after a history rewrite

**Repository:** Farid89-data/Hybrid-ARIMA-LSTM-retail-sales-forecasting-with-BI-integration (currently private)

Hello,

On 13 November 2026 I rewrote the history of this repository with `git filter-repo` and force-pushed `main` and `audit-fixes`. The rewrite removed (1) commit message trailers from an AI coding tool that had listed the tool as a co-author, so that the tool no longer appears as a contributor, and (2) data files that I am not allowed to redistribute (competition data derived from Kaggle). No other change was made to the commits. A full backup of the old history is kept outside GitHub.

The repository now has these refs:
- `main` at 1aea0d9ed667653a01a1f83e762c4a7bac4c96d2
- `audit-fixes` at f85c5e326ace8292676a49e51dd69231620b8dec
- `refs/pull/1/head` (pull request #1) still points to the old commit 779fc8dafdf8d0e080bcbd889636539062bf0bb9

Old commit hashes involved:
- old `main` tip: 4f755ca5cebe609a4552bacd83f44460b0dba4df
- old `audit-fixes` tip: d80b4a36b2f86da2b113ba463bfeb2b59d51d0bd
- pull request #1 head: 779fc8dafdf8d0e080bcbd889636539062bf0bb9
- old root commit: bd1641bdde8007221ebd477ac43b3bd49e969f1b
- commits that contained the data files: 7ad32209aeb4f311cc5df66621090c2f56347720, d145a0be1b1abc1c6bafe0ed2d6323ec27378e58, 779fc8dafdf8d0e080bcbd889636539062bf0bb9
- commits from an earlier version of the history that carried the AI co-author trailer and may have been pushed earlier: ac424a7987b043266ef92840c05b59142716e9f5 and 104e497057c7d83eb50f06af7b8ea68a9cf72ee1

Could you please:
1. refresh the contributors list and the contributors graph, which may still show the AI tool as a contributor;
2. remove `refs/pull/1/head` (or the pull request's cached commits) and any other unreachable commits and cached views that still hold the old history, and run garbage collection on the repository, so that the data files are no longer retrievable by their old commit hashes;
3. confirm when this is done.

Thank you.
Farid Negahbani
