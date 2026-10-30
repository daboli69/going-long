import { flexRender, getCoreRowModel, getSortedRowModel, useReactTable, type ColumnDef, type SortingState } from "@tanstack/react-table";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Detail, GlossaryItem, PropRow } from "../types";
import { compactStamp, num, pct } from "../lib";
import { Badge, Callout, Card, Segmented } from "./ui/primitives";
import { TeamChip } from "./TeamChip";

// ------------------------------------------------------------------ Team matchup and injuries
export function Matchup({ d }: { d: Detail }) {
  const teams = [
    { abbr: d.away, name: d.away_name, color: d.away_color },
    { abbr: d.home, name: d.home_name, color: d.home_color },
  ];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {teams.map((t) => {
          const s = d.matchup[t.abbr];
          return (
            <Card key={t.abbr}>
              <div className="flex items-center gap-3">
                <TeamChip abbr={t.abbr} color={t.color} />
                <div>
                  <div className="text-lg font-extrabold text-white">{t.name}</div>
                  <div className="text-sm text-muted">{s.record} this season</div>
                </div>
              </div>
              <p className="mt-3 text-sm text-slate-300">
                Scores <b>{num(s.pf)}</b> points per game and allows <b>{num(s.pa)}</b> (over {s.games} games).
              </p>
              <div className="mt-3 text-sm font-bold text-white">Last 5 games, newest first</div>
              {s.last.length ? s.last.map((x) => <div key={x} className="border-b border-line py-1 text-sm last:border-0">{x}</div>) : <div className="text-sm text-muted">No games played yet.</div>}
            </Card>
          );
        })}
      </div>
      <div>
        <div className="mb-1 text-lg font-bold text-white">Who is hurt?</div>
        {d.injuries?.stamp ? (
          <p className="mb-3 text-xs text-muted">
            From ESPN&apos;s injury list (checked {compactStamp(d.injuries.stamp)}). Players listed Out or Doubtful are removed from our player projections; Questionable players are kept.
          </p>
        ) : (
          <Callout tone="blue">No injury information saved yet.</Callout>
        )}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {teams.map((t) => (
            <Card key={t.abbr}>
              <div className="mb-2 font-bold text-white">{t.name}</div>
              {(d.injuries?.teams[t.abbr] ?? []).length === 0 && <div className="text-sm text-muted">No notable injuries listed.</div>}
              {(d.injuries?.teams[t.abbr] ?? []).map((r) => (
                <div key={r.player} className="flex items-start justify-between gap-3 border-b border-line py-2 last:border-0">
                  <div>
                    <div className="text-sm">
                      <b>{r.player}</b> <span className="text-muted">{r.pos}</span>
                    </div>
                    <div className="text-xs leading-snug text-muted">{r.note}</div>
                  </div>
                  <Badge tone={r.tone} title={r.meaning}>
                    {r.status}
                  </Badge>
                </div>
              ))}
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ Player props
const cols: ColumnDef<PropRow>[] = [
  { header: "Player", accessorKey: "player", cell: (c) => <span><b>{c.getValue<string>()}</b> <span className="text-muted">{c.row.original.team}</span></span> },
  { header: "Stat", accessorKey: "stat" },
  { header: "Typical projection", accessorKey: "typical", cell: (c) => num(c.getValue<number>(), c.row.original.stat === "Receptions" ? 1 : 0) },
  { header: "Likely range (8 in 10)", id: "range", accessorFn: (r) => r.range_low ?? 0, cell: (c) => `${num(c.row.original.range_low, 0)} to ${num(c.row.original.range_high, 0)}` },
  { header: "Market line", accessorKey: "market_line", cell: (c) => (c.getValue<number | null>() === null ? "—" : `${c.getValue<number>()}+`) },
  { header: "Market's chance", accessorKey: "market_chance", cell: (c) => pct(c.getValue<number | null>()) },
  { header: "Our chance", accessorKey: "our_chance", cell: (c) => pct(c.getValue<number | null>()) },
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
  if (!rows.length) return <Callout tone="blue">No player projections have been saved for this game yet.</Callout>;
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted">
        Each row is one player and one kind of stat. &quot;Typical projection&quot; is our middle estimate; &quot;likely range&quot; is where we expect it to land 8 times in 10. Where a betting market
        exists we show its line and both chances of reaching it. Click a column to sort.
      </p>
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
                  <th key={h.id} className="cursor-pointer select-none px-4 py-3 font-medium hover:text-white" onClick={h.column.getToggleSortingHandler()}>
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
                  <td key={c.id} className="px-4 py-2.5">{flexRender(c.column.columnDef.cell, c.getContext())}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <p className="text-xs text-muted">A dash means there is no active betting market for that player. Players reported Out or Doubtful are not included. Market chances come from Kalshi prices saved before the game.</p>
    </div>
  );
}

// ------------------------------------------------------------------ Spread & total
function LadderTable({ title, rows }: { title: string; rows: { question: string; market: number; model: number }[] }) {
  return (
    <Card>
      <div className="mb-2 text-base font-bold text-white">{title}</div>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs text-muted">
            <th className="py-2 font-medium">Question</th>
            <th className="py-2 font-medium">Market says</th>
            <th className="py-2 font-medium">Our model says</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.question} className="border-b border-line last:border-0">
              <td className="py-2">{r.question}</td>
              <td className="py-2 font-semibold text-white">{pct(r.market)}</td>
              <td className="py-2">{pct(r.model)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

export function SpreadTotal({ d }: { d: Detail }) {
  const m = d.ladders?.margin ?? [];
  const t = d.ladders?.total ?? [];
  if (!m.length && !t.length) return <Callout tone="blue">No market ladder was saved for this game, so there is nothing to compare yet.</Callout>;
  return (
    <div className="space-y-4">
      <Callout tone="blue">
        <b>How to read this.</b> Each row asks a yes/no question about the final score. The market column is what betting-market prices imply; our model column is our own estimate. Big gaps are rare, and when they appear the market has usually been right.
      </Callout>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {m.length > 0 && <LadderTable title="The spread: who wins and by how much" rows={m} />}
        {t.length > 0 && <LadderTable title="The total: how many points in the game" rows={t} />}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ Guide
export function Guide({ reality }: { reality: string }) {
  const [items, setItems] = useState<GlossaryItem[]>([]);
  useEffect(() => { api.glossary().then(setItems).catch(() => setItems([])); }, []);
  return (
    <div className="space-y-4">
      <Card>
        <h3 className="text-lg font-bold text-white">What is this page?</h3>
        <p className="mt-1 text-sm text-slate-300">
          Game Center shows, for every NFL game this week: who is likely to win, by how many points, how many points will be scored, and what individual players might do. Everything comes from data saved on this computer.
        </p>
        <h3 className="mt-4 text-lg font-bold text-white">How much should I trust it?</h3>
        <p className="mt-1 text-sm text-slate-300">{reality} So: the market is the benchmark. Our model is a sensible second opinion, and it is most useful for players that no betting market covers.</p>
        <h3 className="mt-4 text-lg font-bold text-white">What this page does not do</h3>
        <p className="mt-1 text-sm text-slate-300">It does not give betting advice, place bets, or claim to beat the market. It never connects to a sportsbook or a trading account.</p>
      </Card>
      <Card>
        <h3 className="mb-2 text-lg font-bold text-white">Words used on this page</h3>
        {items.map((g) => (
          <details key={g.term} className="border-b border-line py-2 last:border-0">
            <summary className="cursor-pointer text-sm font-semibold text-white">{g.term}</summary>
            <p className="mt-1 text-sm text-slate-300">{g.text}</p>
          </details>
        ))}
      </Card>
    </div>
  );
}
