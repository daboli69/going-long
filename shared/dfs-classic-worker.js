'use strict';
importScripts('/shared/dfs-threshold.js','/shared/dfs-tournament.js','/shared/dfs-classic.js');
self.onmessage=e=>{try{self.postMessage({result:GoingDfsClassic.optimize(e.data.pool,e.data.options)});}catch(error){self.postMessage({error:error.message});}};
