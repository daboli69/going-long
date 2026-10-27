# NBA research source and reports

This download contains all implemented NBA source modules, tests, protocols, reports and the proposed next research task. It does not contain the roughly 250 MB of raw-data caches or frozen full simulation samples. Source URLs/hashes and report receipts are retained.

V1 remains the retained research model. The FGA candidate did not establish predictive improvement. The participation/minutes task is proposed work only. No live ownership estimate or betting accuracy claim is included.

Extract the ZIP completely and run Install-NBA-Ensemble.cmd. The installer targets C:\Users\travi\OneDrive\Documents\ChatGPT\GOING\research\NBA ensemble. Existing differing files are preserved: a complete versioned snapshot is installed inside updates/<version>. Use the installed_root printed in the receipt.

Your existing app.py / nba_lab / START_NBA application has not been integrated by this transfer; its source must be inspected for that work. This is a source/report transfer, not a claim that START_NBA now uses these modules.

After installation, Python 3.12 commands from the installed_root:

python -m pip install -r requirements.txt
python -m unittest tests.test_nba_winners tests.test_king_court tests.test_king_court_diagnostics -q

48 tests passed before transfer. Raw-history replay commands need their separately retained/downloaded input caches.
