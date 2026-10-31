import { useEffect, useState } from "react";
import { api } from "./api";
import type { Detail, GameRow, Meta } from "./types";
import { dayLabel, etTime } from "./lib";
import { GameStrip } from "./components/GameStrip";
import { Overview } from "./components/Overview";
import { About, Matchup, Models } from "./components/Others";
import { Callout, Tabs, TabsContent, TabsList, TabsTrigger } from "./components/ui/primitives";

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [day, setDay] = useState<string | null>(null);
  const [games, setGames] = useState<GameRow[] | null>(null);
  const [gid, setGid] = useState<string | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.meta().then((m) => { setMeta(m); if (m.ok) setDay(m.default_date); }).catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (day === null) return;
    setGames(null);
    api.day(day).then((rows) => {
      setGames(rows);
      const now = Date.now();
      const next = rows.find((r) => new Date(r.tipoff_utc).getTime() > now) ?? rows[0];
      setGid(next ? next.gid : null);
    }).catch((e) => setError(String(e)));
  }, [day]);

  useEffect(() => {
    if (!gid) { setDetail(null); return; }
    api.game(gid).then(setDetail).catch((e) => setError(String(e)));
  }, [gid]);

  if (error) return <div className="p-8"><Callout tone="amber">Can't reach the local server ({error}). Is <code>launch_game_center.bat</code> still running?</Callout></div>;
  if (!meta) return <div className="p-8 text-muted">Loading…</div>;
  if (!meta.ok) return <div className="p-8"><Callout tone="amber">{meta.reason}</Callout></div>;

  const upcoming = (games ?? []).filter((g) => new Date(g.tipoff_utc).getTime() > Date.now());
  const forecasts = (games ?? []).filter((g) => g.p_home !== null).length;
  const summary = games === null ? "Loading games…"
    : games.length === 0 ? "No games on this date."
    : [`${games.length} games`, upcoming.length ? `next tipoff ${etTime(upcoming[0].tipoff_utc)} ET` : "all games started",
       forecasts ? `${forecasts} saved forecasts` : "no saved forecast for this date"].join(" · ");
  const dates = meta.dates.includes(meta.today) ? meta.dates : [...meta.dates, meta.today].sort();

  return (
    <div className="mx-auto max-w-[1280px] space-y-5 px-4 py-6 sm:px-6">
      <header className="flex flex-wrap items-end justify-between gap-3 border-b border-line pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">NBA Game Center</h1>
          <p className="mt-1 text-sm text-muted">{summary}</p>
        </div>
        <label className="flex items-center gap-2 text-sm text-muted">
          Date
          <select
            className="rounded-lg border border-line bg-panel px-3 py-2 text-white focus:border-accent focus:outline-none"
            value={day ?? ""}
            onChange={(e) => setDay(e.target.value)}
          >
            {dates.map((d) => <option key={d} value={d}>{dayLabel(d)}{d === meta.today ? " (today)" : ""}</option>)}
          </select>
        </label>
      </header>

      {games && games.length > 0 && <GameStrip games={games} selected={gid} onSelect={setGid} />}

      {detail && (
        <Tabs defaultValue="game" key={detail.gid}>
          <TabsList>
            <TabsTrigger value="game">Game</TabsTrigger>
            <TabsTrigger value="models">Six models</TabsTrigger>
            <TabsTrigger value="teams">Teams and injuries</TabsTrigger>
            <TabsTrigger value="about">About these numbers</TabsTrigger>
          </TabsList>
          <TabsContent value="game"><Overview d={detail} /></TabsContent>
          <TabsContent value="models"><Models d={detail} /></TabsContent>
          <TabsContent value="teams"><Matchup d={detail} /></TabsContent>
          <TabsContent value="about"><About meta={meta} /></TabsContent>
        </Tabs>
      )}
    </div>
  );
}
