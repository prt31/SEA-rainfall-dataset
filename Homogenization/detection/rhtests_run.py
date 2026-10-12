"""
Step 6: RHtestsV4-style confirmation on long stations (>=30 data-years).
  - recursive penalized maximal F test (PMFmax) on annual totals, NO reference
    (independent of the Climatol neighbour approach)
  - confirm each Climatol break if a PMF break lies within +/-2 years
  - WWII-window and mm->inches (island vs peninsula) diagnostics
"""
import numpy as np, pandas as pd, json
from homoglib import (_maxF, maxF_crit, haversine_km, neighbour_weights,
                      build_reference)

OUT = "/home/claude/homog/out"
LEVEL = 0.95
MIN_SEG = 5
LONG_MIN = 30
NREF, DMAX, WD, MINCORR = 10, 200.0, 60.0, 0.10

annual = pd.read_pickle(f"{OUT}/annual.pkl")
meta   = pd.read_csv(f"{OUT}/stations.csv").set_index("station_name")
clim_brk = pd.read_csv(f"{OUT}/breaks_climatol.csv")
years = annual.index.values

# ---- reference-difference series (for PMT-with-reference), same graph as Climatol ----
allst = [s for s in annual.columns if s in meta.index
         and np.isfinite(meta.loc[s, "lat"]) and np.isfinite(meta.loc[s, "lon"])]
A = annual.reindex(columns=allst).values.astype(float)
mA = np.nanmean(A, axis=0); normA = A/mA
dist = haversine_km(meta.loc[allst, "lat"].values, meta.loc[allst, "lon"].values)
corr = np.nan_to_num(pd.DataFrame(normA, columns=allst).corr(min_periods=8).values, nan=0.0)
W = neighbour_weights(dist, corr=corr, nref=NREF, dmax=DMAX, wd=WD, min_corr=MINCORR)
ref = build_reference(normA, W)
diff = normA - ref                      # stationary-ish difference series
diff_df = pd.DataFrame(diff, index=years, columns=allst)

def pmf_recursive(series, level=LEVEL, min_seg=MIN_SEG, nsim=1500):
    s = np.asarray(series, float)
    idx = np.where(~np.isnan(s))[0]
    if len(idx) < 2*min_seg:
        return []
    y = s[idx]
    F, k = _maxF(y)
    if k < min_seg or (len(y)-k) < min_seg:
        return []
    if F <= maxF_crit(len(y), level, nsim):
        return []
    brk = idx[k]
    left = s.copy();  left[brk:] = np.nan
    right = s.copy(); right[:brk] = np.nan
    return sorted(set([brk] + pmf_recursive(left, level, min_seg, nsim)
                              + pmf_recursive(right, level, min_seg, nsim)))

long_st = meta.index[meta["n_years"] >= LONG_MIN].tolist()
long_st = [s for s in long_st if s in annual.columns]
print(f"long stations (>= {LONG_MIN} yr): {len(long_st)}")

rows = []; rows_t = []
pmf_break_years = []
for st in long_st:
    for b in pmf_recursive(annual[st].values):                 # PMF: no reference
        rows.append(dict(station=st, region=meta.loc[st, "region"],
                         country=meta.loc[st, "country"], break_year=int(years[b]), test="PMF"))
        pmf_break_years.append(int(years[b]))
    if st in diff_df.columns:                                  # PMT: with reference
        for b in pmf_recursive(diff_df[st].values):
            rows_t.append(dict(station=st, region=meta.loc[st, "region"],
                               country=meta.loc[st, "country"], break_year=int(years[b]), test="PMT"))
pmf = pd.DataFrame(rows)
pmt = pd.DataFrame(rows_t)
allbrk = pd.concat([pmf, pmt], ignore_index=True)
allbrk.to_csv(f"{OUT}/breaks_rhtests.csv", index=False)

# ---- confirm Climatol breaks on long stations (by PMF, by PMT, by either) ----
clim_long = clim_brk[clim_brk.station.isin(long_st)].copy()
def _near(tbl, row):
    cand = tbl[tbl.station == row.station] if len(tbl) else tbl
    return bool(len(cand) and (np.abs(cand.break_year.values - row.break_year) <= 2).any())
clim_long["confirmed_pmf"] = clim_long.apply(lambda r: _near(pmf, r), axis=1)
clim_long["confirmed_pmt"] = clim_long.apply(lambda r: _near(pmt, r), axis=1)
clim_long["rhtests_confirmed"] = clim_long.confirmed_pmf | clim_long.confirmed_pmt
clim_long.to_csv(f"{OUT}/climatol_breaks_on_long_stations.csv", index=False)

# ---- WWII + island/peninsula diagnostics on ALL climatol breaks ----
wwii = clim_brk[(clim_brk.break_year >= 1946) & (clim_brk.break_year <= 1953)]
island_regions = {"Sumatra", "Sarawak", "Sabah", "Labuan", "Bangka-Belitung",
                  "Anambas_Riau", "Anambas/Riau"}
clim_brk["island_mm_source"] = clim_brk.country.eq("Indonesia") | clim_brk.region.isin(island_regions)
isl_n = int(clim_brk.island_mm_source.sum())

summary = dict(
    long_stations=len(long_st),
    rhtests_pmf_breaks=int(len(pmf)),
    rhtests_pmt_breaks=int(len(pmt)),
    rhtests_stations_with_break=int(allbrk.station.nunique()) if len(allbrk) else 0,
    climatol_breaks_on_long=int(len(clim_long)),
    confirmed_by_pmf=int(clim_long["confirmed_pmf"].sum()) if len(clim_long) else 0,
    confirmed_by_pmt=int(clim_long["confirmed_pmt"].sum()) if len(clim_long) else 0,
    climatol_confirmed_by_rhtests=int(clim_long["rhtests_confirmed"].sum()) if len(clim_long) else 0,
    confirmation_rate=round(float(clim_long["rhtests_confirmed"].mean()), 3) if len(clim_long) else None,
    climatol_breaks_in_wwii_window_1946_1953=int(len(wwii)),
    pct_climatol_breaks_in_wwii_window=round(100*len(wwii)/max(len(clim_brk), 1), 1),
    island_mm_sourced_breaks=isl_n,
    pmf_break_year_hist=pd.Series(pmf_break_years).value_counts().sort_index().to_dict() if pmf_break_years else {},
)
json.dump(summary, open(f"{OUT}/rhtests_summary.json", "w"), indent=2, default=str)
print(json.dumps(summary, indent=2, default=str))
