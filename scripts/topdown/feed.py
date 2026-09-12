"""Normalize exact two-sided markets. Never join different lines or periods."""
from .model import uid, decimal, stamp

PROP_MARKETS={'player_passing_yards','player_rushing_yards','player_receiving_yards','player_receptions','player_passing_tds'}


def half_line(line):
    return isinstance(line,(float,int)) and abs(line*2-round(line*2))<1e-9 and round(line*2)%2!=0


def normalize(games, props):
    out=[]
    for g in games:
        if not stamp(g.get('commence_time')):continue
        base={'event':uid(g.get('home_team'),g.get('away_team'),stamp(g['commence_time'])),'home':g.get('home_team'),'away':g.get('away_team'),'kickoff':g['commence_time']}
        if not base['home'] or not base['away']:continue
        for book in g.get('bookmakers',[]):
            for m in book.get('markets',[]):
                kind=m.get('key');rows=m.get('outcomes',[])
                if kind not in ('h2h','spreads','totals') or len(rows)!=2:continue
                sides=['Over','Under'] if kind=='totals' else [base['home'],base['away']]
                matched=[next((r for r in rows if r.get('name')==side),None) for side in sides]
                if not all(matched):continue
                prices=[r.get('price') for r in matched]
                if not all(decimal(x) for x in prices):continue
                line=None if kind=='h2h' else matched[0].get('point')
                if kind=='spreads' and (line is None or matched[1].get('point') != -line):continue
                if kind=='totals' and (line is None or matched[1].get('point') != line):continue
                selection=uid(base['event'],kind,line,'full_game_including_overtime')
                out.append(dict(base,selection=selection,market=kind,line=line,sides=sides,book=book.get('key'),prices=prices,updated_at=m.get('last_update') or book.get('last_update'),no_refund=half_line(line),rules='full_game_including_overtime'))
    for r in props:
        if r.get('market_key') not in PROP_MARKETS or not stamp(r.get('commence_time')) or r.get('is_dfs_flat_payout') or r.get('dfs_normalized'):continue
        if not r.get('player') or not r.get('home_team') or not r.get('away_team'):continue
        event=uid(r['home_team'],r['away_team'],stamp(r['commence_time']));prices=[r.get('over_price'),r.get('under_price')]
        if not all(decimal(x) for x in prices):continue
        out.append(dict(event=event,selection=uid(event,r['market_key'],r['player'],r.get('line'),'full_game'),home=r['home_team'],away=r['away_team'],kickoff=r['commence_time'],market=r['market_key'],player=r['player'],line=r.get('line'),sides=['Over','Under'],book=r.get('bookmaker'),prices=prices,updated_at=r.get('last_update'),no_refund=half_line(r.get('line')),rules='full_game_player_must_participate'))
    return out
