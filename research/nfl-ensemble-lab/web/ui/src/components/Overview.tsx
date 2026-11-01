import type { CSSProperties } from "react";
import type { Detail } from "../types";
import { cn, num, pct, splitPct } from "../lib";
import { Callout } from "./ui/primitives";
import { ForecastDots, Hist, tickEvery } from "./Charts";

// The one sentence that tells you whether the forecasts agree.
function finding(d: Detail): string | null {
  const src = d.sources ?? [];
  if (src.length < 2) return null;
  const fav = (p: number) => (p >= 0.5 ? d.home : d.away);
  const first = fav(src[0].p_home);
  const split = src.filter((s) => fav(s.p_home) !== first);
  if (split.length) return `${split.map((s) => s.name).join(" and ")} ${split.length > 1 ? "favor" : "favors"} ${fav(split[0].p_home)}; the other forecasts favor ${first}.`;
  return d.agreement ? `All ${src.length} forecasts favor ${first}, within ${Math.round(d.agreement.gap_points)} points.` : null;
}

export function GameTitle({ d }: { d: Detail }) {
  const f = d.has_forecast ? finding(d) : null;
  return (
    <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 pb-4 pt-2">
      <h1 className="text-[22px] font-bold leading-tight text-white sm:text-2xl">{d.away} at {d.home}</h1>
      {f && <p className="text-accent">{f}</p>}
    </div>
  );
}

// The scorebug: each team as a block of its own colour with its win chance; kickoff, expected score and lines in the middle.
export function Scorebug({ d }: { d: Detail }) {
  const h = d.has_forecast ? d.headline : null;
  const e = d.has_forecast ? d.expected : undefined;
  const [awayP, homeP] = h ? splitPct(h.p_home) : [null, null];
  const fav = e?.margin == null ? null : e.margin >= 0 ? d.home : d.away;
  const team = (abbr: string, name: string, color: string, side: string, p: string | null, home = false) => (
    <div className={cn("team-field flex items-center gap-4 px-4 py-4 text-white sm:px-6", home && "xl:flex-row-reverse")} style={{ "--team": color } as CSSProperties}>
      <div className="text-[28px] font-bold leading-none sm:text-[32px]">{abbr}</div>
      <div className={cn("min-w-0 text-[15px] leading-snug", home && "xl:text-right")}>
        <b className="font-semibold">{name}</b>
        <div className="opacity-85">{d.records[abbr]}, {side}</div>
      </div>
      {p && <div className={cn("text-4xl font-bold leading-none sm:text-[40px]", home ? "ml-auto xl:ml-0 xl:mr-auto" : "ml-auto")}>{p}</div>}
    </div>
  );
  return (
    <section aria-label="Win chance" className="grid grid-cols-1 xl:grid-cols-[1fr_auto_1fr]">
      {team(d.away, d.away_name, d.away_color, "away", awayP)}
      <dl className="order-last grid grid-cols-[auto_auto] content-center gap-x-6 gap-y-0.5 bg-panel2 px-4 py-4 sm:px-6 xl:order-none">
        <div className="col-span-full"><dt className="text-[13px] text-muted">{d.completed ? "Final" : "Kickoff"}</dt><dd className="text-lg font-semibold">{d.completed ? `${d.away} ${d.away_score}, ${d.home} ${d.home_score}` : `${d.date_label}, ${d.time_label} ET`}</dd></div>
        {e?.home_pts !== undefined && e?.away_pts !== undefined && <div><dt className="text-[13px] text-muted">Expected score</dt><dd className="text-lg font-semibold">{d.away} {e.away_pts.toFixed(0)}, {d.home} {e.home_pts.toFixed(0)}</dd></div>}
        {e && (e.margin !== null || e.total !== null) && <div><dt className="text-[13px] text-muted">Spread, total</dt><dd className="text-lg font-semibold">{e.margin === null ? "" : Math.abs(e.margin) < 0.25 ? "Even" : `${fav} by ${num(Math.abs(e.margin))}`}{e.margin !== null && e.total !== null ? ", " : ""}{e.total === null ? "" : num(e.total)}</dd></div>}
        <div className="col-span-full"><dt className="sr-only">Where it comes from</dt><dd className="text-[15px] text-muted">{h ? `Win chance from ${h.p_label}, at ${d.stadium}` : d.stadium}</dd></div>
      </dl>
      {team(d.home, d.home_name, d.home_color, "home", homeP, true)}
    </section>
  );
}

const Card = ({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) => <div className={cn("bg-panel p-4 sm:p-6", className)} {...p} />;

export function Overview({ d }: { d: Detail }) {
  if (!d.has_forecast || !d.headline) return <Callout tone="blue">No lines or forecast are saved for this game yet.</Callout>;
  const e = d.expected!, dist = d.distribution;
  const sources = e.margin_label && e.total_label && e.margin_label !== e.total_label ? `Spread from ${e.margin_label}, total from ${e.total_label}.` : `Spread and total from ${e.margin_label ?? e.total_label}.`;
  return (
    <div className="space-y-4">
      {d.result && <Callout tone={d.result.favorite_won ? "green" : "amber"}>{d.result.winner} won. The favorite ({d.headline.favored}) {d.result.favorite_won ? "won" : "lost"}.</Callout>}
      <div className="grid items-start gap-0.5 xl:grid-cols-[5fr_7fr] xl:[grid-template-areas:'fc_margin''total_margin'] [grid-template-areas:'fc''margin''total']">
        <Card className="[grid-area:fc]"><ForecastDots d={d} /></Card>
        {dist && e.margin !== null && (
          <Card className="[grid-area:margin]">
            <h2 className="text-xl leading-tight text-white">Final margin</h2>
            <p className="mb-4 mt-1 text-[15px] text-muted">Share of simulated games ending at each margin. Yellow line: expected margin.</p>
            <div className="mb-2 ml-[3.1em] flex justify-between text-[15px] font-semibold"><span>{d.away} wins</span><span>{d.home} wins</span></div>
            <Hist bins={dist.margin} exp={e.margin} color={(x) => (x < 0 ? d.away_color : x > 0 ? d.home_color : "#8b9097")} ticks={tickEvery(dist.margin, 20)}
              label={`Final margin distribution, expected ${d.home} by ${e.margin.toFixed(1)}`} />
            {d.outcomes && (
              <div className="mt-4 grid gap-0.5">
                {d.outcomes.map((o) => <div key={o.label} className="flex justify-between bg-panel2 px-4 py-2.5 text-[15px]"><span>{o.label}</span><b>{pct(o.p)}</b></div>)}
              </div>
            )}
            <p className="mt-4 text-sm text-muted">{sources}</p>
          </Card>
        )}
        {dist && e.total !== null && (
          <Card className="[grid-area:total]">
            <h2 className="text-xl leading-tight text-white">Total points</h2>
            <p className="mb-4 mt-1 text-[15px] text-muted">Both teams combined. Yellow line: expected total.</p>
            <Hist bins={dist.total} exp={e.total} color={() => "#8b9097"} ticks={tickEvery(dist.total, 20)} label={`Total points distribution, expected ${e.total.toFixed(1)}`} />
            <p className="mt-4 text-base text-slate-300">8 in 10 games like this land between <b className="text-white">{Math.round(e.total - 1.2816 * e.sd_t)}</b> and <b className="text-white">{Math.round(e.total + 1.2816 * e.sd_t)}</b> points.</p>
          </Card>
        )}
      </div>
    </div>
  );
}
