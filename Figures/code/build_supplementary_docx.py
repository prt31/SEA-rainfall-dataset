#!/usr/bin/env python3
"""Build the supplementary methods document (transcription workflow + settings +
prompts + table-structure figures + Tesseract-vs-VM value comparison)."""
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

SCR = "/tmp/claude-0/-home-claude-my-sg-su-rainfall-dataset/22db5fb9-bd74-5590-a634-2ea29604a7f1/scratchpad/"
OUT = "/home/claude/my-sg-su-rainfall-dataset/docs/supplementary_transcription_methods.docx"

MONO = "Consolas"
ACCENT = RGBColor(0x1F, 0x4E, 0x79)
GREY = RGBColor(0x55, 0x55, 0x55)

doc = Document()
st = doc.styles["Normal"]
st.font.name = "Calibri"; st.font.size = Pt(10.5)
for s in ["Heading 1","Heading 2","Heading 3"]:
    doc.styles[s].font.color.rgb = ACCENT

def para(text="", size=10.5, italic=False, bold=False, color=None, after=6, align=None):
    p = doc.add_paragraph()
    if align: p.alignment = align
    r = p.add_run(text)
    r.font.size = Pt(size); r.italic = italic; r.bold = bold
    if color: r.font.color.rgb = color
    p.paragraph_format.space_after = Pt(after)
    return p

def code_block(text):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8); p.paragraph_format.space_before = Pt(4)
    r = p.add_run(text)
    r.font.name = MONO; r.font.size = Pt(8.8)
    r._element.rPr.rFonts.set(qn("w:eastAsia"), MONO)
    # light shading
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd"); shd.set(qn("w:val"),"clear"); shd.set(qn("w:fill"),"F2F4F7")
    pPr.append(shd)
    return p

def caption(text):
    p = doc.add_paragraph()
    r = p.add_run(text); r.font.size = Pt(8.8); r.italic = True; r.font.color.rgb = GREY
    p.paragraph_format.space_after = Pt(12)

def shade_cell(cell, hexcol):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd"); shd.set(qn("w:val"),"clear"); shd.set(qn("w:fill"),hexcol)
    tcPr.append(shd)

def set_cell(cell, text, bold=False, size=9, color=None, mono=False):
    cell.text = ""
    p = cell.paragraphs[0]; p.paragraph_format.space_after = Pt(0); p.paragraph_format.space_before = Pt(0)
    r = p.add_run(text); r.font.size = Pt(size); r.bold = bold
    if mono: r.font.name = MONO
    if color: r.font.color.rgb = color

# ============================== TITLE ========================================
t = doc.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = t.add_run("Supplementary Material"); r.bold=True; r.font.size=Pt(18); r.font.color.rgb=ACCENT
sub = doc.add_paragraph(); sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = sub.add_run("Transcription Workflow, Model Settings, and Tesseract-vs-Vision-Model Readings")
r.font.size=Pt(12.5); r.italic=True
sub2 = doc.add_paragraph(); sub2.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = sub2.add_run("Digitised Johor rainfall register (Federated Malay States series, 1926–1958)")
r.font.size=Pt(10.5); r.font.color.rgb=GREY
doc.add_paragraph()

# ============================== 1. OVERVIEW ===================================
doc.add_heading("1. Transcription workflow", level=1)
para("Each scanned register page is processed by a three-stage pipeline — "
     "DETECT → READ → STITCH — in which optical character recognition and a "
     "vision-language model play complementary roles and printed annual totals act as "
     "the final arbiter of which readings to trust. No value is ever altered to force a "
     "row to add up; every row is either verified against its printed annual, corrected "
     "by a single unambiguous fix, or kept exactly as read and flagged.", after=8)

doc.add_heading("1.1  Stage 1 — Detection (structural gate)", level=2)
para("The vision model proposes station-block boundaries on the full page (header "
     "position, column side, vertical extent). Each proposed block is then validated "
     "structurally by Tesseract OCR — not by the model that proposed it — using the "
     "token positions Tesseract returns. A block passes the gate only if five checks "
     "hold: (i) ~14 columns are recoverable; (ii) row pitch is regular (low coefficient "
     "of variation of inter-row spacing); (iii) the year column is monotonic; (iv) a "
     "header is present; and (v) a MEAN/MAX sentinel row is found at the foot. "
     "Detection uses Tesseract’s geometry (where tokens sit), which is reliable, not "
     "its character values (what the tokens say), which are not.", after=8)

doc.add_heading("1.2  Stage 2 — Reading (Tesseract-first, reconciliation-gated escalation)", level=2)
para("Within a validated block each row is read cheaply by Tesseract first. The twelve "
     "monthly values are summed and compared with the printed annual. The difference "
     "decides what happens next, on the following escalation ladder:", after=6)
for a,b in [
    ("≤ 0.10","accept the Tesseract row — tag ok_reconciled."),
    ("≤ 0.50","accept, tag ok_rounding (records the computed sum; a rounding artifact)."),
    ("single-cell fix","if exactly one cell change makes the row reconcile, apply it — tag ocr_corrected:MONTH_old→new."),
    ("escalate","otherwise re-read the whole row with the vision model (temperature 0)."),
    ("still fails","keep the reading as-is and tag annual_discrepancy:computed=X_printed=Y — never invent a value."),
]:
    p = doc.add_paragraph(style="List Bullet")
    rr=p.add_run(a+"  "); rr.bold=True; rr.font.size=Pt(10)
    rr2=p.add_run(b); rr2.font.size=Pt(10)
    p.paragraph_format.space_after=Pt(2)
para("Because the printed annual is an independent check carried in the source itself, "
     "escalation is triggered by arithmetic evidence of a misread rather than by a "
     "confidence score. The vision model is therefore invoked only where it is needed, "
     "which is where Tesseract’s cheap reading demonstrably fails to reconcile.", after=8)

doc.add_heading("1.3  Stage 3 — Stitching", level=2)
para("Stations whose rows span a column break or a page break are rejoined. A block "
     "flagged continues_from_prev is a headerless continuation; it is attached to the "
     "most recent block carrying the same (or an inferable) station number, and its "
     "already-reconciled rows are concatenated in year order. Stitching concatenates "
     "rows that were each reconciled during Stage 2; it performs no further arithmetic "
     "reconciliation of its own.", after=8)

doc.add_heading("1.4  Image pre-processing (shared by both readers)", level=2)
para("Pre-processing happens once, at block-crop time, and the same prepared crop is "
     "handed to both Tesseract and the vision model so neither has an unfair advantage. "
     "For each block the page is cropped to the station’s column and vertical extent, "
     "up-scaled ×3 by Lanczos resampling, converted to grayscale, and contrast-"
     "stretched with autocontrast (cutoff 0.35) to burn off scan haze and lift faint "
     "ink. In code (code/johor_detect_and_read.py):", after=6)
code_block(
"def preprocess(img, x1f, y1f, x2f, y2f, scale=3, cutoff=0.35):\n"
"    w, h = img.size\n"
"    c = img.crop((int(w*x1f), int(h*y1f), int(w*x2f), int(h*y2f)))\n"
"    c = c.resize((c.width*scale, c.height*scale), Image.LANCZOS)\n"
"    return ImageOps.autocontrast(c.convert(\"L\"), cutoff=cutoff), c.convert(\"RGB\")")

# ============================== 2. SETTINGS ===================================
doc.add_heading("2. Model and OCR settings", level=1)
para("All settings are recorded verbatim in the header line of every output CSV "
     "(the run_metadata() line), so each delivered file carries its own provenance.", after=8)

doc.add_heading("2.1  Vision-language model", level=2)
tbl = doc.add_table(rows=1, cols=3); tbl.style="Light Grid Accent 1"; tbl.alignment=WD_TABLE_ALIGNMENT.CENTER
hdr = tbl.rows[0].cells
for i,h in enumerate(["Parameter","Value","Role / rationale"]):
    set_cell(hdr[i], h, bold=True, size=9.5, color=RGBColor(0xFF,0xFF,0xFF)); shade_cell(hdr[i],"1F4E79")
rows=[
 ("model","claude-sonnet-4-6","block proposal (Stage 1) and escalated row re-reading (Stage 2)"),
 ("temperature","0","deterministic transcription — same image yields the same reading"),
 ("top_p","1","no nucleus truncation (inert at temperature 0)"),
 ("max_tokens (read)","3000","station-block transcription response budget"),
 ("max_tokens (find)","1500","header-location / block-proposal response budget"),
 ("input","1 PNG + text prompt","single pre-processed crop per call, base64-encoded"),
 ("output","strict JSON","parsed between the first { and last } ; no prose accepted"),
]
for a,b,c in rows:
    cells = tbl.add_row().cells
    set_cell(cells[0],a,mono=True,size=9); set_cell(cells[1],b,mono=True,size=9); set_cell(cells[2],c,size=9)
caption("Table S1. Vision-language model settings. Determinism (temperature 0) is "
        "deliberate: the model is used as a careful reader, not a generator.")

doc.add_heading("2.2  Tesseract OCR", level=2)
tbl = doc.add_table(rows=1, cols=3); tbl.style="Light Grid Accent 1"; tbl.alignment=WD_TABLE_ALIGNMENT.CENTER
hdr = tbl.rows[0].cells
for i,h in enumerate(["Parameter","Value","Role / rationale"]):
    set_cell(hdr[i], h, bold=True, size=9.5, color=RGBColor(0xFF,0xFF,0xFF)); shade_cell(hdr[i],"1F4E79")
rows=[
 ("engine","Tesseract 5.3.4","structural validation + cheap first-pass reading"),
 ("--psm","6","assume a single uniform block of text (tabular rows)"),
 ("preserve_interword_spaces","1","keep column gaps so token x-positions map to columns"),
 ("token filter","regex [0-9]{1,4}\\.?[0-9]{0,2}, conf>30","keep only plausible numeric cells"),
 ("pre-processing","×3 Lanczos, grayscale, autocontrast 0.35","identical crop to the vision model"),
]
for a,b,c in rows:
    cells = tbl.add_row().cells
    set_cell(cells[0],a,mono=True,size=9); set_cell(cells[1],b,mono=True,size=9); set_cell(cells[2],c,size=9)
caption("Table S2. Tesseract OCR settings. Tesseract is trusted for token geometry "
        "(column/row positions) and used only as a first-pass reader whose output must "
        "survive the reconciliation check.")

# ============================== 3. PROMPTS ====================================
doc.add_heading("3. Prompts (verbatim)", level=1)
para("The two prompts below are reproduced exactly as issued. Both demand strict JSON "
     "and forbid prose. The reading prompt explicitly instructs the model to read digits "
     "as printed and never to adjust a cell to make a row sum — the reconciliation step, "
     "not the model, resolves arithmetic.", after=8)

doc.add_heading("3.1  Block-proposal prompt (Stage 1, FIND_PROMPT)", level=2)
code_block(
"This is one full page of a colonial-era Malaysian rainfall register (two\n"
"columns). List every station block in reading order. For each: station_no\n"
"(int or null for a headerless continuation), station_name (or null), column\n"
"(\"left\"/\"right\"), y_start and y_end as fractions of page height,\n"
"continues_from_prev (bool), continues_next_page (bool). Return ONLY JSON:\n"
"{\"blocks\":[...]}. No prose.")

doc.add_heading("3.2  Row-reading prompt (Stage 2, READ_PROMPT)", level=2)
code_block(
"This image is one station block from a rainfall register (station:\n"
"{station}). Each data row: 4-digit YEAR, twelve monthly values (Jan..Dec,\n"
"inches, 2 dp), then printed ANNUAL. Blank cells (dashes) -> null. Summary\n"
"rows labelled MEAN/MAX get year null and row_type MEAN/MAX24HR/MAX48HR/\n"
"MAX72HR; ordinary years row_type DATA. Read digits EXACTLY as printed;\n"
"never adjust to make a row sum. Illegible cell -> null. Return ONLY JSON:\n"
"{\"rows\":[{\"row_type\":\"DATA\",\"year\":1931,\"months\":[...12...],\n"
"\"annual\":118.93}]}")

# ============================== 4. TABLE STRUCTURE ============================
doc.add_heading("4. Table structure", level=1)
para("The figures below trace a single station block (Station 53, Mount Austin Estate; "
     "image Image00029, right column) from the raw two-column page down to one isolated "
     "data row, showing the tabular structure the pipeline must recover: a 4-digit year, "
     "twelve monthly columns (Jan–Dec), and a printed annual total.", after=8)

doc.add_picture(SCR+"figP_a_column_isolation_sm.jpg", width=Inches(6.3))
caption("Figure S1. Column isolation. The full register page (left) is cropped to a single "
        "station column (right); COLUMN_X bounds are {left:(0.07,0.53), right:(0.50,0.995)} "
        "as fractions of page width.")

doc.add_picture(SCR+"figP_b_overlay_preprocessed_sm.jpg", width=Inches(6.3))
caption("Figure S2. Detected data block on the pre-processed crop. The 14-column grid "
        "(year + Jan–Dec + annual) is overlaid on the ×3-upscaled, autocontrast-stretched "
        "block that both readers receive. Summary rows (MEAN, Max.24/48/72hr) sit at the foot.")

doc.add_picture(SCR+"figP_c_single_row_sm.jpg", width=Inches(6.3))
caption("Figure S3. A single isolated data row from Figure S2: one year, twelve monthly "
        "values, one printed annual — the unit on which reconciliation operates.")

# ============================== 5. TESS vs VM =================================
doc.add_heading("5. Tesseract readings vs vision-model readings", level=1)
para("To make the division of labour concrete, the pre-processed Station 53 block "
     "(Figure S2) was read with Tesseract under the exact settings of Table S2, and its "
     "output is set beside the delivered vision-model values. Two characteristic failure "
     "modes appear, both of which the reconciliation check detects.", after=8)

doc.add_heading("5.1  Row collapse", level=2)
para("Because the register’s row pitch is tight and the ink is faint, Tesseract’s "
     "line grouping merged adjacent years: on this block it returned only 8 line-clusters "
     "for ~23 data rows, with several years mashed into one cluster and others fragmented. "
     "Leading-token year matching therefore collapses — which is why rows are aligned by "
     "reading order, and why a structural reader alone cannot safely segment this source. "
     "The vision model, prompted with the explicit row schema, recovers all rows cleanly.", after=8)

doc.add_heading("5.2  Cell-level comparison (worked example: 1933 row)", level=2)
para("The 1933 data row is one Tesseract cluster that aligns almost one-to-one with the "
     "delivered row, so it isolates the per-cell error cleanly. Values that differ are "
     "shaded.", after=6)

months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Annual"]
tess  = ["11.96","6.09","22.33","687","9.30","602","7.95","1090","641","12.44","—(dropped)","10.02",""]
vm    = ["11.96","6.09","22.33","6.87","9.3","6.02","7.95","10.9","6.41","12.44","13.11","10.02","123.40"]
note  = ["✓","✓","✓","decimal dropped","✓","decimal dropped","✓","decimal dropped","decimal dropped","✓","cell missed","✓","(annual not in cluster)"]

tbl = doc.add_table(rows=1, cols=4); tbl.style="Table Grid"; tbl.alignment=WD_TABLE_ALIGNMENT.CENTER
hdr = tbl.rows[0].cells
for i,h in enumerate(["Column","Tesseract (raw)","Vision model (delivered)","Issue"]):
    set_cell(hdr[i], h, bold=True, size=9, color=RGBColor(0xFF,0xFF,0xFF)); shade_cell(hdr[i],"1F4E79")
for m,tv,vv,nt in zip(months,tess,vm,note):
    cells = tbl.add_row().cells
    set_cell(cells[0],m,bold=True,size=9)
    set_cell(cells[1],tv,mono=True,size=9); set_cell(cells[2],vv,mono=True,size=9)
    set_cell(cells[3],nt,size=8.5, color=(RGBColor(0xB0,0x30,0x00) if nt!="✓" else GREY))
    if nt!="✓":
        shade_cell(cells[1],"FDE8E4")
caption("Table S3. Station 53, 1933 row. Tesseract reads the digits but repeatedly drops "
        "the decimal point on two-decimal values (6.87→“687”, 6.02→“602”, 10.9→“1090”, "
        "6.41→“641”) and misses one cell entirely (Nov 13.11). The raw months then sum to "
        "far more than any plausible annual, so the row fails reconciliation and is "
        "escalated; the vision model re-reads it and the twelve months reconcile to the "
        "printed annual 123.40 (ok_reconciled).")

para("The pattern generalises across the block: Tesseract recovers clean integers and "
     "many whole cells correctly (11.96, 22.33, 12.44, and the printed annual 103.56 on "
     "the row above all match exactly), but drops decimals and collapses rows often enough "
     "that its unescalated output would not reconcile. This is the empirical basis for the "
     "Tesseract-first, reconciliation-gated, vision-model-on-failure design: the cheap "
     "reader handles the easy cells, arithmetic flags the misreads, and the expensive "
     "reader is spent only where it earns its cost.", after=8)

# ============================== 6. ACCURACY NOTE ==============================
doc.add_heading("6. A note on accuracy metrics", level=1)
para("Character/word error rate and Levenshtein distance require an independent, "
     "hand-keyed gold standard for the same cells, which does not exist for this source; "
     "computing them against the pipeline’s own output would measure nothing. The "
     "defensible intrinsic accuracy measure is instead the reconciliation rate — the "
     "fraction of full-year rows whose twelve transcribed months sum to the independently "
     "printed annual within tolerance. Across the delivered dataset this stands at 96.4%, "
     "with the remainder explicitly flagged (annual_discrepancy, partial_year, or "
     "column-cascade) rather than silently accepted.", after=8)

doc.save(OUT)
print("saved", OUT)
import os; print("size MB", round(os.path.getsize(OUT)/1e6,2))
