"""
build_corrected.py — assemble the CORRECTED master dataset from the current master.

  1. QC: mask physically-impossible monthly values (<0 or >150 in) -> NaN (logged).
  2. Apply Climatol homogenization corrections (multiplicative, last-segment baseline)
     to the affected station-year segments; keep every column and row of the master.
  3. Recompute annual_computed from corrected months; keep annual_printed as provenance.
  4. Add columns: correction_factor, homogenized, n_breaks.

Inputs : the current master CSV (set MASTER below), out/factors_climatol.csv,
         out/break_inventory.csv, out/breaks_climatol.csv.
Outputs: malaysia_national_rainfall_CORRECTED.csv, CORRECTIONS_LOG.csv, QC_MASKED_LOG.csv.
"""
import pandas as pd, numpy as np

M = ['Jan','Feb','March','April','May','June','July','Aug','Sept','Oct','Nov','Dec']
IMPOSSIBLE_HI = 150.0
MASTER = "malaysia_national_rainfall_with_singapore_final.csv"   # current master

cur   = pd.read_csv(MASTER)
fac   = pd.read_csv("out/factors_climatol.csv")
inv   = pd.read_csv("out/break_inventory.csv")
climb = pd.read_csv("out/breaks_climatol.csv")
nbreaks = climb.groupby('station').break_year.count()

cor = cur.copy()

# 1. QC mask impossible values
qc = []
for m in M:
    bad = (cor[m] < 0) | (cor[m] > IMPOSSIBLE_HI)
    for idx in cor.index[bad]:
        qc.append(dict(station=cor.at[idx,'station_name'], year=int(cor.at[idx,'year']),
                       month=m, masked_value=cor.at[idx,m]))
    cor.loc[bad, m] = np.nan

# 2. apply corrections
cor['correction_factor'] = 1.0
cor['homogenized'] = False
for _, f in fac.iterrows():
    mask = (cor.station_name == f.station) & (cor.year >= f.seg_start) & (cor.year <= f.seg_end)
    if f.factor != 1.0:
        cor.loc[mask, M] = cor.loc[mask, M] * f.factor
    cor.loc[mask, 'correction_factor'] = f.factor
cor.loc[cor.station_name.isin(climb.station.unique()), 'homogenized'] = True
cor['n_breaks'] = cor.station_name.map(nbreaks).fillna(0).astype(int)

# 3. recompute annual, round
cor[M] = cor[M].round(2)
cor['annual_computed'] = cor[M].sum(axis=1, min_count=12).round(2)
cor.to_csv("malaysia_national_rainfall_CORRECTED.csv", index=False)

# 4. logs
log = fac[fac.factor != 1.0].copy(); log['break_year'] = log.seg_end + 1
def conf(st, se):
    r = inv[(inv.station == st) & (inv.break_year == se + 1)]
    return r.confidence.iloc[0] if len(r) else ''
log['confidence'] = [conf(r.station, r.seg_end) for _, r in log.iterrows()]
log['n_years_in_segment'] = [int(((cur.station_name==r.station)&(cur.year>=r.seg_start)&(cur.year<=r.seg_end)).sum())
                             for _, r in log.iterrows()]
(log[['station','seg_start','seg_end','break_year','factor','confidence','n_years_in_segment']]
   .rename(columns={'factor':'correction_factor'}).sort_values(['station','seg_start'])
   .to_csv("CORRECTIONS_LOG.csv", index=False))
pd.DataFrame(qc).to_csv("QC_MASKED_LOG.csv", index=False)
print(f"corrected written: {len(cor)} rows; QC masked {len(qc)}; corrected segments {len(log)}")
