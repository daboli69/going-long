# Local all-model FPDS session — 2026-10-21

Started 09:22 Eastern. Explicitly authorized local run; shadow only.

- Session: `20261021T132259Z`; first forecast job: `5ef33f32d6ed4d2b98372932728fb416`.
- Order: fresh-input week 7 forecasts, then fixed matched 2022–2024 development comparison if time permits.
- Models: six game families for home winner/margin/total; four prop families for passing yards/TDs, receptions, receiving/rushing yards, anytime TD; equal ensembles and derived offensive first TD. NFL-only and NFL+FPDS arms both run.
- Inputs: all audited eligible history from 2021 through available completed-week cutoff; authoritative full-history FPDS folder, verified NFL sources. No unaudited whole-PC file discovery.
- Simulations: 10,000 draws, seed17. Existing frozen parameters; no new search, holdout pass or promotion.
- Timing: request completed-block checkpoint at15:20 Eastern; terminate only owned worker processes at15:30 Eastern (19:30 UTC). Current fit may be discarded at the hard stop; completed blocks remain resumable.
- Forecast archives, private logs, checkpoints and session STATUS.json stay under ignored `data/cache/fpds/amendment6/manual/`. No raw or derived subscription rows are published.
- Process supervision: hidden low-priority local Python, cores minus two; no Windows scheduled task, cloud compute or external notification.
- Startup verified: supervisor alive and projection worker preparing inputs. Future results are not yet known.
- Checks: 33 targeted tests passed; prior full suite382 passed/one existing skip.

View progress/results: `launch_lab.bat` → Research → FPDS Research → refresh status. Keep the PC powered and awake. If fixed work completes early or a failure occurs, the supervisor stops rather than generating redundant trials.
