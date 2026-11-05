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

type SortKey = "player" | "projected" | "line" | "actual" | "diff" | "call" | "result";
const decOf = (stat: string) => (stat === "Receptions" ? 1 : 0);
const callOf = (r: ResultPlayer) => (r.market_line === null ? null : r.projected > r.market_line ? "Over" : "Under");
const resultRank = (r: ResultPlayer) => (r.bet_won === null ? 1 : r.bet_won ? 2 : 0);
const SIDES = ["All", "Over projection", "Under projection"];
const CALLS = ["All", "Right", "Wrong"];

function SortTh({ label, k, sort, onSort, right = true, hide = false }: { label: string; k: SortKey; sort: { key: SortKey; dir: 1 | -1 }; onSort: (k: SortKey) => void; right?: boolean; hide?: boolean }) {
  const on = sort.key === k;
  return (
    <th scope="col" aria-sort={on ? (sort.dir === 1 ? "ascending" : "descending") : "none"} className={cn("px-2 py-1 font-normal", right && "text-right", hide && "hidden sm:table-cell")}>
      <button type="button" onClick={() => onSort(k)} className={cn("min-h-[44px] cursor-pointer text-[13px] hover:text-white", on ? "text-white" : "text-muted")}>{label}{on ? (sort.dir === 1 ? " ▲" : " ▼") : ""}</button>
    </th>
  );
}

function PropTable({ players, stat }: { players: ResultPlayer[]; stat: string }) {
  const [side, setSide] = useState("All");
  const [call, setCall] = useState("All");
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "diff", dir: -1 });
  const onSort = (k: SortKey) => setSort((s) => (s.key === k ? { key: k, dir: (s.dir * -1) as 1 | -1 } : { key: k, dir: k === "player" ? 1 : -1 }));
  const base = useMemo(() => (stat === "All stats" ? players : players.filter((p) => p.stat === stat)), [players, stat]);
  const over = base.filter((p) => p.actual > p.projected).length, under = base.filter((p) => p.actual < p.projected).length;
  const lined = base.filter((p) => p.bet_won !== null);
  const right = lined.filter((p) => p.bet_won).length;
  const rows = useMemo(() => {
    let x = base;
    if (side === "Over projection") x = x.filter((p) => p.actual > p.projected);
    if (side === "Under projection") x = x.filter((p) => p.actual < p.projected);
    if (call === "Right") x = x.filter((p) => p.bet_won === true);
    if (call === "Wrong") x = x.filter((p) => p.bet_won === false);
    const val = (p: ResultPlayer): number | string => {
      switch (sort.key) {
        case "player": return p.player;
        case "projected": return p.projected;
        case "line": return p.market_line ?? -1;
        case "actual": return p.actual;
        case "diff": return p.actual - p.projected;
        case "call": return callOf(p) ?? "";
        default: return resultRank(p);
      }
    };
    return [...x].sort((a, b) => { const va = val(a), vb = val(b); return (va < vb ? -1 : va > vb ? 1 : 0) * sort.dir; });
  }, [base, side, call, sort]);

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        <FilterRow label="Actual vs projection"><Segmented label="Actual vs projection" options={SIDES} value={side} onChange={setSide} /></FilterRow>
        <FilterRow label="Our call vs the line"><Segmented label="Our call vs the line" options={CALLS} value={call} onChange={setCall} /></FilterRow>
      </div>
      <p className="max-w-[75ch] text-[15px] text-slate-300">
        {base.length} players: {over} finished over their projection and {under} under.
        {lined.length > 0 && ` Where a market line was saved, our side of the line was right ${right} of ${lined.length} times (${pct(right / lined.length)}).`}
        {" "}Our call is Over when the projection is above the line and Under when it is below. A call is Right when the player's actual landed on that side of the line: project 45, line 35, take the over, and an actual of 40 is a win even though it missed the projection.
      </p>
      <div className="overflow-x-auto bg-panel p-2 sm:p-4">
        <table className="w-full min-w-[640px] text-left text-[15px]" aria-label="Player props, projection, line, actual and result">
          <thead>
            <tr className="border-b border-bg">
              <SortTh label="Player" k="player" sort={sort} onSort={onSort} right={false} />
              <SortTh label="Projected" k="projected" sort={sort} onSort={onSort} />
              <SortTh label="Line" k="line" sort={sort} onSort={onSort} />
              <SortTh label="Actual" k="actual" sort={sort} onSort={onSort} />
              <SortTh label="Actual minus projection" k="diff" sort={sort} onSort={onSort} hide />
              <SortTh label="Our call" k="call" sort={sort} onSort={onSort} />
              <SortTh label="Result" k="result" sort={sort} onSort={onSort} />
            </tr>
          </thead>
          <tbody>
            {rows.length ? rows.map((r) => {
              const dec = decOf(r.stat), d = r.actual - r.projected, c = callOf(r);
              return (
                <tr key={`${r.gid}${r.team}${r.player}${r.stat}`} className={cn("border-t border-bg", r.bet_won === true && "bg-green-500/10", r.bet_won === false && "bg-red-500/10")}>
                  <td className="px-2 py-2">{r.player} <span className="text-[13px] text-muted">{r.team} vs {r.opp}</span>{stat === "All stats" && <span className="block text-[13px] text-muted">{r.stat}</span>}</td>
                  <td className="px-2 text-right text-muted">{r.projected.toFixed(dec)}</td>
                  <td className="px-2 text-right text-muted">{r.market_line === null ? "No line" : r.market_line.toFixed(dec === 0 ? 1 : 1)}</td>
                  <td className="px-2 text-right text-lg font-bold">{r.actual.toFixed(dec)}</td>
                  <td className="hidden px-2 text-right text-muted sm:table-cell">{d >= 0 ? "+" : "−"}{Math.abs(d).toFixed(dec)} {d > 0 ? "over" : d < 0 ? "under" : "even"}</td>
                  <td className="px-2 text-right">{c ?? "n/a"}</td>
                  <td className="px-2 text-right">{r.bet_won === null ? <Badge>{r.market_line === null ? "No line" : "Push"}</Badge> : <Badge tone={r.bet_won ? "green" : "red"}>{r.bet_won ? "Right" : "Wrong"}</Badge>}</td>
                </tr>
              );
            }) : <tr><td colSpan={7} className="py-4 text-sm text-muted">No players match these filters.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// What the saved pregame forecasts got right and wrong in a week. Every projection shown was saved before the game.
export function ResultsView({ weeks, latest, onOpenGame }: { weeks: number[]; latest: number; onOpenGame: (gid: string) => void }) {
  const [week, setWeek] = useState<number | null>(null);
  const [data, setData] = useState<WeekResults | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stat, setStat] = useState("All stats");

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
        <FilterRow label="Stat"><Segmented label="Stat" options={["All stats", ...STATS]} value={stat} onChange={setStat} /></FilterRow>
        {ps && stat !== "All stats" && (
          <p className="text-[15px] text-slate-300">
            {ps.n} players projected. Off by {num(ps.mean_abs_error, stat === "Receptions" ? 1 : 0)} on average, {ps.bias >= 0 ? "above" : "below"} the projection by {num(Math.abs(ps.bias), stat === "Receptions" ? 1 : 0)} on balance.
            {` ${pct(ps.close_rate)} landed close.`}{ps.inside_range !== null && ` The wide 8-in-10 range held ${pct(ps.inside_range)} of the time, which is easy to do and not the test.`}
          </p>
        )}
        <PropTable players={data.players} stat={stat} />
        <p className="max-w-[75ch] text-sm text-muted">
          Actual yards and catches come from the official play-by-play, or from the last stored ESPN box score for a game it has not published. A player is scored only if he had at least one target, carry or pass attempt in the game.
          {data.summary.left_out > 0 && ` ${data.summary.left_out} projected player lines were left out this week because the player had none, whether he did not play or was not used.`}
          {" "}Touchdown calls are not scored here yet because their pregame chances were not saved.
        </p>
      </section>
    </div>
  );
}
