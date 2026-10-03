'use strict';

// Offline, predeclared ranking experiments. The caller freezes the exact
// Champion-eligible, already best-book/contract-deduplicated cohort in its
// existing Champion order. No eligibility, probability, or staking changes.
const METHODS = Object.freeze(['champion', 'ev', 'family-diversified-ev']);

function expectedValue(row) {
  if (!row || typeof row !== 'object') throw new TypeError('Expected a candidate object');
  const { prob, dec } = row;
  const push = row.push === undefined ? 0 : row.push;
  if (!Number.isFinite(prob) || prob < 0 || prob > 1) throw new RangeError('prob must be an unconditional win probability in [0, 1]');
  if (!Number.isFinite(push) || push < 0 || push > 1 || prob + push > 1) throw new RangeError('push must be an unconditional push probability with prob + push <= 1');
  if (!Number.isFinite(dec) || dec <= 1) throw new RangeError('dec must be finite decimal odds greater than 1');
  // Payoffs per unit staked: win dec-1, push 0, loss -1.
  // An absent push uses the source model's zero-push approximation.
  return prob * dec + push - 1;
}

function identity(value, field) {
  if ((typeof value !== 'string' && typeof value !== 'number') || String(value).trim() === '' || (typeof value === 'number' && !Number.isFinite(value))) {
    throw new TypeError(`${field} must be a nonempty canonical identifier`);
  }
  // Preserve exact event/time aliases; no text, time, or semantic normalization.
  return String(value);
}

function familyKey(row) {
  const event = identity(row.event, 'event');
  const kind = identity(row.kind, 'kind');
  const participant = row.profileId === undefined || row.profileId === null ? 'game' : identity(row.profileId, 'profileId');
  if (kind === 'prop' && participant === 'game') throw new TypeError('prop rows need profileId');
  return JSON.stringify([event, kind, participant, identity(row.market, 'market'), identity(row.side, 'side')]);
}

function timeMs(value, field) {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value !== 'string' || !/(?:Z|[+-]\d\d:\d\d)$/i.test(value)) throw new TypeError(`${field} must be epoch milliseconds or an ISO timestamp with a timezone`);
  const result = Date.parse(value);
  if (!Number.isFinite(result)) throw new TypeError(`${field} must be a valid timestamp`);
  return result;
}

function validateQuoteTimes(rows, options) {
  const historical = options.historical === true || options.evaluationMode === 'historical';
  if (historical && options.decisionTime === undefined) throw new TypeError('Historical evaluation requires frozen decisionTime');
  if (options.decisionTime === undefined) return;
  const decision = timeMs(options.decisionTime, 'decisionTime');
  for (const row of rows) {
    const quote = row.quoteTime || row.updatedAt;
    if (quote === undefined || quote === null || quote === '') throw new TypeError('Frozen evaluation requires quoteTime or updatedAt for every row');
    if (timeMs(quote, 'quoteTime/updatedAt') > decision) throw new RangeError('Quote is newer than frozen decisionTime');
  }
  // This guards quote timing only. Archived feature/model availability and
  // outcomes/splits still require separate evidence before calling it a backtest.
}

function rank(rows, method = 'champion', options = {}) {
  if (!Array.isArray(rows)) throw new TypeError('rows must be an array');
  if (!METHODS.includes(method)) throw new RangeError(`Unknown ranking method: ${method}`);
  if (!options || typeof options !== 'object') throw new TypeError('options must be an object');
  validateQuoteTimes(rows, options);
  const decorated = rows.map((row, index) => ({ row, index, ev: expectedValue(row) }));
  if (method === 'champion') return rows.slice();
  decorated.sort((a, b) => b.ev - a.ev || a.index - b.index);
  if (method === 'ev') return decorated.map(({ row }) => row);
  const seen = new Set();
  return decorated.filter(({ row }) => {
    const key = familyKey(row);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  }).map(({ row }) => row);
}

function rationale(row) {
  const ev = expectedValue(row);
  const push = row.push === undefined ? 0 : row.push;
  return { winProbability: row.prob, pushProbability: push, lossProbability: 1 - row.prob - push, decimalOdds: row.dec, expectedProfitPerUnit: ev, familyKey: familyKey(row) };
}

function summarizeCohort(rows) {
  if (!Array.isArray(rows)) throw new TypeError('rows must be an array');
  const evs = rows.map(expectedValue);
  const byKind = Object.create(null);
  const events = new Set();
  const families = new Set();
  for (const row of rows) {
    const kind = identity(row.kind, 'kind');
    byKind[kind] = (byKind[kind] || 0) + 1;
    events.add(identity(row.event, 'event'));
    families.add(familyKey(row));
  }
  const mean = values => values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
  return {
    count: rows.length,
    byKind: { ...byKind },
    uniqueExactEvents: events.size,
    uniqueFamilies: families.size,
    repeatedFamilyRows: rows.length - families.size,
    meanModelWinProbability: mean(rows.map(row => row.prob)),
    meanModelEVPerUnit: mean(evs),
    positiveModelEVCount: evs.filter(value => value > 0).length,
    minModelEVPerUnit: evs.length ? Math.min(...evs) : null,
    maxModelEVPerUnit: evs.length ? Math.max(...evs) : null,
  };
}

module.exports = { METHODS, expectedValue, familyKey, rank, rationale, summarizeCohort };
