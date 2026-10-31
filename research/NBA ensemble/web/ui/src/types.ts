// Shapes of the JSON served by web/server.py (see nba_lab/gamecenter_data.py). Nothing here is computed in the browser except formatting.
export interface TrackRecord {
  games?: number;
  accuracy?: number;
  home_team_accuracy?: number;
  margin_miss?: { games: number; points: number };
}

export interface Meta {
  ok: boolean;
  reason?: string;
  dates: string[];
  default_date: string;
  today: string;
  track_record: TrackRecord;
  evaluation_status: string | null;
  reality_check: string;
}

export interface GameRow {
  gid: string;
  away: string;
  home: string;
  away_color: string;
  home_color: string;
  tipoff_utc: string;
  completed: boolean;
  started: boolean;
  away_score: number | null;
  home_score: number | null;
  p_home: number | null;
}

export interface TeamSummary {
  record: string;
  games: number;
  pf: number | null;
  pa: number | null;
  last: string[];
}

export interface InjuryRow {
  player: string;
  status: string;
  tone: "red" | "amber";
  updated: string | null;
  note: string;
}

export interface Detail {
  gid: string;
  date: string;
  away: string;
  home: string;
  away_name: string;
  home_name: string;
  away_color: string;
  home_color: string;
  tipoff_utc: string;
  date_label: string;
  time_label: string;
  completed: boolean;
  away_score: number | null;
  home_score: number | null;
  records: Record<string, string>;
  matchup: Record<string, TeamSummary>;
  injuries: { retrieved: string | null; teams: Record<string, InjuryRow[]> };
  has_forecast: boolean;
  headline?: { p_home: number; p_label: string; favored: string; favored_name: string; p_favored: number; saved_at: string; model_version: string };
  models?: { name: string; p_home: number }[];
  vote?: { home: number; away: number; tie: boolean };
  disagreement_points?: number;
  forecast_warning?: string | null;
  sources?: { name: string; p_home: number }[];
  expected?: {
    home_pts: number; away_pts: number; margin: number; total: number; margin_mid: number; total_mid: number;
    margin_range: [number, number]; total_range: [number, number]; p_home_score_model: number; spread_label: string;
  };
  distribution?: { margin: { x: number; p: number }[]; total: { x: number; p: number }[] };
  result?: { winner: string; favorite_won: boolean };
}

export interface GlossaryItem {
  term: string;
  text: string;
}
