(function(root){
'use strict';

const VERSION='dfs-lineup-receipt-1',KEY='going.dfs.lineupReceipts.v1',CAPACITY=200,MAX_RECEIPT_BYTES=30000,MAX_STORE_BYTES=3_500_000;
const STRATEGY_VERSION='dfs-tournament-research-v1',AVAILABILITY_VERSION='dfs-availability-v1',UPSIDE_SOURCE='observed-partial-fantasy-residual-v1';
const CLASSIC_SLOTS=['QB','RB','RB','WR','WR','WR','TE','FLEX','DST'];
const NFL_TEAMS=new Set('ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LA LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS'.split(' '));
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const plain=x=>x!==null&&typeof x==='object'&&!Array.isArray(x)&&(Object.getPrototypeOf(x)===Object.prototype||Object.getPrototypeOf(x)===null);
const time=x=>typeof x==='string'&&x.trim()?Date.parse(x):NaN;
const stamp=x=>new Date(time(x)).toISOString();
const text=(x,max=300)=>typeof x==='string'&&x.trim().length>0&&x.length<=max;
const teamCode=x=>String(x||'').trim().toUpperCase();
const nameKey=x=>String(x||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,'');

function canonical(value){
 if(value===null||typeof value==='string'||typeof value==='boolean')return JSON.stringify(value);
 if(typeof value==='number'){if(!Number.isFinite(value))throw Error('Receipt contains a non-finite number.');return JSON.stringify(Object.is(value,-0)?0:value);}
 if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';
 if(!plain(value))throw Error('Receipt contains a non-JSON value.');
 return '{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+':'+canonical(value[key])).join(',')+'}';
}
function hash(value){
 const source=typeof value==='string'?value:canonical(value);let a=0x811c9dc5,b=0x9e3779b9;
 for(let i=0;i<source.length;i++){const c=source.charCodeAt(i);a=Math.imul(a^c,0x01000193);b=Math.imul(b^c,0x85ebca6b);}
 return (a>>>0).toString(16).padStart(8,'0')+(b>>>0).toString(16).padStart(8,'0');
}
function deepFreeze(value){if(value&&typeof value==='object'&&!Object.isFrozen(value)){Object.values(value).forEach(deepFreeze);Object.freeze(value);}return value;}
function assertJson(value,label,stack=new Set(),depth=0){
 if(depth>40)throw Error(`${label} exceeds the supported nesting depth.`);
 if(value===null||typeof value==='string'||typeof value==='boolean')return;
 if(typeof value==='number'){if(!Number.isFinite(value))throw Error(`${label} contains a non-finite number.`);return;}
 if(!Array.isArray(value)&&!plain(value))throw Error(`${label} must contain JSON-safe data.`);
 if(stack.has(value))throw Error(`${label} cannot contain circular data.`);stack.add(value);
 for(const child of Array.isArray(value)?value:Object.values(value))assertJson(child,label,stack,depth+1);
 stack.delete(value);
}
function cloneJson(value,label){
 try{assertJson(value,label);const encoded=JSON.stringify(value);if(encoded===undefined)throw Error();return JSON.parse(encoded);}
 catch(_){throw Error(`${label} must contain JSON-safe data.`);}
}
function fail(error){return {ok:false,receipt:null,error};}
function salaryCap(site){return site==='draftkings'?50000:60000;}
function showdownCaptain(site){return site==='draftkings'?'CPT':'MVP';}
function eligible(position,slot,contest,site){
 if(contest==='classic')return position===slot||(slot==='FLEX'&&['RB','WR','TE'].includes(position));
 if(slot===showdownCaptain(site)||slot==='FLEX')return ['QB','RB','WR','TE','DST','K'].includes(position);
 return false;
}
function receiptId(receipt){const payload={...receipt};delete payload.id;return `dfs-${receipt.createdAt.replace(/[-:.TZ]/g,'')}-${hash(payload)}`;}
function size(textValue){return textValue.length*2;}
function validUpside(value,now){
 if(value==null)return true;
 if(!plain(value)||value.source!==UPSIDE_SOURCE||!finite(value.value)||value.value<0||!Number.isInteger(value.n)||value.n<8||!Number.isInteger(value.currentGames)||value.currentGames<0||value.currentGames>value.n)return false;
 const asOf=time(value.asOf);return Number.isFinite(asOf)&&asOf<=now;
}
function jsonSafe(value,label){try{cloneJson(value,label);return true;}catch(_){return false;}}

function freeze(input){
 try{
  if(!plain(input))return fail('Lineup receipt input is invalid.');
  const {players,contest,site,mode,salaryHash,modelGeneratedAt,injuryAt}=input,now=input.now;
  if(!Array.isArray(players)||!['classic','showdown'].includes(contest)||!['draftkings','fanduel'].includes(site)||!text(mode,80))return fail('Contest, site, mode or lineup is missing.');
  if(!Number.isSafeInteger(now)||now<0)return fail('A valid capture time in milliseconds is required.');
  if(typeof salaryHash!=='string'||!/^([a-f0-9]{64})$/i.test(salaryHash))return fail('A SHA-256 hash of the imported salary file is required.');
  if(!Number.isFinite(time(modelGeneratedAt))||time(modelGeneratedAt)>now)return fail('The model snapshot timestamp is missing, invalid or in the future.');
  if(injuryAt!=null&&(!Number.isFinite(time(injuryAt))||time(injuryAt)>now))return fail('The roster/injury timestamp is invalid or in the future.');
  const slots=contest==='classic'?CLASSIC_SLOTS:[showdownCaptain(site),'FLEX','FLEX','FLEX','FLEX','FLEX'];
  if(players.length!==slots.length)return fail(`A ${contest} receipt requires exactly ${slots.length} players.`);
  const cap=salaryCap(site),maxTeam=contest==='showdown'?5:site==='draftkings'?8:4,slotCounts=new Map(),ids=new Set(),athletes=new Set(),teams=new Map(),games=new Set(),gameLabels=new Set(),kickoffs=new Set(),slotIndexes=new Set();
  let salaryUsed=0,projectionTotal=0,upsideTotal=0,allUpside=true;
  const captured=[];
  for(let index=0;index<players.length;index++){
   const p=players[index];if(!plain(p))return fail(`Player ${index+1} is invalid.`);
   const slot=p.slot,expectedMultiplier=contest==='classic'?1:slot===showdownCaptain(site)?1.5:1,multiplier=p.multiplier==null?expectedMultiplier:p.multiplier;
   const id=text(String(p.id??''),120)?String(p.id):'',name=text(p.name,180)?p.name:'',team=teamCode(p.team),position=String(p.position||'').trim().toUpperCase();
   const game=typeof p.game==='string'&&p.game.trim()?p.game:null,gameId=typeof p.gameId==='string'&&p.gameId.trim()?p.gameId:null,gameKey=gameId||game,kickoff=p.kickoff;
   if(!id||!name||!NFL_TEAMS.has(team)||!['QB','RB','WR','TE','DST','K'].includes(position)||!text(slot,8))return fail(`Player ${index+1} is missing a valid identity, team, position or slot.`);
   if(!slots.includes(slot)||!eligible(position,slot,contest,site))return fail(`${name} is not eligible for the ${slot||'unknown'} slot.`);
   if(!gameKey||!text(kickoff,80)||!Number.isFinite(time(kickoff))||time(kickoff)<=now)return fail(`${name} has missing game identity or a game that has started.`);
   if(p.slotIndex!=null&&(!Number.isInteger(p.slotIndex)||p.slotIndex<0||p.slotIndex>=slots.length||slots[p.slotIndex]!==slot||slotIndexes.has(p.slotIndex)))return fail(`${name} has an invalid or duplicate slot index.`);
   if(p.unavailable===true||p.injury?.state==='out'||p.injury?.blockRecommendation===true)return fail(`${name} is marked unavailable.`);
   if(!Number.isSafeInteger(p.salary)||p.salary<=0||!finite(p.projection)||p.projection<0||!validUpside(p.upside,now)||!finite(multiplier)||multiplier!==expectedMultiplier)return fail(`${name} has invalid salary, projection, sourced upside or multiplier.`);
   if(contest==='classic'&&p.sourceSalary!=null&&p.sourceSalary!=='draftkings-csv')return fail(`${name} is not tied to the imported DraftKings Classic salary file.`);
   if(contest==='showdown'&&p.showdownRole!=null&&!['CPT','FLEX'].includes(p.showdownRole))return fail(`${name} has an unsupported Showdown salary role.`);
   if(p.showdownRole==='CPT'&&slot!==showdownCaptain(site))return fail(`${name}'s CPT salary row cannot be placed in FLEX.`);
   if(p.showdownRole==='FLEX'&&slot===showdownCaptain(site))return fail(`${name}'s FLEX salary row cannot be used at the multiplier slot.`);
   const athlete=`${nameKey(name)}|${team}`;
   if(ids.has(id)||athletes.has(athlete))return fail('Player IDs and athlete identities must be unique across the lineup.');
   ids.add(id);athletes.add(athlete);slotCounts.set(slot,(slotCounts.get(slot)||0)+1);teams.set(team,(teams.get(team)||0)+1);games.add(gameKey);if(game)gameLabels.add(game);kickoffs.add(time(kickoff));if(p.slotIndex!=null)slotIndexes.add(p.slotIndex);
   if(teams.get(team)>maxTeam)return fail(`${team} exceeds the contest team limit.`);
  if(contest==='showdown'&&(games.size>1||gameLabels.size>1||kickoffs.size>1))return fail('A Showdown receipt must contain players from exactly one game and kickoff.');
   const salaryCost=p.salary*(contest==='showdown'&&slot===showdownCaptain(site)&&p.showdownRole!=='CPT'?1.5:1);
   if(!Number.isSafeInteger(salaryCost))return fail(`${name} has a non-integer contest salary cost.`);
   salaryUsed+=salaryCost;projectionTotal+=p.projection*multiplier;
   if(p.upside==null)allUpside=false;else upsideTotal+=p.upside.value*multiplier;
   const clean={slot,slotIndex:Number.isInteger(p.slotIndex)?p.slotIndex:null,id,name,team,position,game,gameId,kickoff,salary:p.salary,salaryCost,projection:p.projection,upside:cloneJson(p.upside??null,`${name} upside`),opportunityStats:cloneJson(p.opportunityStats??p.stats??null,`${name} opportunity stats`),opportunitySource:cloneJson(p.opportunitySource??p.source??null,`${name} opportunity source`),modelAgeHours:cloneJson(p.modelAgeHours??null,`${name} model age`),evidence:cloneJson(p.evidence??null,`${name} evidence`),injury:cloneJson(p.injury??null,`${name} injury`),concern:cloneJson(p.concern??null,`${name} concern`),concerns:cloneJson(p.concerns??null,`${name} concerns`),multiplier,showdownRole:p.showdownRole??null,sourceSalary:p.sourceSalary??null};
   captured.push(clean);
  }
  for(const slot of new Set(slots))if(slotCounts.get(slot)!==slots.filter(s=>s===slot).length)return fail(`The lineup does not fill every required ${slot} slot.`);
  if(salaryUsed>cap)return fail(`Lineup exceeds the ${site==='draftkings'?'$50,000':'$60,000'} salary cap.`);
  if(contest==='classic'&&games.size<2)return fail('Classic lineups must include at least two games.');
  const createdAt=new Date(now).toISOString(),receipt={version:VERSION,strategyVersion:mode==='tournament'?STRATEGY_VERSION:`legacy-${mode}`,availabilityVersion:AVAILABILITY_VERSION,createdAt,contest,site,mode,salaryHash:salaryHash.toLowerCase(),modelGeneratedAt,injuryAt:injuryAt??null,salaryCap:cap,salaryUsed,projectionTotal,upsideTotal:allUpside?upsideTotal:null,players:captured};
  const encoded=canonical(receipt);if(size(encoded)>MAX_RECEIPT_BYTES)return fail('Receipt evidence exceeds the local storage limit.');
  receipt.id=receiptId(receipt);return {ok:true,receipt:deepFreeze(receipt),error:null};
 }catch(error){return fail(error?.message||'Could not validate lineup receipt.');}
}

function validReceipt(receipt){
 try{
  if(!plain(receipt)||receipt.version!==VERSION||receipt.availabilityVersion!==AVAILABILITY_VERSION||!text(receipt.strategyVersion,100)||!['classic','showdown'].includes(receipt.contest)||!['draftkings','fanduel'].includes(receipt.site)||!Array.isArray(receipt.players)||receipt.players.length!==(receipt.contest==='classic'?9:6)||!text(receipt.id,100)||!Number.isFinite(time(receipt.createdAt))||receipt.id!==receiptId(receipt)||size(canonical(receipt))>MAX_RECEIPT_BYTES)return false;
  if(!Number.isSafeInteger(receipt.salaryUsed)||!finite(receipt.projectionTotal)||!(receipt.upsideTotal===null||finite(receipt.upsideTotal)))return false;
  return receipt.players.every(p=>plain(p)&&text(p.id,120)&&text(p.name,180)&&validUpside(p.upside,Number.MAX_SAFE_INTEGER)&&['opportunityStats','opportunitySource','modelAgeHours','evidence','injury','concern','concerns'].every(key=>Object.hasOwn(p,key)&&jsonSafe(p[key],key)));
 }
 catch(_){return false;}
}
function read(storage){
 try{
  if(!storage||typeof storage.getItem!=='function')return {ok:false,receipts:[],error:'Local storage is unavailable.'};
  const raw=storage.getItem(KEY);if(raw==null||raw==='')return {ok:true,receipts:[],error:null};
  if(typeof raw!=='string'||size(raw)>MAX_STORE_BYTES)return {ok:false,receipts:[],error:'Stored DFS receipts exceed the supported size.'};
  const data=JSON.parse(raw);if(!plain(data)||data.version!==1||!Array.isArray(data.receipts)||data.receipts.length>CAPACITY)return {ok:false,receipts:[],error:'Stored DFS receipt journal is invalid.'};
  const seen=new Set();for(const receipt of data.receipts){if(!validReceipt(receipt)||seen.has(receipt.id))return {ok:false,receipts:[],error:'Stored DFS receipt journal failed its integrity check.'};seen.add(receipt.id);}
  return {ok:true,receipts:data.receipts.map(receipt=>deepFreeze(receipt)),error:null};
 }catch(_){return {ok:false,receipts:[],error:'Stored DFS receipts could not be read; existing data was preserved.'};}
}
function append(storage,receipt){
 if(!validReceipt(receipt))return {ok:false,receipt:null,error:'Only a valid frozen DFS receipt can be appended.'};
 const current=read(storage);if(!current.ok)return {ok:false,receipt:null,error:current.error};
 if(current.receipts.some(item=>item.id===receipt.id))return {ok:false,receipt:null,error:'This receipt is already recorded.'};
 if(current.receipts.length>=CAPACITY)return {ok:false,receipt:null,error:'DFS receipt capacity reached; export receipts before starting another journal.'};
 try{
  const encoded=JSON.stringify({version:1,receipts:[...current.receipts,receipt]});
  if(size(encoded)>MAX_STORE_BYTES)return {ok:false,receipt:null,error:'DFS receipt journal is at its local storage limit; export before adding more.'};
  if(!storage||typeof storage.setItem!=='function')return {ok:false,receipt:null,error:'Local storage is unavailable.'};
  storage.setItem(KEY,encoded);const verified=read(storage);
  if(!verified.ok||!verified.receipts.some(item=>item.id===receipt.id))return {ok:false,receipt:null,error:'Receipt write could not be verified; stored data was preserved.'};
  return {ok:true,receipt:verified.receipts.find(item=>item.id===receipt.id),error:null};
 }catch(_){return {ok:false,receipt:null,error:'Local storage could not append the receipt; existing data was preserved.'};}
}

root.GoingDfsJournal={VERSION,KEY,CAPACITY,freeze,append,read};
if(typeof module!=='undefined')module.exports=root.GoingDfsJournal;
})(globalThis);
