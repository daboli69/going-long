"""Production steps for King of the End Zone v2.

    python scripts/kz2_freeze.py refit [WEEK]   refit the tail model with history before WEEK (default: the current week); saved as a production fit
    python scripts/kz2_freeze.py freeze [GID..] save a hashed, write-once forecast for each game still to play this week (or the games named)
    python scripts/kz2_freeze.py score          score every frozen forecast whose game is final; writes data/kingzone/scores.json

Frozen forecasts live in data/kingzone/frozen with a ledger of hashes. A forecast saved after kickoff is flagged and left out of the score summary.
"""
from __future__ import annotations

import json
import pickle
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lab import gamecenter_data as D  # noqa: E402
from lab import kz2 as K  # noqa: E402
from lab import kz2_board as B  # noqa: E402


def current_week() -> int:
    g = D.games_table()
    g = g[(g["season"] == D.SEASON) & (g["game_type"] == "REG")]
    open_ = g[~g["completed"].astype(bool)]
    return int(open_["week"].min()) if len(open_) else int(g["week"].max())


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "refit":
        week = int(sys.argv[2]) if len(sys.argv) > 2 else current_week()
        B.FITS.mkdir(parents=True, exist_ok=True)
        f = K.fit_tail(D.SEASON, week)
        (B.FITS / f"prod_{D.SEASON}_{week:02d}.pkl").write_bytes(pickle.dumps(f))
        print("fit", D.SEASON, week, f["n_units"], f["n_exceed"], round(f["seconds"]), "rhat", f["rhat_max"])
    elif cmd == "freeze":
        gids = sys.argv[2:]
        if not gids:
            g = D.games_table()
            w = current_week()
            gids = list(g[(g["season"] == D.SEASON) & (g["week"] == w) & (g["game_type"] == "REG") & ~g["completed"].astype(bool)]["game_id"])
        for gid in gids:
            rec = B.freeze(gid)
            print(gid, rec["frozen_at"], "before kickoff" if rec["before_kickoff"] else "AFTER KICKOFF", rec["sha256"][:12])
    elif cmd == "score":
        rows = B.score_frozen()
        good = [r for r in rows if r.get("before_kickoff")]
        summary = {"scored": len(good), "mean_log_score": float(np.mean([r["log_score"] for r in good])) if good else None,
                   "top_pick_hits": int(sum(r["top_pick_won"] for r in good)), "games": rows}
        (ROOT / "data" / "kingzone" / "scores.json").write_text(json.dumps(summary, indent=1))
        print(json.dumps({k: v for k, v in summary.items() if k != "games"}, indent=1))
        for r in rows:
            print(r)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
