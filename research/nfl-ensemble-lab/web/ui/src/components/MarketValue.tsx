import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { MarketRow, TdMarket } from "../types";
import { cn, etTime, pct } from "../lib";
import { Badge, Callout, Card, Segmented } from "./ui/primitives";
import { TdCard } from "./TdCard";

const day = (iso: string) => new Date(iso).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", timeZone: "America/New_York" });
const cents = (x: number | null | undefined) => (x === null || x === undefined ? "–" : `${Math.round(x * 100)}¢`);
const pts = (x: number | null | undefined) => (x === null || x === undefined ? "–" : `${x >= 0 ? "+" : "−"}${Math.abs(x * 100).toFixed(1)}`);
const FILTERS = ["All priced", "Our number above the price", "Price above our number"] as const;

function Line({ r, open, onToggle }: { r: MarketRow; open: boolean; onToggle: () => void }) {
  const edge = r.edge_after_fee ?? null;
  const tone = r.value ? "green" : edge !== null && edge < -0.04 ? "amber" : "neutral";
  return (
    <li className="bg-panel">
      <button className="grid min-h-[68px] w-full grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1 px-4 py-2.5 text-left hover:bg-line sm:grid-cols-[1fr_5.5rem_6.5rem_6rem_14rem]"
        aria-expanded={open} onClick={onToggle}>
        <span className="min-w-0">
          <span className="block truncate text-base font-semibold text-white">{r.player}</span>
          <span className="block truncate text-sm text-muted">{r.pos ?? ""}{r.pos ? " · " : ""}{r.team} {r.home ? "vs" : "at"} {r.opp} · {etTime(r.kickoff_utc).replace(":00 ", " ")}</span>
          <span className="block text-sm text-slate-300 sm:hidden">Ours {pct(r.projection)} · Kalshi {cents(r.market?.bid)} bid, {cents(r.market?.ask)} ask</span>
        </span>
        <span className="hidden text-right sm:block"><span className="block text-xs uppercase tracking-wide text-muted">Our chance</span><span className="text-base font-semibold text-white">{pct(r.projection)}</span></span>
        <span className="hidden text-right sm:block"><span className="block text-xs uppercase tracking-wide text-muted">Kalshi bid / ask</span><span className="text-base font-semibold text-white">{cents(r.market?.bid)} / {cents(r.market?.ask)}</span></span>
        <span className="justify-self-end text-right sm:justify-self-auto"><span className="block text-xs uppercase tracking-wide text-muted">Edge</span><span className={cn("text-lg font-bold", edge === null ? "text-muted" : edge >= 0.04 ? "text-emerald-300" : edge < -0.04 ? "text-amber-300" : "text-white")}>{pts(edge)}</span></span>
        <span className="col-span-2 sm:col-span-1 sm:justify-self-end"><Badge tone={tone}>{r.label}</Badge></span>
      </button>
      {open && <div className="pb-3"><TdCard gid={r.gid} team={r.team} player={r.player} /></div>}
    </li>
  );
}

export function MarketValueView({ week }: { week: number }) {
  const [data, setData] = useState<TdMarket | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("All priced");
  const [dayKey, setDayKey] = useState("All days");
  const [openKey, setOpenKey] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setData(null);
    setError(null);
    api.tdmarket(week).then((x) => { if (alive) setData(x); }).catch((e) => { if (alive) setError(String(e)); });
    return () => { alive = false; };
  }, [week]);

  const days = useMemo(() => {
    const seen: string[] = [];
    [...(data?.rows ?? [])].sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc)).forEach((r) => { const d = day(r.kickoff_utc); if (!seen.includes(d)) seen.push(d); });
    return seen;
  }, [data]);

  if (error) return <Callout tone="amber">Could not read the Kalshi prices ({error}). The rest of the app still works.</Callout>;
  if (!data) return <div className="text-muted">Reading Kalshi's anytime-touchdown prices and pricing every player in week {week}… about 15 seconds the first time.</div>;
  let rows = data.rows.filter((r) => dayKey === "All days" || day(r.kickoff_utc) === dayKey);
  if (filter === "Our number above the price") rows = rows.filter((r) => (r.edge_after_fee ?? 0) > 0);
  if (filter === "Price above our number") rows = rows.filter((r) => (r.edge_after_fee ?? 0) < 0).reverse();
  const value = data.rows.filter((r) => r.value).length;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-white">Market value, week {week}</h2>
        <p className="mt-1 max-w-3xl text-[15px] text-muted">Our chance that a player scores a touchdown, next to what Kalshi charges for "1+ touchdowns". The edge is our chance minus the ask minus Kalshi's fee, in percentage points.
          Tap a player for the reasons behind our number.</p>
      </div>
      <Callout tone="amber">
        An edge here means our number is higher than the market's, not that the bet wins. Kalshi touchdown prices were never saved before this week, so none of these picks has been checked against results, and our model has not been shown to beat the market.
        Across weeks 3 to 7 our chances were close overall (we said 18%, 19% scored), but where we said 40% or more, players scored 44% of the time against our 51% (156 player-games), so the biggest edges are the least reliable.
        It also runs low on quarterbacks and goal-line backs that Kalshi prices high. This tab saves each look at the prices so the picks can be scored after the games.
      </Callout>
      <div className="flex flex-wrap items-center gap-3 text-[15px] text-slate-300">
        <span>{data.matched} of {data.players} players have a Kalshi price · {value} flagged "well above the price" (edge of {Math.round(data.value_edge * 100)} points or more after fees, and a chance of at least {Math.round(data.min_chance * 100)}%)</span>
      </div>
      <Segmented label="Filter" options={[...FILTERS]} value={filter} onChange={(f) => { setFilter(f); setOpenKey(null); }} />
      {days.length > 1 && <Segmented label="Day" options={["All days", ...days]} value={dayKey} onChange={(d) => { setDayKey(d); setOpenKey(null); }} />}
      {rows.length === 0 ? <Callout tone="blue">Nothing matches that filter.</Callout> : (
        <ol className="space-y-0.5">
          {rows.map((r) => { const k = `${r.gid}-${r.player}`; return <Line key={k} r={r} open={openKey === k} onToggle={() => setOpenKey(openKey === k ? null : k)} />; })}
        </ol>
      )}
      {data.unpriced.length > 0 && (
        <details className="bg-panel">
          <summary className="flex min-h-[44px] cursor-pointer items-center px-4 text-[15px] text-muted hover:text-white">{data.unpriced.length} players with a chance of 15% or more but no real Kalshi price (no market, or bid and ask too far apart)</summary>
          <div className="px-4 pb-3 text-[15px] text-slate-300">{data.unpriced.map((r) => `${r.player} (${r.team}) ${pct(r.projection)}`).join(" · ")}</div>
        </details>
      )}
      <Card className="text-sm leading-relaxed text-muted">
        <b className="text-slate-300">How to read this.</b> Kalshi sells a contract that pays $1 if the player scores. The ask is the price to buy it, so an ask of 40¢ means the market says about 40%. Kalshi's fee is about 7% of ask times (1 minus ask) per contract,
        and it is taken off the edge. "No real price" means the bid is missing or more than {Math.round(0.06 * 100)}¢ below the ask. Our chance comes from the team's expected points, its rushing share, and who scores for it; see the card for each player.
        Kalshi's "touchdowns" market counts any touchdown by the player, and ours counts rushing and receiving touchdowns, so a few players have a slightly different question on each side.
      </Card>
    </div>
  );
}
