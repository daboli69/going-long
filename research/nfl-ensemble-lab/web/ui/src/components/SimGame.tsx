import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { SnapSimBody } from "./SnapSim";
import { api } from "../api";
import type { Band, Detail, PropRow, Sim, SimPlay } from "../types";
import { num, pct } from "../lib";
import { Callout, Card, Segmented } from "./ui/primitives";

const SPEEDS = [1, 2, 4];
const MS_PER_PLAY = 1500;
const BANNER: Record<string, string> = { TD: "Touchdown", FG: "Field goal", INT: "Interception", FUMBLE: "Fumble", PUNT: "Punt", DOWNS: "Turnover on downs" };

// ------------------------------------------------------------------ running box score
interface Line { att: number; comp: number; yds: number; td: number; int: number; sacks: number }
interface Box { qb: Line; rush: Map<string, [number, number, number, number]>; rec: Map<string, [number, number, number, number]> }

function boxScore(plays: SimPlay[], upto: number, teams: string[]): Record<string, Box> {
  const out: Record<string, Box> = {};
  for (const t of teams) out[t] = { qb: { att: 0, comp: 0, yds: 0, td: 0, int: 0, sacks: 0 }, rush: new Map(), rec: new Map() };
  for (const p of plays.slice(0, upto + 1)) {
    const b = out[p.team];
    const td = p.event === "TD" ? 1 : 0;
    const add = (m: Map<string, [number, number, number, number]>, k: string, y: number, caught = 1) => {
      const v = m.get(k) ?? [0, 0, 0, 0];
      m.set(k, [v[0] + caught, v[1] + y, v[2] + td, v[3] + 1]);  // catches or carries, yards, touchdowns, targets
    };
    if (p.kind === "pass") { b.qb.att++; b.qb.comp++; b.qb.yds += p.yards; b.qb.td += td; add(b.rec, p.player!, p.yards); }
    else if (p.kind === "incomplete") { b.qb.att++; if (p.event === "INT") b.qb.int++; if (p.player) add(b.rec, p.player, 0, 0); }
    else if (p.kind === "sack") b.qb.sacks++;
    else if (p.kind === "rush") add(b.rush, p.player!, p.yards);
  }
  return out;
}

const leaders = (m: Map<string, [number, number, number, number]>, n: number, by = 1) => [...m.entries()].sort((a, b) => b[1][by] - a[1][by] || b[1][1] - a[1][1]).slice(0, n);
const short = (name: string) => name.replace(/^another [A-Z]+ /, "Other ");

function TeamBox({ team, color, qb, box }: { team: string; color: string; qb: string; box: Box }) {
  const q = box.qb;
  return (
    <div className="space-y-3 text-[15px]">
      <div className="flex items-center gap-2 border-b border-line pb-1 text-lg font-bold text-white">
        <span className="inline-block h-4 w-1.5" style={{ background: color }} />{team}
      </div>
      <div>
        <div className="text-sm text-muted">Passing</div>
        <div className="flex justify-between"><span className="text-slate-300">{qb}</span><span className="font-medium text-white">{q.comp}/{q.att}, {q.yds} yds</span></div>
        <div className="text-sm text-muted">{q.td} TD · {q.int} INT · {q.sacks} sacked</div>
      </div>
      <Leaders title="Rushing" unit="car" rows={leaders(box.rush, 3)} empty="No carries yet" />
      <Leaders title="Receiving" unit="rec/tgt" rows={leaders(box.rec, 10, 3)} empty="No targets yet" targets />
    </div>
  );
}

function Leaders({ title, unit, rows, empty, targets = false }: { title: string; unit: string; rows: [string, [number, number, number, number]][]; empty: string; targets?: boolean }) {
  return (
    <div>
      <div className="flex justify-between text-sm text-muted"><span>{title}</span><span>{unit} / yds / TD</span></div>
      {rows.length === 0 && <div className="text-muted">{empty}</div>}
      {rows.map(([name, v]) => (
        <div key={name} className="flex justify-between"><span className="truncate pr-2 text-slate-300">{short(name)}</span><span className="whitespace-nowrap text-white">{targets ? `${v[0]}/${v[3]}` : v[0]} / {v[1]} / {v[2]}</span></div>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ field
function Field({ p, d, moved }: { p: SimPlay; d: Detail; moved: boolean }) {
  const X = (x: number) => x + 10;
  const ballX = X(moved ? p.x_end : p.x_start);
  const name = p.kind === "pass" || p.kind === "rush" ? short(p.player ?? "").split(" ").slice(-1)[0] : null;
  const showFirst = p.kind !== "fg" && p.kind !== "punt" && p.x_first !== p.x_start;
  const lines = Array.from({ length: 19 }, (_, i) => (i + 1) * 5);
  return (
    <svg viewBox="0 0 120 54" className="w-full" role="img" aria-label={p.text}>
      <rect x="0" y="0" width="120" height="54" fill="#1a5230" />
      <rect x="0" y="0" width="10" height="54" fill={d.away_color} />
      <rect x="110" y="0" width="10" height="54" fill={d.home_color} />
      <text x="5" y="27" fill="white" fontSize="4" fontWeight="700" textAnchor="middle" dominantBaseline="middle" transform="rotate(-90 5 27)">{d.away}</text>
      <text x="115" y="27" fill="white" fontSize="4" fontWeight="700" textAnchor="middle" dominantBaseline="middle" transform="rotate(90 115 27)">{d.home}</text>
      {lines.map((y) => <line key={y} x1={X(y)} x2={X(y)} y1="0" y2="54" stroke="rgba(255,255,255,0.35)" strokeWidth={y % 10 === 0 ? 0.3 : 0.15} />)}
      {[10, 20, 30, 40, 50, 60, 70, 80, 90].map((y) => (
        <text key={y} x={X(y)} y="49" fill="rgba(255,255,255,0.6)" fontSize="3" textAnchor="middle">{y <= 50 ? y : 100 - y}</text>
      ))}
      <line x1={X(p.x_start)} x2={X(p.x_start)} y1="0" y2="54" stroke="#60a5fa" strokeWidth="0.5" />
      {showFirst && <line x1={X(p.x_first)} x2={X(p.x_first)} y1="0" y2="54" stroke="#facc15" strokeWidth="0.5" />}
      {moved && p.x_end !== p.x_start && (
        <path d={p.kind === "pass" ? `M ${X(p.x_start)} 27 Q ${(X(p.x_start) + X(p.x_end)) / 2} 12 ${X(p.x_end)} 27` : `M ${X(p.x_start)} 27 L ${X(p.x_end)} 27`}
          fill="none" stroke="rgba(255,255,255,0.7)" strokeWidth="0.35" strokeDasharray={p.kind === "pass" ? "1 0.8" : undefined} />
      )}
      <g style={{ transform: `translate(${ballX}px, 27px)`, transition: moved ? "transform 700ms ease-out" : "none" }}>
        <ellipse rx="1.4" ry="0.9" fill="#a16207" stroke="white" strokeWidth="0.25" />
        {name && <text y="-2.5" fill="white" fontSize="2.8" fontWeight="700" textAnchor="middle" paintOrder="stroke" stroke="rgba(0,0,0,0.6)" strokeWidth="0.6">{name}</text>}
      </g>
      {moved && p.event && (
        <g>
          <rect x="35" y="19" width="50" height="16" rx="2" fill={p.event === "TD" || p.event === "FG" ? (p.team === d.home ? d.home_color : d.away_color) : "#0e0f11"} stroke="white" strokeWidth="0.3" />
          <text x="60" y="27.5" fill="white" fontSize="5" fontWeight="800" textAnchor="middle" dominantBaseline="middle">{BANNER[p.event].toUpperCase()}</text>
        </g>
      )}
    </svg>
  );
}

// ------------------------------------------------------------------ replay player
function Replay({ sim, d }: { sim: Sim; d: Detail }) {
  const plays = sim.replay!.plays;
  const [i, setI] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [moved, setMoved] = useState(false);
  const teams = [d.away, d.home];
  const box = useMemo(() => boxScore(plays, moved ? i : i - 1, teams), [plays, i, moved]);

  useEffect(() => {
    setMoved(false);
    const t = window.setTimeout(() => setMoved(true), 60);
    return () => window.clearTimeout(t);
  }, [i]);

  useEffect(() => {
    if (!playing) return;
    if (i >= plays.length - 1) { setPlaying(false); return; }
    const t = window.setTimeout(() => setI((x) => x + 1), MS_PER_PLAY / speed);
    return () => window.clearTimeout(t);
  }, [playing, i, speed, plays.length]);

  const p = plays[i];
  const before = i > 0 ? plays[i - 1].score : { [d.away]: 0, [d.home]: 0 };
  const score = moved ? p.score : before;
  const situation = p.kind === "fg" ? "Field goal try" : p.kind === "punt" ? "Punt" : `${["1st", "2nd", "3rd", "4th"][p.down - 1] ?? "4th"} & ${p.togo >= 100 - (p.team === d.away ? p.x_start : 100 - p.x_start) ? "goal" : p.togo} at ${p.spot}`;
  const last = i === plays.length - 1;

  return (
    <Card>
      <div className="mb-4 grid grid-cols-[1fr_auto_1fr] items-stretch">
        <div className="team-field flex items-center gap-2 px-3 py-2 text-white" style={{ "--team": d.away_color } as CSSProperties}>
          <span className="text-lg font-bold">{d.away}</span>
          <span className="ml-auto text-4xl font-bold">{score[d.away]}</span>
        </div>
        <div className="flex flex-col justify-center bg-panel2 px-3 text-center sm:px-5">
          <div className="font-semibold text-white">{last && moved ? "Final" : `Q${p.qtr} ${p.clock}`}</div>
          <div className="text-sm text-muted">{last && moved ? "simulated" : `${p.team} ball`}</div>
        </div>
        <div className="team-field flex items-center gap-2 px-3 py-2 text-white" style={{ "--team": d.home_color } as CSSProperties}>
          <span className="text-4xl font-bold">{score[d.home]}</span>
          <span className="ml-auto text-lg font-bold">{d.home}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[200px_1fr_200px]">
        <div className="order-2 lg:order-1"><TeamBox team={d.away} color={d.away_color} qb={sim.replay!.qbs[d.away]} box={box[d.away]} /></div>
        <div className="order-1 lg:order-2">
          <Field p={p} d={d} moved={moved} />
          <div className="mt-1 flex justify-between text-sm text-muted"><span>Play {i + 1} of {plays.length}</span><span>{situation}</span></div>
          <div className="mt-2 min-h-[3.25rem] bg-panel2 px-3 py-2 text-center text-base text-white">{p.text}</div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button className="min-h-[44px] bg-accent px-5 text-base font-semibold text-bg hover:bg-[#ffdb70]" onClick={() => { if (last) setI(0); setPlaying(!playing || last); }}>
              {playing ? "Pause" : last ? "Watch again" : i === 0 ? "Start replay" : "Resume"}
            </button>
            <div className="flex gap-0.5" role="group" aria-label="Replay speed">
              {SPEEDS.map((s) => (
                <button key={s} aria-pressed={s === speed} className={`min-h-[44px] min-w-[44px] px-3 text-base ${s === speed ? "bg-white text-bg" : "bg-panel2 text-slate-300 hover:bg-line"}`} onClick={() => setSpeed(s)}>{s}x</button>
              ))}
            </div>
            <button className="min-h-[44px] bg-panel2 px-4 text-base text-slate-300 hover:bg-line hover:text-white" onClick={() => { setPlaying(false); setI(plays.length - 1); }}>Skip to final</button>
          </div>
          <input type="range" min={0} max={plays.length - 1} value={i} onChange={(e) => { setPlaying(false); setI(Number(e.target.value)); }}
            className="mt-2 h-11 w-full accent-[#ffcf3f]" aria-label="Replay position" />
        </div>
        <div className="order-3"><TeamBox team={d.home} color={d.home_color} qb={sim.replay!.qbs[d.home]} box={box[d.home]} /></div>
      </div>
    </Card>
  );
}

// ------------------------------------------------------------------ other sections
function Range({ title, b, lo, hi, color }: { title: string; b: Band; lo: number; hi: number; color: string }) {
  const at = (x: number) => `${((x - lo) / (hi - lo)) * 100}%`;
  return (
    <Card>
      <h3 className="text-[15px] text-muted">{title}</h3>
      <div className="mt-1 text-[34px] font-bold text-white">{b.low} to {b.high}</div>
      <div className="relative my-3 h-2 bg-line">
        <div className="absolute h-2" style={{ left: at(b.low), width: `calc(${at(b.high)} - ${at(b.low)})`, background: color }} />
        <div className="absolute -top-1 h-4 w-1 bg-white" style={{ left: at(b.median) }} />
      </div>
      <div className="text-base text-slate-300">Middle result: <b className="text-white">{b.median}</b></div>
    </Card>
  );
}

function Conditions({ sim, d }: { sim: Sim; d: Detail }) {
  const w = sim.weather!;
  const has = w.status === "forecast" || w.status === "recorded";
  const cell = (label: string, value: string) => (
    <div><div className="text-sm text-muted">{label}</div><div className="text-base text-white">{value}</div></div>
  );
  return (
    <Card>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="font-semibold text-white">{d.date_label} · {d.time_label} ET · {d.stadium}</div>
        <div className="text-sm text-muted">{w.roof === "indoors" ? "Indoors" : w.roof === "retractable" ? "Retractable roof" : "Outdoors"}</div>
      </div>
      {has ? (
        <>
          <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
            {cell("Kickoff", `${w.temp_f}°F, ${w.condition!.toLowerCase()}`)}
            {cell("Wind", `${w.wind_mph} mph, gusts ${w.gust_mph}`)}
            {cell(w.status === "recorded" ? "Rain or snow" : "Chance of rain or snow", w.status === "recorded" ? `${w.precip_in} in` : `${w.precip_chance ?? 0}%`)}
            {cell("Source", w.source)}
          </div>
          <div className="mt-3 text-sm text-muted">{w.text} Wind and rain are the highest values in the first 3 hours. Weather is shown for context and does not change the forecast.</div>
        </>
      ) : <div className="mt-2 text-base text-slate-300">{w.text}</div>}
    </Card>
  );
}

function Injuries({ sim }: { sim: Sim }) {
  const r = sim.redistribution;
  const moves = sim.injury_moves ?? [];
  const moved = new Set(moves.map((m) => m.player));
  const rest = (sim.unavailable ?? []).filter((u) => !moved.has(u.player));
  const q = sim.questionable ?? [];
  if (!moves.length && !rest.length && !q.length) return <div className="text-base text-muted">No one in either lineup is listed as out{sim.injury_source ? ` on ${sim.injury_source}` : ""}.</div>;
  return (
    <Card>
      {moves.map((m) => (
        <div key={m.player} className="border-b border-line py-2 text-base last:border-0">
          <div><b className="text-white">{m.player}</b> <span className="text-muted">{m.team} · {m.status.toLowerCase()}</span></div>
          <div className="text-slate-300">{m.text}</div>
        </div>
      ))}
      {q.length > 0 && (
        <div className="border-b border-line py-2 text-base">
          <div className="text-sm text-muted">Listed questionable: each simulated game draws whether they play</div>
          {q.map((x) => (
            <div key={x.player} className="flex justify-between gap-3 py-0.5">
              <span><b className="text-white">{x.player}</b> <span className="text-muted">{x.team} · {x.group}</span></span>
              <span className="text-slate-300">plays {pct(x.chance)} of the time · {x.plays ? "plays in this game" : "sits in this game"}</span>
            </div>
          ))}
        </div>
      )}
      {rest.length > 0 && (
        <details className="text-base">
          <summary className="flex min-h-[44px] items-center text-muted hover:text-white">{rest.length} other player{rest.length === 1 ? "" : "s"} out who were not part of the regular rotation</summary>
          <div className="pb-2 text-slate-300">{rest.map((u) => `${u.player} (${u.team}, ${u.status.toLowerCase()})`).join(", ")}</div>
        </details>
      )}
      <div className="mt-2 text-sm leading-relaxed text-muted">
        From {sim.injury_source}. Players who are out or doubtful, on injured reserve, released, retired or inactive are left out of every game.
        A regular listed questionable plays at the rate regulars with that status played in 2022 to 2025 (about 7 in 10 for receivers, about half for quarterbacks).
        {r && <> Measured on real absences{r.fitted_on ? ` in ${r.fitted_on.join(" and ")}` : ""}: teams keep about {pct(r.kept_rec)} of a missing player's receiving yards and
        {" "}{pct(r.kept_rush)} of his rushing yards. About {pct(r.to_new_rec)} of the receiving share goes to the player who steps in; the rest goes to the regulars by
        their usual share, leaning toward the same position.</>}
        {" "}A backup quarterback gets the team's usual passing volume.
      </div>
    </Card>
  );
}

const POS_NAME: Record<string, string> = { WR: "Wide receivers", TE: "Tight ends", RB: "Running backs", QB: "Quarterbacks" };
const signed = (x: number) => `${x >= 0 ? "+" : "−"}${Math.abs(x * 100).toFixed(0)}%`;

function AllowedCard({ sim }: { sim: Sim }) {
  const a = sim.allowed;
  if (!a?.teams.length) return null;
  return (
    <Card>
      {a.teams.map((t) => {
        const byPos = new Map<string, typeof t.rows>();
        t.rows.forEach((r) => byPos.set(r.pos, [...(byPos.get(r.pos) ?? []), r]));
        return (
          <div key={t.team} className="border-b border-line py-2 text-base last:border-0">
            <div className="text-white"><b>{t.team} offense</b> <span className="text-muted">against the {t.versus} defense</span></div>
            {[...byPos.entries()].map(([pos, rs]) => (
              <div key={pos} className="flex justify-between gap-3 py-0.5">
                <span className="text-slate-300">{POS_NAME[pos] ?? pos}</span>
                <span className="text-slate-300">{rs.map((r) => `${r.stat} ${signed(r.factor - 1)}`).join(" · ")}</span>
              </div>
            ))}
          </div>
        );
      })}
      <div className="mt-2 text-sm leading-relaxed text-muted">
        The change applied to each player's number, from what the defense gave up to that position over its last six games compared with the league (FantasyPoints, converted to catches and yards).
        {a.passed_gate ? "" : " On games the fit had not seen, this did not beat the plain projection, so treat it as context rather than a proven improvement."} It is applied by choice.
      </div>
    </Card>
  );
}

function fpdsLine(r: PropRow): string | null {
  const f = r.fpds;
  if (!f || r.stat === "Passing yards") return null;
  const p = (x?: number) => (x === undefined ? null : `${Math.round(x * 100)}%`);
  const parts = r.stat === "Rushing yards"
    ? [p(f.att_pct) && `${p(f.att_pct)} of carries`, p(f.snap_pct) && `${p(f.snap_pct)} of snaps`, p(f.exp_run) && `${p(f.exp_run)} explosive runs`]
    : [p(f.tgt_pct) && `${p(f.tgt_pct)} of targets`, p(f.rte_pct) && `routes on ${p(f.rte_pct)} of passes`, p(f.ay_share) && `${p(f.ay_share)} of air yards`,
       f.yprr !== undefined ? `${f.yprr.toFixed(1)} yards per route` : null, f.rz_tgt !== undefined ? `${f.rz_tgt.toFixed(1)} red-zone targets a game` : null];
  const shown = parts.filter(Boolean);
  return shown.length ? `FantasyPoints, last ${f.weeks} week${f.weeks === 1 ? "" : "s"}: ${shown.join(" · ")}` : null;
}

function Spotlight({ sim, d }: { sim: Sim; d: Detail }) {
  const props = sim.players ?? [];
  const pick = (team: string) => {
    const mine = props.filter((r) => r.team === team);
    const best = (stat: string, n: number) => mine.filter((r) => r.stat === stat).sort((a, b) => b.typical - a.typical).slice(0, n);
    return [...best("Passing yards", 1), ...best("Rushing yards", 1), ...best("Receiving yards", 2)];
  };
  const row = (r: PropRow) => (
    <div key={r.player + r.stat} className="flex items-center justify-between border-b border-line py-2 last:border-0">
      <div><div className="text-base text-white">{r.player}</div><div className="text-sm text-muted">{r.stat.toLowerCase()}</div>
        {fpdsLine(r) && <div className="max-w-[28rem] text-sm text-muted">{fpdsLine(r)}</div>}</div>
      <div className="text-right"><div className="text-2xl font-bold text-white">{num(r.typical, 0)}</div>
        {r.range_low !== null && <div className="text-sm text-muted">8 in 10: {num(r.range_low, 0)} to {num(r.range_high, 0)}</div>}</div>
    </div>
  );
  return (
    <div className="grid grid-cols-1 gap-0.5 md:grid-cols-2">
      {[{ t: d.away, n: d.away_name, c: d.away_color }, { t: d.home, n: d.home_name, c: d.home_color }].map(({ t, n, c }) => (
        <Card key={t}>
          <h3 className="flex items-center gap-2 text-lg font-bold text-white"><span className="inline-block h-4 w-1.5" style={{ background: c }} />{n}</h3>
          <div className="mb-1 text-sm text-muted">From {sim.player_source?.[t]}{(sim.injury_moves ?? []).some((m) => m.team === t) ? ", adjusted for injuries" : ""}.</div>
          {pick(t).map(row)}
        </Card>
      ))}
    </div>
  );
}

function Defense({ sim, d }: { sim: Sim; d: Detail }) {
  return (
    <div className="grid grid-cols-1 gap-0.5 md:grid-cols-2">
      {sim.defense!.map((c) => (
        <Card key={c.team}>
          <h3 className="text-lg font-bold text-white">{c.team === d.away ? d.away_name : d.home_name} defense</h3>
          <div className="mb-2 text-sm text-muted">This season, {c.games} games. Rank 1 allows the most.</div>
          {c.rows.map((r) => (
            <div key={r.label} className="flex justify-between border-b border-line py-1.5 text-base last:border-0">
              <span className="text-slate-300">{r.label}</span>
              <span className="text-white"><b>{r.value}</b> <span className="text-muted">({r.rank})</span></span>
            </div>
          ))}
        </Card>
      ))}
    </div>
  );
}

const Section = ({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) => (
  <section className="space-y-3">
    <div><h2 className="text-xl font-bold text-white">{title}</h2>{note && <p className="mt-0.5 max-w-[75ch] text-[15px] leading-relaxed text-muted">{note}</p>}</div>
    {children}
  </section>
);

function fpdsNote(sim: Sim): string {
  const f = sim.fpds;
  if (!f?.tested) return "FantasyPoints metrics are shown but have not been tested yet, so they do not change any numbers.";
  const used = [f.receiving_yards_blend && "receiving yards", f.catches_for_thin_history && "catches"].filter(Boolean).join(" and ");
  return `FantasyPoints data runs through week ${f.through_week}. In tests on 2025 and 2026 games, adding its target share and routes run made ${used || "no stat"} more accurate, and its red-zone targets ${f.td_red_zone ? "improved" : "did not improve"} the pick of who catches touchdowns. Rushing and everything else stays on nflverse play-by-play.`;
}

type Mode = "random" | "typical" | "upset";
const MODE_LABEL: Record<Mode, string> = { random: "Random game", typical: "Typical game", upset: "Upset game" };
const MODE_OF: Record<string, Mode> = { "Random game": "random", "Typical game": "typical", "Upset game": "upset" };

function OwnView({ sim, d }: { sim: Sim; d: Detail }) {
  const o = sim.own;
  if (!o) return null;
  const ev = o.evidence;
  const mk = d.headline?.p_home;
  const row = (label: string, a: string, b: string) => (
    <div className="grid grid-cols-[1fr_auto_auto] gap-x-6 border-b border-line py-1.5 text-base last:border-0">
      <span className="text-slate-300">{label}</span><span className="text-right text-white">{a}</span><span className="text-right text-white">{b}</span>
    </div>
  );
  return (
    <Card>
      <div className="grid grid-cols-[1fr_auto_auto] gap-x-6 pb-1 text-sm text-muted"><span /><span className="text-right">Betting market</span><span className="text-right">Drive simulation</span></div>
      {row(`${d.home} win chance`, mk === undefined ? "n/a" : pct(mk), pct(o.p_home))}
      {row("Expected score", d.expected?.home_pts !== undefined ? `${d.away} ${num(d.expected.away_pts, 0)}, ${d.home} ${num(d.expected.home_pts, 0)}` : "n/a", `${d.away} ${num(o.away, 0)}, ${d.home} ${num(o.home, 0)}`)}
      {row("Total points", num(d.expected?.total, 1), num(o.total, 1))}
      <div className="mt-2 text-sm leading-relaxed text-muted">
        The drive simulation uses no betting line: each team's drives per game and its touchdown and field-goal rates per drive, plus what its opponent allows, as known before the game.
        {ev?.pick_accuracy && <> On 2025 and 2026 games the market's side won {pct(ev.pick_accuracy.market, 1)} of the time and the drive simulation's side {pct(ev.pick_accuracy.drive_sim, 1)}; they picked the same side in {pct(ev.same_pick ?? 0)} of games.</>}
        {ev?.used && !Object.values(ev.used).some(Boolean) && <> Blending the two did not beat the market alone, so the market sets the center of the simulated games. Every game still varies: the replay is a random draw, not the market's expected score.</>}
      </div>
    </Card>
  );
}

// A new random game each time a game is opened or a button is pressed; the same number always replays the same game.
const randomDraw = () => 1 + Math.floor(Math.random() * 9999);

export function SimGame({ d }: { d: Detail }) {
  const [sim, setSim] = useState<Sim | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("random");
  const [draw, setDraw] = useState(randomDraw);
  const [loading, setLoading] = useState(false);
  useEffect(() => { setSim(null); setMode("random"); setDraw(randomDraw()); }, [d.gid]);
  useEffect(() => {
    let alive = true;
    setError(null);
    setLoading(true);
    api.sim(d.gid, mode, draw).then((x) => { if (alive) { setSim(x); setLoading(false); } }).catch((e) => { if (alive) { setError(String(e)); setLoading(false); } });
    return () => { alive = false; };
  }, [d.gid, mode, draw]);

  if (error) return <Callout tone="amber">Could not load the simulation ({error}).</Callout>;
  if (!sim) return <div className="text-muted">Simulating 10,000 games…</div>;
  if (!sim.ok) return <Callout tone="blue">{sim.reason}</Callout>;
  const r = sim.ranges!;
  const tgt = sim.replay!.targets;
  const fin = sim.replay!.final;
  const maxPts = Math.max(r.home.high, r.away.high) + 3;
  const noLine = (sim.source?.margin ?? "").includes("no betting line");
  const g = sim.game;
  const winner = fin[d.home] >= fin[d.away] ? d.home : d.away;
  const upsetNote = g ? `${g.underdog} wins ${pct(g.p_underdog)} of the ${r.sims.toLocaleString()} simulated games` : "";
  const title = mode === "typical" ? "Typical game, play by play" : mode === "upset" ? "Upset game, play by play" : "Simulated game, play by play";
  const note = mode === "typical"
    ? `The middle result of ${r.sims.toLocaleString()} simulated games (${d.away} ${tgt[d.away]}, ${d.home} ${tgt[d.home]}${fin[d.away] !== tgt[d.away] || fin[d.home] !== tgt[d.home] ? `, rounded to ${fin[d.away]}-${fin[d.home]} so touchdowns and field goals add up` : ""}). ${upsetNote}. A real game rarely lands exactly here, which is why a random game is what opens first.`
    : mode === "upset"
      ? `A random one of the simulated games that ${g?.underdog} wins (${upsetNote.replace(/^.* wins /, "")}). Scores are rounded to touchdowns and field goals.`
      : `One of the ${r.sims.toLocaleString()} simulated games, picked at random (number ${draw}). ${upsetNote}. Press "Another game" for a different one.`;

  return (
    <div className="space-y-6">
      <Section title="Game conditions">
        <Conditions sim={sim} d={d} />
      </Section>

      <Section title={title} note={`${note} ${sim.receiving?.model === "sampled" ? "Every pass is drawn at random: a target for one of the players available, then a catch or not, then the yards. Some games come out lumpy and some spread out, the way real ones do. Rushing follows each player's number below, moving with the score." : "Player totals follow each player's number below, moving up or down with the score."} The individual plays are made up to connect those numbers.`}>
        <div className="flex flex-wrap items-center gap-2">
          <Segmented<string> label="Which simulated game" options={Object.keys(MODE_OF)} value={MODE_LABEL[mode]} onChange={(l) => { setMode(MODE_OF[l]); setDraw(randomDraw()); }} />
          <button className="min-h-[44px] rounded-lg border border-line px-4 text-base text-white hover:bg-line disabled:opacity-40" disabled={mode === "typical" || loading}
            onClick={() => setDraw(randomDraw())}>Another game</button>
          <span className="text-sm text-muted" aria-live="polite">{loading ? "Simulating…" : `${MODE_LABEL[mode]}: ${winner} wins ${fin[winner]} to ${fin[winner === d.home ? d.away : d.home]}`}</span>
        </div>
        {d.completed && <Callout tone="blue">This game is over. Actual final: {d.away} {d.away_score}, {d.home} {d.home_score}.</Callout>}
        {noLine && <Callout tone="amber">No betting line exists for this game yet, so the expected score comes from each team's points scored and allowed this season. It will switch to the market line once one is posted.</Callout>}
        {!sim.has_players && <Callout tone="blue">No player data is available for this game, so the replay uses generic player names.</Callout>}
        <Replay key={`${d.gid}-${mode}-${draw}`} sim={sim} d={d} />
      </Section>

      <Section title="Snap-by-snap simulation, 10,000 games" note="A second simulator that plays every game one snap at a time from each team's real 2026 tendencies and the active players, with the loud-stadium and rest effects, the running-back scenario and the leans. It does not use the betting line.">
        <SnapSimBody gid={d.gid} />
      </Section>

      <Section title="Injuries in this simulation">
        <Injuries sim={sim} />
      </Section>

      <Section title="Score ranges" note={`8 in 10 of the ${r.sims.toLocaleString()} simulated games land inside each range. Spread from ${sim.source?.margin}; total from ${sim.source?.total}.`}>
        <div className="grid grid-cols-1 gap-0.5 md:grid-cols-3">
          <Range title={`${d.away_name} points`} b={r.away} lo={0} hi={maxPts} color={d.away_color} />
          <Range title={`${d.home_name} points`} b={r.home} lo={0} hi={maxPts} color={d.home_color} />
          <Range title="Total points" b={r.total} lo={Math.max(0, r.total.low - 10)} hi={r.total.high + 10} color="#8b9097" />
        </div>
      </Section>

      <Section title="Our own drive simulation, with no betting line" note="Shown for comparison.">
        <OwnView sim={sim} d={d} />
      </Section>

      {(sim.players ?? []).length > 0 && (
        <Section title="Player projections" note={`Middle number, with the range 8 in 10 games land in where there are enough games to measure it. ${fpdsNote(sim)}`}>
          <Spotlight sim={sim} d={d} />
        </Section>
      )}

      {(sim.allowed?.teams ?? []).length > 0 && (
        <Section title="What each defense gives up" note="How the opposing defense moves each position's numbers in the player projections and the replay.">
          <AllowedCard sim={sim} />
        </Section>
      )}

      {(sim.defense ?? []).length > 0 && (
        <Section title="Defenses in this matchup">
          <Defense sim={sim} d={d} />
        </Section>
      )}
    </div>
  );
}
