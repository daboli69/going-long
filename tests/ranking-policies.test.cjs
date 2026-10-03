'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { expectedValue, familyKey, rank, rationale, summarizeCohort } = require('../shared/ranking-policies.cjs');

const candidate = (id, overrides = {}) => ({ id, event: '2026-10-04T17:00:00Z:A-B', kind: 'prop', profileId: 'player-1', market: 'passing_yards', side: 'over', line: 249.5, prob: 0.6, dec: 1.91, odds: -110, updatedAt: '2026-10-02T23:00:00Z', ...overrides });

test('EV matches explicit win/push/loss payoffs, including zero and certain outcomes', () => {
  const row = candidate('push', { prob: 0.4, push: 0.1, dec: 3 });
  assert.ok(Math.abs(expectedValue(row) - (0.4 * 2 + 0.1 * 0 + 0.5 * -1)) < 1e-12);
  assert.equal(expectedValue(candidate('all-push', { prob: 0, push: 1 })), 0);
  assert.equal(expectedValue(candidate('all-loss', { prob: 0 })), -1);
  assert.equal(expectedValue(candidate('all-win', { prob: 1, dec: 2 })), 1);
  assert.equal(expectedValue(candidate('no-push', { prob: 0.5, dec: 2 })), 0);
});

test('EV ranking responds to payout and push, ignores Score and preserves exact ties in Champion order', () => {
  const rows = [candidate('favorite', { prob: 0.8, dec: 1.2, Score: 1000000 }), candidate('value', { prob: 0.6, dec: 2.5, Score: -1 }), candidate('tie', { prob: 0.6, dec: 2.5 }), candidate('push-value', { prob: 0.4, push: 0.4, dec: 3 })];
  assert.deepEqual(rank(rows, 'ev').map(row => row.id), ['push-value', 'value', 'tie', 'favorite']);
  assert.deepEqual(rank(rows, 'champion'), rows);
  assert.deepEqual(rank(rows, 'ev'), rank(rows, 'ev'));
});

test('ranking leaves frozen input and original objects unchanged and stays within the supplied cohort', () => {
  const rows = Object.freeze([Object.freeze(candidate('a')), Object.freeze(candidate('b', { prob: 0.7 }))]);
  const before = JSON.stringify(rows);
  for (const method of ['champion', 'ev', 'family-diversified-ev']) {
    const result = rank(rows, method);
    assert.notEqual(result, rows);
    for (const row of result) assert.ok(rows.includes(row));
  }
  assert.equal(JSON.stringify(rows), before);
  assert.equal(rank(rows, 'ev').length, rows.length);
});

test('family diversification omits line and book but preserves event, kind, participant, market and side', () => {
  const rows = [candidate('base'), candidate('better-other-line-book', { line: 299.5, dec: 2.5, book: 'other' }), candidate('under', { side: 'under' }), candidate('other-player', { profileId: 'player-2' }), candidate('other-market', { market: 'passing_tds' }), candidate('one-minute-alias', { event: '2026-10-04T17:01:00Z:A-B' }), candidate('game-spread', { kind: 'game', profileId: null, market: 'spread', side: 'A' }), candidate('game-winner', { kind: 'game', profileId: null, market: 'moneyline', side: 'A' })];
  assert.deepEqual(rank(rows, 'family-diversified-ev').map(row => row.id), ['better-other-line-book', 'under', 'other-player', 'other-market', 'one-minute-alias', 'game-spread', 'game-winner']);
  assert.equal(rank(rows, 'ev').length, 8);
  assert.equal(familyKey(rows[0]), familyKey(rows[1]));
  assert.notEqual(familyKey(rows[6]), familyKey(rows[7]));
});

test('identical rows are retained by EV and collapsed only by the declared family method', () => {
  const rows = [candidate('first'), candidate('second')];
  assert.deepEqual(rank(rows, 'ev').map(row => row.id), ['first', 'second']);
  assert.deepEqual(rank(rows, 'family-diversified-ev').map(row => row.id), ['first']);
});

test('invalid estimates are errors rather than quietly altered eligibility', () => {
  for (const overrides of [{ prob: NaN }, { prob: '0.6' }, { prob: -0.1 }, { prob: 1.1 }, { push: -0.1 }, { prob: 0.8, push: 0.3 }, { push: null }, { dec: 1 }, { dec: Infinity }]) {
    assert.throws(() => rank([candidate('invalid', overrides)], 'ev'));
  }
  assert.throws(() => rank([candidate('missing-player', { profileId: undefined })], 'family-diversified-ev'));
  assert.throws(() => rank([candidate('missing-market', { market: '' })], 'family-diversified-ev'));
  assert.throws(() => rank([], 'Score'));
});

test('frozen decision-time guard rejects newly obtained quotes for every method', () => {
  const options = { evaluationMode: 'historical', decisionTime: '2026-10-02T23:47:12Z' };
  for (const method of ['champion', 'ev', 'family-diversified-ev']) {
    assert.equal(rank([candidate('valid')], method, options).length, 1);
    assert.throws(() => rank([candidate('new', { updatedAt: '2026-10-02T23:47:12.001Z' })], method, options), /newer/);
  }
  assert.equal(rank([candidate('exact', { quoteTime: options.decisionTime, updatedAt: '2026-10-03T00:00:00Z' })], 'ev', options).length, 1);
  assert.throws(() => rank([candidate('missing', { updatedAt: undefined })], 'ev', options), /requires quoteTime/);
  assert.throws(() => rank([], 'ev', { historical: true }), /decisionTime/);
  assert.throws(() => rank([candidate('no-zone', { updatedAt: '2026-10-02T23:00:00' })], 'ev', options), /timezone/);
});

test('descriptive cohort summary reports model estimates and exact families without performance claims', () => {
  const rows = [candidate('a', { prob: 0.5, dec: 2 }), candidate('b', { prob: 0.6, dec: 2, line: 299.5 })];
  const summary = summarizeCohort(rows);
  assert.equal(summary.count, 2);
  assert.equal(summary.uniqueExactEvents, 1);
  assert.equal(summary.uniqueFamilies, 1);
  assert.equal(summary.repeatedFamilyRows, 1);
  assert.equal(summary.meanModelWinProbability, 0.55);
  assert.ok(Math.abs(summary.meanModelEVPerUnit - 0.1) < 1e-12);
  assert.equal(summary.positiveModelEVCount, 1);
  assert.equal(rationale(rows[0]).lossProbability, 0.5);
  assert.equal(summarizeCohort([]).meanModelEVPerUnit, null);
  assert.equal(summarizeCohort([]).count, 0);
});
