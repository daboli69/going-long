import { useCallback, useEffect, useState } from "react";
import { api, NotCaptured } from "../api";
import type { Detail, Live, LiveRow } from "../types";
import { cn, pct } from "../lib";
import { Callout, FilterRow, Segmented } from "./ui/primitives";

const STATS = ["Passing yards", "Rushing yards", "Receiving yards"];
const COLS = "grid-cols-[minmax(0,1fr)_3.5em_3.5em_3.5em] sm:grid-cols-[minmax(0,1fr)_4.5em_4.5em_4.5em_7em]";

const clock = (s: number | null) => (s === null ? "" : `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`);
const when = (stamp: string) => `${stamp.slice(9, 11)}:${stamp.slice(11, 13)} UTC`;

function status(l: Live): string {
  if (l.state === "post") return "Final";
  if (l.state === "pre") return "Not started";
  if (l.period === null) return "In progress";
  return `${l.period <= 4 ? `Q${l.period}` : "OT"} ${clock(l.clock)}`;
}

function Row({ r }: { r: LiveRow }) {
  const moved = r.updated - r.frozen;
  return (
    <div role="row" className={cn("grid min-h-[48px] items-center gap-x-3 border-t border-bg py-2", COLS)}>
      <div role="cell" className="min-w-0 text-[15px]">{r.name} <span className="text-[13px] text-muted">{r.team}</span>
        <span className="block text-[13px] text-muted">{r.targets_or_carries} so far</span></div>
      <div role="cell" className="text-right text-[15px]">{r.yards.toFixed(0)}</div>
      <div role="cell" className="text-right text-[15px] text-muted">{r.frozen.toFixed(0)}</div>
      <div role="cell" className="text-right text-xl font-bold">{r.updated.toFixed(0)}
        <span className="block text-[13px] font-normal text-muted">{moved >= 0 ? "+" : "−"}{Math.abs(moved).toFixed(0)}</span></div>
      <div role="cell" className="hidden text-right text-[15px] text-muted sm:block">{r.low.toFixed(0)} to {r.high.toFixed(0)}</div>
    </div>
  );
}

// Newest captured snapshot of the game: updated player projections next to the frozen pregame ones, role warnings, and the live win chance.
export function LiveGame({ d }: { d: Detail }) {
  const [live, setLive] = useState<Live | null>(null);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [stat, setStat] = useState("Passing yards");
  const [team, setTeam] = useState("Both");

  const load = useCallback(() => {
    api.live(d.gid).then((l) => { setLive(l); setMissing(false); setError(null); })
      .catch((e) => { if (e instanceof NotCaptured) { setMissing(true); setLive(null); setError(null); } else setError(String(e)); })
      .finally(() => setLoading(false));
  }, [d.gid]);

  useEffect(() => { setLoading(true); setLive(null); setMissing(false); setError(null); load(); }, [load]);
  useEffect(() => {
    if (live?.state !== "in") return;
    const t = window.setInterval(load, 30000);
    return () => window.clearInterval(t);
  }, [live?.state, load]);

  if (loading) return <Callout tone="blue">Loading the latest snapshot.</Callout>;
  if (error) return <Callout tone="amber">The live data could not be loaded ({error}). <button type="button" onClick={load} className="underline">Try again</button></Callout>;
  if (missing || !live) {
    return (
      <Callout tone="blue">
        No snapshot of this game has been saved yet. The tracker only shows games recorded while they were being played. Start the recorder with <code>scripts\ingame_capture.py</code> before kickoff.
      </Callout>
    );
  }
  const homeP = live.win_chance_home;
  const rows = live.players.filter((r) => r.stat === stat && (team === "Both" || r.team === team)).sort((a, b) => b.updated - a.updated);
  return (
    <div className="space-y-4">
      <section aria-label="Game state" className="grid grid-cols-1 gap-0.5 sm:grid-cols-3">
        <div className="bg-panel p-4"><div className="text-[13px] text-muted">{status(live)}</div>
          <div className="text-xl font-bold">{d.away} {live.score.away}, {d.home} {live.score.home}</div></div>
        <div className="bg-panel p-4"><div className="text-[13px] text-muted">Win chance now</div>
          <div className="text-xl font-bold">{homeP === null ? "Not available" : homeP >= 0.5 ? `${d.home} ${pct(homeP)}` : `${d.away} ${pct(1 - homeP)}`}</div></div>
        <div className="bg-panel p-4"><div className="text-[13px] text-muted">Last snapshot</div>
          <div className="text-xl font-bold">{when(live.snapshot)}</div></div>
      </section>
      {live.last_play && <p className="text-[15px] text-muted">Last play: {live.last_play.trim()}</p>}
      {homeP === null && <Callout tone="amber">The win chance needs a frozen pregame margin for this game, and none was saved.</Callout>}
      {live.warnings.length > 0 ? (
        <Callout tone="amber">
          Role changes: {live.warnings.map((w) => `${w.name} (${w.team}) has ${w.targets_or_carries} of ${w.team_attempts} team attempts, a ${pct(w.share_post)} share against ${pct(w.share_pre)} before the game`).join("; ")}.
        </Callout>
      ) : (
        <p className="text-[15px] text-muted">No role changes flagged. A warning needs at least 12 team attempts and a clear shift in a player's share.</p>
      )}
      <div className="space-y-2">
        <FilterRow label="Stat"><Segmented label="Stat" options={STATS} value={stat} onChange={setStat} /></FilterRow>
        <FilterRow label="Team"><Segmented label="Team" options={["Both", d.away, d.home]} value={team} onChange={setTeam} /></FilterRow>
      </div>
      <section aria-label={`${stat} live`} className="bg-panel p-4 sm:p-6">
        <div role="table" aria-label={`${stat}, live and pregame`}>
          <div role="row" className={cn("grid gap-x-3 text-[13px] text-muted", COLS)}>
            <div role="columnheader">Player</div><div role="columnheader" className="text-right">Now</div>
            <div role="columnheader" className="text-right">Pregame</div><div role="columnheader" className="text-right">Updated</div>
            <div role="columnheader" className="hidden text-right sm:block">8 in 10 range</div>
          </div>
          {rows.length ? rows.map((r) => <Row key={`${r.team}${r.name}${r.stat}`} r={r} />) : <p role="row" className="py-4 text-sm text-muted">No tracked {stat.toLowerCase()} for this selection.</p>}
        </div>
      </section>
      <p className="max-w-[75ch] text-sm text-muted">
        Updated is the final total the tracker expects, given the score, the clock and what each player has done so far. Pregame is the same model at kickoff.
        {live.frozen && ` Pregame numbers were frozen ${live.frozen.before_kickoff ? "before" : "after"} kickoff (hash ${live.frozen.sha256.slice(0, 10)}).`}
        {live.frozen && !live.frozen.before_kickoff && " Frozen after kickoff, so this game is not a clean pregame test."}
        {" "}Snaps and routes are not in the live feed, so opportunity means targets, carries and pass attempts.
      </p>
    </div>
  );
}
