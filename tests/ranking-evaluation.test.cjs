'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {hashPayload} = require('../shared/ranking-journal.cjs');
const evaluation = require('../research/today-ranking/evaluate.cjs');
const registration = require('../research/today-ranking/experiment-v1.json');

const fixtureRegistration = {...registration, minimumPairedSlates: 2, minimumGameClusters: 2,
  bootstrapResamples: 200, maximumUnresolvedFraction: .1, maximumMissingReferenceFraction: .1};
const date = i => new Date(Date.UTC(2026, 9, 24 + i)).toISOString().slice(0, 10);
function observation(i, {missing = [], conflict = false, invalidate = false, referenceMissing = false, manual = false} = {}) {
  const day = date(i), hash = 'snapshot-' + i, rows = [], outcomes = [], observedAt = `${day}T23:00:00Z`;
  const sourceHash = 'a'.repeat(64), sourceRevision = 'fixture-revision';
  const scopes = [];
  for (const [sport, kind] of [['nfl', 'all'], ['ncaa', 'game']]) {
    const ids = [];
    for (let j = 0; j < 3; j++) {
      const id = `${sport}-${j}`, event = `${sport}-event-${i}-${j}`;
      const base = {id, event, sport, kind: 'game', market: 'total', side: 'Over', line: 44.5,
        home: 'A', away: 'B', kickoff: `${day}T17:00:00Z`, book: 'SameBook', updatedAt: `${day}T12:00:00Z`,
        frozenAt: `${day}T12:00:01Z`, prob: [.7, .6, .55][j], push: 0, dec: 2.1,
        ev: [.47, .26, .155][j], family: event, quoteFresh5m: true, profileId: null};
      rows.push(base);
      if (!(referenceMissing && sport === 'nfl' && j === 0)) rows.push({...base, id: `${id}-other`, side: 'Under', dec: 1.9});
      ids.push(id);
      if (!missing.includes(id)) outcomes.push({predictionId: id, status: j === 0 ? 'win' : 'loss', actual: j === 0 ? 48 : 41,
        observedAt, provenance: {sourceHash, sourceRevision, generatedAt: `${day}T22:00:00Z`,
          game: {id: event, sport, home: 'A', away: 'B', kickoff: `${day}T17:00:00Z`}}});
    }
    const champion = ids, ev = [ids[1], ids[0], ids[2]], diversified = [ids[2], ids[1], ids[0]];
    scopes.push({sport, kind, scope: 'today-settleable', policies: {
      champion: {ranks: champion, top3: champion, top10: champion},
      ev: {ranks: ev, top3: ev, top10: ev},
      'family-diversified-ev': {ranks: diversified, top3: diversified, top10: diversified},
    }});
  }
  const records = [{kind: 'settlement', seq: 1, hash: `result-${i}`, observedAt,
    payload: {snapshotHash: hash, sourceHash, sourceRevision, outcomes}}];
  if (conflict) records.push({kind: 'settlement', seq: 2, hash: `correction-${i}`, observedAt,
    payload: {snapshotHash: hash, sourceHash, sourceRevision,
      outcomes: [{...outcomes.find(o => o.predictionId === 'nfl-0'), status: 'loss', actual: 40}], conflicts: ['nfl-0']}});
  if (invalidate) records.push({kind: 'invalidation', seq: 3, hash: `invalid-${i}`,
    payload: {snapshotHash: hash, reason: 'bad source evidence', evidence: 'fixture://bad-source'}});
  return {record: {hash}, records, snapshot: {schemaVersion: 1, experiment: registration.id, slateDate: day,
    decisionTime: `${day}T12:00:01Z`, registrationHash: hashPayload(fixtureRegistration), rows, scopes,
    codeHashes: {policy: registration.policyCodeHash, generator: registration.generatorCodeHash},
    inputVersions: {'data.json': {sha256: 'b'.repeat(64)}}, sourceHashes: {'index.html': 'c'.repeat(64)},
    trigger: {mode: manual ? 'manual' : 'scheduled', primaryWindow: !manual, slot: {date: day, hour: 8, minute: 0}}}};
}

test('registered unlock refuses premature CLI-style evaluation and accepts release time', () => {
  assert.throws(() => evaluation.assertUnlocked('2026-12-06T16:59:59Z'), /locked/);
  assert.doesNotThrow(() => evaluation.assertUnlocked('2026-12-06T17:00:00Z'));
  const before = {...registration, evaluationUnlockAt: '2999-01-01T00:00:00Z'};
  assert.throws(() => evaluation.assertUnlocked(Date.now(), before), /locked/);
});

test('only scheduled primary holdout slates qualify; manual and later slots cannot substitute', () => {
  const valid = observation(0);
  assert.equal(evaluation.eligiblePrimary(valid.snapshot), true);
  assert.equal(evaluation.eligiblePrimary(observation(0, {manual: true}).snapshot), false);
  assert.equal(evaluation.eligiblePrimary({...valid.snapshot, trigger: {...valid.snapshot.trigger, slot: {date: valid.snapshot.slateDate, hour: 10, minute: 0}}}), false);
  assert.equal(evaluation.eligiblePrimary({...valid.snapshot, slateDate: '2026-10-23'}), false);
});

test('reference requires a frozen opposite side at the same book, contract, and quote time', () => {
  const {snapshot} = observation(0), row = snapshot.rows[0];
  assert.ok(Math.abs(evaluation.sameBookReference(row, snapshot.rows) - (1 / 2.1) / (1 / 2.1 + 1 / 1.9)) < 1e-12);
  assert.equal(evaluation.sameBookReference(row, snapshot.rows.filter(r => r.id !== row.id + '-other')), null);
  assert.equal(evaluation.sameBookReference({...row, side: 'Yes'}, snapshot.rows), null);
  assert.equal(evaluation.sameBookReference(row, snapshot.rows.map(r => r.id === row.id + '-other' ? {...r, book: 'OtherBook'} : r)), null);
});

test('conditional nonpush Brier, log loss, and reliability use actual binary outcomes', () => {
  const metrics = evaluation.score({prob: .6, push: .2}, {status: 'win'}, .5);
  assert.ok(Math.abs(metrics.p - .75) < 1e-12);
  assert.ok(Math.abs(metrics.brier - .0625) < 1e-12);
  assert.ok(Math.abs(metrics.excessBrier + .1875) < 1e-12);
  assert.ok(Math.abs(metrics.logLoss + Math.log(.75)) < 1e-12);
  assert.equal(evaluation.score({prob: .6, push: .2}, {status: 'push'}, .5), null);
  const bins = evaluation.reliability([{p: .75, y: 1}, {p: .76, y: 0}]);
  assert.equal(bins[7].n, 2);
  assert.equal(bins[7].observedWinRate, .5);
});

test('first outcome remains immutable; corrections and invalidations exclude evidence', () => {
  const base = observation(0, {conflict: true});
  const index = evaluation.outcomeIndex(base.record.hash, base.records);
  assert.equal(index.first.get('nfl-0').status, 'win');
  assert.equal(index.conflicts.has('nfl-0'), true);
  const invalid = observation(1, {invalidate: true});
  const report = evaluation.evaluateObservations([base, invalid], fixtureRegistration);
  assert.equal(report.invalidatedSnapshotsExcluded, 1);
  assert.equal(report.comparisons.find(c => c.sport === 'nfl' && c.challenger === 'ev').policy.champion.counts.conflict, 1);
  assert.equal(report.comparisons.every(c => c.status === 'INSUFFICIENT'), true);
});

test('registered hashes, official chronology, and invalidation evidence fail closed', () => {
  const badRegistration = observation(0);
  badRegistration.snapshot.registrationHash = 'd'.repeat(64);
  assert.throws(() => evaluation.evaluateObservations([badRegistration], fixtureRegistration), /registered source hashes/);
  const badHash = observation(0);
  badHash.snapshot.codeHashes.policy = 'changed';
  assert.throws(() => evaluation.evaluateObservations([badHash], fixtureRegistration), /registered source hashes/);
  const badChronology = observation(0);
  badChronology.records[0].payload.outcomes[0].provenance.generatedAt = `${badChronology.snapshot.slateDate}T16:00:00Z`;
  assert.throws(() => evaluation.evaluateObservations([badChronology], fixtureRegistration), /chronology/);
  const badGrade = observation(0);
  badGrade.records[0].payload.outcomes[0].status = 'loss';
  assert.throws(() => evaluation.evaluateObservations([badGrade], fixtureRegistration), /chronology/);
  const badInvalidation = observation(0, {invalidate: true});
  badInvalidation.records.at(-1).payload.evidence = '';
  assert.throws(() => evaluation.evaluateObservations([badInvalidation], fixtureRegistration), /evidence reference/);
});

test('eight fixed comparisons use paired slates, seeded slate and game diagnostics, and no ROI or CLV', () => {
  const observations = [observation(0), observation(1)];
  const first = evaluation.evaluateObservations(observations, fixtureRegistration);
  const second = evaluation.evaluateObservations(observations, fixtureRegistration);
  assert.deepEqual(first, second);
  assert.equal(first.comparisons.length, 8);
  assert.equal(first.missingPrimaryDates.length, 41);
  for (const c of first.comparisons) {
    assert.equal(c.pairedSlates, 2);
    assert.equal(c.uniqueGameClusters, 6);
    assert.equal(c.policy.champion.counts.scored, 6);
    assert.equal(c.uncertainty.resamples, 200);
    assert.equal(c.uncertainty.cluster, 'ET slate date');
    assert.equal(c.gameClusterDiagnostic.pairedGames, 6);
    assert.equal(c.gameClusterDiagnostic.uncertainty.cluster, 'game within ET slate (secondary)');
    assert.equal('roi' in c, false);
    assert.equal('clv' in c, false);
    assert.notEqual(c.status, 'INSUFFICIENT');
  }
});

test('coverage and game-cluster thresholds force insufficient evidence without replacing picks', () => {
  const observations = [observation(0, {missing: ['nfl-0']}), observation(1, {referenceMissing: true})];
  const report = evaluation.evaluateObservations(observations, fixtureRegistration);
  const c = report.comparisons.find(x => x.sport === 'nfl' && x.challenger === 'ev' && x.topN === 3);
  assert.equal(c.status, 'INSUFFICIENT');
  assert.ok(c.failures.includes('unresolved_coverage'));
  assert.ok(c.failures.includes('paired_reference_coverage'));
  assert.equal(c.policy.champion.counts.selected, 6);
  assert.equal(c.policy.champion.counts.unresolved, 1);
  const strict = {...fixtureRegistration, minimumGameClusters: 100};
  const strictRows = [observation(0), observation(1)];
  for (const item of strictRows) item.snapshot.registrationHash = hashPayload(strict);
  assert.ok(evaluation.evaluateObservations(strictRows, strict).comparisons.every(x => x.failures.includes('too_few_unique_games')));
});

test('one-sided settled ATD keeps model-only calibration but fails paired-reference coverage', () => {
  const atd = observation(0, {referenceMissing: true}), other = observation(1);
  const player = atd.snapshot.rows.find(r => r.id === 'nfl-0');
  Object.assign(player, {kind: 'prop', profileId: 'p0', player: 'Fixture Player', market: 'atd', side: 'Yes', line: .5});
  const outcome = atd.records[0].payload.outcomes.find(o => o.predictionId === 'nfl-0');
  outcome.actual = 1;
  outcome.provenance.player = {profileId: 'p0', metric: 'atd', date: atd.snapshot.slateDate};
  const report = evaluation.evaluateObservations([atd, other], fixtureRegistration);
  const result = report.comparisons.find(c => c.sport === 'nfl' && c.challenger === 'ev' && c.topN === 3);
  assert.equal(result.status, 'INSUFFICIENT');
  assert.ok(result.failures.includes('paired_reference_coverage'));
  assert.equal(result.policy.champion.counts.probabilityScored, 6);
  assert.equal(result.policy.champion.counts.scored, 5);
  assert.equal(result.policy.champion.allSettledProbabilityDiagnostic.n, 6);
  assert.ok(Number.isFinite(result.policy.champion.allSettledProbabilityDiagnostic.modelBrier));
  assert.equal(result.policy.champion.composition.byMarket.atd, 1);
  assert.equal(result.fullEligibleRanking.byType.prop, 1);
});
