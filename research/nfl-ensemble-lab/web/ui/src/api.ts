import type { WeekResults, Detail, GameRow, GlossaryItem, Live, Meta, Rankings, Sim, TdCardData, TdMarket } from "./types";

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
  meta: () => get<Meta>("/api/meta"),
  week: (week: number) => get<GameRow[]>(`/api/week/${week}`),
  game: (gid: string) => get<Detail>(`/api/game/${gid}`),
  rankings: (week: number) => get<Rankings>(`/api/rankings/${week}`),
  tdcard: (gid: string, team: string, player: string) => get<TdCardData>(`/api/tdcard/${gid}?team=${team}&player=${encodeURIComponent(player)}`),
  tdmarket: (week: number) => get<TdMarket>(`/api/tdmarket/${week}`),
  glossary: () => get<GlossaryItem[]>("/api/glossary"),
  sim: (gid: string, mode = "random", draw = 1) => get<Sim>(`/api/sim/${gid}?mode=${mode}&draw=${draw}`),
};
