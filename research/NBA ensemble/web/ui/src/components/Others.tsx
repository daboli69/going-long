import { useEffect, useState } from "react";
import { ChevronDown } from "lucide-react";
import { api } from "../api";
import type { Detail, GlossaryItem, Meta } from "../types";
import { cn, etStamp, num, pairColors, pct } from "../lib";
import { Badge, Callout, Card, PanelTitle } from "./ui/primitives";
import { TeamChip } from "./TeamChip";

// ------------------------------------------------------------------ Six models on one game
export function Models({ d }: { d: Detail }) {
  if (!d.models || !d.headline) return <Callout tone="blue">No saved forecast for this game, so there are no model numbers to show.</Callout>;
  const c = pairColors(d.away_color, d.home_color);
  const rows = [...d.models].sort((a, b) => b.p_home - a.p_home);
  return (
    <div className="space-y-4">
      <Card>
        <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
          <PanelTitle hint={`Left of the middle line favors ${d.away}.`}>Each model's win chance for {d.home}</PanelTitle>
          {d.disagreement_points !== undefined && (
            <Badge tone={d.disagreement_points >= 15 ? "amber" : "neutral"}>Highest and lowest differ by {d.disagreement_points.toFixed(0)} points</Badge>
          )}
        </div>
        <ul>
          {rows.map((m) => (
            <li key={m.name} className="grid grid-cols-[minmax(0,1fr)_3.5rem] items-center gap-x-3 gap-y-1 py-2 sm:grid-cols-[minmax(0,13rem)_1fr_3.5rem]">
              <span className="truncate text-base text-muted sm:col-start-1">{m.name}</span>
              <span className="text-right text-base font-bold sm:order-last">{pct(m.p_home)}</span>
              <div className="relative col-span-2 h-4 rounded-sm bg-surface2 sm:col-span-1" aria-hidden>
                <div className="absolute inset-y-0 left-1/2 w-0.5 bg-ink/50" />
                <div className="absolute inset-y-0 rounded-sm"
                  style={m.p_home >= 0.5
                    ? { left: "50%", width: `${(m.p_home - 0.5) * 100}%`, background: c.home }
                    : { right: "50%", width: `${(0.5 - m.p_home) * 100}%`, background: c.away }} />
              </div>
            </li>
          ))}
        </ul>
        <div className="mt-2 flex items-center justify-between border-t border-line pt-3">
          <span className="text-base font-bold">Combined</span>
          <span className="display-num text-3xl">{pct(d.headline.p_home)}</span>
        </div>
      </Card>
      <Callout tone="blue">
        All six learn from the same past games and inputs, so they often agree. Six of six agreeing does not mean a sure thing.
        The combined number comes from the frozen combination method, not from counting votes.
      </Callout>
      {d.forecast_warning && <p className="text-sm text-muted">Saved with this note: {d.forecast_warning}</p>}
    </div>
  );
}

// ------------------------------------------------------------------ Teams and injuries
export function Matchup({ d }: { d: Detail }) {
  const c = pairColors(d.away_color, d.home_color);
  const side = (abbr: string, name: string, color: string) => {
    const s = d.matchup[abbr];
    const injuries = d.injuries.teams[abbr] ?? [];
    return (
      <Card key={abbr}>
        <div className="flex items-center gap-3">
          <TeamChip abbr={abbr} color={color} size="sm" />
          <h2 className="text-lg font-bold">{name}</h2>
        </div>
        <dl className="mt-4 grid grid-cols-3 gap-3">
          <div><dt className="text-sm text-muted">Record</dt><dd className="text-lg font-bold">{s.record}</dd></div>
          <div><dt className="text-sm text-muted">Points for</dt><dd className="text-lg font-bold">{num(s.pf)}</dd></div>
          <div><dt className="text-sm text-muted">Points against</dt><dd className="text-lg font-bold">{num(s.pa)}</dd></div>
        </dl>
        <div className="mt-4 flex flex-wrap items-center gap-1">
          {s.last.map((r, i) => (
            <span key={i} className={cn("inline-flex h-7 w-7 items-center justify-center rounded text-sm font-bold", r === "W" ? "bg-ok-bg text-ok-fg" : "bg-bad-bg text-bad-fg")}>{r}</span>
          ))}
          {s.last.length > 0 && <span className="ml-1 text-sm text-muted">last {s.last.length}, oldest first</span>}
        </div>
        <h3 className="mt-5 text-base font-bold">Injury list</h3>
        {injuries.length === 0 ? (
          <p className="mt-1 text-base text-muted">No one listed on the latest saved check. That is not a confirmed lineup.</p>
        ) : (
          <ul className="mt-1">
            {injuries.map((r) => (
              <li key={r.player} className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-line py-2 text-base last:border-0">
                <span>{r.player}</span>
                <span className="flex items-center gap-2">
                  {r.updated && <span className="text-sm text-muted">updated {etStamp(r.updated)}</span>}
                  <Badge tone={r.tone}>{r.status}</Badge>
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    );
  };
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {side(d.away, d.away_name, c.away)}
        {side(d.home, d.home_name, c.home)}
      </div>
      <p className="text-sm text-muted">
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
        <h2 className="text-lg font-bold">Where the numbers come from</h2>
        <p className="mt-1 max-w-prose text-base leading-relaxed text-muted">{meta.reality_check}</p>
        <h2 className="mt-5 text-lg font-bold">Track record</h2>
        {record.length === 0 && <p className="py-2 text-base text-muted">No finished games with a saved forecast yet.</p>}
        <dl>
          {record.map(([label, value]) => (
            <div key={label} className="border-b border-line py-2 last:border-0">
              <dt className="text-sm text-muted">{label}</dt>
              <dd className="text-base font-semibold">{value}</dd>
            </div>
          ))}
        </dl>
      </Card>
      <Card>
        <h2 className="mb-1 text-lg font-bold">Terms</h2>
        {items.map((g) => (
          <details key={g.term} className="group border-b border-line last:border-0">
            <summary className="flex min-h-11 list-none items-center justify-between gap-3 py-2 text-base font-semibold [&::-webkit-details-marker]:hidden">
              {g.term}
              <ChevronDown className="h-5 w-5 shrink-0 text-muted transition-transform group-open:rotate-180" aria-hidden />
            </summary>
            <p className="max-w-prose pb-3 text-base leading-relaxed text-muted">{g.text}</p>
          </details>
        ))}
      </Card>
    </div>
  );
}
