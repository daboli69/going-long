/* Public snapshots follow data refreshes even when Vercel skips a UI build. */
(function(root){'use strict';
async function load(file){
 for(const url of ['/api/snapshot?file='+encodeURIComponent(file),'/data/'+file]){
  try{const response=await fetch(url,{cache:'no-cache',signal:AbortSignal.timeout(15000)});if(response.ok)return await response.json();}catch{}
 }
 throw Error('Published snapshot unavailable: '+file);
}
root.GoingLiveSnapshot={load};
})(globalThis);
