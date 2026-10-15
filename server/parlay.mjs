import markets from '../config/parlay-markets.json' with {type:'json'};

export const SPORT_KEYS={nfl:'americanfootball_nfl',ncaa:'americanfootball_ncaaf',mlb:'baseball_mlb'};
export const MARKET_MAP=Object.fromEntries(Object.entries(markets).flatMap(([market,keys])=>keys.map(key=>[key,market])));
const validNumber=v=>typeof v==='number'&&Number.isFinite(v);
const validOdds=v=>validNumber(v)&&Math.abs(v)>=100?v:null;
const validStringFields=(row,fields)=>fields.every(name=>row[name]==null||typeof row[name]==='string');
// Provider clocks must contain an explicit offset; host-local parsing is unsafe.
const awareTime=value=>{
  if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value))return false;
  const year=Number(value.slice(0,4)),month=Number(value.slice(5,7)),day=Number(value.slice(8,10)),leap=year%4===0&&(year%100!==0||year%400===0),days=[31,leap?29:28,31,30,31,30,31,31,30,31,30,31];
  return year>0&&month>=1&&month<=12&&day>=1&&day<=days[month-1]&&Number(value.slice(11,13))<=23&&Number(value.slice(14,16))<=59&&Number(value.slice(17,19))<=59&&Number.isFinite(Date.parse(value));
};
const validOddsRows=rows=>{
  const children=(row,name)=>{
    const value=Object.hasOwn(row,name)?row[name]:[];
    return Array.isArray(value)&&value.every(item=>item!=null&&typeof item==='object'&&!Array.isArray(item))?value:null;
  };
  return rows.every(event=>{
    if(!validStringFields(event,['id','canonical_event_id','home_team','away_team']))return false;
    const books=children(event,'bookmakers');
    return books!=null&&books.every(book=>{
      if(!validStringFields(book,['key']))return false;
      const markets=children(book,'markets');
      return markets!=null&&markets.every(market=>{
        const outcomes=children(market,'outcomes');
        return (!Object.hasOwn(market,'key')||typeof market.key==='string')&&outcomes!=null&&outcomes.every(outcome=>validStringFields(outcome,['name','description']));
      });
    });
  });
};
const timestamp=value=>{
  if(typeof value==='string')return awareTime(value)?value:null;
  if(!validNumber(value))return null;
  const date=new Date(value>1e12?value:value*1000);
  return Number.isFinite(date.getTime())?date.toISOString():null;
};
const milliseconds=value=>{
  if(!validNumber(value))return null;
  const date=new Date(value);
  return Number.isFinite(date.getTime())?date.toISOString():null;
};
const NON_RETRYABLE_503=new Set(['ENDPOINT_DISABLED','ASYNCAPI_NOT_LOADED','OPENAPI_UNAVAILABLE','INCIDENTS_PARSE_FAILED']);
const RETRY_DELAYS={DB_NOT_READY:30,PRIMARY_TIER_UNAVAILABLE:60,PROPS_BOARD_DEGRADED:5,PROPS_TEMPORARILY_BUSY:5,WARMING:5};
export function retryAfterSeconds(value,now=Date.now()){
  if(value==null||value==='')return 0;
  const seconds=Number(value),delay=Number.isFinite(seconds)?seconds:(Date.parse(value)-now)/1000;
  return Number.isFinite(delay)?Math.max(0,Math.min(60,delay)):0;
}
export class ParlayRequestError extends Error{
  constructor(stage,{status=null,code='UNKNOWN',providerMessage='',requestId='unknown',retryable=false,retryAfterSec=0}={}){
    super(`Parlay ${stage}: ${status?`HTTP ${status}`:'request failed'}; code=${code}; message=${providerMessage||'unavailable'}; request_id=${requestId}`);
    this.name='ParlayRequestError';Object.assign(this,{stage,status,code,providerMessage,requestId,retryable,retryAfterSec});
  }
}
const clean=(value,key)=>String(value||'').replaceAll(key,'[REDACTED]').replace(/[\r\n]/g,' ').slice(0,160);
async function responseFailure(response,stage,key){
  let body={};try{body=await response.clone().json();}catch{}
  const detail=body?.detail&&typeof body.detail==='object'?body.detail:{};
  const code=clean(body?.code||body?.error||detail.code||detail.error||body?.status||'UNKNOWN',key).toUpperCase();
  const providerMessage=clean(body?.message||detail.message||(typeof body?.detail==='string'?body.detail:''),key);
  const requestId=clean(response.headers.get('x-request-id')||'unknown',key);
  const headerDelay=retryAfterSeconds(response.headers.get('retry-after'));
  let retryable=[429,500,502,504].includes(response.status),retryAfterSec=Math.max(2,headerDelay);
  if(response.status===503){retryable=!NON_RETRYABLE_503.has(code);retryAfterSec=Math.max(RETRY_DELAYS[code]||5,headerDelay);}
  return new ParlayRequestError(stage,{status:response.status,code,providerMessage,requestId,retryable,retryAfterSec});
}
export function normalizeProps(rows, now=Date.now()){
  if(!Array.isArray(rows))throw new Error('Unexpected Parlay props response');
  const out=new Map();
  for(const r of rows){
    if(!r||typeof r!=='object'||Array.isArray(r)||!validStringFields(r,['market_key','player','bookmaker']))continue;
    let market=Object.hasOwn(MARKET_MAP,r.market_key)?MARKET_MAP[r.market_key]:null;
    if(market&&r.period!=null){
      if(typeof r.period!=='string')continue;
      const period=r.period.trim().toUpperCase();
      if(/_1[hq]$/.test(market)){
        if(period!==(market.endsWith('_1h')?'1H':'Q1'))continue;
      }else if(period!=='FULL'){
        const suffix=period==='1H'?'_1h':period==='Q1'?'_1q':null;
        if(!suffix||!Object.hasOwn(markets,market+suffix))continue;
        market+=suffix;
      }
    }
    if(!market||!r.player||!r.bookmaker)continue;
    const kickoff=r.commence_time||null;
    if(kickoff&&(!awareTime(kickoff)||Date.parse(kickoff)<=now))continue;
    // Some books use the anytime key for 2+ and 3+ TD alternatives.
    const line=['atd','first_td'].includes(market)&&(r.line==null||r.line===0)?.5:r.line;
    if(!validNumber(line))continue;
    const stamp=r.last_update;
    const updatedAt=timestamp(stamp);
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
    if(!r||typeof r!=='object'||Array.isArray(r)||!validStringFields(r,['match_id','source']))continue;
    const period=String(r.period_key||'').toUpperCase();
    if(!['Q1','1H'].includes(period)||!r.source||!r.match_id)continue;
    if(!['spread','total','team_total','h2h'].includes(r.market)||!validOdds(r.price))continue;
    if(r.market!=='h2h'&&!validNumber(r.line))continue;
    if(!['home','away','over','under','draw'].includes(r.side))continue;
    if(r.market==='team_total'&&!['home','away'].includes(r.team))continue;
    const key=JSON.stringify([r.match_id,r.source,period,r.market,r.team||null,r.side,r.line??null]);
    const kickoff=r.kickoff||r.commence_time||null;
    const observed=r.last_observed_ms||r.timestamp_ms;
    const updatedAt=timestamp(r.updatedAt||r.updated_at)||milliseconds(observed);
    const q={...r,kickoff,updatedAt,period_key:period,quoteKey:key,inPlay:r.inPlay===true||!awareTime(kickoff)||!(Date.parse(kickoff)>Date.now())};
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
export async function fetchParlay(sport,key,fetcher=fetch,{budgetMs=40000,requestMs=18000,sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms))}={}){
  if(!SPORT_KEYS[sport])throw new Error('Unsupported sport');
  if(!key)throw new Error('Parlay API key is not configured');
  const deadline=AbortSignal.timeout(budgetMs),started=Date.now();
  const get=async(endpoint,params)=>{
    const url=new URL(`https://parlay-api.com/v1/sports/${SPORT_KEYS[sport]}/${endpoint}`);
    for(const [k,v] of Object.entries(params))url.searchParams.set(k,v);
    for(let attempt=0;attempt<2;attempt++){
      deadline.throwIfAborted();
      const signal=AbortSignal.any([deadline,AbortSignal.timeout(requestMs)]);
      let r;
      try{r=await fetcher(url,{headers:{'X-API-Key':key,'Accept':'application/json'},signal});}
      catch(error){
        const failure=new ParlayRequestError(endpoint,{code:error?.name||'TRANSPORT_ERROR',providerMessage:'transport unavailable',retryable:true,retryAfterSec:2});
        if(attempt||Date.now()-started+failure.retryAfterSec*1000>=budgetMs)throw failure;
        await sleep(failure.retryAfterSec*1000);continue;
      }
      if(!r.ok){
        const failure=await responseFailure(r,endpoint,key);
        if(!failure.retryable||attempt||Date.now()-started+failure.retryAfterSec*1000>=budgetMs)throw failure;
        await sleep(failure.retryAfterSec*1000);continue;
      }
      const body=await r.json();
      const rows=endpoint==='live/period_markets'&&!Array.isArray(body)?body?.results:body;
      if(!Array.isArray(rows)||rows.some(row=>row==null||typeof row!=='object'||Array.isArray(row)))throw new Error(`Unexpected Parlay ${endpoint} response`);
      if(endpoint==='odds'&&!validOddsRows(rows))throw new Error('Unexpected Parlay odds nested response');
      const fields=endpoint==='props'?['market_key','player','bookmaker']:endpoint==='live/period_markets'?['match_id','source']:[];
      if(rows.some(row=>!validStringFields(row,fields)))throw new Error(`Unexpected Parlay ${endpoint} identity response`);
      const flag=name=>(r.headers.get(name)||'').trim().toLowerCase(),more=r.headers.get('x-result-has-more');
      rows.providerTruncated=flag('x-result-truncated')==='true'||flag('x-result-has-more')==='true'||!['','false','0'].includes(flag('x-result-degraded'))||(endpoint==='props'&&more==null&&rows.length>=Number(params.limit||10000));
      return rows;
    }
  };
  if(sport==='mlb'){
    const keys=['player_home_runs','player_hits','player_hits_runs_rbis','player_strikeouts','player_total_bases'];
    const [batches,games]=await Promise.all([Promise.all(keys.map(markets=>get('props',{markets,limit:'10000'}).then(rows=>({market:markets,rows,status:'loaded'})).catch(()=>({market:markets,rows:[],status:'unavailable'})))),get('odds',{markets:'h2h,spreads,totals',regions:'us',oddsFormat:'american'})]);
    return {provider:'parlay',sport,generated_at:new Date().toISOString(),props:batches.flatMap(b=>b.rows),games_raw:games,coverage:{possibly_truncated:batches.some(b=>b.rows.length>=10000),markets:Object.fromEntries(batches.map(b=>[b.market,{status:b.status,rows:b.rows.length}]))}};
  }
  const derivativeGroups=new Set(Object.keys(markets).filter(k=>k==='first_td'||/_1[hq]$/.test(k)));
  const derivativeKeys=Object.entries(markets).filter(([k])=>derivativeGroups.has(k)).map(([,v])=>v[0]);
  const coreKeys=Object.entries(markets).filter(([k])=>!derivativeGroups.has(k)).map(([,v])=>v[0]);
  const result=(promise)=>promise.then(rows=>({rows,status:rows.providerTruncated?'degraded':'loaded',error:null})).catch(error=>({rows:[],status:'unavailable',error}));
  const [raw, games, periods]=await Promise.all([
    sport==='nfl'?result(get('props',{markets:coreKeys.join(','),limit:'10000'})):Promise.resolve({rows:[],status:'not_applicable',error:null}),
    result(get('odds',{markets:'h2h,spreads,totals',regions:'us',oddsFormat:'american'})),
    result(get('live/period_markets',{period:'all'}))
  ]);
  // Smaller independent boards avoid the provider's slow broad-query path while
  // retaining every sportsbook row required for research and line shopping.
  const derivatives=sport==='nfl'?await result(get('props',{markets:derivativeKeys.join(','),limit:'10000'})):{rows:[],status:'not_applicable',error:null};
  const failures={props:raw.error,odds:games.error,periods:periods.error,derivatives:derivatives.error};
  if(games.status==='unavailable'&&periods.status==='unavailable'&&(raw.status==='unavailable'||sport==='ncaa')&&!['loaded','degraded'].includes(derivatives.status))throw Object.values(failures).find(Boolean)||new Error('Unexpected or unavailable Parlay responses');
  const sources={props:raw,odds:games,periods,derivatives};
  const degraded=Object.values(failures).some(Boolean)||Object.values(sources).some(source=>source.status==='degraded'),sourceErrors=Object.fromEntries(Object.entries(failures).filter(([,e])=>e).map(([name,e])=>[name,{code:e.code||e.name||'ERROR',status:e.status||null,message:e.providerMessage||'unavailable',stage:e.stage||name,retry_after_seconds:e.retryAfterSec||0}]));
  for(const [name,source] of Object.entries(sources))if(source.status==='degraded')sourceErrors[name]={code:'PROVIDER_COVERAGE_DEGRADED',status:200,message:'Provider returned incomplete/degraded coverage; available quotes retained',stage:name,retry_after_seconds:0};
  const observed=new Date().toISOString(),sourceState=source=>({loaded:'FRESH',degraded:'DEGRADED',not_applicable:'NOT_APPLICABLE',unavailable:'FAILED'})[source.status];
  return {provider:'parlay',sport,generated_at:observed,feed_status:degraded?'FALLBACK':'FRESH',refresh_status:degraded?'FALLBACK':'FRESH',source_errors:sourceErrors,source_states:Object.fromEntries(Object.entries(sources).map(([name,source])=>[name,sourceState(source)])),source_observed_at:Object.fromEntries(Object.entries(sources).map(([name,source])=>[name,['loaded','degraded'].includes(source.status)?observed:null])),props:normalizeProps([...raw.rows,...derivatives.rows]),games_raw:games.rows,props_status:raw.status,derivative_status:derivatives.status,
    period_quotes:[...periodsFromGames(games.rows),...normalizePeriods(periods.rows)],period_status:periods.status,
    coverage:{raw_props:raw.rows.length,derivative_props:derivatives.rows.length,possibly_truncated:Object.values(sources).some(source=>source.rows.providerTruncated)},odds_status:games.status};
}
