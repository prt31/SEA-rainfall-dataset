# Figures

Rendered figures for the data paper, plus the data and supporting code they
draw on.

## Layout

```
figures/   rendered figure PNGs
code/       figure-supporting scripts
data/       the data the figures draw on
```

## Figures (`figures/`)

| File | What it shows |
|------|---------------|
| `fig01_full_source_page.png` | A full two-column register page (raw scan). |
| `fig02_station_block.png` | One isolated station block. |
| `fig03_column_isolation.png` | Cropping a page down to a single station column. |
| `fig04_preprocessing_composite.png` | Pre-processing stages composited. |
| `fig04a_raw_row.png` / `fig04b_upscaled_row.png` / `fig04c_processed_row.png` | One data row: raw → ×3 upscaled → autocontrast-stretched. |
| `fig05_flagged_row.png` | A row that failed reconciliation and was flagged. |
| `fig06_year_offset.png` | The year-label vertical-offset source defect. |
| `fig07_column_cascade.png` | The diagonal column-cascade source defect. |
| `fig08_extreme_value.png` | An extreme/outlier value kept as-read. |
| `fig09_two_stage_crop.png` | The two-stage crop (header-find then block-read). |
| `fig10_cross_page_stitching.png` | Rejoining a station across a page break. |
| `fig_combined_workflow_schematic.png` | The full detect→read→stitch workflow schematic. |
| `fig_detected_data_overlay.png` | Detected 14-column grid overlaid on a block. |
| `figP_a_column_isolation.png` | Table structure, panel a: column isolation. |
| `figP_b_overlay_preprocessed.png` | Table structure, panel b: grid on the pre-processed block. |
| `figP_c_single_row.png` | Table structure, panel c: one isolated data row. |
| `fig_page_and_block_composite.png`, `fig_page_block_preprocessing_composite*.png`, `fig_preprocessed_detection_panels.png` | Composite/alternate layouts of the above. |

## Data the figures draw on (`data/`)

- `johor_rainfall_1926-1958.csv` — the delivered dataset (a copy of
  `../Transcription/data/johor_rainfall_1926-1958.csv`), used by the
  value-level figures and the Tesseract-vs-vision-model comparison.
- **Raw register JPEGs** — the source-page figures (`fig01`, `fig02`, `fig03`,
  `fig06`–`fig10`, `figP_*`) are rendered from the scanned register images
  (e.g. `Image00029.jpg`, Station 53). Those scans are the project's raw input
  and are **not** duplicated here; point the scripts at your local copy of the
  image set.

## Code (`code/`)

- `tesseract_vs_vm_compare.py` — runs Tesseract on the Station 53 block under
  the documented settings and prints its readings beside the delivered
  vision-model values (the basis for the comparison in the supplementary
  methods). Expects the raw `Image00029.jpg` path to be set at the top.
- `build_supplementary_docx.py` — assembles the supplementary methods document,
  embedding the `figP_*` table-structure figures and the comparison table.

> **Note on reproducibility.** The register figures were produced
> interactively (crop → upscale → autocontrast → overlay), so a single
> standalone script per figure is not committed here; the two scripts above are
> the figure-related code that exists as reusable files. If you want a clean,
> parameterised `make_figures.py` that regenerates every panel from the raw
> scans and the CSV, that can be reconstructed on request.
