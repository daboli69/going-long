import {execFileSync} from 'node:child_process';

// Nightly snapshots are read from the allowlisted /api/snapshot route, so a
// data-only bot commit must not consume the Hobby plan's single build slot.
// Any source/config/workflow change still builds normally.
let changed=[];
try{
  changed=execFileSync('git',['diff','--name-only','HEAD^','HEAD'],{encoding:'utf8'})
    .split(/\r?\n/).filter(Boolean);
}catch{
  process.exit(1);
}
const dataOnly=changed.length>0&&changed.every(path=>path.startsWith('data/'));
console.log(dataOnly?'Skipping data-only deployment; snapshots are served live.':'Application files changed; continuing deployment.');
process.exit(dataOnly?0:1);
