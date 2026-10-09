import pandas as pd, numpy as np, glob
C=r"C:/Users/travi/OneDrive/Documents/ChatGPT/GOING/FantasyPoints/research/cache/"
ep=pd.concat([pd.read_parquet(C+f"ep_weekly_{y}.parquet") for y in range(2019,2026)])
ep['season']=ep.season.astype(int);ep['week']=ep.week.astype(int)
ep=ep[ep.position.isin(['QB','RB','WR','TE'])].copy()
st=pd.concat([pd.read_csv(C+f"stats_player_week_{y}.csv",usecols=['player_id','season','week','season_type','target_share','air_yards_share','wopr','carries','targets','attempts']) for y in range(2019,2026)])
st=st[st.season_type=='REG']
d=ep.merge(st[['player_id','season','week','target_share','air_yards_share','wopr']],on=['player_id','season','week'],how='left')
d=d.rename(columns={'total_fantasy_points':'act','total_fantasy_points_exp':'xfp'})
d['res']=d.act-d.xfp
d['touch']=d.rush_attempt.fillna(0)+d.rec_attempt.fillna(0)+d.pass_attempt.fillna(0)*0.0
d['vol']=np.where(d.position=='QB',d.pass_attempt+d.rush_attempt,d.rush_attempt+d.rec_attempt)
d['tdres']=(d.pass_touchdown+d.rush_touchdown+d.rec_touchdown)-(d.pass_touchdown_exp+d.rush_touchdown_exp+d.rec_touchdown_exp)
d['recres']=d.receptions-d.receptions_exp
d['yds_res']=(d.rec_yards_gained-d.rec_yards_gained_exp).fillna(0)+(d.pass_yards_gained-d.pass_yards_gained_exp).fillna(0)+(d.rush_yards_gained-d.rush_yards_gained_exp).fillna(0)
gm=pd.read_csv(C+'games.csv',usecols=['game_id','home_team','away_team','spread_line','total_line'])
d=d.merge(gm,on='game_id',how='left')
home=d.posteam==d.home_team
d['impl']=np.where(home,(d.total_line+d.spread_line)/2,(d.total_line-d.spread_line)/2)
d['spr']=np.where(home,d.spread_line,-d.spread_line)  # team favored by
d=d.sort_values(['player_id','season','week']).reset_index(drop=True)
g=d.groupby('player_id')
def tm(col,k): return g[col].transform(lambda s:s.shift(1).rolling(k,min_periods=3).mean())
def ew(col,h): return g[col].transform(lambda s:s.shift(1).ewm(halflife=h,min_periods=3).mean())
for c in ['act','xfp','res','vol','tdres','recres','yds_res','target_share','air_yards_share','wopr']:
    d[c+'_m8']=tm(c,8)
for c in ['act','xfp']:
    d[c+'_m3']=tm(c,3); d[c+'_m16']=tm(c,16)
    for h in [1.5,3,6]: d[f'{c}_e{h}']=ew(c,h)
d['res_m16']=tm('res',16)
d['n_prior']=g.cumcount()
d['y1']=g['act'].shift(-1)
d['y3']=g['act'].transform(lambda s:(s.shift(-1)+s.shift(-2)+s.shift(-3))/3)
d['y1_res']=g['res'].shift(-1)
d['y1_tdres']=g['tdres'].shift(-1); d['y1_recres']=g['recres'].shift(-1); d['y1_ydsres']=g['yds_res'].shift(-1)
d['y1_impl']=g['impl'].shift(-1); d['y3_impl']=g['impl'].transform(lambda s:(s.shift(-1)+s.shift(-2)+s.shift(-3))/3); d['y1_spr']=g['spr'].shift(-1)
d['impl_m8']=tm('impl',8)
d['y1_xfp']=g['xfp'].shift(-1)
d['ny']=g['season'].shift(-1)
d.to_parquet('panel.parquet')   # derived from public nflverse data only
print(d.shape, d.groupby('season').size())
