const { test } = require('node:test');
const assert = require('node:assert/strict');
const { settleRow, resultRecords } = require('../shared/ranking-settlement.cjs');

const observedAt = '2026-09-21T00:00:00Z';
const opts = { observedAt, sourceRevision: 'abc123', sourceHash: 'a'.repeat(64) };
const game = { sport: 'nfl', id: 'official-1', home: 'BAL', away: 'PIT', kickoff: '2026-09-20T17:00:00Z', homeScore: 24, awayScore: 20 };
const row = { id: 'prediction-1', sport: 'nfl', kind: 'game', event: 'vendor-1',
  home: 'BAL', away: 'PIT', kickoff: '2026-09-20T17:01:00Z', frozenAt: '2026-09-20T16:00:00Z',
  market: 'spread', side: 'Home', line: -4, book: 'Fixture' };
function results(changes = {}) {
  return { schema_version: 1, generated_at: '2026-09-20T23:00:00Z',
    sources: { nfl: { status: 'loaded', checked_at: '2026-09-20T22:59:00Z' },
      ncaa: { status: 'loaded', checked_at: '2026-09-20T22:59:00Z' } },
    player_source_at: '2026-09-20T22:58:00Z', games: { one: game },
    players: { 'player-1|2026-09-20': { rec_yds: 62, atd: 0, receptions: 0 } }, ...changes };
}
const reason = (r, data = results(), settings = opts) => settleRow(r, data, settings).reason;

test('unique matchup and ET day tolerate vendor minute drift, with signed spreads and integer pushes', () => {
  assert.equal(settleRow(row, results(), opts).status, 'push');
  assert.equal(settleRow({ ...row, side: 'Away', line: -3.5 }, results(), opts).status, 'loss');
  assert.equal(settleRow({ ...row, side: 'Home', line: -3.5 }, results(), opts).status, 'win');
  assert.equal(settleRow({ ...row, market: 'total', side: 'Over', line: 44 }, results(), opts).status, 'push');
  assert.equal(settleRow({ ...row, market: 'total', side: 'Under', line: 44.5 }, results(), opts).status, 'win');
  assert.equal(settleRow({ ...row, market: 'moneyline', side: 'Away', line: 0 }, results(), opts).status, 'loss');
  assert.equal(settleRow(row, results(), opts).actual, 0);
  assert.deepEqual(settleRow(row, results(), opts).provenance.game,
    { id: game.id, sport: game.sport, home: game.home, away: game.away, kickoff: game.kickoff });
});

test('NCAA full-game finals settle, but swapped teams, ET date changes, aliases, and duplicate matches do not', () => {
  const ncaaGame = { ...game, sport: 'ncaa', id: '401', home: 'North Carolina', away: 'Duke' };
  const ncaaRow = { ...row, sport: 'ncaa', home: ' North  Carolina ', away: 'duke', market: 'moneyline', side: 'Home', line: 0 };
  assert.equal(settleRow(ncaaRow, results({ games: { one: ncaaGame } }), opts).status, 'win');
  assert.equal(reason({ ...ncaaRow, home: 'UNC' }, results({ games: { one: ncaaGame } })), 'official_final_missing');
  assert.equal(reason({ ...ncaaRow, home: 'Duke', away: 'North Carolina' }, results({ games: { one: ncaaGame } })), 'official_final_missing');
  assert.equal(reason({ ...ncaaRow, kickoff: '2026-09-21T17:00:00Z' }, results({ games: { one: ncaaGame } })), 'upcoming');
  assert.equal(reason(ncaaRow, results({ games: { one: ncaaGame, two: { ...ncaaGame, id: '402', homeScore: 10 } } })), 'ambiguous_game');
});

test('chronology, source provenance, source status, and partial finals are required', () => {
  assert.equal(reason({ ...row, frozenAt: game.kickoff }), 'not_before_official_kickoff');
  assert.equal(reason({ ...row, frozenAt: row.kickoff }), 'invalid_prediction_chronology');
  assert.equal(reason(row, results(), { ...opts, observedAt: '2026-09-20T20:00:00Z' }), 'results_chronology');
  assert.equal(reason(row, results({ generated_at: '2026-09-20T16:00:00Z' })), 'results_chronology');
  assert.equal(reason(row, results({ sources: { nfl: { status: 'unavailable', checked_at: '2026-09-20T22:59:00Z' } } })), 'game_source_unverified');
  assert.equal(reason(row, results({ games: { one: { ...game, homeScore: null } } })), 'partial_final');
  assert.equal(reason(row, results(), { ...opts, sourceHash: 'bad' }), 'source_identity_missing');
  assert.equal(reason({ ...row, market: 'total_1h' }), 'unsupported_settlement_rules');
  assert.equal(reason({ ...row, period: '1h' }), 'unsupported_settlement_rules');
});

test('player metrics require exact profile and ET day with an observed finite value', () => {
  const prop = { ...row, kind: 'prop', profileId: 'player-1', player: 'Receiver', market: 'rec_yds', side: 'Over', line: 62 };
  assert.equal(settleRow(prop, results(), opts).status, 'push');
  assert.equal(settleRow({ ...prop, market: 'receptions', side: 'Under', line: .5 }, results(), opts).status, 'win');
  assert.equal(reason({ ...prop, profileId: 'absent' }), 'player_participation_or_result_missing');
  assert.equal(reason(prop, results({ players: { 'player-1|2026-09-20': { rec_yds: null } } })), 'player_market_result_missing');
  assert.equal(reason(prop, results({ player_source_at: '2026-09-20T16:00:00Z' })), 'player_source_unverified');
  assert.equal(reason({ ...prop, sport: 'ncaa' }, results({ games: { one: { ...game, sport: 'ncaa' } } })), 'player_source_unsupported');
  assert.equal(reason({ ...prop, market: 'first_td' }), 'unsupported_settlement_rules');
});

test('negative observed yardage is valid; count and TD results must be nonnegative integers', () => {
  for (const market of ['rush_yds', 'pass_yds', 'rec_yds']) {
    const prop = { ...row, kind: 'prop', profileId: 'player-1', market, side: 'Under', line: .5 };
    const data = results({ players: { 'player-1|2026-09-20': { [market]: -2 } } });
    assert.equal(settleRow(prop, data, opts).status, 'win');
    assert.equal(settleRow(prop, data, opts).actual, -2);
  }
  for (const market of ['receptions', 'pass_tds', 'rush_tds', 'rec_tds', 'atd']) {
    const prop = { ...row, kind: 'prop', profileId: 'player-1', market, side: market === 'atd' ? 'Yes' : 'Over', line: .5 };
    for (const invalid of [-1, .5]) {
      const data = results({ players: { 'player-1|2026-09-20': { [market]: invalid } } });
      assert.equal(reason(prop, data), 'player_market_result_invalid');
    }
  }
});

test('ATD uses the issued Yes at 0.5 contract; missing participation and book voids are not inferred', () => {
  const prop = { ...row, kind: 'prop', profileId: 'absent', market: 'atd', side: 'Yes', line: .5 };
  assert.equal(settleRow(prop, results(), opts).status, 'unresolved');
  assert.equal(reason(prop), 'player_participation_or_result_missing');
  assert.equal(settleRow({ ...prop, profileId: 'player-1' }, results(), opts).status, 'loss');
  assert.equal(settleRow({ ...prop, profileId: 'player-1' }, results({ players: { 'player-1|2026-09-20': { atd: 1 } } }), opts).status, 'win');
  assert.equal(reason({ ...prop, profileId: 'player-1', side: 'No' }), 'invalid_prediction_terms');
  assert.equal(reason({ ...prop, profileId: 'player-1', line: 1 }), 'invalid_prediction_terms');
  assert.equal(reason({ ...prop, profileId: 'player-1', market: 'first_td' }), 'unsupported_settlement_rules');
});

test('resultRecords returns settled candidates without changing the snapshot or results', () => {
  const input = { rows: [row, { ...row, id: 'unresolved', kind: 'prop', profileId: 'missing', market: 'atd', side: 'Yes', line: .5 }] };
  const data = results();
  const beforeInput = JSON.stringify(input), beforeData = JSON.stringify(data);
  const records = resultRecords(input, data, opts);
  assert.equal(records.length, 1);
  assert.equal(records[0].predictionId, row.id);
  assert.equal(records[0].status, 'push');
  assert.equal(records[0].provenance.sourceRevision, opts.sourceRevision);
  assert.equal(records[0].provenance.sourceHash, opts.sourceHash);
  assert.equal(JSON.stringify(input), beforeInput);
  assert.equal(JSON.stringify(data), beforeData);
});
