# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Quoridor board game engine in Python (ICAM mechatronics project, Year 3). 6x6 board, 2 players, 6 walls each. Dual-processor architecture:
- **Raspberry Pi 3/4** : runs the AI and game engine (Python)
- **ESP32-WROOM** (Freenove) : controls all hardware via Arduino C++ (motors, servo, end-stops). Module = WROOM (no PSRAM, GPIO16/17 available).
- **Webapp démo** (`webapp/`) : interface navigateur servie par FastAPI sur RPi (port 8000), frontend SVG vanilla. Mode autonome (moteur Python + IA) ou hybride avec plateau physique via UART (fallback gracieux si ESP32 non connecté). Voir [webapp/README.md](webapp/README.md).
- Communication: UART0 TX/RX (serial, direct cable, 115200 bauds)
- **Hardware state (2026-05-20)** : PCB v2 **abandonnée** (erreur de composant et conflits pins, détails dans le postmortem). Pivot vers **breadboard** avec les composants conservés (2× L298N, 2× steppers NEMA17, servo, 2× fins de course, alim 12V). Bring-up **validé le 2026-05-20** : CoreXY + servo + capteurs + matrices murs (18/60 positions mesurées). Sketch de production : [firmware/src/bringup_l298n_complet.cpp](firmware/src/bringup_l298n_complet.cpp). Détails : [hardware/README.md](hardware/README.md), postmortem dans [hardware/archive/pcb-v2-2026-04-28-ABANDONNEE/POSTMORTEM.md](hardware/archive/pcb-v2-2026-04-28-ABANDONNEE/POSTMORTEM.md), spec breadboard dans `docs/superpowers/specs/2026-05-19-bringup-breadboard-design.md`, validation dans [docs/superpowers/specs/2026-05-20-bringup-breadboard-validation.md](docs/superpowers/specs/2026-05-20-bringup-breadboard-validation.md).
- **ESP32 datasheet questions** : query the dedicated NotebookLM `ESP32 Development Board Pinout Reference Map` (id `7d0bccd1-df3f-456d-99a0-1192766043ba`) via the `notebooklm-mcp` MCP -- it is the source of truth for GPIO, peripherals, strapping pins, ADC, RTC, PWM. Do NOT rely on third-party board pinouts (Freenove DevKitC) which may diverge from the SoC datasheet.

## Commands

```bash
# Run the game
python main.py

# Run all tests (~3.5 min)
pytest

# Run tests with coverage
pytest --cov=quoridor_engine --cov-report=html

# Run a specific test file
pytest tests/test_moves.py

# Run a single test
pytest tests/test_moves.py::TestClassName::test_name -v
```

## Architecture

```
main.py                  → Console UI (display, input parsing, game loop)
quoridor_engine/
  __init__.py            → Public exports: QuoridorGame, GameState, InvalidMoveError, AI
  core.py                → Game logic: GameState (frozen dataclass), rules, move validation, BFS pathfinding
  ai.py                  → AI: Minimax + Alpha-Beta pruning, heuristic evaluation, transposition table
tests/
  test_core.py           → GameState creation, basic structures
  test_moves.py          → Pawn movement validation
  test_walls.py          → Wall placement validation
  test_game.py           → Full game scenarios
  test_ai.py             → AI behavior and performance
```

**Data flow:** `main.py` (UI) calls `QuoridorGame` (facade in `core.py`) which manages `GameState` (immutable) and delegates to module-level functions (`move_pawn`, `place_wall`, `get_possible_pawn_moves`, `_path_exists`, etc.). AI reads `GameState` via `game.get_current_state()`.

**Key design decisions:**
- `GameState` is a frozen dataclass — every move returns a new state (enables undo via history list and AI tree search)
- Walls stored as `FrozenSet[Wall]` for O(1) lookup and hashability (used by AI transposition table)
- `QuoridorGame` is the facade class; game logic lives in module-level functions in `core.py`
- Move format: `('deplacement', (row, col))` or `('mur', ('h'|'v', row, col, 2))`
- Players: `'j1'` (starts row 5, goes to row 0) and `'j2'` (starts row 0, goes to row 5)
- Board coordinates: (0,0) top-left to (5,5) bottom-right

## Code Style

- Language: French for variable names, comments, and docstrings. English for class names.
- Naming: `snake_case` for variables/functions, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants
- PEP 8, 4-space indentation, max 100 chars per line
- Type hints used throughout
