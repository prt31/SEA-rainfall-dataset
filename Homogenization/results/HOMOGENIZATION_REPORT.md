# Homogenization of the Malaysia–Singapore historical rainfall archive (≤ 1958)

**Method:** Climatol-style relative homogenization (SNHT on a distance-weighted
neighbour reference) for detection, correction and infilling, with RHtestsV4-style
penalized maximal *F*/*t* tests as an independent confirmation on the long stations.
**Input:** `malaysia_national_rainfall_to1958.csv` — 672 stations, monthly totals in
inches, 1875–1958. **Run date:** 2026-08-27.

> **Important note on tooling.** The genuine `climatol` and `RHtestsV4` R packages
> could not be installed in the execution sandbox (CRAN, conda and r-universe are
> firewalled there). The results below were produced by a faithful **Python
> implementation of the published algorithms**, validated against synthetic series
> with known injected breaks (7/8 relative breaks recovered within ±3 yr; base-series
> step located exactly; SNHT critical values reproduce the standard tables — n=20→7.0,
> n=40→7.9, n=60→9.1). Ready-to-run R scripts for the **actual packages**
> (`R/run_climatol.R`, `R/run_rhtests.R`) are included so the analysis can be
> reproduced on a machine with CRAN access; small numerical differences from the
> packaged tools are expected but the break structure should be stable.

---

## 1. Data preparation and quality control

Records were restricted to `year ≤ 1958` (14,549 station-years, 672 stations) and
reshaped onto a common 1875–1958 monthly frame (1,008 months × 672 stations with
usable coordinates). Annual totals were formed only for station-years with all 12
months present; seasonal totals (DJF/MAM/JJA/SON, Dec carried to the following DJF)
were also derived. Detection is performed on **annual totals** — more Gaussian and
higher signal-to-noise for tropical rainfall — while corrections are applied at the
**monthly** level.

Quality control followed the agreed rules: physically-impossible values (negative, or
> 150 in/month) were masked to missing — **none occurred** (observed monthly maximum
is 109 in), so all real extremes were retained; reconcile-flagged rows were **kept**.
Stations with **≥ 10 data-years** were treated as homogenization-eligible
(**529 stations**); shorter stations are carried through for infilling but not adjusted.

## 2. Neighbour network

Because equatorial convective rainfall de-correlates quickly in space, the reference
for each station is a distance-weighted mean of its normalized neighbours, capped at
the 10 nearest within 200 km, Gaussian weighting with a 60 km scale, and requiring a
minimum annual-anomaly correlation of 0.10. **525** eligible stations obtained at least
one usable neighbour; the very thin regions (Singapore = 2, Perlis = 5, Province
Wellesley = 1, Sabah = 4, Sarawak = 3 eligible stations) are effectively
absolute-only and their few adjustments should be treated with caution.

## 3. Detection, correction, infilling (Climatol method)

Series were ratio-normalized (each divided by its mean — the precipitation-appropriate
`std=2` analogue). A neighbour reference was built in ratio space, and the
candidate-minus-reference anomaly series was tested with the **Standard Normal
Homogeneity Test** applied recursively for multiple breakpoints (minimum segment
5 years; 95% Monte-Carlo critical values). References were then rebuilt from the
provisionally-adjusted series and detection was repeated (two outer passes).
Corrections are **multiplicative**, bringing each earlier segment onto the level of the
most-recent (reference) segment. Gaps were filled from a seasonal (monthly-climatology)
neighbour reference, **only within each station's observed span** (no extrapolation
beyond a station's life).

**Result:** **78 breaks across 70 stations**; the median multiplicative adjustment was
**0.89** (≈ 11% typical correction). **19,813** interior monthly gaps were filled.

## 4. Independent confirmation (RHtests style)

On the **164 stations with ≥ 30 data-years** two penalized maximal tests were run:
**PMF** (penalized maximal *F*, two-phase regression with a common trend, **no
reference**) directly on the annual totals, and **PMT** (penalized maximal *t*, on the
candidate-minus-reference series). Of the 49 Climatol breaks on long stations,
**17 (35%) were confirmed** by RHtests within ±2 years (16 by PMT, 6 by PMF).

The modest confirmation rate is expected and not a red flag: PMF is an *absolute* test
with low power for artificial breaks in noisy tropical series, and PMT's trend-aware
penalty is deliberately stricter than SNHT — so RHtests endorses the larger, clearer
breaks and leaves marginal ones as Climatol-only. This is why the deliverable **classes
every break by confidence** rather than treating detection as binary.

Break confidence (Climatol breaks): **16 high**, 1 medium-high, **32 medium**,
**29 low**; plus **55 RHtests-only** breaks recorded for information (not corrected).

## 5. The two structural discontinuities

**WWII / post-war.** Breaks cluster strongly right after the war: **41% of all
detected breaks fall in 1946–1953**, peaking in 1948–1950 (see `fig1`). This is the
dominant artificial signal in the archive — network disruption, station relocations and
re-establishment after the occupation — and any trend analysis spanning the war must
account for it.

**mm → inches merge boundary.** The Sumatra/Borneo records were transcribed in mm and
converted to inches on ingestion, making their provenance a candidate offset. Pre-1958,
only a handful of island stations are long and well-connected enough to test, and just
**3 island-sourced breaks** were found — too few to assess the conversion boundary
robustly. The conversion should be spot-checked manually rather than relied on
statistically here.

## 6. Deliverables

| File | What it is |
|---|---|
| `malaysia_rainfall_homogenized_NApreserved.csv` | Homogenized monthly series, original gaps kept as NA (14,200 station-years) |
| `malaysia_rainfall_homogenized_infilled.csv` | Homogenized **and** gap-filled within span (15,684 station-years; +1,484 recovered) |
| `break_inventory.csv` | Every break: station, year, method(s), confidence, applied factor, coords |
| `breaks_climatol.csv`, `breaks_rhtests.csv`, `factors_climatol.csv` | Raw per-method outputs |
| `stations.csv` | Station metadata + eligibility |
| `fig1…fig4 .png` | Breaks-by-year, raw-vs-homogenized examples, station map, network timeline + confidence |
| `R/run_climatol.R`, `R/run_rhtests.R` | Reproduce with the genuine packages |
| `*.py` | The full Python pipeline (prep → homoglib → climatol_run → rhtests_run → finalize → plots) |

Both homogenized CSVs keep the original wide schema (station, metadata, 12 months,
recomputed `annual_computed`) plus `adjusted` and `n_breaks` flags.

## 7. Caveats

Detection is more reliable than correction for this archive: rainfall correlations are
low, many series are short and staggered, and there is no station-move metadata, so all
breaks are *undocumented*. Corrections were applied for every Climatol break (the
primary method); users wanting a conservative product can restrict adjustments to
`confidence ∈ {high, medium-high}` using the inventory. Thin-region and short-station
breaks (`confidence = low`) rest on few neighbours and should be treated as tentative.
The infilled product is spatial interpolation within a station's active period, not
observed data — use the NA-preserving copy for anything sensitive to that distinction.

## References

Alexandersson (1986) *J. Climatol.* 6:661; Alexandersson & Moberg (1997) *Int. J.
Climatol.* 17:25; Guijarro (2018) *Homogenization of climatic series with Climatol*;
Wang, Wen & Wu (2007) *J. Appl. Meteorol. Climatol.* 46:916; Wang (2008) *J. Atmos.
Ocean. Technol.* 25:368; Venema et al. (2012) *Clim. Past* 8:89; Wijngaard, Klein Tank
& Können (2003) *Int. J. Climatol.* 23:679.
