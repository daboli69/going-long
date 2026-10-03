'use strict';
// Offline holdout evaluator. The CLI has no clock override and refuses to read
// outcome journals until the preregistered release time. Exported pure helpers
// are for synthetic fixtures and cannot publish an observation.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {readRecords, hashPayload} = require('../../shared/ranking-journal.cjs');
const {materialize, verifyCompletePools} = require('../../shared/ranking-snapshot.cjs');
const {validateSnapshot} = require('./collect.cjs');
const REGISTERED = require('./experiment-v1.json');
const METHODS = ['champion', 'ev', 'family-diversified-ev'];
const DAY = /^\d{4}-\d{2}-\d{2}$/;
const SHA = /^[0-9a-f]{64}$/;
const ET = new Intl.DateTimeFormat('en-US', {timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', hourCycle: 'h23'});
const mean = xs => xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;

function assertUnlocked(now = Date.now(), registration = REGISTERED) {
  const when = typeof now === 'number' ? now : Date.parse(now);
  if (!Number.isFinite(when) || !Number.isFinite(Date.parse(registration.evaluationUnlockAt))) throw Error('Invalid evaluation clock or registration');
  if (when < Date.parse(registration.evaluationUnlockAt)) throw Error(`Outcome evaluation locked until ${registration.evaluationUnlockAt}`);
}
function eligiblePrimary(snapshot, registration = REGISTERED) {
  const date = snapshot?.slateDate, trigger = snapshot?.trigger;
  const decision = Date.parse(snapshot?.decisionTime);
  if (!Number.isFinite(decision)) return false;
  const parts = Object.fromEntries(ET.formatToParts(new Date(decision)).map(p => [p.type, p.value]));
  const actualDate = `${parts.year}-${parts.month}-${parts.day}`, actualHour = Number(parts.hour), actualMinute = Number(parts.minute);
  return snapshot?.experiment === registration.id && DAY.test(date || '') &&
    date >= registration.holdoutStarts && date <= registration.holdoutEndsInclusive &&
    trigger?.mode === 'scheduled' && trigger?.primaryWindow === true &&
    trigger?.slot?.date === date && trigger.slot.hour === registration.primarySlot && trigger.slot.minute <= 15 &&
    actualDate === date && actualHour === registration.primarySlot && actualMinute === trigger.slot.minute;
}
function etDate(ms) {
  const parts = Object.fromEntries(ET.formatToParts(new Date(ms)).map(p => [p.type, p.value]));
  return `${parts.year}-${parts.month}-${parts.day}`;
}
const label = s => typeof s === 'string' ? s.trim().replace(/\s+/g, ' ').toLowerCase() : '';
function expectedGrade(row, actual) {
  if (row.kind === 'prop') {
    const yards = ['rec_yds', 'rush_yds', 'pass_yds'].includes(row.market);
    if (!yards && (!Number.isSafeInteger(actual) || actual < 0)) return null;
    if (row.market === 'atd' && actual !== 0 && actual !== 1) return null;
  } else if ((row.market === 'total' && (!Number.isSafeInteger(actual) || actual < 0)) ||
             (row.market === 'moneyline' && !Number.isSafeInteger(actual))) return null;
  let margin;
  if (row.market === 'spread' || row.market === 'moneyline') margin = row.side === 'Home' ? actual : row.side === 'Away' ? -actual : NaN;
  else if (row.market === 'atd') margin = row.side === 'Yes' && row.line === .5 ? actual - .5 : NaN;
  else margin = row.side === 'Over' ? actual - row.line : row.side === 'Under' ? row.line - actual : NaN;
  if (!Number.isFinite(margin)) return null;
  return margin > 0 ? 'win' : margin < 0 ? 'loss' : 'push';
}
function validateOutcome(snapshot, record, outcome) {
  const row = snapshot.rows.find(r => r.id === outcome.predictionId), game = outcome.provenance?.game;
  const frozen = Date.parse(snapshot.decisionTime), kickoff = Date.parse(game?.kickoff),
    observed = Date.parse(outcome.observedAt), generated = Date.parse(outcome.provenance?.generatedAt);
  if (!row || !['win', 'loss', 'push'].includes(outcome.status) || !Number.isFinite(outcome.actual) ||
      !game?.id || game.sport !== row.sport || label(game.home) !== label(row.home) || label(game.away) !== label(row.away) ||
      !Number.isFinite(kickoff) || !Number.isFinite(Date.parse(row.kickoff)) ||
      etDate(kickoff) !== etDate(Date.parse(row.kickoff)) || expectedGrade(row, outcome.actual) !== outcome.status ||
      (row.kind === 'prop' && (outcome.provenance?.player?.profileId !== row.profileId ||
       outcome.provenance?.player?.metric !== row.market || outcome.provenance?.player?.date !== etDate(kickoff))) ||
      !Number.isFinite(frozen) ||
      !Number.isFinite(observed) || !Number.isFinite(generated) || !(frozen < kickoff && kickoff < generated && generated <= observed) ||
      observed !== Date.parse(record.observedAt) || !SHA.test(outcome.provenance?.sourceHash || '') ||
      outcome.provenance.sourceHash !== record.payload.sourceHash ||
      outcome.provenance.sourceRevision !== record.payload.sourceRevision ||
      typeof outcome.provenance.sourceRevision !== 'string' || !outcome.provenance.sourceRevision) {
    throw Error('Invalid settlement identity, source, or chronology');
  }
}
function outcomeIndex(snapshotHash, records, snapshot = null) {
  const first = new Map(), conflicts = new Set(), invalidations = [];
  const settlements = records.filter(r => r.kind === 'settlement' && r.payload?.snapshotHash === snapshotHash).sort((a, b) => a.seq - b.seq);
  for (const record of settlements) {
    for (const outcome of record.payload.outcomes || []) {
      if (snapshot) validateOutcome(snapshot, record, outcome);
      const id = outcome?.predictionId;
      if (typeof id !== 'string' || !id) throw Error('Invalid outcome prediction identity');
      const old = first.get(id);
      if (!old) first.set(id, outcome);
      else if (old.status !== outcome.status || old.actual !== outcome.actual ||
               old.provenance?.game?.id !== outcome.provenance?.game?.id) conflicts.add(id);
    }
    for (const id of record.payload.conflicts || []) conflicts.add(id);
  }
  for (const r of records.filter(r => r.kind === 'invalidation')) {
    const target = r.payload?.targetHash ?? r.payload?.snapshotHash;
    if (target === snapshotHash || settlements.some(s => s.hash === target)) {
      if (typeof r.payload?.reason !== 'string' || r.payload.reason.trim().length < 10 ||
          typeof r.payload?.evidence !== 'string' || r.payload.evidence.trim().length < 10) throw Error('Invalidation lacks reason or evidence reference');
      invalidations.push(r.hash);
    }
  }
  return {first, conflicts, invalidations};
}
function opposite(row) {
  if (row.side === 'Home') return 'Away';
  if (row.side === 'Away') return 'Home';
  if (row.side === 'Over') return 'Under';
  if (row.side === 'Under') return 'Over';
  return null; // No invented No side for an ATD Yes contract.
}
function sameBookReference(row, rows) {
  const other = opposite(row);
  if (!other || !Number.isFinite(row.dec) || row.dec <= 1 || !row.book || !row.updatedAt) return null;
  const peers = rows.filter(p => p.sport === row.sport && p.event === row.event && p.kind === row.kind &&
    (p.profileId ?? null) === (row.profileId ?? null) && p.market === row.market && p.line === row.line &&
    p.side === other && p.book === row.book && p.updatedAt === row.updatedAt && Number.isFinite(p.dec) && p.dec > 1);
  const distinct = new Set(peers.map(p => p.dec));
  if (distinct.size !== 1) return null;
  const implied = 1 / row.dec, oppositeImplied = 1 / peers[0].dec;
  return implied / (implied + oppositeImplied);
}
function modelScore(row, outcome) {
  if (!outcome || !['win', 'loss'].includes(outcome.status)) return null;
  const push = row.push ?? 0;
  if (!Number.isFinite(row.prob) || !Number.isFinite(push) || push < 0 || push >= 1 ||
      row.prob < 0 || row.prob + push > 1) return null;
  const p = row.prob / (1 - push), y = outcome.status === 'win' ? 1 : 0;
  const ll = q => -(y * Math.log(Math.max(1e-12, q)) + (1 - y) * Math.log(Math.max(1e-12, 1 - q)));
  return {p, y, brier: (p - y) ** 2, logLoss: ll(p)};
}
function score(row, outcome, reference) {
  const model = modelScore(row, outcome);
  if (!model || reference === null) return null;
  const referenceBrier = (reference - model.y) ** 2;
  const referenceLogLoss = -(model.y * Math.log(Math.max(1e-12, reference)) +
    (1 - model.y) * Math.log(Math.max(1e-12, 1 - reference)));
  return {...model, reference, referenceBrier, excessBrier: model.brier - referenceBrier, referenceLogLoss};
}
function selectedStats(ids, rowsById, allRows, outcomes) {
  const counts = {selected: ids.length, settled: 0, push: 0, unresolved: 0, conflict: 0, missingReference: 0, scored: 0, probabilityScored: 0};
  const scored = [], allScored = [], selected = [];
  for (const id of ids) {
    const row = rowsById.get(id);
    if (!row) throw Error(`Frozen rank refers to missing row ${id}`);
    const conflict = outcomes.conflicts.has(id), outcome = conflict ? null : outcomes.first.get(id);
    selected.push(row);
    if (conflict) { counts.conflict++; counts.unresolved++; continue; }
    if (!outcome || !['win', 'loss', 'push'].includes(outcome.status)) { counts.unresolved++; continue; }
    counts.settled++;
    if (outcome.status === 'push') { counts.push++; continue; }
    const model = modelScore(row, outcome);
    if (!model) { counts.unresolved++; counts.settled--; continue; }
    counts.probabilityScored++;
    allScored.push({...model, id, game: outcome.provenance?.game?.id ?? row.event});
    const reference = sameBookReference(row, allRows);
    if (reference === null) { counts.missingReference++; continue; }
    const metrics = score(row, outcome, reference);
    if (!metrics) { counts.missingReference++; continue; }
    counts.scored++;
    scored.push({...metrics, id, game: outcome.provenance?.game?.id ?? row.event, family: row.family,
      dec: row.dec, ev: row.ev, quoteFresh5m: row.quoteFresh5m});
  }
  return {counts, scored, allScored, selected};
}
function reliability(scored) {
  return Array.from({length: 10}, (_, i) => {
    const members = scored.filter(r => Math.min(9, Math.floor(r.p * 10)) === i);
    return {bin: `${i / 10}-${(i + 1) / 10}`, n: members.length,
      meanProbability: mean(members.map(r => r.p)), observedWinRate: mean(members.map(r => r.y))};
  });
}
function composition(rows) {
  const tally = field => Object.fromEntries([...rows.reduce((counts, row) => {
    const key = field(row);
    counts.set(key, (counts.get(key) || 0) + 1);
    return counts;
  }, new Map())].sort(([a], [b]) => a.localeCompare(b)));
  const families = tally(row => row.family || 'unknown');
  const games = tally(row => row.event || 'unknown');
  const evs = rows.map(r => r.ev).filter(Number.isFinite).sort((a, b) => a - b);
  return {contracts: rows.length, uniqueGames: Object.keys(games).length, uniqueFamilies: Object.keys(families).length,
    byMarket: tally(row => row.market || 'unknown'), byType: tally(row => row.kind || 'unknown'),
    byBook: tally(row => row.book || 'unknown'),
    byQuoteFreshness: tally(row => row.quoteFresh5m === true ? 'within_5_minutes' : row.quoteFresh5m === false ? 'saved_over_5_minutes' : 'unknown'),
    byPrice: tally(row => !Number.isFinite(row.odds) ? 'unknown' : row.odds < -200 ? 'shorter_than_-200' :
      row.odds < 0 ? '-200_to_-100' : row.odds < 200 ? '+100_to_+199' : '+200_or_longer'),
    evDistribution: {n: evs.length, min: evs.length ? evs[0] : null, p25: evs.length ? quantile(evs, .25) : null,
      median: evs.length ? quantile(evs, .5) : null, p75: evs.length ? quantile(evs, .75) : null,
      max: evs.length ? evs.at(-1) : null, mean: mean(evs), positive: evs.filter(v => v > 0).length},
    largestGameShare: rows.length ? Math.max(...Object.values(games)) / rows.length : null,
    largestFamilyShare: rows.length ? Math.max(...Object.values(families)) / rows.length : null};
}
function policySummary(slates) {
  const scored = slates.flatMap(s => s.scored), allScored = slates.flatMap(s => s.allScored), selected = slates.flatMap(s => s.selected),
    counts = Object.fromEntries(Object.keys(slates[0]?.counts || {selected: 0, settled: 0, push: 0, unresolved: 0, conflict: 0, missingReference: 0, scored: 0, probabilityScored: 0})
      .map(k => [k, slates.reduce((n, s) => n + s.counts[k], 0)]));
  const games = new Set(scored.map(r => r.game)), families = new Set(selected.map(r => r.family).filter(Boolean));
  const gameMeans = [...games].map(game => mean(scored.filter(r => r.game === game).map(r => r.excessBrier)));
  return {counts, composition: composition(selected), uniqueGames: games.size,
    uniquePlayers: new Set(selected.map(r => r.profileId).filter(Boolean)).size,
    uniqueFamilies: families.size, reliability: reliability(scored),
    allSettledProbabilityDiagnostic: {n: allScored.length, modelBrier: mean(allScored.map(r => r.brier)),
      modelLogLoss: mean(allScored.map(r => r.logLoss)), reliability: reliability(allScored),
      interpretation: 'Includes settled nonpush contracts without a paired reference; descriptive calibration only, not a betting-value or policy-superiority test.'},
    modelBrier: mean(scored.map(r => r.brier)), referenceBrier: mean(scored.map(r => r.referenceBrier)),
    excessBrier: mean(scored.map(r => r.excessBrier)), gameBalancedExcessBrier: mean(gameMeans), modelLogLoss: mean(scored.map(r => r.logLoss)),
    referenceLogLoss: mean(scored.map(r => r.referenceLogLoss)), meanDecimalPrice: mean(selected.map(r => r.dec).filter(Number.isFinite)),
    meanFrozenEV: mean(selected.map(r => r.ev).filter(Number.isFinite)),
    freshQuoteFraction: selected.length ? selected.filter(r => r.quoteFresh5m === true).length / selected.length : null,
    maxGameShare: scored.length ? Math.max(...[...games].map(g => scored.filter(r => r.game === g).length)) / scored.length : null,
    maxFamilyShare: selected.length && families.size ? Math.max(...[...families].map(f => selected.filter(r => r.family === f).length)) / selected.length : null};
}
function rng(seed) {
  let state = seed >>> 0;
  return () => { state += 0x6D2B79F5; let t = state; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61); return ((t ^ t >>> 14) >>> 0) / 4294967296; };
}
function quantile(sorted, q) {
  const at = (sorted.length - 1) * q, low = Math.floor(at), high = Math.ceil(at);
  return sorted[low] + (sorted[high] - sorted[low]) * (at - low);
}
function intervals(differences, registration = REGISTERED, cluster = 'ET slate date') {
  if (!differences.length) return null;
  const next = rng(registration.seed), draws = [];
  for (let i = 0; i < registration.bootstrapResamples; i++) {
    const sample = Array.from({length: differences.length}, () => differences[Math.floor(next() * differences.length)]);
    draws.push(mean(sample));
  }
  draws.sort((a, b) => a - b);
  const interval = alpha => [quantile(draws, alpha / 2), quantile(draws, 1 - alpha / 2)];
  return {unadjusted95: interval(.05), adjustedFamilywise: interval(registration.alphaFamilywise / 8),
    resamples: registration.bootstrapResamples, cluster, seed: registration.seed};
}
function evaluateObservations(observations, registration = REGISTERED) {
  const primary = observations.filter(o => eligiblePrimary(o.snapshot, registration)), seen = new Set();
  for (const o of primary) {
    if (seen.has(o.snapshot.slateDate)) throw Error('Duplicate primary 8 a.m. slate date');
    seen.add(o.snapshot.slateDate);
    if (o.snapshot.schemaVersion !== registration.schemaVersion ||
        o.snapshot.registrationHash !== hashPayload(registration) ||
        o.snapshot.codeHashes?.policy !== registration.policyCodeHash ||
        o.snapshot.codeHashes?.generator !== registration.generatorCodeHash ||
        !Object.values(o.snapshot.inputVersions || {}).length ||
        Object.values(o.snapshot.inputVersions).some(v => !SHA.test(v?.sha256 || '')) ||
        !Object.values(o.snapshot.sourceHashes || {}).length ||
        Object.values(o.snapshot.sourceHashes).some(v => !SHA.test(v))) throw Error('Frozen snapshot differs from registered source hashes or input schema');
  }
  const missingPrimaryDates = [];
  for (let ms = Date.parse(`${registration.holdoutStarts}T12:00:00Z`);
       ms <= Date.parse(`${registration.holdoutEndsInclusive}T12:00:00Z`); ms += 86400000) {
    const day = new Date(ms).toISOString().slice(0, 10);
    if (!seen.has(day)) missingPrimaryDates.push(day);
  }
  const indexed = primary.map(o => ({...o, outcomes: outcomeIndex(o.record.hash, o.records, o.snapshot)}))
    .filter(o => !o.outcomes.invalidations.length);
  const excludedInvalidated = primary.length - indexed.length, comparisons = [];
  for (const [sport, kind, scopeName] of registration.primaryScopes) for (const topN of registration.topN) {
    const slates = indexed.map(o => {
      const scope = o.snapshot.scopes.find(s => s.sport === sport && s.kind === kind && s.scope === scopeName);
      if (!scope) throw Error(`Missing preregistered scope ${sport}/${kind}/${scopeName}`);
      const rowsById = new Map(o.snapshot.rows.map(r => [r.id, r]));
      if (rowsById.size !== o.snapshot.rows.length) throw Error('Duplicate frozen prediction ID');
      const eligibleRows = scope.policies.champion.ranks.map(id => {
        const row = rowsById.get(id);
        if (!row) throw Error('Full frozen eligible rank refers to a missing row');
        return row;
      });
      const stats = Object.fromEntries(METHODS.map(method => {
        const policy = scope.policies?.[method], ids = policy?.[`top${topN}`];
        if (!Array.isArray(ids) || JSON.stringify(ids) !== JSON.stringify(policy.ranks.slice(0, topN))) throw Error('Invalid frozen top-N ranks');
        return [method, selectedStats(ids, rowsById, o.snapshot.rows, o.outcomes)];
      }));
      return {date: o.snapshot.slateDate, stats, eligibleRows};
    });
    for (const challenger of METHODS.slice(1)) {
      const championSlates = slates.map(s => s.stats.champion), challengerSlates = slates.map(s => s.stats[challenger]);
      const policy = {champion: policySummary(championSlates), challenger: policySummary(challengerSlates)};
      const paired = slates.map(s => ({date: s.date, champion: s.stats.champion.scored, challenger: s.stats[challenger].scored}))
        .filter(s => s.champion.length && s.challenger.length);
      const differences = paired.map(s => mean(s.challenger.map(r => r.excessBrier)) - mean(s.champion.map(r => r.excessBrier)));
      const modelLogLossDifferences = paired.map(s => mean(s.challenger.map(r => r.logLoss)) - mean(s.champion.map(r => r.logLoss)));
      const excessLogLossDifferences = paired.map(s => mean(s.challenger.map(r => r.logLoss - r.referenceLogLoss)) - mean(s.champion.map(r => r.logLoss - r.referenceLogLoss)));
      const gameDifferences = paired.flatMap(s => {
        const championByGame = new Map(), challengerByGame = new Map();
        for (const r of s.champion) { if (!championByGame.has(r.game)) championByGame.set(r.game, []); championByGame.get(r.game).push(r.excessBrier); }
        for (const r of s.challenger) { if (!challengerByGame.has(r.game)) challengerByGame.set(r.game, []); challengerByGame.get(r.game).push(r.excessBrier); }
        return [...championByGame].filter(([game]) => challengerByGame.has(game))
          .map(([game, values]) => mean(challengerByGame.get(game)) - mean(values));
      });
      const uniqueGames = new Set(paired.flatMap(s => [...s.champion, ...s.challenger].map(r => `${s.date}|${r.game}`))).size;
      const selected = policy.champion.counts.selected + policy.challenger.counts.selected;
      const unresolved = policy.champion.counts.unresolved + policy.challenger.counts.unresolved;
      const settledNonpush = selected - unresolved - policy.champion.counts.push - policy.challenger.counts.push;
      const missingReference = policy.champion.counts.missingReference + policy.challenger.counts.missingReference;
      const unresolvedFraction = selected ? unresolved / selected : null;
      const missingReferenceFraction = settledNonpush ? missingReference / settledNonpush : null;
      const failures = [];
      if (paired.length < registration.minimumPairedSlates) failures.push('too_few_paired_slates');
      if (uniqueGames < registration.minimumGameClusters) failures.push('too_few_unique_games');
      if (unresolvedFraction === null || unresolvedFraction > registration.maximumUnresolvedFraction) failures.push('unresolved_coverage');
      if (missingReferenceFraction === null || missingReferenceFraction > registration.maximumMissingReferenceFraction) failures.push('paired_reference_coverage');
      const uncertainty = failures.length ? null : intervals(differences, registration);
      const effect = mean(differences), modelLogLossEffect = mean(modelLogLossDifferences), excessLogLossEffect = mean(excessLogLossDifferences);
      const screeningPass = !failures.length && uncertainty.adjustedFamilywise[1] < 0 &&
        effect <= -registration.minimumExcessBrierBenefit && modelLogLossEffect <= registration.maximumLogLossWorsening;
      comparisons.push({sport, universe: kind, scope: scopeName, topN, challenger, status: failures.length ? 'INSUFFICIENT' : screeningPass ? 'SCREENING_PASS_NO_PROMOTION' : 'NO_SUPERIORITY',
        pairedSlates: paired.length, uniqueGameClusters: uniqueGames, selected, unresolvedFraction, missingReferenceFraction,
        failures, policy, fullEligibleRanking: composition(slates.flatMap(s => s.eligibleRows)),
        meanSlateExcessBrierDifference: effect, meanSlateModelLogLossDifference: modelLogLossEffect,
        meanSlateExcessLogLossDifference: excessLogLossEffect,
        uncertainty, gameClusterDiagnostic: {pairedGames: gameDifferences.length, meanDifference: mean(gameDifferences),
          uncertainty: gameDifferences.length ? intervals(gameDifferences, registration, 'game within ET slate (secondary)') : null,
          note: 'Descriptive only; games from the same slate can remain dependent.'},
        interpretation: 'Negative difference improves model-minus-same-book-reference Brier on selected contracts; this does not measure profit or justify promotion.'});
    }
  }
  return {experiment: registration.id, phase: 'untouched_confirmation', primarySnapshots: primary.length,
    missingPrimaryDates, invalidatedSnapshotsExcluded: excludedInvalidated, validPrimarySnapshots: indexed.length,
    comparisons, limitations: ['Scheduled capture availability can select slates.', 'Complete-case paired references can select markets.',
      'Results are statistical grading, not sportsbook execution or book-specific void decisions.',
      'Today-settleable results cannot establish unrestricted Today ranking superiority.',
      'Log loss probabilities are clipped at 1e-12 for finite numerical reporting.', 'No ROI or CLV is computed.']};
}
function loadObservations(root) {
  assertUnlocked();
  const challengerHash = crypto.createHash('sha256').update(fs.readFileSync(path.join(__dirname, '../../shared/ranking-policies.cjs'), 'utf8').replace(/\r\n/g, '\n')).digest('hex');
  if (challengerHash !== REGISTERED.challengersSourceHash) throw Error('Challenger source differs from preregistration');
  const entries = fs.readdirSync(root, {withFileTypes: true});
  if (entries.some(e => !e.isDirectory() || !DAY.test(e.name))) throw Error('Unexpected journal root entry');
  const out = [];
  for (const entry of entries) {
    const records = readRecords(path.join(root, entry.name));
    verifyCompletePools(records);
    for (const record of records.filter(r => r.kind === 'snapshot')) {
      const snapshot = materialize(record, records);
      validateSnapshot(snapshot);
      if (snapshot.slateDate !== entry.name) throw Error('Snapshot/date segment mismatch');
      out.push({record, snapshot, records});
    }
  }
  return out;
}
function main() {
  if (process.argv.length !== 3) throw Error('Usage: node research/today-ranking/evaluate.cjs JOURNAL_ROOT');
  assertUnlocked(); // Before even listing journal files or reading raw outcomes.
  const observations = loadObservations(path.resolve(process.argv[2]));
  console.log(JSON.stringify(evaluateObservations(observations), null, 2));
}
module.exports = {assertUnlocked, eligiblePrimary, outcomeIndex, sameBookReference, score,
  selectedStats, reliability, intervals, evaluateObservations, loadObservations};
if (require.main === module) try { main(); } catch (error) { console.error(error.message); process.exitCode = 1; }
