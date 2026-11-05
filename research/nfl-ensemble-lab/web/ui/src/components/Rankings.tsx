import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { RankRow, Rankings } from "../types";
import { cn, etTime, num, pct } from "../lib";
import { Callout, FilterRow, Segmented } from "./ui/primitives";
import { TdCard } from "./TdCard";
import { Pick } from "./Leans";

const day = (iso: string) => new Date(iso).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", timeZone: "America/New_York" });
const PAGE = 15;

const value = (r: RankRow, unit: string) => (unit === "chance" ? pct(r.projection) : unit === "rec" ? num(r.projection, 1) : String(Math.round(r.projection)));
const unitWord = (unit: string) => (unit === "chance" ? "" : unit === "rec" ? " catches" : " yards");

// The range column: a bar for the 8 in 10 range with the projection tick and a yellow market tick, or a plain chance bar.
function Gauge({ r, unit, top }: { r: RankRow; unit: string; top: number }) {
  const X = (v: number) => (v / top) * 100;
  const dec = unit === "rec" ? 1 : 0;
  if (unit === "chance") {
    return (
      <div className="relative h-7" role="img" aria-label={`Chance ${pct(r.projection)}`}>
        <span className="absolute inset-x-0 top-[11px] h-1.5 bg-raised" />
        <span className="absolute left-0 top-[11px] h-1.5 bg-white" style={{ width: `${r.projection * 100}%` }} />
      </div>
    );
  }
  if (r.range_low === null || r.range_high === null) return <div className="h-7 text-[13px] leading-7 text-muted">No range yet</div>;
  return (
    <div className="relative h-7" role="img" aria-label={`8 in 10 range ${r.range_low.toFixed(dec)} to ${r.range_high.toFixed(dec)}`}>
      <span className="absolute top-[11px] h-1.5 bg-chart" style={{ left: `${X(r.range_low)}%`, width: `${X(r.range_high - r.range_low)}%` }} />
      <span className="absolute top-1 -ml-px h-5 w-[3px] bg-white" style={{ left: `${X(r.projection)}%` }} />
      {r.market_line !== null && <span className="absolute top-0 h-7 w-0.5 bg-accent" style={{ left: `${X(r.market_line)}%` }} />}
    </div>
  );
}

function Part({ label, weight, v }: { label: string; weight: number; v: number | null }) {
  return (
    <div className="grid min-h-7 grid-cols-[7rem_1fr_4.6rem] items-center gap-2 text-sm sm:grid-cols-[8.5rem_1fr_5rem]">
      <span>{label}, {pct(weight)}</span>
      <span className="h-1.5 bg-raised" aria-hidden>{v !== null && <i className="block h-1.5 bg-white" style={{ width: `${Math.max(2, v)}%` }} />}</span>
      <span className="text-right text-muted">{v === null ? "no data" : `${Math.round(v)} of 100`}</span>
    </div>
  );
}

function Detail({ r, unit, weights, onOpenGame }: { r: RankRow; unit: string; weights: Record<string, number>; onOpenGame: (gid: string) => void }) {
  const dec = unit === "rec" ? 1 : 0;
  const range = r.range_low !== null && r.range_high !== null ? `${r.range_low.toFixed(dec)} to ${r.range_high.toFixed(dec)}` : null;
  return (
    <div className={cn("grid gap-0.5 px-0 pb-4 sm:px-4 xl:pl-[4.5rem]", unit === "chance" ? "xl:grid-cols-[5fr_7fr]" : "xl:grid-cols-[minmax(0,640px)]")}>
      <div className="bg-panel2 p-4">
        <h2 className="mb-2 text-base font-semibold text-white">Behind the score</h2>
        <Part label="Projection" weight={weights.projection} v={r.parts.projection} />
        <Part label="Matchup" weight={weights.matchup} v={r.parts.matchup} />
        <Part label="Usage" weight={weights.usage} v={r.parts.usage} />
        <p className="mt-2 text-sm text-muted">Each part is the player's rank among this week's list.</p>
        {r.tags.length > 0 && <div className="mt-4 flex flex-wrap gap-x-2 gap-y-1">{r.tags.map((t) => <span key={t} className="bg-raised px-2 py-0.5 text-sm">{t}</span>)}</div>}
        {range && unit !== "chance" && <p className="mt-4 text-sm text-muted">Projected {value(r, unit)}{unitWord(unit)}; 8 in 10 games land between {range}.</p>}
        {r.exp_td !== undefined && <p className="mt-4 text-sm text-muted">About {num(r.exp_td, 2)} expected touchdowns, from the team's expected points and who scores for it.</p>}
        {(r.stat === "td" || r.stat === "first_td") && (
          <div className="mt-4">
            <h3 className="text-[15px] font-semibold text-white">Red-zone usage</h3>
            {r.red_zone ? (
              <dl className="mt-1 grid grid-cols-[1fr_auto] gap-x-4 gap-y-0.5 text-[15px]">
                {r.red_zone.ez_tgt !== null && <><dt className="text-muted">End-zone targets a game</dt><dd className="text-right font-semibold">{num(r.red_zone.ez_tgt, 1)}</dd></>}
                {r.red_zone.i20_tgt !== null && <><dt className="text-muted">Targets inside the 20 a game</dt><dd className="text-right font-semibold">{num(r.red_zone.i20_tgt, 1)}</dd></>}
                {r.red_zone.i5_carry_share !== null && <><dt className="text-muted">Inside-5 carry share (I5%)</dt><dd className="text-right font-semibold">{pct(r.red_zone.i5_carry_share)}</dd></>}
              </dl>
            ) : <p className="text-sm text-muted">FantasyPoints has no red-zone numbers for this player yet.</p>}
            <p className="mt-1 text-sm text-muted">FantasyPoints, last {r.red_zone?.weeks || 6} weeks. Receiving touchdown shares weight end-zone and inside-20 targets at 20%, which passed testing. Inside-5 carry share did not improve the rushing split, so they are shown and not used.</p>
          </div>
        )}
        {r.stat === "first_td" && <p className="mt-2 text-sm text-muted">First touchdown is the chance the game has a touchdown at all, times his share of the game's expected touchdowns. It is an estimate that has not been checked against results.</p>}
        <button type="button" className="mt-4 min-h-[44px] bg-white px-4 font-semibold text-bg hover:bg-white" onClick={() => onOpenGame(r.gid)}>Open the game</button>
      </div>
      {unit === "chance" && (
        <div className="bg-panel2 p-4">
          <h2 className="mb-1 text-base font-semibold text-white">Touchdown card</h2>
          <TdCard gid={r.gid} team={r.team} player={r.player} />
        </div>
      )}
    </div>
  );
}

export function RankingsView({ week, onOpenGame }: { week: number; onOpenGame: (gid: string) => void }) {
  const [data, setData] = useState<Rankings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stat, setStat] = useState("rec_yds");
  const [dayKey, setDayKey] = useState("All days");
  const [gameKey, setGameKey] = useState("All games");
  const [openKey, setOpenKey] = useState<string | null>(null);
  const [shown, setShown] = useState(PAGE);

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
  const games = useMemo(() => {
    const seen = new Map<string, { t: string; k: string }>();
    [...(cur?.rows ?? [])].sort((x, y) => x.kickoff_utc.localeCompare(y.kickoff_utc)).forEach((r) => {
      if (!seen.has(r.gid)) seen.set(r.gid, { t: r.home ? `${r.opp} at ${r.team}` : `${r.team} at ${r.opp}`, k: r.kickoff_utc });
    });
    return [...seen.entries()].map(([v, o]) => ({ v, t: `${o.t}, ${day(o.k)}` }));
  }, [cur]);
  useEffect(() => { if (gameKey !== "All games" && !games.some((g) => g.v === gameKey)) setGameKey("All games"); }, [games, gameKey]);
  useEffect(() => { if (dayKey !== "All days" && !days.includes(dayKey)) setDayKey("All days"); }, [days, dayKey]);

  if (error) return <Callout tone="amber">Could not load the rankings ({error}).</Callout>;
  if (!data || !cur) return <p className="text-muted" role="status">Ranking every player in week {week}… the first load takes about 15 seconds.</p>;

  const labels = Object.fromEntries(Object.entries(data.stats).map(([k, v]) => [v.label, k]));
  const rows = cur.rows.filter((r) => (dayKey === "All days" || day(r.kickoff_utc) === dayKey) && (gameKey === "All games" || r.gid === gameKey));
  const visible = rows.slice(0, shown);
  const w = data.weights, unit = cur.unit;
  const lead = rows[0];

  // One scale per prop, so bars compare across rows and across days.
  const mx = Math.max(1, ...cur.rows.map((r) => Math.max(r.range_high ?? 0, r.market_line ?? 0, r.projection)));
  const step = unit === "chance" ? (mx <= 0.3 ? 0.05 : 0.25) : mx > 400 ? 100 : mx > 150 ? 50 : mx > 60 ? 25 : mx > 12 ? 5 : 2;
  const top = unit === "chance" ? (mx <= 0.3 ? Math.ceil(mx / step) * step : 1) : Math.ceil(mx / step) * step;
  const ticks: number[] = [];
  for (let v = 0; v <= top + 1e-9; v += step) ticks.push(v);

  return (
    <div className="space-y-4">
      <div>
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <h1 className="text-[22px] font-bold leading-tight text-white sm:text-2xl">Player rankings, week {week}</h1>
          {lead && <p className="text-accent" aria-live="polite">{lead.player} leads {cur.label.toLowerCase()}{dayKey === "All days" ? "" : `, ${dayKey}`}: {value(lead, unit)}{unitWord(unit)}.</p>}
        </div>
        <p className="mt-2 max-w-[75ch] text-sm text-muted">Ranked by a 0 to 100 score for one prop. The score only sorts players: on played 2026 weeks it ordered them no better than the projection alone.</p>
      </div>

      <div className="space-y-2">
        <FilterRow label="Prop"><Segmented label="Prop" options={Object.keys(labels)} value={cur.label} onChange={(l) => { setStat(labels[l]); setOpenKey(null); setShown(PAGE); }} /></FilterRow>
        {games.length > 1 && <div className="max-w-md"><Pick label="Game" value={gameKey} onChange={(g) => { setGameKey(g); setOpenKey(null); setShown(PAGE); }} options={[{ v: "All games", t: "All games" }, ...games]} /></div>}
        {days.length > 1 && <FilterRow label="Day"><Segmented label="Day" options={["All days", ...days]} value={dayKey} onChange={(d) => { setDayKey(d); setOpenKey(null); setShown(PAGE); }} /></FilterRow>}
      </div>

      {rows.length === 0 ? <Callout tone="blue">No players meet the minimum projection for this prop on this day.</Callout> : (
        <div>
          <div className="hidden grid-cols-[2.5rem_minmax(0,1.3fr)_8rem_minmax(0,1fr)_4.5rem] gap-x-3 px-4 pb-2 text-[13px] text-muted sm:grid" aria-hidden>
            <span>Rank</span><span>Player</span><span className="text-right">{unit === "chance" ? "Our chance" : "Projection"}</span>
            <span>{unit === "chance" ? "Chance" : "8 in 10 range"}<span className="relative block h-4 font-normal">{ticks.map((v) => <span key={v} className="absolute -translate-x-1/2" style={{ left: `${(v / top) * 100}%` }}>{unit === "chance" ? `${Math.round(v * 100)}%` : v}</span>)}</span></span>
            <span className="text-right">Score</span>
          </div>
          <ol className="space-y-0.5">
            {visible.map((r, i) => {
              const k = `${r.gid}-${r.player}-${r.stat}`, open = openKey === k;
              const sub = unit === "chance" ? (r.exp_td !== undefined ? `${num(r.exp_td, 1)} expected TDs` : "") : r.market_line !== null ? `Market line ${num(r.market_line, 1)}` : "";
              return (
                <li key={k} className="bg-panel">
                  <button type="button" aria-expanded={open} onClick={() => setOpenKey(open ? null : k)}
                    className="grid min-h-[64px] w-full grid-cols-[2rem_minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 px-4 py-2 text-left transition-colors hover:bg-raised focus-visible:outline-offset-[-3px] sm:grid-cols-[2.5rem_minmax(0,1.3fr)_8rem_minmax(0,1fr)_4.5rem] max-sm:pb-3">
                    <span className="col-start-1 text-lg font-bold text-muted">{i + 1}</span>
                    <span className="col-start-2 min-w-0">
                      <b className="block truncate text-base">{r.player}</b>
                      <span className="block truncate text-sm text-muted">{r.pos}, {r.team} {r.home ? "vs" : "at"} {r.opp}, {etTime(r.kickoff_utc).replace(":00 ", " ")}{r.tags.includes("Questionable") ? ", questionable" : ""}</span>
                    </span>
                    <span className="col-start-3 row-start-1 justify-self-end bg-raised px-2 py-1.5 text-center text-lg font-bold sm:col-start-5" aria-label={`Score ${r.score.toFixed(1)}`}>{r.score.toFixed(1)}</span>
                    <span className="col-span-2 col-start-2 row-start-2 flex items-baseline gap-2 sm:col-span-1 sm:col-start-3 sm:row-start-1 sm:block sm:text-right">
                      <b className="text-xl leading-tight">{value(r, unit)}</b>
                      <span className={cn("block whitespace-nowrap text-[13px]", r.market_line !== null ? "text-accent" : "text-muted")}>{sub}</span>
                    </span>
                    <span className="col-span-2 col-start-2 row-start-3 sm:col-span-1 sm:col-start-4 sm:row-start-1"><Gauge r={r} unit={unit} top={top} /></span>
                  </button>
                  {open && <Detail r={r} unit={unit} weights={w} onOpenGame={onOpenGame} />}
                </li>
              );
            })}
          </ol>
          {rows.length > shown && <button type="button" className="mt-0.5 min-h-[48px] w-full bg-panel text-[15px] hover:bg-raised" onClick={() => setShown((n) => n + PAGE)}>Show {Math.min(PAGE, rows.length - shown)} more of {rows.length - shown} left</button>}
        </div>
      )}

      <details className="bg-panel">
        <summary className="flex min-h-[48px] cursor-pointer items-center px-4 text-[15px]">How the score works</summary>
        <div className="grid max-w-[80ch] gap-2 px-4 pb-4 text-sm text-muted">
          <p>The score is the player's rank on three parts, each 0 to 100: {pct(w.projection)} the projected number, {pct(w.matchup)} how much the opposing defense moves it (its record against the position over its last six games), and {pct(w.usage)} usage (target share for receiving, carry share for rushing, from FantasyPoints). A part with no data is left out. Passing yards have no usage part.</p>
          <p>On games already played this season, the top 10 by score each week averaged about 75 receiving yards against 36 for all players. The blended score ordered players no better than the projection alone, so read it as a way to sort, not a signal on its own.</p>
          <p>Anytime touchdown is the chance of at least one rushing or receiving touchdown. It ran close to actual results for the likeliest scorers and low for long shots. "Above the line" and "Below the line" only say the projection sits 10% or more above or below a market line. None of this has been shown to beat the market, and it is not betting advice.</p>
        </div>
      </details>
    </div>
  );
}
