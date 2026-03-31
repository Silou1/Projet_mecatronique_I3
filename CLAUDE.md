# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Quoridor board game engine in Python (ICAM mechatronics project, Year 3). 6x6 board, 2 players, 6 walls each. Dual-processor architecture:
- **Raspberry Pi 3/4** : runs the AI and game engine (Python)
- **ESP32-WROVER-Dev** (Freenove v1.6) : controls all hardware via Arduino C++ (motors, LEDs, buttons, servo)
- Communication: UART TX/RX (serial, direct cable)
- PCB designed on EasyEDA by jeanrdc -- see `Schéma_PCB/REFERENCE_PCB.md` for full pin mapping and known issues

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
