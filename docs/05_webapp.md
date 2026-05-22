# 05 — Webapp de démo Quoridor

## Vue d'ensemble

La webapp est servie par **FastAPI** + **uvicorn** sur `localhost:8000`.
Elle tourne sur le **Mac** et expose l'interface de jeu dans n'importe
quel navigateur connecté au même réseau local. En mode démo, l'iPhone
ouvre Safari sur l'IP du Mac dans le réseau Wi-Fi `Quoridor-ESP32`
hébergé par l'ESP32.

- **Frontend** : SVG inline + JS vanilla. Zéro framework, zéro étape de build.
- **Transport HTTP** : polling `/api/state` toutes les 500 ms (pas de WebSocket — fiabilité prioritaire).
- **Trois modes de transport** vers l'ESP32, pilotés par la variable
  d'environnement `QUORIDOR_TRANSPORT` :

| Valeur | Description |
|---|---|
| `wifi` (défaut) | TCP `192.168.4.1:3333` sur le réseau Wi-Fi AP `Quoridor-ESP32` |
| `serial` | USB-série, port auto-détecté (`/dev/cu.usbserial-*`) |
| `none` | Pas de plateau, jeu 100 % logiciel (mode autonome) |

Bascule à chaud sans redémarrer via `POST /api/transport/switch`.

**Forward au plateau physique : automatique.** Quand le transport ESP32 est
joignable (`/api/status` → `transport.alive=true`), chaque mur posé dans la
webapp est miroité sur le plateau (commande `WALL` → chariot CoreXY + servo).
Pas de toggle UI : le mode plateau suit dynamiquement la disponibilité du
transport — un blip momentané du canal n'affecte que les coups concernés, pas
la partie entière.

Lancer le serveur :

```bash
QUORIDOR_TRANSPORT=wifi   python -m webapp.server   # défaut, mode démo
QUORIDOR_TRANSPORT=serial python -m webapp.server   # mode développement (USB)
QUORIDOR_TRANSPORT=none   python -m webapp.server   # mode autonome
# → http://localhost:8000
```

---

## Modules

### `webapp/server.py`

Point d'entrée FastAPI + uvicorn. Déclare les routes HTTP et sert le
frontend statique (`webapp/static/`). Instancie `QuoridorService` au
démarrage et lui injecte la stack transport (transport → plateau bridge
→ LED renderer).

Routes principales :

| Méthode | Route | Rôle |
|---|---|---|
| `GET` | `/` | Sert le HTML principal |
| `GET` | `/api/state` | Retourne l'état courant (polling 500 ms) |
| `POST` | `/api/new-game` | Démarre une nouvelle partie (mode + difficulté) |
| `POST` | `/api/move` | Soumet un coup (déplacement ou mur) |
| `POST` | `/api/pause`, `/api/resume` | Pause / reprise du tick IA |
| `POST` | `/api/speed` | Modifie la vitesse de réflexion IA (lent/normal/rapide) |
| `POST` | `/api/wall-mode` | Bascule entre mode pion et mode mur (frontend) |
| `POST` | `/api/quit` | Quitte la partie en cours |
| `POST` | `/api/transport/switch` | Bascule `wifi` / `serial` / `none` à chaud |
| `GET` | `/api/qr-code`, `/api/qr-code/url` | QR code SVG vers l'URL webapp pour smartphone |
| `GET` | `/api/status` | Statut du transport (état, dernier ping, erreurs) |

---

### `webapp/service.py` — `QuoridorService`

Couche service entre l'API et le moteur de jeu. Singleton thread-safe.

Responsabilités :

- Détient l'état courant de la partie (`GameState`, immuable — chaque coup
  produit un nouvel état).
- Gère les modes de partie : `human_vs_ai`, `ai_vs_ai`, `human_vs_human`.
- Instancie et pilote les instances `AI` (Minimax + Alpha-Bêta, table de
  transposition).
- Lance un thread daemon (`tick`) pour les coups IA en arrière-plan, avec
  délai configurable (`lent` / `normal` / `rapide`).
- Délègue vers `PlateauBridge.forward_move(move)` quand un mur est posé,
  pour que la pose soit miroitée sur le plateau physique.
- Pilote la mise à jour des LEDs via `LedRenderer.update(state)` après
  chaque mutation.
- Sérialise l'état pour la route `GET /api/state`.

---

### `webapp/transport.py` — abstraction de canal

Interface `Transport` (ABC) avec trois implémentations interchangeables
et une factory pilotée par `QUORIDOR_TRANSPORT`.

| Classe | Canal physique |
|---|---|
| `SerialTransport` | USB-série via **pyserial** (115200 bauds, 8N1) |
| `WiFiTransport` | TCP brut vers `192.168.4.1:3333` (socket Python natif) |
| `NullTransport` | No-op (mode autonome ou plateau absent) |

API commune :

```python
class Transport(ABC):
    def open(self) -> None: ...
    def close(self) -> None: ...
    def write_line(self, line: str) -> None: ...
    def read_line(self, timeout: float | None = None) -> str | None: ...
    @property
    def name(self) -> str: ...
```

`make_transport()` lit `QUORIDOR_TRANSPORT` et retourne l'instance
appropriée. Si l'ouverture échoue, fallback gracieux sur `NullTransport`
avec bannière dégradée dans la webapp.

**Détection automatique du port série** :

- Mac : `glob("/dev/cu.usbserial-*")` (driver CP210x / CH340 USB-C)
- Linux : `glob("/dev/ttyUSB*")`

La variable d'environnement `QUORIDOR_SERIAL_PORT` peut forcer un port précis.

---

### `webapp/plateau.py` — `PlateauBridge`

Couche **au-dessus du `Transport`** qui apporte les garanties
applicatives :

- **Heartbeat applicatif** : `PING` toutes les 5 s, détection de coupure
  après 2 `PONG` ratés (timeout total ~10 s).
- **Lock TX** : sérialise toutes les paires (write, read response) pour
  éviter les races entre heartbeat et commandes utilisateur.
- **Reconnexion automatique** : tâche en arrière-plan qui retente
  `transport.open()` toutes les 10 s après une coupure.
- **Bascule à chaud** : `switch_transport(new_transport)` permet de
  changer le canal physique sans recréer le service.
- **Fallback gracieux** : à la première erreur de transport pendant une
  commande, `available = False` ; les forwards suivants deviennent des
  no-ops silencieux jusqu'à la reconnexion.

Méthode principale :

```python
def forward_move(self, move) -> None:
    """Envoie WALL <H|V> <r> <c> si move est une pose de mur.

    Applique l'inversion d'orientation H ↔ V (convention engine ≠ firmware).
    Les déplacements de pion sont des no-ops (pas de système physique).
    """
```

**Handshake initial** : à l'ouverture du transport, envoie `PING` (timeout
5 s, polling 0,5 s). Si `PONG` arrive, le pont devient actif. Sinon, la
webapp démarre quand même avec `available = False` et une bannière
explicite "transport indisponible, mode dégradé".

---

### `webapp/leds.py` — affichage sur la strip WS2812B

Classe `LedRenderer` qui rend l'état du jeu sur la strip de 36 LEDs
WS2812B câblée en serpentin.

- `engine_to_strip_index(row, col)` : convertit une case logique (row, col)
  en index linéaire dans la strip (serpentin alternant gauche↔droite).
- `LedColor` : tuple `(r, g, b)` (`int * 3`, valeurs `[0..255]`).
- `RenderOptions` : `show_legal_moves: bool` (P1, active l'affichage des
  coups légaux en cyan dim).
- `render_state(state, opts) -> list[LedColor]` : produit le vecteur de
  36 couleurs cible pour un `GameState` donné.
- `LedRenderer.update(state)` : compare au vecteur précédent, calcule le
  diff, et envoie via le bridge :
  - `LED <idx> <r> <g> <b>` pour chaque pixel changé
  - `LEDSHOW` final pour le push atomique
- **Reconnexion** : sur callback de reconnexion du `PlateauBridge`, le
  renderer force un re-render complet (le buffer firmware a été réinitialisé).

Palette par défaut :

| Élément | Couleur |
|---|---|
| Joueur 1 (humain) | bleu `(0, 0, 255)` |
| Joueur 2 (IA) | rouge `(255, 0, 0)` |
| Cases atteignables (P1) | cyan dim `(0, 64, 64)` |
| Fond | éteint `(0, 0, 0)` |

Voir la spec complète :
[`superpowers/specs/2026-05-21-leds-design.md`](superpowers/specs/2026-05-21-leds-design.md).

---

### `webapp/schemas.py`

Modèles **Pydantic** des messages échangés entre frontend et API.

Exemples :

- `MoveRequest` — payload de `POST /api/move`
- `GameStateResponse` — réponse de `GET /api/state`
- `NewGameRequest` — paramètres de `POST /api/new-game`
- `TransportStatusResponse` — réponse de `GET /api/status`

---

### `webapp/qr.py`

Génère un QR code SVG vers l'URL de la webapp pour partage avec un
smartphone. Utilisé par `/api/qr-code`. Pas de dépendance externe lourde
(générateur SVG en Python pur).

---

## Modes d'exécution

### Mode autonome (`QUORIDOR_TRANSPORT=none`)

Aucun matériel requis. La webapp tourne entièrement en local sur le Mac
et le moteur Python gère l'état complet. Mode "démo minimum" (P0) si le
plateau physique est indisponible.

### Mode développement (`QUORIDOR_TRANSPORT=serial`)

ESP32 connecté au Mac via USB-C. Détection automatique du port. Plus
fiable que le Wi-Fi pour du debug ; permet de capturer les logs verbeux
du firmware sur le moniteur série en parallèle.

### Mode démo (`QUORIDOR_TRANSPORT=wifi`, défaut)

L'ESP32 héberge le réseau `Quoridor-ESP32`. Le Mac s'y connecte et
joint l'ESP32 via TCP. L'iPhone du joueur se connecte au même réseau et
ouvre la webapp via l'IP du Mac (typiquement `192.168.4.2:8000`).
Aucun accès Internet requis.

L'outil [`tools/wifi_switch.py`](../tools/wifi_switch.py) automatise la
bascule réseau côté Mac via `networksetup` (macOS).

---

## Flux d'un coup en mode démo

```
Frontend                  server.py            service.py          plateau.py            ESP32
   |                         |                     |                   |                    |
   |  POST /api/move         |                     |                   |                    |
   |  {type:'mur',...}       |                     |                   |                    |
   |---------------------->  |                     |                   |                    |
   |                         |  apply_move(move)   |                   |                    |
   |                         |------------------>  |                   |                    |
   |                         |                     | engine.play_move()|                    |
   |                         |                     |       OK          |                    |
   |                         |                     | forward_move(move)|                    |
   |                         |                     |------------------>|  WALL H 2 3\n      |
   |                         |                     |                   |------------------->|
   |                         |                     |                   |   WALL OK ...      |
   |                         |                     |                   |<-------------------|
   |                         |                     | LedRenderer.update|                    |
   |                         |                     |       (diff)      |                    |
   |                         |                     |------------------>|  LED ... LEDSHOW   |
   |                         |                     |                   |------------------->|
   |                         |                     |                   |        OK          |
   |  200 OK + état          |                     |                   |                    |
   |<----------------------- |                     |                   |                    |
```

Voir aussi le diagramme Mermaid :
[`flowcharts/07_webapp_flux.md`](flowcharts/07_webapp_flux.md).

---

## Frontend

- Rendu SVG inline du plateau 6×6.
- Clic sur une case → déplacement du pion (si coup légal).
- Clic sur une arête inter-cases → pose d'un mur (si coup légal).
- Affichage du joueur courant, compteurs de murs restants, statut de la
  partie, transport actif.
- Polling `GET /api/state` toutes les 500 ms pour mettre à jour
  l'affichage (coups IA inclus).
- **QR code intégré** : bouton "Partager sur smartphone" qui affiche
  l'URL via QR (route `/api/qr-code`).
- **Bannière dégradée** affichée si le transport est indisponible, avec
  boutons UI "Réessayer en USB" / "Réessayer en Wi-Fi" qui appellent
  `/api/transport/switch`.
- **Aucun framework** (React, Vue, etc.) — choix pédagogique pour la
  lisibilité du code.

---

## Tests

| Fichier | Couverture |
|---|---|
| `tests/webapp/test_api.py` | Routes FastAPI principales (client httpx) |
| `tests/webapp/test_api_status.py` | Route `/api/status` |
| `tests/webapp/test_api_transport_switch.py` | Bascule transport à chaud |
| `tests/webapp/test_service.py` | Couche service + intégration moteur + transport mocké |
| `tests/webapp/test_plateau_bridge.py` | Heartbeat, lock TX, reconnexion |
| `tests/webapp/test_transport_abstract.py` | Contrat de l'interface `Transport` |
| `tests/webapp/test_transport_factory.py` | Factory `make_transport()` selon env var |
| `tests/webapp/test_transport_null.py` | `NullTransport` (no-ops) |
| `tests/webapp/test_transport_serial.py` | `SerialTransport` avec `serial.Serial` mocké |
| `tests/webapp/test_transport_wifi.py` | `WiFiTransport` avec socket mocké |
| `tests/webapp/test_schemas.py` | Modèles Pydantic |
| `tests/webapp/test_status_schemas.py` | Schémas `/api/status` |

Aucun test ne nécessite un ESP32 physique. Les tests d'intégration
matériel se trouvent dans `tests/devkit/` (markers `devkit_serial` et
`devkit_wifi`). Voir [`08_tests.md`](08_tests.md).

```bash
pytest tests/webapp/ -v          # tests unitaires (sans hardware)
pytest -m devkit_serial          # tests devkit USB (ESP32 branché)
pytest -m devkit_wifi            # tests devkit Wi-Fi
```
