import React,{useEffect,useRef,useState} from 'react';

export function HistoricalOdds({session}){
 const [index,setIndex]=useState(null),[event,setEvent]=useState(''),[market,setMarket]=useState(''),[book,setBook]=useState(''),[data,setData]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const epoch=useRef(0);
 useEffect(()=>{epoch.current++;setIndex(null);setData(null);setEvent('');setMarket('');setBook('');setBusy(false);setError('');return()=>{epoch.current++;};},[session?.access_token]);
 async function load(selected='',filter='',selectedBook='',offset=0){
  if(!session?.access_token)return;
  const run=++epoch.current;setBusy(true);setError('');setData(null);
  try{
   const query=new URLSearchParams();if(selected)query.set('event',selected);if(filter)query.set('market',filter);if(selectedBook)query.set('book',selectedBook);if(offset)query.set('offset',offset);
   const r=await fetch('/api/odds-history?'+query,{headers:{Authorization:'Bearer '+session.access_token},cache:'no-store'});
   if(!r.ok)throw Error(r.status===401?'Sign in again to access your saved odds.':'The historical archive has not finished syncing, or is temporarily unavailable.');
   const body=await r.json();if(run!==epoch.current)return;
   if(selected)setData(body);else setIndex(body);
  }catch(e){if(run===epoch.current)setError(e.message);}finally{if(run===epoch.current)setBusy(false);}
 }
 return <section className="panel" id="historical-odds"><h2>Historical odds archive</h2><p>Saved pregame sportsbook prices for reference and model research. These are historical observations; they do not replace current odds or create betting recommendations.</p>
 {!session?<p>Sign in through Personal journal to browse your private archive.</p>:<><button onClick={()=>load()} disabled={busy}>{busy?'Loading…':index?'Refresh archive index':'Load saved historical odds'}</button>
 {index&&<><p>{index.events.length.toLocaleString()} archived games · {index.quotes.toLocaleString()} price observations · {index.credits.toLocaleString()} acquisition credits. Saved data remains usable without an active odds subscription.</p>
 <label>Archived game<select value={event} onChange={e=>{const id=e.target.value;setEvent(id);setMarket('');setBook('');if(id)load(id);else{epoch.current++;setData(null);setBusy(false);}}}><option value="">Choose a completed game</option>{index.events.map(g=><option key={g.id} value={g.id}>{new Date(g.kickoff).toLocaleDateString()} · {g.away} at {g.home}</option>)}</select></label>
 {data&&<><label>Market<select value={market} onChange={e=>{setMarket(e.target.value);load(event,e.target.value,book);}}><option value="">All markets</option>{data.markets.map(m=><option key={m}>{m}</option>)}</select></label><label>Sportsbook<select value={book} onChange={e=>{setBook(e.target.value);load(event,market,e.target.value);}}><option value="">All sportsbooks</option>{data.books.map(b=><option key={b}>{b}</option>)}</select></label><p>Showing {data.total?data.offset+1:0}–{data.offset+data.quotes.length} of {data.total.toLocaleString()} saved observations. Snapshot time and bookmaker update time are shown separately.</p><div><button disabled={busy||!data.offset} onClick={()=>load(event,market,book,Math.max(0,data.offset-500))}>Previous prices</button> <button disabled={busy||data.offset+500>=data.total} onClick={()=>load(event,market,book,data.offset+500)}>More prices</button></div><div className="table-wrap" tabIndex="0" aria-label="Historical sportsbook prices, scroll horizontally for all columns"><table><thead><tr>{['Snapshot','Book','Market','Player / side','Line','Odds','Book updated'].map(s=><th key={s}>{s}</th>)}</tr></thead><tbody>{data.quotes.map(q=><tr key={q.id}><td>{new Date(q.snapshot_at).toLocaleString()}</td><td>{q.book}</td><td>{q.market}</td><td>{q.player?`${q.player} · `:''}{q.side}</td><td>{q.line??'—'}</td><td>{q.price>0?'+':''}{q.price}</td><td>{new Date(q.quote_at).toLocaleString()}</td></tr>)}</tbody></table></div></>}
 </>}</>}{error&&<p role="alert" className="error">{error}</p>}</section>;
}
