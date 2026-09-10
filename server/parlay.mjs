import markets from '../config/parlay-markets.json' with {type:'json'};

export const SPORT_KEYS={nfl:'americanfootball_nfl',ncaa:'americanfootball_ncaaf'};
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
    const line=market==='atd'&&(r.line==null||r.line===0)?.5:r.line;
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
export async function fetchParlay(sport,key,fetcher=fetch){
  if(!SPORT_KEYS[sport])throw new Error('Unsupported sport');
  if(!key)throw new Error('Parlay API key is not configured');
  const get=async(endpoint,params)=>{
    const url=new URL(`https://parlay-api.com/v1/sports/${SPORT_KEYS[sport]}/${endpoint}`);
    for(const [k,v] of Object.entries(params))url.searchParams.set(k,v);
    const r=await fetcher(url,{headers:{'X-API-Key':key,'Accept':'application/json'},signal:AbortSignal.timeout(45000)});
    if(!r.ok)throw new Error(`Parlay ${endpoint} returned HTTP ${r.status}`);
    const body=await r.json();
    if(!Array.isArray(body))throw new Error(`Unexpected Parlay ${endpoint} response`);
    return body;
  };
  const [raw, games]=await Promise.all([
    sport==='nfl'?get('props',{markets:Object.keys(MARKET_MAP).join(','),limit:'10000'}):Promise.resolve([]),
    get('odds',{markets:'h2h,spreads,totals',regions:'us',oddsFormat:'american'})
  ]);
  return {provider:'parlay',sport,generated_at:new Date().toISOString(),props:normalizeProps(raw),games_raw:games,
    coverage:{raw_props:raw.length,possibly_truncated:raw.length>=10000},odds_status:'loaded'};
}
