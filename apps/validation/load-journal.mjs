// Load complete eligible results, plus a bounded preview of blocked checks.
export async function loadJournal(client,owner,since,until){
 const table=kind=>client.from('market_journal').select('id,kind,observed_at,payload').eq('owner_id',owner).eq('kind',kind);
 async function pages(build){
  let rows=[],cursor=null;
  for(let page=0;page<200;page++){
   let q=build().order('observed_at',{ascending:false}).order('id').limit(500);
   if(cursor)q=q.or(`observed_at.lt.${cursor.observed_at},and(observed_at.eq.${cursor.observed_at},id.gt.${cursor.id})`);
   const {data,error}=await q;if(error)throw error;rows.push(...data);
   if(data.length<500)return rows;cursor=data[data.length-1];
  }
  throw Error('This review contains too many eligible records. Choose a shorter window; incomplete results will not be scored.');
 }
 const predictions=await pages(()=>table('prediction').eq('payload->>actionable','true').gte('observed_at',since).lte('observed_at',until));
 const recent=await table('prediction').gte('observed_at',since).lte('observed_at',until).order('observed_at',{ascending:false}).order('id').limit(100);
 if(recent.error)throw recent.error;
 const followups=[];
 for(let start=0;start<predictions.length;start+=50){
  const ids=predictions.slice(start,start+50).map(p=>p.id);
  for(const kind of ['settlement','closing'])followups.push(...await pages(()=>table(kind).in('payload->>prediction_id',ids).lte('observed_at',until)));
 }
 const bets=await client.from('placed_bets').select('*').eq('owner_id',owner).gte('placed_at',since).order('placed_at',{ascending:false}).limit(1001);
 if(bets.error)throw bets.error;if(bets.data.length>=1000)throw Error('Too many placed bets in this window; choose fewer days.');
 const unique=new Map([...predictions,...recent.data,...followups].map(r=>[r.id,r]));
 return {records:[...unique.values()],actual:bets.data};
}
