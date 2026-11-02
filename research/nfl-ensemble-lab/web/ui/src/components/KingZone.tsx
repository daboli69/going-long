import { useEffect, useState } from "react";
import { api } from "../api";
import type { KingBoard, KingRow, KingWeek } from "../types";
import { etStamp, pct } from "../lib";
import { Callout } from "./ui/primitives";
import { Num } from "./motion";

function Row({ r, top }: { r: KingRow; top: number }) {
  return (
    <details className="group border-t border-bg">
      <summary className="grid min-h-[56px] cursor-pointer list-none grid-cols-[2em_minmax(0,1fr)_4.5em] items-center gap-x-3 py-2 sm:grid-cols-[2.5em_minmax(0,1.2fr)_minmax(0,1fr)_5em_5em_5em]">
        <span className="text-[15px] text-muted">{r.rank}</span>
        <span className="min-w-0 text-[15px]">{r.player} <span className="text-[13px] text-muted">{r.pos}, {r.team} vs {r.opp}</span>
          <span className="block text-[13px] text-muted group-open:hidden">{r.why[0] ?? ""}</span></span>
        <span className="hidden sm:block" aria-hidden="true"><span className="block h-2 bg-bg"><span className="block h-2 bg-yellow-400" style={{ width: `${Math.max(2, (r.chance / top) * 100)}%` }} /></span></span>
        <span className="text-right text-xl font-bold"><Num value={r.chance} pct /></span>
        <span className="hidden text-right text-[15px] text-muted sm:block">{pct(r.p_40)}</span>
        <span className="hidden text-right text-[15px] text-muted sm:block">{pct(r.p_60)}</span>
      </summary>
      <ul className="mb-3 ml-[2.75em] list-disc space-y-1 pl-4 text-[15px] text-slate-300">
        {r.why.map((w) => <li key={w}>{w}</li>)}
      </ul>
    </details>
  );
}

// Who is most likely to score the longest touchdown of a game, for the Monday-night "King of the End Zone" promotion.
export function KingZoneView({ week }: { week: number }) {
  const [wk, setWk] = useState<KingWeek | null>(null);
  const [gid, setGid] = useState<string | null>(null);
  const [board, setBoard] = useState<KingBoard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setWk(null); setBoard(null); setError(null);
    api.kingWeek(week).then((w) => { if (live) { setWk(w); setGid(w.default_gid); } }).catch((e) => live && setError(String(e)));
    return () => { live = false; };
  }, [week]);

  useEffect(() => {
    if (!gid) return;
    let live = true;
    setBoard(null); setError(null);
    api.kingGame(gid).then((b) => live && setBoard(b)).catch((e) => live && setError(String(e)));
    return () => { live = false; };
  }, [gid]);

  const picker = (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <h1 className="text-[22px] font-bold leading-tight text-white sm:text-2xl">King of the End Zone</h1>
      <label className="sr-only" htmlFor="king-game">Game</label>
      <select id="king-game" className="min-h-[44px] bg-panel px-4 text-base text-white hover:bg-raised" value={gid ?? ""} onChange={(e) => setGid(e.target.value)}>
        {wk?.games.map((g) => <option key={g.gid} value={g.gid}>{g.away} at {g.home}{g.monday ? " (Monday)" : ""}{g.completed ? " (final)" : ""}</option>)}
      </select>
    </div>
  );
  if (error) return <div className="space-y-4">{picker}<Callout tone="amber">The board could not be built ({error}).</Callout></div>;
  if (!board) return <div className="space-y-4">{picker}<Callout tone="blue">Building the board. This takes a few seconds the first time.</Callout></div>;

  const top = board.rows[0]?.chance ?? 1;
  const dstTotal = Object.values(board.field.defense_special_teams).reduce((a, v) => a + v, 0);
  return (
    <div className="space-y-6">
      {picker}
      <p className="max-w-[75ch] text-[15px] text-muted">
        The promotion pays the player who scores the longest touchdown of the game. A passing touchdown counts for the receiver, and a return or defensive touchdown can win it. The chance below is the model's estimate that the player's touchdown is the longest. It is not a price or a bet recommendation.
      </p>
      <section aria-label="Top pick" className="grid grid-cols-1 gap-x-10 gap-y-4 bg-panel p-4 sm:grid-cols-[auto_1fr] sm:p-6">
        <div>
          <div className="text-[13px] text-muted">{board.away} at {board.home}, {etStamp(board.kickoff_utc)}</div>
          <div className="fig text-[64px] sm:text-[88px]"><Num value={top} pct /></div>
          <div className="text-[15px] text-slate-300">{board.rows[0]?.player}, the likeliest owner of the longest touchdown</div>
        </div>
        <dl className="grid content-end divide-y divide-line self-end text-[15px]">
          <div className="flex items-baseline justify-between gap-4 py-2"><dt className="text-muted">Typical length of the longest touchdown</dt><dd className="whitespace-nowrap text-xl font-bold">{board.expected_longest.toFixed(0)} yards</dd></div>
          <div className="flex items-baseline justify-between gap-4 py-2"><dt className="text-muted">Longest is a defense or special-teams touchdown</dt><dd className="whitespace-nowrap text-xl font-bold">{pct(dstTotal)}</dd></div>
          <div className="flex items-baseline justify-between gap-4 py-2"><dt className="text-muted">Expected offensive touchdowns</dt><dd className="text-xl font-bold">{Object.entries(board.expected_td).map(([t, v]) => `${t} ${v.toFixed(1)}`).join(", ")}</dd></div>
        </dl>
      </section>
      {board.completed && <Callout tone="blue">This game is final. The board shows the forecast made before kickoff.</Callout>}

      <section aria-label="Ranking" className="bg-panel p-4 sm:p-6">
        <h2 className="text-xl leading-tight text-white">Who is likeliest</h2>
        <div role="table" aria-label="Longest touchdown chances" className="mt-3">
          <div role="row" className="hidden grid-cols-[2.5em_minmax(0,1.2fr)_minmax(0,1fr)_5em_5em_5em] gap-x-3 pb-2 text-[13px] text-muted sm:grid">
            <span>#</span><span>Player</span><span /><span className="text-right">Longest</span><span className="text-right">40+ yd TD</span><span className="text-right">60+ yd TD</span>
          </div>
          {board.rows.map((r) => <Row key={r.player + r.team} r={r} top={top} />)}
        </div>
        <p className="mt-3 text-[13px] text-muted">
          Players listed hold {pct(board.listed_total)} of the total. The rest goes to defense and special teams ({pct(dstTotal)}), touchdowns by players not listed, and a game with no touchdown ({pct(board.no_touchdown, 1)}). Open a row for the reasons behind it.
        </p>
      </section>

      <section aria-label="How it works" className="bg-panel p-4 sm:p-6">
        <h2 className="text-xl leading-tight text-white">How the chance is built</h2>
        <ul className="mt-3 max-w-[80ch] list-disc space-y-2 pl-5 text-[15px] text-slate-300">
          <li>A league record of how long touchdowns are per carry and per target, by position, since 2022. A touchdown's length is the yard line it started from.</li>
          <li>The player's own rate of 20+ and 40+ yard gains per touch, pulled toward his position's rate so a few plays do not decide it. Receivers add how deep their targets go, yards after the catch and yards per route run. Runners add broken tackles per carry.</li>
          <li>The opposing defense's rate of 20+ and 40+ yard gains allowed per carry and per target over its last seven games.</li>
          <li>Expected carries and targets from the simulated game, and each team's expected touchdowns, so a high-scoring game has more chances.</li>
          <li>Every other source of a long touchdown competes: unlisted players, defense and special teams. The longest wins; ties split.</li>
        </ul>
        <p className="mt-3 max-w-[80ch] text-[13px] text-muted">
          Not used because the free data does not have it: player top speed and acceleration, offensive-line and pressure measures, and route or coverage alignment. The weights in the blend are judgment, not fitted. A check on this season's finished games is in docs/KINGZONE.md.
        </p>
      </section>
    </div>
  );
}
