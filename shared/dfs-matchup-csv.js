(function(root){
'use strict';
const SOURCE='local-opponent-csv-research-v1',KEY='going-dfs-matchups-v1';
const teams='ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LAC LA LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS'.split(' ');
const names=['Arizona Cardinals','Atlanta Falcons','Baltimore Ravens','Buffalo Bills','Carolina Panthers','Chicago Bears','Cincinnati Bengals','Cleveland Browns','Dallas Cowboys','Denver Broncos','Detroit Lions','Green Bay Packers','Houston Texans','Indianapolis Colts','Jacksonville Jaguars','Kansas City Chiefs','Los Angeles Chargers','Los Angeles Rams','Las Vegas Raiders','Miami Dolphins','Minnesota Vikings','New England Patriots','New Orleans Saints','New York Giants','New York Jets','Philadelphia Eagles','Pittsburgh Steelers','Seattle Seahawks','San Francisco 49ers','Tampa Bay Buccaneers','Tennessee Titans','Washington Commanders'];
const finite=x=>typeof x==='number'&&Number.isFinite(x),seasonOf=at=>{const d=new Date(at);return d.getUTCFullYear()-(d.getUTCMonth()<2?1:0);};
function team(x){x=String(x||'').trim();return teams[names.indexOf(x)]||({HST:'HOU',JAC:'JAX',LAR:'LA',WSH:'WAS',BLT:'BAL',CLV:'CLE',ARZ:'ARI'})[x]||(teams.includes(x)?x:null);}
function rows(text){
 const out=[];let row=[],v='',quoted=false,closed=false;
 for(let i=0;i<text.length;i++){const c=text[i];if(quoted){if(c==='"'){if(text[i+1]==='"'){v+='"';i++;}else{quoted=false;closed=true;}}else v+=c;}else if(c==='"'){if(v||closed)throw Error('Malformed CSV quotation.');quoted=true;}else if(c===','||c==='\r'||c==='\n'){row.push(v);v='';closed=false;if(c!==','){if(c==='\r'&&text[i+1]==='\n')i++;if(row.some(x=>x.trim()))out.push(row);row=[];}}else{if(closed)throw Error('Unexpected text after CSV quotation.');v+=c;}}
 if(quoted)throw Error('Unterminated CSV quotation.');row.push(v);if(row.some(x=>x.trim()))out.push(row);return out;
}
function parse(text,{name='',season,now=Date.now()}={}){
 if(typeof text!=='string'||text.length>1000000)throw Error('Matchup CSV must be under 1 MB.');
 if(!Number.isInteger(season)||season!==seasonOf(now))throw Error('Confirm the current NFL season for these exports.');
 const data=rows(text.replace(/^\uFEFF/,'')),h=data[1]?.map(x=>x.trim()),groups=data[0];
 if(!h?.includes('G'))throw Error('Expected a Data Suite CSV with two header rows.');
 let kind;if(h.includes('QB FPG'))kind='defense';else if(h.includes('PACE NEU'))kind='pace';else if(h.includes('SLOT %'))kind='receiving';else{
  const pos=[...new Set(data.slice(2).map(r=>r[h.indexOf('POS')]).filter(Boolean))];
  if(pos.length!==1||!/^vs\. (QB|RB|WR|TE)$/.test(pos[0]))throw Error('Unrecognized positional matchup export.');
  kind=pos[0].slice(4).toLowerCase();if(kind==='wr'){if(/\(1\)\.csv$/i.test(name))kind='outside';else if(/\(2\)\.csv$/i.test(name))kind='slot';else if(!/fantasy-points-allowed-wr\.csv$/i.test(name))throw Error('Use the original WR filenames to identify overall, (1) outside and (2) slot.');}
 }
 const footer=data.find(r=>/^Exported from/.test(r[0]))?.[0]||'',match=footer.match(/on (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) UTC/),at=match?Date.parse(match[1]+'T'+match[2]+':00Z'):NaN;
 if(!Number.isFinite(at)||new Date(at).toISOString().slice(0,16)!==match[1]+'T'+match[2]||at>now||now-at>36*3600000||seasonOf(at)!==season)throw Error('CSV export timestamp missing, malformed, future-dated or older than 36 hours.');
 const ix=label=>h.indexOf(label),number=(r,i)=>{const s=r[i]?.trim();if(!s||!Number.isFinite(Number(s)))throw Error('Missing or malformed numeric matchup value.');return Number(s);};
 const field=kind==='pace'?'PACE NEU':kind==='defense'?'PA':'FP/G',primary=ix(field),nameIx=ix(kind==='receiving'?'Team':'Name'),gameIx=ix('G');
 if(nameIx<0||primary<0&&kind!=='receiving')throw Error('Required matchup columns missing.');
 const records={};let league=null;
 for(const r of data.slice(2)){
  if(/^Exported from/.test(r[0]))continue;
  if(h.includes('Season')&&r[ix('Season')]!==String(season))throw Error('CSV contains another season.');
  const t=team(r[nameIx]),avg=!r[nameIx]?.trim()||r[nameIx]==='League Avg';
  if(!t&&!avg)throw Error('Unknown NFL team in matchup CSV.');
  if(t&&records[t])throw Error('Duplicate NFL team in matchup CSV.');
  const record={games:t?number(r,gameIx):null,metrics:{}};
  if(t&&(!Number.isInteger(record.games)||record.games<1||record.games>18))throw Error('Invalid completed-game count.');
  if(kind==='receiving'){for(const group of ['OUTER','SLOT','OUTSIDE LWR','OUTSIDE RWR']){const col=h.findIndex((v,i)=>v==='FPG'&&groups[i]===group);if(col<0)throw Error('Receiving alignment columns missing.');record.metrics[group]=number(r,col);}}
  else{record.metrics[field]=number(r,primary);const extras=kind==='pace'?['PASS %','PROE']:kind==='defense'?['PF','SACKS','EPA/P','QB FPG','RB FPG','WR FPG','TE FPG']:[];for(const key of extras)record.metrics[key]=number(r,ix(key));}
  if((kind!=='defense'&&Object.entries(record.metrics).some(([k,v])=>!['PROE'].includes(k)&&v<0))||kind==='defense'&&record.metrics.PA<0)throw Error('Negative scoring or pace value.');
  if(t)records[t]=record;else{if(league)throw Error('Duplicate league average.');league=record;}
 }
 if(Object.keys(records).length!==32||!league)throw Error('All 32 NFL teams and the league average are required.');
 if(!['defense','receiving','pace'].includes(kind)&&league.metrics['FP/G']<=0)throw Error('Positive league position scoring average required.');
 return {kind,season,exportedAt:new Date(at).toISOString(),records,league};
}
function active(dataset,now=Date.now()){return dataset?.season===seasonOf(now)&&finite(Date.parse(dataset.exportedAt))&&Date.parse(dataset.exportedAt)<=now&&now-Date.parse(dataset.exportedAt)<=36*3600000;}
function annotate(player,datasets,{enabled=false,now=Date.now()}={}){
 const p={...player};delete p.matchupResearch;delete p.matchupContext;
 if(p.unavailable||p.incumbentLocked||p.matched!==true||!finite(p.projection))return p;
 const opponent=team(p.opponent),own=team(p.team),position=String(p.position).toLowerCase(),evidence=[];
 const get=kind=>active(datasets?.[kind],now)?datasets[kind]:null,positionData=get(position),record=positionData?.records[opponent];
 if(record)evidence.push(`${opponent} allows ${record.metrics['FP/G'].toFixed(1)} ${p.position} fantasy points/game (${record.games} games); league ${positionData.league.metrics['FP/G'].toFixed(1)}. Provider scoring, not verified DraftKings scoring.`);
 if(position==='wr')for(const [kind,label] of [['outside','Outside WR'],['slot','Slot WR']]){const d=get(kind),r=d?.records[opponent];if(r)evidence.push(`${label}: ${r.metrics['FP/G'].toFixed(1)} allowed/game; league ${d.league.metrics['FP/G'].toFixed(1)} (${r.games} games). Player alignment unknown; not substituted for overall WR.`);}
 const receiving=get('receiving')?.records[opponent];if(position==='wr'&&receiving)evidence.push(`Receiving alignment allowed: outside ${receiving.metrics.OUTER.toFixed(1)}, slot ${receiving.metrics.SLOT.toFixed(1)} FPG (${receiving.games} games).`);
 const defense=get('defense')?.records[position==='dst'?own:opponent],opposing=get('defense')?.records[opponent];
 if(defense)evidence.push(`${position==='dst'?own:opponent} defense: ${(defense.metrics.PA/defense.games).toFixed(1)} points allowed/game; ${defense.metrics.SACKS} sacks; ${defense.metrics['EPA/P'].toFixed(3)} EPA/play (${defense.games} games).`);
 if(position==='dst'&&opposing)evidence.push(`${opponent} offense: ${(opposing.metrics.PF/opposing.games).toFixed(1)} points scored/game. Context only; no fitted D/ST matchup adjustment.`);
 for(const t of [own,opponent]){const pace=get('pace')?.records[t];if(pace)evidence.push(`${t} neutral pace: ${pace.metrics['PACE NEU'].toFixed(1)} sec/play; ${pace.metrics['PASS %'].toFixed(1)}% pass (${pace.games} games). Context only.`);}
 p.matchupContext=evidence;
 if(enabled&&record&&p.projectionSource==='dfs-current-season-empirical-v1'&&p.projectionSeason===positionData.season){const ratio=record.metrics['FP/G']/positionData.league.metrics['FP/G'];p.matchupResearch={source:SOURCE,season:positionData.season,exportedAt:positionData.exportedAt,opponent,position:p.position,ratio,games:record.games,baseline:p.projection,scenario:p.projection*ratio};}
 return p;
}
function adjustment(player,now=Date.now()){
 const m=player?.matchupResearch;if(player?.unavailable||player?.incumbentLocked||player?.matched!==true||m?.source!==SOURCE||m.opponent!==team(player.opponent)||m.position!==player.position||m.season!==player.projectionSeason||m.season!==seasonOf(now)||!active(m,now)||!finite(m.ratio)||m.ratio<0||!Number.isInteger(m.games)||m.games<1||m.games>18||m.baseline!==player.projection||!finite(m.scenario)||Math.abs(m.scenario-player.projection*m.ratio)>1e-9)return 0;
 return m.scenario-m.baseline;
}
const api={SOURCE,KEY,parse,active,annotate,adjustment,team};root.GoingDfsMatchupCsv=api;if(typeof module!=='undefined')module.exports=api;
})(globalThis);
