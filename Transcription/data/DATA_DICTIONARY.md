# Data dictionary — johor_rainfall_1926-1958.csv

One row per station-year (DATA) or per station summary line (MEAN / MAX*).

| Column | Type | Description |
|---|---|---|
| station_no | int | Register-native station number (gaps are original to the source) |
| station_name | str | Station / estate name as printed |
| distance_to_coast_km | num | Approximate distance to coast (km) |
| elevation_m | num | Approximate elevation (m) |
| lat_decimal | num | Latitude (decimal degrees, approximate) |
| lon_decimal | num | Longitude (decimal degrees, approximate) |
| administrative_unit | str | District, state |
| country_modern | str | Modern country (Malaysia) |
| row_type | str | DATA \| MEAN \| MAX24HR \| MAX48HR \| MAX72HR |
| year | int | Calendar year (blank for summary rows) |
| Jan … Dec | num | Monthly rainfall total, inches (2 d.p.); blank = no data |
| annual | num | Printed annual total, inches |
| data_confidence | str | Validation tag (see below) |

## data_confidence tags

| Tag | Meaning |
|---|---|
| ok_reconciled | 12 months sum to the printed annual within 0.10 in |
| ok_rounding | Difference ≤ 0.50 in (two-decimal rounding) |
| ocr_corrected:FIELD_old→new | One value corrected by the unique-fix rule; change logged |
| partial_year:reason | One or more months missing (wartime gap, station opening, unreadable) |
| wartime_gap | Whole year absent (1941–1947) |
| annual_discrepancy:… | Months and printed annual disagree, no clean fix — kept as read |
| source_printed_mean | A MEAN row, verified against its printed annual |
| source_printed | A MAX row (no reconciliation expected) |

Geographic metadata carries a confidence level; estate gauges are approximate
to the estate locality, fixed institutional sites are more precise.
