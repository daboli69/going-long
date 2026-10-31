import type { GameRow } from "../types";
import { cn, etTime, pairColors, pct } from "../lib";

export function GameStrip({ games, selected, onSelect }: { games: GameRow[]; selected: string | null; onSelect: (gid: string) => void }) {
  return (
    <nav aria-label="Pick a game">
      <ul className="strip -mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:-mx-6 sm:px-6 md:mx-0 md:px-0">
        {games.map((g) => {
          const active = g.gid === selected;
          const homeP = g.p_home;
          const fav = homeP === null ? null : homeP >= 0.5 ? { team: g.home, p: homeP } : { team: g.away, p: 1 - homeP };
          const c = pairColors(g.away_color, g.home_color);
          return (
            <li key={g.gid} className="min-w-[74%] shrink-0 sm:min-w-[210px] sm:flex-1 md:max-w-[280px]">
              <button
                onClick={() => onSelect(g.gid)}
                aria-current={active ? "true" : undefined}
                className={cn("flex min-h-[5.25rem] w-full flex-col justify-between rounded-md p-3 text-left transition-colors", active ? "bg-ink text-bg" : "bg-surface text-ink hover:bg-surface2")}
              >
                <span className="block">
                  <span className="block font-display text-lg font-bold leading-tight">{g.away} at {g.home}</span>
                  <span className={cn("block text-sm", active ? "text-bg" : "text-muted")}>{g.completed ? `Final ${g.away_score}-${g.home_score}` : etTime(g.tipoff_utc)}</span>
                </span>
                {homeP !== null && (
                  <span className="mt-2 block">
                    <span className="flex h-1.5 gap-px overflow-hidden rounded-sm" aria-hidden>
                      <span style={{ width: `${(1 - homeP) * 100}%`, background: c.away }} />
                      <span style={{ width: `${homeP * 100}%`, background: c.home }} />
                    </span>
                    {fav && <span className="mt-1 block text-sm font-semibold">{fav.team} {pct(fav.p)}</span>}
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
