import type { Tails, SnapSim, Leans, Refs, FirstTdAllowed, KingBoard, KingWeek, WeekResults, Detail, GameRow, GlossaryItem, Live, Meta, Rankings, Sim, TdCardData, TdMarket } from "./types";

async function get<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return (await response.json()) as T;
}

export class NotCaptured extends Error {}
async function getLive(gid: string): Promise<Live> {
  const response = await fetch(`/api/live/${gid}`);
  if (response.status === 404) throw new NotCaptured();
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return (await response.json()) as Live;
}

export const api = {
  live: getLive,
  results: (week: number) => get<WeekResults>(`/api/results/${week}`),
  kingWeek: (week: number) => get<KingWeek>(`/api/kingzone/${week}`),
  leans: (q: string) => get<Leans>(`/api/leans?${q}`),
  tails: () => get<Tails>("/api/tails"),
  refs: (q: string) => get<Refs>(`/api/refs?${q}`),
  snapsim: (gid: string, refresh = false) => get<SnapSim>(`/api/snapsim/${gid}?refresh=${refresh}`),
  firstTdAllowed: (q: string) => get<FirstTdAllowed>(`/api/first-td-allowed?${q}`),
  kingGame: (gid: string) => get<KingBoard>(`/api/kingzone/game/${gid}`),
  meta: () => get<Meta>("/api/meta"),
  week: (week: number) => get<GameRow[]>(`/api/week/${week}`),
  game: (gid: string) => get<Detail>(`/api/game/${gid}`),
  rankings: (week: number) => get<Rankings>(`/api/rankings/${week}`),
  tdcard: (gid: string, team: string, player: string) => get<TdCardData>(`/api/tdcard/${gid}?team=${team}&player=${encodeURIComponent(player)}`),
  tdmarket: (week: number) => get<TdMarket>(`/api/tdmarket/${week}`),
  glossary: () => get<GlossaryItem[]>("/api/glossary"),
  sim: (gid: string, mode = "random", draw = 1) => get<Sim>(`/api/sim/${gid}?mode=${mode}&draw=${draw}`),
};
