'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {readRecords, hashPayload} = require('../shared/ranking-journal.cjs');
const {COLUMNS, storeSnapshot, materialize} = require('../shared/ranking-snapshot.cjs');
const {captureAt, validateSnapshot, invalidateSnapshot, textHash} = require('../research/today-ranking/collect.cjs');

test('provenance hashes survive Git CRLF conversion without ignoring substantive edits', () => {
  assert.equal(textHash('line1\r\nline2\r\n'), textHash('line1\nline2\n'));
  assert.notEqual(textHash('line1 \nline2\n'), textHash('line1\nline2\n'));
  assert.notEqual(textHash('{"p":0.5}\r\n'), textHash('{"p":0.6}\n'));
});

const fixedAt = '2026-10-03T03:30:00.000Z';
const sourceRoot = path.resolve(__dirname, '..');
const sourceNames = ['history','nfl_betting','ncaa_lines','football_context','season_learning','injury_context','players','football_game_validation','football_role_validation','data'];
const sourceFixtureAt = (() => {
  const times = sourceNames.map(name => {
    const value = JSON.parse(fs.readFileSync(path.join(sourceRoot, 'data', name + '.json')));
    const generated = value.generated_at ?? value.generatedAt ?? value.betting?.generated_at ?? null;
    if (generated === null) return null;
    const time = Date.parse(generated);
    if (!Number.isFinite(time)) throw new Error('Invalid fixture input generation time: ' + name);
    return time;
  }).filter(time => time !== null);
  if (!times.length) throw new Error('Actual source fixture has no generation time');
  return new Date(Math.max(...times) + 60_000).toISOString();
})();
function tempJournal(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ranking-capture-'));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  return root;
}
function row(id, evidence = {source: 'fixture', input: [1, 2]}) {
  const item = Object.fromEntries(COLUMNS.map(column => [column, null]));
  Object.assign(item, {id, kind: 'game', sport: 'nfl', updatedAt: '2026-10-03T03:29:00.000Z', evidence,
    eligibility: {eligible: false}, frozenAt: fixedAt, quoteAgeSeconds: 60, quoteFresh5m: true});
  return item;
}
function snapshot(rows = [row('r0')]) {
  return {schemaVersion: 1, decisionTime: fixedAt, sourceRevision: 'fixture', rows,
    preCandidateExclusions: [{id: 'excluded-1', reason: 'stale'}], gameExclusions: [{id: 'game-1', reason: 'manual'}], scopes: []};
}

test('columnar storage roundtrips the complete pool and reuses immutable chunks', t => {
  const directory = tempJournal(t);
  const original = snapshot(Array.from({length: 1201}, (_, i) => row('r' + i)));
  const first = storeSnapshot(directory, original, 'slot:1');
  const initial = readRecords(directory);
  assert.equal(initial.filter(record => record.kind === 'snapshot').length, 1);
  assert.ok(first.payload.chunks.filter(ref => ref.field === 'rows').length >= 2);
  assert.equal(first.payload.counts.evidence, 1);
  assert.deepEqual(materialize(first, initial), original);
  const second = storeSnapshot(directory, original, 'slot:2');
  const after = readRecords(directory);
  assert.equal(after.length, initial.length + 1);
  assert.deepEqual(second.payload.chunks, first.payload.chunks);
  assert.deepEqual(materialize(second, after), original);
});

test('schema drift and changed derived times fail before any chunk is published', t => {
  const directory = tempJournal(t);
  const extra = snapshot([row('r0')]);
  extra.rows[0].newSignal = {value: 4};
  assert.throws(() => storeSnapshot(directory, extra, 'slot:extra'), /storage schema/);
  assert.deepEqual(readRecords(directory), []);
  const changed = snapshot([row('r0')]);
  changed.rows[0].quoteAgeSeconds = 0;
  assert.throws(() => storeSnapshot(directory, changed, 'slot:age'), /derived time/);
  assert.deepEqual(readRecords(directory), []);
});

test('materialization rejects missing, wrong, and forward chunk references', t => {
  const directory = tempJournal(t);
  const stored = storeSnapshot(directory, snapshot(), 'slot:1');
  const records = readRecords(directory);
  const modified = JSON.parse(JSON.stringify(stored));
  modified.payload.chunks[0].hash = '0'.repeat(64);
  assert.throws(() => materialize(modified, records), /Missing or invalid/);
  const wrongField = JSON.parse(JSON.stringify(stored));
  wrongField.payload.chunks[0].field = 'evidence';
  assert.throws(() => materialize(wrongField, records), /Missing or invalid/);
  const forward = records.map(record => record.kind === 'status' ? {...record, seq: stored.seq + 1} : record);
  assert.throws(() => materialize(stored, forward), /Missing or invalid/);
  const reduced = JSON.parse(JSON.stringify(stored));
  reduced.payload.chunks.pop();
  assert.throws(() => materialize(reduced, records), /Incomplete candidate pool/);
});

test('explicit invalidation keeps the snapshot and requires a reason with evidence', t => {
  const directory = tempJournal(t);
  const stored = storeSnapshot(directory, snapshot(), 'slot:1');
  assert.throws(() => invalidateSnapshot(directory, {snapshotHash: '0'.repeat(64), reason: 'Incorrect game identity', evidence: 'Review note #1', observedAt: fixedAt}), /preserved snapshot/);
  assert.throws(() => invalidateSnapshot(directory, {snapshotHash: stored.hash, reason: 'bad', evidence: 'Review note #1', observedAt: fixedAt}), /specific reason/);
  const input = {snapshotHash: stored.hash, reason: 'Incorrect game identity', evidence: 'Review note #1', observedAt: fixedAt};
  const invalidation = invalidateSnapshot(directory, input);
  assert.equal(invalidation.kind, 'invalidation');
  assert.equal(invalidateSnapshot(directory, input).hash, invalidation.hash);
  assert.deepEqual(readRecords(directory).filter(record => record.kind === 'snapshot'), [stored]);
});

test('one input-derived clock reproducibly captures every actual source pool', async () => {
  const first = await captureAt(sourceRoot, sourceFixtureAt, {allowFixture: true, revision: 'fixture'});
  assert.equal(validateSnapshot(first), true);
  assert.equal(first.decisionTime, sourceFixtureAt);
  assert.deepEqual(Object.keys(first.inputVersions).sort(), sourceNames.map(name => name + '.json').sort());
  for (const version of Object.values(first.inputVersions)) assert.match(version.sha256, /^[0-9a-f]{64}$/);
  assert.ok(Array.isArray(first.rows));
  assert.ok(Array.isArray(first.preCandidateExclusions));
  assert.ok(Array.isArray(first.gameExclusions));
  assert.equal(first.scopes.length, 12);
  assert.deepEqual(first.rows.map(row => row.id), first.rows.map((_, i) => 'r' + i));
  for (const scope of first.scopes) for (const method of ['champion', 'ev', 'family-diversified-ev']) {
    const policy = scope.policies[method];
    assert.deepEqual(policy.top3, policy.ranks.slice(0, 3));
    assert.deepEqual(policy.top10, policy.ranks.slice(0, 10));
  }
  for (const [sport, kind] of [['nfl', 'all'], ['ncaa', 'game']]) {
    const scope = first.scopes.find(value => value.sport === sport && value.kind === kind && value.scope === 'week');
    const eligible = first.rows.filter(value => value.sport === sport && value.eligibility.eligible).map(value => value.id).sort();
    assert.equal(scope.policies.champion.ranks.slice().sort().join('\n'), eligible.join('\n'));
  }
  const second = await captureAt(sourceRoot, sourceFixtureAt, {allowFixture: true, revision: 'fixture'});
  assert.equal(hashPayload(second), hashPayload(first));
  const weekly = first.scopes.find(value => value.sport === 'nfl' && value.kind === 'all' && value.scope === 'week');
  const champion = weekly.policies.champion;
  champion.top3.push('missing');
  assert.throws(() => validateSnapshot(first), /Top-N mismatch/);
  champion.top3.pop();
  if (champion.ranks.length) {
    const candidate = first.rows.find(value => value.id === champion.ranks[0]);
    const last = champion.ranks.pop();
    assert.throws(() => validateSnapshot(first), /Incomplete eligible Champion pool/);
    champion.ranks.push(last);
    const originalQuote = candidate.updatedAt; candidate.updatedAt = new Date(Date.parse(sourceFixtureAt) + 60_000).toISOString();
    assert.throws(() => validateSnapshot(first), /Eligible row chronology/);
    candidate.updatedAt = originalQuote;
    const originalEv = candidate.ev; candidate.ev = originalEv + 0.01;
    assert.throws(() => validateSnapshot(first), /Frozen price\/return mismatch/);
    candidate.ev = originalEv;
    const originalRank = candidate.eligibility.championRank; candidate.eligibility.championRank = originalRank + 1;
    assert.throws(() => validateSnapshot(first), /Frozen per-row rank mismatch/);
    candidate.eligibility.championRank = originalRank;
  }
  const missing = first.scopes.pop();
  assert.throws(() => validateSnapshot(first), /Missing complete scope/);
  first.scopes.push(missing);
  assert.equal(validateSnapshot(first), true);
});
