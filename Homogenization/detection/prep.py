"""
Step 1-2: Reshape + QC for the Malaysia/Singapore pre-1958 rainfall archive.

- Restrict to year <= 1958 (already done, but re-applied defensively).
- Reshape wide station-year-by-month -> continuous monthly matrix (time x station),
  annual totals, and seasonal totals, on a common 1875-1958 frame.
- QC: screen physically-impossible values (neg or > 150 in/month) -> NA. Extremes kept.
  Reconcile-flagged rows are KEPT (per user instruction).
- Eligibility: stations with >= 10 distinct data-years are flagged homogenizable.

Outputs (in out/):
  monthly.parquet     time(1008) x station   monthly totals (inches)
  annual.parquet      year(84)  x station     annual totals (inches, all-12-present)
  seasonal.parquet    (year,season) x station seasonal totals
  stations.csv        per-station metadata + eligibility
  prep_summary.json
"""
import pandas as pd, numpy as np, json, os

SRC = "/tmp/main_updated.csv"
OUT = "/home/claude/homog/out"
os.makedirs(OUT, exist_ok=True)

MONTHS = ['Jan','Feb','March','April','May','June','July','Aug','Sept','Oct','Nov','Dec']
MON_NUM = {m: i+1 for i, m in enumerate(MONTHS)}
IMPOSSIBLE_HI = 150.0     # in/month; nothing real approaches this (obs max ~109). Extremes kept.
Y0, Y1 = 1875, 1958
MIN_YEARS = 10            # homogenization-eligibility threshold

df = pd.read_csv(SRC)
df = df[df.year <= Y1].copy()

# ---- QC: impossible-value screen (keep extremes) ----
n_impossible = 0
for m in MONTHS:
    bad = (df[m] < 0) | (df[m] > IMPOSSIBLE_HI)
    n_impossible += int(bad.sum())
    df.loc[bad, m] = np.nan

# ---- Long form ----
long = df.melt(id_vars=['station_name','year'], value_vars=MONTHS,
               var_name='mon', value_name='rain')
long['month'] = long['mon'].map(MON_NUM)
long['date'] = pd.to_datetime(dict(year=long.year, month=long.month, day=1))

# ---- Monthly matrix (time x station) on common frame ----
full_idx = pd.date_range(f"{Y0}-01-01", f"{Y1}-12-01", freq="MS")
monthly = long.pivot_table(index='date', columns='station_name', values='rain', aggfunc='mean')
monthly = monthly.reindex(full_idx)
monthly.index.name = 'date'

# ---- Annual totals: only years with all 12 months present ----
cnt = long.dropna(subset=['rain']).groupby(['station_name','year']).rain.count()
sm  = long.dropna(subset=['rain']).groupby(['station_name','year']).rain.sum()
ann_long = pd.DataFrame({'n':cnt,'sum':sm}).reset_index()
ann_long.loc[ann_long.n < 12, 'sum'] = np.nan
annual = ann_long.pivot_table(index='year', columns='station_name', values='sum')
annual = annual.reindex(range(Y0, Y1+1))
annual.index.name = 'year'

# ---- Seasonal totals (monsoon seasons for the region) ----
# DJF = NE monsoon peak, MAM = inter-monsoon 1, JJA = SW monsoon, SON = inter-monsoon 2
SEASON = {12:'DJF',1:'DJF',2:'DJF',3:'MAM',4:'MAM',5:'MAM',
          6:'JJA',7:'JJA',8:'JJA',9:'SON',10:'SON',11:'SON'}
# DJF assigned to the year of Jan/Feb (Dec belongs to following DJF)
ls = long.dropna(subset=['rain']).copy()
ls['season'] = ls.month.map(SEASON)
ls['syear'] = ls.year + ((ls.month==12).astype(int))  # Dec -> next year's DJF
scnt = ls.groupby(['station_name','syear','season']).rain.agg(['sum','count']).reset_index()
scnt.loc[scnt['count'] < 3, 'sum'] = np.nan
seasonal = scnt.pivot_table(index=['syear','season'], columns='station_name', values='sum')

# ---- Station metadata ----
meta = (df.groupby('station_name')
          .agg(region=('region','first'),
               country=('country_modern','first'),
               lat=('lat_decimal','median'),
               lon=('lon_decimal','median'),
               elev=('elevation_m','median'),
               dist_coast=('distance_to_coast_km','median'))
          .reset_index())
nyears = long.dropna(subset=['rain']).groupby('station_name').year.nunique()
span = long.dropna(subset=['rain']).groupby('station_name').year.agg(lambda s: s.max()-s.min()+1)
first = long.dropna(subset=['rain']).groupby('station_name').year.min()
last  = long.dropna(subset=['rain']).groupby('station_name').year.max()
meta = meta.set_index('station_name')
meta['n_years'] = nyears
meta['span'] = span
meta['first_year'] = first
meta['last_year'] = last
meta['n_months'] = monthly.notna().sum()
meta['eligible'] = meta['n_years'] >= MIN_YEARS
meta = meta.reset_index()

# ---- Save ----
monthly.to_pickle(f"{OUT}/monthly.pkl")
annual.to_pickle(f"{OUT}/annual.pkl")
seasonal.to_pickle(f"{OUT}/seasonal.pkl")
meta.to_csv(f"{OUT}/stations.csv", index=False)

summary = dict(
    rows_in=int(len(df)),
    year_range=[int(df.year.min()), int(df.year.max())],
    n_stations=int(df.station_name.nunique()),
    impossible_values_masked=n_impossible,
    monthly_matrix_shape=list(monthly.shape),
    monthly_filled_cells=int(monthly.notna().sum().sum()),
    annual_matrix_shape=list(annual.shape),
    eligible_stations=int(meta.eligible.sum()),
    ineligible_stations=int((~meta.eligible).sum()),
    eligible_by_region=meta[meta.eligible].groupby('region').station_name.count().sort_values(ascending=False).to_dict(),
)
json.dump(summary, open(f"{OUT}/prep_summary.json","w"), indent=2)
print(json.dumps(summary, indent=2))
