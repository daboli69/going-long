"""Market-led research. No price is a known true probability."""
import hashlib
import json
import math
import statistics
from urllib.parse import urlparse
from datetime import datetime, timezone

VERSION = 'topdown-1'
SHARP = {'pinnacle', 'circa'}
RECREATIONAL = {'draftkings', 'fanduel', 'betmgm', 'caesars', 'fanatics', 'betrivers'}


def stamp(value):
    try:
        d = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return d.timestamp() if d.tzinfo else None
    except (ValueError, TypeError):
        return None


def uid(*parts):
    return hashlib.sha256(json.dumps(parts, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def decimal(price):
    if not isinstance(price, (int, float)) or isinstance(price, bool) or not math.isfinite(price) or abs(price) < 100:
        return None
    return 1 + price / 100 if price > 0 else 1 + 100 / -price


def fair_pair(prices):
    """Two common margin-removal assumptions; both conditional on no refund."""
    dec = [decimal(x) for x in prices]
    if len(dec) != 2 or not all(dec):
        return None
    q = [1 / x for x in dec]
    if not 1 <= sum(q) <= 1.30:
        return None
    lo, hi = 0., 10.
    for _ in range(70):
        k = (lo + hi) / 2
        if sum(x ** k for x in q) > 1:lo = k
        else:hi = k
    return {'proportional': [x / sum(q) for x in q], 'power': [x ** ((lo + hi) / 2) for x in q], 'overround': sum(q) - 1}


def shrink_rating(observed, games, league, week, prior_games=None):
    """Normal-normal posterior with equal per-game observation variance.
    Prior strengths are explicit policy values, not fitted betting lift.
    """
    prior = prior_games if prior_games is not None else (8 if week <= 4 else 4)
    if games < 0 or prior <= 0:raise ValueError('Invalid evidence weight')
    weight = games / (games + prior)
    return {'rating': league + weight * (observed - league), 'data_weight': weight, 'prior_games': prior}


def secondary_baseline(season_rate, form_rate, games, league_rate, week):
    """40% season / 60% recent form, then shrink. Rates must be pregame venue splits.
    Do not count those overlapping windows as independent observations.
    """
    if any(x is None for x in (season_rate, form_rate, league_rate)):return None
    return shrink_rating(.4 * season_rate + .6 * form_rate, games, league_rate, week)


def compound_points(td_rate, fg_rate, max_points=100):
    """Secondary NFL scoring check: independent 7-point TD and 3-point FG counts.
    Omits missed PATs, two-point tries and safeties; not an actionable price model.
    """
    if min(td_rate, fg_rate) < 0:raise ValueError('Negative scoring rate')
    out = [0.] * (max_points + 1)
    for td in range(max_points // 7 + 1):
        a = math.exp(-td_rate + td * math.log(td_rate) - math.lgamma(td + 1)) if td_rate else float(td == 0)
        for fg in range((max_points - td * 7) // 3 + 1):
            b = math.exp(-fg_rate + fg * math.log(fg_rate) - math.lgamma(fg + 1)) if fg_rate else float(fg == 0)
            out[7 * td + 3 * fg] += a * b
    return {'mass': out, 'omitted_tail': 1 - sum(out), 'method': 'secondary compound scoring check; not Dixon-Coles'}


def inactive_gate(report, q, now):
    """A timer is insufficient. Require both official team reports and their provenance."""
    kickoff = stamp(q['kickoff'])
    if kickoff is None or not 0 < kickoff - now <= 90 * 60:return False
    if not report or report.get('event') != q['event']:return False
    teams = report.get('teams', [])
    if len(teams) != 2 or {t.get('name') for t in teams} != {q['home'], q['away']}:return False
    for t in teams:
        published, verified = stamp(t.get('published_at')), stamp(t.get('verified_at'))
        if t.get('status') != 'official_confirmed' or (not t.get('source_url', '').startswith('https://') or urlparse(t.get('source_url','')).hostname not in ('www.nfl.com','nfl.com')) or not t.get('source_sha256') or not isinstance(t.get('inactive_players'), list):return False
        if published is None or verified is None or not kickoff - 100 * 60 <= published <= verified <= now:return False
    return True


def fresh(q, now, ttl=180):
    t, kickoff = stamp(q.get('updated_at')), stamp(q.get('kickoff'))
    return t is not None and kickoff is not None and 0 <= now - t <= ttl and kickoff > now and all(decimal(x) for x in q['prices'])


def odds_band(d):
    return '<1.67' if d < 1.67 else '1.67–2.00' if d <= 2 else '2.01–3.00' if d <= 3 else '>3.00'


def evaluate(quotes, reports, now, bankroll=1000, min_ev=.03, min_sharps=2, previous=None, calibration_penalty=0):
    buckets = {}
    for q in quotes:
        if fresh(q, now):buckets.setdefault(q['selection'], {})[q['book']] = q
    predictions, arbs = [], []
    for key, books in buckets.items():
        sharps = [(b, q, fair_pair(q['prices'])) for b, q in books.items() if b in SHARP]
        sharps = [(b, q, f) for b, q, f in sharps if f]
        # Avoid treating asynchronous price changes as simultaneous opportunities.
        if sharps:
            latest = max(stamp(q['updated_at']) for _, q, _ in sharps)
            sharps = [(b, q, f) for b, q, f in sharps if latest - stamp(q['updated_at']) <= 60]
        for book, q in books.items():
            if book not in RECREATIONAL:continue
            for side in (0, 1):
                if not sharps:continue
                values = [f['proportional'][side] for _, _, f in sharps]
                raw = statistics.median(values)
                conservative = max(0, min([raw] + [f['power'][side] for _, _, f in sharps]) - .01 - calibration_penalty)
                dec = decimal(q['prices'][side]); ev = conservative * dec - 1
                reasons = []
                if len(sharps) < min_sharps:reasons.append('Not enough fresh designated reference books')
                if max(values) - min(values) > .03:reasons.append('Reference books disagree by more than 3 percentage points')
                if any(abs(stamp(s['updated_at']) - stamp(q['updated_at'])) > 60 for _, s, _ in sharps):reasons.append('Book timestamps are not closely aligned')
                if not q['no_refund']:reasons.append('Refund probability or settlement rules are unresolved')
                if not inactive_gate(reports.get(q['event']), q, now):reasons.append('Both official inactive reports have not been verified in the final window')
                if q.get('player') and any(q['player'] in team.get('inactive_players',[]) for team in (reports.get(q['event']) or {}).get('teams',[])):reasons.append('Player appears on an official inactive list')
                if ev < min_ev:reasons.append(f'Below the {100*min_ev:g}% minimum estimated return')
                old = (previous or {}).get(key + '|' + str(side)); tags = ['price_disagreement']
                movement = None
                if old and 0 < now - old['at'] <= 900:
                    movement = raw - old['probability']
                    if movement >= .015:tags.append('reference_price_moved')
                stake = bankroll * min(.01, .25 * max(0, ev / (dec - 1))) if not reasons else 0
                predictions.append(dict(id=uid(VERSION,key,book,side,int(now)),event=q['event'],selection=key,market=q['market'],line=q['line'],player=q.get('player'),home=q['home'],away=q['away'],kickoff=q['kickoff'],book=book,side=q['sides'][side],side_index=side,odds=dec,american=q['prices'][side],raw_probability=raw,probability=conservative,ev=ev,proposed_stake=stake,odds_band=odds_band(dec),actionable=not reasons,reasons=reasons,tags=tags,movement=movement,reference_books=[b for b,_,_ in sharps],reference_times=[s['updated_at'] for _,s,_ in sharps],quoted_at=q['updated_at'],model_version=VERSION,probability_type='conditional_on_no_refund',observed_at=datetime.fromtimestamp(now,timezone.utc).isoformat(),no_refund=q['no_refund']))
        executable = [q for b,q in books.items() if b in RECREATIONAL and q['no_refund']]
        if len(executable) >= 2:
            legs = [max(executable, key=lambda q:decimal(q['prices'][i])) for i in (0,1)]
            ds = [decimal(q['prices'][i]) for i,q in enumerate(legs)];cost = sum(1/d for d in ds)
            if legs[0]['book'] != legs[1]['book'] and cost < .995 and abs(stamp(legs[0]['updated_at'])-stamp(legs[1]['updated_at'])) <= 30:
                arbs.append({'selection':key,'event':legs[0]['event'],'return_if_executable':1/cost-1,'stakes_per_100':[100/d/cost for d in ds],'books':[q['book'] for q in legs],'actionable':inactive_gate(reports.get(legs[0]['event']),legs[0],now),'note':'Displayed-price candidate. Limits, accepted stakes and matching void rules are not verified.'})
    return predictions, arbs


def grade(prediction, result):
    if stamp(result.get('observed_at')) is None or stamp(result['observed_at']) <= stamp(prediction['kickoff']):return None
    if result.get('status') not in ('win','loss','refund','void'):return None
    status = result['status']
    return 100 * (prediction['odds'] - 1) if status=='win' else -100 if status=='loss' else 0


def performance(predictions, settlements, now):
    """Only frozen prospective actionable selections; one pick per event/market/side.
    No claims of independence for multiple selections in one game.
    """
    groups = {}; seen = set()
    for p in sorted(predictions,key=lambda p:p['observed_at']):
        decision=(p['event'],p['selection'],p['side'])
        if decision in seen or not p['actionable'] or stamp(p['observed_at']) >= stamp(p['kickoff']):continue
        seen.add(decision);r=settlements.get(p['id'])
        if not r or stamp(r['observed_at']) is None or stamp(r['observed_at']) >= now:continue
        profit=grade(p,r)
        if profit is None:continue
        b=groups.setdefault(p['odds_band'],{'bets':0,'resolved':0,'profit':0,'squared_error':0,'games':set()})
        b['bets']+=1;b['profit']+=profit;b['games'].add(p['event'])
        if r['status'] in ('win','loss'):
            b['resolved']+=1;b['squared_error']+=(p['probability']-int(r['status']=='win'))**2
    return {band:dict(b,roi=b['profit']/(100*b['bets']),games=len(b['games']),brier=b['squared_error']/b['resolved'] if b['resolved'] else None) for band,b in groups.items()}
