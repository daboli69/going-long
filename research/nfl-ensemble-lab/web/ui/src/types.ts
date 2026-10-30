// Shapes of the JSON served by web/server.py (see lab/gamecenter_data.py). Nothing here is computed in the browser except formatting.
export interface Kpis {
  market_acc?: { accuracy: number; games: number; elo_accuracy_same_games: number };
  elo_acc_long?: { accuracy: number; games: number; window: string };
  margin_miss?: { market: number; model: number; games: number };
  range_hit?: Record<string, number>;
}

export interface Meta {
  ok: boolean;
  reason?: string;
  season: number;
  weeks: number[];
  default_week: number;
  forecast_saved_at: Record<string, string>;
  kpis: Kpis;
  reality_check: string;
}

export interface GameRow {
  gid: string;
  away: string;
  home: string;
  away_color: string;
  home_color: string;
  kickoff_utc: string;
  kickoff_label: string;
  completed: boolean;
  started: boolean;
  away_score: number | null;
  home_score: number | null;
  p_home: number | null;
  p_label: string | null;
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
  pos: string | null;
  status: string;
  tone: "red" | "amber";
  meaning: string;
  note: string;
}

export interface PropRow {
  player: string;
  team: string;
  stat: string;
  typical: number;
  range_low: number | null;
  range_high: number | null;
  market_line: number | null;
  market_chance: number | null;
  our_chance: number | null;
}

export interface Ladder {
  question: string;
  market: number;
  model: number;
}

export interface Detail {
  gid: string;
  week: number;
  away: string;
  home: string;
  away_name: string;
  home_name: string;
  away_color: string;
  home_color: string;
  kickoff_utc: string;
  date_label: string;
  kickoff_label: string;
  stadium: string;
  completed: boolean;
  away_score: number | null;
  home_score: number | null;
  forecast_saved_at: string | null;
  forecast_hash_ok: boolean | null;
  records: Record<string, string>;
  matchup: Record<string, TeamSummary>;
  has_forecast: boolean;
  headline?: { p_home: number; p_label: string; favored: string; favored_name: string; p_favored: number };
  sources?: { name: string; p_home: number }[];
  agreement?: { gap_points: number; agree: boolean };
  expected?: { margin: number | null; margin_label: string | null; total: number | null; total_label: string | null; sd_m: number; sd_t: number; home_pts?: number; away_pts?: number };
  lean?: { abstain: boolean; diff_points: number; toward: string | null; text: string } | null;
  outcomes?: { label: string; p: number }[];
  distribution?: { margin: { x: number; p: number }[]; total: { x: number; p: number }[] };
  ladders?: { margin: Ladder[]; total: Ladder[] };
  injuries?: { stamp: string | null; teams: Record<string, InjuryRow[]> };
  props?: PropRow[];
  result?: { winner: string; favorite_won: boolean };
}

export interface GlossaryItem {
  term: string;
  text: string;
}
