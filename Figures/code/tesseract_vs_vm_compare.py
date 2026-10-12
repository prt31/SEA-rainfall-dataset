#!/usr/bin/env python3
"""Tesseract-vs-VM cell comparison for Station 53 (Mount Austin Estate).

Aligns by ROW ORDER (not by year token), the fix for the year-label offset
defect that collapsed the earlier year-token matcher. We take the DATA rows
in reading order and line them up with the verified CSV DATA rows in the same
order, then compare cell by cell.
"""
import re, io, csv, json, sys
import numpy as np
from PIL import Image, ImageOps
import pytesseract

IMG = "/root/.claude/uploads/22db5fb9-bd74-5590-a634-2ea29604a7f1/9cff78d3-Image00029.jpg"
CSV = "/home/claude/my-sg-su-rainfall-dataset/data/johor_rainfall_1926-1958.csv"
# Station 53 right-column block crop (fractions), same as pipeline
X1, Y1, X2, Y2 = 0.505, 0.383, 0.95, 0.585
SCALE, CUTOFF = 3, 0.35

def preprocess(path):
    img = Image.open(path)
    w, h = img.size
    c = img.crop((int(w*X1), int(h*Y1), int(w*X2), int(h*Y2)))
    c = c.resize((c.width*SCALE, c.height*SCALE), Image.LANCZOS)
    return ImageOps.autocontrast(c.convert("L"), cutoff=CUTOFF)

def tess_tokens(gray):
    data = pytesseract.image_to_data(
        gray, config="--psm 6 -c preserve_interword_spaces=1",
        output_type=pytesseract.Output.DICT)
    toks = []
    for i in range(len(data["text"])):
        t = data["text"][i].strip()
        if not t: continue
        conf = float(data["conf"][i]) if data["conf"][i] not in ("-1","") else -1
        if re.fullmatch(r"[0-9]{1,4}\.?[0-9]{0,2}", t) and conf > 20:
            toks.append((data["left"][i], data["top"][i], data["width"][i],
                         data["height"][i], t, conf))
    return toks

def cluster_rows(toks):
    if not toks: return []
    toks = sorted(toks, key=lambda b: b[1]+b[3]/2)
    rows, cur, last = [], [], None
    for b in toks:
        cy = b[1]+b[3]/2
        if last is None or cy-last <= b[3]*0.7:
            cur.append(b)
        else:
            rows.append(cur); cur=[b]
        last = cy
    if cur: rows.append(cur)
    return rows

def assign_cols(row):
    """14 columns: year + 12 months + annual, by x-position within the row."""
    row = sorted(row, key=lambda b: b[0])
    return [b[4] for b in row]  # just the raw tokens left-to-right

def load_vm():
    rows = []
    with open(CSV) as f:
        for r in csv.DictReader(f):
            if r["station_no"]=="53" and r["row_type"]=="DATA":
                months = [r[m] for m in ["Jan","Feb","Mar","Apr","May","Jun",
                                         "Jul","Aug","Sep","Oct","Nov","Dec"]]
                rows.append((r["year"], months, r["annual"]))
    return rows

gray = preprocess(IMG)
gray.save("/tmp/claude-0/-home-claude-my-sg-su-rainfall-dataset/22db5fb9-bd74-5590-a634-2ea29604a7f1/scratchpad/s53_block.png")
toks = tess_tokens(gray)
rows = cluster_rows(toks)
print(f"Tesseract: {len(toks)} numeric tokens, {len(rows)} rows clustered")
for i, r in enumerate(rows):
    print(f"  row{i:2d}: {assign_cols(r)}")

print("\n=== VM verified DATA rows ===")
vm = load_vm()
for yr, months, ann in vm:
    print(f"  {yr}: {months} | {ann}")
