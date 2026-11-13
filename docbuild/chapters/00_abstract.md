# Abstract {-}

Retailers need daily sales forecasts several weeks ahead. Hybrids of ARIMA and long short-term memory (LSTM) networks often report large gains but rarely test them formally. This project tested whether a hybrid improves 28-day store-level forecasts, and how forecasts can support planning in Power BI.

Ten Walmart stores (M5) and 20 Rossmann stores were forecast from rolling origins. Three hybrid variants were compared with seasonal naive, ARIMA, exponential smoothing, a feed-forward network (FFNN) and an LSTM, using five seeds, Holm-corrected Diebold-Mariano tests of the primary hybrid against the seven other models, and split conformal 95% intervals.

On M5, the recursive hybrid (hyb_z) was the most accurate model. Its mean absolute scaled error (MASE) was 11.0% below ARIMA (0.746 against 0.838), and significantly better than all seven alternatives in every seed. The multi-step hybrid (hyb_ms) was 1.1% worse than ARIMA. M5 has only ten series. On Rossmann, hyb_ms had the lowest MASE (0.320 against 0.359 for ARIMA), but its gain over ARIMA was significant in only three of five seeds, and no hybrid was significantly better than the FFNN (0.328), the LSTM or hyb_z. Interval coverage ranged from 90.3% to 96.3%: below 95% for all eight models on M5 and five of eight on Rossmann. Results cover one test period per dataset. The dashboard was built; its interactive tests and the user study are not complete.

A hybrid's benefit depends on the data and the residual design, so it should be validated locally against simpler, cheaper models.
