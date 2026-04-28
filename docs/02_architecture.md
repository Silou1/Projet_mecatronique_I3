# Architecture globale

Vue d'ensemble du projet : deux processeurs, un canal de communication, une séparation nette des responsabilités.

## Schéma

```
┌─────────────────────────────────────────┐         ┌────────────────────────────────────┐
│         Raspberry Pi 3/4                │         │          ESP32-WROOM                │
│         (Python 3.10+)                  │  UART0  │       (Arduino C++ / FreeRTOS)      │
│                                         │ 115200  │                                     │
│  ┌──────────────────┐   ┌────────────┐  │  bauds  │  ┌────────────────┐                 │
│  │ quoridor_engine/ │   │  main.py   │  │ ◄──────►│  │ GameController │  FSM 7 états    │
│  │  - core.py       │   │  (UI       │  │         │  │  (orchestration│                 │
│  │  - ai.py         │   │   console) │  │         │  └────────┬───────┘                 │
│  └──────────────────┘   └────────────┘  │         │           │                         │
│         │                                │         │           ├─► UartLink              │
│         └─► moteur jeu, IA Minimax      │         │           ├─► ButtonMatrix (6×6)    │
│             logique pure, immuable       │         │           ├─► MotionControl         │
│                                         │         │           │   (FreeRTOS Core 0)     │
│                                         │         │           ├─► LedDriver / Animator   │
│                                         │         │           └─► (watchdog 5 s)        │
└─────────────────────────────────────────┘         └────────────────────────────────────┘
                                                                       │
                                                                       │ I2C, GPIO, PWM
                                                                       ▼
                                            ┌────────────────────────────────────────────┐
                                            │  Hardware (PCB v2, commandée 2026-04-28)   │
                                            │  - 2× moteur NEMA 17 + A4988 via MCP23017  │
                                            │  - Servo SG90 (rotation/reset murs)        │
                                            │  - LEDs WS2812B (cases interactives)       │
                                            │  - Matrice boutons 6×6                     │
                                            └────────────────────────────────────────────┘
```

## Répartition des responsabilités

| Couche | Rôle | Technologie | Code |
|---|---|---|---|
| **Moteur jeu** | Règles, état, validation, undo | Python pur, immutable | [quoridor_engine/core.py](../quoridor_engine/core.py) |
| **Intelligence** | Choix du meilleur coup | Minimax + alpha-bêta + cache | [quoridor_engine/ai.py](../quoridor_engine/ai.py) |
| **Interface** | UI console (et plus tard, intégration hardware) | Python | [main.py](../main.py) |
| **Communication** | Protocole texte/binaire RPi ↔ ESP32 | UART0 série | [firmware/src/UartLink.{cpp,h}](../firmware/src/) + *côté Python à écrire* |
| **Orchestration firmware** | FSM, watchdog, multitâche | Arduino + FreeRTOS | [firmware/src/GameController.{cpp,h}](../firmware/src/) |
| **Drivers hardware** | I2C, moteurs pas-à-pas, LEDs adressables, servo | PlatformIO + libs Arduino | [firmware/src/MotionControl.{cpp,h}](../firmware/src/), `LedDriver`, etc. |

## Flux de données typique (cycle de jeu)

1. Le joueur **appuie sur un bouton** de la matrice 6×6 → `ButtonMatrix` détecte l'intent
2. `GameController` passe en `BUTTON_INTENT_PENDING`, allume une LED de feedback (`PENDING_FLASH`)
3. L'ESP32 envoie `MOVE_REQ <ligne> <col>` sur UART au RPi
4. Le RPi (Python) **valide le coup** via `quoridor_engine` et répond `ACK` ou `NACK`
5. Si `ACK`, l'ESP32 passe en `EXECUTING` → commande motrice (déplacement piston XY, push mur)
6. À la fin, l'ESP32 émet `DONE` → retour à l'état `CONNECTED`
7. Le RPi calcule le coup de l'IA si on est en mode joueur vs IA, et envoie `CMD MOVE <ligne> <col>`

Détails de la FSM dans [05_firmware.md](05_firmware.md). Détails du protocole UART dans [06_protocole_uart.md](06_protocole_uart.md) *(à écrire, Plan 2 firmware)*.

## Principes de conception

1. **Séparation moteur / interface** : `quoridor_engine` ne sait rien de la console ni du hardware. Permet de tester unitairement et de réutiliser dans une GUI ou un plateau physique.
2. **Immutabilité de `GameState`** : chaque coup retourne un nouvel état. Permet l'undo, l'arbre de recherche de l'IA, et la sérialisation triviale.
3. **FSM explicite côté firmware** : 7 états, transitions documentées, pas de `if` cachés. Voir [05_firmware.md](05_firmware.md).
4. **Watchdog côté ESP32** : 5 secondes. Tout blocage déclenche un reboot propre.
5. **Pas de logique de jeu dans le firmware** : l'ESP32 valide *le moins possible*. C'est le RPi qui tranche, parce que c'est lui qui a le moteur Quoridor complet.

## Stack technique

| Domaine | Choix |
|---|---|
| Langage RPi | Python 3.10+ |
| Bibliothèques RPi | `colorama` (couleurs console), `pytest` (tests) — aucune dépendance lourde |
| Langage ESP32 | Arduino C++ (PlatformIO, framework Arduino sur ESP-IDF) |
| Multitâche ESP32 | FreeRTOS (tâche moteurs sur Core 0, FSM sur Core 1) |
| Communication | UART0 à 115200 bauds (partage l'USB pour debug) |
| Format protocole | Texte simplifié (Plan 1), binaire prévu (Plan 2) |
| PCB | EasyEDA, fabriquée 2026-04-28, v2 |

## Pour aller plus loin

- [03_moteur_jeu.md](03_moteur_jeu.md) — API et concepts du moteur Python
- [04_ia.md](04_ia.md) — Détails de l'IA Minimax
- [05_firmware.md](05_firmware.md) — FSM, watchdog, modules ESP32
- [07_hardware.md](07_hardware.md) — PCB et électronique
- [jeu/comprendre_le_code.md](jeu/comprendre_le_code.md) — Vue pédagogique de l'architecture
