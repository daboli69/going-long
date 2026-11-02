"""Run the leans backtest once and save docs/leans_backtest.json plus the lean rows the screen reads."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab import leans as L  # noqa: E402

if __name__ == "__main__":
    res, x = L.backtest()
    (ROOT / "docs" / "leans_backtest.json").write_text(json.dumps(res, indent=1))
    out = ROOT / "data" / "leans"
    out.mkdir(parents=True, exist_ok=True)
    L.rows_for_screen(x).to_parquet(out / "backtest_leans.parquet")
    print(json.dumps({k: res[k] for k in ("model_used", "recal_test", "universe_rows", "leans", "no_lean", "all", "benchmarks", "by_market", "by_size", "by_season")}, indent=1))
