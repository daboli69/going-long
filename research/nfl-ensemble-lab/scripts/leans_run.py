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
    show = {k: res[k] for k in ("recal_compare", "universe_rows", "executable_rows", "placebo", "pass")}
    show["models"] = {m: {md: {k: v for k, v in r.items() if k != "note"} for md, r in mm.items()} for m, mm in res["models"].items()}
    show["subgroups"] = {k: {a: v.get(a) for a in ("n", "realized_edge", "p_holm", "claim")} for k, v in res["subgroups"].items()}
    print(json.dumps(show, indent=1, default=float))
