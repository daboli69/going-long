const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');

const source = fs.readFileSync(path.join(__dirname, '../shared/visual-system.js'), 'utf8');
function setup() {
  const dom = new JSDOM(`<!doctype html><body data-going-workspace="long">
    <header id="going-shell"><div class="going-shell-inner">
      <a class="going-wordmark" href="/">GOING LONG</a>
      <nav class="going-global-nav"><a href="/">Home</a><a href="/long/" aria-current="page">Football</a><a href="/yard/">Baseball</a><a href="/players/">Players</a><a href="/results/">Results</a></nav>
    </div></header>
    <main class="bt-wrap"><div class="bt-head">
      <div id="btSportGroup"><button data-sport="nfl" aria-pressed="true">NFL</button><button data-sport="ncaa" aria-pressed="false">NCAA</button></div>
      <div id="btTabGroup"><button data-section="today" data-tab="best" aria-pressed="true">Today</button><button data-section="games" data-tab="games" aria-pressed="false">Games</button><button data-section="score" data-tab="score" aria-pressed="false">GOING Score</button><details class="bt-more-tools"><summary>More</summary><div><button data-section="research" data-tab="signals" aria-pressed="false">Signals</button></div></details></div>
    </div><div id="btToolGroup"></div>
    <details class="g-source-status"><summary>Data status</summary><p id="btDataNote">Observed source time</p></details>
    <div class="going-search"><input id="goingSearch" type="search" value="BUF"></div>
    <section id="btScorePanel"><input id="scoreSearch" value="Saved player query"><div id="scoreBoard"></div></section>
    <div id="bestGameSlate"></div>
    </main><nav id="glNav"><button data-view="betting" aria-current="true">Betting</button><button data-view="fantasy"><span class="ic">old icon</span>Fantasy</button><button data-view="gateway">Gateway</button></nav>
    </body>`, { url: 'https://going-long.test/long/', runScripts: 'outside-only' });
  const scrolls = [];
  dom.window.HTMLElement.prototype.scrollIntoView = function(options) { scrolls.push({ node: this, options }); };
  const doc = dom.window.document;
  const controls = {
    head: doc.querySelector('.bt-head'), league: doc.querySelector('#btSportGroup'), grid: doc.querySelector('#btTabGroup'),
    search: doc.querySelector('#goingSearch'), source: doc.querySelector('.g-source-status'), more: doc.querySelector('.bt-more-tools'),
    scoreQuery: doc.querySelector('#scoreSearch'),
  };
  dom.window.eval(source);
  return { dom, doc, controls, scrolls };
}
async function select(dom, group, dataAttribute, value) {
  group.querySelectorAll(`[${dataAttribute}]`).forEach(button => button.setAttribute('aria-pressed', String(button.getAttribute(dataAttribute) === value)));
  await new Promise(resolve => dom.window.queueMicrotask(resolve));
}

test('header search ignores inactive-view fields and prioritizes the active football query', t => {
  const { dom, doc, controls } = setup();
  t.after(() => dom.window.close());
  const inactive = doc.createElement('section');
  inactive.hidden = true;
  inactive.innerHTML = '<input type="search" id="inactiveSearch" value="private draft query">';
  doc.body.prepend(inactive);
  doc.querySelector('[data-v-search]').click();
  assert.equal(doc.activeElement, controls.search);
  assert.equal(controls.search.value, 'BUF');
  assert.equal(doc.querySelector('#inactiveSearch').value, 'private draft query');
  controls.search.closest('.going-search').hidden = true;
  const active = doc.createElement('input');
  active.type = 'search';
  doc.body.append(active);
  doc.querySelector('[data-v-search]').click();
  assert.equal(doc.activeElement, active);
});

test('Score disclosure moves and restores the same live controls without losing state or listeners', async t => {
  const { dom, doc, controls } = setup(); t.after(() => dom.window.close());
  let changes = 0, toolClicks = 0;
  controls.search.addEventListener('input', () => changes++);
  const gameButton = controls.grid.querySelector('[data-section="games"]');
  gameButton.addEventListener('click', () => toolClicks++);
  const before = [...controls.grid.querySelectorAll('button')];
  await select(dom, controls.grid, 'data-section', 'score');
  const context = doc.querySelector('.v-score-context');
  assert.equal(context.hidden, false);
  assert.equal(context.open, false);
  assert.equal(context.querySelector('.bt-head'), controls.head);
  assert.equal(context.querySelector('.g-source-status'), controls.source);
  assert.equal(context.querySelector('#goingSearch'), controls.search);
  assert.equal(doc.querySelector('.v-football-hero').hidden, true);
  assert.equal(controls.search.value, 'BUF');
  assert.equal(controls.scoreQuery.value, 'Saved player query');
  context.open = true;
  controls.search.value = 'BAL';
  controls.search.dispatchEvent(new dom.window.Event('input', { bubbles: true }));
  controls.source.open = true;
  gameButton.click();
  assert.equal(changes, 1);
  assert.equal(toolClicks, 1);
  await select(dom, controls.grid, 'data-section', 'games');
  assert.equal(context.hidden, true);
  assert.equal(controls.head.parentElement, doc.querySelector('.bt-wrap'));
  assert.equal(controls.source.parentElement, doc.querySelector('.bt-wrap'));
  assert.equal(controls.search.closest('.going-search').parentElement, doc.querySelector('.bt-wrap'));
  assert.equal(controls.search.value, 'BAL');
  assert.equal(controls.source.open, true);
  assert.deepEqual([...controls.grid.querySelectorAll('button')], before);
  assert.equal(doc.querySelectorAll('.v-football-hero').length, 1);
  assert.equal(doc.querySelectorAll('.v-score-context').length, 1);
  assert.equal(controls.source.nextElementSibling.className, 'going-search');
  assert.equal(controls.search.closest('.going-search').nextElementSibling.id, 'btScorePanel');
});

test('presentation follows NFL/NCAA and the selected tool without overriding functional pressed state', async t => {
  const { dom, doc, controls } = setup(); t.after(() => dom.window.close());
  assert.equal(doc.body.dataset.visualLeague, 'nfl');
  assert.equal(doc.body.dataset.visualTool, 'today');
  assert.match(doc.querySelector('.v-football-hero h1').textContent, /NFL TODAY/);
  await select(dom, controls.league, 'data-sport', 'ncaa');
  await select(dom, controls.grid, 'data-section', 'games');
  assert.equal(doc.body.dataset.visualLeague, 'ncaa');
  assert.equal(doc.body.dataset.visualTool, 'games');
  assert.match(doc.querySelector('.v-football-hero h1').textContent, /NCAA GAMES/);
  assert.equal(controls.league.querySelector('[aria-pressed="true"]').dataset.sport, 'ncaa');
  assert.equal(controls.grid.querySelector('button[aria-pressed="true"]').dataset.section, 'games');
  assert.equal(controls.grid.querySelector('[data-section="games"]').dataset.tab, 'games');
  await select(dom, controls.league, 'data-sport', 'nfl');
  await select(dom, controls.grid, 'data-section', 'score');
  assert.equal(doc.body.dataset.visualLeague, 'nfl');
  assert.equal(doc.body.dataset.visualTool, 'score');
  assert.equal(controls.grid.querySelector('[data-section="today"]').getAttribute('aria-pressed'), 'false');
});

test('header search focuses the existing search and preserves its query', t => {
  const { dom, doc, controls, scrolls } = setup(); t.after(() => dom.window.close());
  doc.querySelector('[data-v-search]').click();
  assert.equal(doc.activeElement, controls.search);
  assert.equal(controls.search.value, 'BUF');
  assert.equal(scrolls.at(-1).node, controls.search);
  assert.equal(scrolls.at(-1).options.block, 'center');
});

test('header data-status action opens existing evidence and focuses its summary', t => {
  const { dom, doc, controls } = setup(); t.after(() => dom.window.close());
  doc.querySelector('[data-v-status]').click();
  assert.equal(controls.source.open, true);
  assert.equal(doc.activeElement, controls.source.querySelector('summary'));
});

test('header actions reveal Score tools before focusing searches or data status inside the collapsed disclosure', async t => {
  const { dom, doc, controls } = setup(); t.after(() => dom.window.close());
  await select(dom, controls.grid, 'data-section', 'score');
  const context = doc.querySelector('.v-score-context');
  assert.equal(context.open, false);
  doc.querySelector('[data-v-search]').click();
  assert.equal(context.open, true, 'Search cannot focus a control concealed by collapsed Score context');
  assert.equal(doc.activeElement, controls.search);
  context.open = false;
  doc.querySelector('[data-v-status]').click();
  assert.equal(context.open, true, 'Data status must reveal its enclosing context before focusing evidence');
  assert.equal(controls.source.open, true);
  assert.equal(doc.activeElement, controls.source.querySelector('summary'));
});

test('Escape closes the site menu and returns focus without replacing its real routes', t => {
  const { dom, doc } = setup(); t.after(() => dom.window.close());
  const menu = doc.querySelector('.v-header-menu');
  menu.open = true;
  menu.querySelector('a[href="/players/"]').focus();
  doc.activeElement.dispatchEvent(new dom.window.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  assert.equal(menu.open, false);
  assert.equal(doc.activeElement, menu.querySelector('summary'));
  assert.deepEqual([...menu.querySelectorAll('a')].map(a => a.getAttribute('href')), ['/', '/long/', '/yard/', '/players/', '/results/']);
});

test('native More disclosure and its existing research action remain usable', async t => {
  const { dom, doc, controls } = setup(); t.after(() => dom.window.close());
  let clicked = 0;
  const button = controls.more.querySelector('[data-tab="signals"]');
  button.addEventListener('click', () => clicked++);
  const summary = controls.more.querySelector('summary');
  summary.click();
  assert.equal(controls.more.open, true);
  button.click();
  assert.equal(clicked, 1);
  await select(dom, controls.grid, 'data-section', 'research');
  assert.equal(doc.body.dataset.visualTool, 'research');
  assert.equal(controls.more.querySelector('[data-tab="signals"]'), button);
  summary.click();
  assert.equal(controls.more.open, false);
});

async function mutations(dom) {
  await new Promise(resolve => dom.window.setTimeout(resolve, 0));
}

test('new and rerendered Score cards disclose the same action nodes once, preserving direct and delegated listeners', async t => {
  const { dom, doc } = setup(); t.after(() => dom.window.close());
  const board = doc.querySelector('#scoreBoard');
  const card = doc.createElement('article');
  card.className = 'score-card';
  card.innerHTML = '<h3>Existing player</h3><details><summary>Show score data</summary><p>Actual model evidence</p></details><div class="best-actions"><button data-score-freeze="p1|atd">Freeze score</button><button data-score-market-open="p1|atd">Open market</button></div>';
  const actions = card.querySelector('.best-actions');
  const freeze = card.querySelector('[data-score-freeze]');
  const evidence = card.querySelector('details');
  let direct = 0, delegated = 0;
  freeze.addEventListener('click', () => direct++);
  board.addEventListener('click', e => { if (e.target.closest('[data-score-freeze]')) delegated++; });
  board.append(card);
  await mutations(dom);
  assert.equal(actions.parentElement, evidence);
  assert.equal(evidence.querySelector('[data-score-freeze]'), freeze);
  assert.equal(card.querySelectorAll('.best-actions').length, 1);
  evidence.open = true;
  freeze.click();
  assert.equal(direct, 1);
  assert.equal(delegated, 1);
  assert.equal(freeze.dataset.scoreFreeze, 'p1|atd');
  for (let i = 0; i < 3; i++) {
    evidence.append(doc.createElement('p'));
    await mutations(dom);
  }
  assert.equal(actions.parentElement, evidence);
  assert.equal(card.querySelectorAll('.best-actions').length, 1);
  assert.equal(card.querySelectorAll('[data-score-freeze]').length, 1);
  assert.equal(evidence.open, true);
  assert.equal(evidence.querySelector('[data-score-freeze]'), freeze);
  freeze.click();
  assert.equal(direct, 2);
  assert.equal(delegated, 2);
  const next = doc.createElement('article'); next.className = 'score-card';
  next.innerHTML = '<details><summary>New score evidence</summary></details><div class="best-actions"><button data-score-freeze="p2|atd">Freeze new score</button></div>';
  const nextActions = next.querySelector('.best-actions');
  board.replaceChildren(next);
  await mutations(dom);
  assert.equal(nextActions.parentElement, next.querySelector('details'));
  assert.equal(next.querySelectorAll('.best-actions').length, 1);
  next.querySelector('button').click();
  assert.equal(delegated, 3);
});

function slateCard(doc, sport = 'nfl') {
  const card = doc.createElement('article'); card.className = 'slate-game';
  const key = sport === 'nfl' ? 'nfl|2026-10-04T17:00:00Z|BUF|MIA' : 'ncaa|2026-10-03T19:30:00Z|Example College|Other College';
  card.innerHTML = `<header><h3>${sport === 'nfl' ? 'Buffalo Bills @ Miami Dolphins' : 'Example College @ Other College'}</h3><button data-slate-game="${key}">Choose game</button></header><div class="slate-actions"><button data-slate-parlay="${key}" aria-pressed="true">Selected for parlay</button></div><details class="slate-bets"><summary>View bets</summary><div class="slate-bets-body">Current opportunities</div></details>`;
  return card;
}

test('dynamic NFL game actions move before their actual opportunities without listener/state loss or repeated badge insertion', async t => {
  const { dom, doc } = setup(); t.after(() => dom.window.close());
  const slate = doc.querySelector('#bestGameSlate');
  const calls = [];
  dom.window.teamBadge = team => { calls.push(team); return `<span class="existing-team-badge">${team}</span>`; };
  const card = slateCard(doc);
  const title = card.querySelector('h3');
  const actions = card.querySelector('.slate-actions');
  const button = actions.querySelector('button');
  const bets = card.querySelector('.slate-bets');
  let direct = 0, delegated = 0;
  button.addEventListener('click', () => direct++);
  slate.addEventListener('click', e => { if (e.target.closest('[data-slate-parlay]')) delegated++; });
  slate.append(card);
  await mutations(dom);
  assert.deepEqual(calls, ['BUF', 'MIA']);
  assert.equal(title.getAttribute('aria-label'), 'Buffalo Bills @ Miami Dolphins');
  assert.equal(actions.parentElement, bets);
  assert.equal(actions.nextElementSibling.className, 'slate-bets-body');
  assert.equal(button.getAttribute('aria-pressed'), 'true');
  assert.equal(bets.querySelector('[data-slate-parlay]'), button);
  bets.open = true;
  button.click();
  assert.equal(direct, 1); assert.equal(delegated, 1);
  for (let i = 0; i < 3; i++) {
    card.querySelector('.slate-bets-body').append(doc.createElement('p'));
    await mutations(dom);
  }
  assert.deepEqual(calls, ['BUF', 'MIA']);
  assert.equal(title.querySelectorAll('.existing-team-badge').length, 2);
  assert.equal(card.querySelectorAll('.slate-actions').length, 1);
  assert.equal(bets.querySelector('[data-slate-parlay]'), button);
  assert.equal(bets.open, true);
  button.click();
  assert.equal(direct, 2); assert.equal(delegated, 2);
});

test('NCAA game controls compact without requiring the NFL teamBadge function or replacing actual team labels', async t => {
  const { dom, doc, controls } = setup(); t.after(() => dom.window.close());
  await select(dom, controls.league, 'data-sport', 'ncaa');
  assert.equal(typeof dom.window.teamBadge, 'undefined');
  const slate = doc.querySelector('#bestGameSlate');
  const card = slateCard(doc, 'ncaa');
  const actions = card.querySelector('.slate-actions');
  const button = actions.querySelector('button');
  let clicked = 0; button.addEventListener('click', () => clicked++);
  slate.append(card);
  await mutations(dom);
  assert.equal(card.querySelector('h3').textContent, 'Example College @ Other College');
  assert.equal(actions.parentElement, card.querySelector('.slate-bets'));
  assert.equal(button.getAttribute('aria-pressed'), 'true');
  card.querySelector('.slate-bets').open = true;
  button.click();
  assert.equal(clicked, 1);
  card.querySelector('.slate-bets-body').append(doc.createElement('p'));
  await mutations(dom);
  assert.equal(card.querySelectorAll('.slate-actions').length, 1);
  assert.equal(card.querySelector('[data-slate-parlay]'), button);
});
