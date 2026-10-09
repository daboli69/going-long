// QA: headless propProbabilities on real props; calibration injected from config/calibration_policy.json exactly as build_pipeline._calibration_for does.
const fs=require('fs'),vm=require('vm'),path=require('path');
const root=path.resolve(__dirname,'..'),html=fs.readFileSync(path.join(root,'index.html'),'utf8');
const s=html.indexOf('const finiteNumber = '),e0=html.indexOf('function evPercent(');
const src=html.slice(s,e0)+'\nconst COUNT_MARKETS = new Set(["receptions", "pass_tds", "rush_tds", "rec_tds", "atd"]);this.propProbabilities=propProbabilities;';
const ctx={};vm.createContext(ctx);vm.runInContext(src,ctx);const pp=ctx.propProbabilities;
const pol=JSON.parse(fs.readFileSync(path.join(root,'config/calibration_policy.json'),'utf8'));
const hist=JSON.parse(fs.readFileSync(path.join(root,'data/history.json'),'utf8')).betting;
const feed=JSON.parse(fs.readFileSync(path.join(root,'data/nfl_betting.json'),'utf8'));
const norm=n=>String(n).toLowerCase().replace(/[^a-z ]/g,'').replace(/\b(jr|sr|ii|iii|iv)\b/g,'').replace(/\s+/g,' ').trim();
const idx=new Map();for(const p of Object.values(hist.profiles)){const k=norm(p.name);(idx.get(k)||idx.set(k,[]).get(k)).push(p);}
const calFor=(m,pos)=>{const sp=pol.markets[m];return pol.active&&sp&&sp.positions.includes(pos)?{method:sp.method,params:sp.params,version:pol.version}:null;};
let withCal=0,withoutCal=0;for(const p of Object.values(hist.profiles))for(const m of ['receptions','pass_yds']){const c=calFor(m,p.position);c?withCal++:withoutCal++;}
console.log('profiles x market eligible for calibration',withCal,'not',withoutCal);
const out=[],bad=[];let cnt=0,dir={down:0,up:0,same:0};
const rows=feed.props.filter(p=>['receptions','pass_yds'].includes(p.market)&&!p.dfs&&p.overOdds&&p.underOdds&&p.line!=null);
console.log('non-dfs two-sided',rows.length);
for(const p of rows){const m=idx.get(norm(p.player));if(!m||m.length!==1)continue;const prof=m[0],model=prof.stats?.[p.market];if(!model||model.status!=='ready')continue;
  const cal=calFor(p.market,prof.position);
  const raw=pp({market:p.market,line:p.line,model}),adj=pp({market:p.market,line:p.line,model:cal?{...model,calibration:cal}:model});
  const center=model.family==='poisson'?model.lambda:model.mean,inDomain=center>0&&p.line>=.5*center&&p.line<=1.5*center;
  const sum=adj.over+adj.under+adj.push;if(Math.abs(sum-1)>1e-9||adj.over<0||adj.under<0||adj.over>1||adj.under>1||adj.push<-1e-12)bad.push(['bounds',p.player,p.market,p.line,adj]);
  if(!cal&&adj.over!==raw.over)bad.push(['changed w/o cal',p.player]);
  if(cal&&!inDomain&&adj.over!==raw.over)bad.push(['changed out of domain',p.player,p.line,center]);
  if(cal&&inDomain&&adj.over===raw.over)bad.push(['unchanged in domain',p.player,p.line]);
  if(cal&&inDomain){const d=adj.over-raw.over;dir[Math.abs(d)<1e-12?'same':d<0?'down':'up']++;
    // expected: Platt direction: over>~0.4 goes down; low goes up
    if(prof.position!==cal&&0){}
  }
  if(cal&&cnt<400){cnt++;out.push({player:p.player,pos:prof.position,market:p.market,line:p.line,mean:+center.toFixed(2),inDomain,ro:+raw.over.toFixed(4),co:+adj.over.toFixed(4),ru:+raw.under.toFixed(4),cu:+adj.under.toFixed(4),push:+adj.push.toFixed(4),pol:model.policy||'v1',n:model.n});}
}
console.log('violations',bad.length,JSON.stringify(bad.slice(0,5)));console.log('direction in-domain',dir,'calibrated rows',cnt);
const sample=[...out.filter(r=>r.market==='receptions').slice(0,10),...out.filter(r=>r.market==='pass_yds').slice(0,10)];
for(const r of sample)console.log(JSON.stringify(r));
// check Platt reference vs python-style: p'=expit(a+b*logit(p))
const rr=out.filter(r=>r.market==='receptions'&&r.inDomain);let maxerr=0;for(const r of rr){const pc=r.ro/(r.ro+r.ru);const q=1/(1+Math.exp(-(pol.markets.receptions.params.a+pol.markets.receptions.params.b*Math.log(pc/(1-pc)))));maxerr=Math.max(maxerr,Math.abs(q*(r.ro+r.ru)-r.co));}
console.log('max |JS - reference platt| (rounded to 4dp)',maxerr);
// domain stats
const dom=out.reduce((a,r)=>{a[r.market+(r.inDomain?':in':':out')]=(a[r.market+(r.inDomain?':in':':out')]||0)+1;return a},{});console.log(dom);
const pols=out.reduce((a,r)=>{a[r.market+':'+r.pol]=(a[r.market+':'+r.pol]||0)+1;return a},{});console.log(pols);
