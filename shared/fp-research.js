(function(root){
'use strict';
let pending=null;
let evidence=null,inflight=false,last=0,periodKey='',currentToken=null,epoch=0,status='Private source is not connected to the live backend yet.';
const norm=x=>String(x||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[^a-z0-9]/g,''),esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const team=x=>({ARZ:'ARI',BLT:'BAL',CLV:'CLE',HST:'HOU',JAC:'JAX',LAR:'LA',WSH:'WAS'})[String(x||'').toUpperCase()]||String(x||'').toUpperCase();
function session(){try{for(let i=0;i<localStorage.length;i++){const k=localStorage.key(i);if(/^sb-.*-auth-token$/.test(k)){const value=JSON.parse(localStorage.getItem(k));if(value?.access_token)return value.access_token;}}}catch{}return null;}
async function refresh({season,week,token=session(),fetchImpl=root.fetch,now=Date.now()}={}){
 const key=season+'|'+week;if(key!==periodKey||token!==currentToken){periodKey=key;currentToken=token;epoch++;last=0;evidence=null;pending=null;}
 if(!token||!Number.isInteger(week)||!Number.isInteger(season)){evidence=null;status='Private source needs an authorized GOING session and verified NFL week.';return;}
 if(inflight){pending={season,week,token,fetchImpl,now,requestEpoch:epoch};return;}if(now-last<300000)return;last=now;const requestEpoch=epoch;evidence=null;
 inflight=true;try{const r=await fetchImpl(`/api/fp-research?season=${season}&week=${week}`,{headers:{Authorization:'Bearer '+token},cache:'no-store'});const data=await r.json();if(!r.ok||data.schema!=='going-private-fp-research-v1'||data.season!==season||data.week!==week||!Array.isArray(data.players)||!Array.isArray(data.teams))throw Error('Private research unavailable');if(requestEpoch!==epoch)return;evidence=data;status=`Private Week ${week} research synced; CSVs remain server-side.`;}catch{if(requestEpoch===epoch)status='Private research is unavailable; existing forecasts remain unchanged.';}finally{inflight=false;if(pending){const next=pending;pending=null;if(next.requestEpoch===epoch&&next.token===currentToken)await refresh(next);}if(requestEpoch===epoch&&evidence&&typeof root.dispatchEvent==='function')root.dispatchEvent(new Event('going-fp-research-ready'));}
}
if(typeof root.addEventListener==='function')root.addEventListener('storage',event=>{
 if(event.key!==null&&!/^sb-.*-auth-token$/.test(event.key))return;
 evidence=null;pending=null;currentToken=null;epoch++;last=0;
 status='Private session changed; sign in through the personal journal if needed.';
 if(typeof root.dispatchEvent==='function')root.dispatchEvent(new Event('going-fp-research-ready'));
});
function predictionPeriod(context,now=Date.now()){
 const rows=Array.isArray(context?.games)?context.games:[];const games=rows.filter(g=>g&&typeof g.id==='string'&&/^\d{4}_\d{2}_/.test(g.id)&&Number.isFinite(Date.parse(g.kickoff))&&Date.parse(g.kickoff)>now).sort((a,b)=>Date.parse(a.kickoff)-Date.parse(b.kickoff));const first=games[0];return first?{season:Number(first.id.slice(0,4)),week:Number(first.id.slice(5,7))}:null;
}
function panel(p){
 if(!evidence)return '';
 const found=evidence.players.filter(x=>x&&Array.isArray(x.notes)&&x.notes.every(n=>typeof n==='string')&&team(x.team)===team(p.team)&&norm(x.name)===norm(p.player||p.name)&&(!p.position||x.position===p.position));
 const notes=found.length===1?found[0].notes.slice():[];
 for(const t of evidence.teams)if(t&&Array.isArray(t.notes)&&t.notes.every(n=>typeof n==='string')&&[p.team,p.opponent,p.home,p.away].filter(Boolean).some(x=>team(t.team)===team(x)))notes.push(...t.notes.map(n=>`${t.team}: ${n}`));
 return notes.length?`<details class="dfs-method"><summary>Private current-season research</summary><ul>${[...new Set(notes)].map(n=>'<li>'+esc(n)+'</li>').join('')}</ul><p>Source: your private FantasyPoints inputs. Descriptive evidence; no forecast adjustment or established betting edge.</p></details>`:'';
}
root.GoingFpResearch={refresh,panel,predictionPeriod,get status(){return status;}};
if(typeof module==='object')module.exports=root.GoingFpResearch;
})(globalThis);
