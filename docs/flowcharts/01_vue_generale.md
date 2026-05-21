# Vue générale du système

Ce document présente l'architecture globale du projet Quoridor mécatronique
**après le pivot du 2026-05-20** : un Mac qui exécute toute la logique
logicielle (moteur de jeu, IA, webapp) et un ESP32 qui pilote l'actuation
physique du plateau (CoreXY, servo, LEDs). Communication par USB-série
en développement, par Wi-Fi en démo.

Pour l'historique des décisions ayant mené à cette architecture, voir
[`../decisions.md`](../decisions.md).

---

## Architecture matérielle et logicielle

```mermaid
graph TB
    subgraph MAC["Mac (Python 3.12)"]
        ENGINE["quoridor_engine/<br/>core.py : règles, GameState immuable<br/>ai.py : Minimax + alpha-bêta"]
        WEBAPP["webapp/<br/>server.py (FastAPI :8000)<br/>service.py (orchestration)<br/>transport.py (Serial/WiFi/Null)<br/>plateau.py (heartbeat + lock TX)<br/>leds.py (mapping + diff)"]
        FRONT["Frontend HTML5 + SVG<br/>(navigateur smartphone ou Mac)"]
        WEBAPP --> ENGINE
        FRONT <-->|HTTP polling 500 ms| WEBAPP
    end

    subgraph ESP["ESP32-WROOM (Arduino C++)"]
        BRINGUP["bringup_l298n_complet.cpp<br/>sketch monolithique<br/>traiter(cmd, Stream*)"]
        HOME["HOME automatique<br/>au boot"]
        GOTO["GOTO x y<br/>CoreXY pas à pas"]
        WALL["WALL H/V row col<br/>GOTO + LEVER + BAISSER<br/>x N cases"]
        LEDS["Strip WS2812B<br/>commandes LED/LEDSHOW/..."]
        BRINGUP --> HOME
        BRINGUP --> GOTO
        BRINGUP --> WALL
        BRINGUP --> LEDS
    end

    subgraph HW["Plateau physique (breadboard)"]
        M1["NEMA17 #1 (via L298N #1)"]
        M2["NEMA17 #2 (via L298N #2)"]
        SG["Servo SG90<br/>levée mur"]
        FCX["Fin de course X"]
        FCY["Fin de course Y"]
        STRIP["Strip 36 LEDs WS2812B"]
    end

    WEBAPP <-->|"USB-série 115200 bauds<br/>OU Wi-Fi TCP :3333"| BRINGUP
    GOTO --> M1
    GOTO --> M2
    WALL --> SG
    HOME --> FCX
    HOME --> FCY
    LEDS --> STRIP

    style ENGINE fill:#2196F3,color:#fff
    style BRINGUP fill:#FF9800,color:#fff
    style WEBAPP fill:#4CAF50,color:#fff
    style FRONT fill:#9C27B0,color:#fff
    style HW fill:#E0E0E0
```

Le Mac est le **seul cerveau du jeu** : règles, IA, état de partie, interface
utilisateur. L'ESP32 est un **actionneur intelligent** : il reçoit des
commandes texte et traduit chaque instruction en mouvement physique ou
en affichage LED.

---

## Répartition des responsabilités

| Couche | Rôle | Code |
|---|---|---|
| **Moteur de jeu** | Règles Quoridor, validation des coups, `GameState` immuable, pathfinding BFS anti-blocage | `quoridor_engine/core.py` |
| **Intelligence artificielle** | Minimax + alpha-bêta + iterative deepening + table de transposition | `quoridor_engine/ai.py` |
| **Webapp serveur** | FastAPI, routes API, `QuoridorService` singleton, polling | `webapp/server.py`, `webapp/service.py` |
| **Transport Mac ↔ ESP32** | Interface `Transport` + 3 impls (Serial, WiFi, Null), factory pilotée par env var | `webapp/transport.py` |
| **Pont plateau** | `PlateauBridge` : heartbeat, lock TX, reconnexion auto, bascule à chaud | `webapp/plateau.py` |
| **Affichage LEDs** | Mapping engine↔strip serpentin, classe `LedRenderer` avec diff | `webapp/leds.py` |
| **Frontend** | HTML5 + CSS3 + SVG inline + JS vanilla, zéro framework | `webapp/static/` |
| **Firmware ESP32** | CoreXY, servo, fins de course, strip LED, dispatch Serial+WiFi | `firmware/src/bringup_l298n_complet.cpp` |
| **Interface console** | CLI texte alternative (sans plateau ni webapp) | `main.py` |

---

## Les trois modes d'exécution

```mermaid
flowchart TD
    USER(["Utilisateur"]) --> CHOICE{"Quel mode<br/>de jeu ?"}

    CHOICE -->|"Mode 1 — autonome"| AUTO["webapp sans plateau<br/>QUORIDOR_TRANSPORT=none"]
    CHOICE -->|"Mode 2 — dev"| DEV["webapp + plateau via USB-C<br/>QUORIDOR_TRANSPORT=serial"]
    CHOICE -->|"Mode 3 — démo"| DEMO["webapp + plateau via Wi-Fi<br/>QUORIDOR_TRANSPORT=wifi (défaut)"]
    CHOICE -->|"Mode 4 — console"| CONSOLE["python main.py<br/>(sans webapp ni plateau)"]

    AUTO --> AUTO_FLOW["Partie complète sur navigateur<br/>aucune action physique<br/>= démo minimum (P0)"]

    DEV --> DEV_FLOW["Câble USB-C entre Mac et ESP32<br/>détection auto /dev/cu.usbserial-*"]

    DEMO --> DEMO_FLOW["ESP32 héberge AP Quoridor-ESP32<br/>Mac s'y connecte<br/>navigateur sur 192.168.4.2:8000<br/>aucun Internet requis"]

    CONSOLE --> CONSOLE_FLOW["Interface texte + saisie clavier<br/>plateau ASCII 11×11"]

    AUTO_FLOW --> ENGINE
    DEV_FLOW --> ENGINE
    DEMO_FLOW --> ENGINE
    CONSOLE_FLOW --> ENGINE

    ENGINE["Moteur de jeu commun :<br/>quoridor_engine.core + ai"]

    style USER fill:#2196F3,color:#fff
    style ENGINE fill:#9C27B0,color:#fff
    style AUTO fill:#607D8B,color:#fff
    style DEV fill:#4CAF50,color:#fff
    style DEMO fill:#FF9800,color:#fff
    style CONSOLE fill:#795548,color:#fff
```

---

## Boucle de jeu (vue logique commune)

```mermaid
flowchart TD
    START(["Lancement"]) --> CONFIG["Configuration partie :<br/>mode (PvP / PvIA)<br/>+ difficulté IA"]

    CONFIG --> INIT["create_new_game()<br/>Pions au centre<br/>6 murs/joueur"]
    INIT --> LOOP

    LOOP{"Partie<br/>terminée ?"}
    LOOP -->|Non| RENDER["Afficher l'état :<br/>frontend SVG<br/>+ optionnel : LEDs plateau"]
    LOOP -->|Oui| END(["Annonce du gagnant"])

    RENDER --> WHO{"À qui le tour ?"}
    WHO -->|"Humain"| HUMAN["Clic dans la webapp<br/>→ MovePayload (JSON POST)"]
    WHO -->|"IA"| AI_THINK["AI.find_best_move()<br/>iterative deepening<br/>sous budget temps"]

    HUMAN --> VALIDATE["service.play_move()<br/>→ engine.play_move()"]
    AI_THINK --> VALIDATE

    VALIDATE --> OK{"Coup<br/>valide ?"}
    OK -->|Oui| NEW_STATE["Nouvel GameState immuable<br/>(ajout à l'historique)"]
    OK -->|Non| ERR["HTTP 4xx<br/>+ NackCode typé<br/>(ILLEGAL, WRONG_TURN, ...)"]

    NEW_STATE --> MIRROR{"Coup =<br/>pose de mur ?"}
    MIRROR -->|Oui| PHYS["transport.send WALL H/V r c<br/>→ ESP32 lève le mur physique"]
    MIRROR -->|Non| LED_UPDATE
    PHYS --> LED_UPDATE
    LED_UPDATE["LedRenderer.update()<br/>diff puis LED <i> ... LEDSHOW"]
    LED_UPDATE --> NEXT["Tour du joueur suivant"]
    ERR --> WHO
    NEXT --> LOOP

    style START fill:#4CAF50,color:#fff
    style END fill:#f44336,color:#fff
    style AI_THINK fill:#9C27B0,color:#fff
    style HUMAN fill:#2196F3,color:#fff
    style VALIDATE fill:#FF9800,color:#fff
    style PHYS fill:#FF9800,color:#fff
    style LED_UPDATE fill:#FFD600
```

---

## Principes de conception

1. **Séparation moteur / interface** : `quoridor_engine` ne connaît ni la
   webapp, ni le hardware. La même logique alimente console, webapp et
   plateau.
2. **Immutabilité de `GameState`** : chaque coup retourne un nouvel état.
   Permet l'undo, l'arbre de recherche de l'IA et le hash de la table de
   transposition.
3. **Validation centralisée côté Mac** : l'ESP32 ne valide pas les règles
   du jeu. C'est le moteur Python qui tranche. L'ESP32 se contente
   d'exécuter les commandes hardware reçues.
4. **Fallback gracieux** : si le transport demandé échoue, la webapp
   bascule sur `NullTransport` et continue avec une bannière dégradée.
   Boutons de bascule à chaud `POST /api/transport/switch`.
5. **Pas de boutons sur le plateau** : depuis le 2026-05-21, l'interaction
   se fait exclusivement via la webapp (cf. [`../decisions.md`](../decisions.md)).
   Le plateau est un miroir physique.

---

## Pour aller plus loin

- [02_logique_ia.md](02_logique_ia.md) — détails de l'IA Minimax
- [03_logique_jeu.md](03_logique_jeu.md) — règles et validation
- [04_plateau.md](04_plateau.md) — représentation des données
- [05_firmware_esp32.md](05_firmware_esp32.md) — sketch ESP32 et commandes
- [06_protocole.md](06_protocole.md) — protocole texte Mac ↔ ESP32
- [07_webapp_flux.md](07_webapp_flux.md) — couches webapp et flux HTTP
