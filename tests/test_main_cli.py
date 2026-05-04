"""Tests pour le parsing CLI de main.py (spec P9 §3.4)."""

import subprocess
import sys


def test_help_lists_all_flags():
    """python main.py --help affiche les flags P9."""
    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    out = result.stdout
    assert "--mode" in out
    assert "--port" in out
    assert "--difficulty" in out
    assert "--debug" in out


def test_plateau_mode_without_port_exits_2():
    """--mode plateau sans --port -> exit 2 avec message clair."""
    result = subprocess.run(
        [sys.executable, "main.py", "--mode", "plateau"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "--port" in result.stderr.lower() or "--port" in result.stdout.lower()


def test_parse_args_console_default(monkeypatch):
    """Sans argument, args.mode == 'console'."""
    monkeypatch.setattr(sys, "argv", ["main.py"])
    from main import parse_args

    args = parse_args()

    assert args.mode == "console"
    assert args.port is None
    assert args.debug is False


def test_parse_args_plateau_with_port(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["main.py", "--mode", "plateau", "--port", "/dev/null", "--debug"],
    )
    from main import parse_args

    args = parse_args()

    assert args.mode == "plateau"
    assert args.port == "/dev/null"
    assert args.debug is True
