/* Pure settlement candidates for frozen ranking rows and public results.json v1.
 * The caller owns append-only deduplication, corrections, and invalidations.
 * A results game is a full-game final because build_results.py emits only completed games.
 * Team labels are matched literally after case/whitespace normalization; no aliases are guessed.
 */
'use strict';

const ET = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit',
});
const PLAYER_MARKETS = new Set([
  'rec_yds', 'rush_yds', 'pass_yds', 'receptions', 'pass_tds',
  'rush_tds', 'rec_tds', 'atd',
]);
const YARDAGE_MARKETS = new Set(['rec_yds', 'rush_yds', 'pass_yds']);
const GAME_MARKETS = new Set(['spread', 'total', 'moneyline']);

function time(value) {
  if (typeof value !== 'string' || !/(?:Z|[+-]\d\d:\d\d)$/i.test(value)) return NaN;
  return Date.parse(value);
}
function etDay(ms) {
  const parts = Object.fromEntries(ET.formatToParts(new Date(ms)).map(p => [p.type, p.value]));
  return `${parts.year}-${parts.month}-${parts.day}`;
}
function label(value) {
  return typeof value === 'string' ? value.trim().replace(/\s+/g, ' ').toLowerCase() : '';
}
function unresolved(row, observedAt, reason) {
  return { predictionId: row?.id ?? null, status: 'unresolved', reason, actual: null, observedAt };
}
function validScore(value) { return Number.isSafeInteger(value) && value >= 0; }
function sourceInfo(results, sport, market, observedMs, kickoffMs) {
  if (results?.schema_version !== 1) return 'invalid_results_schema';
  const generated = time(results.generated_at);
  if (!Number.isFinite(generated) || generated < kickoffMs || generated > observedMs) return 'results_chronology';
  const source = results.sources?.[sport];
  const checked = time(source?.checked_at);
  if (source?.status !== 'loaded' || !Number.isFinite(checked) || checked < kickoffMs || checked > generated) return 'game_source_unverified';
  if (PLAYER_MARKETS.has(market)) {
    // The published appearance-aware profile log currently covers NFL only.
    if (sport !== 'nfl') return 'player_source_unsupported';
    const playerAt = time(results.player_source_at);
    if (!Number.isFinite(playerAt) || playerAt < kickoffMs || playerAt > generated) return 'player_source_unverified';
  }
  return null;
}

function settleRow(row, results, opts = {}) {
  const observedAt = opts.observedAt ?? null;
  const observedMs = time(observedAt);
  const frozenMs = time(row?.frozenAt);
  const advertisedMs = time(row?.kickoff);
  const sourceHash = opts.sourceHash;
  const sourceRevision = opts.sourceRevision;
  if (!row || typeof row !== 'object' || typeof row.id !== 'string' || !row.id.trim()) return unresolved(row, observedAt, 'invalid_prediction');
  if (!Number.isFinite(observedMs) || !Number.isFinite(frozenMs) || !Number.isFinite(advertisedMs) ||
      frozenMs >= advertisedMs || observedMs <= frozenMs) return unresolved(row, observedAt, 'invalid_prediction_chronology');
  if (typeof sourceRevision !== 'string' || !sourceRevision.trim() ||
      typeof sourceHash !== 'string' || !/^[a-f\d]{64}$/i.test(sourceHash)) return unresolved(row, observedAt, 'source_identity_missing');
  if (!['nfl', 'ncaa'].includes(row.sport) || !['game', 'prop'].includes(row.kind) ||
      !label(row.home) || !label(row.away) || label(row.home) === label(row.away)) return unresolved(row, observedAt, 'invalid_prediction_identity');
  const market = row.market;
  if (market === 'first_td' || !GAME_MARKETS.has(market) && !PLAYER_MARKETS.has(market) ||
      row.period && row.period !== 'full_game') return unresolved(row, observedAt, 'unsupported_settlement_rules');
  if (row.kind === 'game' && !GAME_MARKETS.has(market) || row.kind === 'prop' && !PLAYER_MARKETS.has(market)) return unresolved(row, observedAt, 'invalid_prediction_market');
  if (observedMs <= advertisedMs) return unresolved(row, observedAt, 'upcoming');
  const games = results?.games && typeof results.games === 'object' && !Array.isArray(results.games) ? Object.values(results.games) : [];
  const matches = games.filter(g => {
    const kick = time(g?.kickoff);
    return g?.sport === row.sport && Number.isFinite(kick) &&
      label(g.home) === label(row.home) && label(g.away) === label(row.away) &&
      etDay(kick) === etDay(advertisedMs);
  });
  if (matches.length !== 1) return unresolved(row, observedAt, matches.length ? 'ambiguous_game' : 'official_final_missing');
  const game = matches[0];
  const officialMs = time(game.kickoff);
  // Vendor kickoff clocks can differ by minutes. Identity is matchup plus ET day;
  // the frozen decision must still precede the official kickoff.
  if (frozenMs >= officialMs) return unresolved(row, observedAt, 'not_before_official_kickoff');
  if (observedMs <= officialMs) return unresolved(row, observedAt, 'upcoming');
  const sourceError = sourceInfo(results, row.sport, market, observedMs, officialMs);
  if (sourceError) return unresolved(row, observedAt, sourceError);
  if (!validScore(game.homeScore) || !validScore(game.awayScore)) return unresolved(row, observedAt, 'partial_final');
  if (!game.id || typeof game.id !== 'string') return unresolved(row, observedAt, 'game_identity_missing');

  let actual;
  let difference;
  if (row.kind === 'game') {
    if (market === 'spread') {
      if (!Number.isFinite(row.line) || !['Home', 'Away'].includes(row.side)) return unresolved(row, observedAt, 'invalid_prediction_terms');
      actual = game.homeScore - game.awayScore + row.line;
      difference = row.side === 'Home' ? actual : -actual;
    } else if (market === 'total') {
      if (!Number.isFinite(row.line) || !['Over', 'Under'].includes(row.side)) return unresolved(row, observedAt, 'invalid_prediction_terms');
      actual = game.homeScore + game.awayScore;
      difference = row.side === 'Over' ? actual - row.line : row.line - actual;
    } else {
      if (!['Home', 'Away'].includes(row.side) || row.line != null && row.line !== 0) return unresolved(row, observedAt, 'invalid_prediction_terms');
      actual = game.homeScore - game.awayScore;
      difference = row.side === 'Home' ? actual : -actual;
    }
  } else {
    if (typeof row.profileId !== 'string' || !row.profileId.trim() || row.profileId.includes('|') ||
        !Number.isFinite(row.line) || (market === 'atd'
          ? row.side !== 'Yes' || row.line !== .5
          : !['Over', 'Under'].includes(row.side))) return unresolved(row, observedAt, 'invalid_prediction_terms');
    const playerKey = `${row.profileId}|${etDay(officialMs)}`;
    const player = results.players?.[playerKey];
    if (!player || typeof player !== 'object' || Array.isArray(player)) return unresolved(row, observedAt, 'player_participation_or_result_missing');
    actual = player[market];
    if (!Number.isFinite(actual)) return unresolved(row, observedAt, 'player_market_result_missing');
    // Sacks and plays behind the line can produce negative yardage. Counting
    // stats (including the binary ATD flag) cannot be fractional or negative.
    if (!YARDAGE_MARKETS.has(market) && (!Number.isSafeInteger(actual) || actual < 0))
      return unresolved(row, observedAt, 'player_market_result_invalid');
    if (market === 'atd' && actual !== 0 && actual !== 1) return unresolved(row, observedAt, 'player_market_result_invalid');
    difference = row.side === 'Under' ? row.line - actual : actual - row.line;
  }
  const status = difference > 0 ? 'win' : difference < 0 ? 'loss' : 'push';
  const provenance = {
    sourceRevision, sourceHash: sourceHash.toLowerCase(), generatedAt: results.generated_at,
    game: { id: game.id, sport: game.sport, home: game.home, away: game.away, kickoff: game.kickoff },
  };
  if (row.kind === 'prop') provenance.player = { profileId: row.profileId, date: etDay(officialMs), metric: market };
  return { predictionId: row.id, status, reason: null, actual, observedAt, provenance };
}

function resultRecords(snapshot, results, opts = {}) {
  const rows = Array.isArray(snapshot) ? snapshot : snapshot?.rows;
  if (!Array.isArray(rows)) return [];
  return rows.map(row => settleRow(row, results, opts))
    .filter(candidate => candidate.status !== 'unresolved');
}

module.exports = { settleRow, resultRecords };
