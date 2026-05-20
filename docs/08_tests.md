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

### Tests hardware

Aucun test hardware automatisé n'est enregistré aujourd'hui. Un harnais de tests d'intégration sur DevKit ESP32 (handshake `PING`/`PONG`, levée de murs `WALL`, etc.) sera ajouté à la phase 5, en cohérence avec le protocole texte stable.

## Marqueur `devkit`

Le marqueur pytest `devkit` reste défini dans `pyproject.toml` pour les futurs tests hardware. Sans test enregistré sous ce marqueur, `pytest -m "not devkit"` et `pytest` produisent le même résultat aujourd'hui.

## Couverture cible

- Globale : ~80 %.
- `quoridor_engine/ai.py` : ~90 %+.
- `quoridor_engine/core.py` : ~75 %+.

La couverture inférieure de `core.py` vient des branches d'erreur (cas extrêmes des sauts par-dessus un pion adverse)
difficiles à mesurer en couverture pure.

## Bonnes pratiques

- **Indépendance** : chaque test crée son propre état initial. Pas de fixtures globales mutables.
- **Docstrings claires** : décrire le scénario testé en une phrase.
- **Regroupement par classe `TestX`** : pour la lisibilité du rapport pytest.
- **Cas nominal + cas d'erreur** : couvrir au minimum la voie heureuse et un cas qui doit échouer.

## Tests hardware manuels (en attendant le harnais automatisé)

Avec un DevKit ESP32 branché en USB-C, on peut valider à la main :

- Ouvrir un moniteur série (`pio device monitor -b 115200`).
- Taper `PING`, attendre `PONG`.
- Taper `LIMITS`, vérifier la lecture des fins de course X et Y.
- Taper `STATUS`, vérifier la position courante et l'état des drivers.

En cas de souci :

- Vérifier que le sketch est bien flashé (`pio run -t upload`).
- Vérifier le port série (`ls /dev/tty.usbserial-* /dev/tty.usbmodem*`).
- S'assurer qu'aucune autre application ne tient le port (fermer `pio device monitor` avant pyserial).
