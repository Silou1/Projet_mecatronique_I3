# Webapp de démonstration — architecture et flux

Ce document détaille la webapp FastAPI développée comme mode de démonstration principal (suite à l'abandon de la PCB v2). Elle fonctionne en **mode autonome** par défaut, ou en **mode hybride** si un ESP32 est détecté au boot.

Sources : `webapp/server.py`, `webapp/service.py`, `webapp/uart_bridge.py`, `webapp/schemas.py`, `webapp/static/`.

---

## Architecture en trois couches

```mermaid
flowchart TB
    subgraph CLIENT["Navigateur (mobile / desktop)"]
        SVG["Frontend HTML5 + SVG inline<br/>JavaScript vanilla"]
        POLL["Polling /api/state<br/>toutes les 500 ms"]
    end

    subgraph SERVER["Raspberry Pi — FastAPI port 8000"]
        API["server.py<br/>Endpoints HTTP"]
        SERVICE["service.py<br/>QuoridorService (lock + tick thread)"]
        BRIDGE["uart_bridge.py<br/>UartBridge (optionnel)"]
        ENGINE["quoridor_engine<br/>core + ai"]
        API --> SERVICE
        SERVICE --> ENGINE
        SERVICE --> BRIDGE
    end

    subgraph HW["Hardware (optionnel)"]
        ESP["ESP32 firmware<br/>CoreXY + servo"]
    end

    CLIENT <-->|"HTTP JSON"| API
    BRIDGE <-.->|"UART si détecté"| ESP

    style CLIENT fill:#2196F3,color:#fff
    style SERVER fill:#4CAF50,color:#fff
    style HW fill:#FF9800,color:#fff
    style ENGINE fill:#9C27B0,color:#fff
```

---

## Endpoints HTTP exposés

```mermaid
flowchart LR
    subgraph EP["Endpoints"]
        E1["GET /<br/>→ sert index.html"]
        E2["GET /api/state<br/>→ état JSON du jeu"]
        E3["POST /api/new-game<br/>→ démarre une partie"]
        E4["POST /api/move<br/>→ applique un coup humain"]
        E5["POST /api/pause<br/>POST /api/resume<br/>→ pause / reprise"]
        E6["POST /api/speed<br/>→ vitesse IA vs IA"]
        E7["POST /api/wall-mode<br/>→ active mode pose de mur"]
        E8["POST /api/quit<br/>→ retour à l'accueil"]
    end

    style EP fill:#E3F2FD
```

Tous les endpoints retournent un JSON sérialisé par `QuoridorService.to_dict()` contenant : mode, difficulté, statut, joueurs, murs, gagnant, état plateau, dernière erreur.

---

## Flux d'un coup humain (mode autonome)

```mermaid
sequenceDiagram
    participant USER as Utilisateur (souris)
    participant FRONT as Frontend SVG
    participant API as FastAPI
    participant SVC as QuoridorService
    participant ENG as quoridor_engine

    USER->>FRONT: Clic sur une case (r, c)
    FRONT->>API: POST /api/move<br/>{type:"deplacement", target:[r,c]}

    API->>SVC: apply_user_move(payload)

    Note over SVC: with self._lock:
    SVC->>SVC: Valide tour humain<br/>(status, mode, current_player)
    SVC->>ENG: move_pawn(state, player, target)

    alt Coup valide
        ENG->>SVC: Nouvel état GameState
        SVC->>SVC: turn_count += 1<br/>check_game_over()
        SVC->>API: 200 OK + to_dict()
        API->>FRONT: JSON état actualisé
    else Coup invalide
        ENG->>SVC: InvalidMoveError(code=...)
        SVC->>API: HTTPException
        API->>FRONT: 400 + {code, message}
        FRONT->>USER: Affiche erreur
    end

    Note over FRONT: Polling /api/state<br/>toutes les 500 ms<br/>→ redessine plateau SVG
```

---

## Flux d'un coup IA via le tick thread

L'IA tourne dans un **thread daemon séparé** qui boucle toutes les 100 ms. Point clé : la réflexion IA (qui peut prendre 0,5 à 5 secondes selon la difficulté) est exécutée **hors du lock** pour ne pas bloquer les requêtes HTTP.

```mermaid
flowchart TD
    TICK(["Tick thread (daemon)<br/>boucle toutes les 100 ms"]) --> ACQ1["Acquiert _lock"]

    ACQ1 --> CHECKS{"Conditions<br/>réunies ?"}
    CHECKS -->|"status != playing<br/>OU pas tour IA<br/>OU délai non écoulé"| SLEEP["Libère le lock<br/>+ sleep(0.1s)"]
    CHECKS -->|Oui| SNAPSHOT["Snapshot state<br/>_ai_thinking = True"]

    SLEEP --> TICK
    SNAPSHOT --> REL1["Libère _lock"]

    REL1 --> THINK["AI.find_best_move(snapshot)<br/>HORS du lock<br/>(0,5 à 5 secondes)"]

    THINK --> ACQ2["Ré-acquiert _lock"]

    ACQ2 --> RECHECK{"Partie toujours<br/>active ?<br/>(pas quit, pas pause)"}
    RECHECK -->|Non| ABANDON["Jette le coup<br/>(utilisateur a quitté)"]
    RECHECK -->|Oui| APPLY["Applique le coup<br/>(move_pawn ou place_wall)"]

    APPLY --> UPDATE["turn_count += 1<br/>check_game_over()<br/>forward au plateau si hybride"]
    UPDATE --> REL2["Libère _lock"]
    REL2 --> TICK
    ABANDON --> REL2

    style TICK fill:#9C27B0,color:#fff
    style THINK fill:#FF5722,color:#fff
    style APPLY fill:#4CAF50,color:#fff
```

> **Pourquoi sortir du lock** ? Une requête `GET /api/state` doit retourner sous 100 ms pour que le polling reste fluide. Si l'IA pensait dans le lock, l'interface serait gelée pendant toute sa réflexion.

---

## Mode hybride : webapp + plateau physique

Si l'ESP32 est branché au boot, `UartBridge` essaie le handshake. Si ça réussit, l'option **« mode plateau »** apparaît dans la webapp. Les coups joués dans le navigateur sont alors miroités physiquement.

```mermaid
flowchart TD
    BOOT(["Démarrage du serveur"]) --> DETECT{"ESP32 branché<br/>(handshake OK) ?"}

    DETECT -->|Non| AUTO["UartBridge non créé<br/>plateau.available = False"]
    DETECT -->|Oui| HYBRID["UartBridge initialisé<br/>plateau.available = True"]

    AUTO --> READY["Webapp démarre<br/>en mode autonome uniquement"]
    HYBRID --> READY2["Webapp démarre<br/>+ checkbox 'plateau mode' active"]

    READY --> GAME1["Partie autonome :<br/>moteur Python uniquement"]

    READY2 --> CHOICE{"Joueur coche<br/>'mode plateau' ?"}
    CHOICE -->|Non| GAME1
    CHOICE -->|Oui| GAME2["Partie hybride :<br/>chaque coup est miroité"]

    GAME2 --> MOVE["Coup joué (humain ou IA)"]
    MOVE --> SVC_APPLY["service.apply_user_move()<br/>ou tick_once()"]
    SVC_APPLY --> FORWARD["_forward_to_plateau_unlocked()"]

    FORWARD --> SEND{"Forward<br/>réussi ?"}
    SEND -->|Oui| OK["DONE reçu de l'ESP32<br/>partie continue"]
    SEND -->|Non| LOST["plateau.available = False<br/>last_error = PLATEAU_LOST"]

    LOST --> FALLBACK["Bascule transparente<br/>en mode autonome<br/>(GameState préservé)"]

    OK --> NEXT["Tour suivant"]
    FALLBACK --> NEXT

    style BOOT fill:#2196F3,color:#fff
    style HYBRID fill:#4CAF50,color:#fff
    style FALLBACK fill:#FF9800,color:#fff
    style LOST fill:#f44336,color:#fff
```

> **Fallback gracieux** : aucune tentative de reconnexion automatique. Une fois le plateau perdu, la partie continue côté logiciel sans interruption — le joueur est juste notifié dans l'interface.

---

## Modèle de threading

```mermaid
flowchart LR
    subgraph THREADS["Threads dans le processus FastAPI"]
        MAIN["Thread principal<br/>(uvicorn ASGI)"]
        WORKERS["Workers HTTP<br/>(traitent les requêtes)"]
        TICK["Tick thread (daemon)<br/>tick_once() toutes les 100 ms"]
    end

    subgraph SHARED["État partagé (sous _lock)"]
        STATE["_state : GameState"]
        STATUS["_status, _winner, _turn_count"]
        FLAGS["_ai_thinking, _last_error"]
    end

    WORKERS -->|"acquire _lock"| SHARED
    TICK -->|"acquire _lock"| SHARED

    style THREADS fill:#E3F2FD
    style SHARED fill:#FFF3E0
```

**Règles** :
1. Toutes les mutations passent par `self._lock`.
2. La réflexion IA (la seule opération longue) sort du lock avec un snapshot.
3. Le tick thread est daemon : il meurt avec le processus, pas besoin de stop explicite.

---

> **Principe clé** : la webapp est conçue pour être **toujours fonctionnelle** — sans hardware, avec hardware, et même si le hardware se déconnecte en pleine partie. C'est ce qui en fait un mode de démonstration robuste pour la présentation finale.
