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
 // Use the owner/kind/time cursor index and filter the small private result set in the
 // browser. JSON-expression filters and large `IN` lists caused statement timeouts on
 // production Supabase even though the same review window was otherwise inexpensive.
 const predictionRows=await pages(()=>table('prediction').gte('observed_at',since).lte('observed_at',until));
 const groups=new Set(['all_model','all_projection','best_model','best_value']);
 const predictions=predictionRows.filter(row=>row.payload?.actionable||groups.has(row.payload?.tracking_group));
 const recent=predictionRows.slice(0,100),followups=[];
 if(predictions.length){
  const predictionIds=new Set(predictions.map(row=>row.id)),actionableIds=new Set(predictions.filter(row=>row.payload?.actionable).map(row=>row.id));
  const settlements=await pages(()=>table('settlement').gte('observed_at',since).lte('observed_at',until));
  followups.push(...settlements.filter(row=>predictionIds.has(row.payload?.prediction_id)));
  if(actionableIds.size){const closings=await pages(()=>table('closing').gte('observed_at',since).lte('observed_at',until));followups.push(...closings.filter(row=>actionableIds.has(row.payload?.prediction_id)));}
 }
 const bets=await client.from('placed_bets').select('*').eq('owner_id',owner).gte('placed_at',since).order('placed_at',{ascending:false}).limit(1001);
 if(bets.error)throw bets.error;if(bets.data.length>=1000)throw Error('Too many placed bets in this window; choose fewer days.');
 const unique=new Map([...predictions,...recent,...followups].map(r=>[r.id,r]));
 return {records:[...unique.values()],actual:bets.data};
}
