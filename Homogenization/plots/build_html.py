import base64, pandas as pd, numpy as np

OUT = "/home/claude/homog/out"
def b64(p):
    return "data:image/png;base64," + base64.b64encode(open(p,"rb").read()).decode()

fig1=b64(f"{OUT}/fig1_breaks_by_year.png")
fig3=b64(f"{OUT}/fig3_station_map.png")
fig4=b64(f"{OUT}/fig4_timeline_confidence.png")
fig6=b64(f"{OUT}/fig6_longest6_adjusted.png")

inv=pd.read_csv(f"{OUT}/break_inventory.csv")
hi=inv[inv.confidence=="high"].sort_values("break_year")
hi_rows="".join(f"<tr><td>{r.station}</td><td>{r.region}</td><td>{r.break_year}</td>"
    f"<td>{'' if pd.isna(r.applied_factor) else f'×{r.applied_factor:.2f}'}</td></tr>"
    for _,r in hi.iterrows())

HTML=f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rainfall Homogenization Report</title>
<style>
:root{{--bg:#ffffff;--fg:#1c2733;--muted:#5b6b7a;--line:#dce2e8;--accent:#2f6f9f;
--accent2:#c1662a;--soft:#f4f7fa;--war:#d9534f;}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.65 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;}}
.wrap{{max-width:860px;margin:0 auto;padding:56px 28px 96px;}}
h1{{font-size:30px;line-height:1.2;margin:0 0 6px;letter-spacing:-.01em}}
.sub{{color:var(--muted);font-size:15px;margin-bottom:8px}}
h2{{font-size:21px;margin:44px 0 12px;padding-bottom:7px;border-bottom:2px solid var(--accent);}}
h3{{font-size:16.5px;margin:26px 0 8px;color:var(--accent);}}
p{{margin:11px 0}}
.lead{{font-size:17px;color:#2a3a48}}
figure{{margin:22px 0;text-align:center}}
img{{max-width:100%;border:1px solid var(--line);border-radius:8px}}
figcaption{{color:var(--muted);font-size:13.5px;margin-top:7px}}
table{{border-collapse:collapse;width:100%;margin:16px 0;font-size:14.5px}}
th,td{{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}}
th{{background:var(--soft);font-weight:600}}
tbody tr:nth-child(even){{background:#fafcfe}}
.kpis{{display:flex;flex-wrap:wrap;gap:12px;margin:20px 0}}
.kpi{{flex:1 1 150px;background:var(--soft);border:1px solid var(--line);
border-radius:10px;padding:14px 16px}}
.kpi .n{{font-size:26px;font-weight:700;color:var(--accent)}}
.kpi .l{{font-size:12.5px;color:var(--muted);margin-top:2px}}
.note{{background:#fff6ec;border:1px solid #f0d3ac;border-left:4px solid var(--accent2);
border-radius:8px;padding:14px 16px;margin:20px 0;font-size:14.5px}}
.ref{{font-size:13.5px;color:#33414e}}
code{{background:var(--soft);padding:1px 5px;border-radius:4px;font-size:13.5px}}
.foot{{margin-top:40px;padding-top:14px;border-top:1px solid var(--line);
color:var(--muted);font-size:13px}}
</style></head><body><div class="wrap">

<h1>Homogenization of the Malaysia–Singapore historical rainfall archive</h1>
<div class="sub">Break detection, correction and infilling of monthly station rainfall, 1875–1958 &nbsp;·&nbsp; Climatol method + RHtestsV4 confirmation &nbsp;·&nbsp; 27 August 2026</div>

<div class="kpis">
<div class="kpi"><div class="n">672</div><div class="l">stations (≤1958)</div></div>
<div class="kpi"><div class="n">529</div><div class="l">eligible (≥10 yr)</div></div>
<div class="kpi"><div class="n">78</div><div class="l">breaks detected</div></div>
<div class="kpi"><div class="n">70</div><div class="l">stations adjusted</div></div>
<div class="kpi"><div class="n">41%</div><div class="l">breaks in 1946–53</div></div>
</div>

<p class="lead">This report documents an end-to-end homogenization of the pre-1958
Malaysia/Singapore monthly rainfall archive: how artificial breaks (inhomogeneities)
were detected against a network of neighbouring stations, how the affected series were
corrected, how gaps were filled, and how an independent test was used to grade the
confidence of each break. The dominant artificial signal is a cluster of breaks in the
years immediately after the Second World War.</p>

<div class="note"><b>Tooling note.</b> The genuine <code>climatol</code> and
<code>RHtestsV4</code> R packages could not be installed in the execution sandbox
(CRAN, conda and r-universe are firewalled there). Results were produced by a faithful
<b>Python implementation of the published algorithms</b>, validated against synthetic
series with known injected breaks. Ready-to-run scripts for the real R packages
(<code>run_climatol.R</code>, <code>run_rhtests.R</code>) are included so the analysis
reproduces on a CRAN-connected machine; small numerical differences from the packaged
tools are expected but the break structure should be stable.</div>

<h2>1. Data and scope</h2>
<p>The source archive merges historical monthly rainfall (in inches) for the Malay
Peninsula and Singapore with data-rescue records from Sumatra, Borneo and the
intervening islands. Records were restricted to <b>year ≤ 1958</b> — the year the
peninsular series close — giving 14,549 station-years from 672 stations. This
restricted core is denser and more complete than the full archive (monthly missing
6.5%, versus 10% with the post-1958 tail included). Seven previously-empty Selangor stations (Bute Estate Nilai, Tandridge, Tanjong Karang D.I.D., Pulau Lumut, Sungei Gumut, Sungei Kalong, Ulu Langat) were populated from newly transcribed records before this run and are now part of the network.</p>
<p>The defining feature for homogenization is that these are <b>many short, staggered,
overlapping records</b>: a median of ~18–26 data-years per station, with only 164
reaching 30 years. Combined with the low spatial correlation of equatorial convective
rainfall and the absence of any station-move metadata, this makes every detected break
<i>undocumented</i> and places the archive among the harder homogenization problems.</p>

<h2>2. Method</h2>
<h3>2.1 Preparation and quality control</h3>
<p>The wide station-year-by-month table was reshaped onto a common 1875–1958 monthly
frame (1,008 months × 672 stations with coordinates), plus annual totals (formed only
where all 12 months are present) and monsoon-season totals. Detection is performed on
<b>annual totals</b>, which are more Gaussian and have higher signal-to-noise for
rainfall; corrections are applied at the monthly level. Per the agreed QC rules,
physically-impossible values (negative or &gt;150 in/month) were masked — none occurred,
so all real extremes were kept — and reconcile-flagged rows were retained. Stations with
<b>≥10 data-years</b> were treated as eligible for homogenization (529 stations);
shorter ones are carried through for infilling only.</p>

<h3>2.2 Neighbour network</h3>
<p>Because rainfall de-correlates quickly in space here, each station's reference is a
distance-weighted mean of its normalized neighbours, capped at the 10 nearest within
200 km (Gaussian weighting, 60 km scale) and requiring a minimum annual-anomaly
correlation of 0.10. 525 eligible stations obtained at least one usable neighbour; the
very thin regions (Singapore, Perlis, Province Wellesley, Sabah, Sarawak) are
effectively absolute-only and are flagged accordingly.</p>

<h3>2.3 Detection — Climatol method (SNHT on a relative series)</h3>
<p>Each series was ratio-normalized (divided by its mean — the precipitation-appropriate
normalization). A neighbour reference was built in ratio space and the
candidate-minus-reference anomaly series was tested with the <b>Standard Normal
Homogeneity Test</b>, applied recursively to find multiple breakpoints (minimum segment
5 years, 95% Monte-Carlo critical values). References were then rebuilt from the
provisionally-corrected series and detection repeated — two outer passes — so that a
single broken neighbour cannot contaminate the references.</p>

<h3>2.4 Correction and infilling</h3>
<p>Corrections are <b>multiplicative</b>: each earlier segment is scaled onto the level
of the most-recent (reference) segment, using the ratio of candidate to reference over
each segment. Missing months were filled from a seasonal (monthly-climatology) neighbour
reference, denormalized to the station's homogenized level, and only <b>within each
station's observed span</b> — gap-filling, never extrapolation beyond a station's life.
Two products are produced: an <b>NA-preserving</b> series (observed values corrected,
gaps left as NA) and an <b>infilled</b> series.</p>

<h3>2.5 Independent confirmation — RHtests style</h3>
<p>On the 164 stations with ≥30 data-years, two penalized maximal tests were run: the
<b>PMF</b> (penalized maximal <i>F</i>, a two-phase regression with a common trend and
no reference) directly on the annual totals, and the <b>PMT</b> (penalized maximal
<i>t</i>, on the candidate-minus-reference series). Both use Monte-Carlo critical values,
which supply the end-point penalty and multiplicity correction directly.</p>

<h3>2.6 Validation of the implementation</h3>
<p>Before running on real data, the detection code was validated on synthetic networks:
7 of 8 injected relative breaks were recovered within ±3 years, a base-series step was
located exactly, and the SNHT critical values reproduced the standard tables
(n=20→7.0, n=40→7.9, n=60→9.1). Correctness of the correction was checked on the real
output: unadjusted stations are bit-identical to the raw data, no negative values are
introduced, and extremes are preserved.</p>

<h2>3. Results</h2>
<h3>3.1 Detection overview</h3>
<p>The Climatol method detected <b>78 breaks across 70 stations</b>. The median
multiplicative correction was <b>0.89</b> (a typical ~11% reduction of inflated early
segments; applied factors range 0.69–1.91), and <b>19,813</b> interior monthly gaps were
filled within span.</p>

<h3>3.2 Temporal structure — the post-war discontinuity</h3>
<p>Breaks are not uniformly distributed in time: <b>41% of all detected breaks fall in
1946–1953</b>, peaking in 1948–1950. This is the archive's dominant artificial signal —
network disruption, station relocation and re-establishment around the Japanese
occupation and its aftermath — and any trend analysis spanning the war must account for
it.</p>
<figure><img src="{fig1}" alt="Breaks by year">
<figcaption>Figure 1. Detected inhomogeneities by year. Bars = Climatol breaks; line =
RHtests PMT breaks. Shaded: the WWII gap (1942–46) and the post-war window (1946–53).</figcaption></figure>

<h3>3.3 Cross-method agreement and confidence</h3>
<p>Of the 49 Climatol breaks on long stations, <b>17 (35%) were confirmed</b> by RHtests
within ±2 years (16 by PMT, 6 by PMF). The modest rate is expected, not alarming: PMF is
an absolute test with weak power for artificial breaks in noisy tropical series, and
PMT's trend-aware penalty is deliberately stricter than SNHT — so RHtests endorses the
larger, clearer breaks and leaves marginal ones as Climatol-only. Every break is
therefore graded by confidence rather than treated as binary: <b>16 high</b>, 1
medium-high, 32 medium, 29 low, plus 55 RHtests-only breaks recorded for information.</p>
<figure><img src="{fig4}" alt="Network timeline and confidence">
<figcaption>Figure 2. Active stations per year (WWII collapse shaded) and the confidence
breakdown of Climatol breaks.</figcaption></figure>

<h3>3.4 High-confidence breaks</h3>
<table><thead><tr><th>Station</th><th>Region</th><th>Break year</th><th>Factor</th></tr></thead>
<tbody>{hi_rows}</tbody></table>

<h3>3.5 Spatial pattern</h3>
<p>Detected breaks concentrate in the dense western-peninsula regions (Perak, Selangor,
Johor, Pahang), simply because those are the only places with enough neighbours to run a
reliable relative test. The east coast, Borneo and the islands contribute few breaks —
not because they are homogeneous, but because they are too sparse to test.</p>
<figure><img src="{fig3}" alt="Station map">
<figcaption>Figure 3. Station network (≤1958); red = stations with a detected
inhomogeneity.</figcaption></figure>

<h3>3.6 Example corrections</h3>
<p>The six longest adjusted stations — all in Perak and Pahang — illustrate the
mechanism. Each has a single break whose pre-break segment reads systematically high
relative to neighbours and is scaled down; the raw and homogenized lines coincide after
the break and diverge before it. Note the 1918 break recurring at two Perak hospitals, a
plausible shared administrative/network change worth checking against station history.</p>
<figure><img src="{fig6}" alt="Longest adjusted stations before/after">
<figcaption>Figure 4. Raw (grey) vs Climatol-homogenized (blue) annual totals for the six
longest adjusted stations. Dashed = detected break; ×f = the applied multiplicative
factor.</figcaption></figure>

<h3>3.7 The mm → inches merge boundary</h3>
<p>The Sumatra/Borneo records were transcribed in millimetres and converted to inches on
ingestion, making their provenance a candidate offset. Pre-1958, only a handful of island
stations are long and well-connected enough to test, and just 3 island-sourced breaks
were found — too few to assess the conversion boundary statistically. It should be
spot-checked manually rather than relied upon here.</p>

<h2>4. Deliverables</h2>
<table><thead><tr><th>File</th><th>Contents</th></tr></thead><tbody>
<tr><td><code>malaysia_rainfall_homogenized_NApreserved.csv</code></td><td>Homogenized monthly series, original gaps kept as NA (14,200 station-years)</td></tr>
<tr><td><code>malaysia_rainfall_homogenized_infilled.csv</code></td><td>Homogenized and gap-filled within span (15,684 station-years; +1,484 recovered)</td></tr>
<tr><td><code>break_inventory.csv</code></td><td>Every break: station, year, detecting method(s), confidence, applied factor, coordinates</td></tr>
<tr><td><code>breaks_climatol.csv</code>, <code>breaks_rhtests.csv</code>, <code>factors_climatol.csv</code></td><td>Raw per-method outputs</td></tr>
<tr><td><code>figures/</code></td><td>Breaks-by-year, network timeline + confidence, station map, example corrections</td></tr>
<tr><td><code>R/run_climatol.R</code>, <code>R/run_rhtests.R</code></td><td>Reproduce with the genuine packages</td></tr>
<tr><td><code>scripts/*.py</code></td><td>The full Python pipeline (prep → homoglib → climatol_run → rhtests_run → finalize → plots)</td></tr>
</tbody></table>
<p>Both homogenized CSVs keep the original wide schema (station, metadata, 12 months,
recomputed <code>annual_computed</code>) plus <code>adjusted</code> and
<code>n_breaks</code> flags.</p>

<h2>5. Caveats and recommendations</h2>
<p>Detection is more reliable than correction for this archive: correlations are low,
series are short and staggered, and all breaks are undocumented. Corrections were applied
for every Climatol break (the primary method); for a conservative product, restrict
adjustments to <code>confidence ∈ {{high, medium-high}}</code> using the inventory.
Thin-region and short-station breaks (confidence = low) rest on few neighbours and should
be treated as tentative. The infilled product is spatial interpolation within a station's
active period, not observed data — use the NA-preserving copy for anything sensitive to
that distinction. Finally, the post-war break cluster and the recurring 1918 Perak break
are the two features most worth checking against any surviving station histories.</p>

<h2>6. References</h2>
<p class="ref">
Alexandersson, H. (1986). A homogeneity test applied to precipitation data. <i>J.
Climatol.</i> 6, 661–675.<br>
Alexandersson, H. &amp; Moberg, A. (1997). Homogenization of Swedish temperature data,
Part I. <i>Int. J. Climatol.</i> 17, 25–34.<br>
Guijarro, J.A. (2018). <i>Homogenization of climatic series with Climatol</i>. AEMET.<br>
Wang, X.L., Wen, Q.H. &amp; Wu, Y. (2007). Penalized maximal <i>t</i> test. <i>J. Appl.
Meteorol. Climatol.</i> 46, 916–931.<br>
Wang, X.L. (2008). Penalized maximal <i>F</i> test. <i>J. Atmos. Ocean. Technol.</i> 25,
368–384.<br>
Venema, V. et al. (2012). Benchmarking homogenization algorithms. <i>Clim. Past</i> 8,
89–115.<br>
Wijngaard, J.B., Klein Tank, A.M.G. &amp; Können, G.P. (2003). Homogeneity of European
daily series. <i>Int. J. Climatol.</i> 23, 679–692.</p>

<div class="foot">Generated for the SEA-climate-dataset project · pre-1958
Malaysia/Singapore rainfall homogenization · methods and results as described above.</div>
</div></body></html>"""

open(f"{OUT}/HOMOGENIZATION_REPORT.html","w").write(HTML)
print("wrote HOMOGENIZATION_REPORT.html", len(HTML), "bytes")
