# Review queue (first-pass mode)

Decisions taken without asking. Each row: ID, file/section, decision taken, alternative, why. Edit or reverse any row.

| ID | File / section | Decision taken | Alternative | Why |
|---|---|---|---|---|
| B1-1 | `docbuild/chapters/*.md`, `dashboard/*.md` | "mean scaled absolute error" replaced by "mean absolute scaled error (MASE)" in captions, alt text, Chapter 3 definition, Appendix E/F rows and dashboard documents; full name added at first use in each dashboard document and in the DAX comments. "Scaled absolute errors" of the conformal method (Chapter 3, Chapter 4 limitations) left unchanged: it names the quantity calibrated, not the metric. | Replace those too | They are not the MASE metric |
| B1-2 | `scripts/run_evaluation.py:243` | Y-axis label changed to "Mean absolute scaled error (MASE)". The PNG files in `outputs/figures/res_*_by_horizon.png` still carry the old label until `run_evaluation.py` is re-run (pipeline stage, not run in chat). | Leave the script alone | The figure text, not only the caption, should use the full name; **action for you: re-run lane E / the evaluation step** |
