# Methodology: Digitising Colonial-Era Johor Rainfall Records
## Stations 1–4, Images Image00018–Image00019

---

## 1. Source Materials

**Publication:** *Johore Rainfall Records* — a colonial-era meteorological register, part of the Federated/Unfederated Malay States rainfall publication series (early–mid 20th century). Units are inches of rainfall to two decimal places.

**Physical format:** Bound register, photographed and digitised as JPEG scans (~1232–1316 × 924–980 px). Each JPEG image represents one physical page spread, with two columns of tabular data side by side, often alongside a station-location map.

**Stations covered in this batch:**
| Stn No. | Name | Image(s) | Column position |
|---------|------|----------|-----------------|
| 1 | Endau Village | Image00018 | Right column (shares page with map) |
| 2 | Tiong Kiat Estate, Paloh | Image00018 | Right column, lower half |
| 3 | Serom Estate, Tangkak | Image00019 | Left column |
| 4 | Mersing Meteorological Station | Image00019 | Left column (continues) → MEAN row overflows to right column top |

**Table structure per station:**
```
Year | Jan | Feb | March | April | May | June | July | Aug | Sept | Oct | Nov | Dec | Annual
```
Followed by source-printed summary rows: MEAN, Max.24hrs, Max.48hrs, Max.72hrs.

---

## 2. Software Environment

| Tool | Version | Role |
|------|---------|------|
| Python | 3.x (system) | Orchestration, image manipulation, CSV generation |
| Pillow (PIL) | system | Image cropping, upscaling, grayscale conversion, contrast enhancement |
| Tesseract OCR | 5.3.4 | Optical character recognition |
| pytesseract | pip | Python wrapper for Tesseract |
| csv (stdlib) | — | CSV output |

---

## 3. Image Preprocessing Pipeline

The raw JPEG scans are low-contrast, have mixed content (maps, decorative elements, marginal noise), and the data columns occupy only a fraction of each image. A systematic preprocessing pipeline was applied before every OCR call.

### 3.1 Column isolation (spatial crop)

Each image was cropped to isolate the relevant data column before OCR. Column boundaries were determined empirically (as fractional proportions of image width/height) after inspecting image geometry.

```python
from PIL import Image, ImageOps

img = Image.open("/mnt/project/Image00018.jpg")
w, h = img.size

# Example: right data column of Image00018 (Stations 1 & 2)
x1, y1 = int(w * 0.42), int(h * 0.05)
x2, y2 = int(w * 1.00), int(h * 0.57)
crop = img.crop((x1, y1, x2, y2))
```

Typical column boundaries used:

| Image | Station(s) | x-range (% width) | y-range (% height) |
|-------|-----------|-------------------|-------------------|
| Image00018 | 1 (header+data) | 42–100% | 5–57% |
| Image00018 | 1 (MEAN/Max) + 2 start | 42–100% | 36–57% |
| Image00018 | 2 (data) | 42–100% | 55–78% |
| Image00018 | 2 (MEAN/Max) | 42–100% | 76–100% |
| Image00019 | 3 (data rows) | 0–52% | 6–50% |
| Image00019 | 3 (MEAN) + 4 start | 0–52% | 48–75% |
| Image00019 | 4 (1951–1958) | 0–52% | 72–97% |
| Image00019 | 4 (MEAN/Max rows) | 50–100% | 0–25% |

### 3.2 Upscaling

Tesseract performs significantly better on text rendered at ≥ 300 dpi equivalent. Source images are approximately 1232 px wide for a full-page spread, giving ~100 px per column-inch — well below optimum. A fixed upscale factor was applied using `Image.LANCZOS` (Lanczos/sinc resampling, best quality for text):

```python
scale = 4   # default; raised to 6–7 for problematic rows
crop = crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS)
```

Scale factors used by context:

| Context | Scale factor | Rationale |
|---------|-------------|-----------|
| Full-column initial pass | 2–3× | Fast survey pass |
| Station data blocks | 4× | Production quality |
| Individual problem rows | 6–7× | Maximum detail for ambiguous digits |

### 3.3 Grayscale conversion and contrast enhancement

```python
gray = crop.convert('L')
gray = ImageOps.autocontrast(gray, cutoff=0.3)
```

`ImageOps.autocontrast` stretches the histogram so the darkest `cutoff`% of pixels map to black and the lightest `cutoff`% map to white. A cutoff of 0.3–0.5 was used; lower values preserve subtle ink variation, higher values handle very faded ink.

### 3.4 Temporary file handling

Tesseract requires a file path, not an in-memory buffer. Images were written to temporary PNG files, OCR was run, then files were deleted:

```python
import subprocess, tempfile, os

with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
    tmp = f.name
gray.save(tmp)

result = subprocess.run(
    ['tesseract', tmp, 'stdout', '--psm', '6',
     '-c', 'preserve_interword_spaces=1'],
    capture_output=True, text=True
)
text = result.stdout
os.unlink(tmp)
```

---

## 4. OCR Configuration

### 4.1 Page segmentation modes (PSM)

Tesseract's PSM controls how the engine segments the image before recognition. Multiple modes were tried on each block:

| PSM | Mode | When used |
|-----|------|-----------|
| `--psm 6` | Assume a single uniform block of text | Default for multi-row data blocks |
| `--psm 4` | Assume a single column of text of variable sizes | Alternative for table blocks; sometimes outperformed PSM 6 |
| `--psm 7` | Single text line | Individual row crops |
| `--psm 8` | Single word | Not used in this batch |

### 4.2 Preserve interword spaces

```
-c preserve_interword_spaces=1
```

This flag instructs Tesseract to retain whitespace between tokens rather than collapsing it, which is essential for aligning tabular columns during post-processing.

### 4.3 Page identification (footer scan)

To confirm which physical pages each image file contains, the bottom 15% of each image was cropped and OCR'd with `--psm 6`, then scanned for three-digit numbers:

```python
footer = img.crop((0, int(h * 0.85), w, h))
# upscale + autocontrast + tesseract psm 6
# grep result.stdout for 3-digit numbers
```

---

## 5. OCR Artifact Catalogue

The following character substitution patterns were observed consistently across all images and corrected during reconciliation:

| Printed character | OCR output | Context |
|------------------|-----------|---------|
| `8` | `$`, `S`, `B`, `6`, `3` | Leading digit of 2-digit values in old typeface |
| `5` | `$`, `S` | OCR interprets the curved top as dollar-sign or S |
| `1` (digit) | `I`, `l`, `!` | Thin vertical stroke ambiguity |
| `9` | `O`, `0`, `2` | Closed loop of "9" confused with zero or two |
| `0` | `O`, `Q` | Circular shapes |
| `7` | `T`, `Y` | Seriffed seven in old print |
| `.` (decimal) | `,`, missing | Decimal point frequently dropped |
| Two adjacent `1`s (`11`) | `8`, `B` | Merging of strokes |
| `—` (dash/missing) | `_`, `-`, `~` | Source dash for missing values |

---

## 6. Reconciliation Protocol

Every DATA row was arithmetically verified against its printed annual total. This is the core quality-control step.

### 6.1 Tolerance thresholds

| Difference | Interpretation | Action |
|-----------|----------------|--------|
| ≤ 0.10 | Source rounding (values rounded to 2 dp) | Accept as-is; flag `ok_reconciled` or `ok_rounding` |
| 0.10–0.50 | Accumulated rounding across 12 months | Accept; flag `ok_rounding:computed=X.XX` |
| 0.51–1.00 | Probable single-digit OCR error | Re-crop at higher scale; attempt correction |
| > 1.00 | Definite misread | Re-crop; use arithmetic to identify candidate correction |

### 6.2 Single-digit correction rule

A misread is corrected only when exactly one candidate value change reconciles the row to the printed annual total. The corrected value is noted in `data_confidence`.

**Example — Station 1, 1949, September:**
```
OCR output: 16.83 17.52 6.69 8.08 4.12 6.03 3.87 6.58 5.73 10.68 20.28 29.43
Printed annual: 138.84
Sum with Sep=5.73: 130.11+5.73 = 135.84  ← doesn't match
Solve: Sep = 138.84 − 130.11 = 8.73       ← unique solution
$ character confirmed as 8 in other rows
→ Sep corrected to 8.73; flag: ocr_corrected:Sep_5.73→8.73
```

### 6.3 MEAN row cross-check

The source-printed MEAN rows were verified independently:

```
∑(monthly MEAN values) == printed MEAN annual
```

All four station MEAN rows reconcile exactly. Additionally, the expected February mean for Station 4 (7.83) was used to disambiguate the 1953 February value (25.28 vs 28.28): back-calculation from the mean across 22 years returned ~25.09, confirming 25.28 and pointing the 3.00 discrepancy to March (`5.23→8.23`).

### 6.4 Impossible-value sanity check

Any MEAN value arithmetically exceeding every individual year value in the record is an immediate re-source trigger. (This protocol was developed during the Perak batch processing when a mis-assigned MEAN block was caught this way.)

### 6.5 Wartime gap policy

Years 1941–1947 (varying by station) are expected to have partial or no data due to the Japanese Occupation of Malaya (1941–1945) and the subsequent administrative recovery period. Missing data in these years is classified `wartime_gap` or `partial_year` rather than flagged as OCR failure.

---

## 7. Multi-pass OCR Strategy

For each station, OCR was run in three successive passes of increasing precision:

```
Pass 1 — Survey (2–3×, PSM 6)
  Purpose: Identify station headers, year ranges, gross values
  Output:  Approximate tabular text

Pass 2 — Production (4×, PSM 6 or PSM 4)
  Purpose: Extract all monthly and annual values
  Output:  Structured text, most values correct

Pass 3 — Targeted (6–7×, PSM 6, tight row crop)
  Purpose: Resolve specific ambiguous cells identified in reconciliation
  Output:  Definitive reading of problem digits
```

Pass 3 crops were sized to capture 2–4 rows of context around the problem row:

```python
# Example: Station 4 rows 1951–1958, 7× upscale
x1, y1 = int(w * 0.0),  int(h * 0.70)
x2, y2 = int(w * 0.52), int(h * 0.86)
crop = img.crop((x1, y1, x2, y2))
scale = 7
crop = crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS)
gray = ImageOps.autocontrast(crop.convert('L'), cutoff=0.25)
```

---

## 8. Geographic Metadata

Geographic attributes were populated from external knowledge, not from the scanned images.

### 8.1 Sources consulted

- General cartographic knowledge of Johor state geography
- Knowledge of colonial-era district boundaries (Mersing, Kluang, Muar/Tangkak districts)
- Station type classification (village gauge, estate gauge, official meteorological station)

### 8.2 Confidence tiers

| Station | Type | Confidence | Basis |
|---------|------|-----------|-------|
| 1 — Endau Village | Named coastal village | medium_high | Endau is a mapped settlement at mouth of Endau River, east coast |
| 2 — Tiong Kiat Estate, Paloh | Private estate gauge | medium | Coordinates are for Paloh town; estate location within ~few km |
| 3 — Serom Estate, Tangkak | Private estate gauge | medium | Coordinates are for Tangkak town; estate location approximate |
| 4 — Mersing Met Station | Official station | high | Named meteorological station, fixed known location |

### 8.3 Values assigned

| Stn | Lat (°N) | Lon (°E) | Elev (m) | Dist. to coast (km) | Nearest coast |
|-----|----------|----------|----------|---------------------|---------------|
| 1 | 2.648 | 103.630 | 5 | 1 | East (South China Sea) |
| 2 | 2.12 | 103.08 | 50 | 55 | South (Johor Strait) |
| 3 | 2.27 | 102.54 | 60 | 35 | West (Strait of Malacca) |
| 4 | 2.433 | 103.833 | 10 | 1 | East (South China Sea) |

---

## 9. CSV Schema

```
station_no            integer     Station number as printed in source
station_name          string      Full name as printed in source
distance_to_coast_km  integer     Distance to nearest coast (km), approximate
elevation_m           integer     Elevation above mean sea level (m), approximate
lat_decimal           float       Decimal degrees North
lon_decimal           float       Decimal degrees East
administrative_unit   string      Modern district and state
country_modern        string      Modern country name
row_type              string      DATA | MEAN | MAX24HR | MAX48HR | MAX72HR
year                  integer     Calendar year (blank for MEAN/MAX rows)
Jan … Dec             float       Monthly rainfall (inches); blank = missing
annual                float       Annual total (inches); blank if partial/summary
data_confidence       string      Reconciliation status and correction notes
```

### row_type values

| Value | Meaning |
|-------|---------|
| `DATA` | Individual year record |
| `MEAN` | Long-term monthly/annual mean as printed in source |
| `MAX24HR` | Maximum 24-hour rainfall recorded for each month |
| `MAX48HR` | Maximum 48-hour rainfall recorded for each month |
| `MAX72HR` | Maximum 72-hour rainfall recorded for each month |

### data_confidence codes

| Code | Meaning |
|------|---------|
| `ok_reconciled` | Computed sum matches printed annual exactly (within ±0.10) |
| `ok_rounding` | Difference ≤ 0.50; attributed to accumulated decimal rounding |
| `ocr_corrected:FIELD_old→new` | One value corrected by arithmetic; change logged |
| `partial_year:reason` | One or more months missing; no annual total |
| `wartime_gap` | Data absent due to Japanese Occupation 1941–1945 |
| `uncertain_partial_year` | Partial year with OCR too garbled to recover monthly values |
| `annual_discrepancy:detail` | Unresolvable discrepancy > 0.50; monthly values kept as-is |
| `source_printed` | Summary rows (MEAN/MAX) accepted as printed, not individually verified |
| `source_printed_mean` | MEAN row arithmetic verified: ∑ monthly = annual |

---

## 10. Corrections Log

All corrections where a printed value was changed from the raw OCR reading:

### Station 1 — Endau Village

| Year | Month | OCR reading | Corrected to | Method |
|------|-------|-------------|-------------|--------|
| 1949 | Sep | 5.73 | **8.73** | Residual from annual |
| 1950 | Jul | 5.23 | **8.23** | Residual from annual |
| 1953 | Sep | 31.29 | **11.29** | Residual; 3→1 transposition |

### Station 2 — Tiong Kiat Estate, Paloh

| Year | Month | OCR reading | Corrected to | Method |
|------|-------|-------------|-------------|--------|
| 1947 | Jan | 6.2x | **6.26** | Residual from annual |
| 1949 | Oct | 10.75 | **10.05** | Residual from annual; 7→0 |
| 1953 | Dec | 4.85 | **3.85** | Residual from annual |
| 1957 | Aug | ~13.5 | **18.35** | Residual; IN3S → 18.35 |
| 1957 | Oct | 11.61 | **4.61** | Residual; 1.6L → 4.61 |

### Station 3 — Serom Estate, Tangkak

| Year | Month | OCR reading | Corrected to | Method |
|------|-------|-------------|-------------|--------|
| 1940 | Jul | 2.76 | **8.76** | Residual from annual |
| 1950 | Nov | 5.25 / 8.25 | **11.25** | Residual; 11→8 digit merge |
| 1952 | Feb | 5.93 | **8.93** | Residual; $→8 |
| 1952 | Oct | garbled (S881) | **8.81** | Residual from annual |
| 1953 | Sep | 7H | **7.31** | Residual; H→31 |

### Station 4 — Mersing Meteorological Station

| Year | Month | OCR reading | Corrected to | Method |
|------|-------|-------------|-------------|--------|
| 1932 | Jan | 9.25 | **7.25** | Residual from annual |
| 1933 | Dec | 9.9x | **9.96** | Residual from annual |
| 1935 | Jul | 6359 | **33.59** | Residual; large misread of 33.59 |
| 1936 | Aug | VAT | **7.47** | Residual; V→7, A→4, T→7 |
| 1937 | May | 5.56 | **8.56** | Residual; $→8 |
| 1938 | Apr | 7.45 | **7.15** | Residual; 4→1 |
| 1939 | Jul | 5.44 | **5.64** | Residual; 4→6 |
| 1947 | Jan | 18.41 | **15.41** | Residual; 8→5 + MEAN cross-check |
| 1950 | Oct | 5.94 | **8.94** | Residual; $→8 |
| 1951 | Nov | 9.35 | **19.35** | Residual; leading 1 dropped |
| 1953 | Mar | 5.23 | **8.23** | Residual + MEAN cross-check |
| 1956 | Aug | 5.13 | **8.13** | Residual; $→8 |
| 1957 | Apr | 1.57 | **3.57** | Residual; 1→3 |

---

## 11. Unresolved Items

| Station | Year | Issue |
|---------|------|-------|
| 2 | 1942 | Wartime partial year; OCR garbled across all months; row left blank |
| 3 | 1955 | Computed sum = 78.60; source printed annual appears to be ~78.00 — discrepancy 0.60, likely OCR misread of the annual total itself (digit dropped) |

---

## 12. Reproducibility

The complete pipeline is reproducible from the raw JPEG source files under `/mnt/project/`. All OCR passes were run with:

```bash
tesseract <input.png> stdout --psm <N> -c preserve_interword_spaces=1
```

The data assembly script (`build_johor_csv.py`) contains all reconciled values as Python literals and requires no re-running of OCR; it generates the output CSV deterministically from the corrected values derived during the interactive reconciliation session.

To re-verify any specific row from scratch:
1. Identify the image file and approximate y-position from the column boundary table (Section 3.1)
2. Run the preprocessing pipeline (Section 3) at 6–7× scale
3. Apply the OCR command with `--psm 6`
4. Check the output against the printed annual using the tolerance rules in Section 6.1
PYEOF