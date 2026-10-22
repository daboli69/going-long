"""One local entry point. Merely opening the menu never starts a job."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "scripts" / "launchers"

# Explicit, fixed argument lists: typed menu responses never become shell code.
ACTIONS = {
    "dashboard": ("Open dashboard", ROOT / "launch_lab.bat", ()),
    "project": ("Create FPDS game + player projections (may take time)", TOOLS / "run_manual_fpds.bat", ("project",)),
    "weekly": ("Weekly FPDS refresh + frozen shadow projections (may take time)", TOOLS / "run_weekly_fpds.bat", ()),
    "import": ("Import + audit downloaded FPDS files", TOOLS / "import_fpds.bat", ()),
    "injuries": ("Update live injury context + optional FPDS CSV; forecasts stay frozen", TOOLS / "update_fpds_injuries.bat", ()),
    "refresh": ("Refresh NFL data", ROOT / "refresh_data.bat", ()),
    "legacy": ("Saved-model weekly winner predictions", TOOLS / "run_weekly_predictions.bat", ()),
    "phase10": ("Phase 10 weekly shadow pipeline", TOOLS / "run_week_projections.bat", ()),
    "prices": ("Refresh FPDS price comparisons only", TOOLS / "run_weekly_fpds.bat", ("--comparisons-only",)),
    "status": ("View saved FPDS job status", TOOLS / "run_manual_fpds.bat", ("status",)),
    "setup": ("Install / repair local environment", TOOLS / "setup_windows.bat", ()),
}


def run_action(name):
    if name in {"reports", "tools"}:
        import os
        path = ROOT / "reports" if name == "reports" else TOOLS
        if not path.is_dir():
            print(f"Folder not available yet: {path}")
            return 1
        os.startfile(str(path))
        return 0
    _, path, args = ACTIONS[name]
    if not path.is_file():
        print(f"Launcher missing: {path}")
        return 1
    return subprocess.call(["cmd.exe", "/d", "/c", "call", str(path), *args], cwd=ROOT)


def menu():
    advanced = False
    while True:
        print("\nNFL ENSEMBLE LAB | Local tools")
        if advanced:
            choices = {"1": "refresh", "2": "legacy", "3": "phase10", "4": "prices", "5": "status", "6": "setup", "7": "tools"}
            print("Advanced tools\n1  Refresh NFL data\n2  Saved-model weekly predictions\n3  Phase 10 weekly pipeline\n4  Price comparisons only\n5  Saved FPDS job status\n6  Setup / repair\n7  Open specialist scripts folder\nB  Back\nQ  Quit")
            print("Specialist scripts include long research and maintenance tools; opening the folder starts nothing.")
        else:
            choices = {"1": "dashboard", "2": "project", "3": "weekly", "4": "import", "5": "reports", "6": "injuries"}
            print("1  Open dashboard [recommended; Enter]\n2  Generate FPDS projections / simulations\n3  Tuesday weekly refresh + projections\n4  Import downloaded FPDS files\n5  Open reports folder\n6  Update this week's injuries only\nA  Advanced tools\nQ  Quit")
            print("Projections are shadow research. Options 2-4 and 6 start local work; the menu itself starts nothing.")
        try:
            answer = input("Choose: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if answer == "q":
            return 0
        if answer == "a" and not advanced:
            advanced = True
            continue
        if answer == "b" and advanced:
            advanced = False
            continue
        if not answer and not advanced:
            answer = "1"
        action = choices.get(answer)
        if action is None:
            print("Choose one of the listed options.")
            continue
        if action in ACTIONS:
            print(f"\n{ACTIONS[action][0]}")
        result = run_action(action)
        if result:
            print(f"Stopped with exit code {result}. Review the message above; no later step was started.")
        elif action == "dashboard":
            print("Dashboard closed. Returning to menu.")
        else:
            print("Finished. Returning to menu.")


def main():
    if len(sys.argv) == 1:
        return menu()
    name = sys.argv[1]
    if len(sys.argv) != 2 or name not in {*ACTIONS, "reports", "tools"}:
        print("Usage: START_HERE.bat [" + " | ".join([*ACTIONS, "reports", "tools"]) + "]")
        return 2
    return run_action(name)


if __name__ == "__main__":
    raise SystemExit(main())
