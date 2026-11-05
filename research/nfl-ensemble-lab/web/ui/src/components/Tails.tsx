import { useEffect, useState } from "react";
import { api } from "../api";
import type { Tails } from "../types";
import { Callout } from "./ui/primitives";

const pct = (x: number, d = 1) => `${(x * 100).toFixed(d)}%`;
const num = (x: number, d = 2) => x.toFixed(d);
const FLAG: Record<string, string> = { u_qb: "Quarterback change or new starter", u_gap: "Model far from the line", u_any: "Either" };

export function TailsView() {
  const [d, setD] = useState<Tails | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api.tails().then(setD).catch((e) => setErr(String(e.message ?? e))); }, []);
  if (err) return <Callout tone="amber">Could not load tails: {err}</Callout>;
  if (!d) return <p className="text-muted">Loading tails.</p>;
  const r = d.results;
  const passed = r.tail_tests.passed;
  const keys = Object.keys(r.tail_tests.confirmation);
  const fa = r.forecast_accuracy;
  const wk = d.week?.forecast;
  const pro = d.prospective.by_flag;

  return (
    <section aria-labelledby="tails-h" className="space-y-6">
      <div>
        <h2 id="tails-h" className="text-xl font-bold">Tails</h2>
        <p className="mt-1 max-w-3xl text-[15px] text-muted">Games where the result is unusually hard to call before kickoff. The test asks one question: do margins land far from the closing line more often in those games than the line's own spread says? The rule and the pass bar were saved before any result was looked at. This is a record of what was found, not advice and not a staking plan.</p>
      </div>

      <Callout tone={passed.length ? "green" : "blue"}>
        {passed.length ? `Pass rule met for ${passed.join(", ")}.` : "No mispricing found."} In games flagged as uncertain, margins landed 14 or more points from the line {pct(r.tail_tests.confirmation.u_any_14.observed_rate)} of the time in 2020 to 2026 ({r.tail_tests.confirmation.u_any_14.flagged_games} games), against {pct(r.tail_tests.confirmation.u_any_14.priced_rate)} implied by the line's own spread. Tails were not fatter in flagged games, in either the earlier seasons or the later ones. The unflagged spread also shrank in recent seasons, which is part of why the later ratios sit below one.
      </Callout>

      <div>
        <h3 className="text-lg font-bold">The tests</h3>
        <p className="mt-1 max-w-3xl text-[14px] text-muted">Rate of margins at least 14 or 21 points from the closing line. Priced rate: a normal curve fitted to unflagged 2006 to 2019 games. A test passes only if it clears the multiple-test correction in both periods with an observed-to-priced ratio of at least 1.15.</p>
        <div className="mt-2 overflow-x-auto"><table className="w-full min-w-[720px] text-left text-[15px]">
          <thead className="text-[13px] text-muted"><tr><th className="py-1">Flag and size</th><th className="text-right">Games 2020 to 2026</th><th className="text-right">Observed</th><th className="text-right">Priced</th><th className="text-right">Ratio 2006 to 2019</th><th className="text-right">Ratio 2020 to 2026</th><th className="text-right">Corrected p</th><th className="text-right">Smallest rise detectable</th></tr></thead>
          <tbody>{keys.map((k) => {
            const c = r.tail_tests.confirmation[k], di = r.tail_tests.discovery[k], pw = r.power.flags[k];
            const [flag, size] = [k.slice(0, k.lastIndexOf("_")), k.slice(k.lastIndexOf("_") + 1)];
            return <tr key={k} className="border-t border-bg"><td className="py-1">{FLAG[flag]}, {size}+ points</td><td className="text-right">{c.flagged_games}</td><td className="text-right">{pct(c.observed_rate)}</td><td className="text-right">{pct(c.priced_rate)}</td><td className="text-right">{num(di.ratio)}</td><td className="text-right">{num(c.ratio)}</td><td className="text-right">{num(c.p_holm)}</td><td className="text-right">{pct(pw.smallest_detectable_rate_increase)}</td></tr>;
          })}</tbody>
        </table></div>
        <p className="mt-2 max-w-3xl text-[13px] text-muted">Smallest rise detectable is the tail-rate increase the confirmation sample could see with 80% power. Smaller real effects would not show, so a non-pass does not prove none exists.</p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div>
          <h3 className="text-lg font-bold">How good the forecast is</h3>
          <p className="mt-1 text-[14px] text-muted">Home-win Brier score, 2020 to 2026 ({fa.games} games). Lower is better.</p>
          <table className="mt-2 w-full text-left text-[15px]"><tbody>
            <tr className="border-t border-bg"><td className="py-1">Closing line</td><td className="text-right">{num(fa.brier.closing_line, 4)}</td></tr>
            <tr className="border-t border-bg"><td className="py-1">Plain rating model</td><td className="text-right">{num(fa.brier.elo, 4)}</td></tr>
            <tr className="border-t border-bg"><td className="py-1">Rating model plus starting quarterback</td><td className="text-right">{num(fa.brier.elo_qb, 4)}</td></tr>
          </tbody></table>
          <p className="mt-2 text-[13px] text-muted">The quarterback term helps the rating model by {num(-fa.paired.elo_qb_minus_elo.mean, 4)} (95% range {num(-fa.paired.elo_qb_minus_elo.ci95[1], 4)} to {num(-fa.paired.elo_qb_minus_elo.ci95[0], 4)}), a real gain. The closing line is still better than both by about {num(fa.paired.elo_qb_minus_closing_line.mean, 3)}.</p>
        </div>
        <div>
          <h3 className="text-lg font-bold">Do long shots pay more than they should?</h3>
          <p className="mt-1 text-[14px] text-muted">Underdog win rate against the devigged moneyline chance, 2020 to 2026.</p>
          <table className="mt-2 w-full text-left text-[15px]">
            <thead className="text-[13px] text-muted"><tr><th className="py-1">Price implies</th><th className="text-right">Games</th><th className="text-right">Implied</th><th className="text-right">Won</th><th className="text-right">95% range</th></tr></thead>
            <tbody>{r.favorite_longshot.confirmation.map((b) => (
              <tr key={b.implied_bin[0]} className="border-t border-bg"><td className="py-1">{pct(b.implied_bin[0], 0)} to {pct(b.implied_bin[1], 0)}</td><td className="text-right">{b.games}</td><td className="text-right">{pct(b.implied)}</td><td className="text-right">{pct(b.realized)}</td><td className="text-right">{pct(b.wilson95[0])} to {pct(b.wilson95[1])}</td></tr>
            ))}</tbody>
          </table>
          <p className="mt-2 text-[13px] text-muted">Where the realized rate sits below the implied one, long shots won less than their price said.</p>
        </div>
      </div>

      <div>
        <h3 className="text-lg font-bold">{wk ? `Week ${wk.week}: flags saved before kickoff` : "This week"}</h3>
        {wk && d.week ? (
          <>
            <p className="mt-1 max-w-3xl text-[14px] text-muted">Saved {d.week.created.slice(0, 16).replace("T", " ")} UTC in a write-once file ({d.week.hash_ok ? "hash checks out" : "hash does not match"}, {d.week.sha256.slice(0, 12)}). Range: where 90% of margins fell around the line in past games like this one. Tail chance: how likely a margin 14 or 21 points from the line is on the line's own spread. Starters are the depth-chart starters on the day it was saved.</p>
            <div className="mt-2 overflow-x-auto"><table className="w-full min-w-[760px] text-left text-[15px]">
              <thead className="text-[13px] text-muted"><tr><th className="py-1">Game</th><th className="text-right">Home spread</th><th className="text-right">90% range, home margin</th><th className="text-right">14+ from line</th><th className="text-right">21+ from line</th><th>Uncertainty flag</th><th>Status</th></tr></thead>
              <tbody>{wk.games.map((g) => (
                <tr key={g.gid} className="border-t border-bg"><td className="py-1">{g.away} at {g.home}</td><td className="text-right">{g.closing_spread_home > 0 ? `-${g.closing_spread_home}` : `+${-g.closing_spread_home}`}</td><td className="text-right">{num(g.range_90[0], 1)} to {num(g.range_90[1], 1)}</td><td className="text-right">{pct(g.baseline_tail_14)}</td><td className="text-right">{pct(g.baseline_tail_21)}</td>
                  <td>{g.u_any ? [g.u_qb ? "QB" : "", g.u_gap ? "model gap" : ""].filter(Boolean).join(" and ") : "None"}</td><td className="text-muted">{passed.length ? "Pass rule met" : "No mispricing found"}</td></tr>
              ))}</tbody>
            </table></div>
          </>
        ) : <p className="mt-1 text-muted">No week has been saved yet. Run scripts/tails_freeze.py before kickoff.</p>}
        <p className="mt-3 max-w-3xl text-[14px] text-muted">Scored so far: {pro.all.games} games ({pro.u_any.games} flagged). {pro.u_any.games ? `Flagged games had a margin 14+ from the line ${pro.u_any.hit14} times against ${pro.u_any.priced14.toFixed(1)} priced.` : "Scoring starts after this week's games finish."}</p>
      </div>

      {d.deep && (() => {
        const dp = d.deep, sc = dp.same_season_control, pc = dp.positive_controls, dr = dp.dose_response;
        const ks = Object.keys(sc.confirmation);
        const spr = dp.kalshi_history.KXNFLSPREAD, tot = dp.kalshi_history.KXNFLTOTAL;
        return (
          <div>
            <h3 className="text-lg font-bold">Deeper checks</h3>
            <p className="mt-1 max-w-3xl text-[14px] text-muted">The first test priced tails with a spread fitted on 2006 to 2019, and margins have been tighter since 2020. These checks compare each flagged game with unflagged games in the same season, so that drift cannot leak in, and add a luck check: 10,000 random flags of the same size.</p>
            <Callout tone={sc.passed.length || dr.passed.length ? "green" : "blue"}>
              {sc.passed.length || dr.passed.length ? "A deeper check passed its pre-set bar." : "Still no mispricing found."} With the same-season control the ratios sit near one ({num(Math.min(...ks.map((k) => sc.confirmation[k].ratio)))} to {num(Math.max(...ks.map((k) => sc.confirmation[k].ratio)))} in 2020 to 2026), so most of the earlier shortfall was era drift, not safer games. The method can see a 20% widening of margins in flagged games {pct(pc.injected["1.2"], 0)} of the time, but only {pct(pc.injected["1.1"], 0)} of the time at 10%, so a null result rules out large effects, not small ones. {pc.natural_detected ? "" : "A natural test, wider margins when the total line is high, was not found in this data either."} A continuous uncertainty score also showed no link to big misses on margin or on totals.
            </Callout>
            <div className="mt-2 overflow-x-auto"><table className="w-full min-w-[720px] text-left text-[15px]">
              <thead className="text-[13px] text-muted"><tr><th className="py-1">Flag and size</th><th className="text-right">Old ratio 2020 to 2026</th><th className="text-right">Same-season ratio 2006 to 2019</th><th className="text-right">Same-season ratio 2020 to 2026</th><th className="text-right">Beats random flags</th><th className="text-right">Corrected p</th></tr></thead>
              <tbody>{ks.map((k) => {
                const flag = k.slice(0, k.lastIndexOf("_")), size = k.slice(k.lastIndexOf("_") + 1), o = dp.original_ratios.confirmation[k];
                return <tr key={k} className="border-t border-bg"><td className="py-1">{FLAG[flag]}, {size}+ points</td><td className="text-right">{o === undefined ? "not run" : num(o)}</td><td className="text-right">{num(sc.discovery[k].ratio)}</td><td className="text-right">{num(sc.confirmation[k].ratio)}</td><td className="text-right">{pct(sc.confirmation[k].placebo_percentile, 0)} of draws</td><td className="text-right">{num(sc.confirmation[k].p_holm)}</td></tr>;
              })}</tbody>
            </table></div>
            <p className="mt-2 max-w-3xl text-[13px] text-muted">Beats random flags: the share of random flags that scored lower than the real one. A real effect would sit near 95% or higher in both periods. Starting quarterbacks from raw play-by-play match the schedule file in {pct(dp.starter_agreement.share)} of team-games. The raw sportsbook pages give a closing spread within one point of the schedule file in {dp.sbr_rederive.spread_within_1_point} of {dp.sbr_rederive.matched_to_games_csv_by_date_and_score} matched games. Kalshi lists {(spr["/historical/markets"].settled_yes_or_no + spr["/markets"].settled_yes_or_no).toLocaleString()} settled spread markets and {(tot["/historical/markets"].settled_yes_or_no + tot["/markets"].settled_yes_or_no).toLocaleString()} settled total markets since {spr["/historical/markets"].first_close?.slice(0, 10)}, not yet used.</p>
          </div>
        );
      })()}

      <div className="max-w-3xl text-[13px] text-muted">
        <p>Data counted: {r.inventory.games_with_result_and_closing_line.toLocaleString()} games from {r.inventory.seasons[0]} to {r.inventory.seasons[1]} with a closing spread; {r.inventory.sbr_open_and_close_games.toLocaleString()} with opening and closing lines ({r.inventory.sbr_seasons[0]} to {r.inventory.sbr_seasons[1]}). Kalshi history begins {r.inventory.kalshi_snapshots.kalshi.first?.slice(0, 10)} and is too short to price tails game by game, so the closing line is the benchmark. Standard deviation of margin around the line: {num(r.reconcile.all.sd_margin_minus_line)} over all games, {num(r.reconcile["2006_2019"].sd_margin_minus_line)} in 2006 to 2019 and {num(r.reconcile["2020_2026"].sd_margin_minus_line)} since 2020; the published figure near 13.9 comes from older seasons. Rule hash {r.rule_sha256.slice(0, 12)}.</p>
      </div>
    </section>
  );
}
