/* Sharp-market consensus service (experimental, research-weights flag OFF by default).
 * Normalizes two-way odds from many books/exchanges to fair probabilities and combines them.
 * Nothing here is a validated edge: weights are hypotheses and every output carries its evidence limits.
 * Only quotes for the identical contract (event, market, line, sides) are ever combined. */
(function(root){
'use strict';
const finite=x=>typeof x==='number'&&Number.isFinite(x);

// ---- numerics -------------------------------------------------------------------------------------------------
// Standard normal CDF (Hart/West double-precision rational approximation) and its inverse (Acklam + one Halley step).
function normalCdf(x){
 if(!finite(x))return NaN;
 const a=Math.abs(x);let c;
 if(a>37)c=0;else{
  const e=Math.exp(-a*a/2);
  if(a<7.07106781186547){
   let b=.0352624965998911*a+.700383064443688;b=b*a+6.37396220353165;b=b*a+33.912866078383;b=b*a+112.079291497871;b=b*a+221.213596169931;b=b*a+220.206867912376;
   c=e*b;
   b=.0883883476483184*a+1.75566716318264;b=b*a+16.064177579207;b=b*a+86.7807322029461;b=b*a+296.564248779674;b=b*a+637.333633378831;b=b*a+793.826512519948;b=b*a+440.413735824752;
   c=c/b;
  }else{let b=a+.65;b=a+4/b;b=a+3/b;b=a+2/b;b=a+1/b;c=e/b/2.506628274631;}
 }
 return x>0?1-c:c;
}
function normalInv(p){
 if(!(p>0&&p<1))return p===0?-Infinity:p===1?Infinity:NaN;
 const a=[-39.69683028665376,220.9460984245205,-275.9285104469687,138.357751867269,-30.66479806614716,2.506628277459239],
  b=[-54.47609879822406,161.5858368580409,-155.6989798598866,66.80131188771972,-13.28068155288572],
  c=[-.007784894002430293,-.3223964580411365,-2.400758277161838,-2.549732539343734,4.374664141464968,2.938163982698783],
  d=[.007784695709041462,.3224671290700398,2.445134137142996,3.754408661907416];
 let x;
 if(p<.02425){const q=Math.sqrt(-2*Math.log(p));x=(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1);}
 else if(p>1-.02425){const q=Math.sqrt(-2*Math.log(1-p));x=-(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5])/((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1);}
 else{const q=p-.5,r=q*q;x=(((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q/(((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1);}
 const e=normalCdf(x)-p,u=e*2.506628274631*Math.exp(x*x/2);
 return x-u/(1+x*u/2);
}
const americanToDecimal=a=>finite(a)&&Math.abs(a)>=100?(a>0?1+a/100:1+100/-a):null;
const decimalToAmerican=d=>!finite(d)||d<=1?null:d>=2?Math.round((d-1)*100):Math.round(-100/(d-1));

// ---- vig removal ------------------------------------------------------------------------------------------------
// Each method takes the two raw implied probabilities (incl. vig) and returns fair probabilities summing to 1.
function devigPair(decA,decB,method='proportional'){
 if(!(decA>1&&decB>1)||!finite(decA)||!finite(decB))return null;
 const qa=1/decA,qb=1/decB,over=qa+qb;let pa;
 if(method==='proportional')pa=qa/over;
 else if(method==='power'){ // p_i = q_i^k with k solving sum = 1
  let lo=.2,hi=5;for(let i=0;i<80;i++){const k=(lo+hi)/2;(Math.pow(qa,k)+Math.pow(qb,k)>1)?lo=k:hi=k;}
  pa=Math.pow(qa,(lo+hi)/2);
 }else if(method==='probit'){ // p_i = Phi(z_i + c) with c solving sum = 1 (shifts in normal space, so favourites bear less of the margin than proportional)
  const za=normalInv(qa),zb=normalInv(qb);let lo=-3,hi=3;
  for(let i=0;i<80;i++){const c=(lo+hi)/2;(normalCdf(za+c)+normalCdf(zb+c)>1)?hi=c:lo=c;}
  pa=normalCdf(za+(lo+hi)/2);
 }else return null;
 return {pA:pa,pB:1-pa,overround:over,method};
}
// Exchange commission reduces the winning payout; applied to the net odds only when a fee is configured.
const afterFee=(dec,fee)=>fee>0?1+(dec-1)*(1-fee):dec;

// ---- source identity --------------------------------------------------------------------------------------------
const compact=s=>String(s??'').toLowerCase().replace(/[^a-z0-9]/g,'');
function makeNormalizer(aliases={}){
 const map=new Map(Object.entries(aliases).map(([k,v])=>[compact(k),compact(v)]));
 return name=>{const c=compact(name);return map.get(c)||c;};
}

// ---- board construction -------------------------------------------------------------------------------------------
const stampMs=v=>{if(typeof v==='string'&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/.test(v)){const t=Date.parse(v);return Number.isFinite(t)?t:null;}return null;};
/* Turns provider events (The-Odds-API-style `games_raw`) into per-contract two-way quotes.
 * Side A is home / over; side B is away / under. Spread lines are the home line.
 * Unusable quotes are counted, never repaired: missing side, mismatched points, no timestamp, future timestamp. */
function boardFromRaw(events,{now=Date.now(),normalize=makeNormalizer(),futureSkewMs=60000}={}){
 const board=[],drop={started:0,noTimestamp:0,futureTimestamp:0,invalidPair:0,mismatchedPoints:0};
 for(const ev of Array.isArray(events)?events:[]){
  const kick=stampMs(ev?.commence_time);
  if(!kick||kick<=now){drop.started++;continue;}
  const row={eventId:String(ev.id||[ev.home_team,ev.away_team,ev.commence_time].join('|')),home:ev.home_team,away:ev.away_team,kickoff:ev.commence_time,markets:{moneyline:[],spread:[],total:[]}};
  for(const book of ev.bookmakers||[]){
   const source=normalize(book.key||book.title);
   for(const m of book.markets||[]){
    const ts=stampMs(m.last_update)??stampMs(book.last_update);
    if(ts==null){drop.noTimestamp++;continue;}
    if(ts>now+futureSkewMs){drop.futureTimestamp++;continue;}
    const out=Array.isArray(m.outcomes)?m.outcomes:[],byName=n=>out.find(o=>o?.name===n);
    let market,a,b,line=null;
    if(m.key==='h2h'){market='moneyline';a=byName(ev.home_team);b=byName(ev.away_team);}
    else if(m.key==='spreads'){market='spread';a=byName(ev.home_team);b=byName(ev.away_team);
     if(!a||!b||!finite(a.point)||!finite(b.point)||a.point!==-b.point){drop.mismatchedPoints++;continue;}line=a.point;}
    else if(m.key==='totals'){market='total';a=byName('Over');b=byName('Under');
     if(!a||!b||!finite(a.point)||a.point!==b.point){drop.mismatchedPoints++;continue;}line=a.point;}
    else continue;
    const da=americanToDecimal(a?.price),db=americanToDecimal(b?.price);
    if(!da||!db){drop.invalidPair++;continue;}
    row.markets[market].push({source,title:book.title||book.key,aOdds:a.price,bOdds:b.price,aDec:da,bDec:db,line,ts,ageSec:Math.max(0,(now-ts)/1000)});
   }
  }
  board.push(row);
 }
 return {board,drop,now};
}

// ---- copied / highly correlated prices -----------------------------------------------------------------------------
/* Two sources whose exact prices coincide on most non-standard markets are treated as one information source.
 * Standard -110/-110 pairs are uninformative and ignored. Returns clusters of size >= 2. */
function detectCopies(board,{minObs=15,minShare=.85}={}){
 const stats=new Map(),key=(a,b)=>a<b?a+'|'+b:b+'|'+a;
 for(const ev of board)for(const market of Object.values(ev.markets)){
  const usable=market.filter(q=>!(q.aOdds===-110&&q.bOdds===-110));
  for(let i=0;i<usable.length;i++)for(let j=i+1;j<usable.length;j++){
   const x=usable[i],y=usable[j];if(x.source===y.source||x.line!==y.line)continue;
   const k=key(x.source,y.source),s=stats.get(k)||{n:0,same:0};s.n++;if(x.aOdds===y.aOdds&&x.bOdds===y.bOdds)s.same++;stats.set(k,s);
  }
 }
 const parent=new Map(),find=x=>{while(parent.get(x)!==x){parent.set(x,parent.get(parent.get(x)));x=parent.get(x);}return x;};
 const pairs=[];
 for(const [k,s] of stats){
  if(s.n<minObs||s.same/s.n<minShare)continue;
  const [a,b]=k.split('|');pairs.push({a,b,n:s.n,share:s.same/s.n});
  for(const x of [a,b])if(!parent.has(x))parent.set(x,x);
  parent.set(find(a),find(b));
 }
 const groups=new Map();for(const x of parent.keys()){const r=find(x);groups.set(r,[...(groups.get(r)||[]),x]);}
 return {clusters:[...groups.values()].map(g=>g.sort()),pairs};
}
const clusterFactors=clusters=>{const f={};for(const c of clusters||[])for(const s of c)f[s]=1/c.length;return f;};

// ---- consensus --------------------------------------------------------------------------------------------------
/* Combines two-way quotes of ONE identical contract.
 * mode 'equal'   : every fresh source counts once (cluster-adjusted). This is the default decision input.
 * mode 'research': config weights (experimental flag), unspecified sources weight 0.
 * excludeSources : leave-one-out, so an offer is never judged against its own book or that book's price copies.
 * reliability    : optional {source: factor in [0,1]} learned from history (see reliabilityFromSamples). */
function consensus(quotes,{mode='equal',weights={},devig='proportional',excludeSources=[],clusters=[],minSources=3,reliability=null,feeRates={},maxAgeSec=Infinity}={}){
 const skip=new Set(excludeSources),factor=clusterFactors(clusters),used=[],dropped=[];
 for(const q of quotes||[]){
  if(skip.has(q.source)){dropped.push({source:q.source,why:'excluded'});continue;}
  if(q.ageSec>maxAgeSec){dropped.push({source:q.source,why:'stale'});continue;}
  const fee=feeRates[q.source]||0,d=devigPair(afterFee(q.aDec,fee),afterFee(q.bDec,fee),devig);
  // A book whose two sides imply less than 100% is an error, not information (exchanges may legitimately sit near 100%).
  if(!d||d.overround<.985){dropped.push({source:q.source,why:'crossed'});continue;}
  const base=mode==='research'?(weights[q.source]||0):1;
  const rel=reliability?(finite(reliability[q.source])?reliability[q.source]:0):1;
  const w=base*rel*(factor[q.source]??1);
  if(!(w>0)){dropped.push({source:q.source,why:mode==='research'?'unweighted':'unreliable'});continue;}
  used.push({source:q.source,title:q.title,p:d.pA,w,overround:d.overround,ageSec:q.ageSec,aOdds:q.aOdds,bOdds:q.bOdds});
 }
 const total=used.reduce((s,u)=>s+u.w,0);
 if(used.length<minSources||!(total>0))return {ok:false,reason:`Only ${used.length} usable source${used.length===1?'':'s'}; ${minSources} required.`,used,dropped,mode};
 const p=used.reduce((s,u)=>s+u.w*u.p,0)/total;
 const sd=Math.sqrt(used.reduce((s,u)=>s+u.w*(u.p-p)**2,0)/total);
 const shares=used.map(u=>u.w/total);
 return {ok:true,mode,devig,pA:p,pB:1-p,n:used.length,sd,range:[Math.min(...used.map(u=>u.p)),Math.max(...used.map(u=>u.p))],
  effectiveSources:1/shares.reduce((s,x)=>s+x*x,0),topShare:Math.max(...shares),
  used:used.map((u,i)=>({...u,share:shares[i]})),dropped,newestAgeSec:Math.min(...used.map(u=>u.ageSec)),oldestAgeSec:Math.max(...used.map(u=>u.ageSec))};
}
/* Sample-size-aware reliability: shrinks a source toward 0 until it has enough scored observations. */
const reliabilityFromSamples=(samples,k=300)=>Object.fromEntries(Object.entries(samples||{}).map(([s,n])=>[s,finite(n)&&n>0?n/(n+k):0]));

/* Groups a market's quotes by line and picks the line with the most distinct sources. Different lines are different contracts. */
function mainLine(quotes){
 const by=new Map();for(const q of quotes){const k=String(q.line);by.set(k,[...(by.get(k)||[]),q]);}
 let best=null;for(const [k,list] of by){const n=new Set(list.map(q=>q.source)).size;if(!best||n>best.n)best={line:list[0].line,n,quotes:list};}
 return best;
}

const api={normalCdf,normalInv,americanToDecimal,decimalToAmerican,devigPair,afterFee,makeNormalizer,compact,boardFromRaw,detectCopies,clusterFactors,consensus,reliabilityFromSamples,mainLine};
root.GoingSharpConsensus=api;if(typeof module!=='undefined')module.exports=api;
})(globalThis);
