import { useEffect, useState } from "react";
import { api } from "../api";
import type { TdCardData } from "../types";
import { cn, num, pct } from "../lib";
import { Badge, Callout } from "./ui/primitives";

const ord = (n: number) => `${n}${n % 100 >= 11 && n % 100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th"}`;

function Block({ title, right, children, open = true }: { title: string; right?: string; children: React.ReactNode; open?: boolean }) {
  return (
    <details open={open} className="group bg-panel2">
      <summary className="flex min-h-[44px] cursor-pointer list-none items-center justify-between gap-3 px-4 text-[15px] font-bold uppercase tracking-wide text-white">
        <span>{title}</span>
        <span className="flex items-center gap-3 text-sm font-normal normal-case tracking-normal text-muted">{right}<span aria-hidden className="group-open:rotate-180">▾</span></span>
      </summary>
      <div className="space-y-2 px-4 pb-4">{children}</div>
    </details>
  );
}

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-line/50 px-3 py-2.5">
      <div className="text-xs uppercase tracking-wide text-muted">{label}</div>
      <div className="text-xl font-bold text-white">{value}</div>
      {sub && <div className="text-xs text-muted">{sub}</div>}
    </div>
  );
}

function Row({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-line/60 py-1.5 last:border-0">
      <span className="text-[15px] text-slate-300">{label}{sub && <span className="block text-xs text-muted">{sub}</span>}</span>
      <span className="text-[15px] font-semibold text-white">{value}</span>
    </div>
  );
}

const rankTone = (r: number | null) => (r === null ? "text-muted" : r <= 8 ? "text-emerald-300" : r >= 25 ? "text-red-300" : "text-amber-300");

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

  if (error) return <Callout tone="amber">No touchdown card for {player}: he has no rushes or targets in his team's last five games ({error}).</Callout>;
  if (!c) return <div className="px-4 py-3 text-muted">Building the card…</div>;
  const p = c.profile;
  const s = c.script;
  const ranks = c.opportunity.ranks;
  const film = c.window.weeks.length ? `weeks ${c.window.weeks[0]} to ${c.window.weeks[c.window.weeks.length - 1]}` : "";
  const fav = s.favored_by === null ? null : s.favored_by >= 0 ? `Favored by ${num(s.favored_by, 1)}` : `Underdog by ${num(-s.favored_by, 1)}`;

  return (
    <div className="space-y-1 pb-1">
      <div className="px-4 pt-1 text-sm text-muted">{c.tagline || "No standout signals"} · based on {film} ({c.window.games} games)</div>
      <div className="flex flex-wrap items-center gap-1.5 px-4 pb-2">
        {c.tags.map((t) => <Badge key={t.label} tone={t.fired ? "green" : "neutral"} className={cn(!t.fired && "opacity-50 line-through")} title={t.why}>{t.label}</Badge>)}
      </div>
      <Block title="Why the tags fired" right={`${c.fired} of ${c.tags.length}`} open={false}>
        {c.tags.map((t) => <Row key={t.label} label={t.label} sub={t.why} value={t.fired ? "Yes" : "No"} />)}
      </Block>

      <div className="flex flex-wrap gap-1.5 px-4 py-1.5">
        {fav && <Badge>{fav}</Badge>}
        {s.total !== null && <Badge>Total {num(s.total, 1)}</Badge>}
        {s.implied !== null && <Badge>Implied {num(s.implied, 1)} pts</Badge>}
        {s.pace_rank !== null && <Badge>Pace {ord(s.pace_rank)} of 32</Badge>}
      </div>

      <div className="grid grid-cols-2 gap-1 px-0 sm:grid-cols-5">
        <Tile label="Red-zone share" value={pct(p.rz_role)} sub="of team's red-zone touches" />
        <Tile label="Touches a game" value={num(p.touches_pg, 1)} sub="carries + targets" />
        <Tile label="Goal line a game" value={num(p.gl_pg, 1)} sub="touches inside the 5" />
        <Tile label="Target share" value={pct(p.target_share)} />
        <Tile label="TD rate" value={pct(p.td_rate)} sub="touchdowns per touch" />
      </div>

      {c.tdp !== null && (
        <div className="px-4 py-2">
          <div className="flex justify-between text-[15px]"><span className="text-slate-300">Anytime-touchdown chance</span><span className="font-bold text-white">{pct(c.tdp)}</span></div>
          <div className="mt-1 h-2 bg-line" aria-hidden><div className="h-2 bg-accent" style={{ width: `${Math.min(100, (c.tdp ?? 0) * 100)}%` }} /></div>
        </div>
      )}

      {c.role_tax && (
        <Block title={`Role tax · ${c.role_tax.role}`} right={`vs ${c.opp}`}>
          <div className="grid grid-cols-[1fr_5rem_5rem_3.5rem] gap-x-2 text-xs uppercase tracking-wide text-muted"><span>Per game</span><span className="text-right">Him</span><span className="text-right">{c.opp} allows</span><span className="text-right">Rank</span></div>
          {c.role_tax.rows.map((r) => (
            <div key={r.metric} className="grid grid-cols-[1fr_5rem_5rem_3.5rem] items-center gap-x-2 border-b border-line/60 py-1 text-[15px] last:border-0">
              <span className="text-slate-300">{r.metric}</span>
              <span className="text-right text-white">{num(r.him, 1)}</span>
              <span className="text-right text-white">{num(r.allows, 1)}</span>
              <span className={cn("text-right font-semibold", rankTone(r.rank))}>{r.rank ?? "–"}</span>
            </div>
          ))}
          <div className="text-xs text-muted">Rank 1 means the defense allows the most of that to the same role (32 teams, last seven games).</div>
        </Block>
      )}

      {c.leaks.length > 0 && (
        <Block title={`Leaks · ${c.opp}`} right={`${c.leaks.filter((l) => l.hits_role).length} hit his role`}>
          {c.leaks.map((l) => <div key={l.text} className={cn("px-3 py-2 text-[15px]", l.hits_role ? "bg-[#18281e] text-white" : "bg-line/50 text-slate-300")}>{l.text}</div>)}
        </Block>
      )}

      <Block title="Expected touchdowns" right={`${film}`}>
        <div className="grid grid-cols-3 gap-1">
          <Tile label="Expected TDs" value={num(c.cheat.expected, 1)} sub="from where his touches happen" />
          <Tile label="Scored" value={num(c.cheat.scored, 0)} />
          <Tile label="TD debt" value={`${c.cheat.debt > 0 ? "+" : ""}${num(c.cheat.debt, 1)}`} sub={c.cheat.debt > 0.5 ? "due to convert" : c.cheat.debt < -0.5 ? "running above expectation" : "about even"} />
        </div>
        <div className="grid grid-cols-[1fr_4rem_4rem_4rem] gap-x-2 pt-1 text-xs uppercase tracking-wide text-muted"><span>Zone</span><span className="text-right">Carries</span><span className="text-right">Targets</span><span className="text-right">xTD</span></div>
        {c.cheat.zones.map((z) => (
          <div key={z.zone} className="grid grid-cols-[1fr_4rem_4rem_4rem] gap-x-2 border-b border-line/60 py-1 text-[15px] last:border-0">
            <span className="text-slate-300">{z.zone}</span><span className="text-right text-white">{z.carries}</span><span className="text-right text-white">{z.targets}</span><span className="text-right font-semibold text-white">{num(z.xtd, 2)}</span>
          </div>
        ))}
        <div className="text-xs text-muted">Each touch is priced by the league touchdown rate for that kind of touch, zone and position (2022 to 2025). Debt is expected minus scored: positive means the ball has found him in scoring spots more than the scoreboard shows.</div>
      </Block>

      <Block title="Baseline profile" right={film}>
        <Row label="Red-zone role" value={pct(p.rz_role)} sub={`${p.rz_claim.mine} of ${p.rz_claim.team_rz_touches} team red-zone touches`} />
        <Row label="Red-zone claim" value={pct(p.rz_claim.share)} sub={`${p.rz_claim.mine} of ${p.rz_claim.group} ${p.rz_claim.group_label} red-zone touches`} />
        <Row label="Red-zone carries / targets a game" value={`${num(p.rz_carries_pg, 1)} / ${num(p.rz_targets_pg, 1)}`} />
        <Row label="Team red-zone trips a game" value={num(p.team_rz_trips_pg, 1)} sub={`conversion ${pct(p.team_rz_td_rate)}`} />
        <Row label={`${c.opp} red-zone TD rate allowed`} value={pct(p.opp_rz_td_rate_allowed)} sub={p.opp_rz_rank ? `${ord(p.opp_rz_rank)} highest of 32` : undefined} />
      </Block>

      <Block title="Opportunity factors" right={`${c.opp} defense`}>
        <Row label="Matchup" value={`${num(c.opportunity.matchup_pg, 2)} TD/g`} sub={`TDs ${c.opp} allowed to ${c.pos} in its last ${c.opportunity.table.length} games`} />
        <div className="overflow-x-auto">
          <table className="w-full text-[15px]">
            <thead><tr className="text-xs uppercase tracking-wide text-muted"><th className="py-1 text-left font-normal">Game</th>{["RB", "WR", "TE", "QB"].map((k) => <th key={k} className={cn("py-1 text-right font-normal", k === c.pos && "text-white")}>{k}</th>)}</tr></thead>
            <tbody>
              {c.opportunity.table.map((r) => (
                <tr key={r.week} className="border-t border-line/60"><td className="py-1 text-slate-300">W{r.week} {r.vs}</td>{(["RB", "WR", "TE", "QB"] as const).map((k) => <td key={k} className={cn("py-1 text-right", r[k] > 0 ? "font-semibold text-white" : "text-muted")}>{r[k]}</td>)}</tr>
              ))}
              <tr className="border-t border-line"><td className="py-1 text-white">Total</td>{["RB", "WR", "TE", "QB"].map((k) => <td key={k} className="py-1 text-right font-semibold text-white">{c.opportunity.totals[k] ?? 0}</td>)}</tr>
              <tr><td className="py-1 text-slate-300">Rank (1 = most)</td>{["RB", "WR", "TE", "QB"].map((k) => <td key={k} className={cn("py-1 text-right font-semibold", rankTone(ranks[k] ?? null))}>{ranks[k] ?? "–"}</td>)}</tr>
            </tbody>
          </table>
        </div>
        {c.opportunity.adv[c.pos] !== undefined && <Row label="Advantage" value={`${c.opportunity.adv[c.pos] >= 0 ? "+" : ""}${(c.opportunity.adv[c.pos] * 100).toFixed(0)}%`} sub={`his offense's share of touchdowns to ${c.pos} minus the share ${c.opp} gives up there`} />}
        <Row label="Snap share" value={pct(c.opportunity.snap_share)} />
        <Row label="Games since a TD" value={String(c.opportunity.games_since_td)} />
      </Block>
    </div>
  );
}
