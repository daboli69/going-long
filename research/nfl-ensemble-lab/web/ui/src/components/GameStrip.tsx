import type { GameRow } from "../types";
import { cn, etTime, pct } from "../lib";

export function GameStrip({ games, selected, onSelect }: { games: GameRow[]; selected: string | null; onSelect: (gid: string) => void }) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-2" role="listbox" aria-label="Pick a game">
      {games.map((g) => {
        const active = g.gid === selected;
        const homeP = g.p_home;
        const fav = homeP === null ? null : homeP >= 0.5 ? { team: g.home, p: homeP } : { team: g.away, p: 1 - homeP };
        return (
          <button
            key={g.gid}
            role="option"
            aria-selected={active}
            onClick={() => onSelect(g.gid)}
            className={cn("min-w-[150px] shrink-0 rounded-lg border bg-panel px-3 py-2.5 text-left transition hover:border-accent", active ? "border-accent" : "border-line")}
          >
            <div className="text-sm font-semibold text-white">{g.away} at {g.home}</div>
            <div className="text-xs text-muted">{g.completed ? `Final ${g.away_score}-${g.home_score}` : etTime(g.kickoff_utc)}</div>
            {homeP !== null && (
              <>
                <div className="mt-2 flex h-1 overflow-hidden rounded-full bg-line" aria-hidden>
                  <div style={{ width: `${(1 - homeP) * 100}%`, background: g.away_color }} />
                  <div style={{ width: `${homeP * 100}%`, background: g.home_color }} />
                </div>
                {fav && <div className="mt-1 text-xs text-slate-300">{fav.team} {pct(fav.p)}</div>}
              </>
            )}
          </button>
        );
      })}
    </div>
  );
}
