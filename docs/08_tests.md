# Tests

La suite de tests utilise pytest. Le marqueur `devkit` isole les tests qui nécessitent un ESP32 physiquement branché.

## Lancer la suite de tests

```bash
# Tous les tests sauf ceux qui nécessitent un ESP32 branché (recommandé en dev)
pytest -m "not devkit"

# Tous les tests, y compris hardware
pytest

# Couverture avec rapport HTML
pytest --cov=quoridor_engine --cov=webapp --cov-report=html

# Un fichier précis
pytest tests/test_moves.py -v

# Un test précis
pytest tests/test_moves.py::TestPawnMovement::test_basic_move
```

Le rapport HTML est généré dans `htmlcov/index.html`.

## Structure des tests

### Tests du moteur de jeu (`tests/`)

| Fichier | Couverture |
|---|---|
| `test_core.py` | Structures de base : `GameState`, constantes, création |
| `test_moves.py` | Validation des déplacements de pion (orthogonaux, sauts) |
| `test_walls.py` | Validation des murs (chevauchement, blocage de chemin) |
| `test_game.py` | Scénarios de partie complets, undo |
| `test_ai.py` | Comportement de l'IA, déterminisme, mate-in-N, performance |
| `test_main_cli.py` | CLI console (smoke test du parser de commandes) |

### Tests de la webapp (`tests/webapp/`)

| Fichier | Couverture |
|---|---|
| `test_api.py` | Routes FastAPI (HTTP) |
| `test_service.py` | Couche service, intégration moteur + transport |
| `test_uart_bridge.py` | Transport série avec `serial.Serial` mocké |
| `test_schemas.py` | Modèles Pydantic |

### Tests hardware (`tests/integration/`)

| Fichier | Couverture |
|---|---|
| `test_uart_devkit.py` | Tests d'intégration avec ESP32 physiquement branché (marqueur `devkit`) |

## Marqueur `devkit`

Les tests dans `tests/integration/test_uart_devkit.py` portent le marqueur pytest `devkit`. Ils nécessitent un ESP32-WROOM réellement branché en USB-C au Mac.

Sans ce matériel, ils sont ignorés. Par défaut, `pytest -m "not devkit"` est recommandé en développement sans plateau.

Ils valident que les commandes de base (`PING`, lecture des `LIMITS`, etc.) fonctionnent sur le canal série réel.

## Couverture cible

- Globale : ~80 %.
- `quoridor_engine/ai.py` : ~90 %+.
- `quoridor_engine/core.py` : ~75 %+.

La couverture inférieure de `core.py` vient des branches d'erreur (cas extrêmes des sauts par-dessus un pion adverse)
qui sont couvertes par les tests d'intégration mais difficiles à mesurer en couverture pure.

## Bonnes pratiques

- **Indépendance** : chaque test crée son propre état initial. Pas de fixtures globales mutables.
- **Docstrings claires** : décrire le scénario testé en une phrase.
- **Regroupement par classe `TestX`** : pour la lisibilité du rapport pytest.
- **Cas nominal + cas d'erreur** : couvrir au minimum la voie heureuse et un cas qui doit échouer.

## Tests hardware manuels (récap)

Avec un DevKit ESP32 branché en USB-C :

```bash
pytest -m devkit
```

Doit valider :

- Handshake `PING` / `PONG`.
- Lecture des fins de course (`LIMITS`).
- Que le moniteur série répond aux commandes envoyées par pyserial.

Si ces tests échouent, vérifier :

- Le sketch est bien flashé (`pio run -t upload`).
- Le port série est bien `/dev/tty.usbserial-*` ou `/dev/tty.usbmodem*`.
- Aucune autre application n'utilise le port (fermer `pio device monitor` avant de lancer pytest).
