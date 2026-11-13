# Measure checklist

Observed values were read from the exported pages (`Dashboard_screenshots.pdf`, M5, all stores, all origins). They are **not** DAX query results: no live connection to the open report was available when this was filled in. Acceptance values are in `data/acceptance_values.json` (M5, store average over seeds).

| Measure | Model | Acceptance value | Observed (screenshot) | Result |
|---|---|---|---|---|
| MASE (store average) | Hybrid-Z (hyb_z) | 0.7458 | 0.746 | match |
| MASE (store average) | Hybrid-D (hyb_d) | 0.7979 | 0.798 | match |
| MASE (store average) | ARIMA | 0.8379 | 0.838 | match |
| MASE (store average) | Hybrid-MS (hyb_ms) | 0.8472 | 0.847 | match |
| MASE (store average) | FFNN | 0.8637 | 0.864 | match |
| MASE (store average) | ETS | 1.0368 | 1.037 | match |
| MASE (store average) | Seasonal naive | 1.1960 | 1.196 (benchmark on the forecast page) | match |
| MASE (store average) | LSTM | 1.0814 | not visible | passed (confirmed by the author) |
| Interval coverage | Seasonal naive | 0.9399 | 94.0% | match |
| Interval coverage | ETS | 0.9261 | 92.6% | match |
| Interval coverage | ARIMA | 0.9358 | 93.6% | match |
| Interval coverage | FFNN | 0.9285 | 92.8% | match |
| Interval coverage | LSTM | 0.9030 | 90.3% | match |
| Interval coverage | Hybrid-D | 0.9358 | 93.6% | match |
| Interval coverage | Hybrid-MS, Hybrid-Z | 0.9288, 0.9426 | not visible | passed (confirmed by the author) |
| Best Model (MASE) | all models | hyb_z | Hybrid-Z, MASE 0.746 | match |
| Forecast sales, stock-out and overstock risk days, safety stock proxy | all models | sum over models 121,705,958; 1,641.6; 546.0 (mean 15,213,245; 205.2; 68.25) | 70,733,426; 1,044.7; 261.7 | not reconciled with all models selected; re-run with one model: passed (confirmed by the author) |
| Mean absolute error, actual sales, forecast sales | one model | per model | not checked | passed (confirmed by the author) |

Interactive tests (slicers, relationships, sort orders, drill-down) and the colour-vision and greyscale checks A2 and A3: passed (confirmed by the author). Keyboard use (A5, A6) and the high-contrast check (A8) have no recorded result. Results for the static checks (A1, A4, A5, A7) are in Appendix F of the report.
