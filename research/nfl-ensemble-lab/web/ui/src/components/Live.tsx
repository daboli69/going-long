import { useCallback, useEffect, useState } from "react";
import { api, NotCaptured } from "../api";
import type { Detail, Live, LiveRow, LiveTd } from "../types";
import { cn, pct } from "../lib";
import { Callout, FilterRow, Segmented } from "./ui/primitives";
import { Num } from "./motion";

const STATS = ["Passing yards", "Rushing yards", "Receiving yards", "Receptions", "Touchdowns"];
const COLS = "grid-cols-[minmax(0,1fr)_4em_4.5em_4.5em] sm:grid-cols-[minmax(0,1fr)_6em_9em_9em_8em]";
const NOUN: Record<string, string> = { "Passing yards": "pass attempts", "Rushing yards": "carries", "Receiving yards": "targets", Receptions: "targets" };

const clock = (s: number | null) => (s === null ? "" : `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`);
const ago = (s: number) => (s < 5 ? "just now" : s < 90 ? `${s} seconds ago` : `${Math.round(s / 60)} minutes ago`);

function status(l: Live): string {
  if (l.state === "post") return "Final";
  if (l.state === "pre") return "Not started";
  if (l.period === null) return "In progress";
  return `${l.period <= 4 ? `Q${l.period}` : "OT"} ${clock(l.clock)}`;
}

function TdRow({ r }: { r: LiveTd }) {
  return (
    <div role="row" className="grid min-h-[48px] grid-cols-[minmax(0,1fr)_4em_4.5em_4.5em] items-center gap-x-3 border-t border-bg py-2 sm:grid-cols-[minmax(0,1fr)_6em_7em_7em]">
      <div role="cell" className="min-w-0 text-[15px]">{r.name} <span className="text-[13px] text-muted">{r.team}</span></div>
      <div role="cell" className="text-right text-[15px]">{r.td_so_far}</div>
      <div role="cell" className="text-right text-[15px] text-muted">{r.chance_pre === null ? "Not modeled" : pct(r.chance_pre)}</div>
      <div role="cell" className="text-right text-xl font-bold">{r.scored ? "Scored" : <Num value={r.chance_now} pct />}</div>
    </div>
  );
}

function Row({ r }: { r: LiveRow }) {
  const dec = r.stat === "Receptions" ? 1 : 0;
  const moved = r.updated - r.frozen;
  return (
    <div role="row" className={cn("grid min-h-[48px] items-center gap-x-3 border-t border-bg py-2", COLS)}>
      <div role="cell" className="min-w-0 text-[15px]">{r.name} <span className="text-[13px] text-muted">{r.team}</span>
        <span className="block text-[13px] text-muted">{r.targets_or_carries} {r.targets_or_carries === 1 ? NOUN[r.stat].replace(/s$/, "") : NOUN[r.stat]} so far</span></div>
      <div role="cell" className="text-right text-[15px]"><Num value={r.yards} dec={dec} /></div>
      <div role="cell" className="text-right text-[15px] text-muted">{r.frozen.toFixed(dec)}</div>
      <div role="cell" className="text-right text-xl font-bold"><Num value={r.updated} dec={dec} />
        <span className="block text-[13px] font-normal text-muted">{moved >= 0 ? "+" : "−"}{Math.abs(moved).toFixed(dec)}</span></div>
      <div role="cell" className="hidden text-right text-[15px] text-muted sm:block">{r.low.toFixed(dec)} to {r.high.toFixed(dec)}</div>
    </div>
  );
}

// Newest captured snapshot of the game: updated player projections next to the frozen pregame ones, role warnings, and the live win chance.
export function LiveGame({ d, onFinished }: { d: Detail; onFinished?: () => void }) {
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
  useEffect(() => { if (live?.state === "post") onFinished?.(); }, [live?.state, onFinished]);
  useEffect(() => {
    if (live?.state !== "in") return;
    const t = window.setInterval(load, 15000);
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
  const tds = (live.touchdowns ?? []).filter((r) => team === "Both" || r.team === team);
  const unit = stat === "Receptions" ? "Catches" : "Yards";
  return (
    <div className="space-y-4">
      <section aria-label="Game state" className="grid grid-cols-1 items-end gap-x-8 gap-y-3 bg-panel px-4 py-4 sm:grid-cols-[auto_1fr_1fr] sm:px-6">
        <div>
          <div className="text-[13px] text-muted">{status(live)}</div>
          <div className="fig text-[44px] sm:text-[56px]"><Num value={live.score.away} /> <span className="text-muted">–</span> <Num value={live.score.home} /></div>
          <div className="text-[13px] text-muted">{d.away} at {d.home}</div>
        </div>
        <div className="sm:border-l sm:border-line sm:pl-6">
          <div className="text-[13px] text-muted">Win chance now</div>
          <div className="text-xl font-bold">{homeP === null ? "Not available" : homeP >= 0.5 ? <>{d.home} <Num value={homeP} pct /></> : <>{d.away} <Num value={1 - homeP} pct /></>}</div>
        </div>
        <div className="sm:border-l sm:border-line sm:pl-6">
          <div className="text-[13px] text-muted">Newest play in the feed</div>
          <div className="text-xl font-bold">{live.newest_play_seconds === null ? "Not shown" : ago(live.newest_play_seconds)}</div>
          <div className="text-[13px] text-muted">{live.feed_lag ? `ESPN usually shows a play ${live.feed_lag.median.toFixed(0)} seconds late (9 in 10 within ${live.feed_lag.p90.toFixed(0)}), from ${live.feed_lag.n} plays` : "ESPN delay not measured yet"}</div>
        </div>
      </section>
      {live.last_play && <p className="text-[15px] text-muted">Last play: {live.last_play.trim()}</p>}
      {live.state === "in" && live.newest_play_seconds !== null && live.newest_play_seconds > Math.max(180, (live.feed_lag?.p90 ?? 0) + 120) && (
        <Callout tone="amber">No new play has appeared for {ago(live.newest_play_seconds)}. That is longer than the usual ESPN delay, so this may be a timeout or review, or the feed may be behind. Treat these numbers as older than they look.</Callout>
      )}
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
      {stat === "Touchdowns" ? (
        <section aria-label="Touchdowns live" className="bg-panel p-4 sm:p-6">
          <p className="mb-3 text-[15px] text-slate-300">
            {live.first_td ? `First touchdown of the game: ${live.first_td.text}${live.first_td.period ? ` (Q${live.first_td.period}${live.first_td.clock ? ` ${live.first_td.clock}` : ""})` : ""}` : "No touchdown has been scored yet."}
          </p>
          <div role="table" aria-label="Touchdowns, so far and chance to score">
            <div role="row" className="grid grid-cols-[minmax(0,1fr)_4em_4.5em_4.5em] gap-x-3 text-[13px] text-muted sm:grid-cols-[minmax(0,1fr)_6em_7em_7em]">
              <div role="columnheader">Player</div><div role="columnheader" className="text-right">Scored so far</div>
              <div role="columnheader" className="text-right">Chance before kickoff</div><div role="columnheader" className="text-right">Chance now</div>
            </div>
            {tds.length ? tds.map((r) => <TdRow key={`${r.team}${r.name}`} r={r} />) : <p role="row" className="py-4 text-sm text-muted">No touchdown chances are available for this game yet.</p>}
          </div>
        </section>
      ) : (
      <section aria-label={`${stat} live`} className="bg-panel p-4 sm:p-6">
        <div role="table" aria-label={`${stat}, live and pregame`}>
          <div role="row" className={cn("grid gap-x-3 text-[13px] text-muted", COLS)}>
            <div role="columnheader">Player</div><div role="columnheader" className="text-right">{unit} so far</div>
            <div role="columnheader" className="text-right">Expected final, before kickoff</div><div role="columnheader" className="text-right">Expected final, now</div>
            <div role="columnheader" className="hidden text-right sm:block">Final {unit.toLowerCase()}, 8 in 10 range</div>
          </div>
          {rows.length ? rows.map((r) => <Row key={`${r.team}${r.name}${r.stat}`} r={r} />) : <p role="row" className="py-4 text-sm text-muted">No tracked {stat.toLowerCase()} for this selection.</p>}
        </div>
      </section>
      )}
      <p className="max-w-[75ch] text-sm text-muted">
        Read each row left to right: what the player has so far, what the tracker expected him to finish with before kickoff, and what it expects now given the score, the clock and what he has done.
        {stat === "Touchdowns" && " Touchdown chance now is his pregame chance scaled by the time left and by any change in his share of his team's attempts. It does not yet account for the score or field position, and it has not been checked against results."} The small number under the last column is the change since kickoff. The line under his name counts his targets, carries or pass attempts so far.
        {live.frozen && ` Pregame numbers were frozen ${live.frozen.before_kickoff ? "before" : "after"} kickoff (hash ${live.frozen.sha256.slice(0, 10)}).`}
        {live.frozen && !live.frozen.before_kickoff && " Frozen after kickoff, so this game is not a clean pregame test."}
        {" "}Snaps and routes are not in the live feed, so opportunity means targets, carries and pass attempts.
      </p>
    </div>
  );
}
