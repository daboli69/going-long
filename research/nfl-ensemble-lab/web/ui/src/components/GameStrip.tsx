import type { GameRow } from "../types";
import { cn, etTime, pct } from "../lib";

// One scorebug cell per game: the two teams stacked with their colours on the left edge, kickoff or final on the right.
export function GameStrip({ games, selected, onSelect }: { games: GameRow[]; selected: string | null; onSelect: (gid: string) => void }) {
  return (
    <nav aria-label="Games this week" className="-mx-4 overflow-x-auto px-4 pb-2 sm:mx-0 sm:px-0">
      <ul className="flex gap-0.5">
        {games.map((g) => {
          const active = g.gid === selected;
          const homeP = g.p_home;
          const fav = homeP === null ? null : homeP >= 0.5 ? { team: g.home, p: homeP } : { team: g.away, p: 1 - homeP };
          const when = g.completed ? "Final" : etTime(g.kickoff_utc).replace(":00 ", " ");
          return (
            <li key={g.gid} className="shrink-0">
              <button
                aria-current={active ? "true" : undefined}
                onClick={() => onSelect(g.gid)}
                className={cn("grid w-[164px] grid-cols-[5px_1fr_auto] gap-x-2.5 px-3 py-2.5 text-left transition-colors", active ? "bg-white text-bg" : "bg-panel text-white hover:bg-line")}
              >
                <span className="row-span-2 flex flex-col" aria-hidden>
                  <span className="flex-1" style={{ background: g.away_color }} />
                  <span className="flex-1" style={{ background: g.home_color }} />
                </span>
                <span className="text-base font-semibold">{g.away}{g.completed ? ` ${g.away_score}` : ""}</span>
                <span className={cn("text-sm", active ? "text-[#4a4d52]" : "text-muted")}>{when}</span>
                <span className="text-base font-semibold">{g.home}{g.completed ? ` ${g.home_score}` : ""}</span>
                <span className={cn("text-sm", active ? "text-[#4a4d52]" : "text-muted")}>{fav ? `${fav.team} ${pct(fav.p)}` : ""}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
