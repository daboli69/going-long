import { useEffect, useState } from "react";
import { api } from "../api";
import type { Detail, GlossaryItem, Meta } from "../types";
import { cn, etStamp, num, pct } from "../lib";
import { Badge, Callout, Card } from "./ui/primitives";
import { TeamChip } from "./TeamChip";

// ------------------------------------------------------------------ Six models on one game
export function Models({ d }: { d: Detail }) {
  if (!d.models || !d.headline) return <Callout tone="blue">No saved forecast for this game, so there are no model numbers to show.</Callout>;
  const rows = [...d.models].sort((a, b) => b.p_home - a.p_home);
  return (
    <div className="space-y-4">
      <Card>
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <div className="text-sm text-muted">Each model's win chance for {d.home} (left of the middle line favors {d.away})</div>
          {d.disagreement_points !== undefined && (
            <Badge tone={d.disagreement_points >= 15 ? "amber" : "neutral"}>Highest and lowest differ by {d.disagreement_points.toFixed(0)} points</Badge>
          )}
        </div>
        {rows.map((m) => (
          <div key={m.name} className="grid grid-cols-[minmax(0,13rem)_1fr_3.5rem] items-center gap-3 py-1.5">
            <span className="truncate text-sm text-slate-300">{m.name}</span>
            <div className="relative h-3 rounded-full bg-line">
              <div className="absolute inset-y-0 left-1/2 w-px bg-muted/60" />
              <div className="absolute inset-y-0 rounded-full"
                style={m.p_home >= 0.5
                  ? { left: "50%", width: `${(m.p_home - 0.5) * 100}%`, background: d.home_color }
                  : { right: "50%", width: `${(0.5 - m.p_home) * 100}%`, background: d.away_color }} />
            </div>
            <span className="text-right text-sm font-medium text-white">{pct(m.p_home)}</span>
          </div>
        ))}
        <div className="mt-2 grid grid-cols-[minmax(0,13rem)_1fr_3.5rem] items-center gap-3 border-t border-line pt-2">
          <span className="text-sm font-semibold text-white">Combined</span>
          <span />
          <span className="text-right text-sm font-bold text-white">{pct(d.headline.p_home)}</span>
        </div>
      </Card>
      <Callout tone="blue">
        All six learn from the same past games and inputs, so they often agree. Six of six agreeing does not mean a sure thing.
        The combined number comes from the frozen combination method, not from counting votes.
      </Callout>
      {d.forecast_warning && <p className="text-xs text-muted">Saved with this note: {d.forecast_warning}</p>}
    </div>
  );
}

// ------------------------------------------------------------------ Teams and injuries
export function Matchup({ d }: { d: Detail }) {
  const side = (abbr: string, name: string, color: string) => {
    const s = d.matchup[abbr];
    const injuries = d.injuries.teams[abbr] ?? [];
    return (
      <Card key={abbr}>
        <div className="flex items-center gap-3">
          <TeamChip abbr={abbr} color={color} size="sm" />
          <div className="font-semibold text-white">{name}</div>
        </div>
        <div className="mt-3 grid grid-cols-3 gap-3 text-sm">
          <div><div className="text-xs text-muted">Record</div><div className="text-white">{s.record}</div></div>
          <div><div className="text-xs text-muted">Points for</div><div className="text-white">{num(s.pf)}</div></div>
          <div><div className="text-xs text-muted">Points against</div><div className="text-white">{num(s.pa)}</div></div>
        </div>
        <div className="mt-2 flex gap-1">
          {s.last.map((r, i) => (
            <span key={i} className={cn("inline-flex h-6 w-6 items-center justify-center rounded text-xs font-bold", r === "W" ? "bg-emerald-950 text-emerald-300" : "bg-red-950 text-red-300")}>{r}</span>
          ))}
          {s.last.length > 0 && <span className="ml-1 self-center text-xs text-muted">last {s.last.length}, oldest first</span>}
        </div>
        <div className="mt-4 text-sm font-semibold text-white">Injury list</div>
        {injuries.length === 0 ? (
          <div className="mt-1 text-sm text-muted">No one listed on the latest saved check. That is not a confirmed lineup.</div>
        ) : injuries.map((r) => (
          <div key={r.player} className="flex items-center justify-between border-b border-line py-1.5 text-sm last:border-0">
            <span className="text-slate-200">{r.player}</span>
            <span className="flex items-center gap-2">
              {r.updated && <span className="text-xs text-muted">updated {etStamp(r.updated)}</span>}
              <Badge tone={r.tone}>{r.status}</Badge>
            </span>
          </div>
        ))}
      </Card>
    );
  };
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {side(d.away, d.away_name, d.away_color)}
        {side(d.home, d.home_name, d.home_color)}
      </div>
      <p className="text-xs text-muted">
        Season so far, games before this one. Injury list from ESPN{d.injuries.retrieved ? `, checked ${etStamp(d.injuries.retrieved)}` : ""}.
        The original forecast does not use injuries.
      </p>
    </div>
  );
}

// ------------------------------------------------------------------ About these numbers
export function About({ meta }: { meta: Meta }) {
  const [items, setItems] = useState<GlossaryItem[]>([]);
  useEffect(() => { api.glossary().then(setItems).catch(() => setItems([])); }, []);
  const k = meta.track_record;
  const record: [string, string][] = [];
  if (k.games) record.push(["Winners picked correctly, saved before tipoff", `${pct(k.accuracy)} (${k.games} games). Always picking the home team: ${pct(k.home_team_accuracy)} on the same games.`]);
  if (k.margin_miss) record.push(["Average miss on the final margin", `${num(k.margin_miss.points)} points (${k.margin_miss.games} games)`]);
  if (k.games !== undefined && k.games < 200) record.push(["Sample size", "Too few games to tell skill from luck yet."]);
  if (meta.evaluation_status) record.push(["Research status", meta.evaluation_status]);
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Card>
        <h3 className="font-semibold text-white">Where the numbers come from</h3>
        <p className="mt-1 text-sm text-slate-300">{meta.reality_check}</p>
        <h3 className="mt-4 font-semibold text-white">Track record</h3>
        {record.length === 0 && <div className="py-2 text-sm text-muted">No finished games with a saved forecast yet.</div>}
        {record.map(([label, value]) => (
          <div key={label} className="border-b border-line py-2 last:border-0">
            <div className="text-xs text-muted">{label}</div>
            <div className="text-sm text-white">{value}</div>
          </div>
        ))}
      </Card>
      <Card>
        <h3 className="mb-1 font-semibold text-white">Terms</h3>
        {items.map((g) => (
          <details key={g.term} className="border-b border-line py-2 last:border-0">
            <summary className="cursor-pointer text-sm text-white">{g.term}</summary>
            <p className="mt-1 text-sm text-slate-300">{g.text}</p>
          </details>
        ))}
      </Card>
    </div>
  );
}
