import { useEffect, useState } from "react";
import { BookOpen, CircleDot, Layers, Users } from "lucide-react";
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

  useEffect(() => {
    document.title = detail ? `${detail.away} at ${detail.home} · NBA Game Center` : "NBA Game Center";
  }, [detail]);

  if (error) return <main className="p-6"><Callout tone="amber">Can't reach the local server ({error}). Is <code>launch_game_center.bat</code> still running?</Callout></main>;
  if (!meta) return <main className="p-6 text-muted" role="status">Loading…</main>;
  if (!meta.ok) return <main className="p-6"><Callout tone="amber">{meta.reason}</Callout></main>;

  const upcoming = (games ?? []).filter((g) => new Date(g.tipoff_utc).getTime() > Date.now());
  const forecasts = (games ?? []).filter((g) => g.p_home !== null).length;
  const summary = games === null ? "Loading games…"
    : games.length === 0 ? "No games on this date."
    : [`${games.length} games`, upcoming.length ? `next tipoff ${etTime(upcoming[0].tipoff_utc)} ET` : "all games started",
       forecasts ? `${forecasts} saved forecasts` : "no saved forecast for this date"].join(" · ");
  const dates = meta.dates.includes(meta.today) ? meta.dates : [...meta.dates, meta.today].sort();

  const tab = (value: string, full: string, short: string, Icon: typeof CircleDot) => (
    <TabsTrigger value={value} aria-label={full}>
      <Icon className="h-5 w-5 md:hidden" aria-hidden />
      <span className="md:hidden">{short}</span>
      <span className="hidden md:inline">{full}</span>
    </TabsTrigger>
  );

  return (
    <>
      <a href="#main" className="skip">Skip to the game</a>
      <div className="mx-auto max-w-[1180px] px-4 pb-[calc(5.5rem+env(safe-area-inset-bottom))] pt-5 sm:px-6 md:pb-12 md:pt-8">
        <header className="flex flex-col gap-3 pb-5 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-[1.75rem] font-extrabold leading-none md:text-4xl">NBA Game Center</h1>
            <p className="mt-2 text-base text-muted" role="status">{summary}</p>
          </div>
          <label className="flex items-center gap-3 text-base text-muted">
            Date
            <select
              className="min-h-11 flex-1 rounded border border-[#4a5461] bg-surface px-3 text-base text-ink md:flex-none"
              value={day ?? ""}
              onChange={(e) => setDay(e.target.value)}
            >
              {dates.map((d) => <option key={d} value={d}>{dayLabel(d)}{d === meta.today ? " (today)" : ""}</option>)}
            </select>
          </label>
        </header>

        {games && games.length > 0 && <GameStrip games={games} selected={gid} onSelect={setGid} />}

        <main id="main" className="mt-5">
          {detail && (
            <Tabs defaultValue="game" key={detail.gid}>
              <TabsList aria-label="Game views">
                {tab("game", "Game", "Game", CircleDot)}
                {tab("models", "Six models", "Models", Layers)}
                {tab("teams", "Teams and injuries", "Teams", Users)}
                {tab("about", "About these numbers", "About", BookOpen)}
              </TabsList>
              <TabsContent value="game"><Overview d={detail} /></TabsContent>
              <TabsContent value="models"><Models d={detail} /></TabsContent>
              <TabsContent value="teams"><Matchup d={detail} /></TabsContent>
              <TabsContent value="about"><About meta={meta} /></TabsContent>
            </Tabs>
          )}
        </main>
      </div>
    </>
  );
}
