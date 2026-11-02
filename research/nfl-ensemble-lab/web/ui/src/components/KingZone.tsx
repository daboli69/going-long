import { useEffect, useState } from "react";
import { api } from "../api";
import type { KingBoard, KingPair, KingRow, KingWalk, KingWeek } from "../types";
import { etStamp, pct } from "../lib";
import { Badge, Callout } from "./ui/primitives";
import { Num } from "./motion";

const BETS: { key: keyof KingPair; label: string; mine: (r: KingRow) => number }[] = [
  { key: "first", label: "First touchdown scorer", mine: (r) => r.first },
  { key: "anytime", label: "Anytime touchdown scorer", mine: (r) => r.anytime },
  { key: "two_plus", label: "2 or more touchdowns", mine: (r) => r.two_plus },
];

function Row({ r, top }: { r: KingRow; top: number }) {
  return (
    <details className="group border-t border-bg">
      <summary className="grid min-h-[56px] cursor-pointer list-none grid-cols-[2em_minmax(0,1fr)_4.5em] items-center gap-x-3 py-2 sm:grid-cols-[2.5em_minmax(0,1.2fr)_minmax(0,0.8fr)_5em_5em_5.5em]">
        <span className="text-[15px] text-muted">{r.rank}</span>
        <span className="min-w-0 text-[15px]">{r.player} <span className="text-[13px] text-muted">{r.pos}, {r.team} vs {r.opp}</span>
          <span className="block text-[13px] text-muted group-open:hidden">{r.why[0] ?? ""}</span></span>
        <span className="hidden sm:block" aria-hidden="true"><span className="block h-2 bg-bg"><span className="block h-2 bg-yellow-400" style={{ width: `${Math.max(2, (r.chance / top) * 100)}%` }} /></span></span>
        <span className="text-right text-xl font-bold"><Num value={r.chance} pct /></span>
        <span className="hidden text-right text-[15px] text-muted sm:block">{pct(r.anytime)}</span>
        <span className="hidden text-right text-[15px] text-muted sm:block">{r.pool_index.toFixed(1)}x</span>
      </summary>
      <div className="mb-4 ml-[2.75em] grid gap-x-8 gap-y-3 text-[15px] lg:grid-cols-2">
        <ul className="list-disc space-y-1 pl-4 text-slate-300">{r.why.map((w) => <li key={w}>{w}</li>)}</ul>
        <div>
          <div role="table" aria-label={`Touchdown bets for ${r.player}`}>
            <div role="row" className="grid grid-cols-[minmax(0,1.3fr)_4em_5.5em] gap-x-3 pb-1 text-[13px] text-muted"><span>Eligible bet</span><span className="text-right">Wins</span><span className="text-right">Longest too</span></div>
            {BETS.map((b) => (
              <div role="row" key={b.key} className="grid grid-cols-[minmax(0,1.3fr)_4em_5.5em] gap-x-3 border-t border-bg py-1">
                <span>{b.label}{r.pairs_best_with === b.key && <span className="text-[13px] text-yellow-400"> pairs best</span>}</span>
                <span className="text-right">{pct(b.mine(r))}</span>
                <span className="text-right">{r.given_longest[b.key] === null ? "n/a" : pct(r.given_longest[b.key] as number)}</span>
              </div>
            ))}
          </div>
          <p className="mt-2 text-[13px] text-muted">
            "Longest too" is how often he also has the longest touchdown when that bet wins. A rarer bet always overlaps more with it, so this says nothing about price. {r.market_anytime !== null ? `Kalshi's anytime quote was ${pct(r.market_anytime)} (the model says ${pct(r.anytime)}).` : "No anytime price was archived for him."}
            {" "}Pool index {r.pool_index.toFixed(1)}x, between {r.pool_index_range[0].toFixed(1)}x and {r.pool_index_range[1].toFixed(1)}x under other crowd assumptions.
          </p>
        </div>
      </div>
    </details>
  );
}

function Status({ b }: { b: KingBoard }) {
  const w = b.walk as KingWalk;
  if (!w || !w.test) return <Callout tone="amber">The walk-forward test has not been run yet, so this board is not checked against anything.</Callout>;
  const t = w.test, v = w.verdict, d = t.diff_vs_b1;
  const top = b.rows[0]?.chance ?? 0;
  const bucket = t.reliability.filter((r) => { const m = r.bucket.match(/(\d+)% to/); return m ? top >= Number(m[1]) / 100 : false; }).pop() ?? null;
  const both = v.P1_beats_expected_td_split && v.P2_calibrated;
  return (
    <Callout tone={both && t.top_pick.stated - t.top_pick.realized <= t.top_pick.se ? "green" : "amber"}>
      <strong>{v.P1_beats_expected_td_split ? "Ranks better than the plain split of expected touchdowns." : "Not shown to rank better than the plain split."}{" "}
      {t.top_pick.stated - t.top_pick.realized > t.top_pick.se ? "The chances run a little high at the top." : "The chances are about right at the top."}</strong>{" "}
      On {t.games} games from 2022 to 2025, each predicted from earlier history only, the average log score was {t.mean_log_model.toFixed(2)} against {t.mean_log_b1.toFixed(2)} for the plain split
      (gain {d.mean.toFixed(2)}, 95% range {d.ci95[0].toFixed(2)} to {d.ci95[1].toFixed(2)}). The top pick of each game was stated at {pct(t.top_pick.stated, 1)} and won {pct(t.top_pick.realized, 1)} of the time.
      {bucket && ` When the model stated ${bucket.bucket.replace(" to 100%", " or more")}, the player had the longest touchdown ${pct(bucket.realized, 0)} of the time (${bucket.n} cases).`}
      {" "}The test is large enough to see a gain of this size, but not a gain as small as 0.05 (that needs about {Math.round(t["games_needed_80pct_power_for_0.05"])} games). This is a check of probabilities, not of profit: no prices for this prize exist. Details: docs/KINGZONE_WALKFORWARD.md.
    </Callout>
  );
}

// Who is most likely to score the longest touchdown of a game, for the Monday-night "King of the End Zone" promotion.
export function KingZoneView({ week }: { week: number }) {
  const [wk, setWk] = useState<KingWeek | null>(null);
  const [gid, setGid] = useState<string | null>(null);
  const [board, setBoard] = useState<KingBoard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setWk(null); setBoard(null); setError(null);
    api.kingWeek(week).then((w) => { if (live) { setWk(w); setGid(w.default_gid); } }).catch((e) => live && setError(String(e)));
    return () => { live = false; };
  }, [week]);

  useEffect(() => {
    if (!gid) return;
    let live = true;
    setBoard(null); setError(null);
    api.kingGame(gid).then((b) => live && setBoard(b)).catch((e) => live && setError(String(e)));
    return () => { live = false; };
  }, [gid]);

  const picker = (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <h1 className="text-[22px] font-bold leading-tight text-white sm:text-2xl">King of the End Zone</h1>
      <label className="sr-only" htmlFor="king-game">Game</label>
      <select id="king-game" className="min-h-[44px] bg-panel px-4 text-base text-white hover:bg-raised" value={gid ?? ""} onChange={(e) => setGid(e.target.value)}>
        {wk?.games.map((g) => <option key={g.gid} value={g.gid}>{g.away} at {g.home}{g.monday ? " (Monday)" : ""}{g.completed ? " (final)" : ""}</option>)}
      </select>
    </div>
  );
  if (error) return <div className="space-y-4">{picker}<Callout tone="amber">The board could not be built ({error}).</Callout></div>;
  if (!board) return <div className="space-y-4">{picker}<Callout tone="blue">Simulating the game 20,000 times. This takes up to a minute the first time.</Callout></div>;

  const top = board.rows[0]?.chance ?? 1;
  return (
    <div className="space-y-6">
      {picker}
      <p className="max-w-[75ch] text-[15px] text-muted">
        The promotion pays the player who scores the longest touchdown of the game. A passing touchdown counts for the receiver, and a return or defensive touchdown can win it. The chance is the model's estimate that a player's touchdown is the longest. It is not a price or a bet recommendation.
      </p>
      <Status b={board} />
      <section aria-label="Top pick" className="grid grid-cols-1 gap-x-10 gap-y-4 bg-panel p-4 sm:grid-cols-[auto_1fr] sm:p-6">
        <div>
          <div className="text-[13px] text-muted">{board.away} at {board.home}, {etStamp(board.kickoff_utc)}</div>
          <div className="fig text-[64px] sm:text-[88px]"><Num value={top} pct /></div>
          <div className="text-[15px] text-slate-300">{board.rows[0]?.player}, the likeliest owner of the longest touchdown</div>
        </div>
        <dl className="grid content-end divide-y divide-line self-end text-[15px]">
          <div className="flex items-baseline justify-between gap-4 py-2"><dt className="text-muted">Typical length of the longest touchdown</dt><dd className="whitespace-nowrap text-xl font-bold">{board.expected_longest.toFixed(0)} yards</dd></div>
          <div className="flex items-baseline justify-between gap-4 py-2"><dt className="text-muted">Longest is a defense, special-teams or unlisted player's</dt><dd className="whitespace-nowrap text-xl font-bold">{pct(board.field)}</dd></div>
          <div className="flex items-baseline justify-between gap-4 py-2"><dt className="text-muted">Expected offensive touchdowns</dt><dd className="text-xl font-bold">{board.teams.map((t) => `${t.team} ${t.lam.toFixed(1)}`).join(", ")}</dd></div>
          <div className="flex items-baseline justify-between gap-4 py-2"><dt className="text-muted">Forecast saved before kickoff</dt><dd className="text-xl font-bold">{board.frozen ? (board.frozen.before_kickoff ? `Yes, ${board.frozen.sha256.slice(0, 8)}` : "Saved after kickoff") : "Not yet"}</dd></div>
        </dl>
      </section>
      {board.completed && <Callout tone="blue">This game is final. The board is today's rebuild, not the saved forecast.</Callout>}

      <section aria-label="Ranking" className="bg-panel p-4 sm:p-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-xl leading-tight text-white">Who is likeliest</h2>
          <Badge>Pool index is an estimate</Badge>
        </div>
        <div role="table" aria-label="Longest touchdown chances" className="mt-3">
          <div role="row" className="hidden grid-cols-[2.5em_minmax(0,1.2fr)_minmax(0,0.8fr)_5em_5em_5.5em] gap-x-3 pb-2 text-[13px] text-muted sm:grid">
            <span>#</span><span>Player</span><span /><span className="text-right">Longest</span><span className="text-right">Any TD</span><span className="text-right">Pool index</span>
          </div>
          {board.rows.map((r) => <Row key={r.pid} r={r} top={top} />)}
        </div>
        <p className="mt-3 max-w-[85ch] text-[13px] text-muted">
          Pool index: his share of the longest-touchdown chance divided by an assumed share of the entries on him. The assumption is that entries follow each player's anytime-touchdown chance (Kalshi's quote where one was archived, else the model's). It is not data: no pick counts are public. Above 1.0x means he would be less crowded than his chance suggests; the range beside each player uses entries that follow that chance to the power 0.5 to 1.5.
          Players listed hold {pct(board.listed_total)} of the chance; the rest is the field and a game with no touchdown ({pct(board.no_touchdown, 1)}).
          {board.dropped_out.length > 0 && ` Left out as Out or on injured reserve: ${board.dropped_out.join(", ")}.`}
        </p>
      </section>

      <section aria-label="How it works" className="bg-panel p-4 sm:p-6">
        <h2 className="text-xl leading-tight text-white">How the chance is built</h2>
        <ul className="mt-3 max-w-[80ch] list-disc space-y-2 pl-5 text-[15px] text-slate-300">
          <li>Every player's carries and targets since 2016 give a Bayesian estimate, pooled by position, role and player, of how often a touch gains 15+ yards and how far those long gains run (a generalized Pareto tail; a touchdown counts as a gain that was stopped by the goal line).</li>
          <li>The game is simulated 20,000 times drive by drive: starting field position, downs, who gets the ball by his share of the team's carries and targets, turnovers, and the opponent's record of allowing 15+ yard gains. Each team's drives are scaled so its touchdowns match its recent scoring and the opponent's.</li>
          <li>The longest touchdown of each simulated game wins, including defense and special teams. Ties split.</li>
          <li>Only play-by-play history is used. Tracking speed was tested on the 2023 season and did not add anything, so it is not used (docs/kingzone_speed_check.json).</li>
        </ul>
      </section>
    </div>
  );
}
