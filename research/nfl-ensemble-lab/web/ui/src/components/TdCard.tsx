import { useEffect, useState } from "react";
import { api } from "../api";
import type { TdCardData } from "../types";
import { cn, num, pct } from "../lib";
import { Callout } from "./ui/primitives";

const ord = (n: number) => `${n}${n % 100 >= 11 && n % 100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th"}`;

// A closed section: title and one fact on the line, the detail one tap away.
function Fold({ title, right, children }: { title: string; right?: string; children: React.ReactNode }) {
  return (
    <details className="group border-t border-bg">
      <summary className="flex min-h-[44px] cursor-pointer list-none items-center justify-between gap-3 text-[15px] [&::-webkit-details-marker]:hidden">
        <span>{title}</span>
        <span className="ml-auto text-sm text-muted">{right}</span>
        <span className="text-sm text-accent group-open:hidden">Show</span>
        <span className="hidden text-sm text-accent group-open:inline">Hide</span>
      </summary>
      <div className="space-y-1 pb-3">{children}</div>
    </details>
  );
}

const Tile = ({ label, value, sub }: { label: string; value: string; sub?: string }) => (
  <div className="bg-raised px-3 py-2">
    <div className="text-[13px] text-muted">{label}</div>
    <div className="text-xl font-bold leading-snug text-white">{value}</div>
    {sub && <div className="text-[13px] text-muted">{sub}</div>}
  </div>
);

const Fact = ({ label, value, sub }: { label: string; value: string; sub?: string }) => (
  <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 border-t border-bg py-1.5 text-sm first:border-0">
    <span className="text-slate-300">{label}{sub && <small className="block text-[13px] text-muted">{sub}</small>}</span>
    <b className="text-right">{value}</b>
  </div>
);

const Head = ({ cols }: { cols: string[] }) => (
  <tr className="text-[13px] text-muted">{cols.map((c, i) => <th key={c} className={cn("py-1 font-normal", i ? "text-right" : "text-left")}>{c}</th>)}</tr>
);

export function TdCard({ gid, team, player }: { gid: string; team: string; player: string }) {
  const [c, setC] = useState<TdCardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    setC(null);
    setError(null);
    api.tdcard(gid, team, player).then((x) => { if (alive) setC(x); }).catch((e) => { if (alive) setError(String(e)); });
    return () => { alive = false; };
  }, [gid, team, player]);

  if (error) return <Callout tone="amber">No touchdown card for {player}: no rushes or targets in the team's last five games ({error}).</Callout>;
  if (!c) return <p className="text-sm text-muted">Building the card…</p>;
  const p = c.profile, s = c.script, ranks = c.opportunity.ranks;
  const weeks = c.window.weeks.length ? `weeks ${c.window.weeks[0]} to ${c.window.weeks[c.window.weeks.length - 1]}` : "";
  const fired = c.tags.filter((t) => t.fired);
  const fav = s.favored_by === null ? null : s.favored_by >= 0 ? `Favored by ${num(s.favored_by, 1)}` : `Underdog by ${num(-s.favored_by, 1)}`;
  const script = [fav, s.total !== null ? `total ${num(s.total, 1)}` : null, s.implied !== null ? `implied ${num(s.implied, 1)} points` : null, s.pace_rank !== null ? `pace ${ord(s.pace_rank)} of 32` : null].filter(Boolean).join(", ");
  return (
    <div>
      <p className="text-sm text-muted">{c.tagline || "No standout signals"}. Built from {weeks}, {c.window.games} games.</p>
      {fired.length > 0 && <div className="mt-2 flex flex-wrap gap-x-2 gap-y-1">{fired.map((t) => <span key={t.label} title={t.why} className="bg-raised px-2 py-0.5 text-sm">{t.label}</span>)}</div>}
      <div className="my-2 grid grid-cols-2 gap-0.5 sm:grid-cols-3 xl:grid-cols-5">
        <Tile label="Red-zone share" value={pct(p.rz_role)} sub="of team touches" />
        <Tile label="Touches a game" value={num(p.touches_pg, 1)} sub="carries and targets" />
        <Tile label="Goal line a game" value={num(p.gl_pg, 1)} sub="inside the 5" />
        <Tile label="Target share" value={pct(p.target_share)} />
        <Tile label="TD rate" value={pct(p.td_rate)} sub="per touch" />
      </div>
      {script && <p className="text-sm text-muted">{script}.</p>}

      <Fold title="Why the tags fired" right={`${c.fired} of ${c.tags.length}`}>
        {c.tags.map((t) => <Fact key={t.label} label={t.label} sub={t.why} value={t.fired ? "Yes" : "No"} />)}
      </Fold>

      {c.role_tax && (
        <Fold title={`Role tax, ${c.role_tax.role}`} right={`against ${c.opp}`}>
          <table className="w-full text-sm">
            <thead><Head cols={["Per game", "Him", `${c.opp} allows`, "Rank"]} /></thead>
            <tbody>
              {c.role_tax.rows.map((r) => (
                <tr key={r.metric} className="border-t border-bg"><td className="py-1.5 text-slate-300">{r.metric}</td><td className="text-right">{num(r.him, 1)}</td><td className="text-right">{num(r.allows, 1)}</td><td className="text-right font-semibold">{r.rank ?? "none"}</td></tr>
              ))}
            </tbody>
          </table>
          <p className="text-[13px] text-muted">Rank 1 means the defense allows the most to this role, of 32 teams over its last seven games.</p>
        </Fold>
      )}

      {c.leaks.length > 0 && (
        <Fold title={`Leaks, ${c.opp}`} right={`${c.leaks.filter((l) => l.hits_role).length} hit his role`}>
          {c.leaks.map((l) => <p key={l.text} className={cn("px-3 py-2 text-sm", l.hits_role ? "bg-[#18281e] text-white" : "bg-raised text-slate-300")}>{l.text}{l.hits_role ? " This hits his role." : ""}</p>)}
        </Fold>
      )}

      <Fold title="Expected touchdowns" right={`${num(c.cheat.expected, 1)} expected, ${num(c.cheat.scored, 0)} scored`}>
        <div className="grid grid-cols-3 gap-0.5">
          <Tile label="Expected TDs" value={num(c.cheat.expected, 1)} sub="from where his touches happen" />
          <Tile label="Scored" value={num(c.cheat.scored, 0)} />
          <Tile label="TD debt" value={`${c.cheat.debt > 0 ? "+" : ""}${num(c.cheat.debt, 1)}`} sub={c.cheat.debt > 0.5 ? "due to convert" : c.cheat.debt < -0.5 ? "running above expectation" : "about even"} />
        </div>
        <table className="w-full text-sm">
          <thead><Head cols={["Zone", "Carries", "Targets", "xTD"]} /></thead>
          <tbody>
            {c.cheat.zones.map((z) => (
              <tr key={z.zone} className="border-t border-bg"><td className="py-1.5 text-slate-300">{z.zone}</td><td className="text-right">{z.carries}</td><td className="text-right">{z.targets}</td><td className="text-right font-semibold">{num(z.xtd, 2)}</td></tr>
            ))}
          </tbody>
        </table>
        <p className="text-[13px] text-muted">Each touch is priced by the league touchdown rate for that kind of touch, zone and position (2022 to 2025). Debt is expected minus scored: positive means the ball has found him in scoring spots more than the scoreboard shows.</p>
      </Fold>

      <Fold title="Baseline profile" right={weeks}>
        <Fact label="Red-zone role" value={pct(p.rz_role)} sub={`${p.rz_claim.mine} of ${p.rz_claim.team_rz_touches} team red-zone touches`} />
        <Fact label="Red-zone claim" value={pct(p.rz_claim.share)} sub={`${p.rz_claim.mine} of ${p.rz_claim.group} ${p.rz_claim.group_label} red-zone touches`} />
        <Fact label="Red-zone carries and targets a game" value={`${num(p.rz_carries_pg, 1)} / ${num(p.rz_targets_pg, 1)}`} />
        <Fact label="Team red-zone trips a game" value={num(p.team_rz_trips_pg, 1)} sub={`conversion ${pct(p.team_rz_td_rate)}`} />
        <Fact label={`${c.opp} red-zone TD rate allowed`} value={pct(p.opp_rz_td_rate_allowed)} sub={p.opp_rz_rank ? `${ord(p.opp_rz_rank)} highest of 32` : undefined} />
      </Fold>

      <Fold title="Opportunity factors" right={`${c.opp} defense`}>
        <Fact label="Matchup" value={`${num(c.opportunity.matchup_pg, 2)} TD/g`} sub={`TDs ${c.opp} allowed to ${c.pos} in its last ${c.opportunity.table.length} games`} />
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[13px] text-muted"><th className="py-1 text-left font-normal">Game</th>{["RB", "WR", "TE", "QB"].map((k) => <th key={k} className={cn("py-1 text-right font-normal", k === c.pos && "text-white")}>{k}</th>)}</tr>
            </thead>
            <tbody>
              {c.opportunity.table.map((r) => (
                <tr key={r.week} className="border-t border-bg"><td className="py-1 text-slate-300">W{r.week} {r.vs}</td>{(["RB", "WR", "TE", "QB"] as const).map((k) => <td key={k} className={cn("py-1 text-right", r[k] > 0 ? "font-semibold text-white" : "text-muted")}>{r[k]}</td>)}</tr>
              ))}
              <tr className="border-t border-line"><td className="py-1 text-white">Total</td>{["RB", "WR", "TE", "QB"].map((k) => <td key={k} className="py-1 text-right font-semibold">{c.opportunity.totals[k] ?? 0}</td>)}</tr>
              <tr><td className="py-1 text-slate-300">Rank (1 = most)</td>{["RB", "WR", "TE", "QB"].map((k) => <td key={k} className="py-1 text-right font-semibold">{ranks[k] ?? "none"}</td>)}</tr>
            </tbody>
          </table>
        </div>
        {c.opportunity.adv[c.pos] !== undefined && <Fact label="Advantage" value={`${c.opportunity.adv[c.pos] >= 0 ? "+" : ""}${(c.opportunity.adv[c.pos] * 100).toFixed(0)}%`} sub={`his offense's share of touchdowns to ${c.pos} minus the share ${c.opp} gives up there`} />}
        <Fact label="Snap share" value={pct(c.opportunity.snap_share)} />
        <Fact label="Games since a TD" value={String(c.opportunity.games_since_td)} />
      </Fold>
    </div>
  );
}
