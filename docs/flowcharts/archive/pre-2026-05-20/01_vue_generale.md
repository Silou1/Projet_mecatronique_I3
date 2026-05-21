# Vue générale du système

Ce document présente l'architecture globale du projet Quoridor mécatronique : deux processeurs (Raspberry Pi + ESP32), trois modes d'utilisation (console, webapp, plateau physique), et un canal de communication série UART.

---

## Architecture matérielle et logicielle

```mermaid
graph TB
    subgraph RPI["Raspberry Pi 3/4 — Python 3.12"]
        ENGINE["quoridor_engine/<br/>core.py : règles, GameState immuable<br/>ai.py : Minimax + alpha-bêta"]
        CONSOLE["main.py<br/>Interface console"]
        WEBAPP["webapp/<br/>FastAPI + frontend SVG"]
        SESSION["game_session.py<br/>Mode plateau"]
        UARTC["uart_client.py<br/>Protocole UART Plan 2"]
        CONSOLE --> ENGINE
        WEBAPP --> ENGINE
        SESSION --> ENGINE
        SESSION --> UARTC
        WEBAPP --> UARTC
    end

    subgraph ESP["ESP32-WROOM (Freenove) — Arduino C++"]
        BRINGUP["bringup_l298n_complet.cpp<br/>Boot auto + boucle série"]
        HOME["Procédure HOME<br/>(homing CoreXY)"]
        MOTORS["Pilotage moteurs<br/>2× L298N PWM"]
        SERVO["Pilotage servo<br/>SG90"]
        SENSORS["Lecture capteurs<br/>2× fins de course"]
        BRINGUP --> HOME
        BRINGUP --> MOTORS
        BRINGUP --> SERVO
        BRINGUP --> SENSORS
    end

    subgraph HW["Hardware breadboard"]
        M1["NEMA17 #1"]
        M2["NEMA17 #2"]
        SG["Servo SG90<br/>mécanisme murs"]
        FCX["Fin de course X"]
        FCY["Fin de course Y"]
    end

    UARTC <-->|"UART0 — 115200 bauds<br/>protocole texte + CRC-16"| BRINGUP
    MOTORS --> M1
    MOTORS --> M2
    SERVO --> SG
    SENSORS --> FCX
    SENSORS --> FCY

    style ENGINE fill:#2196F3,color:#fff
    style BRINGUP fill:#FF9800,color:#fff
    style WEBAPP fill:#4CAF50,color:#fff
    style HW fill:#E0E0E0
```

---

## Répartition des responsabilités

| Couche | Rôle | Code |
|---|---|---|
| **Moteur de jeu** | Règles, validation, GameState immuable, undo | `quoridor_engine/core.py` |
| **Intelligence artificielle** | Minimax + alpha-bêta + iterative deepening | `quoridor_engine/ai.py` |
| **Interface console** | UI texte, plateau ASCII 11×11 | `main.py` |
| **Webapp démo** | API REST + frontend SVG navigateur | `webapp/server.py`, `webapp/service.py` |
| **Mode plateau** | Orchestration RPi ↔ ESP32 via UART | `quoridor_engine/game_session.py` |
| **Protocole UART** | Trames texte + CRC-16 + retry | `quoridor_engine/uart_client.py` |
| **Firmware ESP32** | Bring-up CoreXY + servo + capteurs | `firmware/src/bringup_l298n_complet.cpp` |

---

## Les trois modes d'utilisation

```mermaid
flowchart TD
    USER(["Utilisateur"]) --> CHOICE{"Quel mode<br/>de jeu ?"}

    CHOICE -->|"Mode 1"| CONSOLE_MODE["Console terminal<br/>python main.py"]
    CHOICE -->|"Mode 2"| WEBAPP_MODE["Webapp navigateur<br/>python -m webapp.server"]
    CHOICE -->|"Mode 3"| PLATEAU_MODE["Plateau physique<br/>python main.py --mode plateau"]

    CONSOLE_MODE --> CONSOLE_FLOW["Saisie clavier<br/>+ affichage ASCII<br/>+ moteur Python<br/>+ IA Python"]

    WEBAPP_MODE --> WEBAPP_FLOW["Frontend SVG<br/>+ FastAPI<br/>+ polling /api/state<br/>+ mode hybride optionnel"]

    PLATEAU_MODE --> PLATEAU_FLOW["Boutons physiques<br/>+ moteurs CoreXY<br/>+ servo murs<br/>+ UART RPi ↔ ESP32"]

    CONSOLE_FLOW --> COMMON
    WEBAPP_FLOW --> COMMON
    PLATEAU_FLOW --> COMMON

    COMMON["Moteur de jeu commun :<br/>quoridor_engine.core + ai"]

    style USER fill:#2196F3,color:#fff
    style COMMON fill:#9C27B0,color:#fff
    style CONSOLE_MODE fill:#607D8B,color:#fff
    style WEBAPP_MODE fill:#4CAF50,color:#fff
    style PLATEAU_MODE fill:#FF9800,color:#fff
```

---

## Boucle de jeu (vue logique commune)

```mermaid
flowchart TD
    START(["Lancement"]) --> CONFIG["Configuration partie :<br/>mode (PvP / PvIA / IAvIA)<br/>+ difficulté IA (facile/normal/difficile)"]

    CONFIG --> INIT["create_new_game()<br/>Pions au centre, 6 murs/joueur"]
    INIT --> LOOP

    LOOP{"Partie<br/>terminée ?"}
    LOOP -->|Non| RENDER["Afficher l'état<br/>(console / SVG / plateau)"]
    LOOP -->|Oui| END(["Annonce du gagnant"])

    RENDER --> WHO{"À qui le tour ?"}
    WHO -->|"Humain"| HUMAN["Saisie / clic / bouton<br/>→ MovePayload"]
    WHO -->|"IA"| AI_THINK["AI.find_best_move()<br/>(iterative deepening<br/>sous budget temps)"]

    HUMAN --> VALIDATE["play_move()<br/>= move_pawn ou place_wall"]
    AI_THINK --> VALIDATE

    VALIDATE --> OK{"Coup<br/>valide ?"}
    OK -->|Oui| NEW_STATE["Nouvel état GameState<br/>(immuable, ajout à l'historique)"]
    OK -->|Non| ERR["NACK avec code typé<br/>(ILLEGAL, OUT_OF_BOUNDS, ...)"]

    NEW_STATE --> NEXT["Tour du joueur suivant"]
    ERR --> WHO
    NEXT --> LOOP

    style START fill:#4CAF50,color:#fff
    style END fill:#f44336,color:#fff
    style AI_THINK fill:#9C27B0,color:#fff
    style HUMAN fill:#2196F3,color:#fff
    style VALIDATE fill:#FF9800,color:#fff
```

---

## Principes de conception

1. **Séparation moteur / interface** : `quoridor_engine` ne sait rien de la console, du navigateur ni du hardware. La même logique est réutilisée dans les trois modes.
2. **Immutabilité de `GameState`** : chaque coup retourne un nouvel état. Permet l'undo, l'arbre de recherche de l'IA, et le hash pour la table de transposition.
3. **Validation centralisée côté RPi** : l'ESP32 valide *le moins possible*. C'est le moteur Python qui tranche, parce qu'il détient les règles complètes du Quoridor.
4. **Fallback gracieux** : le mode webapp fonctionne sans plateau ; le mode hybride bascule en mode autonome si l'ESP32 se déconnecte en cours de partie.

> **Pour aller plus loin** : `02_logique_ia.md` détaille l'IA, `03_logique_jeu.md` détaille les règles, `04_plateau.md` détaille la représentation des données, `05_firmware_esp32.md` détaille le firmware, `06_protocole_uart.md` détaille la communication, `07_webapp_flux.md` détaille la webapp.
