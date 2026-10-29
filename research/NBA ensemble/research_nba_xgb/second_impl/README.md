# Second implementation of the availability features

Run from the repo root:

    .venv\Scripts\python.exe research_nba_xgb\second_impl\second_features.py

Output: research_nba_xgb/second_impl/second_features.parquet (game_id, avail_value_diff, full_value_diff, avail_effect_diff, missing_min_diff).
Runtime: about 3 minutes (about 150 s for the 256 weekly ridge refits).
Games produced: 4919 (seasons 2023 to 2026). 56 of 7228 play-by-play games were dropped in stint construction.
See AMBIGUITIES.md for decisions taken where the spec was open.
