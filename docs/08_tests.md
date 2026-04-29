# Tests

Stratégie de tests à deux niveaux : Python (automatisés via pytest) et firmware (scénarios manuels via Serial Monitor en attendant l'automation).

## Tests Python — `pytest`

> **Référence détaillée** : [tests/README.md](../tests/README.md) — découpage par classe de test, statistiques par module.

### Lancer les tests

```bash
pytest                                          # tous (90 tests, ~3,5 min)
pytest --cov=quoridor_engine --cov-report=html  # avec couverture HTML dans htmlcov/
pytest tests/test_moves.py                      # un fichier précis
pytest tests/test_ai.py::TestPathfinding -v     # une classe de test
```

### Couverture actuelle

| Module | Couverture |
|---|---|
| `quoridor_engine/core.py` | 75 % |
| `quoridor_engine/ai.py` | 92 % |
| **Total** | **82 %** |

### Fichiers de tests

| Fichier | Tests | Couvre |
|---|---|---|
| [tests/test_core.py](../tests/test_core.py) | 10 | Structures de données, immutabilité de `GameState`, constantes |
| [tests/test_moves.py](../tests/test_moves.py) | 14 | Déplacements, sauts, blocage par murs |
| [tests/test_walls.py](../tests/test_walls.py) | 21 | Pose, validation, blocage de chemin (BFS) |
| [tests/test_game.py](../tests/test_game.py) | 20 | Orchestration `QuoridorGame`, undo, fin de partie |
| [tests/test_ai.py](../tests/test_ai.py) | 25 | Minimax, alpha-bêta, cache, performance, cas limites |

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
