import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { OuCalls } from "../types";
import { cn, pct } from "../lib";
import { Badge, Callout, FilterRow, Segmented } from "./ui/primitives";
import { Pick } from "./Leans";

type Key = "player" | "game" | "projection" | "line" | "gap" | "chance" | "strength";
const STATS = ["All stats", "Receiving yards", "Receptions", "Rushing yards", "Passing yards", "Passing TDs"];
const SIDES = ["All", "Over", "Under"];

export function OverUnderCallsView() {
  const [d, setD] = useState<OuCalls | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [stat, setStat] = useState("All stats");
  const [side, setSide] = useState("All");
  const [game, setGame] = useState("All games");
  const [sort, setSort] = useState<{ key: Key; dir: 1 | -1 }>({ key: "strength", dir: -1 });
  useEffect(() => { api.ouCalls().then(setD).catch((e) => setErr(String(e.message ?? e))); }, []);
  const rows = useMemo(() => {
    if (!d?.ok) return [];
    let x = d.rows;
    if (stat !== "All stats") x = x.filter((r) => r.stat === stat);
    if (side !== "All") x = x.filter((r) => r.call === side);
    if (game !== "All games") x = x.filter((r) => r.gid === game);
    const v = (r: (typeof x)[number]) => (sort.key === "player" ? r.player : sort.key === "game" ? r.kickoff_utc + r.gid : sort.key === "gap" ? Math.abs(r.gap) : r[sort.key]);
    return [...x].sort((a, b) => (v(a) < v(b) ? -1 : v(a) > v(b) ? 1 : 0) * sort.dir);
  }, [d, stat, side, game, sort]);
  const gameOpts = useMemo(() => {
    const seen = new Map<string, { t: string; k: string }>();
    [...(d?.rows ?? [])].sort((x, y) => x.kickoff_utc.localeCompare(y.kickoff_utc)).forEach((r) => { if (!seen.has(r.gid)) seen.set(r.gid, { t: r.gid.split("_").slice(2).join(" at "), k: r.kickoff_utc }); });
    return [...seen.entries()].map(([v, o]) => ({ v, t: o.t }));
  }, [d]);
  const onSort = (k: Key) => setSort((s) => (s.key === k ? { key: k, dir: (s.dir * -1) as 1 | -1 } : { key: k, dir: k === "player" ? 1 : -1 }));
  const Th = ({ k, label, right = true, hide = false }: { k: Key; label: string; right?: boolean; hide?: boolean }) => (
    <th scope="col" aria-sort={sort.key === k ? (sort.dir === 1 ? "ascending" : "descending") : "none"} className={cn("px-2 py-1 font-normal", right && "text-right", hide && "hidden md:table-cell")}>
      <button type="button" onClick={() => onSort(k)} className={cn("min-h-[44px] cursor-pointer text-[13px] hover:text-white", sort.key === k ? "text-white" : "text-muted")}>{label}{sort.key === k ? (sort.dir === 1 ? " ▲" : " ▼") : ""}</button>
    </th>
  );
  if (err) return <Callout tone="amber">Could not load the over and under calls: {err}</Callout>;
  if (!d) return <p className="text-muted">Loading the calls.</p>;
  if (!d.ok) return <Callout tone="blue">{d.reason}</Callout>;
  const n = rows.length, over = rows.filter((r) => r.call === "Over").length;
  return (
    <section aria-labelledby="ou-h" className="space-y-4">
      <div>
        <h2 id="ou-h" className="text-xl font-bold">Over and under calls, week {d.week}</h2>
        <p className="mt-1 max-w-3xl text-[15px] text-muted">The model's projection for each player against the consensus line. The projection learns from every game of this season so far (weeks 1 to {d.through_week}) and the 2016 to 2025 seasons, using every data source in the lab including the FantasyPoints tables; week {d.through_week} is only the latest week added. Over means the projection is above the line, Under means below. Strength is the gap divided by the width of the projection's 8-in-10 range, so a large number means the call is not a close one. Every call here was made before the games.</p>
      </div>
      <Callout tone="blue">{d.status} Earlier weeks' calls are scored on the Results tab.</Callout>
      <div className="space-y-2">
        <FilterRow label="Stat"><Segmented label="Stat" options={STATS} value={stat} onChange={setStat} /></FilterRow>
        <FilterRow label="Call"><Segmented label="Call" options={SIDES} value={side} onChange={setSide} /></FilterRow>
        <div className="max-w-md"><Pick label="Game" value={game} onChange={setGame} options={[{ v: "All games", t: "All games" }, ...gameOpts]} /></div>
      </div>
      <p className="text-[15px] text-slate-300">{n} calls: {over} over, {n - over} under.</p>
      <div className="overflow-x-auto bg-panel p-2 sm:p-4">
        <table className="w-full min-w-[640px] text-left text-[15px]" aria-label="Over and under calls">
          <thead><tr className="border-b border-bg">
            <Th k="player" label="Player" right={false} /><Th k="game" label="Game" right={false} hide /><Th k="projection" label="Projection" /><Th k="line" label="Line" /><Th k="gap" label="Gap" hide />
            <th scope="col" className="hidden px-2 py-1 text-right text-[13px] font-normal text-muted md:table-cell">8-in-10 range</th>
            <Th k="chance" label="Model chance" /><Th k="strength" label="Strength" /><th scope="col" className="px-2 py-1 text-right text-[13px] font-normal text-muted">Call</th>
          </tr></thead>
          <tbody>{rows.length ? rows.map((r) => {
            const dec = r.stat === "Receptions" || r.stat === "Passing TDs" ? 1 : 0;
            return (
              <tr key={`${r.gid}${r.player}${r.stat}`} className="border-t border-bg">
                <td className="px-2 py-2">{r.player} <span className="text-[13px] text-muted">{r.team} vs {r.opp}</span><span className="block text-[13px] text-muted">{r.stat}</span></td>
                <td className="hidden px-2 text-muted md:table-cell">{r.gid.split("_").slice(2).join(" at ")}</td>
                <td className="px-2 text-right">{r.projection.toFixed(dec)}</td>
                <td className="px-2 text-right text-muted">{r.line.toFixed(1)}</td>
                <td className="hidden px-2 text-right text-muted md:table-cell">{r.gap >= 0 ? "+" : "−"}{Math.abs(r.gap).toFixed(dec)}</td>
                <td className="hidden px-2 text-right text-muted md:table-cell">{r.low.toFixed(dec)} to {r.high.toFixed(dec)}</td>
                <td className="px-2 text-right">{pct(r.chance, 0)}</td>
                <td className="px-2 text-right text-muted">{r.strength.toFixed(2)}</td>
                <td className="px-2 text-right"><Badge tone={r.call === "Over" ? "green" : "amber"}>{r.call}</Badge></td>
              </tr>
            );
          }) : <tr><td colSpan={9} className="py-4 text-sm text-muted">No calls match these filters.</td></tr>}</tbody>
        </table>
      </div>
      <p className="max-w-3xl text-[13px] text-muted">Touchdown props are not listed because their saved lines are prices, not numbers. This list is a record of the model's calls, not advice and not a staking plan.</p>
    </section>
  );
}
