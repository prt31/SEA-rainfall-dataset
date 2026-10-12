#!/usr/bin/env python3
"""
================================================================================
 Johor Rainfall Register — TWO-STAGE Pipeline  (find headers -> crop -> read)
================================================================================
This removes the hand-tuned crop coordinates. Instead of a human deciding where
each station sits, STAGE 1 asks the vision model to scan the whole page and
report every station header with its vertical span. STAGE 2 then makes a tight,
high-resolution crop from those returned fractions and transcribes each block.

    full page --> [STAGE 1: find_stations] --> list of {name, column, y_start, y_end}
                        |
                        v  (for each station)
    tight crop --> [STAGE 2: transcribe_block] --> rows --> reconcile --> CSV

Stage 1 is the piece that used to be me eyeballing the page. Stage 2 is the
recognition we already had. Reconciliation (unchanged) still decides what to
trust — no value is invented to force a row to balance.

Run:
    export ANTHROPIC_API_KEY=sk-ant-...
    pip install anthropic pillow --break-system-packages
    python3 johor_pipeline_2stage.py /mnt/project/Image00029.jpg
Offline demo (no key, stubbed model):
    python3 johor_pipeline_2stage.py --mock /mnt/project/Image00029.jpg
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
VISION_MODEL = "claude-sonnet-4-6"

# Fixed horizontal bounds of the two columns, as fractions of page width.
# (Small pads absorb the gutter shadow / page curvature.)
COLUMN_X = {"left": (0.07, 0.53), "right": (0.50, 0.995)}


# ==============================================================================
# Shared: base64 encode a PIL image for the API
# ==============================================================================
def to_b64_png(pil_img):
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


def _call_vision(pil_img, prompt, model, max_tokens=2000):
    """One image+text call to the Anthropic Messages API; returns parsed JSON."""
    from anthropic import Anthropic
    client = Anthropic()
    resp = client.messages.create(
        model=model, max_tokens=max_tokens,
        temperature=0,   # deterministic transcription (see reproducibility note)
        top_p=1,         # no nucleus truncation (inert at temperature 0)
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64",
             "media_type": "image/png", "data": to_b64_png(pil_img)}},
            {"type": "text", "text": prompt},
        ]}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


# ==============================================================================
# STAGE 1 — FIND STATION HEADERS AND THEIR SPANS
# ==============================================================================
FIND_PROMPT = """\
You are looking at ONE full page (a two-column spread) of a colonial-era
Malaysian rainfall register. Each column contains one or more STATION tables.
A station begins with a header like "Station No. 53—Mount Austin Estate", then
has yearly data rows, and usually MEAN / MAX summary rows.

List EVERY station header visible on this page. For each, report:
  - "station_no": integer after "Station No."
  - "station_name": text after the dash
  - "column": "left" or "right"
  - "y_start": fraction 0..1 of page HEIGHT where the header line sits
  - "y_end": fraction 0..1 where this station's block ends (i.e. where the next
     header begins, or where its MEAN/MAX rows end, or the bottom of the column)
  - "continues_from_prev": true if the yearly rows appear to start mid-sequence
     (data continued from the previous page)
  - "continues_next_page": true if the block runs to the very bottom of the
     column with no MEAN/summary rows (likely continues on the next page)

Estimate the fractions from where things actually sit on the page. Return ONLY
JSON in this shape, no prose:
{"stations":[
  {"station_no":53,"station_name":"Mount Austin Estate","column":"right",
   "y_start":0.40,"y_end":0.72,"continues_from_prev":false,
   "continues_next_page":false}
]}
"""


def find_stations(page_img, model=VISION_MODEL, mock=False):
    """STAGE 1: return a list of station descriptors located on the page."""
    if mock:
        return _mock_find()
    data = _call_vision(page_img, FIND_PROMPT, model)
    return data["stations"]


# ==============================================================================
# STAGE 2 — CROP A STATION AND TRANSCRIBE IT
# ==============================================================================
READ_PROMPT = """\
This image is ONE station's block from a colonial-era Malaysian rainfall
register (station: {station}). Each data row has a 4-digit YEAR, twelve monthly
values (Jan..Dec) in inches to two decimals, then a printed ANNUAL total. Blank
cells (dashes) are null. Summary rows are labelled MEAN or MAX (24/48/72 hrs):
give those "year": null and "row_type" "MEAN"/"MAX24HR"/"MAX48HR"/"MAX72HR".
Ordinary years use "row_type":"DATA".

Read digits EXACTLY as printed. Do NOT adjust a value to make the row sum to the
annual (that is checked downstream). If a single digit is illegible, use null
for that one cell. Watch for a year-label vertical offset (year printed one row
above its data) and pair each year with the correct row.

Return ONLY JSON: {{"rows":[
 {{"row_type":"DATA","year":1931,"months":[13.51,2.46,...,12.98],"annual":118.93}}
]}}
"""


def crop_station(page_img, station, pad_y=0.012, scale=4, cutoff=0.35):
    """Build a tight, preprocessed crop for one station from Stage-1 fractions."""
    w, h = page_img.size
    x1f, x2f = COLUMN_X[station.get("column", "left")]
    y1f = max(0.0, station["y_start"] + 0.008 - pad_y)   # start just below header
    y2f = min(1.0, station["y_end"] + pad_y)
    crop = page_img.crop((int(w*x1f), int(h*y1f), int(w*x2f), int(h*y2f)))
    crop = crop.resize((crop.width*scale, crop.height*scale), Image.LANCZOS)
    return ImageOps.autocontrast(crop.convert("L"), cutoff=cutoff)


def transcribe_block(block_img, station, model=VISION_MODEL, mock=False):
    """STAGE 2: transcribe one cropped station block into row dicts."""
    if mock:
        return _mock_read(station["station_no"])
    prompt = READ_PROMPT.format(station=station.get("station_name", "unknown"))
    data = _call_vision(block_img, prompt, model)
    return data["rows"]


# ==============================================================================
# RECONCILIATION  (unchanged logic; both stages feed into this)
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
    if annual is None or any(m is None for m in months) or len(months) != 12:
        return None
    base = sum(months)
    cands = []
    for i, val in enumerate(months):
        needed = round(annual - (base - val), 2)
        if needed < 0:
            continue
        if 0.01 < abs(needed - val) <= max_delta:
            cands.append((i, val, needed))
    return cands[0] if len(cands) == 1 else None


Row = namedtuple("Row", "station_no station_name row_type year months annual computed confidence")


def process_row(rec, station):
    row_type = rec.get("row_type", "DATA")
    year = rec.get("year")
    months = (list(rec.get("months", [])) + [None]*12)[:12]
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
        tag = "source_printed_mean" if row_type == "MEAN" else "source_printed"
    return Row(station["station_no"], station.get("station_name", ""),
               row_type, year, months, annual, computed, tag)


# ==============================================================================
# CSV
# ==============================================================================
CSV_COLUMNS = (["station_no", "station_name", "row_type", "year"]
               + MONTHS + ["annual", "computed", "data_confidence"])


def append_csv(path, rows):
    import csv
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(CSV_COLUMNS)
        for r in rows:
            vals = ["" if m is None else m for m in r.months]
            w.writerow([r.station_no, r.station_name, r.row_type,
                        "" if r.year is None else r.year, *vals,
                        "" if r.annual is None else r.annual,
                        "" if r.computed is None else r.computed, r.confidence])


# ==============================================================================
# ORCHESTRATION
# ==============================================================================
def run_page(image_path, out_csv, mock=False):
    print("=" * 76)
    print(f" PAGE: {os.path.basename(image_path)}")
    print("=" * 76)
    page = Image.open(image_path)
    print(f" size {page.size[0]}x{page.size[1]}")

    # ---- STAGE 1 ----
    where = "MOCK" if mock else f"API -> {VISION_MODEL}"
    print(f"\n STAGE 1  find_stations ({where})")
    stations = find_stations(page, mock=mock)
    for s in stations:
        flags = []
        if s.get("continues_from_prev"):  flags.append("<-prev")
        if s.get("continues_next_page"):  flags.append("next->")
        print(f"   #{s['station_no']:<3} {s['station_name']:<34} "
              f"{s['column']:<5} y={s['y_start']:.2f}..{s['y_end']:.2f} "
              f"{' '.join(flags)}")

    # ---- STAGE 2 (per station) ----
    print(f"\n STAGE 2  crop + transcribe each station ({where})")
    all_rows = []
    for s in stations:
        block = crop_station(page, s)
        recs = transcribe_block(block, s, mock=mock)
        rows = [process_row(r, s) for r in recs]
        all_rows.extend(rows)
        ok = sum(r.confidence.startswith(("ok_", "source")) for r in rows)
        fix = sum(r.confidence.startswith("ocr_corrected") for r in rows)
        flag = sum(r.confidence.startswith("annual") for r in rows)
        note = ""
        if s.get("continues_next_page"):
            note = "  (continues next page — stitch downstream)"
        print(f"   #{s['station_no']:<3} {s['station_name']:<28} "
              f"crop {block.size[0]}x{block.size[1]}px  ->  "
              f"{len(rows)} rows  [{ok} ok · {fix} fixed · {flag} flagged]{note}")

    append_csv(out_csv, all_rows)
    print(f"\n Wrote {len(all_rows)} rows -> {out_csv}")
    return all_rows


# ==============================================================================
# MOCKS (stand-ins for the two model calls, so the flow runs offline)
# ==============================================================================
def _mock_find():
    """Pretend the model scanned the page and found two stations."""
    return [
        {"station_no": 51, "station_name": "Senai Rubber Estate", "column": "left",
         "y_start": 0.28, "y_end": 0.62, "continues_from_prev": False,
         "continues_next_page": False},
        {"station_no": 53, "station_name": "Mount Austin Estate", "column": "right",
         "y_start": 0.40, "y_end": 0.72, "continues_from_prev": False,
         "continues_next_page": False},
    ]


def _mock_read(station_no):
    """Pretend the model transcribed the cropped block. Real Station values;
    Station 53's 1935 has a corrupted Jan to show the auto-correction."""
    if station_no == 51:
        return [
            {"row_type": "DATA", "year": 1933,
             "months": [14.20,5.20,15.00,7.60,11.20,7.30,5.80,9.30,8.10,15.50,18.70,8.90],
             "annual": 126.80},
            {"row_type": "DATA", "year": 1934,   # genuinely inconsistent -> flag
             "months": [2.80,8.30,22.50,11.20,6.50,14.50,8.20,6.60,8.10,12.10,10.90,7.50],
             "annual": 137.80},
            {"row_type": "DATA", "year": 1935,
             "months": [4.70,7.80,5.90,7.90,10.50,6.20,4.20,9.40,3.40,7.10,12.90,15.10],
             "annual": 95.10},
        ]
    if station_no == 53:
        return [
            {"row_type": "DATA", "year": 1931,
             "months": [13.51,2.46,11.32,16.36,4.54,12.68,8.79,10.92,7.35,4.67,13.35,12.98],
             "annual": 118.93},
            {"row_type": "DATA", "year": 1935,   # Jan corrupted 4.35 -> 24.35
             "months": [24.35,8.31,10.53,9.90,6.89,6.93,4.17,11.22,3.51,8.75,13.11,14.33],
             "annual": 102.00},
            {"row_type": "DATA", "year": 1954,   # verified extreme Dec 49.43
             "months": [11.13,7.65,8.77,13.51,10.02,12.32,5.89,13.01,5.74,17.41,17.15,49.43],
             "annual": 172.03},
            {"row_type": "MEAN", "year": None,
             "months": [11.81,7.63,12.75,11.39,8.97,7.23,6.60,9.63,7.17,10.25,10.70,12.53],
             "annual": 116.66},
        ]
    return []


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    mock = "--mock" in sys.argv or not os.environ.get("ANTHROPIC_API_KEY")
    image = args[0] if args else "/mnt/project/Image00029.jpg"
    if mock and "--mock" not in sys.argv:
        print("(no ANTHROPIC_API_KEY -> running in --mock mode)\n")
    run_page(image, out_csv="/tmp/two_stage_output.csv", mock=mock)
