import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { RankRow, Rankings } from "../types";
import { etTime, num, pct } from "../lib";
import { Badge, Callout, Card, Segmented } from "./ui/primitives";
import { TdCard } from "./TdCard";

const day = (iso: string) => new Date(iso).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", timeZone: "America/New_York" });

function show(r: RankRow, unit: string): string {
  if (unit === "chance") return pct(r.projection);
  if (unit === "rec") return `${num(r.projection, 1)} catches`;
  return `${Math.round(r.projection)} yds`;
}

function Bar({ label, value, note }: { label: string; value: number | null; note?: string }) {
  return (
    <div className="grid grid-cols-[7rem_1fr_auto] items-center gap-3 py-0.5">
      <span className="text-sm text-muted">{label}</span>
      <span className="h-2 bg-line" aria-hidden>{value !== null && <span className="block h-2 bg-accent" style={{ width: `${Math.max(2, value)}%` }} />}</span>
      <span className="w-40 text-right text-sm text-slate-300">{value === null ? "no data" : `${Math.round(value)} of 100`}{note ? ` · ${note}` : ""}</span>
    </div>
  );
}

function Row({ r, unit, open, onToggle, onOpenGame, rank }: { r: RankRow; unit: string; open: boolean; onToggle: () => void; onOpenGame: (gid: string) => void; rank: number }) {
  const range = r.range_low !== null && r.range_high !== null ? `${Math.round(r.range_low)} to ${Math.round(r.range_high)}` : null;
  return (
    <li className="bg-panel">
      <button className="grid min-h-[64px] w-full grid-cols-[2rem_1fr_auto] items-center gap-x-3 gap-y-1 px-4 py-2.5 text-left hover:bg-line sm:grid-cols-[2.5rem_1fr_9rem_5.5rem]"
        aria-expanded={open} onClick={onToggle}>
        <span className="text-lg font-bold text-muted">{rank}</span>
        <span className="min-w-0">
          <span className="block truncate text-base font-semibold text-white">{r.player}</span>
          <span className="block truncate text-sm text-muted">{r.pos ?? ""}{r.pos ? " · " : ""}{r.team} {r.home ? "vs" : "at"} {r.opp} · {etTime(r.kickoff_utc).replace(":00 ", " ")}</span>
          <span className="block text-sm text-slate-300 sm:hidden">{show(r, unit)}{r.market_line !== null ? ` · line ${num(r.market_line, 1)}` : ""}</span>
        </span>
        <span className="hidden text-right sm:block">
          <span className="block text-base text-white">{show(r, unit)}</span>
          <span className="block text-sm text-muted">{r.market_line !== null ? `line ${num(r.market_line, 1)}` : range ? `range ${range}` : ""}</span>
        </span>
        <span className="justify-self-end bg-accent px-3 py-1.5 text-lg font-bold text-bg" aria-label={`Score ${r.score.toFixed(1)}`}>{r.score.toFixed(1)}</span>
      </button>
      {open && (
        <div className="space-y-2 px-4 pb-4 pt-1 sm:pl-[4.25rem]">
          <div>
            <Bar label="Projection" value={r.parts.projection} />
            <Bar label="Matchup" value={r.parts.matchup} />
            <Bar label="Usage" value={r.parts.usage} />
          </div>
          {r.tags.length > 0 && <div className="flex flex-wrap gap-1.5">{r.tags.map((t) => <Badge key={t} tone={t === "Questionable" ? "amber" : "neutral"}>{t}</Badge>)}</div>}
          {range && <div className="text-sm text-muted">Projected {show(r, unit)}; 8 in 10 games land between {range}.</div>}
          {r.exp_td !== undefined && <div className="text-sm text-muted">About {num(r.exp_td, 2)} expected touchdowns, from the team's expected points and who scores for it.</div>}
          <button className="min-h-[44px] bg-line px-4 text-[15px] text-white hover:bg-white hover:text-bg" onClick={() => onOpenGame(r.gid)}>Open the game</button>
          {unit === "chance" && <TdCard gid={r.gid} team={r.team} player={r.player} />}
        </div>
      )}
    </li>
  );
}

export function RankingsView({ week, onOpenGame }: { week: number; onOpenGame: (gid: string) => void }) {
  const [data, setData] = useState<Rankings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stat, setStat] = useState<string>("rec_yds");
  const [dayKey, setDayKey] = useState<string>("All days");
  const [openKey, setOpenKey] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setData(null);
    setError(null);
    api.rankings(week).then((x) => { if (alive) setData(x); }).catch((e) => { if (alive) setError(String(e)); });
    return () => { alive = false; };
  }, [week]);

  const cur = data?.stats[stat];
  const days = useMemo(() => {
    const seen: string[] = [];
    [...(cur?.rows ?? [])].sort((x, y) => x.kickoff_utc.localeCompare(y.kickoff_utc)).forEach((r) => { const d = day(r.kickoff_utc); if (!seen.includes(d)) seen.push(d); });
    return seen;
  }, [cur]);
  useEffect(() => { if (dayKey !== "All days" && !days.includes(dayKey)) setDayKey("All days"); }, [days, dayKey]);

  if (error) return <Callout tone="amber">Could not load the rankings ({error}).</Callout>;
  if (!data) return <div className="text-muted">Ranking every player in week {week}… the first load takes about 15 seconds.</div>;
  const labels = Object.fromEntries(Object.entries(data.stats).map(([k, v]) => [v.label, k]));
  const rows = (cur?.rows ?? []).filter((r) => dayKey === "All days" || day(r.kickoff_utc) === dayKey);
  const w = data.weights;

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-bold text-white">Player rankings, week {week}</h2>
        <p className="mt-1 max-w-3xl text-[15px] text-muted">Every player in the week's games, ranked by a 0 to 100 score for one prop. Tap a player for what is behind the score.</p>
      </div>
      <Segmented label="Prop" options={Object.keys(labels)} value={cur?.label ?? ""} onChange={(l) => { setStat(labels[l]); setOpenKey(null); }} />
      {days.length > 1 && <Segmented label="Day" options={["All days", ...days]} value={dayKey} onChange={(d) => { setDayKey(d); setOpenKey(null); }} />}
      {rows.length === 0 ? <Callout tone="blue">No players meet the minimum projection for this prop on this day.</Callout> : (
        <ol className="space-y-0.5">
          {rows.map((r, i) => {
            const k = `${r.gid}-${r.player}-${r.stat}`;
            return <Row key={k} r={r} unit={cur!.unit} rank={i + 1} open={openKey === k} onToggle={() => setOpenKey(openKey === k ? null : k)} onOpenGame={onOpenGame} />;
          })}
        </ol>
      )}
      <Card className="text-sm leading-relaxed text-muted">
        <b className="text-slate-300">How the score works.</b> {pct(w.projection)} the player's projected number, {pct(w.matchup)} how much the opposing defense moves it (its record against the position
        over its last six games), {pct(w.usage)} usage (target share for receiving, carry share for rushing, from FantasyPoints). Each part is the player's rank among this week's list, 0 to 100;
        a part with no data is left out. Passing yards have no usage part. On games already played this season, the top 10 by score each week averaged about 75 receiving yards against 36 for all players,
        but the blended score ordered players no better than the projection alone, so read it as a way to sort, not a signal on its own.
        Anytime touchdown is the chance of at least one rushing or receiving touchdown; it ran close to actual results for the likeliest scorers and low for long shots.
        "Above the line" and "Below the line" only say the projection sits 10% or more above or below a market line. None of this has been shown to beat the market, and it is not betting advice.
      </Card>
    </div>
  );
}
