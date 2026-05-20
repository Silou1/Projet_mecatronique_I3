# 05 — Webapp de démo Quoridor

## Vue d'ensemble

La webapp est servie par **FastAPI** (Python 3.12) sur `localhost:8000`. Elle tourne sur le
**Mac de développement** et expose l'interface de jeu dans n'importe quel navigateur
(iPhone Safari via Wi-Fi local est le cas d'usage principal pour la démo).

- **Frontend** : SVG vanilla, zéro framework JS, zéro étape de build.
- **Transport backend** : HTTP polling toutes les 500 ms (pas de WebSocket — fiabilité prioritaire).
- **Deux modes** :
  - **Mode autonome** — l'ESP32 n'est pas connecté ; le jeu est entièrement logiciel.
  - **Mode hybride** — l'ESP32 est branché en USB-série ; chaque mur posé à l'écran est
    levé physiquement sur le plateau.

Lancer le serveur :

```bash
uv pip install fastapi "uvicorn[standard]" pyserial httpx
python -m webapp.server
# → http://localhost:8000
```

---

## Modules

### `webapp/server.py`

Point d'entrée FastAPI + uvicorn. Déclare les routes HTTP et sert le frontend statique
(`webapp/static/` — HTML, CSS, JS).

Principales routes :

| Méthode | Route | Rôle |
|---------|-------|------|
| `GET` | `/` | Sert le fichier HTML principal |
| `POST` | `/api/new_game` | Démarre une nouvelle partie |
| `POST` | `/api/move` | Soumet un coup (déplacement ou mur) |
| `GET` | `/api/state` | Retourne l'état courant de la partie |
| `POST` | `/api/reset` | Remet le plateau à zéro |

Le module instancie `QuoridorService` au démarrage, tente d'initialiser `UartBridge`
(mode hybride), et passe l'éventuel bridge au service.

---

### `webapp/service.py`

Couche service entre l'API et le moteur de jeu. Implémentée comme un singleton
thread-safe (`QuoridorService`).

Responsabilités :

- Détient l'état courant de la partie (`GameState`, immuable — chaque coup produit un nouvel état).
- Gère les modes de partie : `human_vs_ai`, `ai_vs_ai`, `human_vs_human`.
- Instancie et pilote les instances `AI` (Minimax + Alpha-Beta, table de transposition).
- Lance un thread daemon (`tick`) pour les coups IA en arrière-plan, avec délai configurable
  (`lent` / `normal` / `rapide`).
- Délègue vers `UartBridge.forward_move(move)` quand un mur est posé en mode hybride.
- Sérialise l'état pour la route `GET /api/state`.

```python
class QuoridorService:
    def __init__(self, uart_bridge: Optional["UartBridge"] = None): ...
    def new_game(self, mode: str, difficulty: str, plateau_mode: bool) -> None: ...
    def apply_move(self, move: tuple) -> dict: ...
```

---

### `webapp/uart_bridge.py`

Transport USB-série vers l'ESP32. Utilise **pyserial** à 115 200 bauds.

#### Détection automatique du port

Au démarrage, `uart_bridge.init()` scanne les ports disponibles :

- **Mac** : `glob("/dev/cu.usbserial-*")` (driver CP210x / CH340 USB-C)
- **Linux** : `glob("/dev/ttyUSB*")`

La variable d'environnement `QUORIDOR_SERIAL_PORT` peut forcer un port précis.

#### Handshake PING/PONG

Avant d'activer le bridge, le module envoie `PING\n` et attend une ligne contenant `PONG`
dans un délai de 5 s (tentatives toutes les 500 ms). Si aucun `PONG` n'est reçu, `init()`
retourne `None` et la webapp bascule en mode autonome.

#### Envoi des coups

```
WALL <H|V> <row> <col>\n
```

Note : le bridge applique une inversion `H ↔ V` car la convention d'orientation du plateau
physique est inverse de celle du moteur Quoridor (mesurée lors du bring-up).

Les déplacements de pions sont des **no-op** (aucun système physique de pion dans cette version).

#### Politique d'erreur

En cas d'erreur série pendant une partie (timeout, port mort, etc.), `UartBridge.available`
passe à `False` et tous les forwards suivants sont silencieux. Pas de tentative de
reconnexion — la partie continue en mode autonome jusqu'au prochain redémarrage.

#### Commande HOME

`UartBridge.send_home()` envoie `HOME\n` au plateau pour déclencher le homing CoreXY au
début d'une nouvelle partie.

#### Placeholder phase 5 — abstraction `Transport`

À terme, une interface `Transport` unifiée (`send_line` / `read_line`) supportera USB-série
et Wi-Fi mode AP via la même API. Sélection prévue par env var :

```bash
QUORIDOR_TRANSPORT=serial python -m webapp.server  # USB-série (défaut actuel)
QUORIDOR_TRANSPORT=wifi   python -m webapp.server  # Wi-Fi mode AP (phase 5)
```

**Prévu, non implémenté à ce jour.** Seul le mode `serial` existe.

---

### `webapp/schemas.py`

Modèles **Pydantic** des messages échangés entre le frontend et l'API.

Exemples :

- `MoveRequest` — payload de `POST /api/move` (`type`, `orientation`, `row`, `col`)
- `GameStateResponse` — réponse de `GET /api/state` (plateau, scores, statut)
- `NewGameRequest` — paramètres de `POST /api/new_game` (mode, difficulté, plateau_mode)

---

## Modes d'exécution

### Mode autonome (sans ESP32)

La webapp tourne en local sans aucun matériel. Les murs posés à l'écran sont uniquement
visuels. Idéal pour développer le moteur, affiner l'IA, ou préparer une démo sans le plateau.

Activé automatiquement si aucun port série n'est détecté au démarrage.

### Mode hybride (avec plateau physique)

L'ESP32 est connecté au Mac via USB-C. Le mode est détecté automatiquement grâce au
handshake PING/PONG. Quand il est actif, le toggle "Plateau physique" s'affiche dans
l'interface de démo.

---

## Flux d'un coup en mode hybride

```
Frontend                       service.py                uart_bridge.py          ESP32
   |                               |                           |                    |
   |  POST /api/move               |                           |                    |
   |  {type:'mur', ori:'h', ...}   |                           |                    |
   |-----------------------------> |                           |                    |
   |                               | validate (moteur Quoridor)|                    |
   |                               |--[valide]---------------->|                    |
   |                               |                           | WALL V 2 3\n       |
   |                               |                           |-------------------->
   |                               |                           |    WALL OK / ERR   |
   |                               |                           |<--------------------|
   |                               | nouvel état               |                    |
   |  200 OK + état mis à jour     |                           |                    |
   |<------------------------------ |                           |                    |
```

Détail des étapes :

1. Le frontend envoie `POST /api/move` avec `{type: 'mur', orientation: 'h', row: 2, col: 3}`.
2. `service.py` valide le coup via `place_wall(state, player, wall)` du moteur Quoridor.
3. Si valide, `service.py` appelle `uart_bridge.forward_move(move)`.
4. `uart_bridge` envoie `WALL V 2 3\n` (après inversion H↔V) et retourne immédiatement
   (mode fire-and-forget — pas d'attente de réponse bloquante pour ce prototype).
5. `service.py` répond `200 OK` au frontend avec le nouvel état sérialisé.

---

## Frontend

- Rendu SVG inline du plateau 6×6.
- Clic sur une case → déplacement du pion (si coup légal).
- Clic sur une arête inter-cases → pose d'un mur (si coup légal).
- Affichage du joueur courant, compteurs de murs restants, statut de la partie.
- Polling `GET /api/state` toutes les 500 ms pour mettre à jour l'affichage (coups IA inclus).
- **Aucun framework** (React, Vue, etc.) — choix pédagogique pour la lisibilité du code.

---

## Tests

| Fichier | Couverture |
|---------|------------|
| `tests/webapp/test_api.py` | Routes FastAPI (client de test httpx) |
| `tests/webapp/test_service.py` | Couche service, intégration moteur + transport mocké |
| `tests/webapp/test_uart_bridge.py` | Transport série avec `serial.Serial` mocké (pyserial) |
| `tests/webapp/test_schemas.py` | Modèles Pydantic — validation entrées/sorties |

Aucun test ne nécessite un ESP32 physique. Les tests d'intégration matériel se trouvent
dans `tests/integration/`.

```bash
pytest tests/webapp/ -v
# Pas de hardware requis.
```
