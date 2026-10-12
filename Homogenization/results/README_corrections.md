# Corrected rainfall dataset — documentation

**Folder contents**

| File | What it is |
|---|---|
| `malaysia_national_rainfall_ORIGINAL.csv` | Verbatim copy of the current master dataset (uncorrected), for reference |
| `malaysia_national_rainfall_CORRECTED.csv` | The corrected dataset (same schema + 3 added columns) |
| `CORRECTIONS_LOG.csv` | Every homogenization correction applied (one row per corrected segment) |
| `QC_MASKED_LOG.csv` | Impossible values masked during QC |
| `README_corrections.md` | This document |

Generated 2026-09-07 from `malaysia_national_rainfall_with_singapore_final.csv` (17,567 rows, 709 stations, monthly totals in inches).

---

## What was changed, and what was not

The corrected dataset keeps **every row and every original column** of the master. Two kinds of change were applied, both documented in the logs:

**1. Quality-control masking.** Physically-impossible monthly values (negative, or greater than 150 in/month) were set to missing. Only **2 values** qualified — both spurious −13.11 entries at Kota Kinabalu (Aerodrome), 1983 and 1998 — listed in `QC_MASKED_LOG.csv`. No real extremes were affected (the largest genuine monthly total in the archive is ~109 in).

**2. Homogenization corrections.** Artificial breaks (inhomogeneities) detected by the Climatol-method relative homogenization were removed by **multiplicative segment adjustment**. This affected **70 stations / 78 breaks**, all within the pre-1958 peninsular network; every affected station-year is flagged. Post-1958 records and stations without a detected break are unchanged (verified bit-identical to the original for all non-adjusted stations).

Nothing else was altered: `annual_printed` is preserved exactly as in the source (provenance), and all metadata columns (coordinates, region, distance-to-coast, elevation, notes) are untouched.

## How the corrections were computed

Breaks were detected with the **Standard Normal Homogeneity Test (SNHT)** applied to each station's annual total *minus* a distance-weighted neighbour reference (≤10 neighbours within 200 km, correlation ≥ 0.10), recursively for multiple breaks, at a 95% Monte-Carlo significance level. Detected breaks split each station's record into segments. Each earlier segment was scaled onto the level of the **most-recent (baseline) segment** by a multiplicative factor

> `factor = k_last / k_seg`, where `k = mean(station / reference)` over the segment.

The factor was applied to all 12 monthly values of every year in that segment; `annual_computed` was then recomputed from the corrected months. The most-recent segment of each station is unchanged (factor = 1.00).

**Independent confirmation.** On the 164 stations with ≥30 years, RHtests-style penalized maximal *F*/*t* tests were run; each break carries a `confidence` grade in `CORRECTIONS_LOG.csv` (high / medium-high / medium / low) reflecting cross-method agreement. Corrections were applied for **all** detected breaks; to use a conservative subset, filter `CORRECTIONS_LOG.csv` to `confidence ∈ {high, medium-high}` and re-apply only those.

## Columns added to the corrected dataset

| Column | Meaning |
|---|---|
| `correction_factor` | Multiplicative factor applied to that row's monthly values (1.00 = unchanged) |
| `homogenized` | TRUE if the station had ≥1 detected break (i.e. was adjusted) |
| `n_breaks` | Number of breaks detected at that station |

## CORRECTIONS_LOG.csv columns

`station, seg_start, seg_end, break_year, correction_factor, confidence, n_years_in_segment`
— one row per corrected segment (78 rows). `break_year` is the break at the end of the segment; `correction_factor` is the multiplier applied to that segment's monthly values.

## Caveats

Detection is more reliable than correction for this archive (low inter-station rainfall correlation; short, staggered records; no station-move metadata, so all breaks are undocumented). `low`-confidence corrections rest on few neighbours and should be treated as tentative. The dominant artificial signal is a cluster of post-war breaks (1946–1953). Full method, figures and references are in `../homogenization/HOMOGENIZATION_REPORT.docx`.
