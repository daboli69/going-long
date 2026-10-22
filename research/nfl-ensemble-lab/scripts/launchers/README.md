# Specialist launchers

For normal use, open **`START_HERE.bat` in the lab folder**. These scripts remain available for specific workflows; they resolve the lab folder automatically even when opened here. Existing arguments still work.

| Group | Scripts | Purpose |
| --- | --- | --- |
| FPDS | `run_manual_fpds.bat`, `run_weekly_fpds.bat`, `import_fpds.bat` | Manual projections/comparisons, frozen weekly refresh, import/audit. |
| Injury context | `update_fpds_injuries.bat` | Import current Week folder injury statuses without changing forecasts. |
| Earlier weekly tools | `run_weekly_predictions.bat`, `run_week_projections.bat` | Saved winner models and Phase 10 shadow pipeline. |
| Research | `run_fpds_research.bat`, `run_fpds_improvements.bat`, `run_fpds_followups.bat`, `run_fpds_simulation.bat`, `run_overnight_research.bat`, `run_research.bat`, `stop_research.bat` | Specialized studies and controls. Several start lengthy work when opened; use explicit `status` commands where supported to inspect saved work. |
| Setup | `setup_windows.bat` | Install/repair the local environment. |
| Maintenance | `release_lab.bat`, `publish_going.bat` | Existing release/publication controls; deliberately excluded from the start menu. Retained for reference. |

From the lab folder, prefix commands with `scripts\launchers\`, for example:

```bat
scripts\launchers\run_manual_fpds.bat project --week 8 --scope all
scripts\launchers\run_fpds_simulation.bat status
```

`launch_lab.bat` and `refresh_data.bat` remain in the lab folder so the dashboard shortcut and existing scheduled refresh path still work. No scheduled task is installed or changed by this organization.
