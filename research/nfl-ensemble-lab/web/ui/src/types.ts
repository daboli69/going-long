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
  fpds_update?: { margin: number; margin_low: number; margin_high: number; total: number; total_low: number; total_high: number; p_home: number; through_week: number; created_at: string } | null;
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
  fpds?: { through_week: number | null; tested: boolean; catches_for_thin_history: boolean; receiving_yards_blend: boolean; td_red_zone: boolean; rushing_yards_blend?: boolean; rush_td_goal_line?: boolean; unvalidated?: string[]; passing_yards?: string; thin_players: Record<string, number> };
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

export type KingPair = { anytime: number | null; two_plus: number | null; first: number | null };
export type KingRow = {
  rank: number; pid: string; player: string; team: string; opp: string; pos: string | null; chance: number; anytime: number; two_plus: number; first: number; p40: number; p60: number;
  market_anytime: number | null; market_at: string | null; crowd_basis: "market" | "model"; given_longest: KingPair; pairs_best_with: keyof KingPair | null;
  pool_index: number; pool_index_range: [number, number]; why: string[];
};
export type KingWalk = {
  verdict: { P1_beats_expected_td_split?: boolean; P2_calibrated?: boolean; P3_holdout_positive?: boolean; label?: string; "have_enough_games_for_0.05"?: boolean };
  test: { games: number; mean_log_model: number; mean_log_b1: number; mean_log_b2: number; diff_vs_b1: { mean: number; ci95: [number, number]; sd: number }; "games_needed_80pct_power_for_0.05": number;
    top_pick: { stated: number; realized: number; se: number; n: number }; field: { stated: number; realized: number };
    reliability: { bucket: string; n: number; stated: number; realized: number; se: number; flag: boolean }[]; flagged_buckets: number } | null;
  holdout: { mean: number; ci95: [number, number] } | null;
};
export type KingBoard = {
  gid: string; away: string; home: string; kickoff_utc: string; week: number; rows: KingRow[]; listed_total: number; field: number; no_touchdown: number; expected_longest: number;
  teams: { team: string; lam: number; pass_rate: number; drives: number }[]; dropped_out: string[]; fit: string; sims: number; completed: boolean; walk: KingWalk | Record<string, never>;
  frozen: { frozen_at: string; before_kickoff: boolean; sha256: string } | null;
};
export type KingWeek = { week: number; default_gid: string | null; games: { gid: string; away: string; home: string; kickoff_utc: string; completed: boolean; monday: boolean }[] };

export type LeansSummary = { n: number; games?: number; effective_n?: number; design_effect?: number; win_rate?: number; stated_edge?: number; realized_edge?: number; clv?: number; need_for_2pt?: number; realized_ci?: [number, number]; note: string };
export type LeansRow = { gid: string; season: number; week: number; market: string; k: number; side: string; q: number; m: number; c: number; price: number; edge: number; size: string; win: number; real: number; clv: number };
export type LeansPending = { gid: string; week: number; market: string; player: string; team: string; side: string; line: number; source: string; model_p: number; market_p: number; edge: number; kickoff_utc: string };
export type Leans = {
  markets: { name: string; testable: boolean; why?: string }[]; summary: LeansSummary; benchmarks: { follow_market_realized: number | null; random_side_realized: number | null };
  headline: LeansSummary; raw_headline: LeansSummary;
  market_accuracy: { rows: number; chosen: string; candidates: Record<string, { log_loss: number; brier: number; gain_vs_mid?: { gain: number; ci: [number, number] }; gain_vs_market?: { gain: number; ci: [number, number] } }> };
  recal_compare: { chosen: string; log_loss: Record<string, number>; gain_logistic: { gain: number; ci: [number, number] }; gain_isotonic: { gain: number; ci: [number, number] } };
  placebo: { mean_edge: number; range: [number, number] }; pass: Record<string, boolean>;
  calibration: Record<string, { bucket: string; n: number; stated: number; realized: number }[]>; rows: LeansRow[]; pending: LeansPending[]; rule_sha256: string; universe_rows: number;
};

export type RefRow = { referee: string; n: number; k: number | null; rate: number; lo: number; hi: number; shrunk: number; league: number; too_few: boolean };
export type RefGame = { gid: string; away: string; home: string; kickoff: string; referee: string | null; tab?: { games: number; home_cover_shrunk: number | null; league_home_cover: number; home_pen_per_game_shrunk: number | null; away_pen_per_game_shrunk: number | null } | null };
export type Refs = {
  measures: Record<string, string>; kind: "rate" | "count"; referees: string[]; rows: RefRow[]; selected: RefRow | null;
  this_week: { season: number; week: number | null; source: string; assigned?: number; games: RefGame[] };
  frozen: { week: number; created: string; games: RefGame[] }[];
  results: {
    rule_sha256: string; games: number; referees: number; any_effect_claimed: boolean; discovery_ats_tests: number; claims: { measure: string; referee: string; confirmed: boolean }[];
    year_to_year: Record<string, { pairs: number; r: number | null; ci: [number, number] | null }>;
    tweet_check: { referee: string; since: number; tweet: Record<string, string | number>; rebuilt: Record<string, string | number | null>; exact_p_vs_league: number | null; luck_check: { extreme_referees_considered: number; share_of_shuffles_with_a_referee_this_far: number } };
    market: { games: number; seasons?: number[]; corr_belief_with_move?: number | null; log_score_gain_vs_constant?: { gain: number; ci: [number, number] }; note?: string };
    coverage: { by_season: Record<string, { games: number; with_referee: number; in_both: number; same: number }>; missing: string };
  };
};

export type FirstTdRow = { team: string; games: number; tds: number; counts: Record<string, number>; pct: Record<string, number | null> };
export type FirstTdAllowed = { season: number; weeks: number[]; weeks_available: number[]; overall: boolean; seasons: number[]; positions: string[]; rows: FirstTdRow[]; league: Omit<FirstTdRow, "team"> };

export type SnapDist = { mean: number; p10: number; median: number; p90: number };
export type SnapLean = { player: string; team: string; stat: string; line: number; market_chance: number; sim_chance: number; edge: number; matchup_ratio: number | null; volume_ratio: number | null; side: string | null; signals: { sim: string | null; matchup: string | null; game: string | null } };
export type SnapSim = {
  gid: string; away: string; home: string; week: number; sims: number; spread_home: number; total: number; kickoff: string; created: string; frozen: boolean; frozen_ok?: boolean; sha256?: string; rule_sha256: string; rest: { away: number; home: number };
  win: Record<string, number>; raw_win: Record<string, number>; cover: Record<string, number>; cover_raw: Record<string, number>; over: number; under: number; over_raw_push: number; over_scoring_adjusted: number; ladder: { spreads: { line: number; home: number; away: number }[]; totals: { line: number; over: number; over_adjusted: number }[] }; scoring_gap_per_team: number;
  score: { home: SnapDist; away: SnapDist; margin: SnapDist; total: SnapDist };
  adjustments: { home_field_points: number; rest_points_to_home: number; rest_beta_per_day: number; rest_se: number; false_start_multiplier: number; false_start_rank: number; false_start_rank_raw: number; stadiums: number; visiting_false_start_rate: number; league_rate: number };
  team_stats: Record<string, Record<string, number>>; scenario: { star?: string; rookie?: string | null; rookie_name?: string; rookie_unavailable?: boolean }; out: Record<string, string[]>;
  scenario_runs: Record<string, { win: Record<string, number>; cover: Record<string, number>; over: number; star: SnapDist | null }>;
  leans: { leans: SnapLean[]; sim_only: SnapLean[]; props_checked: number };
  players: { team: string; name: string; pos: string; anytime_td: number; stats: Record<string, SnapDist> }[];
  validation: { v1: Record<string, { sim: number; actual: number; ratio: number; within_5pct: boolean } | boolean | number>; v2: Record<string, number> } | null;
};

export type TailTest = { flagged_games: number; observed_rate: number; priced_rate: number; ratio: number; diff: number; p_one_sided: number; p_holm: number };
export type TailGame = { gid: string; away: string; home: string; closing_spread_home: number; elo_qb_margin: number; gap: number; u_qb: boolean; u_gap: boolean; u_any: boolean; range_90: [number, number]; baseline_tail_14: number; baseline_tail_21: number; starters: { home: { qb: string; career_dropbacks: number; changed: boolean }; away: { qb: string; career_dropbacks: number; changed: boolean } } };
export type Tails = {
  results: {
    inventory: { games_with_result_and_closing_line: number; seasons: [number, number]; games_with_moneyline: number; sbr_open_and_close_games: number; sbr_seasons: [number, number]; kalshi_snapshots: Record<string, { files: number; first: string | null; last: string | null }> };
    reconcile: Record<string, { games: number; sd_margin_minus_line: number }> & { key_numbers_share_of_games_pct: Record<string, number> };
    power: { reference_sigma: number; flags: Record<string, { flagged_confirmation: number; expected_rate: number; smallest_detectable_rate_increase: number; relative: number }> };
    tail_tests: { discovery: Record<string, TailTest>; confirmation: Record<string, TailTest>; passed: string[] };
    forecast_accuracy: { games: number; brier: Record<string, number>; paired: Record<string, { mean: number; ci95: [number, number] }> };
    range_models: { coverage_90_model: number; pinball_model_minus_constant: { mean: number; ci95: [number, number] }; t_fit_flagged: { df: number }; pit_deciles_flagged_confirmation: number[] };
    favorite_longshot: Record<string, { implied_bin: [number, number]; games: number; implied: number; realized: number; wilson95: [number, number] }[]>;
    rule_sha256: string;
  };
  week: { file: string; sha256: string; hash_ok: boolean; created: string; forecast: { season: number; week: number; games: TailGame[] } } | null;
  deep: {
    starter_agreement: { team_games_compared: number; share: number };
    sbr_rederive: { html_games_parsed: number; matched_to_games_csv_by_date_and_score: number; closing_spread_equal: number; spread_within_1_point: number };
    kalshi_history: Record<string, Record<string, { markets: number; events: number; settled_yes_or_no: number; first_close: string | null; last_close: string | null }>>;
    same_season_control: { discovery: Record<string, TailTest & { placebo_percentile: number }>; confirmation: Record<string, TailTest & { placebo_percentile: number }>; passed: string[] };
    original_ratios: { discovery: Record<string, number>; confirmation: Record<string, number> };
    positive_controls: { natural_detected: boolean; injected: Record<string, number>; method_has_power_at_1_20: boolean };
    dose_response: { passed: string[] };
  } | null;
  ladders: {
    counts: Record<string, { games?: number; events?: number; rungs?: number; settled_rungs?: number; rungs_with_candles?: number; rungs_with_trade_tape?: number; first_kickoff?: string; last_kickoff?: string }>;
    recovery: { scale_bar_ok: boolean; tail_bar_ok: boolean };
    audit: { settled_rungs: number; rungs_where_kalshi_settlement_disagrees_with_nflverse: number; games_dropped_for_settlement_mismatch: number };
    fitted_ladders: number;
    tape_check: { markets_with_tape: number; compared: number; median_abs_diff: number | null };
    tail_test_informative?: boolean;
    tests: null | {
      passed: string[];
      decide_2025: Record<string, LadderRow>; confirm_2026: Record<string, LadderRow>;
    };
  } | null;
  leadlag: {
    counts: { games_2026_weeks_1_to_8_played: number; games_with_both_sides_and_closes: Record<string, number>; going_archive_snapshots: number; kalshi_winner_games: number; trade_prints_center_rungs: number; sportsbook: { book_quote_rows: number; book_quote_games: number; books: number; book_quote_range: [string, string] } };
    power: Record<string, { games: number; informative: boolean; a_B_kalshi_leads?: { min_detectable: number }; a_K_book_leads?: { min_detectable: number } }>;
    qb_events: { qb_status_changes: number; before_that_teams_game_within_72h: number; with_both_markets_priced: number };
    any_informative: boolean;
  } | null;
  ladders_forward: { files: number; games_scored: number; width_level?: number; tail10?: number } | null;
  prospective: { weeks: { file: string; scored_games?: number; games?: number; status?: string }[]; by_flag: Record<string, { games: number; hit14: number; hit21: number; priced14: number; priced21: number }> };
};

export type LadderRow = { games: number; note?: string; width_level: number; tail10: number; tail2: number; center_diff: number; center_ci95: [number, number]; width_ci95: [number, number]; holm_width: number; holm_tail10: number; ks_p: number; median_df: number; median_abs_gap_to_line: number; perm_percentile: { width_level: number; tail10: number; tail2: number }; power: { min_detectable_width_error: number; min_detectable_tail10_excess: number } };

export type OuRow = { player: string; team: string; opp: string; pos: string | null; stat: string; gid: string; kickoff_utc: string; projection: number; mean: number; low: number; high: number; line: number; call: "Over" | "Under" | "Even"; chance: number; gap: number; strength: number; line_status: string; tier: string };
export type OuCalls = { ok: boolean; reason?: string; week?: number; through_week?: number; created_at?: string; status?: string; rows: OuRow[] };

export type CovShare = { WR: number; TE: number; RB: number };
export type CovRate = { key: string; label: string; pct: number; league: number };
export type CovPosition = {
  pos: "WR" | "TE" | "RB"; tgt_pg: number; tgt_pg_league: number; tgt_rank: number; ypt: number; ypt_league: number; fp_pg: number; fp_rank: number;
  expl: number; expl_league: number; epa: number; epa_league: number; nfl_targets: number; share: number; share_league: number; read: string;
};
export type CovReceiver = {
  name: string; pos: string; routes: number; yprr: number; man_routes: number; zone_routes: number; man_yprr: number; zone_yprr: number;
  man_yprr_raw: number | null; zone_yprr_raw: number | null; man_minus_zone: number; edge?: number;
};
export type CovSide = {
  qb_team: string; defense: string; note: string | null;
  qb: { id: string | null; name: string | null; missing?: boolean; tagged?: number; seasons?: Record<string, number>; untagged_2026?: number };
  defense_mix: { weeks: number; prior_weeks: number; shells: CovRate[]; looks: CovRate[] };
  positions: CovPosition[]; allowed_share: CovShare; receivers: CovReceiver[];
  by_coverage?: { key: string; att: number; epa: number; raw_epa: number | null; shares: CovShare; defense_weight: number }[];
  compare?: { usual: CovShare; expected: CovShare; usual_epa: number; expected_epa: number };
};
export type Coverage = { gid: string; season: number; week: number; away: string; home: string; fpds_weeks: number; sides: [CovSide, CovSide];
  params: { k_weeks: number; shrink_routes: number; k_qb_share: number; k_qb_epa: number; min_routes: number } };
