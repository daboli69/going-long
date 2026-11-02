import { useEffect, useState } from "react";
import { api } from "./api";
import type { Detail, GameRow, Meta } from "./types";
import { etStamp, etTime } from "./lib";
import { GameStrip } from "./components/GameStrip";
import { GameTitle, Overview, Scorebug } from "./components/Overview";
import { About, Matchup } from "./components/Others";
import { Props } from "./components/Players";
import { LiveGame } from "./components/Live";
import { SimGame } from "./components/SimGame";
import { RankingsHub } from "./components/RankingsHub";
import { MarketValueView } from "./components/MarketValue";
import { ResultsView } from "./components/Results";
import { KingZoneView } from "./components/KingZone";
import { LeansView } from "./components/Leans";
import { RefsView } from "./components/Refs";
import { SnapSimView } from "./components/SnapSim";
import { Callout, Tabs, TabsContent, TabsList, TabsTrigger } from "./components/ui/primitives";

type View = "games" | "rankings" | "king" | "leans" | "refs" | "snap" | "market" | "results";

export default function App() {
  const [view, setView] = useState<View>("games");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [week, setWeek] = useState<number | null>(null);
  const [games, setGames] = useState<GameRow[] | null>(null);
  const [gid, setGid] = useState<string | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [retrying, setRetrying] = useState(false);
  const [gameTab, setGameTab] = useState("game");
  const [finished, setFinished] = useState<string[]>([]);
  useEffect(() => { setGameTab("game"); }, [gid]);

  useEffect(() => {
    api.meta().then((m) => { setMeta(m); setError(null); if (m.ok) setWeek((w) => w ?? m.default_week); }).catch((e) => setError(String(e))).finally(() => setRetrying(false));
  }, [attempt]);

  useEffect(() => {
    if (week === null) return;
    setGames(null);
    api.week(week).then((rows) => {
      setGames(rows);
      const now = Date.now();
      const next = rows.find((r) => new Date(r.kickoff_utc).getTime() > now) ?? rows[0];
      setGid((g) => (g && rows.some((r) => r.gid === g) ? g : next ? next.gid : null));
    }).catch((e) => setError(String(e)));
  }, [week, attempt]);

  useEffect(() => {
    if (!gid) { setDetail(null); return; }
    api.game(gid).then(setDetail).catch((e) => setError(String(e)));
  }, [gid, attempt]);

  if (error) return (
    <div className="mx-auto max-w-[640px] space-y-3 p-6">
      <Callout tone="amber">Can't reach the local server ({error}). Is <code>launch_game_center.bat</code> still running?</Callout>
      <button type="button" disabled={retrying} className="min-h-[44px] bg-white px-4 font-semibold text-bg hover:bg-white disabled:opacity-70"
        onClick={() => { setRetrying(true); setError(null); setAttempt((n) => n + 1); }}>{retrying ? "Trying…" : "Try again"}</button>
    </div>
  );
  if (!meta) return <div className="p-8 text-muted">Loading…</div>;
  if (!meta.ok) return <div className="p-8"><Callout tone="amber">{meta.reason}</Callout></div>;

  const liveOn = !!detail && !detail.completed && !finished.includes(detail.gid) && Date.now() >= new Date(detail.kickoff_utc).getTime();
  const upcoming = (games ?? []).filter((g) => new Date(g.kickoff_utc).getTime() > Date.now());
  const saved = week !== null ? meta.forecast_saved_at[String(week)] : undefined;
  const next = upcoming[0];
  const status = games === null ? "Loading games…" : games.length === 0 ? "No games found for this week."
    : saved ? `Forecast saved ${etStamp(saved)}` : "No saved forecast, using sportsbook lines";

  return (
    <>
      <header className="bg-panel2">
        <div className="mx-auto flex min-h-[64px] max-w-[1320px] flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2 sm:px-6">
          <span className="text-lg font-bold text-white">NFL Game Center</span>
          <label className="sr-only" htmlFor="week">Week</label>
          <select id="week" className="min-h-[44px] bg-panel px-4 text-base text-white hover:bg-raised" value={week ?? ""} onChange={(e) => setWeek(Number(e.target.value))}>
            {meta.weeks.map((w) => <option key={w} value={w}>Week {w}</option>)}
          </select>
          <span className="basis-full pb-1 text-sm text-muted sm:ml-auto sm:basis-auto sm:pb-0">{status}<span className="hidden sm:inline">{next ? `, next kickoff ${etTime(next.kickoff_utc)} ET` : games && games.length ? ", all games played" : ""}</span></span>
        </div>
      </header>

      <main className="mx-auto max-w-[1320px] px-4 pb-12 sm:px-6">
        <Tabs value={view} onValueChange={(v) => setView(v as View)}>
          <TabsList aria-label="Views" className="mt-4">
            <TabsTrigger value="games">Games</TabsTrigger>
            <TabsTrigger value="rankings">Player rankings</TabsTrigger>
            <TabsTrigger value="king">King of the End Zone</TabsTrigger>
            <TabsTrigger value="leans">Leans</TabsTrigger>
            <TabsTrigger value="refs">Refs</TabsTrigger>
            <TabsTrigger value="snap">Snap sim</TabsTrigger>
            <TabsTrigger value="market">Market value</TabsTrigger>
            <TabsTrigger value="results">Results</TabsTrigger>
          </TabsList>

          <TabsContent value="games" className="mt-4">
            {games && games.length > 0 && week !== null && <GameStrip games={games} selected={gid} onSelect={setGid} week={week} />}
            {detail && (
              <div className="mt-2">
                <GameTitle d={detail} />
                <Scorebug d={detail} />
                <Tabs value={gameTab} onValueChange={setGameTab} key={detail.gid} className="mt-6">
                  <TabsList aria-label="Game views">
                    <TabsTrigger value="game">Game</TabsTrigger>
                    <TabsTrigger value="sim">Simulated game</TabsTrigger>
                    {liveOn && <TabsTrigger value="live">Live</TabsTrigger>}
                    <TabsTrigger value="players">Players</TabsTrigger>
                    <TabsTrigger value="teams">Teams and injuries</TabsTrigger>
                    <TabsTrigger value="about">About these numbers</TabsTrigger>
                  </TabsList>
                  <TabsContent value="game"><Overview d={detail} /></TabsContent>
                  <TabsContent value="sim"><SimGame d={detail} /></TabsContent>
                  {liveOn && <TabsContent value="live"><LiveGame d={detail} onFinished={() => { setFinished((f) => (f.includes(detail.gid) ? f : [...f, detail.gid])); setGameTab("game"); }} /></TabsContent>}
                  <TabsContent value="players"><Props d={detail} /></TabsContent>
                  <TabsContent value="teams"><Matchup d={detail} /></TabsContent>
                  <TabsContent value="about"><About meta={meta} /></TabsContent>
                </Tabs>
              </div>
            )}
          </TabsContent>

          <TabsContent value="rankings" className="mt-6">{week !== null && <RankingsHub week={week} onOpenGame={(g) => { setGid(g); setView("games"); }} />}</TabsContent>
          <TabsContent value="leans" className="mt-6"><LeansView /></TabsContent>
          <TabsContent value="refs" className="mt-6"><RefsView /></TabsContent>
          <TabsContent value="snap" className="mt-6">{games && <SnapSimView games={games} gid={gid} onPick={setGid} />}</TabsContent>
          <TabsContent value="king" className="mt-6">{week !== null && <KingZoneView week={week} />}</TabsContent>
          <TabsContent value="results" className="mt-6"><ResultsView weeks={meta.weeks.filter((w) => w <= meta.default_week)} latest={meta.default_week} onOpenGame={(g) => { setGid(g); setView("games"); }} /></TabsContent>
          <TabsContent value="market" className="mt-6">{week !== null && <MarketValueView week={week} />}</TabsContent>
        </Tabs>
      </main>
    </>
  );
}
