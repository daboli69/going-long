import { useEffect, useState } from "react";
import { api } from "../api";
import type { Refs } from "../types";
import { Callout } from "./ui/primitives";
import { Pick } from "./Leans";

const pct = (x: number | null | undefined) => (x === null || x === undefined || Number.isNaN(x) ? "n/a" : `${(x * 100).toFixed(1)}%`);
const num = (x: number | null | undefined, d = 2) => (x === null || x === undefined || Number.isNaN(x) ? "n/a" : x.toFixed(d));

export function RefsView() {
  const [measure, setMeasure] = useState("home_ats");
  const [referee, setReferee] = useState("All");
  const [from, setFrom] = useState("2015");
  const [to, setTo] = useState("2026");
  const [d, setD] = useState<Refs | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setErr(null);
    api.refs(new URLSearchParams({ measure, referee, season_from: from, season_to: to }).toString()).then(setD).catch((e) => setErr(String(e.message ?? e)));
  }, [measure, referee, from, to]);

  const seasons = Array.from({ length: 12 }, (_, i) => ({ v: String(2015 + i), t: String(2015 + i) }));
  const rate = d?.kind === "rate";
  const f = (x: number | null | undefined) => (rate ? pct(x) : num(x));
  const r = d?.results;
  const tw = d?.this_week;
  const rows = d ? (d.selected ? [d.selected] : d.rows) : [];

  return (
    <section aria-labelledby="refs-h" className="space-y-6">
      <div>
        <h2 id="refs-h" className="text-xl font-bold">Referees</h2>
        <p className="mt-1 max-w-3xl text-[15px] text-muted">Head-referee records for completed regular-season games since 2015: how the home team did against the closing spread, the over, and penalties on each side. A record only means something if it repeats, so the tests below ask whether a referee's tendency survives a luck check and shows up again in a later season. These are past records, not advice and not a staking plan.</p>
      </div>
      {err && <Callout tone="amber">Could not load referees: {err}</Callout>}
      {!d && !err && <p className="text-muted">Loading referees.</p>}
      {d && r && (
        <>
          <Callout tone={r.any_effect_claimed ? "green" : "blue"}>
            {r.any_effect_claimed ? "At least one referee effect passed the pre-registered test." : "No real referee effect was found."} Of {r.discovery_ats_tests} referee-by-measure tests in 2015 to 2023, none held up after correcting for how many were run. Year to year, a referee's home ATS rate correlates {num(r.year_to_year.home_ats.r)} with the next season's (95% range {num(r.year_to_year.home_ats.ci?.[0])} to {num(r.year_to_year.home_ats.ci?.[1])}) and the penalty gap {num(r.year_to_year.pen_gap.r)} (range {num(r.year_to_year.pen_gap.ci?.[0])} to {num(r.year_to_year.pen_gap.ci?.[1])}), so there is no stable referee tendency to read.
          </Callout>
          <div className="grid gap-3 sm:grid-cols-4">
            <Pick label="Referee" value={referee} onChange={setReferee} options={[{ v: "All", t: "All referees" }, ...d.referees.map((n) => ({ v: n, t: n }))]} />
            <Pick label="Measure" value={measure} onChange={setMeasure} options={Object.entries(d.measures).map(([v, t]) => ({ v, t }))} />
            <Pick label="From season" value={from} onChange={setFrom} options={seasons} />
            <Pick label="To season" value={to} onChange={setTo} options={seasons} />
          </div>
          <div className="overflow-x-auto"><table className="w-full min-w-[640px] text-left text-[15px]">
            <thead className="text-[13px] text-muted"><tr><th className="py-1">Referee</th><th className="text-right">Games</th><th className="text-right">{rate ? "Record rate" : "Per game"}</th><th className="text-right">95% range</th><th className="text-right">Shrunken</th><th className="text-right">League</th><th>Note</th></tr></thead>
            <tbody>{rows.map((x) => (
              <tr key={x.referee} className="border-t border-bg"><td className="py-1">{x.referee}</td><td className="text-right">{x.n}</td><td className="text-right">{rate && x.k !== null ? `${x.k.toFixed(0)}-${x.n - x.k}  ${pct(x.rate)}` : f(x.rate)}</td>
                <td className="text-right">{f(x.lo)} to {f(x.hi)}</td><td className="text-right">{f(x.shrunk)}</td><td className="text-right">{f(x.league)}</td><td className="pl-3 text-muted">{x.too_few ? "Too few games to mean anything" : ""}</td></tr>
            ))}</tbody>
          </table></div>
          <p className="text-[13px] text-muted">Shrunken pulls a small sample toward the league number in proportion to how much referees really differ. Pushes are left out of ATS and over records. Penalties are flagged penalties in play-by-play, one per play.</p>

          <div>
            <h3 className="text-lg font-bold">This week's assigned crews</h3>
            {tw && tw.games.length > 0 ? (
              <ul className="mt-2 divide-y divide-bg text-[15px]">{tw.games.map((g) => (
                <li key={g.gid} className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 py-2"><span>{g.away} at {g.home}<span className="block text-[13px] text-muted">{g.kickoff}</span></span>
                  <span className="text-right">{g.referee ?? "Not announced"}{g.tab && <span className="block text-[13px] text-muted">home covers {pct(g.tab.home_cover_shrunk)} (league {pct(g.tab.league_home_cover)}), {g.tab.games} games</span>}</span></li>
              ))}</ul>
            ) : <p className="mt-1 text-[15px] text-muted">No games listed.</p>}
            <p className="mt-1 text-[13px] text-muted">Week {tw?.week ?? "n/a"}, {tw?.assigned ?? 0} of {tw?.games.length ?? 0} assigned. Source: {tw?.source}. The assignment file lags the league announcement, so a blank means the file has not been refreshed, not that no crew exists. A hashed record is written once an assignment appears and before kickoff.</p>
          </div>

          <div>
            <h3 className="text-lg font-bold">{r.tweet_check.referee} against the tweet</h3>
            <div className="mt-2 overflow-x-auto"><table className="w-full min-w-[520px] text-left text-[15px]">
              <thead className="text-[13px] text-muted"><tr><th className="py-1">Claim since {r.tweet_check.since}</th><th className="text-right">Tweet</th><th className="text-right">Rebuilt here</th></tr></thead>
              <tbody>
                <tr className="border-t border-bg"><td className="py-1">Home ATS</td><td className="text-right">{r.tweet_check.tweet.home_ats}</td><td className="text-right">{r.tweet_check.rebuilt.home_ats} ({r.tweet_check.rebuilt.games} games)</td></tr>
                <tr className="border-t border-bg"><td className="py-1">Home favorites up to 4 ATS</td><td className="text-right">{r.tweet_check.tweet.home_fav_up_to_4_ats}</td><td className="text-right">{r.tweet_check.rebuilt.home_fav_up_to_4_ats}</td></tr>
                <tr className="border-t border-bg"><td className="py-1">More penalties on away than home, 2025</td><td className="text-right">{r.tweet_check.tweet.away_minus_home_penalties_2025}</td><td className="text-right">{r.tweet_check.rebuilt.away_minus_home_penalties_2025} (rank {r.tweet_check.rebuilt.away_minus_home_2025_league_rank} of {r.tweet_check.rebuilt.referees_2025})</td></tr>
              </tbody>
            </table></div>
            <p className="mt-2 text-[15px] text-muted">The record is real in the schedule data: p = {num(r.tweet_check.exact_p_vs_league, 4)} against the league rate, and in {pct(r.tweet_check.luck_check.share_of_shuffles_with_a_referee_this_far)} of shuffles that deal referees out at random, some one of the {r.tweet_check.luck_check.extreme_referees_considered} referees with enough games looks this far from the league. That is the whole sample, picked after the fact, and it is the same window the tweet used, so it is not an independent test. It did not show up in his earlier seasons, and referees' rates do not repeat from year to year. The record to watch is the one written before kickoff.</p>
          </div>

          <p className="text-[13px] text-muted">Rule and amendments: docs/REFS_PREREG.md, hash {r.rule_sha256.slice(0, 12)}. {r.games} games, {r.referees} referees. Market check: a referee's earlier tendency {r.market.log_score_gain_vs_constant && r.market.log_score_gain_vs_constant.ci[1] < 0 ? "predicted covers worse than the league rate" : "did not beat the league rate"} on {r.market.games} games (log score gain {num(r.market.log_score_gain_vs_constant?.gain, 4)}, range {num(r.market.log_score_gain_vs_constant?.ci[0], 4)} to {num(r.market.log_score_gain_vs_constant?.ci[1], 4)}), and it did not move the line from open to close (correlation {num(r.market.corr_belief_with_move)}). The data holds only open and close lines, not the line at the assignment announcement. Crew positions other than referee are not analyzed. The official gamebooks were not read.</p>
        </>
      )}
    </section>
  );
}
