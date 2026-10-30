import type { GameRow } from "../types";
import { cn, etTime, pct } from "../lib";
import { TeamChip } from "./TeamChip";

export function GameStrip({ games, selected, onSelect }: { games: GameRow[]; selected: string | null; onSelect: (gid: string) => void }) {
  return (
    <div className="flex gap-3 overflow-x-auto pb-2" role="listbox" aria-label="Pick a game">
      {games.map((g) => {
        const active = g.gid === selected;
        const homeP = g.p_home;
        return (
          <button
            key={g.gid}
            role="option"
            aria-selected={active}
            onClick={() => onSelect(g.gid)}
            className={cn("min-w-[190px] shrink-0 rounded-xl border bg-panel p-3 text-left transition hover:border-accent", active ? "border-accent ring-1 ring-accent" : "border-line")}
          >
            <div className="flex items-center justify-between gap-2">
              <TeamChip abbr={g.away} color={g.away_color} size="sm" />
              <span className="text-xs text-muted">@</span>
              <TeamChip abbr={g.home} color={g.home_color} size="sm" />
            </div>
            <div className="mt-2 text-sm font-semibold text-white">
              {g.away} @ {g.home}
            </div>
            <div className="text-xs text-muted">{g.completed ? `Final ${g.away_score} - ${g.home_score}` : etTime(g.kickoff_utc)}</div>
            {homeP !== null && (
              <div className="mt-2">
                <div className="flex h-1.5 overflow-hidden rounded-full bg-line">
                  <div style={{ width: `${(1 - homeP) * 100}%`, background: g.away_color }} />
                  <div style={{ width: `${homeP * 100}%`, background: g.home_color }} />
                </div>
                <div className="mt-1 flex justify-between text-[11px] text-muted">
                  <span>{pct(1 - homeP)}</span>
                  <span>{pct(homeP)}</span>
                </div>
              </div>
            )}
          </button>
        );
      })}
    </div>
  );
}
