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
  const [d, setD] = useState<Leans | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const q = new URLSearchParams({ market, size });
    if (season) q.set("season", season);
    if (from) q.set("week_from", from);
    if (to) q.set("week_to", to);
    setErr(null);
    api.leans(q.toString()).then(setD).catch((e) => setErr(String(e.message ?? e)));
  }, [market, from, to, size, season]);

  const weeks = Array.from({ length: 18 }, (_, i) => ({ v: String(i + 1), t: `Week ${i + 1}` }));
  const bad = d && d.markets.find((m) => m.name === market && !m.testable);
  const s = d?.summary;

  return (
    <section aria-labelledby="leans-h" className="space-y-6">
      <div>
        <h2 id="leans-h" className="text-xl font-bold">Leans</h2>
        <p className="mt-1 max-w-3xl text-[15px] text-muted">A lean is a side (over or under) on a real Kalshi player prop, logged 90 minutes before kickoff when our chance and the market's differ by 5 points or more. These are past results of that rule on 2025 and 2026 games, not advice and not a staking plan.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-5">
        <Pick label="Market" value={market} onChange={setMarket} options={[{ v: "All", t: "All" }, ...(d?.markets ?? []).map((m) => ({ v: m.name, t: m.testable ? m.name : `${m.name} (not testable)` }))]} />
        <Pick label="Season" value={season} onChange={setSeason} options={[{ v: "", t: "Both" }, { v: "2026", t: "2026" }, { v: "2025", t: "2025" }]} />
        <Pick label="From week" value={from} onChange={setFrom} options={[{ v: "", t: "Any" }, ...weeks]} />
        <Pick label="To week" value={to} onChange={setTo} options={[{ v: "", t: "Any" }, ...weeks]} />
        <Pick label="Edge size" value={size} onChange={setSize} options={[{ v: "All", t: "All" }, { v: "small", t: "Small (5 to 8 points)" }, { v: "medium", t: "Medium (8 to 12)" }, { v: "large", t: "Large (12 and over)" }]} />
      </div>
      {err && <Callout tone="amber">Could not load leans: {err}</Callout>}
      {!d && !err && <p className="text-muted">Loading leans.</p>}
      {bad && <Callout tone="amber">{bad.name} is not testable yet: {bad.why}. Nothing is logged for it.</Callout>}
      {d && s && !bad && (
        <>
          <dl className="grid grid-cols-2 gap-px bg-bg text-[15px] sm:grid-cols-5">
            {([["Leans", String(s.n)], ["Win rate", plain(s.win_rate)], ["Stated edge", pts(s.stated_edge)], ["Realized edge", pts(s.realized_edge)], ["Closing line value", pts(s.clv)]] as const).map(([k, v]) => (
              <div key={k} className="bg-[#12161c] p-3"><dt className="text-[13px] text-muted">{k}</dt><dd className="text-xl font-bold">{v}</dd></div>
            ))}
          </dl>
          {s.realized_ci && <p className="text-[15px] text-muted">Realized edge 95% range: {pts(s.realized_ci[0])} to {pts(s.realized_ci[1])}. {s.finds_edge ? "This selection meets the pass rule." : "This selection does not meet the pass rule."}</p>}
          <Callout tone={s.n < (s.need_for_2pt ?? 0) ? "amber" : "blue"}>{s.note} Stated edge is how far apart our chance and the market's were. Realized edge is how often the lean won minus the price of that side. Closing line value is how far the price moved toward the lean by kickoff.</Callout>
        </>
      )}
      {d && (
        <>
          <Callout tone="blue">
            Over all {d.all.n} leans: realized edge {pts(d.all.realized_edge)} (range {d.all.realized_ci ? `${pts(d.all.realized_ci[0])} to ${pts(d.all.realized_ci[1])}` : "n/a"}). No edge found. Always following the market scored {pts(d.benchmarks.follow_market_realized)} and a random side {pts(d.benchmarks.random_side_realized)} on the same rows. Recalibrating our chances did not help (log loss gain {d.recal_test.gain.toFixed(4)}, range {d.recal_test.ci[0].toFixed(4)} to {d.recal_test.ci[1].toFixed(4)}).
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
            <div className="mt-2 overflow-x-auto"><table className="w-full min-w-[640px] text-left text-[15px]">
              <thead className="text-[13px] text-muted"><tr><th className="py-1">Game</th><th>Market</th><th>Side and line</th><th className="text-right">Ours</th><th className="text-right">Market</th><th className="text-right">Close</th><th className="text-right">Result</th></tr></thead>
              <tbody>{d.rows.map((r, i) => (
                <tr key={i} className="border-t border-bg"><td className="py-1">{r.season} wk {r.week}</td><td>{r.market}</td><td>{r.side} {r.k}</td><td className="text-right">{plain(r.q)}</td><td className="text-right">{plain(r.m)}</td><td className="text-right">{plain(r.c)}</td><td className="text-right">{r.win ? "Won" : "Lost"}</td></tr>
              ))}</tbody>
            </table></div>
            {s && s.n > d.rows.length && <p className="mt-1 text-[13px] text-muted">Showing the latest {d.rows.length} of {s.n}.</p>}
          </div>
          <div>
            <h3 className="text-lg font-bold">Calibration by chance</h3>
            <div className="mt-2 overflow-x-auto"><table className="w-full min-w-[520px] text-left text-[15px]">
              <thead className="text-[13px] text-muted"><tr><th className="py-1">Stated chance</th><th className="text-right">Cases</th><th className="text-right">Ours said</th><th className="text-right">Happened</th><th className="text-right">Market said</th><th className="text-right">Happened</th></tr></thead>
              <tbody>{d.calibration.model.map((b, i) => { const m = d.calibration.market[i]; return (
                <tr key={b.bucket} className="border-t border-bg"><td className="py-1">{b.bucket}</td><td className="text-right">{b.n}</td><td className="text-right">{plain(b.stated)}</td><td className="text-right">{plain(b.realized)}</td><td className="text-right">{m ? plain(m.stated) : ""}</td><td className="text-right">{m ? plain(m.realized) : ""}</td></tr>
              ); })}</tbody>
            </table></div>
          </div>
          <p className="text-[13px] text-muted">Rule fixed before scoring: docs/LEANS_PREREG.md, hash {d.rule_sha256.slice(0, 12)}. Prices are Kalshi mid prices; the cost of crossing the spread is not subtracted. Game totals, spreads and moneylines cannot be tested because the model's game numbers come from the market.</p>
        </>
      )}
    </section>
  );
}
