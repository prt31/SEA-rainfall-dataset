import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec

OUT = "/home/claude/homog/out"
MONTHS = ['Jan','Feb','March','April','May','June','July','Aug','Sept','Oct','Nov','Dec']
C = dict(clim="#2f6f9f", pmf="#c1662a", pmt="#4a8b6f", war="#d9534f", grid="#d9dde1")

inv   = pd.read_csv(f"{OUT}/break_inventory.csv")
meta  = pd.read_csv(f"{OUT}/stations.csv")
annual= pd.read_pickle(f"{OUT}/annual.pkl")
mon_na= pd.read_pickle(f"{OUT}/monthly_homog_napreserve.pkl")
monthly_raw = pd.read_pickle(f"{OUT}/monthly.pkl")
fac   = pd.read_csv(f"{OUT}/factors_climatol.csv")
rh    = pd.read_csv(f"{OUT}/breaks_rhtests.csv")
climb = pd.read_csv(f"{OUT}/breaks_climatol.csv")

plt.rcParams.update({"font.size":10,"axes.edgecolor":"#888","axes.linewidth":.8,
                     "figure.dpi":130})

# ---------- Fig 1: break-year distribution with WWII window ----------
fig, ax = plt.subplots(figsize=(10,4.2))
yrs = np.arange(1875,1959)
ch = climb.break_year.value_counts().reindex(yrs, fill_value=0)
ax.bar(yrs, ch.values, color=C["clim"], width=.9, label="Climatol breaks")
pmt_h = rh[rh.test=="PMT"].break_year.value_counts().reindex(yrs, fill_value=0)
ax.plot(yrs, pmt_h.values, color=C["pmt"], lw=1.4, label="RHtests PMT breaks")
ax.axvspan(1942,1946, color=C["war"], alpha=.15, label="WWII gap (1942–46)")
ax.axvspan(1946,1953, color="#e8a94b", alpha=.12, label="Post-war window (1946–53)")
ax.set_xlabel("Year"); ax.set_ylabel("Number of breaks detected")
ax.set_title("Detected inhomogeneities by year — Malaysia/Singapore rainfall (≤1958)")
ax.legend(frameon=False, fontsize=8.5, ncol=2); ax.set_xlim(1875,1958)
ax.grid(axis="y", color=C["grid"]); fig.tight_layout()
fig.savefig(f"{OUT}/fig1_breaks_by_year.png", dpi=140); plt.close(fig)

# ---------- Fig 2: before/after for high-confidence adjusted stations ----------
hi = inv[inv.confidence.isin(["high","medium-high"])].sort_values("n_years",ascending=False)
picks = hi.drop_duplicates("station").station.head(4).tolist()
fig, axes = plt.subplots(2,2, figsize=(11,6.4)); axes=axes.ravel()
for ax, st in zip(axes, picks):
    yr = annual.index.values
    raw_ann = monthly_raw[st].groupby(monthly_raw.index.year).sum(min_count=12).reindex(yr)
    hom_ann = mon_na[st].groupby(mon_na.index.year).sum(min_count=12).reindex(yr)
    ax.plot(yr, raw_ann.values, color="#999", lw=1.2, label="raw")
    ax.plot(yr, hom_ann.values, color=C["clim"], lw=1.4, label="homogenized")
    for by in climb[climb.station==st].break_year:
        ax.axvline(by, color=C["war"], ls="--", lw=1)
    ax.set_title(st[:42], fontsize=9); ax.grid(color=C["grid"], lw=.6)
    ax.set_ylabel("annual rainfall (in)")
axes[0].legend(frameon=False, fontsize=8)
fig.suptitle("Annual totals: raw vs Climatol-homogenized (dashed = break year)", y=1.0)
fig.tight_layout(); fig.savefig(f"{OUT}/fig2_before_after.png", dpi=140); plt.close(fig)

# ---------- Fig 3: station map, breaks highlighted ----------
fig, ax = plt.subplots(figsize=(7.6,7.2))
brk_st = set(climb.station)
m = meta.dropna(subset=["lat","lon"])
nb = m[~m.station_name.isin(brk_st)]; yb = m[m.station_name.isin(brk_st)]
ax.scatter(nb.lon, nb.lat, s=10, c="#b8c2cc", label="no break", edgecolor="none")
ax.scatter(yb.lon, yb.lat, s=34, c=C["war"], label="break detected", edgecolor="k", linewidth=.3)
ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
ax.set_title("Station network (≤1958) — stations with detected inhomogeneities")
ax.legend(frameon=False); ax.grid(color=C["grid"], lw=.6); ax.set_aspect(1.05)
fig.tight_layout(); fig.savefig(f"{OUT}/fig3_station_map.png", dpi=140); plt.close(fig)

# ---------- Fig 4: network timeline + confidence donut ----------
fig = plt.figure(figsize=(11,4.2)); gs = GridSpec(1,3, figure=fig, width_ratios=[2,2,1.3])
ax1 = fig.add_subplot(gs[0,0:2])
active = (monthly_raw.notna().groupby(monthly_raw.index.year).any().sum(axis=1))
ax1.fill_between(active.index, active.values, color=C["clim"], alpha=.85)
ax1.axvspan(1942,1946, color=C["war"], alpha=.18)
ax1.set_title("Active stations per year"); ax1.set_xlabel("Year"); ax1.set_ylabel("stations")
ax1.grid(color=C["grid"], lw=.6); ax1.set_xlim(1875,1958)
ax2 = fig.add_subplot(gs[0,2])
cc = inv[inv.detected_by_climatol==True].confidence.value_counts()
order=["high","medium-high","medium","low"]; cc=cc.reindex([o for o in order if o in cc.index])
cols={"high":"#2f6f9f","medium-high":"#5b9bd5","medium":"#e8a94b","low":"#c9c9c9"}
ax2.pie(cc.values, labels=cc.index, colors=[cols[i] for i in cc.index],
        autopct=lambda p:f"{int(round(p*cc.sum()/100))}", textprops={"fontsize":8})
ax2.set_title("Climatol breaks by confidence", fontsize=9.5)
fig.tight_layout(); fig.savefig(f"{OUT}/fig4_timeline_confidence.png", dpi=140); plt.close(fig)

print("figures written:",
      [f"fig{i}" for i in range(1,5)])
