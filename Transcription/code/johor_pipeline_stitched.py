#!/usr/bin/env python3
"""
================================================================================
 Johor Rainfall Register — TWO-STAGE Pipeline with CROSS-PAGE STITCHING
================================================================================
Stage 1 finds every station header on a page and its vertical span.
Stage 2 crops each block from those fractions and transcribes it.
STITCHING then joins any station whose data runs across a page break into one
record, using the model's continues_next_page / continues_from_prev flags.

    page N ─▶ find ─▶ [St.43 …rows… continues_next_page=true]  ── held over ──┐
    page N+1─▶ find ─▶ [headerless continuation continues_from_prev=true] ◀───┘
                              └────────────── merged into one St.43 record

This is a real, runnable version: Stages 1 and 2 make genuine Anthropic API
calls. Use --mock to exercise the full orchestration + stitching offline
(it simulates a station split across two pages).

Run for real:
    export ANTHROPIC_API_KEY=sk-ant-...
    pip install anthropic pillow --break-system-packages
    python3 johor_pipeline_stitched.py page01.jpg page02.jpg page03.jpg ...

Offline test of the stitching:
    python3 johor_pipeline_stitched.py --mock

Principle unchanged: the model READS; arithmetic reconciliation DECIDES what to
trust; no value is invented to force a row to balance.
================================================================================
"""

import os
import io
import sys
import csv
import json
import time
import base64
from dataclasses import dataclass, field
from typing import Optional
from PIL import Image, ImageOps

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# --- Recognition model & sampling settings (cite these in the methods) --------
# Transcription is deterministic, not generative, so sampling is pinned:
#   temperature = 0  -> take the single most-probable reading of each glyph
#   top_p       = 1  -> no nucleus truncation (has no effect at temperature 0)
#   top_k       -> left unset (no practical effect at temperature 0)
# NOTE: LLMs are not guaranteed bit-for-bit deterministic even at temperature 0;
# the guarantee of correctness comes from downstream reconciliation against the
# printed annual totals, not from these settings.
VISION_MODEL = "claude-sonnet-4-6"
TEMPERATURE  = 0
TOP_P        = 1
MAX_TOKENS_READ = 3000     # station-block transcription
MAX_TOKENS_FIND = 1500     # header-location stage
COLUMN_X = {"left": (0.07, 0.53), "right": (0.50, 0.995)}


def run_metadata():
    """Return a one-line provenance record of the exact recognition settings,
    written into the output CSV header so the deposited data cites its own run."""
    import datetime
    try:
        import anthropic
        sdk = getattr(anthropic, "__version__", "unknown")
    except Exception:
        sdk = "not-installed"
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (f"# recognition: model={VISION_MODEL}; temperature={TEMPERATURE}; "
            f"top_p={TOP_P}; max_tokens_read={MAX_TOKENS_READ}; "
            f"max_tokens_find={MAX_TOKENS_FIND}; anthropic_sdk={sdk}; run_utc={ts}")


# ==============================================================================
# API plumbing — real call with retries and robust JSON parsing
# ==============================================================================
def _to_b64_png(pil_img):
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


def _extract_json(text):
    """Pull the JSON object out of a model reply, tolerating code fences/prose."""
    text = text.strip()
    if "```" in text:
        # take the content of the first fenced block
        parts = text.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                text = p
                break
    # fall back: slice from first { to last }
    if not text.startswith("{"):
        i, j = text.find("{"), text.rfind("}")
        if i != -1 and j != -1:
            text = text[i:j + 1]
    return json.loads(text)


def call_vision(pil_img, prompt, model=VISION_MODEL, max_tokens=MAX_TOKENS_READ,
                retries=4, backoff=2.0):
    """One image+text API call, with exponential-backoff retries. Returns dict."""
    from anthropic import Anthropic
    client = Anthropic()  # reads ANTHROPIC_API_KEY
    b64 = _to_b64_png(pil_img)
    last_err = None
    for attempt in range(retries):
        try:
            resp = client.messages.create(
                model=model, max_tokens=max_tokens,
                temperature=TEMPERATURE,  # deterministic transcription, not generation
                top_p=TOP_P,              # no nucleus truncation (inert at temperature 0)
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64",
                     "media_type": "image/png", "data": b64}},
                    {"type": "text", "text": prompt},
                ]}],
            )
            text = "".join(b.text for b in resp.content
                           if getattr(b, "type", "") == "text")
            return _extract_json(text)
        except Exception as e:                      # transient errors -> retry
            last_err = e
            if attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))
    raise RuntimeError(f"vision call failed after {retries} tries: {last_err}")


# ==============================================================================
# STAGE 1 — find station headers + spans
# ==============================================================================
FIND_PROMPT = """\
You are looking at ONE full page (a two-column spread) of a colonial-era
Malaysian rainfall register. Each column holds one or more STATION tables. A
station begins with a header like "Station No. 53—Mount Austin Estate", then
yearly rows, then usually MEAN / MAX summary rows.

List EVERY block in reading order (left column top-to-bottom, then right column).
Two kinds of block:
  (A) a normal station starting with a header, and
  (B) a HEADERLESS CONTINUATION: a column that BEGINS with data rows and no
      header, because the data continues from the previous page.

For each block report:
  - "station_no": integer after "Station No.", or null for a headerless
     continuation
  - "station_name": text after the dash, or null for a continuation
  - "column": "left" or "right"
  - "y_start", "y_end": fractions 0..1 of page HEIGHT bounding the block
  - "continues_from_prev": true for a headerless continuation block
  - "continues_next_page": true if the block runs to the very bottom of its
     column with NO MEAN/MAX summary (its data likely continues next page)

Return ONLY JSON, no prose:
{"blocks":[
  {"station_no":53,"station_name":"Mount Austin Estate","column":"right",
   "y_start":0.40,"y_end":0.72,"continues_from_prev":false,
   "continues_next_page":false}
]}
"""


def find_blocks(page_img, model=VISION_MODEL, mock=False, _page_id=None):
    if mock:
        return _mock_find(_page_id)
    data = call_vision(page_img, FIND_PROMPT, model, max_tokens=MAX_TOKENS_FIND)
    return data.get("blocks", [])


# ==============================================================================
# STAGE 2 — crop + transcribe one block
# ==============================================================================
READ_PROMPT = """\
This image is ONE block from a colonial-era Malaysian rainfall register
(station: {station}). Each data row has a 4-digit YEAR, twelve monthly values
(Jan..Dec) in inches to two decimals, then a printed ANNUAL total. Blank cells
(dashes) are null. Summary rows are labelled MEAN or MAX (24/48/72 hrs): give
those "year": null and "row_type" "MEAN"/"MAX24HR"/"MAX48HR"/"MAX72HR".
Ordinary years use "row_type":"DATA". This block may be a continuation with no
header — just transcribe the rows you see.

Read digits EXACTLY as printed. Do NOT adjust a value to make the row sum to the
annual (checked downstream). If one digit is illegible, use null for that cell.
Watch for a year-label vertical offset (year printed one row above its data).

Return ONLY JSON:
{{"rows":[
 {{"row_type":"DATA","year":1931,"months":[13.51,2.46,...,12.98],"annual":118.93}}
]}}
"""


def crop_block(page_img, blk, pad_y=0.012, scale=4, cutoff=0.35):
    w, h = page_img.size
    x1f, x2f = COLUMN_X.get(blk.get("column", "left"), COLUMN_X["left"])
    # a continuation starts at the very top of the column (no header to skip)
    head_skip = 0.0 if blk.get("continues_from_prev") else 0.008
    y1f = max(0.0, blk["y_start"] + head_skip - pad_y)
    y2f = min(1.0, blk["y_end"] + pad_y)
    crop = page_img.crop((int(w*x1f), int(h*y1f), int(w*x2f), int(h*y2f)))
    crop = crop.resize((crop.width*scale, crop.height*scale), Image.LANCZOS)
    return ImageOps.autocontrast(crop.convert("L"), cutoff=cutoff)


def transcribe_block(page_img, blk, model=VISION_MODEL, mock=False, _page_id=None):
    if mock:
        return _mock_read(_page_id, blk)
    crop = crop_block(page_img, blk)
    name = blk.get("station_name") or "continuation"
    data = call_vision(crop, READ_PROMPT.format(station=name), model)
    return data.get("rows", [])


# ==============================================================================
# RECONCILIATION (unchanged)
# ==============================================================================
def reconcile(months, annual, tol_ok=0.10, tol_round=0.50):
    present = [m for m in months if m is not None]
    if len(present) < 12:
        return "incomplete", (round(sum(present), 2) if present else None)
    computed = round(sum(present), 2)
    if annual is None:
        return "no_annual", computed
    d = abs(computed - annual)
    return ("ok_reconciled" if d <= tol_ok else
            "ok_rounding" if d <= tol_round else "check"), computed


def try_single_fix(months, annual, max_delta=25.0):
    if annual is None or any(m is None for m in months) or len(months) != 12:
        return None
    base = sum(months)
    cands = [(i, v, round(annual - (base - v), 2)) for i, v in enumerate(months)]
    cands = [(i, v, n) for (i, v, n) in cands if n >= 0 and 0.01 < abs(n - v) <= max_delta]
    return cands[0] if len(cands) == 1 else None


# ==============================================================================
# STATION RECORD + STITCHING
# ==============================================================================
@dataclass
class Block:
    station_no: Optional[int]
    station_name: Optional[str]
    rows: list                       # raw row dicts from Stage 2
    from_prev: bool = False
    to_next: bool = False
    pages: list = field(default_factory=list)
    note: str = ""


def stitch_step(pending: Optional[Block], blk: Block):
    """Fold one freshly-read block into the running state.
    Returns (new_pending, [completed_blocks])."""
    completed = []

    if pending is not None:
        if blk.from_prev:
            # This is the continuation of the held-over station: merge.
            pending.rows.extend(blk.rows)
            pending.pages.extend(blk.pages)
            pending.to_next = blk.to_next
            if blk.to_next:
                return pending, completed          # still open (spans 3+ pages)
            return None, [pending]                 # station now complete
        else:
            # We expected a continuation but got a normal header instead:
            # close the pending station as-is (its record ends at the page break).
            pending.note = "closed_without_continuation"
            completed.append(pending)
            pending = None
            # fall through to handle blk normally

    # No pending (or just cleared it): handle blk on its own.
    if blk.from_prev:
        # A continuation with nothing to attach to (missing prior page / false flag).
        blk.note = "orphan_continuation_no_parent"
        completed.append(blk)
        return None, completed
    if blk.to_next:
        return blk, completed                       # hold it for the next page
    completed.append(blk)
    return None, completed


def reading_order(blocks):
    """Left column (top→bottom) before right column (top→bottom)."""
    return sorted(blocks, key=lambda b: (0 if b.get("column") == "left" else 1,
                                         b.get("y_start", 0.0)))


# ==============================================================================
# OUTPUT
# ==============================================================================
CSV_COLUMNS = (["station_no", "station_name", "row_type", "year"]
               + MONTHS + ["annual", "computed", "data_confidence", "source_pages"])


def finalize_and_write(stations, out_csv):
    """Reconcile every row of every completed station and write the CSV."""
    total = ok = fixed = flagged = 0
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        f.write(run_metadata() + "\n")   # provenance of recognition settings
        w = csv.writer(f)
        w.writerow(CSV_COLUMNS)
        for st in stations:
            pages = "+".join(dict.fromkeys(st.pages))     # unique, order-preserving
            for rec in st.rows:
                total += 1
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
                        fixed += 1
                    else:
                        tag = (f"annual_discrepancy:computed={computed}"
                               f"_printed={annual}_unresolved")
                        flagged += 1
                elif status.startswith("ok"):
                    ok += 1
                if row_type != "DATA" and status == "ok_reconciled":
                    tag = "source_printed_mean" if row_type == "MEAN" else "source_printed"
                if st.note:
                    tag = f"{tag};{st.note}"
                vals = ["" if m is None else m for m in months]
                w.writerow([st.station_no, st.station_name, row_type,
                            "" if year is None else year, *vals,
                            "" if annual is None else annual,
                            "" if computed is None else computed, tag, pages])
    return total, ok, fixed, flagged


# ==============================================================================
# ORCHESTRATION over an ordered list of page images
# ==============================================================================
def run_pages(image_paths, out_csv, model=VISION_MODEL, mock=False, verbose=True):
    completed = []
    pending: Optional[Block] = None

    for idx, path in enumerate(image_paths):
        page_id = idx if mock else None
        page = None if mock else Image.open(path)
        label = path if not mock else f"[mock page {idx+1}]"
        if verbose:
            print("=" * 74)
            print(f" PAGE {idx+1}/{len(image_paths)}: {os.path.basename(str(label))}")
            print("=" * 74)

        blocks = find_blocks(page, model, mock, _page_id=page_id)
        for b in reading_order(blocks):
            rows = transcribe_block(page, b, model, mock, _page_id=page_id)
            blk = Block(
                station_no=b.get("station_no"),
                station_name=b.get("station_name"),
                rows=rows,
                from_prev=bool(b.get("continues_from_prev")),
                to_next=bool(b.get("continues_next_page")),
                pages=[os.path.basename(str(label))],
            )
            if verbose:
                who = (f"#{blk.station_no} {blk.station_name}" if blk.station_no
                       else "«headerless continuation»")
                flags = " ".join(fl for fl, on in
                                 [("<-prev", blk.from_prev), ("next->", blk.to_next)] if on)
                print(f"   read {who:<40} {len(blk.rows):>2} rows  {flags}")

            pending, done = stitch_step(pending, blk)
            for st in done:
                completed.append(st)
                if verbose and (st.from_prev or len(st.pages) > 1 or st.note):
                    tag = st.note or ("stitched across " + "+".join(dict.fromkeys(st.pages)))
                    print(f"      -> completed #{st.station_no} "
                          f"{st.station_name}  ({tag})")

    if pending is not None:               # flush a station left open at the end
        pending.note = pending.note or "open_at_end_of_input"
        completed.append(pending)

    total, ok, fixed, flagged = finalize_and_write(completed, out_csv)
    if verbose:
        print("\n" + "=" * 74)
        print(f" DONE  {len(completed)} stations · {total} rows  "
              f"[{ok} ok · {fixed} auto-corrected · {flagged} flagged]")
        print(f" -> {out_csv}")
    return completed


# ==============================================================================
# MOCKS — simulate a station (No. 60) split across two pages, plus a normal one
# ==============================================================================
def _mock_find(page_id):
    if page_id == 0:   # page 1: Station 60 starts bottom-right, runs off the page
        return [
            {"station_no": 59, "station_name": "Kangkar Estate", "column": "left",
             "y_start": 0.15, "y_end": 0.55, "continues_from_prev": False,
             "continues_next_page": False},
            {"station_no": 60, "station_name": "Sedenak Estate", "column": "right",
             "y_start": 0.60, "y_end": 0.99, "continues_from_prev": False,
             "continues_next_page": True},          # <-- runs onto next page
        ]
    if page_id == 1:   # page 2: headerless continuation of 60, then Station 61
        return [
            {"station_no": None, "station_name": None, "column": "left",
             "y_start": 0.12, "y_end": 0.34, "continues_from_prev": True,   # <-- cont.
             "continues_next_page": False},
            {"station_no": 61, "station_name": " Layang Estate", "column": "left",
             "y_start": 0.36, "y_end": 0.80, "continues_from_prev": False,
             "continues_next_page": False},
        ]
    return []


def _mock_read(page_id, blk):
    # Station 59 (page 1, complete)
    if page_id == 0 and blk.get("station_no") == 59:
        return [
            {"row_type": "DATA", "year": 1948,
             "months": [10.0,5.0,8.0,9.0,7.0,6.0,5.0,8.0,9.0,10.0,11.0,7.0], "annual": 95.0},
            {"row_type": "MEAN", "year": None,
             "months": [10.0,5.0,8.0,9.0,7.0,6.0,5.0,8.0,9.0,10.0,11.0,7.0], "annual": 95.0},
        ]
    # Station 60 FIRST half (page 1): early years, no MEAN yet
    if page_id == 0 and blk.get("station_no") == 60:
        return [
            {"row_type": "DATA", "year": 1951,
             "months": [12.0,4.0,9.0,8.0,6.0,7.0,5.0,10.0,9.0,8.0,7.0,6.0], "annual": 91.0},
            {"row_type": "DATA", "year": 1952,
             "months": [11.0,5.0,8.0,9.0,7.0,6.0,6.0,9.0,8.0,7.0,8.0,7.0], "annual": 91.0},
        ]
    # Station 60 SECOND half (page 2, headerless continuation): later years + MEAN
    if page_id == 1 and blk.get("continues_from_prev"):
        return [
            {"row_type": "DATA", "year": 1953,
             "months": [10.0,6.0,7.0,8.0,9.0,5.0,6.0,8.0,7.0,9.0,10.0,6.0], "annual": 91.0},
            {"row_type": "MEAN", "year": None,
             "months": [11.0,5.0,8.0,8.33,7.33,6.0,5.67,9.0,8.0,8.0,8.33,6.33], "annual": 91.0},
        ]
    # Station 61 (page 2, complete)
    if page_id == 1 and blk.get("station_no") == 61:
        return [
            {"row_type": "DATA", "year": 1955,
             "months": [9.0,5.0,7.0,8.0,6.0,7.0,6.0,8.0,9.0,10.0,9.0,7.0], "annual": 91.0},
        ]
    return []


if __name__ == "__main__":
    argv = sys.argv[1:]
    mock = "--mock" in argv
    paths = [a for a in argv if not a.startswith("--")]
    if mock:
        # Two simulated pages; real Image.open is skipped in mock mode.
        run_pages(["page01.jpg", "page02.jpg"],
                  out_csv="/tmp/stitched_output.csv", mock=True)
    else:
        if not paths:
            print("usage: python3 johor_pipeline_stitched.py page01.jpg page02.jpg ...")
            print("   or: python3 johor_pipeline_stitched.py --mock")
            sys.exit(1)
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("ERROR: set ANTHROPIC_API_KEY, or use --mock to test offline.")
            sys.exit(1)
        run_pages(paths, out_csv="johor_stitched.csv", mock=False)
