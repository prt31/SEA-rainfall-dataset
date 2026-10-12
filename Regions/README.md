# Regions

Per-territory rainfall tables (pre-1958), split out from the consolidated
master in `../data/MY_SG_SU_rainfall_pre1958_dist_filled.csv`. Each of the 16
territories has two files:

- **`<Region>_raw_pre1958.csv`** — transcribed and reconciled observations
  *before* homogenisation (25 columns).
- **`<Region>_corrected_pre1958.csv`** — the same rows *after* break detection
  and adjustment, adding `correction_factor`, `homogenized`, and `n_breaks`
  (28 columns). Row counts match the raw file one-to-one.

The difference between the two files for a territory is exactly the
homogenisation step: comparing them shows which station-years were adjusted and
by how much.

## Territories

Johor, Kedah, Kelantan, Malacca, Negri Sembilan, Pahang, Penang, Perak, Perlis,
Province Wellesley, Sabah, Sarawak, Selangor, Singapore, Sumatra, Terengganu.

## Columns

The raw files carry the transcription/reconciliation columns
(`station_name`, `year`, station metadata, `Jan … Dec`, `annual_printed`,
`annual_computed`, `reconcile_flag`, `row_note`); the corrected files add:

| Column | Meaning |
|--------|---------|
| `correction_factor` | Homogenisation adjustment applied (1.0 = unchanged) |
| `homogenized` | Whether a break adjustment was applied to this row |
| `n_breaks` | Number of detected breaks affecting this station-year |

See the top-level `README.md` for the full column reference. The concatenation
of all `*_corrected_pre1958.csv` files, with station metadata completed, is the
consolidated master in `../data/`.
