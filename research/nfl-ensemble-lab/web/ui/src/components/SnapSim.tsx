import { useEffect, useState } from "react";
import { api } from "../api";
import type { GameRow, SnapSim } from "../types";
import { Callout } from "./ui/primitives";
import { Pick } from "./Leans";

const pct = (x: number | null | undefined, d = 1) => (x === null || x === undefined || Number.isNaN(x) ? "n/a" : `${(x * 100).toFixed(d)}%`);
const n1 = (x: number | null | undefined) => (x === null || x === undefined ? "n/a" : x.toFixed(1));
const COLS: [string, string][] = [["pass_yds", "Pass yds"], ["comp", "Comp"], ["rec", "Rec"], ["rec_yds", "Rec yds"], ["car", "Carries"], ["rush_yds", "Rush yds"]];

export function SnapSimView({ games, gid, onPick }: { games: GameRow[]; gid: string | null; onPick: (g: string) => void }) {
  const [d, setD] = useState<SnapSim | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!gid) return;
    setD(null); setErr(null); setBusy(true);
    api.snapsim(gid).then(setD).catch((e) => setErr(String(e.message ?? e))).finally(() => setBusy(false));
  }, [gid]);

  const rerun = () => { if (gid) { setBusy(true); api.snapsim(gid, true).then(setD).catch((e) => setErr(String(e.message ?? e))).finally(() => setBusy(false)); } };
  const v1 = d?.validation?.v1;
  const v2 = d?.validation?.v2;
  const a = d?.adjustments;

  return (
    <section aria-labelledby="snap-h" className="space-y-6">
      <div>
        <h2 id="snap-h" className="text-xl font-bold">Snap simulator</h2>
        <p className="mt-1 max-w-3xl text-[15px] text-muted">Every game is played 10,000 times one snap at a time, using each team's real 2026 tendencies: pass and run mix by down and distance, fourth-down habits, pressure and blitz, run gaps, penalties and the clock, plus the real players on each roster. It never looks at the betting line; the line is used afterward only to turn simulated scores into cover and over percentages. Past results of a model, not advice and not a staking plan.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <Pick label="Game" value={gid ?? ""} onChange={onPick} options={games.map((g) => ({ v: g.gid, t: `${g.away} at ${g.home}` }))} />
      </div>
      {busy && !d && <p className="text-muted">Running 10,000 simulated games. The first run takes about a minute; later views are instant.</p>}
      {err && <Callout tone="amber">Could not run the simulator: {err}</Callout>}
      {d && a && (
        <>
          <Callout tone={d.frozen ? "green" : "blue"}>
            {d.frozen ? `Saved before kickoff (write-once file, hash ${d.sha256?.slice(0, 12)}${d.frozen_ok ? ", intact" : ", DOES NOT MATCH"}).` : "Live run, not yet saved. A write-once copy is saved before kickoff with scripts/snapsim_run.py --freeze."} {d.kickoff}. Rest: {d.away} {d.rest.away} days, {d.home} {d.rest.home} days.
          </Callout>
          <dl className="grid grid-cols-2 gap-px bg-bg text-[15px] sm:grid-cols-3 lg:grid-cols-6">
            {([[`${d.home} wins`, pct(d.win[d.home])], [`${d.away} wins`, pct(d.win[d.away])], [`${d.home} ${d.spread_home > 0 ? "-" : "+"}${Math.abs(d.spread_home)} covers`, pct(d.cover[d.home])], [`${d.away} ${d.spread_home > 0 ? "+" : "-"}${Math.abs(d.spread_home)} covers`, pct(d.cover[d.away])], [`Over ${d.total}`, pct(d.over)], [`Under ${d.total}`, pct(d.under)]] as const).map(([k, v]) => (
              <div key={k} className="bg-[#12161c] p-3"><dt className="text-[13px] text-muted">{k}</dt><dd className="text-xl font-bold">{v}</dd></div>
            ))}
          </dl>
          <p className="text-[13px] text-muted">Out of {d.sims.toLocaleString()} simulated games. With no home-field or rest adjustment the raw simulation has {d.home} winning {pct(d.raw_win[d.home])}, covering {pct(d.cover_raw[d.home])} with {pct(d.cover_raw.push)} pushes. The simulator scores {d.scoring_gap_per_team.toFixed(1)} fewer points per team than 2026 teams actually have (see the check at the bottom), so the totals above lean low. Adding that gap to both teams, the over {d.total} would be {pct(d.over_scoring_adjusted)}. Median score {d.home} {n1(d.score.home.median)}, {d.away} {n1(d.score.away.median)}; 8 in 10 totals fall between {n1(d.score.total.p10)} and {n1(d.score.total.p90)}.</p>

          <div>
            <h3 className="text-lg font-bold">Other lines</h3>
            <p className="mt-1 text-[13px] text-muted">The schedule file's current line is {d.home} {d.spread_home > 0 ? "-" : "+"}{Math.abs(d.spread_home)} and a total of {d.total}. Books move; here is the same simulation at nearby numbers.</p>
            <div className="mt-2 overflow-x-auto"><table className="w-full min-w-[520px] text-left text-[15px]">
              <thead className="text-[13px] text-muted"><tr><th className="py-1">{d.home} spread</th><th className="text-right">{d.home} covers</th><th className="text-right">{d.away} covers</th><th className="pl-6">Total</th><th className="text-right">Over</th><th className="text-right">Over, scoring adjusted</th></tr></thead>
              <tbody>{d.ladder.spreads.map((s, i) => { const t = d.ladder.totals[i]; return (
                <tr key={s.line} className="border-t border-bg"><td className="py-1">{s.line > 0 ? "-" : "+"}{Math.abs(s.line)}</td><td className="text-right">{pct(s.home)}</td><td className="text-right">{pct(s.away)}</td><td className="pl-6">{t.line}</td><td className="text-right">{pct(t.over)}</td><td className="text-right">{pct(t.over_adjusted)}</td></tr>
              ); })}</tbody>
            </table></div>
          </div>

          <div>
            <h3 className="text-lg font-bold">What the simulation adds for this game</h3>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-[15px]">
              <li><b>Loud stadium.</b> Visiting offenses here false-start on {pct(a.visiting_false_start_rate, 2)} of snaps against {pct(a.league_rate, 2)} league-wide, which ranks {a.false_start_rank_raw} of {a.stadiums} (2015 to 2025). Shrunk toward the league for noise, the simulator uses {a.false_start_multiplier.toFixed(2)} times the normal rate for the visitor. It is not assumed to be second.</li>
              <li><b>Rest.</b> {d.away} {d.rest.away} days, {d.home} {d.rest.home}. History says a rest edge is worth {a.rest_beta_per_day.toFixed(2)} points a day (standard error {a.rest_se.toFixed(2)}), which is no detectable effect; the simulator applies {a.rest_points_to_home.toFixed(2)} points to {d.home}.</li>
              <li><b>Home field.</b> The league's average home margin, {a.home_field_points.toFixed(1)} points, is added to the final margin.</li>
              {d.scenario.star && <li><b>{d.scenario.star}{d.scenario.rookie ? ` and ${d.scenario.rookie}` : ""}.</b> {d.scenario.star} is the expected starter with no 2026 carries yet, so his workload and efficiency are scenario draws, not measured: each simulated game gives him between 40% and 65% of the backs' carries and about 95% of his usual yards per carry (his 2023 to 2025 history), {d.scenario.rookie ? `and ${d.scenario.rookie} takes 55% of what is left` : `and the rest go to the other backs. ${d.scenario.rookie_name ?? "The rookie"} is on the reserve list this week (roster file status, not the injury report), so he does not play`}. Team results at the two ends of that range are below.</li>}
            </ul>
            {Object.keys(d.scenario_runs).length > 0 && (
              <div className="mt-3 overflow-x-auto"><table className="w-full min-w-[520px] text-left text-[15px]">
                <thead className="text-[13px] text-muted"><tr><th className="py-1">Scenario</th><th className="text-right">{d.home} win</th><th className="text-right">{d.home} cover</th><th className="text-right">Over</th><th className="text-right">{d.scenario.star} rush yds</th></tr></thead>
                <tbody>{(["low", "high"] as const).map((k) => d.scenario_runs[k] && (
                  <tr key={k} className="border-t border-bg"><td className="py-1">{k === "low" ? "Low: 40% of carries, 0.88 yards multiplier" : "High: 65% of carries, 1.02 yards multiplier"}</td><td className="text-right">{pct(d.scenario_runs[k].win[d.home])}</td><td className="text-right">{pct(d.scenario_runs[k].cover[d.home])}</td><td className="text-right">{pct(d.scenario_runs[k].over)}</td><td className="text-right">{n1(d.scenario_runs[k].star?.mean)}</td></tr>
                ))}</tbody>
              </table></div>
            )}
            {Object.entries(d.out).some(([, v]) => v.length) && <p className="mt-2 text-[13px] text-muted">Left out because the injury report lists them out or doubtful: {Object.entries(d.out).map(([t, v]) => `${t}: ${v.join(", ") || "none"}`).join("; ")}.</p>}
          </div>

          <div>
            <h3 className="text-lg font-bold">Leans where the simulation, the matchup and the game script agree</h3>
            {d.leans.leans.length === 0 ? <p className="mt-1 text-[15px] text-muted">No prop passes all three tests for this game ({d.leans.props_checked} props with a market line checked).</p> : (
              <div className="mt-2 overflow-x-auto"><table className="w-full min-w-[720px] text-left text-[15px]">
                <thead className="text-[13px] text-muted"><tr><th className="py-1">Player</th><th>Prop</th><th className="text-right">Side</th><th className="text-right">Simulation</th><th className="text-right">Market</th><th className="text-right">Matchup</th><th className="text-right">Game volume</th></tr></thead>
                <tbody>{d.leans.leans.map((l) => (
                  <tr key={l.player + l.stat} className="border-t border-bg"><td className="py-1">{l.player} ({l.team})</td><td>{l.stat} {l.line}</td><td className="text-right font-bold">{l.side}</td><td className="text-right">{pct(l.sim_chance, 0)}</td><td className="text-right">{pct(l.market_chance, 0)}</td><td className="text-right">{l.matchup_ratio?.toFixed(2)}x league</td><td className="text-right">{l.volume_ratio?.toFixed(2)}x usual</td></tr>
                ))}</tbody>
              </table></div>
            )}
            <p className="mt-2 text-[13px] text-muted">A lean needs all three: the simulated chance of reaching the line is 5 points or more away from the market's; the opposing defense allows that stat at least 5% over (or under) the league; and the simulated pass or rush attempts are at least 3% over (or under) the team's usual. Earlier tests found no edge when this model's prop chances were compared to Kalshi's, and this agreement filter has no track record yet. It is a list to watch and to save before kickoff, not a pick.{d.leans.sim_only.length > 0 && ` ${d.leans.sim_only.length} more props differ from the market in the simulation alone but fail the matchup or game test.`}</p>
          </div>

          <div>
            <h3 className="text-lg font-bold">Team totals per game</h3>
            <div className="mt-2 overflow-x-auto"><table className="w-full min-w-[520px] text-left text-[15px]">
              <thead className="text-[13px] text-muted"><tr><th className="py-1">Team</th><th className="text-right">Snaps</th><th className="text-right">Pass attempts</th><th className="text-right">Rush attempts</th><th className="text-right">Sacks taken</th><th className="text-right">Penalties</th><th className="text-right">False starts</th><th className="text-right">Fourth-down tries</th></tr></thead>
              <tbody>{Object.entries(d.team_stats).map(([t, s]) => (
                <tr key={t} className="border-t border-bg"><td className="py-1">{t}</td><td className="text-right">{n1(s.snaps)}</td><td className="text-right">{n1(s.pass_att)}</td><td className="text-right">{n1(s.rush_att)}</td><td className="text-right">{n1(s.sacks)}</td><td className="text-right">{n1(s.penalties)}</td><td className="text-right">{n1(s.false_starts)}</td><td className="text-right">{n1(s.fourth_go)}</td></tr>
              ))}</tbody>
            </table></div>
          </div>

          <div>
            <h3 className="text-lg font-bold">Players: simulated mean (8 in 10 range)</h3>
            <div className="mt-2 overflow-x-auto"><table className="w-full min-w-[820px] text-left text-[15px]">
              <thead className="text-[13px] text-muted"><tr><th className="py-1">Player</th>{COLS.map(([, t]) => <th key={t} className="text-right">{t}</th>)}<th className="text-right">Anytime TD</th></tr></thead>
              <tbody>{d.players.filter((p) => ["QB", "RB", "WR", "TE", "FB"].includes(p.pos) && (p.stats.tgt?.mean ?? 0) + (p.stats.car?.mean ?? 0) >= 1).sort((x, y) => (x.team === y.team ? (y.stats.tgt?.mean ?? 0) + (y.stats.car?.mean ?? 0) - ((x.stats.tgt?.mean ?? 0) + (x.stats.car?.mean ?? 0)) : x.team.localeCompare(y.team))).map((p) => (
                <tr key={p.team + p.name} className="border-t border-bg"><td className="py-1">{p.name} <span className="text-muted">{p.team} {p.pos}</span></td>
                  {COLS.map(([k]) => <td key={k} className="text-right">{p.stats[k] ? `${n1(p.stats[k].mean)} (${p.stats[k].p10.toFixed(0)}-${p.stats[k].p90.toFixed(0)})` : ""}</td>)}<td className="text-right">{pct(p.anytime_td, 0)}</td></tr>
              ))}</tbody>
            </table></div>
          </div>

          {v1 && v2 && (
            <div>
              <h3 className="text-lg font-bold">How well does the simulator match 2026 so far?</h3>
              <p className="mt-1 text-[15px] text-muted">Every 2026 game played through week 8 was simulated using only the weeks before it. Per team per game, simulated against actual: {(["points_per_team", "snaps_per_team", "pass_rate", "sacks_per_team", "penalties_per_team", "fourth_go_per_team"] as const).map((k) => { const r = v1[k] as { sim: number; actual: number; within_5pct: boolean }; return `${k.replace(/_per_team|_/g, " ").trim()} ${r.sim.toFixed(k === "pass_rate" ? 3 : 1)} vs ${r.actual.toFixed(k === "pass_rate" ? 3 : 1)}${r.within_5pct ? "" : " (off by more than the 5% bar)"}`; }).join("; ")}. {v1.calibrated ? "All within the pre-set bar." : "Not all within the pre-set bar, so treat the percentages above with caution."} On weeks 4 to 8 ({v2.games} games) the simulated home win chance scored a log loss of {v2.win_log_loss_sim.toFixed(3)} against {v2.win_log_loss_market.toFixed(3)} for the betting market and {v2.win_log_loss_coin.toFixed(3)} for a coin flip. Too few games to prove an edge either way.</p>
            </div>
          )}
          <p className="text-[13px] text-muted">Rule: docs/SNAPSIM_PREREG.md, hash {d.rule_sha256.slice(0, 12)}. Not modeled because free data does not have them: coverage shells (man or zone) and route types. Pressure, blitz rate and box count stand in for the defensive scheme. <button type="button" className="min-h-[44px] cursor-pointer underline" onClick={rerun} disabled={busy}>{busy ? "Running." : "Run again with today's data"}</button></p>
        </>
      )}
    </section>
  );
}
