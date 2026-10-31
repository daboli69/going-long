import { Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Detail } from "../types";
import { etStamp, num, pct } from "../lib";
import { Callout, Card } from "./ui/primitives";
import { TeamChip } from "./TeamChip";

function Header({ d }: { d: Detail }) {
  const team = (abbr: string, name: string, color: string, side: string, right = false) => (
    <div className={right ? "flex flex-row-reverse items-center gap-3 text-right" : "flex items-center gap-3"}>
      <TeamChip abbr={abbr} color={color} />
      <div>
        <div className="text-lg font-bold leading-tight text-white">{name}</div>
        <div className="text-sm text-muted">{d.records[abbr]} · {side}</div>
      </div>
    </div>
  );
  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-4">
        {team(d.away, d.away_name, d.away_color, "away")}
        <div className="text-center font-semibold text-white">
          {d.completed ? `Final: ${d.away} ${d.away_score}, ${d.home} ${d.home_score}` : `${d.date_label} · ${d.time_label} ET`}
        </div>
        {team(d.home, d.home_name, d.home_color, "home", true)}
      </div>
    </Card>
  );
}

function WinChance({ d }: { d: Detail }) {
  const h = d.headline!;
  const homeP = h.p_home;
  return (
    <Card>
      <div className="text-sm text-muted">Win chance</div>
      <div className="mt-1 flex items-end justify-between text-2xl font-bold text-white">
        <span>{d.away} {pct(1 - homeP)}</span>
        <span>{pct(homeP)} {d.home}</span>
      </div>
      <div className="my-2 flex h-3 overflow-hidden rounded-full bg-line" role="img" aria-label={`${d.away} ${pct(1 - homeP)}, ${d.home} ${pct(homeP)}`}>
        <div style={{ width: `${(1 - homeP) * 100}%`, background: d.away_color }} />
        <div style={{ width: `${homeP * 100}%`, background: d.home_color }} />
      </div>
      <div className="text-xs text-muted">Source: {h.p_label}, saved {etStamp(h.saved_at)}.</div>
      {d.vote && (
        <div className="mt-3 flex justify-between border-t border-line pt-2 text-sm">
          <span className="text-slate-300">Model vote</span>
          <span className="font-medium text-white">
            {d.vote.tie ? `${d.vote.home}-${d.vote.away} tie` : `${d.vote.home > d.vote.away ? d.home : d.away} ${Math.max(d.vote.home, d.vote.away)} of 6`}
          </span>
        </div>
      )}
      {(d.sources ?? []).length > 0 && (
        <div className="mt-2 border-t border-line pt-2">
          <div className="mb-1 text-xs text-muted">Research forecasts, {d.home} win chance (not used above)</div>
          {d.sources!.map((s) => (
            <div key={s.name} className="flex justify-between py-0.5 text-sm">
              <span className="text-slate-300">{s.name}</span>
              <span className="font-medium text-white">{pct(s.p_home)}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function Score({ d }: { d: Detail }) {
  const e = d.expected!;
  const fav = e.margin >= 0 ? d.home : d.away;
  return (
    <Card>
      <div className="text-sm text-muted">Expected score</div>
      <div className="mt-1 text-2xl font-bold text-white">
        {d.away} {e.away_pts.toFixed(0)}, {d.home} {e.home_pts.toFixed(0)}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3 border-t border-line pt-2 text-sm">
        <div>
          <div className="text-xs text-muted">Spread</div>
          <div className="font-medium text-white">{Math.abs(e.margin) < 0.25 ? "Even" : `${fav} by ${num(Math.abs(e.margin))}`}</div>
        </div>
        <div>
          <div className="text-xs text-muted">Total points</div>
          <div className="font-medium text-white">{num(e.total)}</div>
        </div>
      </div>
      <div className="mt-2 text-xs text-muted">Source: the separate score model, not a sportsbook line. Its own win chance for {d.home} is {pct(e.p_home_score_model)}.</div>
    </Card>
  );
}

const axis = { tick: { fill: "#9fb0cc", fontSize: 12 }, tickLine: false };
const tip = { cursor: { fill: "rgba(255,255,255,0.05)" }, contentStyle: { background: "#0f1a2e", border: "1px solid #1e2b45", borderRadius: 8 } };

function MarginChart({ d }: { d: Detail }) {
  const data = d.distribution!.margin;
  const e = d.expected!;
  const side = (x: number) => (x === 0 ? "Even" : x > 0 ? `${d.home} by ${x}` : `${d.away} by ${-x}`);
  return (
    <Card>
      <div className="text-sm text-muted">Final margin</div>
      <div className="mb-2 text-xs text-muted">Left of 0: {d.away} wins. Right of 0: {d.home} wins. Dashed line: middle of the range.</div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }} barCategoryGap={1}>
          <XAxis dataKey="x" interval={9} {...axis} axisLine={{ stroke: "#1e2b45" }} />
          <YAxis hide />
          <Tooltip {...tip} formatter={(v: number) => [`${(v * 100).toFixed(1)}%`, "Chance"]} labelFormatter={(x: number) => side(x)} />
          <Bar dataKey="p" isAnimationActive={false}>
            {data.map((r) => <Cell key={r.x} fill={r.x > 0 ? d.home_color : r.x < 0 ? d.away_color : "#64748b"} />)}
          </Bar>
          <ReferenceLine x={Math.round(e.margin_mid)} stroke="#fbbf24" strokeDasharray="5 4" />
        </BarChart>
      </ResponsiveContainer>
      <div className="mt-2 border-t border-line pt-2 text-sm text-slate-300">
        8 in 10 games like this land between <b className="text-white">{side(Math.round(e.margin_range[0]))}</b> and <b className="text-white">{side(Math.round(e.margin_range[1]))}</b>.
      </div>
    </Card>
  );
}

function TotalChart({ d }: { d: Detail }) {
  const data = d.distribution!.total;
  const e = d.expected!;
  return (
    <Card>
      <div className="text-sm text-muted">Total points</div>
      <div className="mb-2 text-xs text-muted">Both teams combined. Dashed line: middle of the range.</div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }} barCategoryGap={1}>
          <XAxis dataKey="x" interval={9} {...axis} axisLine={{ stroke: "#1e2b45" }} />
          <YAxis hide />
          <Tooltip {...tip} formatter={(v: number) => [`${(v * 100).toFixed(1)}%`, "Chance"]} labelFormatter={(x: number) => `${x} points`} />
          <Bar dataKey="p" fill="#60a5fa" isAnimationActive={false} />
          <ReferenceLine x={Math.round(e.total_mid)} stroke="#fbbf24" strokeDasharray="5 4" />
        </BarChart>
      </ResponsiveContainer>
      <div className="mt-2 border-t border-line pt-2 text-sm text-slate-300">
        8 in 10 games like this land between <b className="text-white">{Math.round(e.total_range[0])}</b> and <b className="text-white">{Math.round(e.total_range[1])}</b> points.
      </div>
    </Card>
  );
}

export function Overview({ d }: { d: Detail }) {
  if (!d.has_forecast || !d.headline) {
    return (
      <div className="space-y-4">
        <Header d={d} />
        <Callout tone="blue">No forecast is saved for this game yet. Forecasts are saved by the daily refresh (option 2 in START_NBA.bat) before tipoff.</Callout>
      </div>
    );
  }
  return (
    <div className="space-y-4">
      <Header d={d} />
      {d.result && (
        <Callout tone={d.result.favorite_won ? "green" : "amber"}>
          {d.result.winner} won. The favorite ({d.headline.favored}) {d.result.favorite_won ? "won" : "lost"}.
        </Callout>
      )}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <WinChance d={d} />
        {d.expected ? <Score d={d} /> : <Callout tone="blue">No score projection is saved for this game.</Callout>}
      </div>
      {d.distribution && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <MarginChart d={d} />
          <TotalChart d={d} />
        </div>
      )}
    </div>
  );
}
