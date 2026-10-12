import pandas as pd, numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
OUT='/home/claude/homog/out'
meta=pd.read_csv(f'{OUT}/stations.csv').set_index('station_name')
raw=pd.read_pickle(f'{OUT}/monthly.pkl'); hom=pd.read_pickle(f'{OUT}/monthly_homog_napreserve.pkl')
climb=pd.read_csv(f'{OUT}/breaks_climatol.csv'); inv=pd.read_csv(f'{OUT}/break_inventory.csv')
fac=pd.read_csv(f'{OUT}/factors_climatol.csv')
adj=climb.station.unique()
picks=meta.loc[meta.index.isin(adj)].sort_values('n_years',ascending=False).head(6).index.tolist()
C=dict(raw='#9aa4ad',hom='#2f6f9f',brk='#d9534f',grid='#dde1e5')
plt.rcParams.update({'font.size':10,'figure.dpi':130,'axes.edgecolor':'#888'})
fig,axes=plt.subplots(3,2,figsize=(12,10)); axes=axes.ravel(); yr=raw.index.year
for ax,s in zip(axes,picks):
    r=raw[s].groupby(yr).sum(min_count=12); h=hom[s].groupby(yr).sum(min_count=12)
    ax.plot(r.index,r.values,color=C['raw'],lw=1.6,label='raw',zorder=2)
    ax.plot(h.index,h.values,color=C['hom'],lw=1.6,label='Climatol-homogenized',zorder=3)
    for _,br in climb[climb.station==s].iterrows():
        by=int(br.break_year); ax.axvline(by,color=C['brk'],ls='--',lw=1.1,zorder=1)
        frr=fac[(fac.station==s)&(fac.seg_end==by-1)]
        if len(frr): ax.annotate(f'x{frr.factor.iloc[0]:.2f}',(by,ax.get_ylim()[1]),fontsize=7.5,color=C['brk'],ha='center',va='top')
    ax.set_title(f'{s[:38]}  ·  {int(meta.loc[s,"n_years"])} yr · {meta.loc[s,"region"]}',fontsize=9.5)
    ax.set_ylabel('annual rainfall (in)'); ax.grid(color=C['grid'],lw=.6)
axes[0].legend(frameon=False,fontsize=8.5)
fig.suptitle('Raw vs Climatol-homogenized annual totals — 6 longest ADJUSTED stations (dashed = break, xf = applied factor)',y=1.0,fontsize=11.5)
fig.tight_layout(); fig.savefig(f'{OUT}/fig6_longest6_adjusted.png',dpi=150,bbox_inches='tight'); print('fig6 saved; picks:',picks)
