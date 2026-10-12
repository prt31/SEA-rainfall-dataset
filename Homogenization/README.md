# Homogenization

Homogeneity assessment of the transcribed Johor rainfall series and adjustment
of detected inhomogeneities (station moves, gauge changes, exposure changes,
undocumented discontinuities).

This work builds on the validated dataset produced under `../Transcription/`
(`Transcription/data/johor_rainfall_1926-1958.csv`).

## Layout

```
detection/     breakpoint-detection scripts and per-station test output
adjustments/   adjustment factors and the homogenised series
results/        summary tables and the break catalogue
plots/          diagnostic and before/after adjustment plots
breakpoints.csv catalogue of detected / known breaks
```

## `breakpoints.csv`

The break catalogue. One row per detected or known break, with columns:

```
station_no, station_name, break_year, break_month, detection_method,
test_statistic, p_value, break_type, adjustment_applied, adjustment_factor, notes
```

## Intended methods (to populate)

- Absolute tests on single series: Pettitt, standard normal homogeneity test
  (SNHT), Buishand range test, von Neumann ratio.
- Relative tests against neighbour composites where station density allows.
- Metadata cross-check against known station moves / gauge changes.
- Adjustment of accepted breaks (e.g. monthly adjustment factors), retaining
  both the raw and the adjusted series.
- Diagnostic and before/after plots saved to `plots/`.

## Principle

As with transcription, nothing is silently altered: every adjustment is logged
in `breakpoints.csv` with its detection method, significance, and the applied
correction, so the raw and homogenised series remain fully traceable.

> **Status:** scaffold. `breakpoints.csv` holds the header/template and the
> working subfolders are in place; detection and adjustment outputs populate
> here as the homogenisation is run.
