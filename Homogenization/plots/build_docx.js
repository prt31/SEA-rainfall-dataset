const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType, ImageRun,
  PageBreak, TableOfContents
} = require('docx');

const OUT = '/home/claude/homog/out';
const img = f => fs.readFileSync(`${OUT}/${f}`);
const ACC = '2F6F9F', ACC2 = 'C1662A', LINE = 'DCE2E8', SOFT = 'F4F7FA', MUT = '5B6B7A';

// ---- helpers ----
const H1 = t => new Paragraph({ heading: HeadingLevel.HEADING_1, spacing:{before:320,after:140}, children:[new TextRun({text:t, color:ACC, bold:true})],
  border:{bottom:{color:ACC, size:10, style:BorderStyle.SINGLE, space:4}} });
const H2 = t => new Paragraph({ heading: HeadingLevel.HEADING_2, spacing:{before:220,after:80}, children:[new TextRun({text:t, color:ACC2, bold:true})] });
function P(runs, opts={}) {
  const arr = Array.isArray(runs) ? runs : [new TextRun(runs)];
  return new Paragraph({ spacing:{after:120, line:300}, children:arr, ...opts });
}
const b = t => new TextRun({text:t, bold:true});
const t = s => new TextRun(s);
function figure(file, w, h, cap) {
  return [
    new Paragraph({ alignment:AlignmentType.CENTER, spacing:{before:120,after:40},
      children:[new ImageRun({ type:'png', data:img(file), transformation:{width:w, height:h} })] }),
    new Paragraph({ alignment:AlignmentType.CENTER, spacing:{after:160},
      children:[new TextRun({text:cap, italics:true, size:18, color:MUT})] })
  ];
}
function table(headers, rows, widths) {
  const total = widths.reduce((a,c)=>a+c,0);
  const hc = headers.map((htext,i)=> new TableCell({ width:{size:widths[i],type:WidthType.DXA},
    shading:{type:ShadingType.CLEAR, fill:SOFT}, margins:{top:40,bottom:40,left:80,right:80},
    children:[new Paragraph({children:[new TextRun({text:htext,bold:true,size:19})]})] }));
  const trs = [ new TableRow({ tableHeader:true, children:hc }) ];
  rows.forEach(r=>{
    trs.push(new TableRow({ children: r.map((c,i)=> new TableCell({
      width:{size:widths[i],type:WidthType.DXA}, margins:{top:30,bottom:30,left:80,right:80},
      children:[new Paragraph({children:[new TextRun({text:String(c),size:18})]})] })) }));
  });
  return new Table({ columnWidths:widths, width:{size:total,type:WidthType.DXA},
    borders:['top','bottom','left','right','insideHorizontal','insideVertical'].reduce((o,k)=>{
      o[k]={style:BorderStyle.SINGLE,size:4,color:LINE}; return o;},{}),
    rows:trs });
}

// ---- high-confidence rows from inventory ----
const inv = fs.readFileSync(`${OUT}/break_inventory.csv`,'utf8').trim().split('\n');
const head = inv[0].split(',');
const ci = n => head.indexOf(n);
const hiRows = inv.slice(1).map(l=>l.split(',')).filter(c=>c[ci('confidence')]==='high')
  .map(c=>[c[ci('station')], c[ci('region')], c[ci('break_year')],
           c[ci('applied_factor')] ? '×'+parseFloat(c[ci('applied_factor')]).toFixed(2) : ''])
  .sort((a,b)=>a[2]-b[2]);

const children = [];
// Title
children.push(new Paragraph({ spacing:{after:40}, children:[new TextRun({
  text:'Homogenization of the Malaysia–Singapore historical rainfall archive', bold:true, size:36, color:'1C2733'})] }));
children.push(new Paragraph({ spacing:{after:60}, children:[new TextRun({
  text:'Break detection, correction and infilling of monthly station rainfall, 1875–1958', size:22, color:MUT})] }));
children.push(new Paragraph({ spacing:{after:200}, children:[new TextRun({
  text:'Climatol method + RHtestsV4 confirmation  ·  27 August 2026', size:20, color:MUT})] }));

// KPI table
children.push(table(['Stations (≤1958)','Eligible (≥10 yr)','Breaks detected','Stations adjusted','Breaks in 1946–53'],
  [['672','529','78','70','41%']], [1900,1900,1900,1900,1900]));
children.push(P(''));

children.push(P([t('This report documents an end-to-end homogenization of the pre-1958 Malaysia/Singapore monthly rainfall archive: how artificial breaks were detected against a network of neighbouring stations, how affected series were corrected, how gaps were filled, and how an independent test graded the confidence of each break. The dominant artificial signal is a cluster of breaks in the years immediately after the Second World War.')]));

// Tooling note
children.push(new Paragraph({ spacing:{before:80,after:160}, shading:{type:ShadingType.CLEAR, fill:'FFF6EC'},
  border:{left:{color:ACC2,size:18,style:BorderStyle.SINGLE,space:8},
          top:{color:'F0D3AC',size:4,style:BorderStyle.SINGLE,space:6},
          bottom:{color:'F0D3AC',size:4,style:BorderStyle.SINGLE,space:6},
          right:{color:'F0D3AC',size:4,style:BorderStyle.SINGLE,space:6}},
  children:[ b('Tooling note.  '), t('The genuine climatol and RHtestsV4 R packages could not be installed in the execution sandbox (CRAN, conda and r-universe are firewalled there). Results were produced by a faithful Python implementation of the published algorithms, validated against synthetic series with known injected breaks. Ready-to-run scripts for the real R packages (run_climatol.R, run_rhtests.R) are included so the analysis reproduces on a CRAN-connected machine; small numerical differences from the packaged tools are expected but the break structure should be stable.') ] }));

// 1 Data
children.push(H1('1. Data and scope'));
children.push(P([t('The source archive merges historical monthly rainfall (inches) for the Malay Peninsula and Singapore with data-rescue records from Sumatra, Borneo and the intervening islands. Records were restricted to '), b('year ≤ 1958'), t(' — the year the peninsular series close — giving 14,549 station-years from 672 stations. This restricted core is denser and more complete than the full archive (6.5% monthly missing vs 10% with the post-1958 tail). Seven previously-empty Selangor stations were populated from newly transcribed records before this run.')]));
children.push(P([t('The defining feature for homogenization is that these are '), b('many short, staggered, overlapping records'), t(': a median of ~18–26 data-years per station, with only 164 reaching 30 years. Combined with the low spatial correlation of equatorial rainfall and the absence of any station-move metadata, this makes every detected break undocumented and places the archive among the harder homogenization problems.')]));

// 2 Method
children.push(H1('2. Method'));
children.push(H2('2.1 Preparation and quality control'));
children.push(P([t('The wide table was reshaped onto a common 1875–1958 monthly frame (1,008 months × 672 stations with coordinates), plus annual totals (only where all 12 months are present) and monsoon-season totals. Detection uses '), b('annual totals'), t(' (more Gaussian, higher signal-to-noise for rainfall); corrections are applied monthly. Impossible values (negative or >150 in/month) were masked — none occurred, so all real extremes were kept — and reconcile-flagged rows retained. Stations with '), b('≥10 data-years'), t(' are eligible (529); shorter ones are carried through for infilling only.')]));
children.push(H2('2.2 Neighbour network'));
children.push(P([t('Because rainfall de-correlates quickly here, each station’s reference is a distance-weighted mean of normalized neighbours, capped at the 10 nearest within 200 km (Gaussian, 60 km scale) with a minimum annual-anomaly correlation of 0.10. 525 eligible stations obtained a usable neighbour; the very thin regions (Singapore, Perlis, Province Wellesley, Sabah, Sarawak) are effectively absolute-only and are flagged.')]));
children.push(H2('2.3 Detection — Climatol method (SNHT on a relative series)'));
children.push(P([t('Series were ratio-normalized (divided by their mean). A neighbour reference was built in ratio space and the candidate-minus-reference anomaly tested with the '), b('Standard Normal Homogeneity Test'), t(', applied recursively for multiple breakpoints (minimum segment 5 years, 95% Monte-Carlo critical values). References were then rebuilt from the provisionally-corrected series and detection repeated — two outer passes — so a single broken neighbour cannot contaminate the references.')]));
children.push(H2('2.4 Correction and infilling'));
children.push(P([b('Multiplicative'), t(' corrections scale each earlier segment onto the level of the most-recent segment, via the candidate-to-reference ratio over each segment. Gaps were filled from a seasonal (monthly-climatology) neighbour reference, denormalized to the station’s homogenized level, and only '), b('within each station’s observed span'), t(' — never extrapolation. Two products result: an NA-preserving series and an infilled series.')]));
children.push(H2('2.5 Independent confirmation — RHtests style'));
children.push(P([t('On the 164 stations with ≥30 data-years, two penalized maximal tests were run: '), b('PMF'), t(' (penalized maximal F, two-phase regression with a common trend, no reference) on annual totals, and '), b('PMT'), t(' (penalized maximal t, on the candidate-minus-reference series). Both use Monte-Carlo critical values, supplying the end-point penalty and multiplicity correction directly.')]));
children.push(H2('2.6 Validation of the implementation'));
children.push(P([t('Before running on real data, detection was validated on synthetic networks: 7 of 8 injected relative breaks recovered within ±3 years, a base-series step located exactly, and SNHT critical values reproducing the standard tables (n=20→7.0, n=40→7.9, n=60→9.1). On the real output, unadjusted stations are bit-identical to raw, no negatives are introduced, and extremes are preserved.')]));

// 3 Results
children.push(H1('3. Results'));
children.push(H2('3.1 Detection overview'));
children.push(P([t('The Climatol method detected '), b('78 breaks across 70 stations'), t('. The median correction was '), b('0.89'), t(' (a typical ~11% reduction of inflated early segments; factors 0.69–1.91), and '), b('19,813'), t(' interior monthly gaps were filled within span.')]));
children.push(H2('3.2 Temporal structure — the post-war discontinuity'));
children.push(P([b('41% of all detected breaks fall in 1946–1953'), t(', peaking in 1948–1950 — the archive’s dominant artificial signal, reflecting network disruption, relocation and re-establishment around the occupation and its aftermath. Any trend analysis spanning the war must account for it.')]));
figure('fig1_breaks_by_year.png', 600, 252, 'Figure 1. Detected inhomogeneities by year. Bars = Climatol breaks; line = RHtests PMT breaks. Shaded: WWII gap (1942–46) and post-war window (1946–53).').forEach(x=>children.push(x));
children.push(H2('3.3 Cross-method agreement and confidence'));
children.push(P([t('Of the 49 Climatol breaks on long stations, '), b('17 (35%) were confirmed'), t(' by RHtests within ±2 years (16 by PMT, 6 by PMF). The modest rate is expected: PMF is an absolute test with weak power for artificial breaks in noisy tropical series, and PMT’s trend-aware penalty is stricter than SNHT, so RHtests endorses the larger breaks and leaves marginal ones as Climatol-only. Every break is graded: '), b('16 high'), t(', 1 medium-high, 32 medium, 29 low, plus 55 RHtests-only recorded for information.')]));
figure('fig4_timeline_confidence.png', 600, 229, 'Figure 2. Active stations per year (WWII collapse shaded) and the confidence breakdown of Climatol breaks.').forEach(x=>children.push(x));
children.push(H2('3.4 High-confidence breaks'));
children.push(table(['Station','Region','Break year','Factor'], hiRows, [3800,2000,1400,1400]));
children.push(P(''));
children.push(H2('3.5 Spatial pattern'));
children.push(P([t('Breaks concentrate in the dense western-peninsula regions (Perak, Selangor, Johor, Pahang) — the only places with enough neighbours for a reliable relative test. The east coast, Borneo and islands contribute few breaks, not because they are homogeneous but because they are too sparse to test.')]));
figure('fig3_station_map.png', 480, 455, 'Figure 3. Station network (≤1958); red = stations with a detected inhomogeneity.').forEach(x=>children.push(x));
children.push(H2('3.6 Example corrections'));
children.push(P([t('The six longest adjusted stations — all in Perak and Pahang — illustrate the mechanism. Each has a single break whose pre-break segment reads systematically high relative to neighbours and is scaled down; raw and homogenized lines coincide after the break and diverge before it. The 1918 break recurs at two Perak hospitals — a plausible shared administrative/network change worth checking against station history.')]));
figure('fig6_longest6_adjusted.png', 600, 507, 'Figure 4. Raw (grey) vs Climatol-homogenized (blue) annual totals for the six longest adjusted stations. Dashed = break; ×f = applied factor.').forEach(x=>children.push(x));
children.push(H2('3.7 The mm → inches merge boundary'));
children.push(P([t('The Sumatra/Borneo records were transcribed in millimetres and converted to inches on ingestion, making their provenance a candidate offset. Pre-1958, only a handful of island stations are long and well-connected enough to test, and just 3 island-sourced breaks were found — too few to assess statistically. Spot-check the conversion manually rather than relying on it here.')]));

// 4 Deliverables
children.push(H1('4. Deliverables'));
children.push(table(['File','Contents'], [
  ['malaysia_rainfall_homogenized_NApreserved.csv','Homogenized monthly series, gaps kept as NA (14,200 station-years)'],
  ['malaysia_rainfall_homogenized_infilled.csv','Homogenized and gap-filled within span (15,684 station-years; +1,484)'],
  ['break_inventory.csv','Every break: station, year, method(s), confidence, factor, coordinates'],
  ['breaks_climatol.csv / breaks_rhtests.csv / factors_climatol.csv','Raw per-method outputs'],
  ['figures/','Breaks-by-year, timeline+confidence, station map, example corrections'],
  ['R/run_climatol.R / run_rhtests.R','Reproduce with the genuine packages'],
  ['scripts/*.py','Full Python pipeline (prep → homoglib → climatol_run → rhtests_run → finalize → plots)'],
], [4200,4400]));
children.push(P([t('Both homogenized CSVs keep the original wide schema (station, metadata, 12 months, recomputed annual_computed) plus adjusted and n_breaks flags.')]));

// 5 Caveats
children.push(H1('5. Caveats and recommendations'));
children.push(P([t('Detection is more reliable than correction here: correlations are low, series short and staggered, all breaks undocumented. Corrections were applied for every Climatol break (the primary method); for a conservative product, restrict adjustments to confidence ∈ {high, medium-high} using the inventory. Low-confidence breaks rest on few neighbours and are tentative. The infilled product is spatial interpolation within a station’s active period, not observed data — use the NA-preserving copy where that distinction matters. The post-war cluster and the recurring 1918 Perak break are the two features most worth checking against surviving station histories.')]));

// 6 References
children.push(H1('6. References'));
[
 'Alexandersson, H. (1986). A homogeneity test applied to precipitation data. J. Climatol. 6, 661–675.',
 'Alexandersson, H. & Moberg, A. (1997). Homogenization of Swedish temperature data, Part I. Int. J. Climatol. 17, 25–34.',
 'Guijarro, J.A. (2018). Homogenization of climatic series with Climatol. AEMET.',
 'Wang, X.L., Wen, Q.H. & Wu, Y. (2007). Penalized maximal t test. J. Appl. Meteorol. Climatol. 46, 916–931.',
 'Wang, X.L. (2008). Penalized maximal F test. J. Atmos. Ocean. Technol. 25, 368–384.',
 'Venema, V. et al. (2012). Benchmarking homogenization algorithms. Clim. Past 8, 89–115.',
 'Wijngaard, J.B., Klein Tank, A.M.G. & Können, G.P. (2003). Homogeneity of European daily series. Int. J. Climatol. 23, 679–692.'
].forEach(r=>children.push(new Paragraph({spacing:{after:60}, children:[new TextRun({text:r, size:18, color:'33414E'})]})));

const doc = new Document({
  styles:{ default:{ document:{ run:{ font:'Calibri', size:21 } } } },
  sections:[{ properties:{ page:{ size:{ width:12240, height:15840 }, margin:{top:1080,bottom:1080,left:1180,right:1180} } }, children }]
});
Packer.toBuffer(doc).then(bfr=>{ fs.writeFileSync(`${OUT}/HOMOGENIZATION_REPORT.docx`, bfr); console.log('wrote HOMOGENIZATION_REPORT.docx', bfr.length, 'bytes'); });
