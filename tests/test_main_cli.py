"""Tests CLI pour `python main.py` (mode console uniquement)."""

import subprocess
import sys
from pathlib import Path

import pytest

import main


ROOT = Path(__file__).resolve().parent.parent


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, str(ROOT / "main.py"), *args],
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_help_lists_expected_flags():
    """`main.py --help` mentionne --difficulty et --debug, pas de --mode/--port."""
    result = _run_cli("--help")
    assert result.returncode == 0
    out = result.stdout.lower()
    assert "--difficulty" in out
    assert "--debug" in out
    assert "--mode" not in out
    assert "--port" not in out


def test_parse_args_no_flags():
    """parse_args() retourne un Namespace avec difficulty=None et debug=False par défaut."""
    sys.argv = ["main.py"]
    args = main.parse_args()
    assert args.difficulty is None
    assert args.debug is False


def test_parse_args_difficulty_facile():
    """--difficulty facile doit être accepté."""
    sys.argv = ["main.py", "--difficulty", "facile"]
    args = main.parse_args()
    assert args.difficulty == "facile"


def test_parse_args_difficulty_invalid_exits_2():
    """--difficulty avec une valeur invalide doit échouer (exit code 2)."""
    result = _run_cli("--difficulty", "invalide")
    assert result.returncode == 2


def test_parse_args_debug_flag():
    """--debug active le mode verbeux."""
    sys.argv = ["main.py", "--debug"]
    args = main.parse_args()
    assert args.debug is True
