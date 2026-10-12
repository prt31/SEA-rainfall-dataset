"""
alt_correction.py — alternative correction using the FIRST (earliest) segment as
the homogeneous baseline, instead of the most-recent segment.

Detection and breakpoints are unchanged; only the correction anchor moves:
    f_{i,1} = 1,   f_{i,s} = k_{i,1} / k_{i,s}
where k_{i,s} = mean( candidate / reference ) over segment s.

Produces monthly_homog_firstseg_napreserve.pkl and factors_firstseg.csv.
Run after climatol_run.py (needs out/annual.pkl, out/monthly.pkl, out/stations.csv,
out/breaks_climatol.csv, out/factors_climatol.csv).
"""
import numpy as np, pandas as pd
from homoglib import haversine_km, neighbour_weights, build_reference, snht_recursive

OUT = "out"
NREF, DMAX, WD, MINCORR = 10, 200.0, 60.0, 0.10
LEVEL, MIN_SEG, MIN_YEARS = 0.95, 5, 10

monthly = pd.read_pickle(f"{OUT}/monthly.pkl")
annual  = pd.read_pickle(f"{OUT}/annual.pkl")
meta    = pd.read_csv(f"{OUT}/stations.csv").set_index("station_name")
climb   = pd.read_csv(f"{OUT}/breaks_climatol.csv")

stations = [s for s in monthly.columns if s in meta.index
            and np.isfinite(meta.loc[s, "lat"]) and np.isfinite(meta.loc[s, "lon"])]
monthly = monthly[stations]; annual = annual.reindex(columns=stations); meta = meta.loc[stations]
S = len(stations); years = annual.index.values; A = annual.values.astype(float)
eligible = meta["n_years"].values >= MIN_YEARS
meanA = np.nanmean(A, axis=0); normA = A / meanA
dist = haversine_km(meta["lat"].values, meta["lon"].values)
corr = np.nan_to_num(pd.DataFrame(normA, columns=stations).corr(min_periods=8).values, nan=0.0)
W = neighbour_weights(dist, corr=corr, nref=NREF, dmax=DMAX, wd=WD, min_corr=MINCORR)
has_ref = (W.sum(1) > 0)

def segs(brks):
    cuts = [0] + sorted(brks) + [len(years)]
    return [(cuts[i], cuts[i + 1]) for i in range(len(cuts) - 1)]

# replay pass A -> refB (same detection reference as climatol_run)
refA = build_reference(normA, W); anomA = normA - refA
adj = normA.copy()
for j in range(S):
    if not (eligible[j] and has_ref[j]): continue
    bk = snht_recursive(anomA[:, j], level=LEVEL, min_seg=MIN_SEG)
    if not bk: continue
    ks = []
    for lo, hi in segs(bk):
        o = normA[lo:hi, j]; r = refA[lo:hi, j]; m = np.isfinite(o) & np.isfinite(r) & (r > 0)
        ks.append(np.nanmean(o[m] / r[m]) if m.sum() >= 3 else np.nan)
    tgt = ks[-1] if np.isfinite(ks[-1]) else np.nanmean(ks)
    for si, (lo, hi) in enumerate(segs(bk)):
        if np.isfinite(ks[si]) and np.isfinite(tgt) and ks[si] > 0: adj[lo:hi, j] *= tgt / ks[si]
refB = build_reference(adj, W)

brk_by_st = {}
for st_, g in climb.groupby("station"):
    if st_ in stations:
        j = stations.index(st_)
        brk_by_st[j] = sorted([int(np.where(years == y)[0][0]) for y in g.break_year])

mon_years = monthly.index.year.values
Mv = monthly.values.copy(); rows = []
for j, bk in brk_by_st.items():
    ks = []
    for lo, hi in segs(bk):
        o = normA[lo:hi, j]; r = refB[lo:hi, j]; m = np.isfinite(o) & np.isfinite(r) & (r > 0)
        ks.append(np.nanmean(o[m] / r[m]) if m.sum() >= 3 else np.nan)
    base = ks[0] if np.isfinite(ks[0]) else np.nanmean(ks)        # FIRST segment baseline
    for si, (lo, hi) in enumerate(segs(bk)):
        yl, yh = years[lo], years[hi - 1]; f = 1.0
        if si != 0 and np.isfinite(ks[si]) and np.isfinite(base) and ks[si] > 0: f = float(base / ks[si])
        sel = (mon_years >= yl) & (mon_years <= yh); Mv[sel, j] *= f
        rows.append(dict(station=stations[j], seg_start=int(yl), seg_end=int(yh),
                         factor_firstseg=round(f, 4), is_baseline_segment=(si == 0)))
pd.DataFrame(Mv, index=monthly.index, columns=stations).to_pickle(f"{OUT}/monthly_homog_firstseg_napreserve.pkl")
pd.DataFrame(rows).to_csv(f"{OUT}/factors_firstseg.csv", index=False)
print("first-segment-baseline correction written.")
