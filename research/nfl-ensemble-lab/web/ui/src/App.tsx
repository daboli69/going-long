import { useEffect, useState } from "react";
import { api } from "./api";
import type { Detail, GameRow, Meta } from "./types";
import { etStamp, etTime } from "./lib";
import { GameStrip } from "./components/GameStrip";
import { KpiRow } from "./components/KpiRow";
import { Overview } from "./components/Overview";
import { Guide, Matchup, Props, SpreadTotal } from "./components/Others";
import { Callout, Tabs, TabsContent, TabsList, TabsTrigger } from "./components/ui/primitives";

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [week, setWeek] = useState<number | null>(null);
  const [games, setGames] = useState<GameRow[]>([]);
  const [gid, setGid] = useState<string | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.meta().then((m) => { setMeta(m); if (m.ok) setWeek(m.default_week); }).catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (week === null) return;
    setGames([]);
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

  if (error) return <div className="p-8"><Callout tone="amber">Something went wrong reaching the local server: {error}. Is <code>launch_game_center.bat</code> still running?</Callout></div>;
  if (!meta) return <div className="p-8 text-muted">Loading…</div>;
  if (!meta.ok) return <div className="p-8"><Callout tone="amber">{meta.reason}</Callout></div>;

  const upcoming = games.filter((g) => new Date(g.kickoff_utc).getTime() > Date.now());
  const saved = week !== null ? meta.forecast_saved_at[String(week)] : undefined;

  return (
    <div className="mx-auto max-w-[1500px] space-y-4 px-4 py-6 sm:px-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white">🏈 NFL Game Center</h1>
          <p className="text-sm text-muted">Who is likely to win, by how much, and what each player might do. Plain English, local data, no betting advice.</p>
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

      <KpiRow meta={meta} gamesThisWeek={games.length} nextKickoff={upcoming[0] ? etTime(upcoming[0].kickoff_utc) + " ET" : null} />
      <Callout tone="blue">
        <b>Reality check.</b> {meta.reality_check} Open <b>How to read this</b> for plain-English definitions.
      </Callout>

      <GameStrip games={games} selected={gid} onSelect={setGid} />
      {saved && <p className="text-xs text-muted">Forecast saved {etStamp(saved)}, before the week&apos;s first kickoff. It is never edited afterward.</p>}

      {detail && (
        <Tabs defaultValue="overview" key={detail.gid}>
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="matchup">Team matchup</TabsTrigger>
            <TabsTrigger value="props">Player props</TabsTrigger>
            <TabsTrigger value="spread">Spread &amp; total</TabsTrigger>
            <TabsTrigger value="guide">How to read this</TabsTrigger>
          </TabsList>
          <TabsContent value="overview"><Overview d={detail} /></TabsContent>
          <TabsContent value="matchup"><Matchup d={detail} /></TabsContent>
          <TabsContent value="props"><Props d={detail} /></TabsContent>
          <TabsContent value="spread"><SpreadTotal d={detail} /></TabsContent>
          <TabsContent value="guide"><Guide reality={meta.reality_check} /></TabsContent>
        </Tabs>
      )}
    </div>
  );
}
