# Tests

Stratégie de tests à deux niveaux : Python (automatisés via pytest) et firmware (scénarios manuels via Serial Monitor en attendant l'automation).

## Tests Python — `pytest`

> **Référence détaillée** : [tests/README.md](../tests/README.md) — découpage par classe de test, statistiques par module.

### Lancer les tests

```bash
pytest -m "not devkit"                          # tous (278 tests, ~8 s sur Mac)
pytest --cov=quoridor_engine --cov-report=html  # avec couverture HTML dans htmlcov/
pytest tests/test_moves.py                      # un fichier précis
pytest tests/test_ai.py::TestPathfinding -v     # une classe de test
pytest -m devkit                                # tests hardware (DevKit ESP32 requis)
```

### Couverture actuelle

| Module | Couverture |
|---|---|
| `quoridor_engine/core.py` | 75 % |
| `quoridor_engine/ai.py` | 92 % |
| **Total** | **82 %** |

### Fichiers de tests

**Moteur de jeu et IA** (Python pur, sans hardware) :

| Fichier | Tests | Couvre |
|---|---|---|
| [tests/test_core.py](../tests/test_core.py) | 22 | Structures, immutabilité `GameState`, constantes, `NackCode`, `InvalidMoveError` |
| [tests/test_moves.py](../tests/test_moves.py) | 14 | Déplacements, sauts, blocage par murs |
| [tests/test_walls.py](../tests/test_walls.py) | 19 | Pose, validation, blocage de chemin (BFS), double-clic |
| [tests/test_game.py](../tests/test_game.py) | 20 | Orchestration `QuoridorGame`, undo, fin de partie |
| [tests/test_ai.py](../tests/test_ai.py) | 25 | Minimax, alpha-bêta, cache, performance, cas limites |

**Intégration RPi ↔ ESP32** (mocks UART, pas de hardware) :

| Fichier | Tests | Couvre |
|---|---|---|
| [tests/test_uart_client.py](../tests/test_uart_client.py) | 102 | Framing Plan 2, CRC-16, séquencement, retry, codes NACK |
| [tests/test_game_session.py](../tests/test_game_session.py) | 20 | Boucle P9 RPi↔ESP32, handshake, reconnexion, undo |
| [tests/test_main_cli.py](../tests/test_main_cli.py) | 4 | Parsing args CLI, mode console vs plateau |

**Webapp** (FastAPI TestClient, sans hardware) :

| Fichier | Tests | Couvre |
|---|---|---|
| [tests/webapp/test_schemas.py](../tests/webapp/test_schemas.py) | 10 | Pydantic API payloads |
| [tests/webapp/test_service.py](../tests/webapp/test_service.py) | 23 | `QuoridorService`, threading, IA tick, transitions |
| [tests/webapp/test_uart_bridge.py](../tests/webapp/test_uart_bridge.py) | 8 | Bridge UART (mocks) |
| [tests/webapp/test_api.py](../tests/webapp/test_api.py) | 11 | TestClient FastAPI, 9 routes HTTP |

**Hardware (DevKit physique requis)** :

| Fichier | Tests | Statut |
|---|---|---|
| [tests/integration/test_uart_devkit.py](../tests/integration/test_uart_devkit.py) | 8 | Marqueur `@pytest.mark.devkit`, skip par défaut |

**Total exécuté en CI/local** : **278 tests** (8 devkit skippés sans hardware).

### Bonnes pratiques en place

- Chaque test est indépendant (pas d'état partagé)
- Docstrings sur chaque test
- Tests groupés par classe selon le concept
- Couverture des cas nominaux **et** des erreurs

## Tests firmware — scénarios manuels

> **Statut** : 🚧 *Non automatisés. Procédure complète dans [firmware/TESTS_PENDING.md](../firmware/TESTS_PENDING.md).*

7 scénarios à exécuter via Serial Monitor (115200 bauds, fin de ligne `LF`) dès que l'ESP32 / PCB est branché :

1. **Boot nominal vers `DEMO`** — reset, ne rien taper, vérifier la séquence
2. **Boot nominal vers `CONNECTED`** — taper `HELLO_ACK` dans les 3 s
3. **Cycle de jeu simulé complet** — `BTN`, `ACK`, `NACK`, `CMD MOVE`
4. **Perte UART** — silence 4 s → transition `ERROR` avec code `UART_LOST`
5. **Escalade timeout intent** — 3 timeouts consécutifs → `ERROR`
6. **Récupération depuis `ERROR`** — taper `RESET` → reboot
7. **Watchdog** — provocation contrôlée (modification non commitée du code), vérifier reboot ~5 s

Si tous les scénarios passent, supprimer [firmware/TESTS_PENDING.md](../firmware/TESTS_PENDING.md) et committer `test(firmware): plan 1 valide en bout-en-bout sur cible`.

### Automation future

Un script Python qui rejoue les scénarios via `pyserial` est envisagé. Voir Phase P10 dans [00_plan_global.md](00_plan_global.md).

## Intégration continue

📋 **Aucune CI configurée actuellement.** Décision : reportée à la fin du projet (les badges du README qui mentionnaient GitHub Actions et Codecov étaient erronés et ont été retirés).

Quand on l'ajoutera, la base sera :

```yaml
# .github/workflows/tests.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
          cache: 'pip'
      - run: pip install -r requirements.txt
      - run: pytest --cov=quoridor_engine
```
