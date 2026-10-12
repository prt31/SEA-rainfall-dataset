"""Verification: inject known breaks into synthetic networks, check detection."""
import numpy as np
from homoglib import (snht_recursive, pmf_detect, build_reference,
                      neighbour_weights, haversine_km, snht_crit, maxF_crit)

rng = np.random.default_rng(2024)

# --- 1. SNHT critical values are sane vs literature (approx) ---
for n in [20, 40, 60]:
    print(f"SNHT crit n={n}: {snht_crit(n,0.95):.2f} (95%)   maxF crit: {maxF_crit(n,0.95):.2f}")

# --- 2. Detection power / false alarm on a synthetic regional network ---
T, S = 84, 40
# common regional signal (interannual) + station noise; ratio-like around 1.0
regional = 1.0 + 0.15*rng.standard_normal(T)
true_series = np.empty((T, S))
for s in range(S):
    true_series[:, s] = regional*(1+0.05*rng.standard_normal()) + 0.10*rng.standard_normal(T)

# inject a +18% multiplicative break at t=45 into 8 stations, known positions
broken = {}
data = true_series.copy()
for s in range(8):
    bt = 40 + s  # staggered
    data[bt:, s] *= 1.18
    broken[s] = bt

# normalize (ratio) and build reference from neighbours (all mutual here)
mean_i = np.nanmean(data, axis=0)
norm = data/mean_i
# fake coords in a compact cluster
lat = 3.0 + 0.3*rng.standard_normal(S); lon = 101.0 + 0.3*rng.standard_normal(S)
dist = haversine_km(lat, lon)
W = neighbour_weights(dist, nref=12, dmax=500, wd=40)
ref = build_reference(norm, W)
anom = norm - ref

hits = 0; false = 0; detected_stations = 0
for s in range(S):
    bks = snht_recursive(anom[:, s], level=0.95, min_seg=6)
    if s in broken:
        near = [b for b in bks if abs(b-broken[s]) <= 3]
        if near: hits += 1
        detected_stations += 1 if bks else 0
    else:
        false += len(bks)
print(f"\nSNHT relative detection: {hits}/8 injected breaks found (+/-3 yr); "
      f"false breaks on 32 clean stations: {false}")

# --- 3. PMF on a base series with trend + step ---
n = 70
t = np.arange(n)
base = 50 + 0.2*t + rng.standard_normal(n)*3
base[35:] += 12   # step
r = pmf_detect(base, level=0.95, min_seg=6)
print(f"PMF base-series: injected step at 35 -> detected at "
      f"{r['break_index'] if r else 'NONE'} (F={r['F']:.1f}, crit={r['crit']:.1f})" if r else "PMF: NONE")

# clean series false alarm
fa = sum(1 for _ in range(100) if pmf_detect(50+0.2*np.arange(60)+rng.standard_normal(60)*3, 0.95, 6))
print(f"PMF false-alarm rate on 100 clean trended series: {fa}%")
