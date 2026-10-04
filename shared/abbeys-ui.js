(function (root) {
  'use strict';

  const WEEK_KEY = 'going-abbeys-selected-week';
  let payloadPromise = null;
  let selectedWeekKey = null;
  const panelState = new WeakMap();

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function text(value, fallback = 'Unavailable') {
    return value === null || value === undefined || value === '' ? fallback : String(value);
  }

  function dateLabel(value, options) {
    if (!value) return 'Unavailable';
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) return String(value);
    return new Intl.DateTimeFormat('en-US', Object.assign({
      timeZone: 'America/New_York', month: 'short', day: 'numeric', year: 'numeric',
      hour: 'numeric', minute: '2-digit', timeZoneName: 'short'
    }, options || {})).format(date);
  }

  function weekId(week) { return `${week?.season ?? ''}-${week?.week ?? ''}`; }

  function sortWeeks(weeks) {
    return [...weeks].sort((a, b) =>
      (Number(b?.season) || 0) - (Number(a?.season) || 0) ||
      (Number(b?.week) || 0) - (Number(a?.week) || 0));
  }

  async function readBoard(url) {
    const response = await root.fetch(url, { credentials: 'same-origin' });
    if (!response.ok) throw new Error(`Board data returned ${response.status}.`);
    const data = await response.json();
    if (!data || !Array.isArray(data.weeks)) throw new Error('The ABBEYS board data is incomplete.');
    return data;
  }

  function loadPayload() {
    if (!payloadPromise) {
      payloadPromise = readBoard('/api/snapshot?file=abbeys-board.json').catch(apiError =>
        readBoard('/data/abbeys-board.json').catch(() => { throw apiError; })
      );
      const current = payloadPromise;
      current.catch(() => { if (payloadPromise === current) payloadPromise = null; });
    }
    return payloadPromise;
  }

  function list(items, emptyText) {
    const ul = el('ul', 'abbeys-evidence-list');
    if (!items.length) ul.append(el('li', 'abbeys-empty-item', emptyText));
    else items.forEach(item => ul.append(el('li', '', item)));
    return ul;
  }

  function itemStrings(value) {
    return Array.isArray(value) ? value.filter(item => item !== null && item !== undefined && String(item).trim() !== '').map(String) : [];
  }

  function scoreText(away, home) {
    const validAway = away !== null && away !== undefined && away !== '' && Number.isFinite(Number(away));
    const validHome = home !== null && home !== undefined && home !== '' && Number.isFinite(Number(home));
    return validAway && validHome ? `${away}–${home}` : 'Score unavailable';
  }

  function oddsText(value) {
    if (value === null || value === undefined || value === '') return 'Unavailable';
    return typeof value === 'number' && Number.isFinite(value) && value > 0 ? `+${value}` : String(value);
  }

  function addFact(parent, label, value, className = 'abbeys-fact') {
    const row = el('div', className);
    row.append(el('dt', '', label), el('dd', '', text(value)));
    parent.append(row);
  }

  function evidenceFor(pick) {
    const support = itemStrings(pick?.support);
    const concerns = itemStrings(pick?.concerns);
    const availabilityPattern = /\b(injur\w*|availability|inactive\w*|out|doubtful|questionable|practice|roster|depth chart)\b/i;
    return {
      availability: [...support, ...concerns].filter(value => availabilityPattern.test(value)),
      support: support.filter(value => !availabilityPattern.test(value)),
      concerns: concerns.filter(value => !availabilityPattern.test(value))
    };
  }

  function settlementDetails(body, pick) {
    const settlement = pick?.settlement;
    const section = el('section', 'abbeys-evidence-group abbeys-settlement-evidence');
    section.append(el('h4', '', 'Settlement and actual score'));
    if (!settlement) {
      section.append(el('p', 'abbeys-muted', 'Pending official settlement. The frozen prediction remains unchanged.'));
    } else {
      section.append(el('p', '', `Recorded result · ${text(settlement.outcome).toUpperCase()} · Final ${text(pick.away).toUpperCase()} ${scoreText(settlement.actualAway, settlement.actualHome)} ${text(pick.home).toUpperCase()}`));
      section.append(el('p', 'abbeys-muted', `Settled ${dateLabel(settlement.settledAt)} · Source: ${text(settlement.source)}`));
    }
    body.append(section);
  }

  function marketContext(body, week, pick) {
    const section = el('section', 'abbeys-evidence-group abbeys-market-context');
    section.append(el('h4', '', 'Post-freeze market context · optional, not a pick input'));
    const context = week?.marketContext?.[pick?.gameId];
    if (!context || typeof context !== 'object') {
      section.append(el('p', 'abbeys-muted', 'No post-freeze market context attached.'));
    } else {
      section.append(el('p', 'abbeys-muted', `Observed after this pick was frozen · ${dateLabel(context.observedAt)} · ${text(context.source)}`));
      const facts = el('dl', 'abbeys-facts');
      addFact(facts, 'Away price', oddsText(context.awayOdds));
      addFact(facts, 'Home price', oddsText(context.homeOdds));
      addFact(facts, 'Market favorite', context.marketFavorite);
      section.append(facts);
    }
    body.append(section);
  }

  function renderPick(pick, week) {
    const card = el('article', 'abbeys-pick');
    const head = el('header', 'abbeys-pick-head');
    head.append(el('h3', '', `${text(pick?.away, 'Away').toUpperCase()} @ ${text(pick?.home, 'Home').toUpperCase()}`));
    head.append(el('p', 'abbeys-kickoff', dateLabel(pick?.kickoff, { year: undefined, timeZoneName: undefined })));
    if (pick?.settlement) {
      const outcome = text(pick.settlement.outcome, 'Settled');
      head.append(el('span', `abbeys-result-chip is-${['win', 'loss', 'tie'].includes(outcome.toLowerCase()) ? outcome.toLowerCase() : 'settled'}`, outcome.toUpperCase()));
    } else {
      head.append(el('span', 'abbeys-pending-chip', 'Pending'));
    }
    card.append(head);

    card.append(el('p', 'abbeys-winner', `${text(pick?.winner).toUpperCase()} to win`));
    const hasAwayGames = pick?.gamesAway !== null && pick?.gamesAway !== undefined && pick.gamesAway !== '' && Number.isFinite(Number(pick.gamesAway));
    const hasHomeGames = pick?.gamesHome !== null && pick?.gamesHome !== undefined && pick.gamesHome !== '' && Number.isFinite(Number(pick.gamesHome));
    const sample = hasAwayGames && hasHomeGames
      ? `Evidence · ${text(pick.confidence)} (uncalibrated) · current-season games A/H ${pick.gamesAway}/${pick.gamesHome}`
      : `Evidence · ${text(pick.confidence)} (uncalibrated) · current-season sample unavailable`;
    card.append(el('p', 'abbeys-card-meta', sample));

    const details = el('details', 'abbeys-why-details');
    details.append(el('summary', '', 'Why this pick?'));
    const body = el('div', 'abbeys-evidence-body');
    body.append(el('p', 'abbeys-exact-score', `Frozen exact-score projection · ${text(pick?.away, 'Away').toUpperCase()} ${scoreText(pick?.projectedAway, pick?.projectedHome)} ${text(pick?.home, 'Home').toUpperCase()}`));

    const evidence = evidenceFor(pick);
    const availability = el('section', 'abbeys-evidence-group');
    availability.append(el('h4', '', 'Current availability evidence'));
    availability.append(list(evidence.availability, 'No current availability evidence attached.'));
    body.append(availability);
    const supporting = el('section', 'abbeys-evidence-group');
    supporting.append(el('h4', '', 'Supporting evidence'));
    supporting.append(list(evidence.support, 'No supporting evidence attached.'));
    body.append(supporting);
    const concerns = el('section', 'abbeys-evidence-group abbeys-concerns');
    concerns.append(el('h4', '', 'Concerns and opposing evidence'));
    concerns.append(list(evidence.concerns, 'No concerns supplied.'));
    body.append(concerns);
    settlementDetails(body, pick);
    marketContext(body, week, pick);
    body.append(el('p', 'abbeys-historical-note', 'Historical matchup context · none verified or used for this pick.'));
    details.append(body);
    card.append(details);
    return card;
  }

  function renderRecord(parent, record, recordScope) {
    const section = el('section', 'abbeys-record');
    const heading = el('h3', '', 'Season record');
    if (recordScope) heading.append(el('span', 'abbeys-record-scope', ` · ${recordScope}`));
    section.append(heading);
    const grid = el('dl', 'abbeys-record-grid');
    for (const [key, label] of [['wins', 'Wins'], ['losses', 'Losses'], ['ties', 'Ties'], ['pending', 'Pending']]) {
      const value = record && record[key] !== undefined && record[key] !== null ? String(record[key]) : '—';
      addFact(grid, label, value, 'abbeys-record-item');
    }
    section.append(grid);
    parent.append(section);
  }

  function renderMethodology(parent, payload, week) {
    const details = el('details', 'abbeys-method-details');
    details.append(el('summary', '', 'Methodology and source cutoffs'));
    details.append(el('h3', 'abbeys-method-name', week?.methodology?.name || 'Methodology unavailable'));
    details.append(el('p', 'abbeys-method-description', week?.methodology?.description || 'No methodology description was supplied.'));
    const limitations = itemStrings(week?.methodology?.limitations);
    const listNode = el('ul', 'abbeys-limitations');
    if (limitations.length) limitations.forEach(value => listNode.append(el('li', '', value)));
    else listNode.append(el('li', '', 'No limitations were supplied.'));
    details.append(listNode);
    const source = week?.source || payload?.source || {};
    const facts = el('dl', 'abbeys-facts abbeys-source-facts');
    addFact(facts, 'Season / week', `${week?.season ?? '—'} / ${week?.week ?? '—'}`);
    addFact(facts, 'Input cutoff', source.cutoff);
    addFact(facts, 'Source snapshot', dateLabel(source.generatedAt));
    addFact(facts, 'Source hash', source.sourceSHA);
    addFact(facts, 'Week frozen', dateLabel(week?.frozenAt));
    addFact(facts, 'Observation hash', week?.observationHash);
    addFact(facts, 'Model version', week?.modelVersion || payload?.modelVersion);
    details.append(facts);
    parent.append(details);
  }

  function renderMonday(parent, week) {
    const monday = week?.monday;
    if (!monday) return;
    const section = el('section', 'abbeys-monday');
    section.append(el('span', 'abbeys-eyebrow', 'Final Monday game · exact-score projection'));
    section.append(el('h3', '', `${text(monday.away, 'Away').toUpperCase()} @ ${text(monday.home, 'Home').toUpperCase()}`));
    section.append(el('p', 'abbeys-monday-score', `${text(monday.away, 'Away').toUpperCase()} ${scoreText(monday.predictedAway, monday.predictedHome)} ${text(monday.home, 'Home').toUpperCase()}`));
    if (monday.settlement) {
      const settlement = monday.settlement;
      section.append(el('p', 'abbeys-monday-actual', `Final · ${text(monday.away).toUpperCase()} ${scoreText(settlement.actualAway, settlement.actualHome)} ${text(monday.home).toUpperCase()}`));
      const validScores = [settlement.actualAway, settlement.actualHome, monday.predictedAway, monday.predictedHome].every(value => value !== null && value !== undefined && Number.isFinite(Number(value)));
      if (validScores) {
        const awayError = Math.abs(Number(settlement.actualAway) - Number(monday.predictedAway));
        const homeError = Math.abs(Number(settlement.actualHome) - Number(monday.predictedHome));
        const combinedError = Math.abs(Number(settlement.actualAway) + Number(settlement.actualHome) - Number(monday.predictedAway) - Number(monday.predictedHome));
        section.append(el('p', 'abbeys-monday-errors', `Score errors · Away ${awayError} · Home ${homeError} · Combined ${combinedError}`));
        section.append(el('p', 'abbeys-muted', 'Descriptive error for one settled game; not model validation.'));
      }
      section.append(el('p', 'abbeys-muted', `Settlement source · ${text(settlement.source)} · ${dateLabel(settlement.settledAt)}`));
    } else {
      section.append(el('p', 'abbeys-muted', 'Frozen for this week. No settlement metrics are shown before the game is final.'));
    }
    parent.append(section);
  }

  function paint(panel, state, payload, restoreWeekFocus = false) {
    const weeks = sortWeeks(payload.weeks.filter(week => week && typeof week === 'object'));
    const board = el('section', 'abbeys-board');
    board.setAttribute('aria-label', 'ABBEYS current-season prediction board');
    const top = el('header', 'abbeys-board-header');
    top.append(el('p', 'abbeys-kicker', 'GOING LONG · CURRENT SEASON'));
    top.append(el('h2', '', 'ABBEYS'));
    top.append(el('p', 'abbeys-board-intro', 'Frozen weekly NFL picks. Confidence is an uncalibrated evidence category, not a win probability.'));
    board.append(top);

    if (!weeks.length) {
      board.append(el('p', 'abbeys-empty', 'No frozen ABBEYS weeks are available yet.'));
      panel.replaceChildren(board);
      if (restoreWeekFocus) panel.querySelector('.abbeys-week-select')?.focus({ preventScroll: true });
      return;
    }

    let rememberedWeek = null;
    try { rememberedWeek = root.localStorage?.getItem?.(WEEK_KEY); } catch (_) { /* Storage can be disabled. */ }
    const requested = state.selectedWeekKey || selectedWeekKey || rememberedWeek;
    const week = weeks.find(item => weekId(item) === requested) || weeks[0];
    state.selectedWeekKey = weekId(week);
    selectedWeekKey = state.selectedWeekKey;
    try { root.localStorage?.setItem?.(WEEK_KEY, selectedWeekKey); } catch (_) { /* Storage can be disabled. */ }

    const controls = el('div', 'abbeys-controls');
    const label = el('label', 'abbeys-week-label');
    label.append(el('span', '', 'Season / week'));
    const select = el('select', 'abbeys-week-select');
    select.setAttribute('aria-label', 'Choose ABBEYS season and week');
    weeks.forEach(optionWeek => {
      const option = el('option', '', `${optionWeek.season ?? 'Season'} · Week ${String(optionWeek.week ?? '').padStart(2, '0')}`);
      option.value = weekId(optionWeek);
      option.selected = option.value === state.selectedWeekKey;
      select.append(option);
    });
    select.addEventListener('change', () => {
      state.selectedWeekKey = select.value;
      selectedWeekKey = select.value;
      try { root.localStorage?.setItem?.(WEEK_KEY, select.value); } catch (_) { /* Storage can be disabled. */ }
      paint(panel, state, payload, true);
    });
    label.append(select);
    controls.append(label, el('span', 'abbeys-pick-count', `${Array.isArray(week.picks) ? week.picks.length : 0} frozen picks`));
    board.append(controls, el('p', 'abbeys-freeze-time', `Official picks frozen · ${dateLabel(week.frozenAt)}`));
    if (Array.isArray(week.invalidations) && week.invalidations.length) {
      const notice=el('section','abbeys-error');
      notice.append(el('strong','','This board is invalidated. Original predictions remain visible for audit, not active recommendations.'));
      for (const entry of week.invalidations) notice.append(el('p','',`${text(entry.reason)} · Evidence: ${text(entry.evidence)}`));
      board.append(notice);
    }

    renderRecord(board, payload.record, payload.recordScope);
    renderMonday(board, week);
    const picks = el('section', 'abbeys-picks');
    picks.setAttribute('aria-label', `Week ${week.week} official picks`);
    if (Array.isArray(week.picks) && week.picks.length) week.picks.forEach(pick => picks.append(renderPick(pick || {}, week)));
    else picks.append(el('p', 'abbeys-empty', 'No picks were frozen for this week.'));
    board.append(picks);
    renderMethodology(board, payload, week);
    board.append(el('p', 'abbeys-updated', `Board snapshot · ${dateLabel(payload.generatedAt)}`));
    panel.replaceChildren(board);
    if (restoreWeekFocus) panel.querySelector('.abbeys-week-select')?.focus({ preventScroll: true });
  }

  function errorView(panel, state, error) {
    const box = el('div', 'abbeys-error-box');
    const message = el('p', 'abbeys-error', `ABBEYS data could not be loaded. ${error?.message || 'Please try again later.'}`);
    message.setAttribute('role', 'status');
    const retry = el('button', 'abbeys-retry', 'Retry loading board');
    retry.type = 'button';
    retry.addEventListener('click', () => {
      state.status = 'idle';
      state.promise = null;
      render(panel);
    });
    box.append(message, retry);
    panel.replaceChildren(box);
  }

  function render(panel) {
    if (!panel || typeof panel.replaceChildren !== 'function') return Promise.resolve();
    let state = panelState.get(panel);
    if (!state) {
      state = { status: 'idle', promise: null, selectedWeekKey: null };
      panelState.set(panel, state);
    }
    if (state.status === 'loaded' || state.status === 'failed') return state.promise || Promise.resolve();
    if (state.status === 'loading') return state.promise;

    state.status = 'loading';
    const loading = el('p', 'abbeys-loading', 'Loading the public ABBEYS board…');
    loading.setAttribute('role', 'status');
    panel.replaceChildren(loading);
    state.promise = loadPayload().then(payload => {
      paint(panel, state, payload);
      state.status = 'loaded';
      return payload;
    }).catch(error => {
      state.status = 'failed';
      errorView(panel, state, error);
    });
    return state.promise;
  }

  root.GoingAbbeysUI = { render };
})(globalThis);
