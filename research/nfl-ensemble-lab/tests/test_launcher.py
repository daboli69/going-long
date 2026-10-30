"""Offline launcher checks: no refreshes, fits, browser or external actions."""
from pathlib import Path
from unittest.mock import patch

from lab import launcher


def test_opening_menu_and_invalid_input_start_nothing(capsys):
    with patch('builtins.input', side_effect=['invalid', 'a', 'b', 'q']), patch.object(launcher, 'run_action') as run:
        assert launcher.menu() == 0
        run.assert_not_called()
    assert 'Choose one of the listed options' in capsys.readouterr().out


def test_enter_opens_dashboard_and_returns_to_menu():
    with patch('builtins.input', side_effect=['', 'q']), patch.object(launcher, 'run_action', return_value=0) as run:
        assert launcher.menu() == 0
        run.assert_called_once_with('dashboard')


def test_failed_weekly_action_does_not_fall_through(capsys):
    with patch('builtins.input', side_effect=['3', 'q']), patch.object(launcher, 'run_action', return_value=7) as run:
        assert launcher.menu() == 0
        run.assert_called_once_with('weekly')
    assert 'Stopped with exit code 7' in capsys.readouterr().out


def test_every_action_exists_and_uses_fixed_arguments():
    for name, (_, target, args) in launcher.ACTIONS.items():
        assert target.is_file(), name
        with patch.object(launcher.subprocess, 'call', return_value=0) as call:
            assert launcher.run_action(name) == 0
            call.assert_called_once_with(['cmd.exe', '/d', '/c', 'call', str(target), *args], cwd=launcher.ROOT)


def test_specialists_resolve_lab_root_and_internal_call():
    scripts = list(launcher.TOOLS.glob('*.bat'))
    assert len(scripts) == 17
    for script in scripts:
        content = script.read_text()
        assert 'cd /d "%~dp0..\\.."' in content, script.name
    assert 'call "%~dp0run_manual_fpds.bat"' in (launcher.TOOLS / 'run_fpds_research.bat').read_text()
    assert {p.name for p in launcher.ROOT.glob('*.bat')} == {'START_HERE.bat', 'launch_lab.bat', 'refresh_data.bat'}


def test_real_windows_batch_dispatch_with_spaces(tmp_path):
    # Exercise cmd quoting / argument forwarding against a harmless synthetic batch.
    import os
    if os.name != 'nt':
        return
    folder = tmp_path / 'folder with spaces'
    folder.mkdir()
    script = folder / 'test action.bat'
    output = folder / 'result.txt'
    script.write_text('@echo off\necho %~1>"%~dp0result.txt"\nexit /b 7\n')
    with patch.dict(launcher.ACTIONS, {'fixture': ('Fixture', script, ('hello',))}):
        assert launcher.run_action('fixture') == 7
    assert output.read_text().strip() == 'hello'


def test_unknown_command_is_rejected_without_shell():
    with patch('sys.argv', ['launcher', 'project & unwanted']), patch.object(launcher, 'run_action') as run:
        assert launcher.main() == 2
        run.assert_not_called()
