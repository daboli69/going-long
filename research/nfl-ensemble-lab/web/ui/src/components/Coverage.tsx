import { useEffect, useState } from "react";
import { api } from "../api";
import type { CovPosition, CovRate, CovShare, CovSide, Coverage } from "../types";
import { cn } from "../lib";
import { Callout, Segmented } from "./ui/primitives";

const POS = ["WR", "TE", "RB"] as const;
const SEG = { WR: "bg-white text-bg", TE: "bg-chart text-bg", RB: "bg-info text-bg" } as const;
const pc = (x: number, d = 0) => `${(x * 100).toFixed(d)}%`;
const sg = (x: number, d = 1) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(d)}`;
const SHELL: Record<string, string> = { COVER_1: "Cover 1", COVER_2: "Cover 2", COVER_3: "Cover 3", COVER_4: "Cover 4", OTHER: "Cover 0, 6, 2-man" };

function ShareBar({ s, label }: { s: CovShare; label: string }) {
  return (
    <div role="img" aria-label={`${label}: ${POS.map((p) => `${p} ${pc(s[p])}`).join(", ")}`} className="flex h-7 gap-0.5 bg-panel2">
      {POS.map((p) => (
        <div key={p} style={{ flex: Math.max(s[p], 0.001) }} className={cn("flex min-w-0 items-center justify-center overflow-hidden whitespace-nowrap text-[13px] font-bold", SEG[p])}>
          {s[p] >= 0.09 ? `${p} ${pc(s[p])}` : ""}
        </div>
      ))}
    </div>
  );
}

function RateRow({ r, scale }: { r: CovRate; scale: number }) {
  const diff = (r.pct - r.league) * 100;
  return (
    <div className="grid grid-cols-[5.5rem_1fr_6.5rem] items-center gap-2 border-t sm:grid-cols-[7.5rem_1fr_9.5rem] sm:gap-3 border-t border-bg py-1.5 text-[15px] first:border-t-0">
      <span>{r.label}</span>
      <div role="img" aria-label={`${r.label} ${pc(r.pct)}, league ${pc(r.league)}`} className="relative h-4 bg-panel2">
        <div className="absolute inset-y-0 left-0 bg-white" style={{ width: `${Math.min(r.pct / scale, 1) * 100}%` }} />
        <div className="absolute -inset-y-0.5 w-0.5 bg-accent" style={{ left: `${Math.min(r.league / scale, 1) * 100}%` }} />
      </div>
      <span className="text-right text-muted tabular-nums"><span className="text-white">{pc(r.pct)}</span> <span className="text-[13px]">({sg(diff, 0)} pts)</span></span>
    </div>
  );
}

function quickReads(s: CovSide): string[] {
  const out: string[] = [];
  const all = [...s.defense_mix.shells, ...s.defense_mix.looks.filter((l) => l.key === "hi1" || l.key === "hi2")];
  const top = [...all].sort((a, b) => (b.pct - b.league) - (a.pct - a.league))[0];
  const man = s.defense_mix.looks.find((l) => l.key === "man");
  if (top) out.push(`${s.defense} leans on ${top.label.toLowerCase()} (${pc(top.pct)}, ${sg((top.pct - top.league) * 100, 0)} pts against the league)${man ? ` and plays man ${pc(man.pct)} of the time (league ${pc(man.league)})` : ""}.`);
  const notable = s.positions.filter((p) => !p.read.startsWith("Near league average"));
  notable.slice(0, 3).forEach((p) => out.push(`${p.pos}: ${p.read.replace(/ Small sample\.$/, "")}`));
  if (s.by_coverage && s.qb.name) {
    const w = [...s.by_coverage].sort((a, b) => a.epa - b.epa);
    out.push(`${s.qb.name}'s weakest coverage by EPA is ${SHELL[w[0].key]} (${sg(w[0].epa, 2)}) and his best is ${SHELL[w[w.length - 1].key]} (${sg(w[w.length - 1].epa, 2)}), after pulling small samples toward the league.`);
  }
  return out;
}

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="text-lg font-bold">{title}</h3>
      {hint && <p className="max-w-3xl text-[14px] text-muted">{hint}</p>}
      {children}
    </section>
  );
}

function PosTable({ rows, def }: { rows: CovPosition[]; def: string }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-left text-[15px]">
        <caption className="sr-only">{def} pass defense by receiver position</caption>
        <thead className="text-[13px] text-muted"><tr>
          <th scope="col" className="py-1">Position</th><th scope="col" className="text-right">Share of targets</th><th scope="col" className="text-right">Targets per game</th>
          <th scope="col" className="text-right">Yards per target</th><th scope="col" className="text-right">20+ yard plays</th><th scope="col" className="text-right">EPA per target</th><th scope="col" className="pl-4">Read</th>
        </tr></thead>
        <tbody>{rows.map((p) => (
          <tr key={p.pos} className="border-t border-bg align-top">
            <th scope="row" className="py-2 font-bold">{p.pos}<div className="text-[13px] font-normal text-muted">{p.nfl_targets} targets</div></th>
            <td className="py-2 text-right tabular-nums">{pc(p.share, 1)}<div className="text-[13px] text-muted">{sg((p.share - p.share_league) * 100)} pts</div></td>
            <td className="py-2 text-right tabular-nums">{p.tgt_pg.toFixed(1)}<div className="text-[13px] text-muted">#{p.tgt_rank} of 32 (league {p.tgt_pg_league.toFixed(1)})</div></td>
            <td className="py-2 text-right tabular-nums">{p.ypt.toFixed(1)}<div className="text-[13px] text-muted">{sg(p.ypt - p.ypt_league)} vs league</div></td>
            <td className="py-2 text-right tabular-nums">{pc(p.expl, 1)}<div className="text-[13px] text-muted">{sg((p.expl - p.expl_league) * 100)} pts</div></td>
            <td className="py-2 text-right tabular-nums">{sg(p.epa, 2)}<div className="text-[13px] text-muted">{sg(p.epa - p.epa_league, 2)} vs league</div></td>
            <td className="min-w-[200px] py-2 pl-4 text-slate-300">{p.read}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function Side({ s, cov }: { s: CovSide; cov: Coverage }) {
  const qb = s.qb.name ?? `${s.qb_team} quarterback`;
  const reads = quickReads(s);
  const scale = 0.5;
  return (
    <div className="space-y-7">
      {s.note && <Callout tone="amber">{s.note}</Callout>}
      {s.qb.missing && <Callout tone="amber">{qb} has no coverage-tagged passes in 2022 to 2025, so there is no quarterback split to show. The defense side below still applies.</Callout>}
      {s.qb.untagged_2026 ? <p className="text-[14px] text-muted">{s.qb.untagged_2026} of {qb}'s 2026 passes have no coverage tag yet and are not in his splits.</p> : null}

      {reads.length > 0 && (
        <Section title="Quick read">
          <ul className="max-w-3xl list-disc space-y-1 pl-5 text-[15px] text-slate-300">{reads.map((r) => <li key={r}>{r}</li>)}</ul>
        </Section>
      )}

      <Section title={`What ${s.defense} runs`} hint={`Share of pass snaps, FantasyPoints data: ${s.defense_mix.weeks} games of 2026 plus last season as ${cov.params.k_weeks} games of prior. The yellow tick is the league rate. Scale 0 to 50%.`}>
        <div className="grid gap-x-10 gap-y-4 lg:grid-cols-2">
          <div><h4 className="pb-1 text-[13px] text-muted">Coverage shells</h4>{s.defense_mix.shells.map((r) => <RateRow key={r.key} r={r} scale={scale} />)}</div>
          <div><h4 className="pb-1 text-[13px] text-muted">Looks and pressure</h4>{s.defense_mix.looks.map((r) => <RateRow key={r.key} r={r} scale={r.key === "blitz" ? 0.7 : r.key === "zone" ? 1 : scale} />)}</div>
        </div>
      </Section>

      {s.by_coverage && s.compare && (
        <>
          <Section title={`${qb} by coverage`} hint={`Where his targets go and his EPA per pass, 2022 to 2025 (${s.qb.tagged} tagged passes). Small samples are pulled toward the league. The last column is how often ${s.defense} plays that coverage.`}>
            <div>
              <div className="hidden grid-cols-[8.5rem_1fr_9rem_6rem] gap-3 pb-1 text-[13px] text-muted sm:grid"><span>Coverage</span><span>Share of his targets</span><span className="text-right">EPA per pass</span><span className="text-right">{s.defense} plays</span></div>
              {s.by_coverage.map((c) => (
                <div key={c.key} className="grid grid-cols-1 gap-1.5 border-t border-bg py-2 text-[15px] sm:grid-cols-[8.5rem_1fr_9rem_6rem] sm:items-center sm:gap-3 sm:py-1.5">
                  <span className="flex items-baseline justify-between gap-2 sm:block">{SHELL[c.key]}<span className="block text-[13px] text-muted">{c.att} passes</span></span>
                  <ShareBar s={c.shares} label={SHELL[c.key]} />
                  <span className="flex items-baseline justify-between gap-2 tabular-nums sm:block sm:text-right"><span>{sg(c.epa, 2)} EPA <span className="text-[13px] text-muted sm:block">raw {c.raw_epa === null ? "n/a" : sg(c.raw_epa, 2)}</span></span><span className="text-[13px] text-muted sm:hidden">{s.defense} plays it {pc(c.defense_weight)}</span></span>
                  <span className="hidden text-right tabular-nums text-muted sm:block">{pc(c.defense_weight)}</span>
                </div>
              ))}
            </div>
          </Section>

          <Section title={`${qb} against ${s.defense}`} hint="Three views of where the targets go. The middle row applies the defense's coverage rates to his habits. It does not know the game plan, injuries or who is playing.">
            <div className="text-[15px]">
              {[{ t: "His usual mix", sh: s.compare.usual, e: s.compare.usual_epa }, { t: `Expected against ${s.defense}`, sh: s.compare.expected, e: s.compare.expected_epa }, { t: `${s.defense} allows`, sh: s.allowed_share, e: null as number | null }].map((r) => (
                <div key={r.t} className="grid grid-cols-1 gap-1.5 border-t border-bg py-2 first:border-t-0 sm:grid-cols-[11rem_1fr_6rem] sm:items-center sm:gap-3">
                  <span className="flex items-baseline justify-between gap-2"><span>{r.t}</span><span className="tabular-nums text-muted sm:hidden">{r.e === null ? "" : `${sg(r.e, 2)} EPA`}</span></span>
                  <ShareBar s={r.sh} label={r.t} />
                  <span className="hidden text-right tabular-nums sm:block">{r.e === null ? "" : `${sg(r.e, 2)} EPA`}</span>
                </div>
              ))}
            </div>
          </Section>
        </>
      )}

      <Section title={`${s.defense} by receiver position`} hint="Targets per game and fantasy points come from FantasyPoints data (2026 plus last season as prior). Share of targets, 20+ yard plays and EPA come from play-by-play. Volume is read from share of targets, since targets per game follows how many passes a defense sees.">
        <PosTable rows={s.positions} def={s.defense} />
      </Section>

      {s.receivers.length > 0 && (
        <Section title={`${s.qb_team} receivers against man and zone`} hint={`Yards per route run, 2025 and 2026 to date, FantasyPoints data. Splits with few routes are pulled toward the receiver's overall number (weight ${cov.params.shrink_routes} routes). The last column weights his man and zone rates by how often ${s.defense} plays each.`}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-[15px]">
              <caption className="sr-only">{s.qb_team} receivers, yards per route against man and zone</caption>
              <thead className="text-[13px] text-muted"><tr><th scope="col" className="py-1">Receiver</th><th scope="col" className="text-right">Routes</th><th scope="col" className="text-right">Overall</th><th scope="col" className="text-right">Vs man</th><th scope="col" className="text-right">Vs zone</th><th scope="col" className="text-right">Against {s.defense}</th></tr></thead>
              <tbody>{s.receivers.map((r) => (
                <tr key={r.name} className="border-t border-bg">
                  <th scope="row" className="py-1.5 font-normal">{r.name} <span className="text-[13px] text-muted">{r.pos}</span></th>
                  <td className="text-right tabular-nums">{r.routes}</td>
                  <td className="text-right tabular-nums">{r.yprr.toFixed(2)}</td>
                  <td className="text-right tabular-nums">{r.man_yprr.toFixed(2)}<span className="block text-[13px] text-muted">{r.man_routes} routes</span></td>
                  <td className="text-right tabular-nums">{r.zone_yprr.toFixed(2)}<span className="block text-[13px] text-muted">{r.zone_routes} routes</span></td>
                  <td className="text-right tabular-nums">{r.edge === undefined ? "n/a" : sg(r.edge, 2)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </Section>
      )}
    </div>
  );
}

export function CoverageView({ gid }: { gid: string }) {
  const [d, setD] = useState<Coverage | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [side, setSide] = useState(0);
  useEffect(() => {
    setD(null); setErr(null); setSide(0);
    api.coverage(gid).then(setD).catch((e) => setErr(String(e.message ?? e)));
  }, [gid]);
  if (err) return <Callout tone="amber">Could not load the coverage matchup: {err}</Callout>;
  if (!d) return <p className="text-muted">Loading coverage matchup.</p>;
  const labels = d.sides.map((s) => `${s.qb_team} QB`);
  return (
    <section aria-labelledby="cov-h" className="space-y-6">
      <div>
        <h2 id="cov-h" className="text-xl font-bold">Coverage matchup</h2>
        <p className="mt-1 max-w-3xl text-[15px] text-muted">How each quarterback has done against each coverage, and what the defense he faces runs and gives up by receiver position. This is history, not a forecast or a pick, and it does not change any number elsewhere in the app. FantasyPoints data runs through Week {d.fpds_weeks}; coverage tags for quarterback splits end with 2025.</p>
      </div>
      <Segmented label="Quarterback" options={labels} value={labels[side]} onChange={(v) => setSide(labels.indexOf(v))} />
      <Side key={side} s={d.sides[side]} cov={d} />
      <p className="max-w-3xl text-[13px] text-muted">The two data sources name coverages differently, so the groups are matched by number (Cover 1 to Cover 1, and so on; Cover 0, Cover 6 and 2-man are grouped). A quarterback's starter is the one with the most passes in his team's latest game unless the latest injury report has him out. Explosive means a completion of 20 or more yards.</p>
    </section>
  );
}
