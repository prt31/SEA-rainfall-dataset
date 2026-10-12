#!/usr/bin/env python3
"""
================================================================================
 Johor Rainfall Register — COMBINED detect-and-read pipeline
================================================================================
Two validation gates, one for each half of the problem:

  DETECTION  (finding/bounding a station block)   -> STRUCTURAL checks
  READING    (transcribing the numbers)           -> ARITHMETIC reconciliation

There is no printed total to validate a bounding box, so detection is gated by
self-consistency of the table's SHAPE instead: exactly 14 columns, regular row
pitch, a monotonic year column, a header on top, a summary/next-header sentinel
at the bottom. Only once a block passes those does its grid get read, and only
then does the annual-sum reconciliation apply.

Flow:
  propose blocks (vision model, or Tesseract header scan)
     -> for each: crop -> STRUCTURAL validate -> (repair/escalate if fail)
        -> read grid -> ARITHMETIC reconcile -> tag -> CSV

Run offline demo (no API key needed):
    python3 johor_detect_and_read.py --mock
Run for real:
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 johor_detect_and_read.py page01.jpg page02.jpg ...
================================================================================
"""

import os, sys, io, json, base64, re
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
from PIL import Image, ImageOps

try:
    import pytesseract
    HAVE_TESS = True
except Exception:
    HAVE_TESS = False

MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
VISION_MODEL = "claude-sonnet-4-6"
TEMPERATURE, TOP_P = 0, 1
COLUMN_X = {"left": (0.07, 0.53), "right": (0.50, 0.995)}
EXPECTED_COLS = 14                      # year + 12 months + annual


# ==============================================================================
#  PREPROCESS
# ==============================================================================
def preprocess(img, x1f, y1f, x2f, y2f, scale=3, cutoff=0.35):
    w, h = img.size
    c = img.crop((int(w*x1f), int(h*y1f), int(w*x2f), int(h*y2f)))
    c = c.resize((c.width*scale, c.height*scale), Image.LANCZOS)
    return ImageOps.autocontrast(c.convert("L"), cutoff=cutoff), c.convert("RGB")


# ==============================================================================
#  DETECTION-STAGE VALIDATION  (structural, no arithmetic available)
# ==============================================================================
@dataclass
class StructReport:
    ok: bool
    n_cols: int
    n_rows: int
    years: list
    year_monotonic: bool
    row_pitch_cv: float          # coefficient of variation of row spacing
    has_header: bool
    has_sentinel: bool
    violations: list = field(default_factory=list)


def _tess_tokens(gray):
    """Return numeric tokens [(x,y,w,h,text,conf)] and all words."""
    data = pytesseract.image_to_data(
        gray, config="--psm 6 -c preserve_interword_spaces=1",
        output_type=pytesseract.Output.DICT)
    num, words = [], []
    for i in range(len(data["text"])):
        t = data["text"][i].strip()
        if not t: continue
        conf = float(data["conf"][i]) if data["conf"][i] not in ("-1","") else -1
        box = (data["left"][i], data["top"][i], data["width"][i],
               data["height"][i], t, conf)
        words.append(box)
        if re.fullmatch(r"[0-9]{1,4}\.?[0-9]{0,2}", t) and conf > 30:
            num.append(box)
    return num, words


def _cluster_1d(vals, gap):
    vals = sorted(vals); groups=[[vals[0]]]
    for v in vals[1:]:
        (groups[-1] if v-groups[-1][-1] <= gap else groups.append([v]) or groups[-1]).append(v) \
            if False else None
        if v - groups[-1][-1] <= gap: groups[-1].append(v)
        else: groups.append([v])
    return [float(np.mean(g)) for g in groups]


def validate_block(gray, words, num):
    """Run the five structural checks on a candidate block crop.
    Returns a StructReport; .ok is the detection gate."""
    viol = []
    if not num:
        return StructReport(False,0,0,[],False,9.9,False,False,["no numeric tokens found"])

    # rows: cluster by y-centre
    centres = sorted([(b[1]+b[3]/2, b) for b in num], key=lambda x:x[0])
    rows=[]; cur=[]; last=None
    for cy,b in centres:
        if last is None or cy-last <= b[3]*0.7: cur.append((cy,b))
        else: rows.append(cur); cur=[(cy,b)]
        last=cy
    if cur: rows.append(cur)
    row_centres=[np.mean([c for c,_ in r]) for r in rows]

    # Check 2 — row pitch regularity (coefficient of variation of gaps)
    pitches=np.diff(row_centres) if len(row_centres)>1 else np.array([1.0])
    cv = float(np.std(pitches)/np.mean(pitches)) if np.mean(pitches)>0 else 9.9
    if cv > 0.6: viol.append(f"irregular row pitch (cv={cv:.2f})")

    # Check 1 — column count from x-centre clustering
    cols=_cluster_1d([b[0]+b[2]/2 for b in num], gap=42)
    n_cols=len(cols)
    if n_cols != EXPECTED_COLS:
        viol.append(f"expected {EXPECTED_COLS} columns, found {n_cols}")

    # Check 3 — leftmost column should be a monotonic year sequence.
    # Tesseract often recovers only a few year labels on faded pages, so we
    # require monotonicity of what IS read, and treat "too few to judge" as a
    # soft warning (not a hard fail) — the vision model owns the year column.
    left_x = min(cols)
    year_toks=[]
    for (x,y,w,h,t,c) in num:
        if abs((x+w/2)-left_x) < 45 and re.fullmatch(r"(18|19)\d{2}", t):
            year_toks.append((y, int(t)))
    years=[yr for _,yr in sorted(year_toks)]
    strictly_up = all(years[i] < years[i+1] for i in range(len(years)-1))
    if len(years) >= 3:
        mono = strictly_up
        if not mono: viol.append(f"year column not monotonic: {years[:8]}")
    elif len(years) >= 1:
        mono = strictly_up            # what we have is consistent
        viol.append(f"few year labels legible ({len(years)}) — verify year column")
    else:
        mono = True                   # nothing to contradict; leave to other checks
        viol.append("no year labels legible — verify block bounds")

    # Check 4 — header present on the top line
    top_y = min(b[1] for b in words)
    header_line=" ".join(t for (x,y,w,h,t,c) in sorted(words,key=lambda b:b[0])
                         if y < top_y + 40)
    has_header = bool(re.search(r"stat\w*\s*no", header_line, re.I))
    if not has_header: viol.append("no 'Station No.' header on top line")

    # Check 5 — summary sentinel (MEAN / MAX) somewhere in the block
    alltext=" ".join(t for *_,t,_ in [(b[0],b[1],b[2],b[3],b[4],b[5]) for b in words]).lower()
    has_sentinel = ("mean" in alltext) or ("max" in alltext) or ("hrs" in alltext)

    # Gate: hard structural failures are wrong column count, a POSITIVE year
    # non-monotonicity, irregular row pitch, or a missing header. Sparse-year
    # warnings do not fail the gate (they route the year column to the model).
    year_hard_fail = (len(years) >= 3 and not strictly_up)
    ok = (n_cols==EXPECTED_COLS) and (not year_hard_fail) and (cv<=0.6) and has_header
    return StructReport(ok, n_cols, len(rows), years, mono, cv,
                        has_header, has_sentinel, viol)


# ==============================================================================
#  DETECTION — propose candidate blocks
# ==============================================================================
FIND_PROMPT = """\
This is one full page of a colonial-era Malaysian rainfall register (two columns).
List every station block in reading order. For each: station_no (int or null for a
headerless continuation), station_name (or null), column ("left"/"right"), y_start
and y_end as fractions of page height, continues_from_prev (bool),
continues_next_page (bool). Return ONLY JSON: {"blocks":[...]}. No prose."""


def propose_blocks(page_img, mock=False, _pid=None):
    """Vision model proposes header positions (robust). Mock returns a stub."""
    if mock:
        return _mock_find(_pid)
    from anthropic import Anthropic
    client=Anthropic()
    buf=io.BytesIO(); page_img.save(buf,format="PNG")
    b64=base64.standard_b64encode(buf.getvalue()).decode()
    r=client.messages.create(model=VISION_MODEL,max_tokens=1500,
        temperature=TEMPERATURE,top_p=TOP_P,
        messages=[{"role":"user","content":[
            {"type":"image","source":{"type":"base64","media_type":"image/png","data":b64}},
            {"type":"text","text":FIND_PROMPT}]}])
    txt="".join(b.text for b in r.content if getattr(b,"type","")=="text")
    txt=txt[txt.find("{"):txt.rfind("}")+1]
    return json.loads(txt).get("blocks",[])


# ==============================================================================
#  READING — transcribe a validated block
# ==============================================================================
READ_PROMPT = """\
This image is one station block from a rainfall register (station: {station}).
Each data row: 4-digit YEAR, twelve monthly values (Jan..Dec, inches, 2 dp), then
printed ANNUAL. Blank cells (dashes) -> null. Summary rows labelled MEAN/MAX get
year null and row_type MEAN/MAX24HR/MAX48HR/MAX72HR; ordinary years row_type DATA.
Read digits EXACTLY as printed; never adjust to make a row sum. Illegible cell ->
null. Return ONLY JSON: {{"rows":[{{"row_type":"DATA","year":1931,
"months":[...12...],"annual":118.93}}]}}"""


def read_block(crop_gray, station, mock=False, _pid=None, _blk=None):
    if mock:
        return _mock_read(_pid, _blk)
    from anthropic import Anthropic
    client=Anthropic()
    buf=io.BytesIO(); crop_gray.convert("RGB").save(buf,format="PNG")
    b64=base64.standard_b64encode(buf.getvalue()).decode()
    r=client.messages.create(model=VISION_MODEL,max_tokens=3000,
        temperature=TEMPERATURE,top_p=TOP_P,
        messages=[{"role":"user","content":[
            {"type":"image","source":{"type":"base64","media_type":"image/png","data":b64}},
            {"type":"text","text":READ_PROMPT.format(station=station or "continuation")}]}])
    txt="".join(b.text for b in r.content if getattr(b,"type","")=="text")
    txt=txt[txt.find("{"):txt.rfind("}")+1]
    return json.loads(txt).get("rows",[])


# ==============================================================================
#  READING-STAGE VALIDATION  (arithmetic reconciliation)
# ==============================================================================
def reconcile_and_tag(rec):
    months=(list(rec.get("months",[]))+[None]*12)[:12]
    annual=rec.get("annual"); rt=rec.get("row_type","DATA")
    present=[m for m in months if m is not None]
    computed=round(sum(present),2) if present else None
    if len(present)<12:
        return months, computed, "partial_year"
    if annual is None:
        return months, computed, "no_annual"
    d=abs(computed-annual)
    if d<=0.10: tag="ok_reconciled"
    elif d<=0.50: tag="ok_rounding"
    else:
        # unique single-cell fix?
        base=sum(months); cands=[]
        for i,v in enumerate(months):
            need=round(annual-(base-v),2)
            if need>=0 and 0.01<abs(need-v)<=25: cands.append((i,v,need))
        if len(cands)==1:
            i,old,new=cands[0]; months[i]=new
            tag=f"ocr_corrected:{MONTHS[i]}_{old}->{new}"; computed=round(sum(months),2)
        else:
            tag=f"annual_discrepancy:computed={computed}_printed={annual}_unresolved"
    if rt!="DATA" and tag=="ok_reconciled":
        tag="source_printed_mean" if rt=="MEAN" else "source_printed"
    return months, computed, tag


def _is_accepted(tag):
    """Reading tags that count as reconciled/accepted (no escalation needed)."""
    return tag.startswith(("ok_reconciled", "ok_rounding", "source_printed"))


# ==============================================================================
#  TESSERACT ROW READER  (cheap first pass for the escalation ladder)
# ==============================================================================
def tesseract_read_rows(crop_gray):
    """Read a station block with Tesseract into row dicts, cheaply.
    Uses positioned tokens: leftmost column = year, next 12 = months, last = annual.
    Returns a list of {row_type, year, months[12], annual} — best-effort; cells it
    can't read become None (which reconciliation will then catch)."""
    if not HAVE_TESS:
        return []
    num, words = _tess_tokens(crop_gray)
    if not num:
        return []
    # cluster into rows by y
    centres=sorted([(b[1]+b[3]/2,b) for b in num],key=lambda x:x[0])
    rows=[]; cur=[]; last=None
    for cy,b in centres:
        if last is None or cy-last<=b[3]*0.7: cur.append(b)
        else: rows.append(cur); cur=[b]
        last=cy
    if cur: rows.append(cur)
    # column centres
    cols=_cluster_1d([b[0]+b[2]/2 for b in num], gap=42)
    def to_num(t):
        t=t.replace("$","5").replace("S","5").replace("B","8").replace("O","0")
        if "." not in t and t.isdigit() and len(t) in (3,4):   # dropped-decimal repair
            t=t[:-2]+"."+t[-2:]
        try: return round(float(t),2)
        except: return None
    out=[]
    for r in rows:
        # assign each token to nearest column
        slots=[None]*len(cols)
        for (x,y,w,h,t,c) in r:
            ci=min(range(len(cols)), key=lambda i:abs((x+w/2)-cols[i]))
            slots[ci]=t
        yr=None
        if slots and slots[0] and re.fullmatch(r"(18|19)\d{2}", slots[0]):
            yr=int(slots[0])
        # months = columns 1..12, annual = last column (14-col layout)
        month_slots = slots[1:13] if len(slots)>=13 else slots[1:]
        months=[to_num(s) if s else None for s in month_slots]
        months=(months+[None]*12)[:12]
        annual = to_num(slots[-1]) if len(slots)>=14 and slots[-1] else None
        out.append({"row_type":"DATA","year":yr,"months":months,"annual":annual})
    return out


# ==============================================================================
#  ESCALATION LADDER  (Tesseract -> reconcile -> vision model -> reconcile -> flag)
# ==============================================================================
def read_row_escalating(tess_rec, crop_gray, station, blk, mock=False, _pid=None,
                         stats=None):
    """Implements the 5-step ladder for ONE row:
      1. Tesseract read (already done -> tess_rec)
      2. reconcile vs printed annual
      3. reconciles  -> accept Tesseract's read              (engine=tesseract)
      4. fails       -> escalate this row to the vision model, re-read, reconcile
      5. still fails -> flag it
    Returns (months, computed, confidence_tag, engine)."""
    # steps 1-2
    months, computed, tag = reconcile_and_tag(tess_rec)
    # step 3: accept if Tesseract already reconciles (or it's a partial we can't judge)
    if _is_accepted(tag):
        if stats is not None: stats["tesseract"] += 1
        return months, computed, tag, "tesseract"
    if tag.startswith("ocr_corrected"):
        # a unique single-cell fix already reconciled it — count as Tesseract+fix
        if stats is not None: stats["tesseract_fixed"] += 1
        return months, computed, tag + ";engine=tesseract", "tesseract"

    # step 4: escalate this single row to the vision model
    vrows = read_row_vision(crop_gray, tess_rec.get("year"), station, blk,
                            mock=mock, _pid=_pid)
    if vrows:
        vmonths, vcomputed, vtag = reconcile_and_tag(vrows[0])
        if _is_accepted(vtag) or vtag.startswith("ocr_corrected"):
            if stats is not None: stats["vision"] += 1
            return vmonths, vcomputed, vtag + ";engine=vision", "vision"
        # step 5: still fails after vision model
        if stats is not None: stats["flagged"] += 1
        return vmonths, vcomputed, vtag + ";engine=vision", "vision"

    # vision unavailable/empty -> keep Tesseract's flagged read
    if stats is not None: stats["flagged"] += 1
    return months, computed, tag + ";engine=tesseract", "tesseract"


def read_row_vision(crop_gray, year, station, blk, mock=False, _pid=None):
    """Re-read one row with the vision model. In mock mode, return the true value
    for the escalated row so the ladder can be demonstrated offline."""
    if mock:
        return _mock_read_one(_pid, blk, year)
    # For a real run we re-read the whole block once and cache would be added in
    # production; here we call the block reader and pick the matching year.
    allrows = read_block(crop_gray, station, mock=False, _blk=blk)
    for r in allrows:
        if r.get("year") == year:
            return [r]
    return allrows[:1] if allrows else []


# ==============================================================================
#  ORCHESTRATION — combined detect-then-read
# ==============================================================================
def crop_from_block(page, blk, scale=3):
    x1f,x2f=COLUMN_X.get(blk.get("column","left"),COLUMN_X["left"])
    head=0.0 if blk.get("continues_from_prev") else 0.006
    y1=max(0,blk["y_start"]-0.006+head); y2=min(1,blk["y_end"]+0.010)
    return preprocess(page,x1f,y1,x2f,y2)

def widen_right(blk, step=0.02):
    x1f,x2f=COLUMN_X.get(blk.get("column","left"))
    COLUMN_X[blk.get("column","left")]=(x1f, min(0.999, x2f+step))


# ==============================================================================
#  STITCHING  (join a station whose rows run across a page break)
# ==============================================================================
@dataclass
class StitchBlock:
    """One block already read + reconciled, carrying the flags the stitcher needs.
    `rows` are CSV-ready dicts: {row_type, year, months, annual, computed, conf}."""
    station_no: Optional[int]
    station_name: Optional[str]
    rows: list
    from_prev: bool = False
    to_next: bool = False
    detect_status: str = ""
    pages: list = field(default_factory=list)
    note: str = ""


def stitch_step(pending, blk):
    """Fold one freshly-read block into the running state.
    Returns (new_pending, [completed_blocks]). Identical logic to the standalone
    stitched pipeline, so a station split across 2+ pages becomes ONE record."""
    completed = []
    if pending is not None:
        if blk.from_prev:                      # continuation of the held station
            pending.rows.extend(blk.rows)
            pending.pages.extend(blk.pages)
            pending.to_next = blk.to_next
            if blk.to_next:
                return pending, completed       # still open (spans 3+ pages)
            return None, [pending]              # now complete
        else:                                   # expected continuation never came
            pending.note = "closed_without_continuation"
            completed.append(pending); pending = None
    if blk.from_prev:                           # continuation with no parent
        blk.note = "orphan_continuation_no_parent"
        completed.append(blk); return None, completed
    if blk.to_next:
        return blk, completed                   # hold for next page
    completed.append(blk); return None, completed


def reading_order(blocks):
    """Left column (top→bottom) before right column (top→bottom)."""
    return sorted(blocks, key=lambda b: (0 if b.get("column")=="left" else 1,
                                         b.get("y_start", 0.0)))


CSV_COLS=(["station_no","station_name","row_type","year"]+MONTHS+
          ["annual","computed","data_confidence","detect_status","source_pages"])

def _write_station(w, st):
    """Write one completed (possibly stitched) station's rows to the CSV.
    source_pages records provenance; a stitch note is appended to each tag."""
    pages="+".join(dict.fromkeys(st.pages))      # unique, order-preserving
    for r in st.rows:
        conf=r["conf"]+((";"+st.note) if st.note else "")
        vals=["" if m is None else m for m in r["months"]]
        w.writerow([st.station_no, st.station_name, r["row_type"],
                    r["year"] or "", *vals,
                    r["annual"] if r["annual"] is not None else "",
                    r["computed"] if r["computed"] is not None else "",
                    conf, st.detect_status, pages])

def run(image_paths, out_csv, mock=False):
    import csv, datetime
    fout=open(out_csv,"w",newline=""); w=csv.writer(fout)
    fout.write(f"# detect: structural(cols={EXPECTED_COLS},monotonic-years,header,"
               f"row-pitch); read: reconcile-vs-annual; model={VISION_MODEL} "
               f"temp={TEMPERATURE}\n")
    w.writerow(CSV_COLS)
    tot_read=tot_flag=tot_detect_fail=0
    engine_stats={"tesseract":0,"tesseract_fixed":0,"vision":0,"flagged":0}
    stitch_stats={"merged":0,"orphan":0,"unclosed":0}
    pending=None                                # held-over block awaiting continuation

    for pi,path in enumerate(image_paths):
        page=None if mock else Image.open(path)
        pid=pi if mock else None
        pname=f"[mock page {pi+1}]" if mock else os.path.basename(path)
        print("="*72); print(f" PAGE {pi+1}: {pname}"); print("="*72)

        blocks=reading_order(propose_blocks(page,mock,_pid=pid))
        for bi,blk in enumerate(blocks):
            name=blk.get("station_name")
            sid=blk.get("station_no")
            # ---- DETECTION gate: crop, structurally validate, repair once ----
            if mock:
                rep=_mock_struct(pid,blk)   # simulated structural report
                gray=None
            else:
                gray,_=crop_from_block(page,blk)
                num,words=_tess_tokens(gray) if HAVE_TESS else ([],[])
                rep=validate_block(gray,words,num)
                if not rep.ok and "found 13" in " ".join(rep.violations):
                    widen_right(blk); gray,_=crop_from_block(page,blk)
                    num,words=_tess_tokens(gray); rep=validate_block(gray,words,num)

            status = "detect_ok" if rep.ok else "detect_flagged:"+";".join(rep.violations)
            tag=f"#{sid} {name}" if sid else "«continuation»"
            print(f"  {tag:<34} cols={rep.n_cols} rows={rep.n_rows} "
                  f"years_monotonic={rep.year_monotonic} -> "
                  f"{'PASS' if rep.ok else 'FLAG'}")
            if not rep.ok:
                tot_detect_fail+=1
                for v in rep.violations: print(f"        · {v}")

            # ---- READING gate: Tesseract-first escalation ladder ----
            # 1. Tesseract reads each row (cheap).  2. reconcile.  3. accept if OK.
            # 4. escalate failures to the vision model.  5. flag if still failing.
            if mock:
                tess_rows = _mock_tess_rows(pid, blk)      # simulated cheap read
            else:
                tess_rows = tesseract_read_rows(gray)
                if not tess_rows:                          # no OCR at all -> vision
                    tess_rows = [{"row_type":r.get("row_type","DATA"),
                                  "year":r.get("year"),"months":r.get("months"),
                                  "annual":r.get("annual")}
                                 for r in read_block(gray,name,mock,_pid=pid,_blk=blk)]
            block_rows=[]
            for rec in tess_rows:
                months, computed, conf, engine = read_row_escalating(
                    rec, gray, name, blk, mock=mock, _pid=pid, stats=engine_stats)
                if conf.startswith("annual_discrepancy"): tot_flag+=1
                else: tot_read+=1
                block_rows.append({"row_type":rec.get("row_type","DATA"),
                    "year":rec.get("year"),"months":months,
                    "annual":rec.get("annual"),"computed":computed,"conf":conf})

            # ---- STITCH gate: hold a page-spanning block, merge its continuation
            sb=StitchBlock(station_no=sid, station_name=name, rows=block_rows,
                           from_prev=bool(blk.get("continues_from_prev")),
                           to_next=bool(blk.get("continues_next_page")),
                           detect_status=status, pages=[pname])
            pending, done = stitch_step(pending, sb)
            for st in done:
                if len(dict.fromkeys(st.pages))>1: stitch_stats["merged"]+=1
                if st.note=="orphan_continuation_no_parent": stitch_stats["orphan"]+=1
                if st.note=="closed_without_continuation": stitch_stats["unclosed"]+=1
                _write_station(w, st)
            if sb.to_next and pending is sb:
                print(f"        … held for stitching (continues on next page)")

    if pending is not None:                      # flush a station open at input end
        pending.note = pending.note or "open_at_end_of_input"
        stitch_stats["unclosed"]+=1
        _write_station(w, pending)
    fout.close()
    print("\n"+"="*72)
    print(f" DETECT: {tot_detect_fail} block(s) flagged by structural checks")
    print(f" READ (escalation ladder):")
    print(f"   • {engine_stats['tesseract']} rows accepted from Tesseract "
          f"(reconciled on first read)")
    print(f"   • {engine_stats['tesseract_fixed']} rows fixed by unique single-cell "
          f"correction (Tesseract)")
    print(f"   • {engine_stats['vision']} rows escalated to the vision model "
          f"(Tesseract failed to reconcile)")
    print(f"   • {engine_stats['flagged']} rows still flagged after escalation")
    print(f" STITCH:")
    print(f"   • {stitch_stats['merged']} station(s) merged across a page break")
    print(f"   • {stitch_stats['orphan']} orphan continuation(s) (no parent)")
    print(f"   • {stitch_stats['unclosed']} station(s) closed without expected continuation")
    print(f" -> {out_csv}")


# ==============================================================================
#  MOCKS
# ==============================================================================
def _mock_find(pid):
    # Real-world invariant: only the LAST block in reading order on a page can
    # continue to the next page. So Station 54 is the bottom-right block of page 1.
    if pid==0:   # page 1: Station 53 complete (left); Station 54 runs off page (right)
        return [
            {"station_no":53,"station_name":"Mount Austin Estate","column":"left",
             "y_start":0.15,"y_end":0.80,"continues_from_prev":False,"continues_next_page":False},
            {"station_no":54,"station_name":"Skudai Estate","column":"right",
             "y_start":0.15,"y_end":0.95,"continues_from_prev":False,"continues_next_page":True},
        ]
    # page 2: headerless continuation of Station 54 (top-left), then new Station 55
    return [
        {"station_no":None,"station_name":None,"column":"left",
         "y_start":0.12,"y_end":0.40,"continues_from_prev":True,"continues_next_page":False},
        {"station_no":55,"station_name":"Tebrau Estate","column":"left",
         "y_start":0.45,"y_end":0.80,"continues_from_prev":False,"continues_next_page":False},
    ]

def _mock_struct(pid, blk):
    # All blocks pass detection cleanly so the demo focuses on the STITCH stage.
    # A headerless continuation legitimately has no 'Station No.' header, so its
    # report reflects that without being treated as a hard fail here.
    if blk.get("continues_from_prev"):
        return StructReport(True,14,3,[1950],True,0.2,False,True,
                            ["headerless continuation (expected)"])
    return StructReport(True,14,20,[1948,1949,1950],True,0.2,True,True,[])

def _mock_read(pid, blk):
    if blk.get("station_no")==53:
        return [
            {"row_type":"DATA","year":1931,
             "months":[13.51,2.46,11.32,16.36,4.54,12.68,8.79,10.92,7.35,4.67,13.35,12.98],
             "annual":118.93},
            {"row_type":"DATA","year":1935,   # Jan corrupted -> reconcile fixes it
             "months":[24.35,8.31,10.53,9.90,6.89,6.93,4.17,11.22,3.51,8.75,13.11,14.33],
             "annual":102.00},
            {"row_type":"MEAN","year":None,
             "months":[11.81,7.63,12.75,11.39,8.97,7.23,6.60,9.63,7.17,10.25,10.70,12.53],
             "annual":116.66},
        ]
    return [
        {"row_type":"DATA","year":1948,
         "months":[10.0,5.0,8.0,9.0,7.0,6.0,5.0,8.0,9.0,10.0,11.0,7.0],"annual":95.0},
    ]


def _mock_tess_rows(pid, blk):
    """Simulated CHEAP Tesseract pass. Row 1931 is read cleanly (will reconcile
    -> accepted from Tesseract). Row 1933 has a dropped-decimal error that does
    NOT reconcile and is not uniquely fixable -> forces escalation to vision."""
    if blk.get("station_no")==53:
        return [
            {"row_type":"DATA","year":1931,   # clean read, reconciles
             "months":[13.51,2.46,11.32,16.36,4.54,12.68,8.79,10.92,7.35,4.67,13.35,12.98],
             "annual":118.93},
            {"row_type":"DATA","year":1933,   # Tesseract garbled two cells -> fails
             "months":[1196,6.09,2233,6.87,9.30,6.02,7.95,10.90,6.41,12.44,13.11,10.02],
             "annual":123.40},
            {"row_type":"MEAN","year":None,
             "months":[11.81,7.63,12.75,11.39,8.97,7.23,6.60,9.63,7.17,10.25,10.70,12.53],
             "annual":116.66},
        ]
    # Station 54 FIRST half (page 1): early years, no MEAN yet
    if blk.get("station_no")==54:
        return [
            {"row_type":"DATA","year":1948,
             "months":[10.0,5.0,8.0,9.0,7.0,6.0,5.0,8.0,9.0,10.0,11.0,7.0],"annual":95.0},
            {"row_type":"DATA","year":1949,
             "months":[9.0,6.0,8.0,8.0,7.0,7.0,6.0,8.0,9.0,9.0,10.0,8.0],"annual":95.0},
        ]
    # Station 54 SECOND half (page 2, headerless continuation): later years + MEAN
    if blk.get("continues_from_prev"):
        return [
            {"row_type":"DATA","year":1950,
             "months":[11.0,5.0,7.0,9.0,8.0,6.0,5.0,8.0,8.0,10.0,11.0,7.0],"annual":95.0},
            {"row_type":"MEAN","year":None,
             "months":[10.0,5.33,7.67,8.67,7.33,6.33,5.33,8.0,8.67,9.67,10.67,7.33],"annual":95.0},
        ]
    # Station 55 (page 2, complete)
    if blk.get("station_no")==55:
        return [
            {"row_type":"DATA","year":1952,
             "months":[8.0,6.0,9.0,8.0,7.0,7.0,6.0,8.0,9.0,10.0,9.0,8.0],"annual":95.0},
        ]
    return []


def _mock_read_one(pid, blk, year):
    """Vision model's clean re-read of a single escalated row."""
    if blk.get("station_no")==53 and year==1933:
        return [{"row_type":"DATA","year":1933,
                 "months":[11.96,6.09,22.33,6.87,9.30,6.02,7.95,10.90,6.41,12.44,13.11,10.02],
                 "annual":123.40}]
    return []


if __name__=="__main__":
    argv=sys.argv[1:]; mock="--mock" in argv
    paths=[a for a in argv if not a.startswith("--")]
    if mock:
        run(["page01.jpg","page02.jpg"], "/tmp/detect_and_read.csv", mock=True)
    else:
        if not paths or not os.environ.get("ANTHROPIC_API_KEY"):
            print("usage: ANTHROPIC_API_KEY=... python3 johor_detect_and_read.py page1.jpg ...")
            print("   or: python3 johor_detect_and_read.py --mock"); sys.exit(1)
        run(paths, "johor_detect_and_read.csv", mock=False)
