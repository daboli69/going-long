import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { ResultGame, ResultPlayer, WeekResults } from "../types";
import { cn, num, pct } from "../lib";
import { Badge, Callout, FilterRow, Segmented } from "./ui/primitives";

const STATS = ["Passing yards", "Rushing yards", "Receiving yards", "Receptions"];

const Verdict = ({ ok }: { ok: boolean | null }) => (ok === null ? <Badge>Not scored</Badge> : <Badge tone={ok ? "green" : "red"}>{ok ? "Right" : "Wrong"}</Badge>);

function byMargin(g: ResultGame) {
  if (g.exp_margin === null) return "No spread saved";
  const exp = Math.abs(g.exp_margin) < 0.25 ? "even" : `${g.exp_margin > 0 ? g.home : g.away} by ${num(Math.abs(g.exp_margin))}`;
  const act = g.margin === 0 ? "tie" : `${g.margin > 0 ? g.home : g.away} by ${Math.abs(g.margin).toFixed(0)}`;
  return `Expected ${exp}, finished ${act}`;
}

function Tile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="bg-panel p-4">
      <div className="text-[13px] text-muted">{label}</div>
      <div className="text-xl font-bold">{value}</div>
      {note && <div className="text-[13px] text-muted">{note}</div>}
    </div>
  );
}

function PlayerRow({ r }: { r: ResultPlayer }) {
  const dec = r.stat === "Receptions" ? 1 : 0;
  return (
    <div role="row" className="grid min-h-[48px] grid-cols-[minmax(0,1fr)_4em_4em_4.5em] items-center gap-x-3 border-t border-bg py-2 sm:grid-cols-[minmax(0,1fr)_5em_5em_5em_5em]">
      <div role="cell" className="min-w-0 text-[15px]">{r.player} <span className="text-[13px] text-muted">{r.team} vs {r.opp}</span>
        {r.no_line && <span className="block text-[13px] text-muted">No recorded line, counted as 0</span>}</div>
      <div role="cell" className="text-right text-[15px] text-muted">{r.projected.toFixed(dec)}</div>
      <div role="cell" className="text-right text-xl font-bold">{r.actual.toFixed(dec)}</div>
      <div role="cell" className="hidden text-right text-[15px] text-muted sm:block">{r.error >= 0 ? "+" : "−"}{Math.abs(r.error).toFixed(dec)}</div>
      <div role="cell" className="text-right"><Verdict ok={r.inside} /></div>
    </div>
  );
}

// What the saved pregame forecasts got right and wrong in a week. Every projection shown was saved before the game.
export function ResultsView({ week, onOpenGame }: { week: number; onOpenGame: (gid: string) => void }) {
  const [data, setData] = useState<WeekResults | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stat, setStat] = useState("Receiving yards");
  const [show, setShow] = useState("Biggest misses");

  useEffect(() => {
    setData(null); setError(null);
    api.results(week).then(setData).catch((e) => setError(String(e)));
  }, [week]);

  const rows = useMemo(() => {
    if (!data) return [];
    const x = data.players.filter((p) => p.stat === stat);
    const sizable = (p: ResultPlayer) => p.projected >= (stat === "Receptions" ? 2 : 20);
    if (show === "Biggest misses") return [...x].sort((a, b) => Math.abs(b.error) - Math.abs(a.error)).slice(0, 12);
    if (show === "Closest calls") return x.filter(sizable).sort((a, b) => Math.abs(a.error) - Math.abs(b.error)).slice(0, 12);
    return [...x].sort((a, b) => b.projected - a.projected);
  }, [data, stat, show]);

  if (error) return <Callout tone="amber">The results could not be loaded ({error}).</Callout>;
  if (!data) return <Callout tone="blue">Loading the results.</Callout>;
  const s = data.summary;
  if (!data.games.length) return <Callout tone="blue">No games from week {week} have finished yet, so there is nothing to score. Come back after the first game ends.</Callout>;
  const ps = data.player_summary[stat];
  return (
    <div className="space-y-6">
      <h1 className="text-[22px] font-bold leading-tight text-white sm:text-2xl">Week {week} results</h1>
      <p className="max-w-[75ch] text-[15px] text-muted">
        Every number below was saved before the game. {s.games_played} of the week's games are final{s.games_played > s.games_scored ? `, and ${s.games_scored} have a saved forecast to score` : ""}.
        "Right" for a winner means the team we favored won. "Right" for a player means he finished inside the 8-in-10 range we showed, which should happen about 8 times in 10.
      </p>
      <section aria-label="Week summary" className="grid grid-cols-2 gap-0.5 sm:grid-cols-4">
        <Tile label="Winners picked right" value={`${s.picked_right} of ${s.picked_right + s.picked_wrong}`} note={s.accuracy === null ? undefined : `${pct(s.accuracy)}; we averaged ${pct(s.avg_confidence)} confidence`} />
        <Tile label="Margin off by, on average" value={`${num(s.mean_abs_margin_error)} points`} note={`${pct(s.margin_inside_80)} inside the 8-in-10 range`} />
        <Tile label="Total off by, on average" value={`${num(s.mean_abs_total_error)} points`} note={`${pct(s.total_inside_80)} inside the 8-in-10 range`} />
        <Tile label="Player ranges that held" value={pct(Object.values(data.player_summary).reduce((a, v) => a + (v.inside_range ?? 0) * v.n, 0) / Math.max(1, Object.values(data.player_summary).reduce((a, v) => a + v.n, 0)))} note="Target: about 80%" />
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
            {ps.inside_range !== null && ` ${pct(ps.inside_range)} finished inside the range${ps.inside_range < 0.7 ? ", fewer than the 8 in 10 we claim" : ""}.`}
          </p>
        )}
        <section aria-label={`${stat} results`} className="bg-panel p-4 sm:p-6">
          <div role="table" aria-label={`${stat}, projected and actual`}>
            <div role="row" className={cn("grid grid-cols-[minmax(0,1fr)_4em_4em_4.5em] gap-x-3 text-[13px] text-muted sm:grid-cols-[minmax(0,1fr)_5em_5em_5em_5em]")}>
              <div role="columnheader">Player</div><div role="columnheader" className="text-right">Projected</div><div role="columnheader" className="text-right">Actual</div>
              <div role="columnheader" className="hidden text-right sm:block">Miss</div><div role="columnheader" className="text-right">In range?</div>
            </div>
            {rows.length ? rows.map((r) => <PlayerRow key={`${r.gid}${r.team}${r.player}${r.stat}`} r={r} />) : <p role="row" className="py-4 text-sm text-muted">No projections for this stat yet.</p>}
          </div>
        </section>
        <p className="max-w-[75ch] text-sm text-muted">
          Actual yards and catches come from the official play-by-play, or from the last stored ESPN box score for a game it has not published. A player with no recorded line counts as zero, which includes a player who did not play.
          Touchdown calls are not scored here yet because their pregame chances were not saved.
        </p>
      </section>
    </div>
  );
}
