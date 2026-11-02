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
  fpds?: Record<string, number>;
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
  time_label: string;
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
  props_left_out?: { player: string; team: string; status: string }[];
  props_questionable?: { player: string; team: string; status: string }[];
  props_moves?: { player: string; team: string; text: string }[];
  injury_adjustment?: { since: string; margin: number; total: number; coefficients: { lost_share: number; qb: number }; saved: { margin: number; total: number; p_home: number };
    teams: Record<string, { known: boolean; points: number; lost_share: number; qb: number; new_out: { player: string; pos: string | null; share: number }[]; back: { player: string; pos: string | null; share: number }[] }> } | null;
  result?: { winner: string; favorite_won: boolean };
}

export interface GlossaryItem {
  term: string;
  text: string;
}

export interface SimPlay {
  team: string;
  kind: "pass" | "incomplete" | "sack" | "rush" | "fg" | "punt";
  player: string | null;
  passer: string | null;
  yards: number;
  qtr: number;
  clock: string;
  down: number;
  togo: number;
  x_start: number;
  x_end: number;
  x_first: number;
  spot: string;
  event: "TD" | "FG" | "PUNT" | "INT" | "FUMBLE" | "DOWNS" | null;
  text: string;
  score: Record<string, number>;
}

export interface Band { low: number; median: number; high: number }

export interface DefenseCard {
  team: string;
  faces: string;
  games: number;
  rows: { label: string; value: number; rank: string }[];
}

export interface Sim {
  gid: string;
  away: string;
  home: string;
  ok: boolean;
  reason?: string;
  ranges?: { sims: number; home: Band; away: Band; total: Band };
  replay?: { plays: SimPlay[]; final: Record<string, number>; qbs: Record<string, string>; targets: Record<string, number> };
  defense?: DefenseCard[];
  source?: { margin: string | null; total: string | null };
  has_players?: boolean;
  players?: PropRow[];
  player_source?: Record<string, string>;
  injury_moves?: { player: string; team: string; status: string; text: string }[];
  unavailable?: { player: string; team: string; status: string }[];
  injury_source?: string | null;
  weather?: Weather;
  questionable?: { team: string; player: string; group: string; chance: number; plays: boolean }[];
  allowed?: { applied: boolean; passed_gate: boolean; teams: { team: string; versus: string; rows: { defense: string; pos: string; stat: string; gap: number; factor: number }[] }[] };
  receiving?: { model: "sampled" | "averaged" };
  game?: { mode: "typical" | "random" | "upset"; draw: number; favorite: string; underdog: string; p_home: number; p_underdog: number; points: Record<string, number> };
  own?: { p_home: number; margin: number; total: number; home: number; away: number; sd_m: number; sd_t: number;
          evidence?: { pick_accuracy?: { market: number; drive_sim: number }; same_pick?: number; used?: Record<string, boolean> } } | null;
  fpds?: { through_week: number | null; tested: boolean; catches_for_thin_history: boolean; receiving_yards_blend: boolean; td_red_zone: boolean; thin_players: Record<string, number> };
  redistribution?: { kept_rec: number; kept_rush: number; to_new_rec: number; to_new_rush: number; fitted_on: number[] | null };
}

export interface Weather {
  stadium: string;
  roof: "indoors" | "outdoors" | "retractable";
  source: string;
  status: "indoors" | "too_early" | "unavailable" | "forecast" | "recorded";
  text: string;
  temp_f?: number;
  condition?: string;
  wind_mph?: number;
  gust_mph?: number;
  precip_chance?: number | null;
  precip_in?: number;
}

export interface RankRow {
  rank: number; player: string; team: string; opp: string; home: boolean; gid: string; kickoff_utc: string; pos: string | null; stat: string;
  projection: number; range_low: number | null; range_high: number | null; market_line: number | null; market_chance: number | null;
  exp_td?: number; red_zone?: RedZone | null; carries?: number | null; score: number; parts: { projection: number; matchup: number | null; usage: number | null }; tags: string[];
}
export interface RankStat { label: string; unit: "yds" | "rec" | "chance"; rows: RankRow[]; players?: number }
export interface Rankings { week: number; weights: Record<string, number>; stats: Record<string, RankStat> }

export interface TdZone { zone: string; carries: number; targets: number; xtd: number }
export interface TdCardData {
  player: string; pid: string; team: string; opp: string; pos: string; role: string | null; tdp: number | null; score: number | null; exp_td: number | null;
  window: { weeks: number[]; games: number; team_games: number };
  script: { favored_by: number | null; total: number | null; implied: number | null; pace_rank: number | null; pace: number | null };
  profile: {
    rz_role: number | null; rz_claim: { mine: number; group: number; share: number | null; group_label: string; team_rz_touches: number };
    rz_targets_pg: number; rz_carries_pg: number; team_rz_trips_pg: number; team_rz_td_rate: number | null; opp_rz_td_rate_allowed: number | null; opp_rz_rank: number | null;
    touches_pg: number; gl_pg: number; target_share: number | null; td_rate: number | null;
  };
  cheat: { expected: number; scored: number; debt: number; zones: TdZone[] };
  role_tax: { role: string; rows: { metric: string; him: number; allows: number; rank: number | null }[] } | null;
  leaks: { text: string; hits_role: boolean }[];
  opportunity: {
    matchup_pg: number | null; table: { week: number; vs: string; RB: number; WR: number; TE: number; QB: number }[];
    totals: Record<string, number>; ranks: Record<string, number>; adv: Record<string, number>; snap_share: number | null; games_since_td: number;
  };
  tags: { label: string; fired: boolean; why: string }[]; tagline: string; fired: number;
}
export interface MarketRow {
  player: string; team: string; opp: string; home: boolean; gid: string; kickoff_utc: string; pos: string | null; projection: number; score: number; tags: string[];
  market: { ticker: string; bid: number | null; ask: number | null; last: number | null; vol24: number } | null;
  edge?: number | null; edge_after_fee?: number | null; label?: string; mid?: number | null; value?: boolean;
}
export interface TdMarket { week: number; fee_rate: number; value_edge: number; min_chance: number; markets_open: number; players: number; matched: number; rows: MarketRow[]; unpriced: MarketRow[] }

export type RedZone = { ez_tgt: number | null; i20_tgt: number | null; i5_carry_share: number | null; weeks: number };
export type ResultGame = {
  gid: string; away: string; home: string; away_score: number; home_score: number; kickoff_label: string; pick: string; p_pick: number; winner: string | null; correct: boolean | null;
  exp_margin: number | null; margin: number; margin_error: number | null; exp_total: number | null; total: number; total_error: number | null; actuals_from: string | null;
};
export type ResultPlayer = { gid: string; player: string; team: string; opp: string; stat: string; projected: number; low: number | null; high: number | null; actual: number; error: number; inside: boolean | null; opps: number; tolerance: number; close: boolean; market_line: number | null; bet_won: boolean | null };
export type WeekResults = {
  week: number; games: ResultGame[]; players: ResultPlayer[];
  summary: { games_played: number; games_scored: number; pending_actuals: string[]; left_out: number; picked_right: number; picked_wrong: number; accuracy: number | null; avg_confidence: number; mean_abs_margin_error: number; mean_abs_total_error: number; margin_inside_80: number; total_inside_80: number };
  player_summary: Record<string, { close_rate: number; bets: number; bets_won: number; n: number; mean_abs_error: number; bias: number; inside_range: number | null }>;
};
export type LiveTd = { team: string; name: string; td_so_far: number; chance_pre: number | null; chance_now: number; scored: boolean };
export type LiveRow = { team: string; name: string; stat: string; yards: number; targets_or_carries: number; team_attempts: number; frozen: number; updated: number; low: number; high: number; share_pre: number; share_post: number; kind?: string };
export type Live = {
  gid: string; event: string; snapshot: string; age_seconds: number; newest_play_seconds: number | null; feed_lag: { n: number; median: number; p90: number; basis: string } | null; state: string; period: number | null; clock: number | null; score: { home: number; away: number };
  possession: string | null; last_play: string | null; win_chance_home: number | null;
  frozen: { sha256: string; frozen_at: string; before_kickoff: boolean } | null;
  players: LiveRow[]; touchdowns: LiveTd[]; first_td: { text: string; period: number | null; clock: string | null } | null; warnings: LiveRow[]; not_in_feed: string[];
};

export type KingRow = { rank: number; player: string; team: string; opp: string; pos: string; chance: number; exp_td: number; p_40: number; p_60: number; why: string[]; kinds: string[] };
export type KingBoard = {
  gid: string; away: string; home: string; kickoff_utc: string; week: number; rows: KingRow[]; players_scored: number; listed_total: number;
  field: { defense_special_teams: Record<string, number>; other_players: Record<string, number> };
  no_touchdown: number; expected_longest: number; expected_td: Record<string, number>; completed: boolean;
};
export type KingWeek = { week: number; default_gid: string | null; games: { gid: string; away: string; home: string; kickoff_utc: string; completed: boolean; monday: boolean }[] };
