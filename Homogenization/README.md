# Homogenization

Break detection, correction and infilling of the pre-1958 Malaya–Singapore–Sumatra
monthly rainfall archive. Artificial breaks (station moves, gauge/exposure changes,
undocumented discontinuities) are detected against a network of neighbouring stations
and removed by multiplicative adjustment, keeping the raw and homogenised series
fully traceable.

**Input:** the consolidated master (≤1958 window): 672 stations, 14,549 station-years,
monthly totals in inches, 1875–1958.

## Method (summary)

- **Detection — Climatol method.** Each station's annual total is ratio-normalized and
  compared to a distance-weighted neighbour reference (≤10 neighbours within 200 km,
  correlation ≥ 0.10). The **Standard Normal Homogeneity Test (SNHT)** is applied
  recursively to the candidate-minus-reference series at a 95% Monte-Carlo level.
- **Independent confirmation — RHtests style.** On the 164 stations with ≥30 years,
  the penalized maximal **F** test (PMF, no reference) and **t** test (PMT, against a
  neighbour reference) grade each break's confidence.
- **Correction.** Multiplicative segment adjustment, bringing each earlier segment onto
  the level of the most-recent (baseline) segment. An alternative first-segment baseline
  is also provided.
- **Infilling.** Missing months filled from a seasonal neighbour reference, within each
  station's observed span only.

**Result:** 78 breaks across 70 stations (16 high / 1 medium-high / 32 medium / 29 low
confidence); median adjustment 0.89 (~11%). The dominant artificial signal is a cluster
of post-war breaks (41% of all breaks fall in 1946–1953).

> **Note on tooling.** Results were produced by a faithful Python implementation of the
> published algorithms (validated against synthetic series with known injected breaks).
> Ready-to-run scripts for the genuine R packages are in `detection/R/`.

## Layout

```
detection/      SNHT + RHtests detection (Python), run_climatol.R / run_rhtests.R,
                per-method break lists (breaks_climatol.csv, breaks_rhtests.csv)
adjustments/    correction scripts, adjustment factors, homogenised + corrected series,
                corrections and QC logs
results/        break catalogue, station metadata, and the full methods report
                (HOMOGENIZATION_REPORT .md/.html/.docx)
plots/          all diagnostic and before/after figures (fig1–fig14) + plotting scripts
breakpoints.csv flat break catalogue (one row per detected break)
```

### `detection/`
- `homoglib.py` — core routines: haversine, neighbour weights, reference construction,
  SNHT (+ Monte-Carlo critical values), penalized maximal F.
- `prep.py` — reshape/QC the master to the monthly/annual/seasonal matrices.
- `climatol_run.py` — SNHT relative detection, correction, infilling.
- `rhtests_run.py` — PMF/PMT confirmation on long stations.
- `validate.py` — synthetic-break validation of the detection code.
- `breaks_climatol.csv`, `breaks_rhtests.csv` — per-method break lists.
- `R/run_climatol.R`, `R/run_rhtests.R` — reproduce with the genuine CRAN/ECCC packages.

### `adjustments/`
- `finalize.py` — reconcile breaks, grade confidence, write homogenised wide CSVs.
- `alt_correction.py` — first-segment-baseline variant.
- `build_corrected.py` — assemble the corrected master (QC + factors applied).
- `factors_climatol.csv` (last-seg baseline), `factors_firstseg.csv` (first-seg baseline).
- `malaysia_rainfall_homogenized_NApreserved.csv` — corrected, gaps preserved.
- `malaysia_rainfall_homogenized_infilled.csv` — corrected + gap-filled within span.
- `malaysia_rainfall_homogenized_firstseg_NApreserved.csv` — first-seg-baseline variant.
- `malaysia_national_rainfall_CORRECTED.csv` — full master with corrections + QC applied.
- `CORRECTIONS_LOG.csv`, `QC_MASKED_LOG.csv` — every change, logged.

### `breakpoints.csv`
Flat catalogue, one row per detected break:
`station_no, station_name, break_year, break_month, detection_method, test_statistic,
p_value, break_type, adjustment_applied, adjustment_factor, notes`.

## Principle

Nothing is silently altered: every adjustment is logged with its detecting method(s),
confidence and applied factor, and both the raw and homogenised series are retained.
