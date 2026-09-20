const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

const html=fs.readFileSync('apps/yard/index.html','utf8');
const code=html.split('// SPLIT_OVERLAPS_START')[1]?.split('// SPLIT_OVERLAPS_END')[0];

test('Vercel Going Yard includes the complete Split Overlaps route',()=>{
  assert.ok(code,'Split Overlaps implementation is present');
  assert.match(html,/data-nav="splits"/);
  assert.match(html,/if\(view==='splits'\)\{safe\(renderSplitOverlaps\);return;\}/);
  assert.match(html,/"splits","dailycard"/);
});

test('Vercel Split Overlaps keeps player-board context separate and sortable',()=>{
  const context={localStorage:{getItem:()=>null,setItem:()=>{}},console};
  vm.createContext(context);vm.runInContext('// SPLIT_OVERLAPS_START'+code,context);
  const rows=[
    {id:1,game_pk:1,overlap_strength:100,batter_stats:{pa:50},pitcher_stats:{bf:30}},
    {id:2,game_pk:1,overlap_strength:80,batter_stats:{pa:100},pitcher_stats:{bf:50}},
  ];
  context.BOARD={players:[
    {id:1,game_pk:1,heat:42,hit_heat:81,hrr_heat:63,tier:'STRONG',badges:[{k:'pow',t:'POWER'}],matchup_grade:{grade:'ELITE'},why:'real board evidence'},
    {id:2,game_pk:1,heat:77,hit_heat:51,hrr_heat:71},
  ]};
  context.badgeChips=p=>`BADGES:${p.badges?.length||0}`;
  const payload={boards:{HR_OVERLAP:rows.map(r=>({...r})),HIT_OVERLAP:rows.map(r=>({...r})),HRR_OVERLAP:[]}};
  context.splitAttachBoardContext(payload);
  assert.equal(payload.boards.HR_OVERLAP[0].board_context.active_heat,42);
  assert.equal(payload.boards.HIT_OVERLAP[0].board_context.active_heat,81);
  assert.equal(context.splitVisible(payload.boards.HR_OVERLAP,{pa:50,bf:30},'board_context.active_heat',-1)[0].id,2);
  const card=context.splitBoardContext(payload.boards.HR_OVERLAP[0]);
  assert.match(card,/comparison only · not included in overlap strength/);
  assert.match(card,/BADGES:1/);assert.match(card,/HR Heat/);assert.match(card,/ELITE/);
});

test('Vercel Going Yard page scripts parse',()=>{
  for(const match of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g))new vm.Script(match[1]);
});
