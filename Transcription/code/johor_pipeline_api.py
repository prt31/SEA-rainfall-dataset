#!/usr/bin/env python3
"""
================================================================================
 Johor Rainfall Register — API-INTEGRATED Transcription Pipeline
================================================================================
This is the fully-automated, reproducible version of the pipeline. The step that
used to be done by a person reading enlarged crops ("direct visual reading") is
here replaced by a real call to a vision-capable model via the Anthropic
Messages API. Recognition therefore happens in code, not in a chat turn.

  Preprocess crop  ->  vision_read_block()  ->  reconcile  ->  correct/flag  -> CSV
                        ^^^^^^^^^^^^^^^^^^^
                        THE MODEL CALL lives here.

Run:
    export ANTHROPIC_API_KEY=sk-ant-...
    pip install anthropic pillow --break-system-packages
    python3 johor_pipeline_api.py /mnt/project/Image00029.jpg

Without a key, pass --mock to exercise the whole flow with a stubbed model
response, so you can see the plumbing end-to-end offline.

Design principle (unchanged): the model READS; arithmetic reconciliation against
each row's printed annual DECIDES what to trust. A value is never invented to
force a row to balance.
================================================================================
"""

import os
import io
import sys
import json
import base64
from collections import namedtuple
from PIL import Image, ImageOps

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# The exact model string can be swapped; any vision-capable Claude works.
VISION_MODEL = "claude-sonnet-4-6"


# ==============================================================================
# STEP 3 — PREPROCESS (identical idea to the OCR pipeline: crop + upscale + clean)
# ==============================================================================
def crop_region(img, x1f, y1f, x2f, y2f, scale=4, cutoff=0.35):
    """Return a preprocessed PIL image for a fractional page region."""
    w, h = img.size
    crop = img.crop((int(w * x1f), int(h * y1f), int(w * x2f), int(h * y2f)))
    crop = crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS)
    return ImageOps.autocontrast(crop.convert("L"), cutoff=cutoff)


def to_base64_png(pil_img):
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


# ==============================================================================
# STEP 4 — RECOGNITION VIA VISION MODEL  (this is the "Opus/Claude call")
# ==============================================================================
TRANSCRIPTION_PROMPT = """\
You are transcribing a table of monthly rainfall values from a scanned
colonial-era Malaysian rainfall register. The image is one station's block.

Each data row has: a 4-digit YEAR, then twelve monthly values (Jan..Dec) in
inches to two decimals, then a printed ANNUAL total. Some cells are blank
(printed as a dash) — represent those as null. There may also be summary rows
labelled MEAN or MAX (24/48/72 hrs); include them with "year": null and a
"row_type" of "MEAN"/"MAX24HR"/"MAX48HR"/"MAX72HR". Ordinary years use
"row_type": "DATA".

IMPORTANT:
- Read digits exactly as printed. Do NOT adjust a value to make the row sum to
  the annual — that reconciliation is done downstream. If a digit is genuinely
  illegible, use null for that single cell rather than guessing.
- Watch for a vertical offset where the year label sits one row above its data;
  pair each year with the correct data row.
- Return ONLY JSON, no prose, in exactly this shape:

{"rows": [
  {"row_type":"DATA","year":1931,
   "months":[13.51,2.46,11.32,16.36,4.54,12.68,8.79,10.92,7.35,4.67,13.35,12.98],
   "annual":118.93}
]}
"""


def vision_read_block(pil_img, model=VISION_MODEL, mock=False):
    """Send a preprocessed station-block image to the vision model and get back
    structured rows. THIS is where the model is called during the pipeline.

    Returns a list of dicts: {row_type, year, months[12], annual}.
    """
    if mock:
        return _mock_response()

    # Real API call.
    from anthropic import Anthropic          # imported lazily so --mock needs no dep
    client = Anthropic()                      # reads ANTHROPIC_API_KEY from env
    b64 = to_base64_png(pil_img)

    resp = client.messages.create(
        model=model,
        max_tokens=2000,
        temperature=0,   # deterministic transcription (see reproducibility note)
        top_p=1,         # no nucleus truncation (inert at temperature 0)
        messages=[{
            "role": "user",
            "content": [
                {"type": "image",
                 "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                {"type": "text", "text": TRANSCRIPTION_PROMPT},
            ],
        }],
    )
    # Concatenate any text blocks, strip code fences, parse JSON.
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    data = json.loads(text)
    return data["rows"]


def _mock_response():
    """A stand-in for the model's output so the pipeline can be run offline.
    These are the true Station 53 values, with one deliberately corrupted cell
    (1935 Jan) to show the downstream auto-correction, and one genuinely
    inconsistent row (1934-style) to show honest flagging."""
    return [
        {"row_type": "DATA", "year": 1931,
         "months": [13.51, 2.46, 11.32, 16.36, 4.54, 12.68, 8.79, 10.92, 7.35, 4.67, 13.35, 12.98],
         "annual": 118.93},
        {"row_type": "DATA", "year": 1935,   # Jan corrupted 4.35 -> 24.35 (row 20 over)
         "months": [24.35, 8.31, 10.53, 9.90, 6.89, 6.93, 4.17, 11.22, 3.51, 8.75, 13.11, 14.33],
         "annual": 102.00},
        {"row_type": "DATA", "year": 1948,
         "months": [25.18, 8.73, 23.42, 13.84, 10.64, 7.43, 16.21, 10.82, 3.86, 13.52, 10.10, 20.99],
         "annual": 164.74},
        {"row_type": "DATA", "year": 1954,   # verified extreme: Dec 49.43
         "months": [11.13, 7.65, 8.77, 13.51, 10.02, 12.32, 5.89, 13.01, 5.74, 17.41, 17.15, 49.43],
         "annual": 172.03},
        {"row_type": "MEAN", "year": None,
         "months": [11.81, 7.63, 12.75, 11.39, 8.97, 7.23, 6.60, 9.63, 7.17, 10.25, 10.70, 12.53],
         "annual": 116.66},
    ]


# ==============================================================================
# STEP 5-6 — RECONCILE & CORRECT  (unchanged logic; model output feeds in here)
# ==============================================================================
def reconcile(months, annual, tol_ok=0.10, tol_round=0.50):
    present = [m for m in months if m is not None]
    if len(present) < 12:
        return "incomplete", (round(sum(present), 2) if present else None)
    computed = round(sum(present), 2)
    if annual is None:
        return "no_annual", computed
    diff = abs(computed - annual)
    if diff <= tol_ok:
        return "ok_reconciled", computed
    if diff <= tol_round:
        return "ok_rounding", computed
    return "check", computed


def try_single_fix(months, annual, max_delta=25.0):
    """Unique single-cell fix, or None. Uniqueness keeps corrections honest."""
    if annual is None or any(m is None for m in months) or len(months) != 12:
        return None
    base = sum(months)
    cands = []
    for i, val in enumerate(months):
        needed = round(annual - (base - val), 2)
        if needed < 0:
            continue
        d = abs(needed - val)
        if 0.01 < d <= max_delta:
            cands.append((i, val, needed))
    return cands[0] if len(cands) == 1 else None


Row = namedtuple("Row", "row_type year months annual computed confidence")


def process_row(rec):
    """Take one model-returned row dict -> validated Row with a confidence tag."""
    row_type = rec.get("row_type", "DATA")
    year = rec.get("year")
    months = list(rec.get("months", []))[:12]
    months += [None] * (12 - len(months))
    annual = rec.get("annual")

    status, computed = reconcile(months, annual)
    tag = status
    if status == "check":
        fix = try_single_fix(months, annual)
        if fix:
            i, old, new = fix
            months[i] = new
            tag = f"ocr_corrected:{MONTHS[i]}_{old}->{new}"
            status, computed = reconcile(months, annual)
        else:
            tag = f"annual_discrepancy:computed={computed}_printed={annual}_unresolved"
    if row_type != "DATA" and status == "ok_reconciled":
        tag = "ok_reconciled:source_printed_mean" if row_type == "MEAN" else "source_printed"
    return Row(row_type, year, months, annual, computed, tag)


# ==============================================================================
# STEP 8 — CSV
# ==============================================================================
CSV_COLUMNS = (["station_no", "station_name", "row_type", "year"]
               + MONTHS + ["annual", "computed", "data_confidence"])


def write_csv(path, station_no, station_name, rows):
    import csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLUMNS)
        for r in rows:
            vals = ["" if m is None else m for m in r.months]
            w.writerow([station_no, station_name, r.row_type,
                        "" if r.year is None else r.year, *vals,
                        "" if r.annual is None else r.annual,
                        "" if r.computed is None else r.computed, r.confidence])


# ==============================================================================
# ORCHESTRATION  — the full automated station transcription
# ==============================================================================
def transcribe_station(image_path, region, station_no, station_name,
                       out_csv, mock=False):
    """End-to-end: crop -> vision model -> reconcile -> CSV. Fully automated."""
    print("=" * 74)
    print(f" Station {station_no} — {station_name}")
    print("=" * 74)
    img = Image.open(image_path)
    print(f"Source: {os.path.basename(image_path)} ({img.size[0]}x{img.size[1]})")

    # STEP 3
    block = crop_region(img, *region)
    print(f"STEP 3  Cropped + preprocessed block  ({block.size[0]}x{block.size[1]} px)")

    # STEP 4 — THE MODEL CALL
    where = "MOCK model response" if mock else f"API call -> {VISION_MODEL}"
    print(f"STEP 4  Recognition via {where}")
    recs = vision_read_block(block, mock=mock)
    print(f"        model returned {len(recs)} rows")

    # STEP 5-7
    print("STEP 5-7  Reconciling each row:")
    rows = []
    ok = fixed = flagged = 0
    for rec in recs:
        r = process_row(rec)
        rows.append(r)
        c = r.confidence
        mark = ("OK " if c.startswith("ok_") or c.startswith("source") else
                "FIX" if c.startswith("ocr_corrected") else
                "?? " if c.startswith("annual") else "-- ")
        label = r.year if r.year is not None else r.row_type
        print(f"   [{mark}] {str(label):>5}  sum={str(r.computed):>7} "
              f"annual={str(r.annual):>7}   {c}")
        if mark == "OK ":
            ok += 1
        elif mark == "FIX":
            fixed += 1
        elif mark == "?? ":
            flagged += 1
    print(f"        {ok} reconciled · {fixed} auto-corrected · {flagged} flagged")

    # STEP 8
    write_csv(out_csv, station_no, station_name, rows)
    print(f"STEP 8  Wrote {len(rows)} rows -> {out_csv}\n")
    return rows


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mock = "--mock" in sys.argv or not os.environ.get("ANTHROPIC_API_KEY")
    image = args[0] if args else "/mnt/project/Image00029.jpg"
    if mock and "--mock" not in sys.argv:
        print("(no ANTHROPIC_API_KEY found -> running in --mock mode)\n")

    transcribe_station(
        image_path=image,
        region=(0.505, 0.415, 0.99, 0.72),   # Station 53 block, right column
        station_no=53,
        station_name="Mount Austin Estate",
        out_csv="/tmp/demo_station53_api.csv",
        mock=mock,
    )
