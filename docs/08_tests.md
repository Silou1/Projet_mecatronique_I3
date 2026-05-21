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
| `test_api.py` | Routes FastAPI principales (HTTP) |
| `test_api_status.py` | Route `/api/status` (état transport) |
| `test_api_transport_switch.py` | Bascule transport à chaud |
| `test_service.py` | Couche service, intégration moteur + transport mocké |
| `test_plateau_bridge.py` | `PlateauBridge` : heartbeat, lock TX, reconnexion |
| `test_transport_abstract.py` | Contrat de l'interface `Transport` |
| `test_transport_factory.py` | Factory `make_transport()` selon `QUORIDOR_TRANSPORT` |
| `test_transport_null.py` | `NullTransport` (no-ops) |
| `test_transport_serial.py` | `SerialTransport` avec `serial.Serial` mocké |
| `test_transport_wifi.py` | `WiFiTransport` avec socket mocké |
| `test_schemas.py` | Modèles Pydantic |
| `test_status_schemas.py` | Schémas de réponse `/api/status` |

### Tests hardware (`tests/devkit/`)

Tests qui nécessitent un ESP32 physiquement branché. Deux marqueurs
pytest pour distinguer le canal :

- **`devkit_serial`** : ESP32 connecté en USB-C. Couvre handshake
  `PING`/`PONG`, lecture `LIMITS`, commande `WALL`, parseur d'erreurs.
- **`devkit_wifi`** : ESP32 reachable via Wi-Fi AP `Quoridor-ESP32`. La
  fixture `wifi_fixture` automatise la bascule réseau Mac via
  [`tools/wifi_switch.py`](../tools/wifi_switch.py). Couvre handshake
  Wi-Fi, politique "dernier client gagne", coexistence USB + Wi-Fi.

```bash
pytest -m devkit_serial      # ESP32 en USB
pytest -m devkit_wifi        # ESP32 en Wi-Fi (bascule auto du Mac)
```

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
