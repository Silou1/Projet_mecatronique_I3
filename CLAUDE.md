# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Quoridor board game engine in Python (ICAM mechatronics project, Year 3). 6x6 board, 2 players, 6 walls each. Dual-processor architecture:
- **Raspberry Pi 3/4** : runs the AI and game engine (Python)
- **ESP32-WROOM** (Freenove) : controls all hardware via Arduino C++ (motors, LEDs, buttons, servo). Note: PCB schematic incorrectly references WROVER; actual module is WROOM (no PSRAM, GPIO16/17 available)
- Communication: UART TX/RX (serial, direct cable)
- PCB designed on EasyEDA by jeanrdc, ordered 2026-04-28. See [hardware/README.md](hardware/README.md) for the entry point, [hardware/AUDIT_PCB_V2.md](hardware/AUDIT_PCB_V2.md) for the detailed audit, and [hardware/PCB_PCB_mecatronique_2026-04-28.json](hardware/PCB_PCB_mecatronique_2026-04-28.json) for the EasyEDA source. Anomalies flagged in the audit have been validated by Jean against the official ESP32 datasheet; final physical checks happen at first power-up (capacitor polarity, GPIO0 boot behavior, GPIO of pin 27 for LED data). UART2 (GPIO16/17) is NOT available -- consumed by the button matrix; RPi link uses UART0 (shared with USB)
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
