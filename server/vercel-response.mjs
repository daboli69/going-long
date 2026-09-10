import {gzipSync} from 'node:zlib';
export function sendJson(req,res,body,status=200,ttl=0){
  res.statusCode=status;
  res.setHeader('Content-Type','application/json; charset=utf-8');
  res.setHeader('X-Content-Type-Options','nosniff');
  res.setHeader('Cache-Control','no-store');
  res.setHeader('Vercel-CDN-Cache-Control',ttl>0?`public, s-maxage=${ttl}`:'no-store');
  res.setHeader('Vary','Accept-Encoding');
  const text=JSON.stringify(body);
  // Large odds feeds must remain within serverless response size limits.
  if(text.length>65536&&/\bgzip\b/i.test(req.headers?.['accept-encoding']||'')){
    res.setHeader('Content-Encoding','gzip');res.end(gzipSync(text));
  }else res.end(text);
}
