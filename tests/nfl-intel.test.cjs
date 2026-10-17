const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');

const source = fs.readFileSync(path.join(__dirname, '../shared/nfl-intel.js'), 'utf8');
const NOW = Date.parse('2026-10-18T12:00:00Z');

function feed(overrides = {}) {
  const game = {
    game_id: '2026_06_ARI_LA', season: 2026, week: 6, home_team: 'LA', away_team: 'ARI', kickoff_utc: '2026-10-18T20:05:00+00:00',
    status: 'scheduled', final_score: null,
    forecast: { stage: 't24h', stage_label: '24 h before kickoff', archived_at: '2026-10-17T20:05:35+00:00', timeliness: 'on_time',
      stale_inputs: false, data_refreshed_at: '2026-10-17T19:02:19+00:00',
      champion: { version: 'v20261016_212540', p_home: 0.7925, predicted_winner: 'LA', margin_home: 10.5 },
      models: [{ key: 'logreg', label: 'Logistic regression', p_home: 0.8088, margin_home: 10.7 },
               { key: 'mlp', label: 'Neural network (MLP)', p_home: 0.7743, margin_home: 7.4 }],
      disagreement: { vote: '6-0', range: 0.0547, std: 0.0199 } },
    stages: [{ stage: 't24h', archived_at: '2026-10-17T20:05:35+00:00', p_home: 0.7925, timeliness: 'on_time' }],
    challengers: [{ version: 'v20261017_142546_p7_qb_snap', label: 'Phase 7 challenger', p_home: 0.7985 }],
    player_intel: { qb: { home: { champion_assumes: 'Matthew Stafford', live_projection: 'Matthew Stafford', live_status: 'projected (sources agree)', injury_report: 'verified pregame report' },
                          away: { champion_assumes: 'Backup QB', live_projection: 'Starter QB', live_status: 'projected (sources agree)', injury_report: 'verified pregame report' } },
                    lineups: { home: { available: true, starters_expected_out: 1.1, ol_starters_expected: 5, ol_regular_starters: 5,
                                       important_absences: [{ player: 'Kam Curl', unit: 'DB', status: 'Questionable (dnp practice)', availability: 0.5 }] },
                               away: { available: false } }, lineup_note: 'analysis' },
    simulation: { experimental: true, stage: 't24h', archived_at: '2026-10-17T20:05:48+00:00', p_home: 0.80, margin_home: 16.2, total: 57.5,
                  margin_p10: -3, margin_p90: 35.7, total_p10: 29.9, total_p90: 85.5 },
    market: { at_forecast: { source: 'nfldata line at forecast data refresh', timestamp: '2026-10-17T19:02:19+00:00', p_home_novig: 0.8465, spread_home: 12.5 },
              latest: { source: 'DraftKings via ESPN', retrieved_at: '2026-10-17T22:00:34+00:00', p_home_novig_current: 0.8465, p_home_novig_open: 0.84, spread_home_current: 12.5 },
              champion_minus_market_at_forecast: -0.054, comparable: true, warning: 'Benchmark, not an edge.' },
  };
  return Object.assign({ schema: 'going-nfl-lab-feed', schema_version: '1.0.0', generated_at: '2026-10-18T10:00:00+00:00',
    source: { champion_version: 'v20261016_212540', challengers: [] }, freshness: { latest_forecast_archived_at: '2026-10-17T20:05:35+00:00', stale_after_hours: 36 },
    notices: { correlation: 'The six models read the same inputs.', market: 'Not a betting edge.', experimental: 'Experimental.', challengers: '128+ games.' },
    performance: { historical: { note: 'research-exposed', windows: [{ window: 'walk-forward 2018-22', games: 1365, accuracy: 0.646, log_loss: 0.628, brier: 0.219, margin_mae: 10.15 }] },
                   prospective: { games: 0, required_games: 128, by_version: [], note: 'No archived game has finished yet.' } },
    games: [game] }, overrides);
}

function setup() {
  const dom = new JSDOM('<section id="p"></section>', { url: 'https://going-long.test/long/', runScripts: 'outside-only' });
  dom.window.eval(source);
  return { dom, el: dom.window.document.getElementById('p'), api: dom.window.GoingNflIntel };
}

test('renders the overview, six-model debate, player intel, simulation, market and performance from the feed', () => {
  const { el, api } = setup();
  api.render(el, feed(), { now: NOW });
  const t = el.textContent;
  assert.match(t, /ARI @ LA/);
  assert.match(t, /LA 79%/);                                 // champion pick from p_home 0.7925
  assert.match(t, /\+10\.5/);                                // predicted margin
  assert.match(t, /6-0/);
  assert.match(t, /Logistic regression/);
  assert.match(t, /not six independent confirmations|read the same inputs/);
  assert.match(t, /Matthew Stafford/);
  assert.match(t, /QB differs/);                             // champion vs live monitoring mismatch is flagged
  assert.match(t, /Kam Curl/);
  assert.match(t, /Experimental/);
  assert.match(t, /DraftKings via ESPN/);
  assert.match(t, /-5\.4 pts/);                              // champion minus market, in points
  assert.match(t, /0 of 128 games/);
  assert.ok(!/Stale data/.test(t));
});

test('flags stale feeds, and degrades cleanly when the feed is missing or invalid', () => {
  const { el, api } = setup();
  api.render(el, feed({ generated_at: '2026-10-15T00:00:00+00:00' }), { now: NOW });
  assert.match(el.textContent, /Stale data/);
  api.render(el, null, { now: NOW, error: 'offline' });
  assert.match(el.textContent, /not available/);
  assert.match(el.textContent, /GOING's own predictions on the other tabs are unaffected/);
  const bad = feed();
  bad.games[0].forecast.archived_at = '2026-10-18T21:00:00+00:00';   // after kickoff: never a pregame forecast
  api.render(el, bad, { now: NOW });
  assert.match(el.textContent, /failed validation/);
  assert.deepEqual(Array.from(api.validate(feed({ schema_version: '2.0.0' }))), ['schema_version']);
});

test('QB mismatch flag ignores name suffixes', () => {
  const { el, api } = setup();
  const f = feed();
  f.games[0].player_intel.qb.away = { champion_assumes: 'Michael Penix Jr.', live_projection: 'Michael Penix', live_status: 'projected' };
  f.games[0].player_intel.qb.home = { champion_assumes: 'Matthew Stafford', live_projection: 'Matthew Stafford' };
  api.render(el, f, { now: NOW });
  assert.ok(!/QB differs/.test(el.textContent));
});

test('escapes feed text (no HTML injection from published data)', () => {
  const { el, api } = setup();
  const f = feed();
  f.games[0].player_intel.qb.home.champion_assumes = '<img src=x onerror=alert(1)>';
  api.render(el, f, { now: NOW });
  assert.equal(el.querySelector('img'), null);
});

test('API route serves the published feed, falls back, and never writes', async () => {
  const { default: handler, validFeed } = await import('../api/nfl-lab.mjs');
  const response = () => ({ headers: {}, setHeader(k, v) { this.headers[k] = v; }, end(b) { this.body = String(b); } });
  let res = response();
  await handler({ method: 'GET', url: '/api/nfl-lab', headers: {} }, res, { fetch: async () => ({ ok: true, json: async () => feed() }) });
  assert.equal(res.statusCode, 200);
  assert.equal(res.headers['X-Feed-Source'], 'published');
  assert.equal(JSON.parse(res.body).games[0].game_id, '2026_06_ARI_LA');
  res = response();
  await handler({ method: 'GET', url: '/api/nfl-lab', headers: {} }, res, { fetch: async () => { throw new Error('offline'); } });
  assert.ok([200, 503].includes(res.statusCode));             // packaged copy if one was deployed, otherwise 503
  if (res.statusCode === 503) assert.equal(JSON.parse(res.body).status, 'unavailable');
  res = response();
  await handler({ method: 'GET', url: '/api/nfl-lab', headers: {} }, res, { fetch: async () => ({ ok: true, json: async () => ({ schema: 'something-else' }) }) });
  assert.notEqual(res.headers['X-Feed-Source'], 'published');  // invalid upstream content is never served as published
  res = response();
  await handler({ method: 'POST', url: '/api/nfl-lab', headers: {} }, res);
  assert.equal(res.statusCode, 405);
  assert.equal(validFeed(feed()), true);
});

test('GOING board wiring: NFL-only section, existing sections untouched', () => {
  const html = fs.readFileSync(path.join(__dirname, '../index.html'), 'utf8');
  assert.match(html, /data-section="intel" data-tab="intel"[^>]*>NFL Intelligence</);
  assert.match(html, /<section id="btIntelPanel"/);
  assert.match(html, /\/shared\/nfl-intel\.js/);
  for (const s of ['today', 'score', 'dfs', 'opportunities', 'games', 'cheatsheets', 'research', 'parlay'])
    assert.match(html, new RegExp(`data-section="${s}"`), s);
  assert.match(html, /\[data-section="intel"\]'\)\.hidden=BET\.sport!=='nfl'/);
});
