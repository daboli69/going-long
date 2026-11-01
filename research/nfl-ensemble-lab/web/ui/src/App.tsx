import { useEffect, useState } from "react";
import { api } from "./api";
import type { Detail, GameRow, Meta } from "./types";
import { etStamp, etTime } from "./lib";
import { GameStrip } from "./components/GameStrip";
import { Overview, Scorebug } from "./components/Overview";
import { About, Matchup, Props } from "./components/Others";
import { SimGame } from "./components/SimGame";
import { RankingsView } from "./components/Rankings";
import { Callout, Segmented, Tabs, TabsContent, TabsList, TabsTrigger } from "./components/ui/primitives";

export default function App() {
  const [view, setView] = useState<"Games" | "Player rankings">("Games");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [week, setWeek] = useState<number | null>(null);
  const [games, setGames] = useState<GameRow[] | null>(null);
  const [gid, setGid] = useState<string | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.meta().then((m) => { setMeta(m); if (m.ok) setWeek(m.default_week); }).catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (week === null) return;
    setGames(null);
    api.week(week).then((rows) => {
      setGames(rows);
      const now = Date.now();
      const next = rows.find((r) => new Date(r.kickoff_utc).getTime() > now) ?? rows[0];
      setGid(next ? next.gid : null);
    }).catch((e) => setError(String(e)));
  }, [week]);

  useEffect(() => {
    if (!gid) { setDetail(null); return; }
    api.game(gid).then(setDetail).catch((e) => setError(String(e)));
  }, [gid]);

  if (error) return <div className="p-6"><Callout tone="amber">Can't reach the local server ({error}). Is <code>launch_game_center.bat</code> still running?</Callout></div>;
  if (!meta) return <div className="p-8 text-muted">Loading…</div>;
  if (!meta.ok) return <div className="p-8"><Callout tone="amber">{meta.reason}</Callout></div>;

  const upcoming = (games ?? []).filter((g) => new Date(g.kickoff_utc).getTime() > Date.now());
  const saved = week !== null ? meta.forecast_saved_at[String(week)] : undefined;
  const summary = games === null ? "Loading games…"
    : games.length === 0 ? "No games found for this week."
    : [`${games.length} games`, upcoming.length ? `next kickoff ${etTime(upcoming[0].kickoff_utc)} ET` : "all games played",
       saved ? `forecast saved ${etStamp(saved)}` : "no saved forecast, using sportsbook lines"].join(" · ");

  return (
    <>
      <header className="bg-panel2">
        <div className="mx-auto flex max-w-[1280px] flex-wrap items-center justify-between gap-x-6 gap-y-3 px-4 py-4 sm:px-6">
          <div>
            <h1 className="text-2xl font-bold text-white">NFL Game Center</h1>
            <p className="mt-0.5 text-[15px] text-muted">{summary}</p>
          </div>
          <label className="flex items-center gap-3 text-[15px] text-muted">
            Week
            <select
              className="min-h-[44px] bg-panel px-3 text-base text-white hover:bg-line"
              value={week ?? ""}
              onChange={(e) => setWeek(Number(e.target.value))}
            >
              {meta.weeks.map((w) => <option key={w} value={w}>Week {w}</option>)}
            </select>
          </label>
        </div>
      </header>

      <main className="mx-auto max-w-[1280px] space-y-5 px-4 pb-10 pt-0.5 sm:px-6">
      <Segmented label="View" options={["Games", "Player rankings"]} value={view} onChange={setView} />

      {view === "Player rankings" && week !== null && <RankingsView week={week} onOpenGame={(g) => { setGid(g); setView("Games"); }} />}

      {view === "Games" && games && games.length > 0 && <GameStrip games={games} selected={gid} onSelect={setGid} />}

      {view === "Games" && detail && <Scorebug d={detail} />}

      {view === "Games" && detail && (
        <Tabs defaultValue="game" key={detail.gid}>
          <TabsList>
            <TabsTrigger value="game">Game</TabsTrigger>
            <TabsTrigger value="sim">Simulated game</TabsTrigger>
            <TabsTrigger value="players">Players</TabsTrigger>
            <TabsTrigger value="teams">Teams and injuries</TabsTrigger>
            <TabsTrigger value="about">About these numbers</TabsTrigger>
          </TabsList>
          <TabsContent value="game"><Overview d={detail} /></TabsContent>
          <TabsContent value="sim"><SimGame d={detail} /></TabsContent>
          <TabsContent value="players"><Props d={detail} /></TabsContent>
          <TabsContent value="teams"><Matchup d={detail} /></TabsContent>
          <TabsContent value="about"><About meta={meta} /></TabsContent>
        </Tabs>
      )}
      </main>
    </>
  );
}
