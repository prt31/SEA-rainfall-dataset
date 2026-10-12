# MY-SG-SU-rainfall-dataset

Digitised colonial-era **Johor rainfall records** (Federated Malay States
rainfall publication series, **1926–1958**), transcribed from scanned register
pages into a validated, openly documented dataset for a Geoscience Data Journal
(GDJ) data paper.

The core principle throughout is **honesty over completeness**: no rainfall
value is ever invented or silently adjusted. Every transcribed row is either
verified against its printed annual total, corrected by a single unambiguous
fix, or kept exactly as read and explicitly flagged; every homogeneity
adjustment is logged with its method and magnitude so the raw and corrected
series stay fully traceable.

## Repository layout

```
Transcription/    Turning scanned register pages into the validated CSV
  code/             detect → read → stitch pipeline (Python)
  data/             the delivered dataset + data dictionary
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

Each folder has its own `README.md` with the detail.

## Dataset at a glance

- **Stations:** 40 | **Rows:** 917 | **Period:** 1926–1958
- **Delivered file:** `Transcription/data/johor_rainfall_1926-1958.csv`
- **Intrinsic accuracy:** 96.4% of full-year rows reconcile to their printed
  annual total within tolerance; the remainder are explicitly flagged.

## Licensing

- Code: see `LICENSE`.
- Data: see `LICENSE-DATA`.
- Please cite via `CITATION.cff`.
