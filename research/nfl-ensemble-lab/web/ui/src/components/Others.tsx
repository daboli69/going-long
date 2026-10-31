import { flexRender, getCoreRowModel, getSortedRowModel, useReactTable, type ColumnDef, type SortingState } from "@tanstack/react-table";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Detail, GlossaryItem, Meta, PropRow } from "../types";
import { compactStamp, num, pct } from "../lib";
import { Badge, Callout, Card, Segmented } from "./ui/primitives";

// ------------------------------------------------------------------ Teams and injuries
export function Matchup({ d }: { d: Detail }) {
  const teams = [
    { abbr: d.away, name: d.away_name },
    { abbr: d.home, name: d.home_name },
  ];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {teams.map((t) => {
          const s = d.matchup[t.abbr];
          const inj = d.injuries?.teams[t.abbr] ?? [];
          return (
            <Card key={t.abbr}>
              <div className="flex items-baseline justify-between">
                <div className="text-lg font-bold text-white">{t.name}</div>
                <div className="text-sm text-muted">{s.record}</div>
              </div>
              {s.games > 0 && (
                <div className="mt-1 text-sm text-slate-300">
                  Scores {num(s.pf)} and allows {num(s.pa)} points a game.
                </div>
              )}
              <div className="mt-4 text-xs text-muted">Recent games</div>
              {s.last.length ? s.last.map((x) => <div key={x} className="border-b border-line py-1 text-sm last:border-0">{x}</div>) : <div className="text-sm text-muted">No games played yet.</div>}
              <div className="mt-4 text-xs text-muted">Injury report</div>
              {inj.length === 0 && <div className="text-sm text-muted">{d.injuries?.stamp ? "No players listed." : "No injury report saved."}</div>}
              {inj.map((r) => (
                <div key={r.player} className="flex items-start justify-between gap-3 border-b border-line py-2 last:border-0">
                  <div>
                    <div className="text-sm"><b>{r.player}</b> <span className="text-muted">{r.pos}</span></div>
                    {r.note && <div className="text-xs leading-snug text-muted">{r.note}</div>}
                  </div>
                  <Badge tone={r.tone} title={r.meaning}>{r.status}</Badge>
                </div>
              ))}
            </Card>
          );
        })}
      </div>
      {d.injuries?.stamp && (
        <p className="text-xs text-muted">
          ESPN injury list, checked {compactStamp(d.injuries.stamp)}. Out and Doubtful players are left out of player projections.
        </p>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ Players
const cols: ColumnDef<PropRow>[] = [
  { header: "Player", accessorKey: "player", cell: (c) => <span><b>{c.getValue<string>()}</b> <span className="text-muted">{c.row.original.team}</span></span> },
  { header: "Stat", accessorKey: "stat" },
  { header: "Projection", accessorKey: "typical", cell: (c) => num(c.getValue<number>(), c.row.original.stat === "Receptions" ? 1 : 0) },
  { header: "8 in 10 range", id: "range", accessorFn: (r) => r.range_low ?? 0, cell: (c) => `${num(c.row.original.range_low, 0)} to ${num(c.row.original.range_high, 0)}` },
  { header: "Market line", accessorKey: "market_line", cell: (c) => (c.getValue<number | null>() === null ? "" : `${c.getValue<number>()}+`) },
  { header: "Market chance", accessorKey: "market_chance", cell: (c) => (c.getValue<number | null>() === null ? "" : pct(c.getValue<number>())) },
];

export function Props({ d }: { d: Detail }) {
  const rows = d.props ?? [];
  const stats = ["All", ...Array.from(new Set(rows.map((r) => r.stat))).sort()];
  const [stat, setStat] = useState("All");
  const [team, setTeam] = useState("Both");
  const [sorting, setSorting] = useState<SortingState>([{ id: "typical", desc: true }]);
  useEffect(() => { setStat("All"); setTeam("Both"); }, [d.gid]);
  const data = useMemo(() => rows.filter((r) => (stat === "All" || r.stat === stat) && (team === "Both" || r.team === team)), [rows, stat, team]);
  const table = useReactTable({ data, columns: cols, state: { sorting }, onSortingChange: setSorting, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel() });
  if (!rows.length) return <Callout tone="blue">No player projections are saved for this game yet.</Callout>;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-x-8 gap-y-2">
        <Segmented label="Stat" options={stats} value={stat} onChange={setStat} />
        <Segmented label="Team" options={["Both", d.away, d.home]} value={team} onChange={setTeam} />
      </div>
      <Card className="overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} className="border-b border-line text-left text-xs text-muted">
                {hg.headers.map((h) => (
                  <th key={h.id} className="cursor-pointer select-none whitespace-nowrap px-4 py-3 font-medium hover:text-white" onClick={h.column.getToggleSortingHandler()}>
                    {flexRender(h.column.columnDef.header, h.getContext())}
                    {{ asc: " ▲", desc: " ▼" }[h.column.getIsSorted() as string] ?? ""}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((r) => (
              <tr key={r.id} className="border-b border-line last:border-0 hover:bg-panel2">
                {r.getVisibleCells().map((c) => (
                  <td key={c.id} className="whitespace-nowrap px-4 py-2.5">{flexRender(c.column.columnDef.cell, c.getContext())}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <p className="text-xs text-muted">
        Projection is the middle estimate; the stat lands inside the range about 8 times in 10. Market line and chance come from Kalshi prices saved before the game,
        shown only where a market exists.
      </p>
    </div>
  );
}

// ------------------------------------------------------------------ About these numbers
export function About({ meta }: { meta: Meta }) {
  const [items, setItems] = useState<GlossaryItem[]>([]);
  useEffect(() => { api.glossary().then(setItems).catch(() => setItems([])); }, []);
  const k = meta.kpis;
  const record: [string, string][] = [];
  if (k.market_acc) record.push(["Winners picked correctly, 2025-26", `Market ${pct(k.market_acc.accuracy)}, Elo ${pct(k.market_acc.elo_accuracy_same_games)} (${k.market_acc.games} games)`]);
  if (k.margin_miss) record.push(["Average miss on the final margin, 2026", `Market ${num(k.margin_miss.market)} pts, our model ${num(k.margin_miss.model)} pts (${k.margin_miss.games} games)`]);
  const hit = k.range_hit?.liquid ?? k.range_hit?.thin;
  if (hit !== undefined) record.push(["Player stats inside the 8 in 10 range", `${pct(hit)} in past tests (target 80%)`]);
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Card>
        <h3 className="font-semibold text-white">Where the numbers come from</h3>
        <p className="mt-1 text-sm text-slate-300">{meta.reality_check}</p>
        <h3 className="mt-4 font-semibold text-white">Track record</h3>
        {record.map(([label, value]) => (
          <div key={label} className="border-b border-line py-2 last:border-0">
            <div className="text-xs text-muted">{label}</div>
            <div className="text-sm text-white">{value}</div>
          </div>
        ))}
      </Card>
      <Card>
        <h3 className="mb-1 font-semibold text-white">Terms</h3>
        {items.map((g) => (
          <details key={g.term} className="border-b border-line py-2 last:border-0">
            <summary className="cursor-pointer text-sm text-white">{g.term}</summary>
            <p className="mt-1 text-sm text-slate-300">{g.text}</p>
          </details>
        ))}
      </Card>
    </div>
  );
}
