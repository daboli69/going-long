import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { FirstTdAllowed, FirstTdRow } from "../types";
import { Callout } from "./ui/primitives";
import { Pick } from "./Leans";

const pct = (x: number | null) => (x === null ? "n/a" : `${(x * 100).toFixed(0)}%`);

export function FirstTdAllowedView() {
  const [season, setSeason] = useState("2026");
  const [weeks, setWeeks] = useState<number[]>([]);
  const [overall, setOverall] = useState(false);
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 }>({ key: "team", dir: 1 });
  const [d, setD] = useState<FirstTdAllowed | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setErr(null);
    api.firstTdAllowed(new URLSearchParams({ season, weeks: weeks.join(","), overall: String(overall) }).toString()).then(setD).catch((e) => setErr(String(e.message ?? e)));
  }, [season, weeks, overall]);

  const rows = useMemo(() => {
    if (!d) return [];
    const val = (r: FirstTdRow) => (sort.key === "team" ? r.team : sort.key === "tds" ? r.tds : r.pct[sort.key] ?? -1);
    return [...d.rows].sort((a, b) => { const x = val(a), y = val(b); return (x < y ? -1 : x > y ? 1 : a.team.localeCompare(b.team)) * sort.dir; });
  }, [d, sort]);

  // Per column, the lowest share is red and the highest is green, so a green cell is where that defense gives up the most to that position.
  const range = useMemo(() => {
    const out: Record<string, [number, number]> = {};
    for (const p of d?.positions ?? []) {
      const v = (d?.rows ?? []).map((r) => r.pct[p]).filter((x): x is number => x !== null);
      out[p] = v.length ? [Math.min(...v), Math.max(...v)] : [0, 0];
    }
    return out;
  }, [d]);
  const tint = (p: string, x: number | null) => {
    const [lo, hi] = range[p] ?? [0, 0];
    if (x === null || hi === lo) return undefined;
    return { backgroundColor: `hsl(${Math.round(((x - lo) / (hi - lo)) * 125)} 55% 28%)` };
  };

  const toggle = (w: number) => setWeeks((cur) => (cur.includes(w) ? cur.filter((x) => x !== w) : [...cur, w].sort((a, b) => a - b)));
  const head = (key: string, label: string, right = true) => (
    <th scope="col" className={right ? "text-right" : ""} aria-sort={sort.key === key ? (sort.dir === 1 ? "ascending" : "descending") : "none"}>
      <button type="button" className="min-h-[44px] cursor-pointer px-2 text-[13px] text-muted hover:text-white" onClick={() => setSort((s) => (s.key === key ? { key, dir: (s.dir * -1) as 1 | -1 } : { key, dir: key === "team" ? 1 : -1 }))}>
        {label}{sort.key === key ? (sort.dir === 1 ? " ↑" : " ↓") : ""}
      </button>
    </th>
  );
  const cell = (r: { counts: Record<string, number>; pct: Record<string, number | null> }, p: string) => `${pct(r.pct[p])} (${r.counts[p]})`;
  const chosen = d ? (d.weeks.length === d.weeks_available.length && weeks.length === 0 ? "all weeks" : `week${d.weeks.length > 1 ? "s" : ""} ${d.weeks.join(", ")}`) : "";

  return (
    <section aria-labelledby="ftd-h" className="space-y-5">
      <div>
        <h2 id="ftd-h" className="text-xl font-bold">First touchdown allowed, by position</h2>
        <p className="mt-1 max-w-3xl text-[15px] text-muted">For each defense, who scored the first touchdown against it in each game: the share by position and, in brackets, the number of touchdowns. These are counts from games already played, not predictions. Click a column to sort. Pick any weeks and the table recalculates.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-4">
        <Pick label="Season" value={season} onChange={(v) => { setSeason(v); setWeeks([]); }} options={(d?.seasons ?? [2026]).slice().reverse().map((s) => ({ v: String(s), t: String(s) }))} />
        <label className="flex min-h-[44px] cursor-pointer items-center gap-2 self-end text-[15px]"><input type="checkbox" className="h-5 w-5 cursor-pointer" checked={overall} onChange={(e) => setOverall(e.target.checked)} />Only the game's first touchdown</label>
      </div>
      <fieldset>
        <legend className="text-[13px] text-muted">Weeks (none selected means all)</legend>
        <div className="mt-1 flex flex-wrap gap-2">
          <button type="button" className={`min-h-[44px] cursor-pointer border px-3 text-[15px] ${weeks.length === 0 ? "border-white bg-white text-black" : "border-bg bg-[#12161c]"}`} aria-pressed={weeks.length === 0} onClick={() => setWeeks([])}>All</button>
          {(d?.weeks_available ?? []).map((w) => (
            <button key={w} type="button" className={`min-h-[44px] min-w-[44px] cursor-pointer border px-3 text-[15px] ${weeks.includes(w) ? "border-white bg-white text-black" : "border-bg bg-[#12161c]"}`} aria-pressed={weeks.includes(w)} onClick={() => toggle(w)}>{w}</button>
          ))}
        </div>
      </fieldset>
      {err && <Callout tone="amber">Could not load: {err}</Callout>}
      {!d && !err && <p className="text-muted">Loading.</p>}
      {d && (
        <>
          <p className="text-[13px] text-muted">{season}, {chosen}. {overall ? "Each game counts once: its first touchdown, charged to the defense that gave it up." : "Each defense's first touchdown given up in each game, so a game can count for both teams."} Percentages use the touchdowns shown, not games played; a defense that shut an offense out adds nothing. Def/ST means a return or defensive score; Other is any non-QB, RB, WR or TE scorer.</p>
          <p className="flex items-center gap-2 text-[13px] text-muted"><span>Colors compare teams within each column:</span><span className="inline-block px-2 text-white" style={{ backgroundColor: "hsl(0 55% 28%)" }}>lowest share</span><span className="inline-block px-2 text-white" style={{ backgroundColor: "hsl(125 55% 28%)" }}>highest share</span></p>
          <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-[15px]">
            <thead><tr>{head("team", "Defense", false)}<th scope="col" className="text-right text-[13px] text-muted">Games</th>{head("tds", "TDs")}{d.positions.map((p) => head(p, p))}</tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.team} className="border-t border-bg"><th scope="row" className="py-1 text-left font-medium">{r.team}</th><td className="text-right">{r.games}</td><td className="text-right">{r.tds}</td>{d.positions.map((p) => <td key={p} className="px-2 text-right" style={tint(p, r.pct[p])}>{cell(r, p)}</td>)}</tr>
              ))}
              <tr className="border-t-2 border-bg font-bold"><th scope="row" className="py-1 text-left">League</th><td className="text-right">{d.league.games}</td><td className="text-right">{d.league.tds}</td>{d.positions.map((p) => <td key={p} className="text-right">{cell(d.league, p)}</td>)}</tr>
            </tbody>
          </table></div>
          <p className="text-[13px] text-muted">Small samples swing hard: with a few games, one touchdown moves a share by 10 points or more. Use more weeks, or last season, before reading a pattern into a team.</p>
        </>
      )}
    </section>
  );
}
