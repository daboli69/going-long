import type { Detail, GameRow, GlossaryItem, Meta, Rankings, Sim, TdCardData, TdMarket } from "./types";

async function get<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return (await response.json()) as T;
}

export const api = {
  meta: () => get<Meta>("/api/meta"),
  week: (week: number) => get<GameRow[]>(`/api/week/${week}`),
  game: (gid: string) => get<Detail>(`/api/game/${gid}`),
  rankings: (week: number) => get<Rankings>(`/api/rankings/${week}`),
  tdcard: (gid: string, team: string, player: string) => get<TdCardData>(`/api/tdcard/${gid}?team=${team}&player=${encodeURIComponent(player)}`),
  tdmarket: (week: number) => get<TdMarket>(`/api/tdmarket/${week}`),
  glossary: () => get<GlossaryItem[]>("/api/glossary"),
  sim: (gid: string, mode = "random", draw = 1) => get<Sim>(`/api/sim/${gid}?mode=${mode}&draw=${draw}`),
};
