"""
homoglib.py  -- core routines for a Climatol-method + RHtests-style pipeline.

Implements the published algorithms (not the R packages, which cannot be
installed in this sandbox):

 * Climatol method (Guijarro; Alexandersson & Moberg 1997):
     - ratio normalization of precipitation series (std=2 analogue)
     - distance-weighted neighbour REFERENCE built from normalized neighbours
     - SNHT (Standard Normal Homogeneity Test) on the candidate-minus-reference
       anomaly series, applied recursively for MULTIPLE breakpoints
     - multiplicative (ratio) segment adjustment to the most-recent segment
     - neighbour-based infilling of gaps (denormalized reference)

 * RHtestsV4 style (Wang, Wen & Wu 2007; Wang 2008):
     - penalized maximal F test (PMFmax): two-phase regression, a step in the
       mean superimposed on a common linear trend, no reference (base series)
     - t-form against a reference series (PMTmax)
   Critical values for both are obtained by Monte-Carlo of the null, which
   supplies the position penalty / multiplicity correction directly.
"""
import numpy as np
import pandas as pd

# ----------------------------------------------------------------------
# geography
# ----------------------------------------------------------------------
def haversine_km(lat, lon):
    lat = np.radians(np.asarray(lat, float)); lon = np.radians(np.asarray(lon, float))
    dlat = lat[:, None] - lat[None, :]
    dlon = lon[:, None] - lon[None, :]
    a = np.sin(dlat/2)**2 + np.cos(lat)[:, None]*np.cos(lat)[None, :]*np.sin(dlon/2)**2
    return 2*6371.0*np.arcsin(np.sqrt(np.clip(a, 0, 1)))

# ----------------------------------------------------------------------
# SNHT (Alexandersson) -- single shift, standardized series
# ----------------------------------------------------------------------
def snht_stat(z):
    """Max SNHT statistic and its position for standardized 1-D array z (no NaN)."""
    n = len(z)
    if n < 4:
        return 0.0, -1
    cs = np.cumsum(z)
    tot = cs[-1]
    a = np.arange(1, n)                    # split after index a-1 (1..n-1)
    z1 = cs[:-1] / a
    z2 = (tot - cs[:-1]) / (n - a)
    T = a*z1**2 + (n - a)*z2**2
    k = int(np.argmax(T))
    return float(T[k]), k+1                # break BEFORE position k+1 (0-based split index)

_snht_cache = {}
def snht_crit(n, level=0.95, nsim=2000, seed=12345):
    key = (n, level, nsim)
    if key in _snht_cache:
        return _snht_cache[key]
    rng = np.random.default_rng(seed + n)
    sims = np.empty(nsim)
    for i in range(nsim):
        z = rng.standard_normal(n)
        z = (z - z.mean())/z.std(ddof=1)
        sims[i], _ = snht_stat(z)
    cv = float(np.quantile(sims, level))
    _snht_cache[key] = cv
    return cv

def snht_recursive(series, level=0.95, min_seg=5, nsim=1500, _depth=0):
    """Return sorted list of 0-based break indices (split points) via recursive SNHT."""
    s = np.asarray(series, float)
    idx = np.where(~np.isnan(s))[0]
    if len(idx) < 2*min_seg:
        return []
    v = s[idx]
    z = (v - v.mean())/v.std(ddof=1) if v.std(ddof=1) > 0 else v*0
    T, kpos = snht_stat(z)
    if kpos < min_seg or (len(v)-kpos) < min_seg:
        return []
    cv = snht_crit(len(v), level, nsim)
    if T <= cv:
        return []
    brk = idx[kpos]                       # first index of the second segment (original coords)
    left  = s.copy();  left[brk:]  = np.nan
    right = s.copy();  right[:brk] = np.nan
    return sorted(set([brk]
                      + snht_recursive(left,  level, min_seg, nsim, _depth+1)
                      + snht_recursive(right, level, min_seg, nsim, _depth+1)))

# ----------------------------------------------------------------------
# RHtests style: penalized maximal F (two-phase regression, common trend)
# ----------------------------------------------------------------------
def _maxF(y):
    """Max F for a mean shift on top of a common linear slope; return (Fmax,pos)."""
    n = len(y)
    t = np.arange(n, dtype=float)
    # reduced model: y = a + b t  (df=2)
    X0 = np.column_stack([np.ones(n), t])
    beta0, *_ = np.linalg.lstsq(X0, y, rcond=None)
    rss0 = np.sum((y - X0@beta0)**2)
    best = (0.0, -1)
    for k in range(2, n-1):               # step after position k
        step = (t >= k).astype(float)
        X1 = np.column_stack([np.ones(n), t, step])   # common slope + intercept jump
        beta1, *_ = np.linalg.lstsq(X1, y, rcond=None)
        rss1 = np.sum((y - X1@beta1)**2)
        if rss1 <= 0:
            continue
        F = (rss0 - rss1) / (rss1 / (n - 3))
        if F > best[0]:
            best = (float(F), k)
    return best

_maxF_cache = {}
def maxF_crit(n, level=0.95, nsim=2000, seed=777):
    key = (n, level, nsim)
    if key in _maxF_cache:
        return _maxF_cache[key]
    rng = np.random.default_rng(seed + n)
    sims = np.empty(nsim)
    for i in range(nsim):
        sims[i], _ = _maxF(rng.standard_normal(n))
    cv = float(np.quantile(sims, level))
    _maxF_cache[key] = cv
    return cv

def pmf_detect(series, level=0.95, min_seg=5, nsim=1500):
    """Single most-significant PMF break on a base series (no reference)."""
    s = np.asarray(series, float)
    idx = np.where(~np.isnan(s))[0]
    if len(idx) < 2*min_seg:
        return None
    y = s[idx]
    F, k = _maxF(y)
    if k < min_seg or (len(y)-k) < min_seg:
        return None
    cv = maxF_crit(len(y), level, nsim)
    if F <= cv:
        return None
    return dict(break_index=int(idx[k]), F=float(F), crit=float(cv))

# ----------------------------------------------------------------------
# neighbour reference (ratio space)
# ----------------------------------------------------------------------
def build_reference(norm, W):
    """
    norm : (T, S) normalized values (ratios), NaN where missing
    W    : (S, S) neighbour weights, 0 on diagonal / non-neighbours
    returns (T,S) weighted-mean neighbour reference in ratio space.
    """
    X = np.where(np.isnan(norm), 0.0, norm)
    present = (~np.isnan(norm)).astype(float)
    num = X @ W.T            # (T,S): sum_j w_ij * x_jt
    den = present @ W.T      # (T,S): sum_j w_ij present
    ref = np.where(den > 0, num/den, np.nan)
    return ref

def neighbour_weights(dist, corr=None, nref=10, dmax=200.0, wd=60.0, min_corr=0.10):
    """Gaussian-by-distance weights, capped to nref nearest eligible neighbours."""
    S = dist.shape[0]
    W = np.zeros((S, S))
    for i in range(S):
        d = dist[i].copy(); d[i] = np.inf
        elig = d <= dmax
        if corr is not None:
            elig &= (corr[i] >= min_corr)
        cand = np.where(elig)[0]
        if len(cand) == 0:
            continue
        order = cand[np.argsort(d[cand])][:nref]
        w = np.exp(-0.5*(d[order]/wd)**2)
        W[i, order] = w
    return W
