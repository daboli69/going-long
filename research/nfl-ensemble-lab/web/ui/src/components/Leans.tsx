import { useEffect, useState } from "react";
import { api } from "../api";
import type { Leans } from "../types";
import { Callout } from "./ui/primitives";

const pts = (x: number | null | undefined) => (x === null || x === undefined || Number.isNaN(x) ? "n/a" : `${x >= 0 ? "+" : ""}${(x * 100).toFixed(1)}%`);
const plain = (x: number | null | undefined) => (x === null || x === undefined ? "n/a" : `${(x * 100).toFixed(1)}%`);
const SEL = "min-h-[44px] w-full cursor-pointer border border-bg bg-[#12161c] px-3 text-[15px] text-white";

function Pick({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: { v: string; t: string }[] }) {
  return (
    <label className="block text-[13px] text-muted">{label}
      <select className={`${SEL} mt-1`} value={value} onChange={(e) => onChange(e.target.value)}>{options.map((o) => <option key={o.v} value={o.v}>{o.t}</option>)}</select>
    </label>
  );
}

export function LeansView() {
  const [market, setMarket] = useState("All");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [size, setSize] = useState("All");
  const [season, setSeason] = useState("");
  const [model, setModel] = useState("recal");
  const [mode, setMode] = useState("exec");
  const [d, setD] = useState<Leans | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const q = new URLSearchParams({ market, size, model, mode });
    if (season) q.set("season", season);
    if (from) q.set("week_from", from);
    if (to) q.set("week_to", to);
    setErr(null);
    api.leans(q.toString()).then(setD).catch((e) => setErr(String(e.message ?? e)));
  }, [market, from, to, size, season, model, mode]);

  const weeks = Array.from({ length: 18 }, (_, i) => ({ v: String(i + 1), t: `Week ${i + 1}` }));
  const bad = d && d.markets.find((m) => m.name === market && !m.testable);
  const s = d?.summary;
  const exec = mode === "exec";

  return (
    <section aria-labelledby="leans-h" className="space-y-6">
      <div>
        <h2 id="leans-h" className="text-xl font-bold">Leans</h2>
        <p className="mt-1 max-w-3xl text-[15px] text-muted">A lean is a side (over or under) on a real Kalshi player prop, logged 90 minutes before kickoff when our chance and the market's differ by 5 points or more. Each player and stat counts once, at the strike with the biggest gap. These are past results of that rule on 2025 and 2026 games, not advice and not a staking plan.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-4 lg:grid-cols-7">
        <Pick label="Market" value={market} onChange={setMarket} options={[{ v: "All", t: "All" }, ...(d?.markets ?? []).map((m) => ({ v: m.name, t: m.testable ? m.name : `${m.name} (not testable)` }))]} />
        <Pick label="Season" value={season} onChange={setSeason} options={[{ v: "", t: "Both" }, { v: "2026", t: "2026" }, { v: "2025", t: "2025" }]} />
        <Pick label="From week" value={from} onChange={setFrom} options={[{ v: "", t: "Any" }, ...weeks]} />
        <Pick label="To week" value={to} onChange={setTo} options={[{ v: "", t: "Any" }, ...weeks]} />
        <Pick label="Edge size" value={size} onChange={setSize} options={[{ v: "All", t: "All" }, { v: "small", t: "Small (5 to 8 points)" }, { v: "medium", t: "Medium (8 to 12)" }, { v: "large", t: "Large (12 and over)" }]} />
        <Pick label="Price" value={mode} onChange={setMode} options={[{ v: "exec", t: "Executable (ask or bid, plus fee)" }, { v: "mid", t: "Mid price" }]} />
        <Pick label="Model" value={model} onChange={setModel} options={[{ v: "recal", t: "Recalibrated (chosen by owner)" }, { v: "raw", t: "Raw model" }]} />
      </div>
      {err && <Callout tone="amber">Could not load leans: {err}</Callout>}
      {!d && !err && <p className="text-muted">Loading leans.</p>}
      {bad && <Callout tone="amber">{bad.name} is not testable yet: {bad.why}. Nothing is logged for it.</Callout>}
      {d && s && !bad && (
        <>
          <dl className="grid grid-cols-2 gap-px bg-bg text-[15px] sm:grid-cols-4 lg:grid-cols-8">
            {([["Leans", String(s.n)], ["Effective bets", s.effective_n === undefined ? "n/a" : s.effective_n.toFixed(0)], ["Win rate", plain(s.win_rate)], ["Stated edge", pts(s.stated_edge)],
               ["Realized edge" + (exec ? " after costs" : ""), pts(s.realized_edge)], ["Before fees", pts(s.realized_before_fees)], ["Closing line value", pts(s.clv)], ["Needed", s.need_for_2pt ? String(s.need_for_2pt) : "n/a"]] as const).map(([k, v]) => (
              <div key={k} className="bg-[#12161c] p-3"><dt className="text-[13px] text-muted">{k}</dt><dd className="text-xl font-bold">{v}</dd></div>
            ))}
          </dl>
          {s.realized_ci && <p className="text-[15px] text-muted">Realized edge 95% range (resampling whole games): {pts(s.realized_ci[0])} to {pts(s.realized_ci[1])}.</p>}
          <Callout tone={s.n < (s.need_for_2pt ?? 0) ? "amber" : "blue"}>{s.note} Stated edge is how far apart our chance and the market's were. Realized edge is how often the lean won minus the price paid{exec ? " and the fee" : ""}. Closing line value is how far the price moved toward the lean by kickoff{exec ? ", measured from what you could pay to what you could sell for" : ""}.</Callout>
        </>
      )}
      {d && (
        <>
          <Callout tone={d.pass.edge_found ? "green" : "blue"}>
            Headline test (all leans, recalibrated model, executable prices): {d.headline.n} leans, {d.headline.effective_n?.toFixed(0)} effective, realized edge after costs {pts(d.headline.realized_edge)} (range {d.headline.realized_ci ? `${pts(d.headline.realized_ci[0])} to ${pts(d.headline.realized_ci[1])}` : "n/a"}), closing line value {pts(d.headline.clv)}.
            {d.pass.edge_found ? " The pass rule is met." : " No edge found: the pass rule is not met."} A shuffled-model placebo scored {pts(d.placebo.mean_edge)} (range {pts(d.placebo.range[0])} to {pts(d.placebo.range[1])}), which is about what costs alone take. The raw model scored {pts(d.raw_headline.realized_edge)} on the same test. Following the market scored {pts(d.benchmarks.follow_market_realized)} and a random side {pts(d.benchmarks.random_side_realized)} here.
            The recalibration was adopted by choice, not by test: its log loss gain was {d.recal_compare.gain_logistic.gain.toFixed(4)} (range {d.recal_compare.gain_logistic.ci[0].toFixed(4)} to {d.recal_compare.gain_logistic.ci[1].toFixed(4)}).
          </Callout>
          <div>
            <h3 className="text-lg font-bold">Upcoming leans</h3>
            {d.pending.length === 0 ? <p className="mt-1 text-[15px] text-muted">No leans saved for games that have not started. They are written once, before kickoff, to a hashed file.</p> : (
              <ul className="mt-2 divide-y divide-bg text-[15px]">{d.pending.map((p) => (
                <li key={`${p.gid}${p.player}${p.market}${p.line}`} className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 py-2"><span>{p.player} ({p.team}) {p.side} {p.line} {p.market}<span className="block text-[13px] text-muted">{p.gid} · {p.source}</span></span><span className="text-right">{plain(p.model_p)} vs {plain(p.market_p)}<span className="block text-[13px] text-muted">edge {pts(p.edge)}</span></span></li>
              ))}</ul>
            )}
          </div>
          <div>
            <h3 className="text-lg font-bold">Settled leans in this selection</h3>
            <div className="mt-2 overflow-x-auto"><table className="w-full min-w-[720px] text-left text-[15px]">
              <thead className="text-[13px] text-muted"><tr><th className="py-1">Game</th><th>Market</th><th>Side and line</th><th className="text-right">Ours</th><th className="text-right">Market</th><th className="text-right">Price paid</th><th className="text-right">Close</th><th className="text-right">Result</th></tr></thead>
              <tbody>{d.rows.map((r, i) => (
                <tr key={i} className="border-t border-bg"><td className="py-1">{r.season} wk {r.week}</td><td>{r.market}</td><td>{r.side} {r.k}</td><td className="text-right">{plain(r.q)}</td><td className="text-right">{plain(r.m)}</td><td className="text-right">{plain(r.price)}</td><td className="text-right">{plain(r.c)}</td><td className="text-right">{r.win ? "Won" : "Lost"}</td></tr>
              ))}</tbody>
            </table></div>
            {s && s.n > d.rows.length && <p className="mt-1 text-[13px] text-muted">Showing the latest {d.rows.length} of {s.n}.</p>}
          </div>
          <div>
            <h3 className="text-lg font-bold">Calibration by chance</h3>
            <p className="mt-1 text-[13px] text-muted">How often things happened at each stated chance, for the raw model, the two recalibrations and the market.</p>
            <div className="mt-2 overflow-x-auto"><table className="w-full min-w-[640px] text-left text-[15px]">
              <thead className="text-[13px] text-muted"><tr><th className="py-1">Stated chance</th><th className="text-right">Cases</th><th className="text-right">Raw said / happened</th><th className="text-right">Logistic said / happened</th><th className="text-right">Isotonic said / happened</th><th className="text-right">Market said / happened</th></tr></thead>
              <tbody>{d.calibration.raw.map((b, i) => { const c = (k: string) => { const r = d.calibration[k][i]; return r ? `${plain(r.stated)} / ${plain(r.realized)}` : ""; }; return (
                <tr key={b.bucket} className="border-t border-bg"><td className="py-1">{b.bucket}</td><td className="text-right">{b.n}</td><td className="text-right">{c("raw")}</td><td className="text-right">{c("logistic")}</td><td className="text-right">{c("isotonic")}</td><td className="text-right">{c("market")}</td></tr>
              ); })}</tbody>
            </table></div>
          </div>
          <p className="text-[13px] text-muted">Rule and Amendment 1: docs/LEANS_PREREG.md, hash {d.rule_sha256.slice(0, 12)}. The scored set holds {d.universe_rows} Kalshi prop rows that were all liquid at the 90-minute mark ({plain(d.dropped.dropped_thin)} of leans dropped for thin markets in this set; most stored quotes are thin and were never scored). Fee: 7% of price times one minus price per contract, from secondary reports of Kalshi's schedule. Game totals, spreads and moneylines cannot be tested because the model's game numbers come from the market.</p>
        </>
      )}
    </section>
  );
}
