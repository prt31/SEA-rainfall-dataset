# Transcription pipeline

Progressive implementations of the detect–read–stitch workflow:

| File | What it is |
|---|---|
| `johor_pipeline.py` | OCR-only baseline (Tesseract) with reconciliation demo |
| `johor_pipeline_api.py` | Single-call vision-model recognition via the Anthropic API |
| `johor_pipeline_2stage.py` | Two-stage: model finds headers, then crops + reads |
| `johor_pipeline_stitched.py` | Adds cross-page stitching of split stations |
| `johor_detect_and_read.py` | Combined detect → read → stitch (the full workflow) |

Each script has a `--mock` mode that runs fully offline. Live runs need an
`ANTHROPIC_API_KEY` and `pip install anthropic pillow pytesseract` (plus the
system `tesseract-ocr` binary). Recognition sampling is pinned to
temperature = 0 for reproducibility; correctness is guaranteed by
reconciliation against printed annual totals, not by model determinism.
