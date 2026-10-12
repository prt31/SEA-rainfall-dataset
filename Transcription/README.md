# Transcription

Turning scanned colonial-era Johor rainfall register pages into a clean,
validated CSV. The pipeline reads the numbers as printed and lets arithmetic
decide what to trust — it never invents or adjusts a value to make a row add up.

## Layout

```
code/   the transcription pipeline
data/   the delivered dataset and its data dictionary
docs/   methodology write-up and supplementary methods
```

## The pipeline (`code/`)

A three-stage pipeline — **DETECT → READ → STITCH** — in which a
vision-language model and Tesseract OCR play complementary roles and the
printed annual total is the final arbiter.

| Stage | What happens |
|-------|--------------|
| **Detect** | The vision model proposes station-block boundaries; Tesseract validates each block structurally (≈14 columns, regular row pitch, monotonic year column, header present, MEAN/MAX sentinel). Detection trusts Tesseract's token *geometry*, not its character values. |
| **Read** | Each row is read cheaply by Tesseract first; the twelve months are summed and compared with the printed annual. Rows that reconcile are accepted; rows that fail are escalated to the vision model (temperature 0); rows that still fail are kept as-read and flagged — never fabricated. |
| **Stitch** | Stations whose rows span a column or page break are rejoined in year order from their already-reconciled rows. |

The main combined pipeline is `code/johor_detect_and_read.py`. Earlier staged
variants (`johor_pipeline*.py`) are retained for provenance. See
`code/README.md` for the per-file guide.

## The data (`data/`)

- `johor_rainfall_1926-1958.csv` — the delivered dataset (40 stations, 917
  rows). Its CSV header records the exact model and OCR settings used for the
  run (`run_metadata()` provenance line).
- `DATA_DICTIONARY.md` — column definitions and the `data_confidence` flag
  vocabulary.

## The docs (`docs/`)

- `methodology.md` — the methodology write-up.
- `supplementary_transcription_methods.docx` — supplementary methods: workflow
  detail, model and OCR settings, the verbatim prompts, table-structure
  figures, and a cell-level comparison of Tesseract vs vision-model readings.
- `transcription_process_illustrated.docx` — an illustrated walkthrough of the
  process.

## Reconciliation flags (`data_confidence`)

| Flag | Meaning |
|------|---------|
| `ok_reconciled` | months sum to the printed annual within 0.10 |
| `ok_rounding` | difference ≤ 0.50 (rounding artifact; computed sum noted) |
| `ocr_corrected:F_old->new` | one cell fixed by the unique-fix rule |
| `partial_year:reason` | one or more months missing |
| `wartime_gap` | whole year absent (1941–1947) |
| `annual_discrepancy:…` | months and annual disagree, no clean fix — kept as-read |
| `source_printed_mean` / `source_printed` | MEAN / MAX summary rows |
