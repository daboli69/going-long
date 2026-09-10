import {defineConfig} from 'vite';
import {sites} from '@openai/sites-vite-plugin';
import {oddsResponse} from './server/worker.mjs';

export default defineConfig({
  publicDir:false,
  plugins:[sites(),{
    name:'going-long-local-odds',
    configureServer(server){
      server.middlewares.use(async(req,res,next)=>{
        if(!req.url?.startsWith('/api/odds'))return next();
        try{
          const response=await oddsResponse(new Request('http://127.0.0.1:8765'+req.url,{method:req.method}),{PARLAY_API_KEY:process.env.PARLAY_API_KEY});
          res.statusCode=response.status;for(const [k,v]of response.headers)res.setHeader(k,v);
          res.end(await response.text());
        }catch{res.statusCode=500;res.end('{"error":"Local odds service unavailable"}');}
      });
    }
  }],
  server:{host:'127.0.0.1',port:8765,strictPort:true},
  build:{ssr:'server/worker.mjs',outDir:'dist/server',emptyOutDir:false,
    rollupOptions:{output:{entryFileNames:'index.js',format:'es'}}}
});
