# nflfastR PR 618 run

Recomputes `ep` and `epa` with the real code of [nflfastR PR 618](https://github.com/nflverse/nflfastR/pull/618) on a season of the local play-by-play.
R 4.6 is installed per-user at `C:\Users\travi\R\R-4.6.2`; packages live in `data/cache/rlib` (gitignored). `install.R` installs the PR build and `fastrmodels`.

    .venv/Scripts/python.exe scripts/ep_pr618.py 2026

Writes `data/cache/ep_pr618_<season>.csv` (game_id, play_id, old ep/epa, PR ep_pr/epa_pr). The nflverse columns are not the ones the package builds itself, so `run.R`
derives the model inputs with the package's own `make_model_mutations()` and a few scoring flags, and blanks are read as NA.
Descriptive only; not part of any freeze or forecast.
