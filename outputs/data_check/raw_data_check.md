# Raw data check

Checked at (UTC): 2026-11-08T23:50:37+00:00

| File | Size (MB) | Rows | Columns | Null cells | Status | SHA-256 (first 16) |
|---|---|---|---|---|---|---|
| Dataset\m5-forecasting-accuracy\calendar.csv | 0.1 | 1969 | 14 | 7542 | OK | d12b5914ef03e666 |
| Dataset\m5-forecasting-accuracy\sales_train_validation.csv | 120.01 | 30490 | 1919 | 0 | OK | f368e66ed1dbecb4 |
| Dataset\m5-forecasting-accuracy\sales_train_evaluation.csv | 121.74 | 30490 | 1947 | 0 | OK | 4b4a47c44c38380d |
| Dataset\m5-forecasting-accuracy\sell_prices.csv | 203.4 | 6841121 | 4 | 0 | OK | 9da3ad1f8b8ccacd |
| Dataset\m5-forecasting-accuracy\sample_submission.csv | 5.23 | 60980 | 29 | 0 | OK | eb7597afbec36747 |
| Dataset\rossmann-store-sales\train.csv | 38.06 | 1017209 | 9 | 0 | OK | f6e4597c142d7d90 |
| Dataset\rossmann-store-sales\test.csv | 1.43 | 41088 | 8 | 11 | OK | e75f79972de046d8 |
| Dataset\rossmann-store-sales\store.csv | 0.05 | 1115 | 10 | 2343 | OK | f56bd124a2849489 |
| Dataset\rossmann-store-sales\sample_submission.csv | 0.32 | 41088 | 2 | 0 | OK | 592d892eb07072dd |

## Column names
- **Dataset\m5-forecasting-accuracy\calendar.csv**: date, wm_yr_wk, weekday, wday, month, year, d, event_name_1, event_type_1, event_name_2, event_type_2, snap_CA, snap_TX, snap_WI
- **Dataset\m5-forecasting-accuracy\sales_train_validation.csv**: id, item_id, dept_id, cat_id, store_id, state_id, d_1 ... d_1913 (1913 day columns)
- **Dataset\m5-forecasting-accuracy\sales_train_evaluation.csv**: id, item_id, dept_id, cat_id, store_id, state_id, d_1 ... d_1941 (1941 day columns)
- **Dataset\m5-forecasting-accuracy\sell_prices.csv**: store_id, item_id, wm_yr_wk, sell_price
- **Dataset\m5-forecasting-accuracy\sample_submission.csv**: id, F1, F2, F3, F4, F5, F6, F7, F8, F9, F10, F11, F12, F13, F14, F15, F16, F17, F18, F19, F20, F21, F22, F23, F24, F25, F26, F27, F28
- **Dataset\rossmann-store-sales\train.csv**: Store, DayOfWeek, Date, Sales, Customers, Open, Promo, StateHoliday, SchoolHoliday
- **Dataset\rossmann-store-sales\test.csv**: Id, Store, DayOfWeek, Date, Open, Promo, StateHoliday, SchoolHoliday
- **Dataset\rossmann-store-sales\store.csv**: Store, StoreType, Assortment, CompetitionDistance, CompetitionOpenSinceMonth, CompetitionOpenSinceYear, Promo2, Promo2SinceWeek, Promo2SinceYear, PromoInterval
- **Dataset\rossmann-store-sales\sample_submission.csv**: Id, Sales
