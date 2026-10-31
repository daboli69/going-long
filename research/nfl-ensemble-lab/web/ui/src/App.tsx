import { useEffect, useState } from "react";
import { api } from "./api";
import type { Detail, GameRow, Meta } from "./types";
import { etStamp, etTime } from "./lib";
import { GameStrip } from "./components/GameStrip";
import { Overview } from "./components/Overview";
import { About, Matchup, Props } from "./components/Others";
import { SimGame } from "./components/SimGame";
import { Callout, Tabs, TabsContent, TabsList, TabsTrigger } from "./components/ui/primitives";

export default function App() {
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

  if (error) return <div className="p-8"><Callout tone="amber">Can't reach the local server ({error}). Is <code>launch_game_center.bat</code> still running?</Callout></div>;
  if (!meta) return <div className="p-8 text-muted">Loading…</div>;
  if (!meta.ok) return <div className="p-8"><Callout tone="amber">{meta.reason}</Callout></div>;

  const upcoming = (games ?? []).filter((g) => new Date(g.kickoff_utc).getTime() > Date.now());
  const saved = week !== null ? meta.forecast_saved_at[String(week)] : undefined;
  const summary = games === null ? "Loading games…"
    : games.length === 0 ? "No games found for this week."
    : [`${games.length} games`, upcoming.length ? `next kickoff ${etTime(upcoming[0].kickoff_utc)} ET` : "all games played",
       saved ? `forecast saved ${etStamp(saved)}` : "no saved forecast, using sportsbook lines"].join(" · ");

  return (
    <div className="mx-auto max-w-[1280px] space-y-5 px-4 py-6 sm:px-6">
      <header className="flex flex-wrap items-end justify-between gap-3 border-b border-line pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">NFL Game Center</h1>
          <p className="mt-1 text-sm text-muted">{summary}</p>
        </div>
        <label className="flex items-center gap-2 text-sm text-muted">
          Week
          <select
            className="rounded-lg border border-line bg-panel px-3 py-2 text-white focus:border-accent focus:outline-none"
            value={week ?? ""}
            onChange={(e) => setWeek(Number(e.target.value))}
          >
            {meta.weeks.map((w) => <option key={w} value={w}>Week {w}</option>)}
          </select>
        </label>
      </header>

      {games && games.length > 0 && <GameStrip games={games} selected={gid} onSelect={setGid} />}

      {detail && (
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
    </div>
  );
}
