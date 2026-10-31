import { Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Detail } from "../types";
import { etStamp, num, pairColors, pct } from "../lib";
import { Callout, Card, PanelTitle } from "./ui/primitives";

type Colors = ReturnType<typeof pairColors>;

// The page's main graphic: two blocks in the teams' own colors, each carrying that team's win chance.
function Hero({ d, c }: { d: Detail; c: Colors }) {
  const h = d.headline;
  const side = (abbr: string, name: string, where: string, bg: string, ink: string, p: number | null) => (
    <div className="flex min-h-[11.5rem] flex-col justify-between gap-5 p-4 sm:p-6 md:min-h-[15rem]" style={{ background: bg, color: ink }}>
      <div>
        <div className="font-display text-xl font-extrabold leading-none">{abbr}</div>
        <div className="mt-2 text-base font-semibold leading-tight sm:text-lg">{name}</div>
        <div className="text-sm font-medium">{d.records[abbr]} · {where}</div>
      </div>
      {p !== null && (
        <div className="display-num" style={{ fontSize: "clamp(3.5rem, 14vw, 9rem)" }}>
          {pct(p)}<span className="sr-only"> win chance</span>
        </div>
      )}
    </div>
  );
  return (
    <section aria-label="Matchup">
      <div className="grid grid-cols-2 gap-0.5 overflow-hidden rounded-md">
        {side(d.away, d.away_name, "away", c.away, c.awayInk, h ? 1 - h.p_home : null)}
        {side(d.home, d.home_name, "home", c.home, c.homeInk, h ? h.p_home : null)}
      </div>
      <p className="mt-3 text-lg font-bold">
        {d.completed ? `Final: ${d.away} ${d.away_score}, ${d.home} ${d.home_score}` : `${d.date_label} · ${d.time_label} ET`}
      </p>
    </section>
  );
}

function WinChance({ d, c }: { d: Detail; c: Colors }) {
  const h = d.headline!;
  const homeP = h.p_home;
  return (
    <Card>
      <PanelTitle>Win chance</PanelTitle>
      <div className="flex items-baseline justify-between text-lg font-bold">
        <span>{d.away} {pct(1 - homeP)}</span>
        <span>{pct(homeP)} {d.home}</span>
      </div>
      <div className="my-2 flex h-5 gap-0.5 overflow-hidden rounded-sm" role="img" aria-label={`${d.away} ${pct(1 - homeP)}, ${d.home} ${pct(homeP)}`}>
        <div style={{ width: `${(1 - homeP) * 100}%`, background: c.away }} />
        <div style={{ width: `${homeP * 100}%`, background: c.home }} />
      </div>
      <p className="text-sm text-muted">Source: {h.p_label}, saved {etStamp(h.saved_at)}.</p>
      {d.vote && (
        <div className="mt-4 flex justify-between gap-3 border-t border-line pt-3 text-base">
          <span className="text-muted">Model vote</span>
          <span className="font-semibold">
            {d.vote.tie ? `${d.vote.home}-${d.vote.away} tie` : `${d.vote.home > d.vote.away ? d.home : d.away} ${Math.max(d.vote.home, d.vote.away)} of 6`}
          </span>
        </div>
      )}
      {(d.sources ?? []).length > 0 && (
        <div className="mt-3 border-t border-line pt-3">
          <h3 className="mb-1 text-base font-bold">Research forecasts, {d.home} win chance</h3>
          <p className="mb-2 text-sm text-muted">Not used above.</p>
          {d.sources!.map((s) => (
            <div key={s.name} className="flex justify-between gap-3 py-1 text-base">
              <span className="text-muted">{s.name}</span>
              <span className="font-semibold">{pct(s.p_home)}</span>
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
      <PanelTitle>Expected score</PanelTitle>
      <p className="display-num text-[2.75rem] sm:text-5xl" style={{ lineHeight: 1 }}>
        {d.away} {e.away_pts.toFixed(0)}, {d.home} {e.home_pts.toFixed(0)}
      </p>
      <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-line pt-3">
        <div>
          <dt className="text-sm text-muted">Spread</dt>
          <dd className="text-lg font-bold">{Math.abs(e.margin) < 0.25 ? "Even" : `${fav} by ${num(Math.abs(e.margin))}`}</dd>
        </div>
        <div>
          <dt className="text-sm text-muted">Total points</dt>
          <dd className="text-lg font-bold">{num(e.total)}</dd>
        </div>
      </dl>
      <p className="mt-3 text-sm text-muted">Source: the separate score model, not a sportsbook line. Its own win chance for {d.home} is {pct(e.p_home_score_model)}.</p>
    </Card>
  );
}

const axis = { tick: { fill: "#a9b3c1", fontSize: 13 }, tickLine: false };
const tip = { cursor: { fill: "rgba(255,255,255,0.08)" }, contentStyle: { background: "#1d222a", border: "1px solid #39424f", borderRadius: 4, color: "#f2f4f7" }, labelStyle: { color: "#f2f4f7" }, itemStyle: { color: "#f2f4f7" } };

function MarginChart({ d, c }: { d: Detail; c: Colors }) {
  const data = d.distribution!.margin;
  const e = d.expected!;
  const side = (x: number) => (x === 0 ? "Even" : x > 0 ? `${d.home} by ${x}` : `${d.away} by ${-x}`);
  const summary = `8 in 10 games like this land between ${side(Math.round(e.margin_range[0]))} and ${side(Math.round(e.margin_range[1]))}.`;
  return (
    <Card>
      <PanelTitle hint={`Left of 0: ${d.away} wins. Right of 0: ${d.home} wins. Dashed line: middle of the range.`}>Final margin</PanelTitle>
      <div role="img" aria-label={`Final margin chart. ${summary}`}>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }} barCategoryGap={1}>
            <XAxis dataKey="x" interval={9} {...axis} axisLine={{ stroke: "#39424f" }} />
            <YAxis hide />
            <Tooltip {...tip} formatter={(v: number) => [`${(v * 100).toFixed(1)}%`, "Chance"]} labelFormatter={(x: number) => side(x)} />
            <Bar dataKey="p" isAnimationActive={false}>
              {data.map((r) => <Cell key={r.x} fill={r.x > 0 ? c.home : r.x < 0 ? c.away : "#7b8696"} />)}
            </Bar>
            <ReferenceLine x={Math.round(e.margin_mid)} stroke="#ffffff" strokeDasharray="5 4" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 border-t border-line pt-3 text-base">
        8 in 10 games like this land between <b>{side(Math.round(e.margin_range[0]))}</b> and <b>{side(Math.round(e.margin_range[1]))}</b>.
      </p>
    </Card>
  );
}

function TotalChart({ d }: { d: Detail }) {
  const data = d.distribution!.total;
  const e = d.expected!;
  return (
    <Card>
      <PanelTitle hint="Both teams combined. Dashed line: middle of the range.">Total points</PanelTitle>
      <div role="img" aria-label={`Total points chart. 8 in 10 games like this land between ${Math.round(e.total_range[0])} and ${Math.round(e.total_range[1])} points.`}>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 4 }} barCategoryGap={1}>
            <XAxis dataKey="x" interval={9} {...axis} axisLine={{ stroke: "#39424f" }} />
            <YAxis hide />
            <Tooltip {...tip} formatter={(v: number) => [`${(v * 100).toFixed(1)}%`, "Chance"]} labelFormatter={(x: number) => `${x} points`} />
            <Bar dataKey="p" fill="#aab4c3" isAnimationActive={false} />
            <ReferenceLine x={Math.round(e.total_mid)} stroke="#ffffff" strokeDasharray="5 4" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 border-t border-line pt-3 text-base">
        8 in 10 games like this land between <b>{Math.round(e.total_range[0])}</b> and <b>{Math.round(e.total_range[1])}</b> points.
      </p>
    </Card>
  );
}

export function Overview({ d }: { d: Detail }) {
  const c = pairColors(d.away_color, d.home_color);
  if (!d.has_forecast || !d.headline) {
    return (
      <div className="space-y-4">
        <Hero d={d} c={c} />
        <Callout tone="blue">No forecast is saved for this game yet. Forecasts are saved by the daily refresh (option 2 in START_NBA.bat) before tipoff.</Callout>
      </div>
    );
  }
  return (
    <div className="space-y-4">
      <Hero d={d} c={c} />
      {d.result && (
        <Callout tone={d.result.favorite_won ? "green" : "amber"}>
          {d.result.winner} won. The favorite ({d.headline.favored}) {d.result.favorite_won ? "won" : "lost"}.
        </Callout>
      )}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <WinChance d={d} c={c} />
        {d.expected ? <Score d={d} /> : <Callout tone="blue">No score projection is saved for this game.</Callout>}
      </div>
      {d.distribution && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <MarginChart d={d} c={c} />
          <TotalChart d={d} />
        </div>
      )}
    </div>
  );
}
