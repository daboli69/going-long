import type { CSSProperties } from "react";
import { Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Detail } from "../types";
import { cn, num, pct, splitPct } from "../lib";
import { Callout, Card, Label } from "./ui/primitives";

// The scorebug: each team as a block of its own colour with its win chance, kickoff and source in the middle.
export function Scorebug({ d }: { d: Detail }) {
  const h = d.has_forecast ? d.headline : null;
  const [awayP, homeP] = h ? splitPct(h.p_home) : [null, null];
  const team = (abbr: string, name: string, color: string, side: string, p: string | null, home = false) => (
    <div className={cn("team-field flex items-center gap-4 px-5 py-4 text-white", home && "md:flex-row-reverse md:text-right")} style={{ "--team": color } as CSSProperties}>
      <div className="text-4xl font-bold leading-none sm:text-[44px]">{abbr}</div>
      <div className="min-w-0">
        <div className="text-[17px] leading-tight">{name}</div>
        <div className="text-[15px] opacity-90">{d.records[abbr]} · {side}</div>
      </div>
      {p && <div className={cn("ml-auto text-5xl font-bold leading-none sm:text-[56px]", home && "md:ml-0 md:mr-auto")}>{p}</div>}
    </div>
  );
  return (
    <section aria-label="Matchup" className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr]">
      {team(d.away, d.away_name, d.away_color, "away", awayP)}
      <div className="order-first flex flex-col justify-center bg-panel2 px-5 py-3 text-center md:order-none md:min-w-[200px]">
        <div className="text-lg font-semibold text-white">{d.completed ? `Final: ${d.away} ${d.away_score}, ${d.home} ${d.home_score}` : `${d.date_label} · ${d.time_label} ET`}</div>
        <div className="text-[15px] text-muted">{d.stadium}</div>
        {h && <div className="text-[15px] text-muted">Win chance from {h.p_label}</div>}
      </div>
      {team(d.home, d.home_name, d.home_color, "home", homeP, true)}
    </section>
  );
}

function Forecasts({ d }: { d: Detail }) {
  const others = (d.sources ?? []).filter((s) => !s.name.startsWith("Betting market"));
  if (!others.length) return null;
  return (
    <Card>
      <Label className="mb-2">Other forecasts, {d.home} win chance</Label>
      {others.map((s) => (
        <div key={s.name} className="flex justify-between border-line py-1.5 text-base [&+&]:border-t">
          <span className="text-slate-300">{s.name}</span>
          <span className="font-semibold text-white">{pct(s.p_home)}</span>
        </div>
      ))}
      {d.agreement && !d.agreement.agree && (
        <p className="mt-2 text-[15px] text-warn">Forecasts differ by {d.agreement.gap_points.toFixed(0)} points on this game.</p>
      )}
    </Card>
  );
}

function Score({ d }: { d: Detail }) {
  const e = d.expected!;
  if (e.margin === null && e.total === null) return null;
  const fav = e.margin === null ? null : e.margin >= 0 ? d.home : d.away;
  return (
    <Card>
      <Label>Expected score</Label>
      {e.home_pts !== undefined && e.away_pts !== undefined && (
        <div className="mt-1 text-[34px] font-bold leading-tight text-white">
          {d.away} {e.away_pts.toFixed(0)} · {d.home} {e.home_pts.toFixed(0)}
        </div>
      )}
      <div className="mt-2">
        {e.margin !== null && (
          <div className="flex justify-between py-1.5 text-base">
            <span className="text-slate-300">Spread</span>
            <span className="font-semibold text-white">{Math.abs(e.margin) < 0.25 ? "Even" : `${fav} by ${num(Math.abs(e.margin))}`}</span>
          </div>
        )}
        {e.total !== null && (
          <div className="flex justify-between border-t border-line py-1.5 text-base">
            <span className="text-slate-300">Total points</span>
            <span className="font-semibold text-white">{num(e.total)}</span>
          </div>
        )}
      </div>
      <p className="mt-2 text-[15px] text-muted">
        {e.margin_label && e.total_label && e.margin_label !== e.total_label
          ? `Spread: ${e.margin_label}. Total: ${e.total_label}.`
          : `Source: ${e.margin_label ?? e.total_label}.`}
      </p>
    </Card>
  );
}

const axis = { tick: { fill: "#a9adb3", fontSize: 13 }, tickLine: false };
const tip = { cursor: { fill: "rgba(255,255,255,0.06)" }, contentStyle: { background: "#0e0f11", border: 0, borderRadius: 0, color: "#f2f2f0" } };

function MarginChart({ d }: { d: Detail }) {
  const data = d.distribution!.margin;
  const mu = d.expected!.margin!;
  return (
    <Card>
      <h2 className="text-lg font-semibold text-white">Final margin</h2>
      <p className="mb-3 text-[15px] text-muted">Left of 0: {d.away} wins. Right of 0: {d.home} wins. Dashed line: expected margin.</p>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }} barCategoryGap={1}>
          <XAxis dataKey="x" interval={9} {...axis} axisLine={{ stroke: "#2c3036" }} />
          <YAxis hide />
          <Tooltip {...tip} formatter={(v: number) => [`${(v * 100).toFixed(1)}%`, "Chance"]}
            labelFormatter={(x: number) => (x === 0 ? "Tie" : x > 0 ? `${d.home} by ${x}` : `${d.away} by ${-x}`)} />
          <Bar dataKey="p" isAnimationActive={false}>
            {data.map((r) => <Cell key={r.x} fill={r.x > 0 ? d.home_color : r.x < 0 ? d.away_color : "#6b7076"} />)}
          </Bar>
          <ReferenceLine x={Math.round(mu)} stroke="#ffcf3f" strokeDasharray="5 4" />
        </BarChart>
      </ResponsiveContainer>
      {d.outcomes && (
        <div className="mt-3">
          {d.outcomes.map((o) => (
            <div key={o.label} className="flex justify-between border-t border-line py-1.5 text-base">
              <span className="text-slate-300">{o.label}</span>
              <span className="font-semibold text-white">{pct(o.p)}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function TotalChart({ d }: { d: Detail }) {
  const data = d.distribution!.total;
  const mu = d.expected!.total!;
  const sd = d.expected!.sd_t;
  return (
    <Card>
      <h2 className="text-lg font-semibold text-white">Total points</h2>
      <p className="mb-3 text-[15px] text-muted">Both teams combined. Dashed line: expected total.</p>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }} barCategoryGap={1}>
          <XAxis dataKey="x" interval={9} {...axis} axisLine={{ stroke: "#2c3036" }} />
          <YAxis hide />
          <Tooltip {...tip} formatter={(v: number) => [`${(v * 100).toFixed(1)}%`, "Chance"]} labelFormatter={(x: number) => `${x} points`} />
          <Bar dataKey="p" fill="#8b9097" isAnimationActive={false} />
          <ReferenceLine x={Math.round(mu)} stroke="#ffcf3f" strokeDasharray="5 4" />
        </BarChart>
      </ResponsiveContainer>
      <p className="mt-3 border-t border-line pt-2 text-base text-slate-300">
        8 in 10 games like this land between <b className="text-white">{Math.round(mu - 1.2816 * sd)}</b> and <b className="text-white">{Math.round(mu + 1.2816 * sd)}</b> points.
      </p>
    </Card>
  );
}

export function Overview({ d }: { d: Detail }) {
  if (!d.has_forecast || !d.headline) {
    return <Callout tone="blue">No lines or forecast are saved for this game yet.</Callout>;
  }
  return (
    <div className="space-y-0.5">
      {d.result && (
        <div className="pb-4">
          <Callout tone={d.result.favorite_won ? "green" : "amber"}>
            {d.result.winner} won. The favorite ({d.headline.favored}) {d.result.favorite_won ? "won" : "lost"}.
          </Callout>
        </div>
      )}
      <div className="grid grid-cols-1 gap-0.5 md:grid-cols-[1.1fr_1fr]">
        <Score d={d} />
        <Forecasts d={d} />
      </div>
      {d.distribution && (
        <div className="grid grid-cols-1 gap-0.5 lg:grid-cols-2">
          <MarginChart d={d} />
          <TotalChart d={d} />
        </div>
      )}
    </div>
  );
}
