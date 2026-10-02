(function(root){
'use strict';
// Prospective, user-selected observations. These counts are not a model backtest.
const CAPACITY=10000, MARKETS=['atd','pass_yds','pass_tds','rush_yds','receptions'];
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const plain=x=>x!=null&&typeof x==='object'&&!Array.isArray(x)&&Object.getPrototypeOf(x)===Object.prototype;
const str=x=>typeof x==='string'&&x.trim().length>0&&x.length<=500;
const copy=x=>JSON.parse(JSON.stringify(x));
function time(x){return (typeof x==='string'&&x.trim()||finite(x))?new Date(x).getTime():NaN;}
function stamp(x){return new Date(time(x)).toISOString();}
function create(){return {version:1,records:{},settlements:{}};}
function identity(r){return JSON.stringify([r.sport,r.profileId,r.home,r.away,r.kickoff,r.market,r.side,r.line,r.scoreVersion]);}
function gameIdentity(r){return JSON.stringify([r.sport,r.home,r.away,r.kickoff]);}
function band(score){return score>=90?'90+':`${Math.floor(score/10)*10}-${Math.floor(score/10)*10+9}`;}
function snapshot(input,now){
 if(!plain(input)||!finite(now))return null;
 const r={};
 for(const k of ['scoreVersion','sport','profileId','player','team','opp','home','away','market','side']){
  if(!str(input[k]))return null;r[k]=input[k];
 }
 if(r.sport!=='nfl'||!MARKETS.includes(r.market)||r.home===r.away||r.team===r.opp||
  ![r.home,r.away].includes(r.team)||![r.home,r.away].includes(r.opp))return null;
 if(r.side!==(r.market==='atd'?'Yes':'Over')||!finite(input.line)||input.line<0||
  (r.market==='atd'&&input.line!==.5)||!finite(input.score)||input.score<0||input.score>100)return null;
 const kickoff=time(input.kickoff), modelAt=time(input.modelAt);
 if(!Number.isFinite(kickoff)||kickoff<=now||!Number.isFinite(modelAt)||modelAt>now)return null;
 Object.assign(r,{kickoff:stamp(input.kickoff),modelAt:stamp(input.modelAt),line:input.line,score:input.score});
 if(input.contextAt!=null){if(!Number.isFinite(time(input.contextAt))||time(input.contextAt)>now)return null;r.contextAt=stamp(input.contextAt);}
 if(input.evidenceAt!=null){
  if(!plain(input.evidenceAt))return null;r.evidenceAt={};
  for(const key of ['learning','injury','roster'])if(Object.hasOwn(input.evidenceAt,key)){
   if(!Number.isFinite(time(input.evidenceAt[key]))||time(input.evidenceAt[key])>now)return null;
   r.evidenceAt[key]=stamp(input.evidenceAt[key]);
  }
 }
 for(const k of ['probability','scoreProbability','pushProbability','projection'])if(input[k]!=null){
  if(!finite(input[k])||(k!=='projection'&&(input[k]<0||input[k]>1)))return null;r[k]=input[k];
 }
 if(r.probability!=null&&r.pushProbability!=null&&r.probability+r.pushProbability>1)return null;
 for(const k of ['cohortSize','rank','sampleGames','currentGames'])if(input[k]!=null){
  if(!Number.isInteger(input[k])||input[k]<(k==='rank'||k==='cohortSize'?1:0))return null;r[k]=input[k];
 }
 if(r.rank!=null&&r.cohortSize!=null&&r.rank>r.cohortSize)return null;
 if(input.componentCoverage!=null){if(!finite(input.componentCoverage)||input.componentCoverage<0||input.componentCoverage>1)return null;r.componentCoverage=input.componentCoverage;}
 if(input.confidence!=null){
  if(!plain(input.confidence)||!finite(input.confidence.value)||input.confidence.value<0||input.confidence.value>100||!str(input.confidence.label))return null;
  r.confidence={value:input.confidence.value,label:input.confidence.label};
 }
 if(input.components!=null){
  if(!plain(input.components))return null;r.components={};
  for(const k of ['projection','role','matchup','environment'])if(input.components[k]!=null){
   const c=input.components[k];if(!plain(c))return null;const clean={};
   for(const field of ['value','weight','percentile'])if(c[field]!=null){
    if(!finite(c[field])||(field==='weight'&&(c[field]<0||c[field]>1))||(field==='percentile'&&(c[field]<0||c[field]>100)))return null;
    clean[field]=c[field];
   }else if(Object.hasOwn(c,field))clean[field]=null;
   for(const field of ['label','evidence'])if(c[field]!=null){
    if(typeof c[field]!=='string'||!c[field].trim()||c[field].length>(field==='evidence'?4000:500))return null;clean[field]=c[field];
   }
   r.components[k]=clean;
  }
 }
 if(input.quote!=null){
  const q=input.quote;
  if(!plain(q)||!str(q.book)||!finite(q.odds)||Math.abs(q.odds)<100||!finite(q.line)||q.line!==r.line||!Number.isFinite(time(q.updatedAt))||time(q.updatedAt)>now)return null;
  r.quote={book:q.book,odds:q.odds,line:q.line,updatedAt:stamp(q.updatedAt)};
  r.quoteFreshAtFreeze=now-time(q.updatedAt)<=5*60*1000;
 }
 return r;
}
function settlement(input,r,now){
 if(!plain(input)||!finite(now)||now<time(r.kickoff)||!['win','loss','push','void'].includes(input.status)||
  input.source!=='published-player-game-result'||!Number.isFinite(time(input.resultAt))||time(input.resultAt)<time(r.kickoff)||time(input.resultAt)>now||
  input.profileId!==r.profileId||!str(input.game)||input.home!==r.home||input.away!==r.away||
  !Number.isFinite(time(input.kickoff))||Math.abs(time(input.kickoff)-time(r.kickoff))>120000)return null;
 if(input.value!==null&&!finite(input.value))return null;
 if(input.status!=='void'&&input.value===null)return null;
 // A result cannot supply a grade that contradicts its frozen contract.
 if(input.status!=='void'){
  const expected=input.value===r.line?'push':input.value>r.line?'win':'loss';
  if(input.status!==expected)return null;
 }
 const clean={status:input.status,value:input.value,source:input.source,resultAt:stamp(input.resultAt),settledAt:new Date(now).toISOString(),game:input.game,profileId:input.profileId,
  home:input.home,away:input.away,kickoff:stamp(input.kickoff)};
 for(const k of ['playerSourceAt','sourceCheckedAt'])if(input[k]!=null){
  if(!Number.isFinite(time(input[k]))||time(input[k])<time(r.kickoff)||time(input[k])>now)return null;
  clean[k]=stamp(input[k]);
 }
 return clean;
}
function restore(input){
 try{
  if(!plain(input)||input.version!==1||!plain(input.records)||!plain(input.settlements)||Object.keys(input.records).length>CAPACITY)return null;
  const ledger=create();
  for(const [key,r] of Object.entries(input.records)){
   if(!plain(r)||!Number.isFinite(time(r.frozenAt)))return null;
   const clean=snapshot(r,time(r.frozenAt));
   if(!clean||identity(clean)!==key||r.key!==key||r.band!==band(clean.score)||r.selectionBias!=='user-selected')return null;
   ledger.records[key]={...clean,key,band:r.band,frozenAt:stamp(r.frozenAt),selectionBias:'user-selected'};
  }
  for(const [key,s] of Object.entries(input.settlements)){
   const r=ledger.records[key];if(!r||!plain(s)||!Number.isFinite(time(s.settledAt)))return null;
   const clean=settlement(s,r,time(s.settledAt));if(!clean)return null;
   ledger.settlements[key]=clean;
  }
  return ledger;
 }catch(_){return null;}
}
function freeze(inputLedger,input,now=Date.now()){
 const ledger=restore(inputLedger);if(!ledger)return {ledger:inputLedger,record:null,added:false,error:'Invalid ledger'};
 const r=snapshot(input,now);if(!r)return {ledger,record:null,added:false,error:'Invalid or non-prospective snapshot'};
 const key=identity(r);
 if(Object.hasOwn(ledger.records,key))return {ledger,record:copy(ledger.records[key]),added:false,error:null};
 if(Object.keys(ledger.records).length>=CAPACITY)return {ledger,record:null,added:false,error:'Tracker capacity reached; export before starting a new ledger'};
 const record={...r,key,band:band(r.score),frozenAt:new Date(now).toISOString(),selectionBias:'user-selected'};
 ledger.records[key]=record;return {ledger,record:copy(record),added:true,error:null};
}
function attachSettlement(inputLedger,key,grade,now=Date.now()){
 const ledger=restore(inputLedger);if(!ledger)return {ledger:inputLedger,settlement:null,added:false,error:'Invalid ledger'};
 const r=Object.hasOwn(ledger.records,key)?ledger.records[key]:null;
 if(!r)return {ledger,settlement:null,added:false,error:'Unknown observation'};
 if(Object.hasOwn(ledger.settlements,key))return {ledger,settlement:copy(ledger.settlements[key]),added:false,error:'Settlement already recorded'};
 const s=settlement(grade,r,now);if(!s)return {ledger,settlement:null,added:false,error:'Invalid or premature published result'};
 ledger.settlements[key]=s;return {ledger,settlement:copy(s),added:true,error:null};
}
function summary(inputLedger){
 const ledger=restore(inputLedger);if(!ledger)return null;
 const bands={},games=new Set();let settled=0;
 for(const [key,r] of Object.entries(ledger.records)){
  games.add(gameIdentity(r));const b=bands[r.band]||(bands[r.band]={count:0,settled:0,pending:0,win:0,loss:0,push:0,void:0});b.count++;
  const s=ledger.settlements[key];if(s){settled++;b.settled++;b[s.status]++;}else b.pending++;
 }
 const total=Object.keys(ledger.records).length;
 return {total,settled,pending:total-settled,games:games.size,bands,selectionBias:'user-selected'};
}
root.GoingScoreTracker={create,freeze,attachSettlement,restore,summary,CAPACITY};
if(typeof module!=='undefined')module.exports=root.GoingScoreTracker;
})(globalThis);
