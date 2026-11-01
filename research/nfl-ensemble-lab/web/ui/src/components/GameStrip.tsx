import type { CSSProperties } from "react";
import type { GameRow } from "../types";
import { cn, etTime } from "../lib";

const away = (g: GameRow) => (g.p_home === null ? null : 100 - Math.round(g.p_home * 100));
const home = (g: GameRow) => (g.p_home === null ? null : Math.round(g.p_home * 100));
const slotName = (s: GameRow[]) => (s[0].completed ? `${s[0].kickoff_label.split(" ")[0]}, final` : s[0].kickoff_label);

function Tile({ g, active, onSelect }: { g: GameRow; active: boolean; onSelect: (gid: string) => void }) {
  const a = away(g), h = home(g);
  const label = g.completed ? `${g.away} at ${g.home}, final, ${g.away} ${g.away_score}, ${g.home} ${g.home_score}` : `${g.away} at ${g.home}${h === null ? "" : `, ${g.home} ${h}% to win`}`;
  return (
    <button
      type="button"
      aria-current={active ? "true" : undefined}
      aria-label={label}
      onClick={() => onSelect(g.gid)}
      className={cn("flex min-h-[64px] flex-col px-2 pt-2 text-left transition-colors", active ? "bg-white text-bg" : "bg-panel text-white hover:bg-raised active:bg-[#33383e]")}
    >
      {([[g.away, g.completed ? g.away_score : a === null ? null : `${a}%`], [g.home, g.completed ? g.home_score : h === null ? null : `${h}%`]] as const).map(([t, v]) => (
        <span key={t} className="flex justify-between gap-1 text-[15px] leading-[1.3]"><b>{t}</b><span className={active ? "text-[#3a3d42]" : "text-muted"}>{v ?? ""}</span></span>
      ))}
      <span className={cn("hidden text-xs sm:max-xl:block", active ? "text-[#3a3d42]" : "text-muted")}>{g.completed ? "Final" : g.kickoff_label}</span>
      <span className="-mx-2 mt-1.5 flex h-1" aria-hidden>
        {a !== null && h !== null && !g.completed ? (<><i style={{ flex: a, background: g.away_color }} /><i style={{ flex: h, background: g.home_color }} /></>) : (<><i className="flex-1" style={{ background: g.away_color }} /><i className="flex-1" style={{ background: g.home_color }} /></>)}
      </span>
    </button>
  );
}

// The whole week on one board, grouped by kickoff slot: 7 across on a tablet, a picker on a phone.
export function GameStrip({ games, selected, onSelect, week }: { games: GameRow[]; selected: string | null; onSelect: (gid: string) => void; week: number }) {
  const slots: GameRow[][] = [];
  games.forEach((g) => {
    const s = slots.find((x) => x[0].kickoff_label === g.kickoff_label);
    if (s) s.push(g); else slots.push([g]);
  });
  const cur = games.find((g) => g.gid === selected) ?? games[0];
  return (
    <nav aria-label={`Games in week ${week}`}>
      <div className="hidden grid-cols-7 gap-0.5 sm:grid xl:[grid-template-columns:repeat(var(--n),minmax(0,1fr))]" style={{ "--n": games.length } as CSSProperties}>
        {slots.map((s) => <div key={s[0].gid} aria-hidden className="hidden truncate pb-1 text-[13px] text-muted xl:block" style={{ gridColumn: `span ${s.length}` }}>{slotName(s)}</div>)}
        {slots.flat().map((g) => <Tile key={g.gid} g={g} active={g.gid === selected} onSelect={onSelect} />)}
      </div>
      <details className="group sm:hidden">
        <summary className="flex min-h-[56px] cursor-pointer list-none items-center gap-4 bg-panel px-4 py-2 [&::-webkit-details-marker]:hidden">
          <span><b>{cur.away} at {cur.home}</b><br /><span className="text-sm text-muted">{cur.completed ? "Final" : etTime(cur.kickoff_utc).replace(":00 ", " ") + " ET"}, {games.length} games this week</span></span>
          <span className="ml-auto text-[15px] text-accent group-open:hidden">Show all games</span>
          <span className="ml-auto hidden text-[15px] text-accent group-open:inline">Hide</span>
        </summary>
        <div className="mt-0.5 grid grid-cols-2 gap-0.5">
          {slots.map((s) => (
            <div key={s[0].gid} className="contents">
              <h2 className="col-span-full pt-2 text-[13px] font-normal text-muted">{slotName(s)}</h2>
              {s.map((g) => <Tile key={g.gid} g={g} active={g.gid === selected} onSelect={onSelect} />)}
            </div>
          ))}
        </div>
      </details>
    </nav>
  );
}
