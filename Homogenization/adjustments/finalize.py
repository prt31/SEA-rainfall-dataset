"""
Step 7-8: reconcile breaks -> confidence-classified inventory, and write
homogenized deliverables back in the ORIGINAL wide schema.
"""
import numpy as np, pandas as pd, json

OUT = "/home/claude/homog/out"
MONTHS = ['Jan','Feb','March','April','May','June','July','Aug','Sept','Oct','Nov','Dec']

meta   = pd.read_csv(f"{OUT}/stations.csv").set_index("station_name")
climb  = pd.read_csv(f"{OUT}/breaks_climatol.csv")
rh     = pd.read_csv(f"{OUT}/breaks_rhtests.csv")
fac    = pd.read_csv(f"{OUT}/factors_climatol.csv")
mon_na = pd.read_pickle(f"{OUT}/monthly_homog_napreserve.pkl")
mon_if = pd.read_pickle(f"{OUT}/monthly_homog_infilled.pkl")
LONG_MIN = 30

pmf = rh[rh.test == "PMF"]; pmt = rh[rh.test == "PMT"]

def near(tbl, st, yr, tol=2):
    c = tbl[tbl.station == st]
    return bool(len(c) and (np.abs(c.break_year.values - yr) <= tol).any())

# ---- break inventory with confidence + applied factor ----
inv = []
for _, r in climb.iterrows():
    st, yr = r.station, int(r.break_year)
    nyr = int(meta.loc[st, "n_years"]) if st in meta.index else 0
    is_long = nyr >= LONG_MIN
    cpmf, cpmt = near(pmf, st, yr), near(pmt, st, yr)
    if is_long and (cpmf and cpmt):
        conf = "high"
    elif is_long and (cpmf or cpmt):
        conf = "high" if cpmt else "medium-high"
    elif is_long:
        conf = "medium"          # long, Climatol-only
    else:
        conf = "low"             # short station, no cross-check possible
    # factor applied to the pre-break segment (seg_end == yr-1)
    fr = fac[(fac.station == st) & (fac.seg_end == yr-1)]
    factor = float(fr.factor.iloc[0]) if len(fr) else np.nan
    inv.append(dict(station=st, region=r.region, country=r.country,
                    break_year=yr, n_years=nyr, station_class=("long" if is_long else "short"),
                    detected_by_climatol=True, confirmed_pmf=cpmf, confirmed_pmt=cpmt,
                    confidence=conf, applied_factor=round(factor,4) if np.isfinite(factor) else np.nan,
                    lat=r.lat, lon=r.lon))
# rhtests-only breaks (no matching climatol break within +/-2 yr) -> informational
for _, r in rh.iterrows():
    st, yr = r.station, int(r.break_year)
    if not near(climb, st, yr):
        inv.append(dict(station=st, region=r.region, country=r.country, break_year=yr,
                        n_years=int(meta.loc[st,"n_years"]) if st in meta.index else 0,
                        station_class="long", detected_by_climatol=False,
                        confirmed_pmf=(r.test=="PMF"), confirmed_pmt=(r.test=="PMT"),
                        confidence="rhtests-only", applied_factor=np.nan,
                        lat=meta.loc[st,"lat"] if st in meta.index else np.nan,
                        lon=meta.loc[st,"lon"] if st in meta.index else np.nan))
inv = pd.DataFrame(inv).sort_values(["confidence","region","station","break_year"])
inv.to_csv(f"{OUT}/break_inventory.csv", index=False)

# ---- reshape homogenized matrix -> wide schema ----
metacols = ['distance_to_coast_km','elevation_m','lat_decimal','lon_decimal',
            'administrative_unit','country_modern','region']
src = pd.read_csv("/tmp/main_updated.csv")
src = src[src.year <= 1958]
meta_wide = src.groupby('station_name')[metacols].first()
adj_stations = set(climb.station.unique())
nbreaks = climb.groupby('station').break_year.count()

def to_wide(mon, label):
    m = mon.copy(); m.index = pd.MultiIndex.from_arrays(
        [mon.index.year, mon.index.month], names=['year','month'])
    long = m.stack().rename('rain').reset_index()
    long.columns = ['year','month','station_name','rain']
    wide = long.pivot_table(index=['station_name','year'], columns='month', values='rain')
    wide = wide.reindex(columns=range(1,13))
    wide.columns = MONTHS
    wide = wide.reset_index()
    # drop all-NaN station-years (outside observed/infilled span)
    wide = wide[wide[MONTHS].notna().any(axis=1)]
    wide['annual_computed'] = wide[MONTHS].sum(axis=1, min_count=12)
    wide = wide.merge(meta_wide, on='station_name', how='left')
    wide['adjusted'] = wide.station_name.isin(adj_stations)
    wide['n_breaks'] = wide.station_name.map(nbreaks).fillna(0).astype(int)
    cols = ['station_name','distance_to_coast_km','elevation_m','lat_decimal','lon_decimal',
            'administrative_unit','country_modern','region','year'] + MONTHS + \
           ['annual_computed','adjusted','n_breaks']
    wide = wide[cols].sort_values(['region','station_name','year'])
    wide.to_csv(f"{OUT}/{label}.csv", index=False)
    return wide

w_na = to_wide(mon_na, "malaysia_rainfall_homogenized_NApreserved")
w_if = to_wide(mon_if, "malaysia_rainfall_homogenized_infilled")

summary = dict(
    inventory_rows=int(len(inv)),
    climatol_breaks=int((inv.detected_by_climatol==True).sum()),
    by_confidence=inv.confidence.value_counts().to_dict(),
    stations_adjusted=int(len(adj_stations)),
    wide_NApreserved_rows=int(len(w_na)),
    wide_infilled_rows=int(len(w_if)),
    infilled_extra_station_years=int(len(w_if)-len(w_na)),
)
json.dump(summary, open(f"{OUT}/finalize_summary.json","w"), indent=2, default=str)
print(json.dumps(summary, indent=2, default=str))
