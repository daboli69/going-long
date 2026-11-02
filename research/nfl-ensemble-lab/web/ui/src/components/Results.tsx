import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { ResultGame, ResultPlayer, WeekResults } from "../types";
import { cn, num, pct } from "../lib";
import { Badge, Callout, FilterRow, Segmented } from "./ui/primitives";
import { Num } from "./motion";

const STATS = ["Passing yards", "Rushing yards", "Receiving yards", "Receptions"];

const Verdict = ({ ok }: { ok: boolean | null }) => (ok === null ? <Badge>Not scored</Badge> : <Badge tone={ok ? "green" : "red"}>{ok ? "Right" : "Wrong"}</Badge>);

function byMargin(g: ResultGame) {
  if (g.exp_margin === null) return "No spread saved";
  const exp = Math.abs(g.exp_margin) < 0.25 ? "even" : `${g.exp_margin > 0 ? g.home : g.away} by ${num(Math.abs(g.exp_margin))}`;
  const act = g.margin === 0 ? "tie" : `${g.margin > 0 ? g.home : g.away} by ${Math.abs(g.margin).toFixed(0)}`;
  return `Expected ${exp}, finished ${act}`;
}

function PlayerRow({ r }: { r: ResultPlayer }) {
  const dec = r.stat === "Receptions" ? 1 : 0;
  return (
    <div role="row" className="grid min-h-[48px] grid-cols-[minmax(0,1fr)_4em_4em_4.5em] items-center gap-x-3 border-t border-bg py-2 sm:grid-cols-[minmax(0,1fr)_5em_5em_5em_5em]">
      <div role="cell" className="min-w-0 text-[15px]">{r.player} <span className="text-[13px] text-muted">{r.team} vs {r.opp}</span>
        <span className="block text-[13px] text-muted">{r.opps} {r.stat === "Passing yards" ? "pass attempts" : r.stat === "Rushing yards" ? "carries" : "targets"}</span></div>
      <div role="cell" className="text-right text-[15px] text-muted">{r.projected.toFixed(dec)}</div>
      <div role="cell" className="text-right text-xl font-bold">{r.actual.toFixed(dec)}</div>
      <div role="cell" className="hidden text-right text-[15px] text-muted sm:block">{r.error >= 0 ? "+" : "−"}{Math.abs(r.error).toFixed(dec)}</div>
      <div role="cell" className="text-right"><Verdict ok={r.close} /><span className="block text-[13px] text-muted">within ±{r.tolerance.toFixed(r.stat === "Receptions" ? 0 : 0)}</span></div>
    </div>
  );
}

// What the saved pregame forecasts got right and wrong in a week. Every projection shown was saved before the game.
export function ResultsView({ weeks, latest, onOpenGame }: { weeks: number[]; latest: number; onOpenGame: (gid: string) => void }) {
  const [week, setWeek] = useState<number | null>(null);
  const [data, setData] = useState<WeekResults | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stat, setStat] = useState("Receiving yards");
  const [show, setShow] = useState("Biggest misses");

  // Start on the most recent week that has a finished game: try the current week, then step back.
  useEffect(() => {
    let live = true;
    (async () => {
      for (let w = latest; w >= 1; w--) {
        try {
          const r = await api.results(w);
          if (!live) return;
          if (r.games.length || w === 1) { setWeek(w); setData(r); return; }
        } catch (e) { if (live) setError(String(e)); return; }
      }
    })();
    return () => { live = false; };
  }, [latest]);

  const pick = (w: number) => {
    setWeek(w); setData(null); setError(null);
    api.results(w).then(setData).catch((e) => setError(String(e)));
  };

  const rows = useMemo(() => {
    if (!data) return [];
    const x = data.players.filter((p) => p.stat === stat);
    const sizable = (p: ResultPlayer) => p.projected >= (stat === "Receptions" ? 2 : 20);
    if (show === "Biggest misses") return [...x].sort((a, b) => Math.abs(b.error) - Math.abs(a.error)).slice(0, 12);
    if (show === "Closest calls") return x.filter(sizable).sort((a, b) => Math.abs(a.error) - Math.abs(b.error)).slice(0, 12);
    return [...x].sort((a, b) => b.projected - a.projected);
  }, [data, stat, show]);

  const picker = (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <h1 className="text-[22px] font-bold leading-tight text-white sm:text-2xl">Results</h1>
      <label className="sr-only" htmlFor="results-week">Week</label>
      <select id="results-week" className="min-h-[44px] bg-panel px-4 text-base text-white hover:bg-raised" value={week ?? ""} onChange={(e) => pick(Number(e.target.value))}>
        {weeks.map((w) => <option key={w} value={w}>Week {w}</option>)}
      </select>
    </div>
  );
  if (error) return <div className="space-y-4">{picker}<Callout tone="amber">The results could not be loaded ({error}).</Callout></div>;
  if (!data || week === null) return <div className="space-y-4">{picker}<Callout tone="blue">Loading the results.</Callout></div>;
  const s = data.summary;
  if (!data.games.length) return <div className="space-y-4">{picker}<Callout tone="blue">No games from week {week} have finished yet, so there is nothing to score. Pick an earlier week, or come back after the first game ends.</Callout></div>;
  const ps = data.player_summary[stat];
  return (
    <div className="space-y-6">
      {picker}
      <p className="max-w-[75ch] text-[15px] text-muted">
        Every number below was saved before the game. {s.games_played} of the week's games are final{s.games_played > s.games_scored ? `, and ${s.games_scored} have a saved forecast to score` : ""}.
        "Right" for a winner means the team we favored won. "Right" for a player means the projection landed close: within 20% or 15 yards of the actual, whichever is larger, or within 1 catch. A projection of 120 against an actual 80 is wrong.
      </p>
      <section aria-label="Week summary" className="grid grid-cols-1 gap-x-10 gap-y-4 bg-panel p-4 sm:grid-cols-[auto_1fr] sm:p-6">
        <div>
          <div className="text-[13px] text-muted">Winners picked right</div>
          <div className="fig text-[64px] sm:text-[88px]">{s.picked_right}<span className="text-muted"> of </span>{s.picked_right + s.picked_wrong}</div>
          {s.accuracy !== null && <div className="text-[15px] text-slate-300">{pct(s.accuracy)}, at {pct(s.avg_confidence)} average confidence</div>}
        </div>
        <dl className="grid content-end divide-y divide-line self-end text-[15px]">
          <div className="flex items-baseline justify-between gap-4 py-2"><dt className="text-muted">Margin off by, on average</dt><dd className="text-xl font-bold"><Num value={s.mean_abs_margin_error} dec={1} /> points <span className="text-[13px] font-normal text-muted">{pct(s.margin_inside_80)} inside the range</span></dd></div>
          <div className="flex items-baseline justify-between gap-4 py-2"><dt className="text-muted">Total off by, on average</dt><dd className="text-xl font-bold"><Num value={s.mean_abs_total_error} dec={1} /> points <span className="text-[13px] font-normal text-muted">{pct(s.total_inside_80)} inside the range</span></dd></div>
          <div className="flex items-baseline justify-between gap-4 py-2"><dt className="text-muted">Player projections that landed close</dt><dd className="text-xl font-bold">{pct(Object.values(data.player_summary).reduce((a, v) => a + v.close_rate * v.n, 0) / Math.max(1, Object.values(data.player_summary).reduce((a, v) => a + v.n, 0)))} <span className="text-[13px] font-normal text-muted">within 20% or 15 yards</span></dd></div>
        </dl>
      </section>
      {s.pending_actuals.length > 0 && <Callout tone="amber">{s.pending_actuals.length} finished game(s) are not scored for players yet because no official or recorded box score is available for them.</Callout>}

      <section aria-label="Games" className="bg-panel p-4 sm:p-6">
        <h2 className="text-xl leading-tight text-white">Games</h2>
        <div role="table" aria-label="Game results" className="mt-3">
          {data.games.map((g) => (
            <div role="row" key={g.gid} className="grid grid-cols-1 items-center gap-x-4 gap-y-1 border-t border-bg py-3 sm:grid-cols-[minmax(0,1.2fr)_minmax(0,1.6fr)_minmax(0,1.4fr)_5em]">
              <div role="cell"><button type="button" onClick={() => onOpenGame(g.gid)} className="text-left text-[15px] font-semibold text-white underline-offset-2 hover:underline">{g.away} {g.away_score.toFixed(0)}, {g.home} {g.home_score.toFixed(0)}</button>
                <div className="text-[13px] text-muted">{g.kickoff_label}</div></div>
              <div role="cell" className="text-[15px]">We favored {g.pick} ({pct(g.p_pick)})
                <div className="text-[13px] text-muted">{byMargin(g)}</div></div>
              <div role="cell" className="text-[15px] text-muted">
                {g.margin_error === null ? "" : `Margin off by ${Math.abs(g.margin_error).toFixed(1)}`}{g.total_error === null ? "" : `. Total: expected ${num(g.exp_total)}, was ${g.total.toFixed(0)}`}</div>
              <div role="cell" className="sm:text-right"><Verdict ok={g.correct} /></div>
            </div>
          ))}
        </div>
      </section>

      <section aria-label="Players" className="space-y-3">
        <h2 className="text-xl leading-tight text-white">Players</h2>
        <div className="space-y-2">
          <FilterRow label="Stat"><Segmented label="Stat" options={STATS} value={stat} onChange={setStat} /></FilterRow>
          <FilterRow label="Show"><Segmented label="Show" options={["Biggest misses", "Closest calls", "Everyone"]} value={show} onChange={setShow} /></FilterRow>
        </div>
        {ps && (
          <p className="text-[15px] text-slate-300">
            {ps.n} players projected. Off by {num(ps.mean_abs_error, stat === "Receptions" ? 1 : 0)} on average, {ps.bias >= 0 ? "above" : "below"} the projection by {num(Math.abs(ps.bias), stat === "Receptions" ? 1 : 0)} on balance.
            {` ${pct(ps.close_rate)} landed close.`}{ps.inside_range !== null && ` The wide 8-in-10 range held ${pct(ps.inside_range)} of the time, which is easy to do and not the test.`}{ps.bets >= 5 && ` Where a market line was saved, the projection's side won ${ps.bets_won} of ${ps.bets}.`}
          </p>
        )}
        <section aria-label={`${stat} results`} className="bg-panel p-4 sm:p-6">
          <div role="table" aria-label={`${stat}, projected and actual`}>
            <div role="row" className={cn("grid grid-cols-[minmax(0,1fr)_4em_4em_4.5em] gap-x-3 text-[13px] text-muted sm:grid-cols-[minmax(0,1fr)_5em_5em_5em_5em]")}>
              <div role="columnheader">Player</div><div role="columnheader" className="text-right">Projected</div><div role="columnheader" className="text-right">Actual</div>
              <div role="columnheader" className="hidden text-right sm:block">Miss</div><div role="columnheader" className="text-right">Close?</div>
            </div>
            {rows.length ? rows.map((r) => <PlayerRow key={`${r.gid}${r.team}${r.player}${r.stat}`} r={r} />) : <p role="row" className="py-4 text-sm text-muted">No projections for this stat yet.</p>}
          </div>
        </section>
        <p className="max-w-[75ch] text-sm text-muted">
          Actual yards and catches come from the official play-by-play, or from the last stored ESPN box score for a game it has not published. A player is scored only if he had at least one target, carry or pass attempt in the game.
          {data.summary.left_out > 0 && ` ${data.summary.left_out} projected player lines were left out this week because the player had none, whether he did not play or was not used.`}
          {" "}Touchdown calls are not scored here yet because their pregame chances were not saved.
        </p>
      </section>
    </div>
  );
}
