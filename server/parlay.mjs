import markets from '../config/parlay-markets.json' with {type:'json'};

export const SPORT_KEYS={nfl:'americanfootball_nfl',ncaa:'americanfootball_ncaaf',mlb:'baseball_mlb'};
export const MARKET_MAP=Object.fromEntries(Object.entries(markets).flatMap(([market,keys])=>keys.map(key=>[key,market])));
const validNumber=v=>typeof v==='number'&&Number.isFinite(v);
const validOdds=v=>validNumber(v)&&Math.abs(v)>=100?v:null;
export function normalizeProps(rows, now=Date.now()){
  if(!Array.isArray(rows))throw new Error('Unexpected Parlay props response');
  const out=new Map();
  for(const r of rows){
    const market=MARKET_MAP[r.market_key];
    if(!market||!r.player||!r.bookmaker)continue;
    const kickoff=r.commence_time||null;
    if(kickoff&&(!Number.isFinite(Date.parse(kickoff))||Date.parse(kickoff)<=now))continue;
    // Some books use the anytime key for 2+ and 3+ TD alternatives.
    const line=['atd','first_td'].includes(market)&&(r.line==null||r.line===0)?.5:r.line;
    if(!validNumber(line))continue;
    const stamp=r.last_update;
    const updatedAt=typeof stamp==='number'?new Date(stamp>1e12?stamp:stamp*1000).toISOString():stamp||null;
    const eventId=r.canonical_event_id||r.event_id||`player:${r.game_date||'unknown'}:${r.player}`;
    const quoteKey=JSON.stringify([eventId,r.bookmaker,market,r.player,line]);
    // DFS comparison prices are synthetic, not straight-bet payouts.
    const dfs=Boolean(r.is_dfs_flat_payout||r.dfs_normalized||['prizepicks','betr','pick6','sleeper','underdog'].includes(r.bookmaker));
    const p={quoteKey,eventId,player:r.player,team:'',opp:'',homeName:r.home_team||'',awayName:r.away_team||'',
      market,line,book:r.bookmaker_title||r.bookmaker,bookKey:r.bookmaker,
      overOdds:dfs?null:validOdds(r.over_price),underOdds:dfs?null:validOdds(r.under_price),
      source:'parlay',updatedAt,kickoff,dfs,gameDate:r.game_date||null};
    const old=out.get(quoteKey);
    if(!old||(Date.parse(updatedAt)||0)>(Date.parse(old.updatedAt)||0))out.set(quoteKey,p);
  }
  return [...out.values()];
}
export function normalizePeriods(rows){
  const quotes=new Map();
  for(const r of rows||[]){
    const period=String(r.period_key||'').toUpperCase();
    if(!['Q1','1H'].includes(period)||!r.source||!r.match_id)continue;
    if(!['spread','total','team_total','h2h'].includes(r.market)||!validOdds(r.price))continue;
    if(r.market!=='h2h'&&!validNumber(r.line))continue;
    if(!['home','away','over','under','draw'].includes(r.side))continue;
    if(r.market==='team_total'&&!['home','away'].includes(r.team))continue;
    const key=JSON.stringify([r.match_id,r.source,period,r.market,r.team||null,r.side,r.line??null]);
    const kickoff=r.kickoff||r.commence_time||null;
    const observed=r.last_observed_ms||r.timestamp_ms;
    const updatedAt=r.updatedAt||r.updated_at||(validNumber(observed)?new Date(observed).toISOString():null);
    const q={...r,kickoff,updatedAt,period_key:period,quoteKey:key,inPlay:r.inPlay===true||!(Date.parse(kickoff)>Date.now())};
    const old=quotes.get(key);
    if(!old||(validNumber(r.age_seconds)&&(!validNumber(old.age_seconds)||r.age_seconds<old.age_seconds)))quotes.set(key,q);
  }
  const result=[...quotes.values()],threeWay=new Set(result.filter(q=>q.market==='h2h'&&q.side==='draw').map(q=>JSON.stringify([q.match_id,q.source,q.period_key])));
  for(const q of result)q.threeWay=threeWay.has(JSON.stringify([q.match_id,q.source,q.period_key]));
  return result;
}
export function periodsFromGames(events){
  const rows=[];
  for(const event of events||[])for(const book of event.bookmakers||[])for(const market of book.markets||[]){
    const key=market.key?.toLowerCase()||'';
    const period=/(^|_)(1h|h1|1st_half)($|_)/.test(key)?'1H':/(^|_)(1q|q1|1st_quarter)($|_)/.test(key)?'Q1':null;
    const kind=key.includes('team_total')?'team_total':key.includes('spread')?'spread':key.includes('total')?'total':(key.includes('h2h')||key.includes('moneyline'))?'h2h':null;
    if(!period||!kind)continue;
    for(const o of market.outcomes||[]){
      const side=o.name===event.home_team?'home':o.name===event.away_team?'away':String(o.name).toLowerCase();
      const team=o.description===event.home_team?'home':o.description===event.away_team?'away':null;
      rows.push({match_id:event.canonical_event_id||event.id,source:book.key,home_team:event.home_team,away_team:event.away_team,
        period_key:period,market:kind,side,team,line:o.point,price:o.price,kickoff:event.commence_time,
        inPlay:!(Date.parse(event.commence_time)>Date.now()),updated_at:market.last_update||book.last_update});
    }
  }
  return normalizePeriods(rows);
}
export async function fetchParlay(sport,key,fetcher=fetch){
  if(!SPORT_KEYS[sport])throw new Error('Unsupported sport');
  if(!key)throw new Error('Parlay API key is not configured');
  const get=async(endpoint,params)=>{
    const url=new URL(`https://parlay-api.com/v1/sports/${SPORT_KEYS[sport]}/${endpoint}`);
    for(const [k,v] of Object.entries(params))url.searchParams.set(k,v);
    const r=await fetcher(url,{headers:{'X-API-Key':key,'Accept':'application/json'},signal:AbortSignal.timeout(45000)});
    if(!r.ok)throw new Error(`Parlay ${endpoint} returned HTTP ${r.status}`);
    const body=await r.json();
    if(endpoint==='live/period_markets'){
      if(Array.isArray(body))return body;
      if(!Array.isArray(body?.results))throw new Error('Unexpected Parlay period response');
      return body.results;
    }
    if(!Array.isArray(body))throw new Error(`Unexpected Parlay ${endpoint} response`);
    return body;
  };
  if(sport==='mlb'){
    const keys=['player_home_runs','player_hits','player_hits_runs_rbis','player_strikeouts','player_total_bases'];
    const [batches,games]=await Promise.all([Promise.all(keys.map(markets=>get('props',{markets,limit:'10000'}).then(rows=>({market:markets,rows,status:'loaded'})).catch(()=>({market:markets,rows:[],status:'unavailable'})))),get('odds',{markets:'h2h,spreads,totals',regions:'us',oddsFormat:'american'})]);
    return {provider:'parlay',sport,generated_at:new Date().toISOString(),props:batches.flatMap(b=>b.rows),games_raw:games,coverage:{possibly_truncated:batches.some(b=>b.rows.length>=10000),markets:Object.fromEntries(batches.map(b=>[b.market,{status:b.status,rows:b.rows.length}]))}};
  }
  const derivativeKeys=Object.entries(markets).filter(([k])=>k==='first_td'||/_1[hq]$/.test(k)).flatMap(([,v])=>v);
  const [raw, games, periods, derivatives]=await Promise.all([
    sport==='nfl'?get('props',{markets:Object.keys(MARKET_MAP).join(','),limit:'10000'}).then(rows=>({rows,status:'loaded'})).catch(()=>({rows:[],status:'unavailable'})):Promise.resolve({rows:[],status:'not_applicable'}),
    get('odds',{markets:'h2h,spreads,totals',regions:'us',oddsFormat:'american'}).then(rows=>({rows,status:'loaded'})).catch(()=>({rows:[],status:'unavailable'})),
    get('live/period_markets',{period:'all'}).then(rows=>({rows,status:'loaded'})).catch(()=>({rows:[],status:'unavailable'})),
    sport==='nfl'?get('props',{markets:derivativeKeys.join(','),limit:'10000'}).then(rows=>({rows,status:'loaded'})).catch(()=>({rows:[],status:'unavailable'})):Promise.resolve({rows:[],status:'not_applicable'})
  ]);
  if(games.status==='unavailable'&&periods.status==='unavailable'&&(raw.status==='unavailable'||sport==='ncaa')&&derivatives.status!=='loaded')throw new Error('Unexpected or unavailable Parlay responses');
  return {provider:'parlay',sport,generated_at:new Date().toISOString(),props:normalizeProps([...raw.rows,...derivatives.rows]),games_raw:games.rows,props_status:raw.status,derivative_status:derivatives.status,
    period_quotes:[...periodsFromGames(games.rows),...normalizePeriods(periods.rows)],period_status:periods.status,
    coverage:{raw_props:raw.rows.length,derivative_props:derivatives.rows.length,possibly_truncated:raw.rows.length>=10000||derivatives.rows.length>=10000},odds_status:games.status};
}
