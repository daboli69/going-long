import {mkdir,copyFile,cp,rm} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
// Vercel receives only public assets; server functions are built from /api.
const root=new URL('../',import.meta.url);
const output=new URL('dist/vercel/',root);
await rm(output,{recursive:true,force:true});
await mkdir(output,{recursive:true});
await copyFile(new URL('index.html',root),new URL('index.html',output));
await cp(new URL('data/',root),new URL('data/',output),{recursive:true});
console.log('Vercel public assets built:',fileURLToPath(output));
