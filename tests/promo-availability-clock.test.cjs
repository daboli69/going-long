const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('index.html','utf8');
const source=html.slice(html.indexOf('function promoAvailabilityClock('),html.indexOf('async function renderPromo('));
const clock=vm.runInNewContext(source+';promoAvailabilityClock');
test('Jackpot availability clock remains strict without the optional Fanatics engine',()=>{
 assert.equal(clock('2026-10-11T13:00:00-04:00'),Date.parse('2026-10-11T17:00:00Z'));
 for(const invalid of [null,'2026-10-11T17:00:00','2026-02-30T17:00:00Z','2026-10-11T24:00:00Z','2026-10-11T17:00:00+00:60'])assert.ok(Number.isNaN(clock(invalid)),String(invalid));
 assert.match(html,/availabilityFresh=Number\.isFinite\(availabilityAt\)&&now>=availabilityAt&&now-availabilityAt<=600000/);
});
