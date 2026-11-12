# Abstract {-}

Retailers need daily sales forecasts several weeks ahead to plan orders, staff and revenue. Hybrids of ARIMA and long short-term memory (LSTM) networks often report large gains but rarely test them formally. This project evaluated whether a hybrid ARIMA-LSTM improves 28-day store-level forecasts, and how the forecasts can support planning in Power BI.

Ten Walmart stores from the M5 dataset and 20 sampled Rossmann stores were forecast from rolling origins. Three hybrid variants, which differ in the residuals the network learns, were compared with seasonal naive, ARIMA, exponential smoothing, a feed-forward network and a standalone LSTM. Networks used five seeds. Differences were tested with Holm-corrected Diebold-Mariano tests, every model received split conformal 95% intervals, and runtime was recorded.

A hybrid was the most accurate model on both datasets, but not the same variant. On M5, the recursive hybrid reduced the mean absolute scaled error by 11.0% relative to ARIMA (0.746 against 0.838) and beat all seven alternatives significantly in every seed. On Rossmann, the multi-step hybrid reduced it by 10.8% (0.320 against 0.359), but the gain over ARIMA held in only three of five seeds, and the feed-forward network was nearly as accurate (0.328) at about a tenth of the cost. Conformal coverage ranged from 90.3% to 96.3% but varied by horizon. The results cover store-level series and one test period per dataset. The dashboard's data model and test plan are complete; the dashboard file and user study are not.

The hybrid's benefit is real but depends on the data and on the residual design, so it should be validated locally against simpler, cheaper models.
