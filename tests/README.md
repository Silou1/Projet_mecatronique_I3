# Tests — Quoridor mécatronique

**278 tests** au total (8 marqués `@pytest.mark.devkit` skip par défaut sans hardware ESP32).

> Documentation maître : [docs/08_tests.md](../docs/08_tests.md).

## Lancer les tests

```bash
pytest -m "not devkit"                          # tous (278 tests, ~8 s sur Mac)
pytest --cov=quoridor_engine --cov-report=html  # avec couverture HTML
pytest tests/test_moves.py                      # un fichier précis
pytest tests/test_ai.py::TestPathfinding -v     # une classe de test
pytest -m devkit                                # tests hardware (DevKit ESP32 requis)
```

## Structure

```
tests/
├── conftest.py                  Fixtures globales (MockSerial, MockClock)
│
├── test_core.py                 GameState, NackCode, InvalidMoveError, structures
├── test_moves.py                Déplacements, sauts, blocage par murs
├── test_walls.py                Pose, validation, BFS, double-clic
├── test_game.py                 Orchestration QuoridorGame, undo, fin de partie
├── test_ai.py                   Minimax + alpha-bêta + cache, performance
│
├── test_uart_client.py          Protocole UART Plan 2 (framing, CRC-16, retry)
├── test_game_session.py         Boucle P9 RPi↔ESP32 (handshake, reconnexion)
├── test_main_cli.py             CLI args, mode console vs --mode plateau
│
├── webapp/
│   ├── test_schemas.py          Pydantic payloads API
│   ├── test_service.py          QuoridorService, threading, IA tick
│   ├── test_uart_bridge.py      Bridge UART (mocks)
│   └── test_api.py              TestClient FastAPI, 9 routes HTTP
│
└── integration/
    └── test_uart_devkit.py      Hardware (marker devkit, skip par défaut)
```

## Marqueurs custom

| Marqueur | Quand l'utiliser | Comportement par défaut |
|---|---|---|
| `@pytest.mark.devkit` | Test nécessite un ESP32 DevKit branché en USB | Skip si `pytest -m "not devkit"` |

Définis dans `pyproject.toml`.

## Bonnes pratiques en place

- Tests indépendants (pas d'état partagé entre tests)
- Docstrings sur chaque test
- Tests groupés par classe selon le concept
- Couverture des cas nominaux **et** des erreurs
- Fixtures `MockSerial` / `MockClock` pour isoler des dépendances temps/IO

## Couverture

Voir [docs/08_tests.md](../docs/08_tests.md) pour les chiffres à jour par module.
Rapport HTML local : `pytest --cov=quoridor_engine --cov-report=html` puis ouvrir `htmlcov/index.html`.
