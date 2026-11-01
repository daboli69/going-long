import { useEffect, useState, type CSSProperties } from "react";
import { api } from "../api";
import type { Detail, GlossaryItem, Meta } from "../types";
import { compactStamp, num, pct } from "../lib";
import { Badge, Card } from "./ui/primitives";

// ------------------------------------------------------------------ Teams and injuries
export function Matchup({ d }: { d: Detail }) {
  const teams = [
    { abbr: d.away, name: d.away_name, color: d.away_color },
    { abbr: d.home, name: d.home_name, color: d.home_color },
  ];
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-0.5 md:grid-cols-2">
        {teams.map((t) => {
          const s = d.matchup[t.abbr];
          const inj = d.injuries?.teams[t.abbr] ?? [];
          return (
            <Card key={t.abbr} className="p-0">
              <div className="team-field flex items-baseline justify-between px-5 py-3 text-white" style={{ "--team": t.color } as CSSProperties}>
                <h2 className="text-xl font-bold">{t.name}</h2>
                <div className="text-base">{s.record}</div>
              </div>
              <div className="px-5 pb-5 pt-3">
              {s.games > 0 && (
                <div className="text-base text-slate-300">
                  Scores {num(s.pf)} and allows {num(s.pa)} points a game.
                </div>
              )}
              <h3 className="mt-4 text-[15px] text-muted">Recent games</h3>
              {s.last.length ? s.last.map((x) => <div key={x} className="border-b border-line py-1.5 text-base last:border-0">{x}</div>) : <div className="text-base text-muted">No games played yet.</div>}
              <h3 className="mt-4 text-[15px] text-muted">Injury report</h3>
              {inj.length === 0 && <div className="text-base text-muted">{d.injuries?.stamp ? "No players listed." : "No injury report saved."}</div>}
              {inj.map((r) => (
                <div key={r.player} className="flex items-start justify-between gap-3 border-b border-line py-2 last:border-0">
                  <div>
                    <div className="text-base"><b>{r.player}</b> <span className="text-muted">{r.pos}</span></div>
                    {r.note && <div className="text-sm leading-snug text-muted">{r.note}</div>}
                  </div>
                  <Badge tone={r.tone} title={r.meaning}>{r.status}</Badge>
                </div>
              ))}
              </div>
            </Card>
          );
        })}
      </div>
      {d.injuries?.stamp && (
        <p className="text-sm text-muted">
          ESPN injury list, checked {compactStamp(d.injuries.stamp)}. Out and Doubtful players are left out of the player projections, here and on the Players tab.
        </p>
      )}
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
    <div className="grid grid-cols-1 gap-0.5 lg:grid-cols-2">
      <Card>
        <h3 className="text-lg font-semibold text-white">Where the numbers come from</h3>
        <p className="mt-1 text-base leading-relaxed text-slate-300">{meta.reality_check}</p>
        <h3 className="mt-5 text-lg font-semibold text-white">Track record</h3>
        {record.map(([label, value]) => (
          <div key={label} className="border-b border-line py-2 last:border-0">
            <div className="text-sm text-muted">{label}</div>
            <div className="text-base text-white">{value}</div>
          </div>
        ))}
      </Card>
      <Card>
        <h3 className="mb-1 text-lg font-semibold text-white">Terms</h3>
        {items.map((g) => (
          <details key={g.term} className="border-b border-line last:border-0">
            <summary className="flex min-h-[44px] items-center text-base text-white hover:text-accent">{g.term}</summary>
            <p className="pb-3 text-base leading-relaxed text-slate-300">{g.text}</p>
          </details>
        ))}
      </Card>
    </div>
  );
}
