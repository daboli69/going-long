# Going Up: October 28 player-points research

[Download the complete research and Claude handoff ZIP (10.0 MB)](https://github.com/daboli69/going-long/raw/refs/heads/nba-research-transfer-2026-10-27/Going-Up-NBA-Points-Research-2026-10-28.zip)

[Read the research report](GOING_UP_REPORT.md) · [Read the Claude handoff](GOING_UP_HANDOFF.md)

The overall verdict is **Inconclusive: insufficient reliable evidence**. The candidate improved retrospective CRPS against a historical baseline, but did not establish improvement over the unseen local model. The report retains clustered uncertainty, missing-data limits and mixed calibration findings.

1. Download the ZIP and use **Extract All** into a separate folder.
2. Give Claude the extracted folder and GOING_UP_HANDOFF.md, together with access to your existing local NBA project.
3. Have Claude read the handoff and run verify_bundle.py before integration. The package contains code, safe derived inputs, forecast PMFs, outcomes, protocols, tests and reproduction scripts.
4. Preserve the existing app and earlier installed snapshot. This is research, with no automatic app integration or production replacement.

Recorded checks: 14 new tests plus 48 original tests; 56 protected original files unchanged; independent CRPS arithmetic verified for 13,281 model forecasts. There were 95 assessment games and 2,322 scored player-games. Raw vendor caches and the local PC application are not included.

ZIP SHA256:

~~~text
af8ded87daa3dcc14a2da408755b4217713b697508ae3cc80941e420460bbc87
~~~

Payload: 116 files including the manifest. Manifest SHA256:

~~~text
e58a1e976ea19272ee0002fa80e3649c36b0ee1b6b16f493d6e11d9daae8c663
~~~

This remains a download-only transfer branch. **Do not merge the whole branch into the application.** Prior transfer artifacts are unchanged.
