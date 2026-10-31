import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Band, Detail, PropRow, Sim, SimPlay } from "../types";
import { num } from "../lib";
import { Callout, Card } from "./ui/primitives";

const SPEEDS = [1, 2, 4];
const MS_PER_PLAY = 1500;
const BANNER: Record<string, string> = { TD: "Touchdown", FG: "Field goal", INT: "Interception", FUMBLE: "Fumble", PUNT: "Punt", DOWNS: "Turnover on downs" };

// ------------------------------------------------------------------ running box score
interface Line { att: number; comp: number; yds: number; td: number; int: number; sacks: number }
interface Box { qb: Line; rush: Map<string, [number, number, number]>; rec: Map<string, [number, number, number]> }

function boxScore(plays: SimPlay[], upto: number, teams: string[]): Record<string, Box> {
  const out: Record<string, Box> = {};
  for (const t of teams) out[t] = { qb: { att: 0, comp: 0, yds: 0, td: 0, int: 0, sacks: 0 }, rush: new Map(), rec: new Map() };
  for (const p of plays.slice(0, upto + 1)) {
    const b = out[p.team];
    const td = p.event === "TD" ? 1 : 0;
    const add = (m: Map<string, [number, number, number]>, k: string, y: number) => {
      const v = m.get(k) ?? [0, 0, 0];
      m.set(k, [v[0] + 1, v[1] + y, v[2] + td]);
    };
    if (p.kind === "pass") { b.qb.att++; b.qb.comp++; b.qb.yds += p.yards; b.qb.td += td; add(b.rec, p.player!, p.yards); }
    else if (p.kind === "incomplete") { b.qb.att++; if (p.event === "INT") b.qb.int++; }
    else if (p.kind === "sack") b.qb.sacks++;
    else if (p.kind === "rush") add(b.rush, p.player!, p.yards);
  }
  return out;
}

const leaders = (m: Map<string, [number, number, number]>, n: number) => [...m.entries()].sort((a, b) => b[1][1] - a[1][1]).slice(0, n);
const short = (name: string) => name.replace(/^another [A-Z]+ /, "Other ");

function TeamBox({ team, color, qb, box }: { team: string; color: string; qb: string; box: Box }) {
  const q = box.qb;
  return (
    <div className="space-y-3 text-sm">
      <div className="flex items-center gap-2 border-b border-line pb-1 font-bold text-white">
        <span className="inline-block h-3 w-3 rounded-sm" style={{ background: color }} />{team}
      </div>
      <div>
        <div className="text-xs text-muted">Passing</div>
        <div className="flex justify-between"><span className="text-slate-300">{qb}</span><span className="font-medium text-white">{q.comp}/{q.att}, {q.yds} yds</span></div>
        <div className="text-xs text-muted">{q.td} TD · {q.int} INT · {q.sacks} sacked</div>
      </div>
      <Leaders title="Rushing" unit="car" rows={leaders(box.rush, 3)} empty="No carries yet" />
      <Leaders title="Receiving" unit="rec" rows={leaders(box.rec, 4)} empty="No catches yet" />
    </div>
  );
}

function Leaders({ title, unit, rows, empty }: { title: string; unit: string; rows: [string, [number, number, number]][]; empty: string }) {
  return (
    <div>
      <div className="flex justify-between text-xs text-muted"><span>{title}</span><span>{unit} / yds / TD</span></div>
      {rows.length === 0 && <div className="text-muted">{empty}</div>}
      {rows.map(([name, v]) => (
        <div key={name} className="flex justify-between"><span className="truncate pr-2 text-slate-300">{short(name)}</span><span className="whitespace-nowrap text-white">{v[0]} / {v[1]} / {v[2]}</span></div>
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
    <svg viewBox="0 0 120 54" className="w-full rounded-lg" role="img" aria-label={p.text}>
      <rect x="0" y="0" width="120" height="54" fill="#14532d" />
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
          <rect x="35" y="19" width="50" height="16" rx="2" fill={p.event === "TD" || p.event === "FG" ? (p.team === d.home ? d.home_color : d.away_color) : "#0f1a2e"} stroke="white" strokeWidth="0.3" />
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
      <div className="mb-3 grid grid-cols-[1fr_auto_1fr] items-center gap-2 rounded-lg border border-line bg-[#0b1220] px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="h-8 w-1.5 rounded" style={{ background: d.away_color }} />
          <span className="font-bold text-white">{d.away}</span>
          <span className="ml-auto text-3xl font-extrabold tabular-nums text-white">{score[d.away]}</span>
        </div>
        <div className="px-3 text-center">
          <div className="font-semibold tabular-nums text-white">{last && moved ? "Final" : `Q${p.qtr} ${p.clock}`}</div>
          <div className="text-xs text-muted">{last && moved ? "simulated" : `${p.team} ball`}</div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-3xl font-extrabold tabular-nums text-white">{score[d.home]}</span>
          <span className="ml-auto font-bold text-white">{d.home}</span>
          <span className="h-8 w-1.5 rounded" style={{ background: d.home_color }} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[200px_1fr_200px]">
        <div className="order-2 lg:order-1"><TeamBox team={d.away} color={d.away_color} qb={sim.replay!.qbs[d.away]} box={box[d.away]} /></div>
        <div className="order-1 lg:order-2">
          <Field p={p} d={d} moved={moved} />
          <div className="mt-1 flex justify-between text-xs text-muted"><span>Play {i + 1} of {plays.length}</span><span>{situation}</span></div>
          <div className="mt-2 min-h-[3rem] rounded-lg border border-line px-3 py-2 text-center text-sm font-medium text-white">{p.text}</div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-[#0b1220]" onClick={() => { if (last) setI(0); setPlaying(!playing || last); }}>
              {playing ? "Pause" : last ? "Watch again" : i === 0 ? "Start replay" : "Resume"}
            </button>
            <div className="flex overflow-hidden rounded-lg border border-line" role="group" aria-label="Replay speed">
              {SPEEDS.map((s) => (
                <button key={s} className={`px-3 py-2 text-sm ${s === speed ? "bg-line text-white" : "text-muted"}`} onClick={() => setSpeed(s)}>{s}x</button>
              ))}
            </div>
            <button className="rounded-lg border border-line px-3 py-2 text-sm text-muted hover:text-white" onClick={() => { setPlaying(false); setI(plays.length - 1); }}>Skip to final</button>
          </div>
          <input type="range" min={0} max={plays.length - 1} value={i} onChange={(e) => { setPlaying(false); setI(Number(e.target.value)); }}
            className="mt-3 w-full accent-[#60a5fa]" aria-label="Replay position" />
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
      <div className="text-sm text-muted">{title}</div>
      <div className="mt-1 text-3xl font-bold text-white">{b.low} to {b.high}</div>
      <div className="relative my-3 h-2 rounded-full bg-line">
        <div className="absolute h-2 rounded-full" style={{ left: at(b.low), width: `calc(${at(b.high)} - ${at(b.low)})`, background: color }} />
        <div className="absolute -top-1 h-4 w-1 rounded bg-white" style={{ left: at(b.median) }} />
      </div>
      <div className="text-sm text-slate-300">Middle result: <b className="text-white">{b.median}</b></div>
    </Card>
  );
}

function Spotlight({ d, out }: { d: Detail; out: string[] }) {
  const props = (d.props ?? []).filter((r) => !out.includes(r.player));
  const pick = (team: string) => {
    const mine = props.filter((r) => r.team === team);
    const best = (stat: string, n: number) => mine.filter((r) => r.stat === stat).sort((a, b) => b.typical - a.typical).slice(0, n);
    return [...best("Passing yards", 1), ...best("Rushing yards", 1), ...best("Receiving yards", 2)];
  };
  const row = (r: PropRow) => (
    <div key={r.player + r.stat} className="flex items-center justify-between border-b border-line py-2 last:border-0">
      <div><div className="text-sm font-medium text-white">{r.player}</div><div className="text-xs text-muted">{r.stat.toLowerCase()}</div></div>
      <div className="text-right"><div className="text-xl font-bold text-white">{num(r.typical, 0)}</div>
        {r.range_low !== null && <div className="text-xs text-muted">8 in 10: {num(r.range_low, 0)} to {num(r.range_high, 0)}</div>}</div>
    </div>
  );
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {[{ t: d.away, n: d.away_name, c: d.away_color }, { t: d.home, n: d.home_name, c: d.home_color }].map(({ t, n, c }) => (
        <Card key={t}>
          <div className="mb-1 flex items-center gap-2 font-bold text-white"><span className="inline-block h-3 w-3 rounded-sm" style={{ background: c }} />{n}</div>
          {pick(t).map(row)}
        </Card>
      ))}
    </div>
  );
}

function Defense({ sim, d }: { sim: Sim; d: Detail }) {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {sim.defense!.map((c) => (
        <Card key={c.team}>
          <div className="font-bold text-white">{c.team === d.away ? d.away_name : d.home_name} defense</div>
          <div className="mb-2 text-xs text-muted">This season, {c.games} games. Rank 1 allows the most.</div>
          {c.rows.map((r) => (
            <div key={r.label} className="flex justify-between border-b border-line py-1.5 text-sm last:border-0">
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
  <section className="space-y-2">
    <div><h2 className="text-lg font-bold text-white">{title}</h2>{note && <p className="text-sm text-muted">{note}</p>}</div>
    {children}
  </section>
);

export function SimGame({ d }: { d: Detail }) {
  const [sim, setSim] = useState<Sim | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setSim(null);
    setError(null);
    api.sim(d.gid).then(setSim).catch((e) => setError(String(e)));
  }, [d.gid]);

  if (error) return <Callout tone="amber">Could not load the simulation ({error}).</Callout>;
  if (!sim) return <div className="text-muted">Simulating 10,000 games…</div>;
  if (!sim.ok) return <Callout tone="blue">{sim.reason}</Callout>;
  const r = sim.ranges!;
  const tgt = sim.replay!.targets;
  const fin = sim.replay!.final;
  const maxPts = Math.max(r.home.high, r.away.high) + 3;
  const out = sim.left_out ?? [];
  const unsure = Object.values(d.injuries?.teams ?? {}).flat().filter((x) => !out.includes(x.player) && (d.props ?? []).some((p) => p.player === x.player)).map((x) => `${x.player} (${x.status.toLowerCase()})`);

  return (
    <div className="space-y-6">
      <Section title="Typical game, play by play"
        note={`One game built to end on the middle result of ${r.sims.toLocaleString()} simulations (${d.away} ${tgt[d.away]}, ${d.home} ${tgt[d.home]}${fin[d.away] !== tgt[d.away] || fin[d.home] !== tgt[d.home] ? `, rounded to ${fin[d.away]}-${fin[d.home]} so touchdowns and field goals add up` : ""}) with player totals close to each player's middle projection. The individual plays are made up to connect those numbers.`}>
        {d.completed && <Callout tone="blue">This game is over. Actual final: {d.away} {d.away_score}, {d.home} {d.home_score}.</Callout>}
        {(out.length > 0 || unsure.length > 0) && (
          <Callout tone="amber">
            {out.length > 0 && <>Ruled out, so left out of the replay: {out.join(", ")}. Their usual catches and carries go to teammates. </>}
            {unsure.length > 0 && <>Not yet ruled out, so the replay assumes they play: {unsure.join(", ")}.</>}
          </Callout>
        )}
        {!sim.has_players && <Callout tone="blue">No player projections are saved for this game, so the replay uses generic player names.</Callout>}
        <Replay sim={sim} d={d} />
      </Section>

      <Section title="Score ranges" note={`8 in 10 of the ${r.sims.toLocaleString()} simulated games land inside each range. Spread from ${sim.source?.margin}; total from ${sim.source?.total}.`}>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Range title={`${d.away_name} points`} b={r.away} lo={0} hi={maxPts} color={d.away_color} />
          <Range title={`${d.home_name} points`} b={r.home} lo={0} hi={maxPts} color={d.home_color} />
          <Range title="Total points" b={r.total} lo={Math.max(0, r.total.low - 10)} hi={r.total.high + 10} color="#60a5fa" />
        </div>
      </Section>

      {(d.props ?? []).length > 0 && (
        <Section title="Player projections" note="Middle projection, with the range 8 in 10 games land in.">
          <Spotlight d={d} out={sim.left_out ?? []} />
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
