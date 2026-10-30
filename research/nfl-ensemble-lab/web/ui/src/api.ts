import type { Detail, GameRow, GlossaryItem, Meta } from "./types";

async function get<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return (await response.json()) as T;
}

export const api = {
  meta: () => get<Meta>("/api/meta"),
  week: (week: number) => get<GameRow[]>(`/api/week/${week}`),
  game: (gid: string) => get<Detail>(`/api/game/${gid}`),
  glossary: () => get<GlossaryItem[]>("/api/glossary"),
};
