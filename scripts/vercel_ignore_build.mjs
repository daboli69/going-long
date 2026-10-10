import {execFileSync} from 'node:child_process';
import {isLiveSnapshot} from '../server/public-snapshots.mjs';

// Compare with Vercel's last successful deployment, not HEAD's first parent:
// a source commit followed by a bot data commit must still deploy the source.
// Only API-served snapshots may skip; packaged-only assets require a build.
const previous=process.env.VERCEL_GIT_PREVIOUS_SHA;
if(!/^[0-9a-f]{40}$/.test(previous||'')){
  console.log('No verified previous deployment; continuing deployment.');
  process.exit(1);
}
let changed=[];
try{
  execFileSync('git',['merge-base','--is-ancestor',previous,'HEAD'],{stdio:'pipe'});
  changed=execFileSync('git',['diff','--name-status','--no-renames','-z',previous,'HEAD'],{encoding:'utf8',stdio:'pipe'})
    .split('\0').filter(Boolean);
}catch{
  console.log('Previous deployment unavailable in local history; continuing deployment.');
  process.exit(1);
}
const dataOnly=changed.length>0&&changed.length%2===0&&changed.every((value,i)=>i%2===0?['A','M'].includes(value):value.startsWith('data/')&&isLiveSnapshot(value.slice(5)));
console.log(dataOnly?'Skipping data-only deployment; snapshots are served live.':'Application files changed; continuing deployment.');
process.exit(dataOnly?0:1);
