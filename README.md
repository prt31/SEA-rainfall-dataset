# SEA-rainfall-dataset

Digitised and homogenised **historical rainfall records for Southeast
Asia** — the Malaysia, Singapore, Sumatra rainfall publication series and neighbours —
rescued from scanned register pages into a validated, openly documented dataset
for Scientific Data Nature Journal (SDATA) data papers.

The core principle throughout is **honesty over completeness**: no rainfall
value is ever invented or silently adjusted. Every transcribed row is either
verified against its printed annual total, corrected by a single unambiguous
fix, or kept exactly as read and flagged; every homogeneity adjustment is
logged with its method and magnitude so the raw and corrected series stay fully
traceable.

## Final consolidated dataset

**`data/MY_SG_SU_rainfall_pre1958.csv`** — the consolidated,
reconciled, homogenised and metadata-filled master table that the data paper
describes.

| | |
|---|---|
| **Stations** | 672 |
| **Rows (station-years)** | 14,549 |
| **Period** | 1875–1958 |
| **Coverage** | Malaysia (13,243 rows), Sumatra/Indonesia (1,185), Singapore (121) |
| **Regions** | Perak, Selangor, Johor, Pahang, Negri Sembilan, Kedah, Kelantan, Malacca, Terengganu, Penang, Perlis, Province Wellesley, Sabah, Sarawak, Sumatra, Singapore |
| **Homogenised rows** | 2,496 across 70 stations (break-adjusted) |

### Column reference

Each row is one station-year; the twelve monthly columns are rainfall in inches.

| Column | Meaning |
|--------|---------|
| `station_name` | Station name as printed in the register |
| `year` | Calendar year |
| `distance_to_coast_km`, `distance_source` | Distance to coast; `original` or derived (`coastline:ne_10m`) |
| `elevation_m`, `elevation_source` | Elevation; `original` or filled from a DEM (`DEM:open-meteo`) |
| `lat_decimal`, `lon_decimal` | Station coordinates (decimal degrees) |
| `administrative_unit`, `country_modern`, `region` | Modern location context |
| `Jan … Dec` | Monthly rainfall (inches) |
| `annual_printed` | Annual total as printed in the source |
| `annual_computed` | Sum of the twelve transcribed months |
| `reconcile_flag` | `OK`, blank, `(no printed total)`, or `CHECK` / `CHECK (partial)` where months and printed annual disagree |
| `row_note` | Free-text note on the row |
| `correction_factor` | Homogenisation adjustment applied (1.0 = unchanged; 1,308 rows adjusted) |
| `homogenized` | Whether a break adjustment was applied to this row |
| `n_breaks` | Number of detected breaks affecting this station-year |

"`dist_filled`" denotes that station metadata (distance-to-coast, elevation)
has been completed from reference sources where the register did not print it;
the rainfall values themselves are the transcribed/homogenised observations.

## Repository layout

```
data/             the final consolidated dataset (above)

Transcription/    Turning scanned register pages into validated per-territory CSVs
  code/             detect → read → stitch pipeline (Python)
  data/             a worked per-territory output (Johor, 1926–1958) + data dictionary
  docs/             methodology and supplementary methods

Homogenization/   Break detection and adjustment of the transcribed series
  detection/        breakpoint-detection scripts and per-station test output
  adjustments/      adjustment factors and the homogenised series
  results/          summary tables and the break catalogue
  plots/            diagnostic and before/after adjustment plots
  breakpoints.csv   catalogue of detected / known breaks

Figures/          Everything needed to reproduce the paper figures
  figures/          rendered figure PNGs
  code/             figure-supporting scripts
  data/             the data the figures draw on
```

Each folder has its own `README.md` with the detail. The consolidated file in
`data/` is the end product of the Transcription and Homogenization stages; the
`Transcription/data/johor_rainfall_1926-1958.csv` file is a per-territory
intermediate retained as a worked example.

## Licensing

- Code: see `LICENSE`.
- Data: see `LICENSE-DATA`.
- Please cite via `CITATION.cff`.
