"""
Self-contained regenerator for the Kuala Kangsar SNHT figure (fig13).
Reads fig13_data.csv (produced by the homogenization pipeline) and rebuilds the
3-panel plot. Needs only numpy, pandas, matplotlib — no pipeline dependency.

fig13_data.csv columns:
  year            calendar year (station reports every year -> full-length reference)
  candidate_norm  candidate annual total / its own mean (ratio-normalized)
  reference_norm  distance-weighted neighbour reference, same ratio space
  z               standardized candidate-minus-reference anomaly  = (q - mean q)/sd q
  T_k             SNHT statistic if the series is split BEFORE this year
                  T_k = k*mean(z[:k])^2 + (n-k)*mean(z[k:])^2   (NaN at the first row)

Break = the year of max T_k; significant if Tmax > the Monte-Carlo 95% threshold
(8.66 for n=62; see fig13_meta.txt).
"""
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

d = pd.read_csv("fig13_data.csv")
meta = dict(l.split("=", 1) for l in open("fig13_meta.txt").read().splitlines())
brk = int(meta["break_year"]); Tmax = float(meta["Tmax"]); cv = float(meta["SNHT_95_threshold"])
z1 = float(meta["z_mean_before"]); z2 = float(meta["z_mean_after"]); station = meta["station"]
yr = d.year.values; n = len(d)

C = dict(cand="#c1662a", ref="#2f6f9f", z="#33414e", mean="#2f6f9f",
         brk="#d9534f", grid="#dde1e5", fill="#f6d9c6", thr="#888")
plt.rcParams.update({"font.size": 10, "figure.dpi": 130, "axes.edgecolor": "#888"})
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(10.5, 10.2))

# (1) candidate vs reference
ax1.plot(yr, d.candidate_norm, "o-", color=C["cand"], ms=3.2, lw=1.05, label="candidate (normalized)")
ax1.plot(yr, d.reference_norm, "-", color=C["ref"], lw=2.2, label="neighbour reference (full record length)")
ax1.fill_between(yr, d.candidate_norm, d.reference_norm, where=yr < brk,
                 color=C["fill"], alpha=.7, label="candidate above reference (pre-break)")
ax1.axvline(brk, color=C["brk"], ls=":", lw=1.4); ax1.axhline(1, color="#bbb", ls=":", lw=.8)
ax1.set_ylabel("rainfall / mean"); ax1.set_title(f"{station} ({n} yr) — SNHT relative detection")
ax1.legend(frameon=False, fontsize=8.2, loc="upper left"); ax1.grid(color=C["grid"], lw=.6)
ax1.set_xlim(yr[0]-1, yr[-1]+1)

# (2) standardized anomaly with segment means
ax2.axhline(0, color="#bbb", lw=.8)
ax2.plot(yr, d.z, "o-", color=C["z"], ms=3.2, lw=1.05, label="standardized anomaly z (candidate - reference)")
ax2.hlines(z1, yr[0], brk, color=C["mean"], lw=2.6); ax2.hlines(z2, brk, yr[-1], color=C["mean"], lw=2.6)
ax2.annotate(f"mean z = {z1:+.2f}", (yr[0]+1, z1+.2), color=C["mean"], fontsize=9)
ax2.annotate(f"mean z = {z2:+.2f}", (brk+1, z2-.32), color=C["mean"], fontsize=9)
ax2.annotate("", xy=(brk, z2), xytext=(brk, z1), arrowprops=dict(arrowstyle="->", color=C["brk"], lw=1.8))
ax2.axvline(brk, color=C["brk"], ls=":", lw=1.4)
ax2.set_ylabel("z"); ax2.set_title("(2) The break shifts the MEAN of z")
ax2.legend(frameon=False, fontsize=8.2, loc="upper right"); ax2.grid(color=C["grid"], lw=.6)
ax2.set_xlim(yr[0]-1, yr[-1]+1)

# (3) T(k) scan
ax3.plot(yr, d.T_k, color=C["ref"], lw=1.8)
ax3.axhline(cv, color=C["thr"], ls="--", lw=1.4)
ax3.text(yr[1], cv+0.4, f"Monte-Carlo 95% threshold = {cv:.1f}", fontsize=8.5, color=C["thr"])
ax3.plot(brk, Tmax, "o", color=C["brk"], ms=7)
ax3.annotate(f"Tmax={Tmax:.1f} at {brk}", (brk, Tmax), textcoords="offset points",
             xytext=(8, -2), fontsize=9, color=C["brk"])
ax3.axvline(brk, color=C["brk"], ls=":", lw=1.3)
ax3.set_ylabel("T(k)"); ax3.set_xlabel("Year / candidate split point k")
ax3.set_title("(3) The T statistic peaks at the split that best explains the mean shift")
ax3.grid(color=C["grid"], lw=.6); ax3.set_xlim(yr[0]-1, yr[-1]+1)

fig.tight_layout()
fig.savefig("fig13_fulllength_reference_break.png", dpi=150, bbox_inches="tight")
print("wrote fig13_fulllength_reference_break.png")
