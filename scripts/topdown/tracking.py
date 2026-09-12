"""Freeze prospective research separately from actionable alerts. Never select by outcome."""
from .model import uid,stamp


def track_predictions(journal,predictions):
    existing={p['id'] for p in journal.rows('prediction') if p.get('tracking_group')}
    count=0
    for p in sorted(predictions,key=lambda p:p.get('observed_at','')):
        if p.get('tracking_group') or stamp(p.get('observed_at')) is None or stamp(p['observed_at']) >= (stamp(p.get('kickoff')) or 0):continue
        key=uid('all_model',p['event'],p['selection'],p['side'])
        if key in existing:continue
        row=dict(p,id=key,tracking_group='all_model',origin_prediction_id=p['id'],actionable=False,proposed_stake=0,tracking_note='First recorded pregame price-model estimate; includes blocked checks. Hypothetical $100, not an accepted bet.')
        journal.append('prediction',key,row);existing.add(key);count+=1
    return count


def collect_board(journal,root,now):
    import subprocess,json
    from datetime import datetime,timezone
    from .model import odds_band
    result=subprocess.run(['node',str(root/'scripts/collect_model_plays.cjs')],cwd=root,capture_output=True,text=True,encoding='utf-8',timeout=90,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:raise RuntimeError('Board collection failed: '+result.stderr[-300:])
    rows=json.loads(result.stdout);existing={p['id'] for p in journal.rows('prediction') if p.get('tracking_group')};count=0
    # Freeze only after collection; a request crossing kickoff cannot create a pregame record.
    at=datetime.now(timezone.utc).isoformat()
    markets={'spread':'spreads','total':'totals','moneyline':'h2h','pass_yds':'player_passing_yards','rush_yds':'player_rushing_yards','rec_yds':'player_receiving_yards','receptions':'player_receptions','pass_tds':'player_passing_tds'}
    for c in rows:
        if stamp(c['kickoff'])<=stamp(at):continue
        group=c['tracking_group'];key=uid(group,c['contract'])
        if key in existing:continue
        market=markets.get(c['market'],c['market']);side=c['side'];side_index=1 if side in ('Under','Away') else 0
        p=dict(id=key,tracking_group=group,event=c['event'],selection=c['contract'],sport=c['sport'],home=c['home'],away=c['away'],kickoff=c['kickoff'],player=c['player'] if c['kind']=='prop' else None,profile_id=c.get('profileId'),market=market,line=c['line'],side=side,side_index=side_index,book=c['book'],odds=c['dec'],american=c['odds'],probability=c['prob'],raw_probability=c['prob'],ev=c['ev'],odds_band=odds_band(c['dec']),actionable=False,proposed_stake=0,reasons=['Automatic hypothetical tracking; not an alert-qualified or accepted bet'],observed_at=at,quoted_at=c['updatedAt'],model_version='board-tracking-1',evidence=c.get('flags',[]))
        journal.append('prediction',key,p);existing.add(key);count+=1
    return count
