import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { MarketRow, TdMarket } from "../types";
import { cn, etTime, pct } from "../lib";
import { Callout, FilterRow, Segmented } from "./ui/primitives";
import { TdCard } from "./TdCard";

const day = (iso: string) => new Date(iso).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", timeZone: "America/New_York" });
const cents = (x: number | null | undefined) => (x === null || x === undefined ? "none" : String(Math.round(x * 100)));
const FILTERS = ["All priced", "Our number above the price", "Price above our number"] as const;
const PAGE = 15, LIM = 0.3;
const at = (v: number) => 50 + (Math.max(-LIM, Math.min(LIM, v)) / LIM) * 50;

// Edge after fees as a bar from a zero line; the sign and number are printed, so colour is not needed.
function Edge({ edge }: { edge: number | null }) {
  if (edge === null) return <span className="text-sm text-muted">No edge</span>;
  const pos = edge >= 0, p = at(edge), pts = Math.abs(edge * 100).toFixed(1);
  return (
    <span className="relative block h-7 before:absolute before:left-1/2 before:top-0 before:h-7 before:w-px before:bg-chart before:content-['']" role="img" aria-label={`Edge ${pos ? "plus" : "minus"} ${pts} points`}>
      <span className="absolute top-2 h-3" style={{ left: `${pos ? 50 : p}%`, width: `${Math.abs(p - 50)}%`, background: pos ? "#f2f2f0" : "#8b9097" }} />
      <span className="absolute top-0.5 whitespace-nowrap text-sm font-bold" style={pos ? { left: `calc(${p}% + 6px)` } : { right: `calc(${100 - p}% + 6px)` }}>{pos ? "+" : "−"}{pts}</span>
    </span>
  );
}

function Line({ r, open, onToggle }: { r: MarketRow; open: boolean; onToggle: () => void }) {
  return (
    <li className="bg-panel">
      <button type="button" aria-expanded={open} onClick={onToggle}
        className="grid min-h-[64px] w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 px-4 py-2 text-left transition-colors hover:bg-raised focus-visible:outline-offset-[-3px] sm:grid-cols-[minmax(0,1.4fr)_4.5rem_6rem_minmax(0,1fr)] xl:grid-cols-[minmax(0,1.4fr)_5rem_7rem_minmax(0,1fr)_16rem] max-sm:pb-3">
        <span className="min-w-0">
          <b className="block truncate text-base">{r.player}</b>
          <span className="block truncate text-sm text-muted">{r.pos}, {r.team} {r.home ? "vs" : "at"} {r.opp}, {etTime(r.kickoff_utc).replace(":00 ", " ")}</span>
        </span>
        <span className="text-right text-lg font-bold max-sm:col-start-2 max-sm:row-start-1" aria-label={`Our chance ${pct(r.projection)}`}>{pct(r.projection)}</span>
        <span className="col-span-2 text-sm text-muted sm:col-span-1 sm:text-right sm:text-base sm:text-white">{cents(r.market?.bid)} / {cents(r.market?.ask)} cents</span>
        <span className="col-span-2 sm:col-span-1"><Edge edge={r.edge_after_fee ?? null} /></span>
        <span className={cn("hidden text-sm xl:block", r.value ? "font-semibold text-white" : "text-muted")}>{r.label}</span>
      </button>
      {open && <div className="bg-panel2 px-4 pb-4 pt-3 sm:mx-4 sm:mb-4"><TdCard gid={r.gid} team={r.team} player={r.player} /></div>}
    </li>
  );
}

export function MarketValueView({ week }: { week: number }) {
  const [data, setData] = useState<TdMarket | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("All priced");
  const [dayKey, setDayKey] = useState("All days");
  const [openKey, setOpenKey] = useState<string | null>(null);
  const [shown, setShown] = useState(PAGE);

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
  if (!data) return <p className="text-muted" role="status">Reading Kalshi's anytime-touchdown prices and pricing every player in week {week}… about 15 seconds the first time.</p>;
  let rows = data.rows.filter((r) => dayKey === "All days" || day(r.kickoff_utc) === dayKey);
  if (filter === "Our number above the price") rows = rows.filter((r) => (r.edge_after_fee ?? 0) > 0);
  if (filter === "Price above our number") rows = rows.filter((r) => (r.edge_after_fee ?? 0) < 0).reverse();
  const flagged = data.rows.filter((r) => r.value).length;
  const reset = () => { setOpenKey(null); setShown(PAGE); };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h1 className="text-[22px] font-bold leading-tight text-white sm:text-2xl">Market value, week {week}</h1>
        <p className="text-accent">{data.matched} of {data.players} players have a Kalshi price; {flagged} sit well above it.</p>
      </div>
      <div className="max-w-[90ch] bg-panel px-4 py-3 text-[15px] leading-relaxed sm:px-6">
        <b>An edge means our number is higher than the market's, not that the bet wins.</b> Kalshi touchdown prices were not saved before this week, so no pick here has been checked against results, and our model has not been shown to beat the market.
        Across weeks 3 to 7 our chances were close overall (we said 18%, 19% scored), but where we said 40% or more, players scored 44% of the time against our 51% (156 player-games), so the biggest edges are the least reliable.
        It also runs low on quarterbacks and goal-line backs that Kalshi prices high. This tab saves each look at the prices so the picks can be scored after the games.
      </div>
      <p className="max-w-[90ch] text-sm text-muted">The edge is our chance minus the ask minus Kalshi's fee, in percentage points. "Well above the price" means an edge of {Math.round(data.value_edge * 100)} points or more after fees and a chance of at least {Math.round(data.min_chance * 100)}%. Tap a player for the reasons behind our number.</p>
      <div className="space-y-2">
        <FilterRow label="Show"><Segmented label="Filter" options={[...FILTERS]} value={filter} onChange={(f) => { setFilter(f); reset(); }} /></FilterRow>
        {days.length > 1 && <FilterRow label="Day"><Segmented label="Day" options={["All days", ...days]} value={dayKey} onChange={(d) => { setDayKey(d); reset(); }} /></FilterRow>}
      </div>
      {rows.length === 0 ? <Callout tone="blue">Nothing matches that filter.</Callout> : (
        <div>
          <div className="hidden grid-cols-[minmax(0,1.4fr)_4.5rem_6rem_minmax(0,1fr)] gap-x-3 px-4 pb-2 text-[13px] text-muted sm:grid xl:grid-cols-[minmax(0,1.4fr)_5rem_7rem_minmax(0,1fr)_16rem]" aria-hidden>
            <span>Player</span><span className="text-right">Our chance</span><span className="text-right">Kalshi bid / ask</span><span>Edge after fees, in points</span><span className="hidden xl:block">Reading</span>
          </div>
          <ol className="space-y-0.5">
            {rows.slice(0, shown).map((r) => { const k = `${r.gid}-${r.player}`; return <Line key={k} r={r} open={openKey === k} onToggle={() => setOpenKey(openKey === k ? null : k)} />; })}
          </ol>
          {rows.length > shown && <button type="button" className="mt-0.5 min-h-[48px] w-full bg-panel text-[15px] hover:bg-raised" onClick={() => setShown((n) => n + PAGE)}>Show {Math.min(PAGE, rows.length - shown)} more of {rows.length - shown} left</button>}
        </div>
      )}
      {data.unpriced.length > 0 && (
        <details className="bg-panel">
          <summary className="flex min-h-[44px] cursor-pointer items-center px-4 text-[15px] text-muted hover:text-white">{data.unpriced.length} players with a chance of 15% or more but no real Kalshi price (no market, or bid and ask too far apart)</summary>
          <p className="px-4 pb-3 text-[15px] text-slate-300">{data.unpriced.map((r) => `${r.player} (${r.team}) ${pct(r.projection)}`).join("; ")}</p>
        </details>
      )}
      <details className="bg-panel">
        <summary className="flex min-h-[48px] cursor-pointer items-center px-4 text-[15px]">How to read this</summary>
        <div className="grid max-w-[80ch] gap-2 px-4 pb-4 text-sm text-muted">
          <p>Kalshi sells a contract that pays $1 if the player scores. The ask is the price to buy it, so an ask of 40 cents means the market says about 40%.</p>
          <p>Kalshi's fee is about 7% of ask times (1 minus ask) per contract, and it is taken off the edge. "No real price" means the bid is missing or more than {Math.round(0.06 * 100)} cents below the ask.</p>
          <p>Our chance comes from the team's expected points, its rushing share, and who scores for it; see the card for each player. Kalshi's "touchdowns" market counts any touchdown by the player, and ours counts rushing and receiving touchdowns, so a few players have a slightly different question on each side.</p>
        </div>
      </details>
    </div>
  );
}
