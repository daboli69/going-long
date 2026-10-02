const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');

const source = fs.readFileSync(path.join(__dirname, '../shared/football-slate.js'), 'utf8');
function setup() {
  const dom = new JSDOM('<main id="slate"></main>', { runScripts: 'outside-only' });
  dom.window.eval(source);
  const api = dom.window.GoingFootballSlate;
  const kickoff = '2026-10-11T17:00:00Z';
  const game = { sport: 'nfl', home: 'BAL', away: 'CIN', kickoff };
  const model = { ...game, kind: 'prop', player: 'Ja\'Marr <Chase>', market: 'rec_yds', line: 66.5, n: 12,
    flags: [{ id: 'gap', why: 'Model evidence & matchup support' }], key: 'model-contract' };
  const price = { ...game, kind: 'game', market: 'spread', side: 'Away', line: 3.5, odds: -110,
    key: 'price-contract', quoteStatus: 'fresh' };
  const callbacks = { label: c => `${c.market} ${c.line}`, confidence: () => ({ label: 'Moderate' }), score: () => 72.4,
    teamLabel: x => ({ CIN: 'Bengals', BAL: 'Ravens' }[x] || x) };
  return { dom, api, host: dom.window.document.querySelector('#slate'), game, model, price, callbacks };
}

test('group joins exact sport, kickoff and teams while keeping simultaneous games separate', () => {
  const { api, game, model, price } = setup();
  const rows = api.group([model], [price, { ...price, away: 'PIT', home: 'CLE' }, { ...price, sport: 'ncaa' },
    { ...price, kickoff: '2026-10-11T17:01:00Z' }, { ...price, home: 'bal', away: 'cin', kickoff: '2026-10-11T13:00:00-04:00' }]);
  assert.equal(rows.length, 4);
  assert.equal(rows[0].model[0], model);
  assert.equal(rows[0].price[0], price);
  assert.equal(rows[0].game, model);
  assert.notEqual(rows[0].key, rows[1].key, 'same kickoff with different teams stays distinct');
  assert.notEqual(rows[0].key, rows[2].key, 'same teams with a different sport stay distinct');
  assert.notEqual(rows[0].key, rows[3].key, 'one minute kickoff change stays distinct');
  assert.equal(rows[0].model.length, 1);
  assert.equal(rows[0].model[0], model);
  assert.equal(rows[0].price.length, 2, 'equivalent timestamp representation groups into the same game');
  assert.equal(rows[0].price[0], price);
  assert.equal(api.key({ ...game, kickoff: 'invalid' }), '');
});

test('renders research and fresh price comparison as distinct concepts and preserves candidate order', () => {
  const { api, host, model, price, callbacks } = setup();
  const second = { ...model, market: 'atd', line: null, player: 'Second Candidate' };
  const groups = api.group([model, second], [price]);
  host.innerHTML = api.render(groups, callbacks);
  const card = host.querySelector('.slate-game');
  assert.match(card.querySelector('.slate-count').textContent, /2 model-ranked research candidates · 1 fresh price comparisons/);
  assert.match(card.textContent, /Lead candidate · not a ticket suggestion/);
  assert.match(card.querySelector('strong').textContent, /Ja'Marr <Chase>/);
  assert.match(card.textContent, /Evidence: Moderate · Player GOING Score 72.4\/100 \(evidence index, not win chance\)/);
  const detail = card.querySelector('details.slate-bets');
  assert.equal(detail.open, false, 'research list begins collapsed');
  assert.equal(detail.querySelector('.slate-bets-body').innerHTML, '', 'evidence body is lazy/empty until populated');
  assert.match(detail.querySelector('summary').textContent, /View bets & why · 3 research entries/);
});

test('escapes candidate evidence and game data in generated HTML', () => {
  const { api, host, model, callbacks } = setup();
  const hostile = { ...model, away: '<img src=x onerror=alert(1)>', player: '<script>bad()</script>',
    flags: [{ id: 'gap', why: '<svg onload=alert(1)>' }] };
  host.innerHTML = api.render(api.group([hostile], []), callbacks);
  assert.equal(host.querySelectorAll('script, img, svg').length, 0);
  assert.match(host.innerHTML, /&lt;script&gt;bad\(\)&lt;\/script&gt;/);
  assert.match(host.innerHTML, /&lt;svg onload=alert\(1\)&gt;/);
});

test('NCAA has no player GOING Score action and parlay state exposes selected accessibility', () => {
  const { api, host, model, callbacks, game } = setup();
  const ncaa = { ...model, ...game, sport: 'ncaa', kind: 'game', market: 'spread', player: undefined };
  const ncaaGroup = api.group([ncaa], []);
  host.innerHTML = api.render(ncaaGroup, { ...callbacks, selected: new Set([ncaaGroup[0].key]) });
  assert.equal(host.querySelector('[data-slate-action="score"]'), null);
  const selected = host.querySelector('[data-slate-action="parlay"]');
  assert.equal(selected.getAttribute('aria-pressed'), 'true');
  assert.match(selected.textContent, /Selected for parlay/);
  const nflGroup = api.group([model], []);
  host.innerHTML = api.render(nflGroup, callbacks);
  assert.ok(host.querySelector('[data-slate-action="score"]'));
  assert.equal(host.querySelector('[data-slate-action="parlay"]').getAttribute('aria-pressed'), 'false');
});

test('render is capped at twelve games and collapsed groups can be controlled by the open set', () => {
  const { api, host, callbacks, model } = setup();
  const rows = Array.from({ length: 15 }, (_, i) => ({ ...model, home: `H${i}`, away: `A${i}`, kickoff: new Date(Date.parse(model.kickoff) + i * 3600000).toISOString() }));
  const groups = api.group(rows, []);
  host.innerHTML = api.render(groups, { ...callbacks, open: new Set([groups[1].key]), limit: 12 });
  assert.equal(host.querySelectorAll('.slate-game').length, 12);
  assert.equal(host.querySelectorAll('.slate-bets[open]').length, 1);
  assert.equal(host.querySelector('.slate-bets[open]').dataset.slateOpen, groups[1].key);
});
