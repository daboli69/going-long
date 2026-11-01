import { useEffect, useState } from "react";
import type { Detail, PropRow } from "../types";
import { cn, pct } from "../lib";
import { Callout, FilterRow, Segmented } from "./ui/primitives";

const ORDER = ["Passing yards", "Rushing yards", "Receiving yards", "Receptions"];
type Sort = { k: "player" | "typical"; d: 1 | -1 };
const COLS = "grid-cols-[minmax(0,1fr)_4em] sm:grid-cols-[minmax(0,1fr)_5em_minmax(0,1.4fr)]";

function Group({ stat, all, rows, sort, onSort, away, home, team }: { stat: string; all: PropRow[]; rows: PropRow[]; sort: Sort; onSort: (k: Sort["k"]) => void; away: string; home: string; team: string }) {
  const dec = stat === "Receptions" ? 1 : 0;
  const mx = Math.max(...all.map((r) => Math.max(r.range_high ?? 0, r.market_line ?? 0, r.typical)));
  const stp = mx > 400 ? 100 : mx > 150 ? 50 : mx > 60 ? 25 : mx > 12 ? 5 : 2, top = Math.ceil(mx / stp) * stp, X = (v: number) => (v / top) * 100;
  const ticks: number[] = [];
  for (let v = 0; v <= top; v += stp) ticks.push(v);
  const sorted = [...rows].sort((a, b) => (sort.k === "player" ? sort.d * a.player.localeCompare(b.player) : sort.d * (a.typical - b.typical)));
  const head = (k: Sort["k"], label: string, right = false) => (
    <button type="button" onClick={() => onSort(k)} className={cn("min-h-[44px] whitespace-nowrap text-[13px] text-muted hover:text-white", right ? "text-right" : "text-left")}
      aria-label={`Sort ${stat} by ${label.toLowerCase()}`}>{label}{sort.k === k ? (sort.d < 0 ? " ▾" : " ▴") : ""}</button>
  );
  const ariaSort = (k: Sort["k"]) => (sort.k === k ? (sort.d < 0 ? "descending" : "ascending") : "none");
  return (
    <section aria-label={stat} className="bg-panel p-4 sm:p-6">
      <h2 className="text-xl leading-tight text-white">{stat}</h2>
      <div role="table" aria-label={`${stat} projections`}>
      <div role="row" className={cn("mt-4 grid gap-x-4", COLS)}>
        <div role="columnheader" aria-sort={ariaSort("player")}>{head("player", "Player")}</div>
        <div role="columnheader" aria-sort={ariaSort("typical")} className="text-right">{head("typical", "Projection", true)}</div>
        <div role="columnheader" className="hidden self-center text-[13px] text-muted sm:block">8 in 10 range</div>
      </div>
      {sorted.length ? sorted.map((r) => (
        <div key={r.player} role="row" className={cn("grid min-h-[48px] items-center gap-x-4 border-t border-bg py-2 sm:py-0", COLS)}>
          <div role="cell" className="min-w-0 text-[15px]">{r.player} <span className="text-[13px] text-muted">{r.team}</span>
            {r.market_line !== null && <span className="block text-[13px] text-accent">Market {r.market_line}+{r.market_chance !== null ? ` at ${pct(r.market_chance)}` : ""}</span>}</div>
          <div role="cell" className="text-right text-xl font-bold">{r.typical.toFixed(dec)}</div>
          <div role="cell" className="col-span-full sm:col-span-1"><div className="relative h-7" role="img" aria-label={r.range_low !== null && r.range_high !== null ? `Range ${r.range_low.toFixed(dec)} to ${r.range_high.toFixed(dec)}` : "No range"}>
            {r.range_low !== null && r.range_high !== null && <span className="absolute top-[11px] h-1.5 bg-chart" style={{ left: `${X(r.range_low)}%`, width: `${X(r.range_high - r.range_low)}%` }} />}
            <span className="absolute top-1 -ml-px h-5 w-[3px] bg-white" style={{ left: `${X(r.typical)}%` }} />
            {r.market_line !== null && <span className="absolute top-0 h-7 w-0.5 bg-accent" style={{ left: `${X(r.market_line)}%` }} />}
          </div></div>
        </div>
      )) : <div role="row"><p role="cell" className="py-4 text-sm text-muted">No {team === away ? away : team === home ? home : team} player has a {stat.toLowerCase()} projection for this game.</p></div>}
      </div>
      <div className="grid grid-cols-1 gap-x-4 sm:grid-cols-[minmax(0,1fr)_5em_minmax(0,1.4fr)]" aria-hidden>
        <div className="hidden sm:block" /><div className="hidden sm:block" />
        <div className="relative mt-1 h-[18px] text-[13px] text-muted">{ticks.map((v) => <span key={v} className="absolute -translate-x-1/2" style={{ left: `${X(v)}%` }}>{v}</span>)}</div>
      </div>
    </section>
  );
}

// Players grouped by stat, each as a range on a labelled scale. Filters and sorting are the same as the old table.
export function Props({ d }: { d: Detail }) {
  const rows = d.props ?? [];
  const present = Array.from(new Set(rows.map((r) => r.stat)));
  const stats = [...ORDER.filter((s) => present.includes(s)), ...present.filter((s) => !ORDER.includes(s))];
  const [stat, setStat] = useState("All");
  const [team, setTeam] = useState("Both");
  const [sorts, setSorts] = useState<Record<string, Sort>>({});
  useEffect(() => { setStat("All"); setTeam("Both"); setSorts({}); }, [d.gid]);
  const out = d.props_left_out ?? [];
  const quest = d.props_questionable ?? [];
  const moves = d.props_moves ?? [];
  const notice = (out.length > 0 || quest.length > 0 || moves.length > 0) && (
    <Callout tone="amber">
      {out.length > 0 && <>Left out because they are not expected to play: {out.map((p) => `${p.player} (${p.team}, ${p.status.toLowerCase()})`).join(", ")}. Their work moves to teammates, so these projections differ from the ones saved earlier in the week.</>}
      {moves.length > 0 && <> {moves.map((m) => m.text).join(" ")}</>}
      {quest.length > 0 && <>{out.length > 0 ? " " : ""}Still listed questionable: {quest.map((p) => `${p.player} (${p.team})`).join(", ")}.</>}
    </Callout>
  );
  if (!rows.length) return <div className="space-y-4">{notice}<Callout tone="blue">No player projections are saved for this game yet.</Callout></div>;
  const shown = stats.filter((s) => stat === "All" || s === stat);
  return (
    <div className="space-y-4">
      {notice}
      <div className="space-y-2">
        <FilterRow label="Stat"><Segmented label="Stat" options={["All", ...stats]} value={stat} onChange={setStat} /></FilterRow>
        <FilterRow label="Team"><Segmented label="Team" options={["Both", d.away, d.home]} value={team} onChange={setTeam} /></FilterRow>
      </div>
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted" aria-hidden>
        <span className="inline-flex items-center gap-2"><i className="inline-block h-1.5 w-6 bg-chart" />8 in 10 range</span>
        <span className="inline-flex items-center gap-2"><i className="inline-block h-4 w-[3px] bg-white" />Projection</span>
        <span className="inline-flex items-center gap-2"><i className="inline-block h-4 w-0.5 bg-accent" />Market line</span>
      </div>
      <div className="grid items-start gap-0.5 xl:grid-cols-2">
        {shown.map((s) => (
          <Group key={s} stat={s} all={rows.filter((r) => r.stat === s)} rows={rows.filter((r) => r.stat === s && (team === "Both" || r.team === team))}
            sort={sorts[s] ?? { k: "typical", d: -1 }} away={d.away} home={d.home} team={team}
            onSort={(k) => setSorts((o) => { const c = o[s] ?? { k: "typical", d: -1 }; return { ...o, [s]: { k, d: c.k === k ? (-c.d as 1 | -1) : k === "player" ? 1 : -1 } }; })} />
        ))}
      </div>
      <p className="max-w-[75ch] text-sm text-muted">Projection is the middle estimate; the stat lands inside the range about 8 times in 10. Market line and chance come from Kalshi prices saved before the game, shown only where a market exists.</p>
    </div>
  );
}
