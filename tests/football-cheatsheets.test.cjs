const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');

const source = fs.readFileSync(path.join(__dirname, '../shared/football-cheatsheets.js'), 'utf8');
function setup() {
  const dom = new JSDOM('<main id="sheet"></main>', { url: 'https://going-long.test/long/', runScripts: 'outside-only' });
  dom.window.eval(source);
  const later = new Date(Date.now() + 86400000).toISOString();
  const profile = { id: 'p1', name: 'Test Runner', position: 'RB', team: 'BUF', games: [
    { season: 2026, date: '2026-09-10', receptions: 5, rush_yds: 67, atd: 1 },
    { season: 2026, date: '2026-09-17', receptions: 3, rush_yds: 42, atd: 0 },
    { season: 2026, date: '2026-09-24', receptions: 7, rush_yds: 81, atd: 1 },
  ] };
  const props = ['Book A', 'Book B'].map((book, i) => ({
    id: `q${i}`, eventId: 'event1', profileId: 'p1', player: profile.name, team: 'BUF', opp: 'MIA',
    homeName: 'Buffalo Bills', awayName: 'Miami Dolphins', market: 'receptions', line: 4.5,
    overOdds: i ? -105 : -110, underOdds: -110, book, bookKey: book.toLowerCase(),
    kickoff: later, updatedAt: new Date().toISOString(), model: { family: 'lognormal', n: 3 }, projMean: 5.1, projSd: 1.2,
  }));
  props.push({ id: 'td', eventId: 'event1', profileId: 'p1', player: profile.name, team: 'BUF', opp: 'MIA',
    market: 'atd', line: null, overOdds: 140, book: 'Book A', bookKey: 'booka', kickoff: later,
    updatedAt: new Date().toISOString(), model: { family: 'poisson', n: 3 }, projMean: 0.4, projSd: 0.5 });
  const weakness = { id: 'MIA|RB_RUSHING', defense: 'MIA', current_status: 'persisting', confidence: 'medium',
    historical: { season: 2025, sample: 120, games: 16, yards_per_opportunity: 4.2, explosive_rate: .12, redzone_rate: .17 },
    current: { season: 2026, sample: 30, games: 3, yards_per_opportunity: 4.7, explosive_rate: .16, redzone_rate: .2 },
    weights: { historical_weight: .2, current_weight: .8, historical_effective_sample: 24 },
    opponent_adjustment: 'Opponent adjusted', lineage: ['football_context.scopes.2026.defense_rushing'] };
  const context = { season: 2026, as_of: '2026-09-28', scopes: { '2026': {
    players: { p1: { player_id: 'p1', name: profile.name, team: 'BUF', position: 'RB', games: 3, last_game: '2026-09-24',
      targets: 15, target_share: .2, rush_attempts: 45, rush_share: .42, share: .68, share_type: 'offensive_snap_share',
      offense_snaps: 80, team_snaps: 117, routes: 30, charting_coverage: .8 } },
    teams: { BUF: { games: 3, plays_per_game: 62, pace_seconds: 28, pass_over_expected: .03, opening_pass_rate: .52, rb_target_share: .2, te_target_share: .15 },
      MIA: { games: 3, plays_per_game: 60, pace_seconds: 29 } },
    defense_receiving: { 'MIA|WR': { targets: 50, yards: 380, explosives: 4, explosive_rate: .08, yards_per_target: 7.6, redzone_target_rate: .16, games: 3, status: 'too_few_plays', depth: { deep: { targets: 8, yards_per_target: 12 } } } },
    defense_rushing: { 'MIA|RB': { carries: 70, yards: 315, explosives: 5, explosive_rate: .071, yards_per_carry: 4.5, redzone_carry_rate: .13, games: 3, status: 'too_few_plays' } },
  } } };
  const learning = {
    generated_at: new Date().toISOString(), defensive_weaknesses: [weakness],
    matchup_signals: [{ id: 'm1', player_id: 'p1', player: profile.name, team: 'BUF', opponent: 'MIA', role: 'RB_RUSHING',
      kickoff: later, status: 'persisting', confidence: 'medium', active_signal: true, plain_language: 'Role-matched matchup evidence.',
      usage: { games: 3, opportunities: 45, share: .42, snap_share: .68, snap_share_type: 'offensive_snap_share' }, weakness_id: weakness.id,
      lineage: ['season_learning.matchup_signals'] }],
    coverage_matchup_signals: [{ id: 'c1', player_id: 'p1', qb_id: 'qb1', qb: 'Test QB', team: 'BUF', opponent: 'MIA', role: 'RB_RECEIVING', kickoff: later,
      active_signal: false, plain_language: 'Conditional coverage watch.', projected_game_state: { period: '1H', defense_margin: 2.5, bucket: 'leading_1_7' },
      coverage_tendency: { season: 2025, shell: 'COVER_2', rate: .25, plays: 45, state_dropbacks: 180, state_games: 12, overall_rate: .2 },
      qb_tendency: { season: 2025, position: 'RB', target_rate: .22, overall_target_rate: .18, targets: 22, dropbacks: 100, games: 8 },
      defense_role_weakness: { status: 'uncertain', confidence: 'low' }, coverage_role_results: { targets: 30, games: 12, yards_per_target: 7.1 },
      beneficiaries: [{ player_id: 'p1', player: profile.name, targets: 15, target_share: .2 }], lineage: ['football_context.scopes.2025'] }],
  };
  const game = { id: 'g1', sport: 'nfl', home: 'BUF', homeCode: 'BUF', away: 'MIA', awayCode: 'MIA', kickoff: later,
    model: { margin_mean: 2, total_mean: 44, home_n: 3, away_n: 3, home_wp: .56 }, spread: -2, total: 44,
    homeSpreadOdds: -110, awaySpreadOdds: -110, overOdds: -110, underOdds: -110, mlHome: -130, mlAway: 110,
    book: 'Book A', updatedAt: new Date().toISOString() };
  const data = { sport: 'nfl', season: 2026, asOf: '2026-09-28', priceStatus: 'live', props, games: [game],
    schedule: [{ home: 'BUF', away: 'MIA', kickoff: later }], history: { generated_at: new Date().toISOString(), profiles: { p1: profile },
      features: { nfl: { players: { 'BUF|p1': { last_game: '2026-09-24', route_participation: .7, charting_coverage: .8, participation_charted_dropbacks: 90,
        shares: { red_zone_targets: .18, goal_line_carries: .25 } } } } } }, context, learning,
    isCurrentProp: () => true, isCurrentGame: () => true, quoteStatus: () => null, freshGameQuote: () => true, currentGameMarket: () => true,
    bestGameLines: quotes => ({ spread: quotes[0], total: quotes[0], ml: quotes[0] }),
    evaluateQuote: p => ({ probabilities: { over: .58, under: .42, push: 0 }, best: { side: 'Over', prob: .58, ev: .04, trust: { reasons: [] } } }),
  };
  return { dom, data, profile };
}

test('NFL cheatsheets render sourced market, results, role, matchup, coverage, team, defense, line and odds views', () => {
  const { dom, data } = setup();
  const host = dom.window.document.querySelector('#sheet');
  const api = dom.window.GoingFootballCheatsheets;
  assert.ok(api, 'cheatsheets module registers its public renderer');
  api.render(host, data);
  for (const sheet of ['markets','game-lines','hit-rates','roles','matchups','coverage','teams','defense','odds']) {
    const button = host.querySelector(`[data-cheat-sheet="${sheet}"]`);
    assert.ok(button, `has ${sheet} sheet navigation`);
    button.click();
    assert.match(host.textContent, /Cheatsheets/);
    assert.doesNotMatch(host.textContent, /\[object Object\]/);
  }
  host.querySelector('[data-cheat-sheet="hit-rates"]').click();
  assert.match(host.textContent, /Observed over rate/);
  assert.match(host.textContent, /3 decisive games/);
  host.querySelector('[data-cheat-sheet="roles"]').click();
  assert.match(host.textContent, /Target share/);
  assert.match(host.textContent, /Passing-snap proxy|Offensive snap share/);
  host.querySelector('[data-cheat-sheet="coverage"]').click();
  assert.match(host.textContent, /COVER_2/);
  host.querySelector('[data-cheat-sheet="game-lines"]').click();
  assert.match(host.textContent, /GOING margin/);
  dom.window.close();
});

test('NCAA does not present NFL-only charting sheets as supported', () => {
  const { dom, data } = setup();
  data.sport = 'ncaa';
  const host = dom.window.document.querySelector('#sheet');
  dom.window.GoingFootballCheatsheets.render(host, data);
  assert.match(host.textContent, /currently use NFL charting and season data/);
  dom.window.close();
});

test('active filter chips expose hidden research context and independently clear filters',()=>{
 const {dom,data}=setup(),host=dom.window.document.querySelector('#sheet');dom.window.GoingFootballCheatsheets.render(host,data);
 host.querySelector('[data-cheat-sheet="hit-rates"]').click();
 function set(key,value){const field=host.querySelector(`[data-cheat-filter="${key}"]`);field.value=value;field.dispatchEvent(new dom.window.Event('change',{bubbles:true}));}
 set('market','receptions');set('book','Book A');set('team','MIA');
 assert.equal(host.querySelectorAll('.gcs-row').length,0);
 const summary=host.querySelector('.gcs-active-filters');assert.ok(summary);
 assert.match(summary.textContent,/Team: MIA/);assert.match(summary.textContent,/Market: Receptions/);assert.match(summary.textContent,/Book: Book A/);
 assert.equal(host.querySelector('[data-cheat-filters]').getAttribute('aria-expanded'),'false');
 const clear=host.querySelector('[data-cheat-clear="team"]');clear.focus();clear.click();
 assert.equal(host.querySelector('[data-cheat-filter="team"]').value,'ALL');
 assert.equal(host.querySelector('[data-cheat-filter="market"]').value,'receptions');assert.equal(host.querySelector('[data-cheat-filter="book"]').value,'Book A');
 assert.equal(host.querySelectorAll('.gcs-row').length,1);assert.ok(dom.window.document.activeElement.matches('[data-cheat-clear]'));
 host.querySelector('[data-cheat-reset]').click();assert.equal(host.querySelector('.gcs-active-filters'),null);
 dom.window.close();
});

test('sample and window chips reset only their criterion and return focus when the last chip is removed',()=>{
 const {dom,data}=setup(),host=dom.window.document.querySelector('#sheet');dom.window.GoingFootballCheatsheets.render(host,data);
 host.querySelector('[data-cheat-sheet="hit-rates"]').click();
 for(const [key,value] of [['window','last5'],['minGames','4']]){const field=host.querySelector(`[data-cheat-filter="${key}"]`);field.value=value;field.dispatchEvent(new dom.window.Event('change',{bubbles:true}));}
 assert.equal(host.querySelectorAll('.gcs-row').length,0);
 host.querySelector('[data-cheat-clear="minGames"]').click();assert.equal(host.querySelector('[data-cheat-filter="window"]').value,'last5');
 assert.ok(host.querySelectorAll('.gcs-row').length>0);
 const final=host.querySelector('[data-cheat-clear="window"]');final.focus();final.click();
 assert.equal(host.querySelector('[data-cheat-filter="window"]').value,'season');assert.equal(host.querySelector('.gcs-active-filters'),null);
 assert.equal(dom.window.document.activeElement,host.querySelector('[data-cheat-reset]'));
 dom.window.close();
});

test('cheatsheet navigation and filter toggles preserve keyboard focus after repaint', () => {
  const {dom,data}=setup(),host=dom.window.document.querySelector('#sheet');
  dom.window.GoingFootballCheatsheets.render(host,data);
  for(const selector of ['[data-cheat-sheet="hit-rates"]','[data-cheat-filters]','[data-cheat-fresh]','[data-cheat-reset]']){
    const control=host.querySelector(selector);assert.ok(control,selector);control.focus();control.click();
    assert.equal(dom.window.document.activeElement,host.querySelector(selector),selector);
  }
  const mobile=host.querySelector('[data-cheat-select]');mobile.focus();mobile.value='roles';
  mobile.dispatchEvent(new dom.window.Event('change',{bubbles:true}));
  assert.equal(dom.window.document.activeElement,host.querySelector('[data-cheat-select]'));
  assert.equal(dom.window.document.activeElement.value,'roles');
  dom.window.close();
});

test('pagination retains focus and hands it to the result count when all rows are shown', () => {
  const {dom,data}=setup(),host=dom.window.document.querySelector('#sheet'),players=data.context.scopes['2026'].players;
  for(let i=2;i<=85;i++)players['p'+i]={...players.p1,player_id:'p'+i,name:'Player '+i};
  dom.window.GoingFootballCheatsheets.render(host,data);
  let more=host.querySelector('[data-cheat-more]');more.focus();more.click();
  assert.equal(dom.window.document.activeElement,host.querySelector('[data-cheat-more]'));
  more=host.querySelector('[data-cheat-more]');more.click();
  assert.equal(host.querySelectorAll('.gcs-row').length,85);
  assert.equal(dom.window.document.activeElement,host.querySelector('.gcs-count'));
  dom.window.close();
});

test('mobile sheet selection shows real game bars and preserves exact line outcomes', () => {
  const {dom,data}=setup(),host=dom.window.document.querySelector('#sheet');
  dom.window.GoingFootballCheatsheets.render(host,data);
  const select=host.querySelector('[data-cheat-select]');select.value='hit-rates';select.dispatchEvent(new dom.window.Event('change',{bubbles:true}));
  const market=host.querySelector('[data-cheat-filter="market"]');market.value='receptions';market.dispatchEvent(new dom.window.Event('change',{bubbles:true}));
  const chart=host.querySelector('.gcs-history');assert.ok(chart);
  assert.equal(chart.querySelectorAll('rect.over').length,2);assert.equal(chart.querySelectorAll('rect.under').length,1);
  assert.match(chart.textContent,/2026-09-10: 5, over/);assert.match(chart.textContent,/line 4.5/);
  assert.equal(host.querySelector('.gcs-row').open,true);
  assert.doesNotMatch(chart.innerHTML,/NaN|Infinity/);dom.window.close();
});

test('compact sheet pagination retains the full filtered population and reset restores it', () => {
  const {dom,data}=setup(),host=dom.window.document.querySelector('#sheet'),players=data.context.scopes['2026'].players,base=players.p1;
  for(let i=2;i<=85;i++)players['p'+i]={...base,player_id:'p'+i,name:'Player '+i,target_share:i/100};
  dom.window.GoingFootballCheatsheets.render(host,data);
  assert.equal(host.querySelectorAll('.gcs-row').length,40);assert.match(host.querySelector('.gcs-count').textContent,/85 rows/);
  host.querySelector('[data-cheat-more]').click();assert.equal(host.querySelectorAll('.gcs-row').length,80);
  host.querySelector('[data-cheat-more]').click();assert.equal(host.querySelectorAll('.gcs-row').length,85);
  const team=host.querySelector('[data-cheat-filter="team"]');team.value='MIA';team.dispatchEvent(new dom.window.Event('change',{bubbles:true}));
  assert.equal(host.querySelectorAll('.gcs-row').length,0);
  host.querySelector('[data-cheat-reset]').click();assert.equal(host.querySelectorAll('.gcs-row').length,40);
  assert.match(host.querySelector('.gcs-row summary').textContent,/Player 85/);dom.window.close();
});

function usageFixture(data){
 const scope=data.context.scopes['2026'];
 scope.player_game_usage={
  third:{player_id:'p1',team:'BUF',game_id:'2026_03_BUF_MIA',date:'2026-09-24',targets:7,rush_attempts:18},
  first:{player_id:'p1',team:'BUF',game_id:'2026_01_BUF_NE',date:'2026-09-10',targets:2,rush_attempts:9},
  second:{player_id:'p1',team:'BUF',game_id:'2026_02_NYJ_BUF',date:'2026-09-17',targets:0},
 };
 return scope;
}
test('roles expose chronological opportunity counts, latest usage and bounded source evidence',()=>{
 const {dom,data}=setup(),scope=usageFixture(data),host=dom.window.document.querySelector('#sheet');
 dom.window.GoingFootballCheatsheets.render(host,data);
 const mini=host.querySelector('.gcs-usage-mini');assert.ok(mini);
 assert.match(mini.textContent,/Latest recorded.*Sep 24.*7 targets.*18 carries/);
 const log=host.querySelector('.gcs-usage-log');assert.ok(log);
 assert.match(log.textContent,/nflverse.*2026-09-28/);
 const rows=[...log.querySelectorAll('tbody tr')];assert.equal(rows.length,3);
 assert.deepEqual(rows.map(r=>r.querySelector('th').textContent),['2026-09-10','2026-09-17','2026-09-24']);
 assert.match(rows[1].textContent,/NYJ.*0.*—/,'observed zero remains zero; absent carry count is unavailable');
 assert.match(log.textContent,/Missing games.*not filled with zeros/);
 assert.match(log.textContent,/qualifying regulation/);
 assert.equal(log.querySelectorAll('figure').length,2);
 assert.match(log.textContent,/9\.0|9/);
 assert.deepEqual(scope.player_game_usage.second,{player_id:'p1',team:'BUF',game_id:'2026_02_NYJ_BUF',date:'2026-09-17',targets:0});
 dom.window.close();
});
test('usage ignores cross-team, prior-season, malformed, conflicting, future and cutoff-day rows',()=>{
 const {dom,data}=setup(),scope=usageFixture(data),host=dom.window.document.querySelector('#sheet');
 const valid=scope.player_game_usage.third;
 Object.assign(scope.player_game_usage,{
  wrongPlayer:{...valid,player_id:'p2'},wrongTeam:{...valid,team:'MIA'},prior:{...valid,game_id:'2025_03_BUF_MIA'},
  future:{...valid,game_id:'2026_06_BUF_MIA',date:'2026-10-15'},cutoff:{...valid,game_id:'2026_04_BUF_MIA',date:'2026-09-28'},
  invalidDate:{...valid,game_id:'2026_05_BUF_MIA',date:'2026-09-31'},badCounts:{...valid,game_id:'2026_06_BUF_MIA',date:'2026-09-25',targets:-1,rush_attempts:1.5},
  conflict:{...scope.player_game_usage.first,targets:8},duplicate:{...scope.player_game_usage.second},
 });
 dom.window.GoingFootballCheatsheets.render(host,data);
 const rows=host.querySelectorAll('.gcs-usage-log tbody tr');assert.equal(rows.length,2,'conflicting game excluded; identical duplicate counted once');
 assert.doesNotMatch(host.querySelector('.gcs-usage-log').textContent,/2026-09-10|2026-10-15|2026-09-28.*BUF/);
 dom.window.close();
});
test('latest usage sorting retains missingness and ignores unknown player identity',()=>{
 const {dom,data}=setup(),scope=usageFixture(data),host=dom.window.document.querySelector('#sheet');
 scope.players.p2={...scope.players.p1,player_id:'p2',name:'Other Receiver',position:'WR'};
 scope.player_game_usage.other={player_id:'p2',team:'BUF',game_id:'2026_03_BUF_MIA',date:'2026-09-24',targets:10};
 dom.window.GoingFootballCheatsheets.render(host,data);
 const sort=host.querySelector('[data-cheat-filter="sort"]');sort.value='latest_targets';sort.dispatchEvent(new dom.window.Event('change',{bubbles:true}));
 assert.match(host.querySelector('.gcs-row h3').textContent,/Other Receiver/);
 const next=host.querySelector('[data-cheat-filter="sort"]');next.value='latest_carries';next.dispatchEvent(new dom.window.Event('change',{bubbles:true}));
 assert.match(host.querySelector('.gcs-row h3').textContent,/Test Runner/);
 delete scope.player_game_usage;dom.window.GoingFootballCheatsheets.render(host,{...data,context:{...data.context}},true);
 assert.equal(host.querySelector('.gcs-usage-mini'),null);assert.match(host.textContent,/Opportunity log unavailable/);
 dom.window.close();
});

test('usage follows NFL season identity across January and fails closed without a dated cutoff',()=>{
 const {dom,data}=setup(),scope=usageFixture(data),host=dom.window.document.querySelector('#sheet');
 data.context.as_of='2027-01-10';data.asOf='2027-01-10';
 scope.player_game_usage.january={player_id:'p1',team:'BUF',game_id:'2026_18_BUF_NE',date:'2027-01-03',targets:5,rush_attempts:22};
 scope.player_game_usage.badYear={player_id:'p1',team:'BUF',game_id:'2026_01_BUF_NE',date:'2025-09-01',targets:8};
 dom.window.GoingFootballCheatsheets.render(host,data);
 assert.match(host.querySelector('.gcs-usage-mini').textContent,/Jan 3.*5 targets.*22 carries/);
 assert.equal(host.querySelectorAll('.gcs-usage-log tbody tr').length,4);
 delete data.context.as_of;delete data.asOf;dom.window.GoingFootballCheatsheets.render(host,data,true);
 assert.equal(host.querySelector('.gcs-usage-log'),null);assert.match(host.textContent,/Opportunity log unavailable/);
 dom.window.close();
});
