"""
Step 3-5: Climatol-method homogenization.
  detection  : SNHT on annual ratio-normalized candidate-minus-reference series
               (2 outer passes; references rebuilt from provisionally-adjusted data)
  correction : multiplicative segment adjustment to the most-recent segment
  infilling  : monthly neighbour reference, denormalized -> gaps filled
Outputs to out/.
"""
import numpy as np, pandas as pd, json
from homoglib import (haversine_km, neighbour_weights, build_reference,
                      snht_recursive)

OUT = "/home/claude/homog/out"
LEVEL = 0.95
NREF, DMAX, WD, MINCORR = 10, 200.0, 60.0, 0.10
MIN_SEG = 5           # years
MIN_YEARS = 10

monthly = pd.read_pickle(f"{OUT}/monthly.pkl")          # (1008, S)
annual  = pd.read_pickle(f"{OUT}/annual.pkl")           # (84, S)
meta    = pd.read_csv(f"{OUT}/stations.csv").set_index("station_name")

# align station universe = stations present in monthly matrix with metadata coords
stations = [s for s in monthly.columns if s in meta.index
            and np.isfinite(meta.loc[s, "lat"]) and np.isfinite(meta.loc[s, "lon"])]
monthly = monthly[stations]
annual  = annual.reindex(columns=stations)
meta    = meta.loc[stations]
S = len(stations)
print(f"stations in run: {S}")

eligible = meta["n_years"].values >= MIN_YEARS
years = annual.index.values
A = annual.values.astype(float)                          # (Y, S)

# ---- neighbour graph: distance + annual-anomaly correlation ----
dist = haversine_km(meta["lat"].values, meta["lon"].values)
# ratio-normalized annual anomalies for correlation
meanA = np.nanmean(A, axis=0)
normA = A / meanA
corr = pd.DataFrame(normA, columns=stations).corr(min_periods=8).values
corr = np.nan_to_num(corr, nan=0.0)
W = neighbour_weights(dist, corr=corr, nref=NREF, dmax=DMAX, wd=WD, min_corr=MINCORR)
has_ref = (W.sum(1) > 0)
print(f"stations with >=1 usable neighbour: {int(has_ref.sum())}")

def segments_from_breaks(brks, y_present):
    """brks: 0-based split indices into full year axis. Return list of (lo,hi) index ranges."""
    cuts = [0] + sorted(brks) + [len(years)]
    return [(cuts[i], cuts[i+1]) for i in range(len(cuts)-1)]

def detect(normmat):
    ref = build_reference(normmat, W)
    anom = normmat - ref
    breaks = {}
    for j in range(S):
        if not (eligible[j] and has_ref[j]):
            continue
        bks = snht_recursive(anom[:, j], level=LEVEL, min_seg=MIN_SEG)
        if bks:
            breaks[j] = bks
    return breaks, ref

def adjust_norm(normmat, breaks, ref):
    """Return provisionally homogenized normalized matrix (adjust to last segment)."""
    out = normmat.copy()
    for j, bks in breaks.items():
        segs = segments_from_breaks(bks, None)
        # ratio obs/ref per segment
        ks = []
        for (lo, hi) in segs:
            o = normmat[lo:hi, j]; r = ref[lo:hi, j]
            m = np.isfinite(o) & np.isfinite(r) & (r > 0)
            ks.append(np.nanmean(o[m]/r[m]) if m.sum() >= 3 else np.nan)
        target = ks[-1] if np.isfinite(ks[-1]) else np.nanmean(ks)
        for si, (lo, hi) in enumerate(segs):
            if np.isfinite(ks[si]) and np.isfinite(target) and ks[si] > 0:
                out[lo:hi, j] *= target/ks[si]
    return out

# ---- Pass A ----
breaksA, refA = detect(normA)
normA_adj = adjust_norm(normA, breaksA, refA)
# ---- Pass B (references rebuilt from adjusted series) ----
refB = build_reference(normA_adj, W)
anomB = normA - refB
breaks = {}
for j in range(S):
    if not (eligible[j] and has_ref[j]):
        continue
    bks = snht_recursive(anomB[:, j], level=LEVEL, min_seg=MIN_SEG)
    if bks:
        breaks[j] = bks
print(f"stations with break(s): passA={len(breaksA)}  passB(final)={len(breaks)}")

# ---- correction factors per segment, applied to MONTHLY ----
mon_years = monthly.index.year.values
factors_rows = []
mon_h = monthly.copy()                                   # NA-preserving homogenized
Mvals = mon_h.values.copy()
for j, bks in breaks.items():
    segs = segments_from_breaks(bks, None)
    ks = []
    for (lo, hi) in segs:
        o = normA[lo:hi, j]; r = refB[lo:hi, j]
        m = np.isfinite(o) & np.isfinite(r) & (r > 0)
        ks.append(np.nanmean(o[m]/r[m]) if m.sum() >= 3 else np.nan)
    target = ks[-1] if np.isfinite(ks[-1]) else np.nanmean(ks)
    for si, (lo, hi) in enumerate(segs):
        yr_lo, yr_hi = years[lo], years[hi-1]
        f = 1.0
        if si != len(segs)-1 and np.isfinite(ks[si]) and np.isfinite(target) and ks[si] > 0:
            f = float(target/ks[si])
        # apply to monthly cells in [yr_lo, yr_hi]
        sel = (mon_years >= yr_lo) & (mon_years <= yr_hi)
        Mvals[sel, j] *= f
        factors_rows.append(dict(station=stations[j], seg_start=int(yr_lo),
                                 seg_end=int(yr_hi), factor=round(f, 4),
                                 is_reference_segment=(si == len(segs)-1)))
mon_h = pd.DataFrame(Mvals, index=monthly.index, columns=stations)

# ---- break inventory ----
brk_rows = []
for j, bks in breaks.items():
    for b in bks:
        brk_rows.append(dict(station=stations[j], region=meta.iloc[j]["region"],
                             country=meta.iloc[j]["country"],
                             break_year=int(years[b]),
                             lat=meta.iloc[j]["lat"], lon=meta.iloc[j]["lon"]))
brk = pd.DataFrame(brk_rows).sort_values(["region", "station", "break_year"])
brk.to_csv(f"{OUT}/breaks_climatol.csv", index=False)

# ---- monthly infilling (seasonal ratio reference) ----
mon_mat = mon_h.values
month_of = monthly.index.month.values
clim = np.full((12, S), np.nan)
for m in range(1, 13):
    sel = month_of == m
    clim[m-1] = np.nanmean(mon_mat[sel], axis=0)
normM = np.empty_like(mon_mat)
for ti in range(mon_mat.shape[0]):
    c = clim[month_of[ti]-1]
    normM[ti] = np.where(c > 0, mon_mat[ti]/c, np.nan)
refM = build_reference(normM, W)
filled = mon_mat.copy()
# within-span mask: only fill gaps between each station's first and last real obs
obs_mask = np.isfinite(monthly.values)
first_ti = np.array([np.argmax(obs_mask[:, j]) if obs_mask[:, j].any() else 10**9
                     for j in range(S)])
last_ti  = np.array([mon_mat.shape[0]-1-np.argmax(obs_mask[::-1, j]) if obs_mask[:, j].any()
                     else -1 for j in range(S)])
n_filled = 0
for ti in range(mon_mat.shape[0]):
    c = clim[month_of[ti]-1]
    est = refM[ti]*c
    within = (ti >= first_ti) & (ti <= last_ti)
    gap = np.isnan(filled[ti]) & np.isfinite(est) & within
    filled[ti][gap] = est[gap]
    n_filled += int(gap.sum())
mon_infilled = pd.DataFrame(filled, index=monthly.index, columns=stations)

# ---- save ----
mon_h.to_pickle(f"{OUT}/monthly_homog_napreserve.pkl")
mon_infilled.to_pickle(f"{OUT}/monthly_homog_infilled.pkl")
pd.DataFrame(factors_rows).to_csv(f"{OUT}/factors_climatol.csv", index=False)

summary = dict(
    stations_run=S,
    stations_eligible=int(eligible.sum()),
    stations_with_reference=int(has_ref.sum()),
    stations_with_break=len(breaks),
    total_breaks=int(len(brk)),
    breaks_by_year_top=brk.break_year.value_counts().head(12).sort_index().to_dict(),
    monthly_gaps_filled=n_filled,
    median_adjustment_factor=float(np.median([r["factor"] for r in factors_rows
                                              if not r["is_reference_segment"]] or [1.0])),
)
json.dump(summary, open(f"{OUT}/climatol_summary.json", "w"), indent=2, default=str)
print(json.dumps(summary, indent=2, default=str))
