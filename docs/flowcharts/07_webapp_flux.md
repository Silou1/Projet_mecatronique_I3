# Webapp — couches HTTP et flux de jeu

La webapp est servie par **FastAPI** + **uvicorn** sur le port 8000. Elle
tourne sur le Mac et est accessible depuis n'importe quel navigateur sur
le même réseau (Safari iPhone, Chrome sur le Mac, etc.). Frontend HTML5 +
SVG inline + JS vanilla — zéro framework, zéro étape de build.

Pour l'historique de l'architecture serveur côté **RPi** (avant le pivot
2026-05-20), voir
[`archive/pre-2026-05-20/07_webapp_flux.md`](archive/pre-2026-05-20/07_webapp_flux.md).

---

## Architecture en couches

```mermaid
graph TB
    subgraph FRONT["Frontend (navigateur)"]
        SVG["Rendu SVG inline 6×6<br/>HTML5 + CSS3 + JS vanilla"]
        POLL["Polling 500 ms<br/>GET /api/state"]
    end

    subgraph SERVER["Couche HTTP — webapp/server.py"]
        FASTAPI["FastAPI app<br/>+ uvicorn"]
        ROUTES["Routes :<br/>/ , /api/new_game<br/>/api/move , /api/state<br/>/api/transport/switch<br/>/api/qr-code"]
    end

    subgraph SERVICE["Couche service — webapp/service.py"]
        QSERVICE["QuoridorService singleton<br/>thread-safe (lock)"]
        STATE["GameState courant<br/>(immuable)"]
        TICK["thread daemon tick<br/>(pour coups IA)"]
    end

    subgraph ENGINE_LAYER["Moteur — quoridor_engine/"]
        CORE["core.py<br/>règles, validation, BFS"]
        AI["ai.py<br/>Minimax + alpha-bêta"]
    end

    subgraph TRANSPORT["Couche plateau — webapp/"]
        BRIDGE["plateau.py<br/>PlateauBridge<br/>heartbeat + lock TX<br/>reconnexion auto"]
        TRANSP["transport.py<br/>SerialTransport<br/>WiFiTransport<br/>NullTransport"]
        LEDS["leds.py<br/>LedRenderer + diff<br/>mapping serpentin"]
    end

    SVG -->|HTTP| FASTAPI
    POLL -->|HTTP| FASTAPI
    FASTAPI --> ROUTES
    ROUTES --> QSERVICE
    QSERVICE --> CORE
    QSERVICE --> AI
    TICK --> AI
    QSERVICE --> BRIDGE
    BRIDGE --> TRANSP
    QSERVICE --> LEDS
    LEDS --> BRIDGE

    TRANSP -.->|USB ou Wi-Fi| ESP[(ESP32)]

    style FRONT fill:#2196F3,color:#fff
    style SERVER fill:#4CAF50,color:#fff
    style SERVICE fill:#FF9800,color:#fff
    style ENGINE_LAYER fill:#9C27B0,color:#fff
    style TRANSPORT fill:#795548,color:#fff
```

---

## Routes principales

| Méthode | Route | Rôle |
|---|---|---|
| `GET` | `/` | Sert le fichier HTML principal |
| `GET` | `/api/state` | Retourne l'état courant (polling 500 ms) |
| `POST` | `/api/new_game` | Démarre une nouvelle partie (mode + difficulté) |
| `POST` | `/api/move` | Soumet un coup (déplacement ou mur) |
| `POST` | `/api/reset` | Remet le plateau à zéro |
| `POST` | `/api/transport/switch` | Bascule à chaud entre `wifi`, `serial`, `none` |
| `GET` | `/api/qr-code` | Retourne un QR code SVG vers l'URL de la webapp |
| `GET` | `/api/status` | Statut du transport (état, dernier ping, erreurs) |

---

## Flux d'un coup humain (pose de mur, mode démo Wi-Fi)

```mermaid
sequenceDiagram
    participant FRONT as Frontend SVG
    participant API as server.py
    participant SVC as QuoridorService
    participant ENGINE as quoridor_engine
    participant BRIDGE as PlateauBridge
    participant LED as LedRenderer
    participant ESP as ESP32

    FRONT->>API: POST /api/move<br/>{type:'mur', orientation:'h', row:2, col:3}
    API->>SVC: apply_move(('mur', 'h', 2, 3))
    SVC->>ENGINE: play_move(state, move)

    alt Coup valide (BFS confirme un chemin pour les 2 joueurs)
        ENGINE->>SVC: nouveau GameState
        SVC->>SVC: state = nouveau
        SVC->>BRIDGE: send_wall('H', 2, 3) (inversion H↔V)
        BRIDGE->>ESP: WALL H 2 3\n
        Note over ESP: GOTO + LEVER + BAISSER<br/>× nombre de cases mesurées
        ESP->>BRIDGE: WALL OK H 2 3 raised=2
        BRIDGE->>SVC: retour OK
        SVC->>LED: render_state(state)
        LED->>LED: diff vs précédent
        LED->>BRIDGE: LED <i> <r> <g> <b> (× N)
        LED->>BRIDGE: LEDSHOW
        BRIDGE->>ESP: (commandes LED batch)
        SVC->>API: dict état sérialisé
        API->>FRONT: 200 OK + état
    else Coup invalide (mur bloque le chemin, déjà posé, etc.)
        ENGINE-->>SVC: InvalidMoveError(code=ILLEGAL)
        SVC-->>API: HTTPException 400
        API->>FRONT: 400 + {error: 'ILLEGAL'}
    end

    Note over FRONT,ESP: Polling /api/state continue<br/>indépendamment toutes les 500 ms
```

---

## Flux d'un coup IA (tick thread)

```mermaid
sequenceDiagram
    participant TICK as Thread tick<br/>(daemon, service.py)
    participant SVC as QuoridorService
    participant AI as ai.py
    participant ENGINE as quoridor_engine.core
    participant BRIDGE as PlateauBridge
    participant ESP as ESP32

    loop Toutes les 0,5 s
        TICK->>SVC: lock.acquire()
        TICK->>SVC: current_player == AI ?

        alt Oui
            SVC->>AI: find_best_move(state)<br/>iterative deepening
            AI->>ENGINE: explore arbre minimax
            AI->>SVC: meilleur coup
            SVC->>ENGINE: play_move(state, ai_move)
            ENGINE->>SVC: nouveau GameState
            SVC->>SVC: state = nouveau

            alt Coup IA = mur
                SVC->>BRIDGE: send_wall(...)
                BRIDGE->>ESP: WALL ...
                ESP->>BRIDGE: WALL OK ...
            end

            SVC->>BRIDGE: LedRenderer.update + LEDSHOW
        else Non (tour humain)
            Note over TICK: attend, polling 500 ms
        end

        TICK->>SVC: lock.release()
    end
```

---

## Modes d'exécution

```mermaid
flowchart LR
    START(["Démarrage webapp"]) --> ENV{QUORIDOR_TRANSPORT}

    ENV -->|none| AUTONOMOUS[NullTransport<br/>jeu 100 % logiciel<br/>= démo P0]
    ENV -->|serial| HYBRID_USB[SerialTransport<br/>câble USB-C<br/>= mode dev]
    ENV -->|wifi (défaut)| HYBRID_WIFI[WiFiTransport<br/>AP Quoridor-ESP32<br/>= mode démo]

    AUTONOMOUS --> NO_MIRROR[Murs posés à l'écran<br/>aucun écho physique]
    HYBRID_USB --> MIRROR[Webapp pilote le plateau]
    HYBRID_WIFI --> MIRROR

    MIRROR --> CRASH{Erreur transport<br/>en cours ?}
    CRASH -->|Oui| FALLBACK[available = False<br/>bannière PLATEAU_LOST<br/>reconnexion auto background]
    CRASH -->|Non| OK[Partie suit son cours]
    FALLBACK --> OK

    style AUTONOMOUS fill:#9E9E9E,color:#fff
    style HYBRID_USB fill:#4CAF50,color:#fff
    style HYBRID_WIFI fill:#FF9800,color:#fff
    style FALLBACK fill:#f44336,color:#fff
```

> **Bascule à chaud** : `POST /api/transport/switch` permet de basculer
> `wifi` ↔ `serial` ↔ `none` sans redémarrer la webapp. Pratique pendant
> la démo si le Wi-Fi devient instable.

---

## Frontend

Un seul fichier HTML + un fichier CSS + un fichier JS vanilla. Rendu
**SVG inline** du plateau 6×6 :

- **Clic sur une case** : envoie `/api/move` avec `{type:'deplacement', row, col}`
- **Clic sur une arête inter-cases** : envoie `/api/move` avec `{type:'mur', orientation, row, col}`
- **Coups légaux pré-affichés** en cyan dim (sur le plateau LED aussi, depuis 2026-05-21)
- **Bannières de statut** : transport actif, erreurs, mode dégradé
- **Polling 500 ms** sur `/api/state` met à jour le plateau pour refléter
  les coups IA jouée en arrière-plan
- **QR code intégré** au démarrage (route `/api/qr-code`) pour partager
  l'URL avec un smartphone

Choix volontaire : zéro framework, zéro build. Toute la logique frontale
tient dans ~300 lignes JS, lisible par n'importe quel développeur.

---

## Tests

| Fichier | Couverture |
|---|---|
| `tests/webapp/test_api.py` | Routes FastAPI (client httpx) |
| `tests/webapp/test_service.py` | Couche service, intégration moteur + transport mocké |
| `tests/webapp/test_transport.py` | Implémentations Serial / WiFi / Null |
| `tests/webapp/test_plateau.py` | `PlateauBridge` : heartbeat, lock, reconnexion |
| `tests/webapp/test_leds.py` | `LedRenderer` : mapping serpentin, diff |
| `tests/webapp/test_schemas.py` | Modèles Pydantic |
| `tests/devkit/*.py` | Tests requérant un ESP32 branché (markers `devkit_serial`, `devkit_wifi`) |

Aucun test webapp standard ne nécessite un ESP32 physique. Les tests
hardware sont isolés via marqueurs pytest. Voir
[`../08_tests.md`](../08_tests.md).
