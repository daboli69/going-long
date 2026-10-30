import { Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Detail } from "../types";
import { num, pct } from "../lib";
import { Callout, Card } from "./ui/primitives";
import { TeamChip } from "./TeamChip";

function Header({ d }: { d: Detail }) {
  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <TeamChip abbr={d.away} color={d.away_color} />
          <div>
            <div className="text-xl font-extrabold leading-tight text-white">{d.away_name}</div>
            <div className="text-sm text-muted">Record {d.records[d.away]} · away team</div>
          </div>
        </div>
        <div className="text-center">
          <div className="text-lg font-bold text-white">{d.completed ? `Final: ${d.away} ${d.away_score}, ${d.home} ${d.home_score}` : `${d.date_label} · ${d.kickoff_label} ET`}</div>
          <div className="text-sm text-muted">{d.stadium}</div>
        </div>
        <div className="flex flex-row-reverse items-center gap-3 text-right">
          <TeamChip abbr={d.home} color={d.home_color} />
          <div>
            <div className="text-xl font-extrabold leading-tight text-white">{d.home_name}</div>
            <div className="text-sm text-muted">Record {d.records[d.home]} · home team</div>
          </div>
        </div>
      </div>
    </Card>
  );
}

function WinBar({ d }: { d: Detail }) {
  const h = d.headline!;
  const homeP = h.p_home;
  return (
    <Card>
      <div className="text-base font-bold text-white">Who is likely to win?</div>
      <div className="mt-2 flex items-end justify-between text-2xl font-extrabold text-white">
        <span>
          {d.away} {pct(1 - homeP)}
        </span>
        <span>
          {pct(homeP)} {d.home}
        </span>
      </div>
      <div className="my-2 flex h-5 overflow-hidden rounded-full bg-line" role="img" aria-label={`${d.away} ${pct(1 - homeP)}, ${d.home} ${pct(homeP)}`}>
        <div style={{ width: `${(1 - homeP) * 100}%`, background: d.away_color }} />
        <div style={{ width: `${homeP * 100}%`, background: d.home_color }} />
      </div>
      <div className="text-xs text-muted">Based on {h.p_label}. The percentages are each team&apos;s chance to win.</div>
    </Card>
  );
}

function Sources({ d }: { d: Detail }) {
  if (!d.sources?.length) return null;
  const agree = d.agreement!.agree;
  return (
    <>
      <Card>
        <div className="mb-1 text-base font-bold text-white">What each source says</div>
        {d.sources.map((s) => (
          <div key={s.name} className="flex justify-between border-b border-line py-1.5 text-sm last:border-0">
            <span>{s.name}</span>
            <span>
              <b>
                {d.home} {pct(s.p_home)}
              </b>{" "}
              · {d.away} {pct(1 - s.p_home)}
            </span>
          </div>
        ))}
      </Card>
      <Callout tone={agree ? "green" : "amber"}>
        The sources {agree ? <b>agree</b> : <b>disagree by {d.agreement!.gap_points.toFixed(0)} points</b>} on this game. {d.headline!.favored_name} are favored at about {pct(d.headline!.p_favored)}.
      </Callout>
    </>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <Card className="flex flex-col gap-1">
      <div className="text-xs text-muted">{label}</div>
      <div className="text-2xl font-bold leading-tight text-white">{value}</div>
      <div className="text-xs leading-snug text-muted">{sub}</div>
    </Card>
  );
}

function MarginChart({ d }: { d: Detail }) {
  const data = d.distribution!.margin;
  const mu = d.expected!.margin!;
  return (
    <Card>
      <div className="mb-2 text-base font-bold text-white">How the final margin could play out</div>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: 0 }} barCategoryGap={1}>
          <XAxis dataKey="x" interval={9} tick={{ fill: "#9fb0cc", fontSize: 12 }} tickLine={false} axisLine={{ stroke: "#1e2b45" }} />
          <YAxis tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`} tick={{ fill: "#9fb0cc", fontSize: 12 }} tickLine={false} axisLine={false} width={42} />
          <Tooltip
            cursor={{ fill: "rgba(255,255,255,0.05)" }}
            contentStyle={{ background: "#0f1a2e", border: "1px solid #1e2b45", borderRadius: 8 }}
            formatter={(v: number) => [`${(v * 100).toFixed(1)}%`, "Chance"]}
            labelFormatter={(x: number) => (x === 0 ? "Tie" : x > 0 ? `${d.home} wins by ${x}` : `${d.away} wins by ${-x}`)}
          />
          <Bar dataKey="p" isAnimationActive={false}>
            {data.map((r) => (
              <Cell key={r.x} fill={r.x > 0 ? d.home_color : r.x < 0 ? d.away_color : "#64748b"} />
            ))}
          </Bar>
          <ReferenceLine x={Math.round(mu)} stroke="#fbbf24" strokeDasharray="5 4" />
        </BarChart>
      </ResponsiveContainer>
      <div className="text-xs text-muted">
        Taller bars are more likely. Bars to the right of 0 are {d.home} wins, to the left {d.away} wins. The dashed line is the expected margin.
      </div>
    </Card>
  );
}

function TotalChart({ d }: { d: Detail }) {
  const data = d.distribution!.total;
  const mu = d.expected!.total!;
  return (
    <Card>
      <div className="mb-2 text-base font-bold text-white">How many points could be scored</div>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: 0 }} barCategoryGap={1}>
          <XAxis dataKey="x" interval={9} tick={{ fill: "#9fb0cc", fontSize: 12 }} tickLine={false} axisLine={{ stroke: "#1e2b45" }} />
          <YAxis tickFormatter={(v: number) => `${(v * 100).toFixed(1)}%`} tick={{ fill: "#9fb0cc", fontSize: 12 }} tickLine={false} axisLine={false} width={42} />
          <Tooltip
            cursor={{ fill: "rgba(255,255,255,0.05)" }}
            contentStyle={{ background: "#0f1a2e", border: "1px solid #1e2b45", borderRadius: 8 }}
            formatter={(v: number) => [`${(v * 100).toFixed(1)}%`, "Chance"]}
            labelFormatter={(x: number) => `${x} total points`}
          />
          <Bar dataKey="p" fill="#60a5fa" isAnimationActive={false} />
          <ReferenceLine x={Math.round(mu)} stroke="#fbbf24" strokeDasharray="5 4" />
        </BarChart>
      </ResponsiveContainer>
      <div className="text-xs text-muted">Both teams combined. The dashed line is the expected total.</div>
    </Card>
  );
}

export function Overview({ d }: { d: Detail }) {
  if (!d.has_forecast || !d.headline) {
    return (
      <div className="space-y-4">
        <Header d={d} />
        <Callout tone="blue">No forecast has been saved for this game yet. The weekly forecast is saved before each week&apos;s first kickoff.</Callout>
      </div>
    );
  }
  const e = d.expected!;
  const favMargin = e.margin === null ? null : e.margin >= 0 ? d.home : d.away;
  return (
    <div className="space-y-4">
      <Header d={d} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.1fr_1fr]">
        <div className="space-y-3">
          <WinBar d={d} />
          <Sources d={d} />
        </div>
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {e.margin !== null && <Stat label="Expected margin" value={`${favMargin} by ${num(Math.abs(e.margin))}`} sub={`Based on ${e.margin_label}. A margin of 3 = a field goal; 7 = a touchdown.`} />}
            {e.total !== null && <Stat label="Expected total points" value={num(e.total)} sub={`Both teams combined, based on ${e.total_label}.`} />}
            {e.home_pts !== undefined && e.away_pts !== undefined && (
              <Stat label="Expected score" value={`${e.away_pts.toFixed(0)} - ${e.home_pts.toFixed(0)}`} sub={`${d.away} ${e.away_pts.toFixed(1)}, ${d.home} ${e.home_pts.toFixed(1)}. A typical outcome, not a guarantee.`} />
            )}
          </div>
          {d.lean && <Callout tone={d.lean.abstain ? "green" : "amber"}>{d.lean.abstain ? <b>No strong opinion.</b> : <b>Our model disagrees with the market.</b>} {d.lean.text.replace(/^No strong opinion\. |^Our model disagrees with the market\. /, "")}</Callout>}
        </div>
      </div>
      {d.distribution && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <MarginChart d={d} />
          <TotalChart d={d} />
        </div>
      )}
      {d.outcomes && (
        <Card>
          <div className="mb-2 text-base font-bold text-white">How the game could play out</div>
          <table className="w-full text-sm">
            <tbody>
              {d.outcomes.map((o) => (
                <tr key={o.label} className="border-b border-line last:border-0">
                  <td className="py-2">{o.label}</td>
                  <td className="w-40 py-2">
                    <div className="h-2 rounded-full bg-line">
                      <div className="h-2 rounded-full bg-accent" style={{ width: `${o.p * 100}%` }} />
                    </div>
                  </td>
                  <td className="w-14 py-2 text-right font-semibold text-white">{pct(o.p)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      {d.result && (
        <Callout tone="blue">
          <b>Result:</b> {d.result.winner} won. The market&apos;s favorite was {d.headline.favored}, so the favorite {d.result.favorite_won ? "won" : "did not win"}.
        </Callout>
      )}
    </div>
  );
}
