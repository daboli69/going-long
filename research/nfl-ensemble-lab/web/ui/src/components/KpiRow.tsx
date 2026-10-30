import type { Meta } from "../types";
import { num, pct } from "../lib";
import { Card } from "./ui/primitives";

function Kpi({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <Card className="flex flex-col gap-1">
      <div className="text-sm text-muted">{label}</div>
      <div className="text-3xl font-bold leading-tight text-white">{value}</div>
      <div className="text-xs leading-snug text-muted">{sub}</div>
    </Card>
  );
}

export function KpiRow({ meta, gamesThisWeek, nextKickoff }: { meta: Meta; gamesThisWeek: number; nextKickoff: string | null }) {
  const k = meta.kpis;
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {k.market_acc && (
        <Kpi
          label="Game winners picked correctly"
          value={pct(k.market_acc.accuracy)}
          sub={`The betting market, 2025-26 (${k.market_acc.games} games). Simple Elo ratings: ${pct(k.market_acc.elo_accuracy_same_games)} on the same games.`}
        />
      )}
      {k.margin_miss && (
        <Kpi
          label="Typical miss on the final margin"
          value={`${num(k.margin_miss.market)} pts`}
          sub={`Betting market. Our model misses by ${num(k.margin_miss.model)} pts (2026, ${k.margin_miss.games} games). Lower is better.`}
        />
      )}
      {k.range_hit && (
        <Kpi
          label="Player ranges that held"
          value={pct(k.range_hit.liquid ?? k.range_hit.thin)}
          sub={'We say a player\u2019s stat lands in our "likely range" 8 times in 10. In past tests it did.'}
        />
      )}
      <Kpi label="Games this week" value={String(gamesThisWeek)} sub={nextKickoff ? `Next kickoff: ${nextKickoff}` : "All games this week are finished."} />
    </div>
  );
}
