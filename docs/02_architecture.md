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
| **Interface** | UI console ou mode plateau physique | Python | [main.py](../main.py) |
| **Orchestration plateau** | Boucle P9 RPi ↔ ESP32 | Python | [quoridor_engine/game_session.py](../quoridor_engine/game_session.py) |
| **Communication** | Protocole UART Plan 2 RPi ↔ ESP32 | UART0 série | [quoridor_engine/uart_client.py](../quoridor_engine/uart_client.py) + [firmware/src/UartLink.{cpp,h}](../firmware/src/) |
| **Orchestration firmware** | FSM, watchdog, multitâche | Arduino + FreeRTOS | [firmware/src/GameController.{cpp,h}](../firmware/src/) |
| **Drivers hardware** | I2C, moteurs pas-à-pas, LEDs adressables, servo | PlatformIO + libs Arduino | [firmware/src/MotionControl.{cpp,h}](../firmware/src/), `LedDriver`, etc. |

### Couche d'orchestration plateau (P9)

Depuis P9, [main.py](../main.py) accepte un argument `--mode plateau` qui
remplace le prompt console par un dialogue UART avec l'ESP32. La logique
d'orchestration vit dans [quoridor_engine/game_session.py](../quoridor_engine/game_session.py)
(classe `GameSession`).

Cycle de vie d'une partie en mode plateau :

1. `main.py --mode plateau --port /dev/ttyUSB0` ouvre `serial.Serial(...)`.
2. `GameSession.run()` appelle `uart.connect(timeout=15.0)` (handshake HELLO/HELLO_ACK).
3. La boucle de jeu alterne :
   - tour `j1` (humain) : `_await_player_intent` lit `MOVE_REQ`/`WALL_REQ` du firmware,
     valide via `QuoridorGame.play_move`, répond `ACK` ou `NACK <code>` (cf. `NackCode`).
   - tour `j2` (IA) : `_send_ai_move` calcule le coup, envoie `CMD MOVE`/`CMD WALL`,
     bloque jusqu'au `DONE`.
4. Fin de partie : `CMD GAMEOVER <winner>` envoyée puis `uart.close()`.

**Robustesse aux déconnexions** : le client UART détecte les pertes de session
(`ERR UART_LOST` reçu après silence UART côté firmware), envoie `CMD_RESET`,
puis ré-établit le handshake. Limitation P9 acceptée : la position physique des
pions et l'état des LEDs sont perdus à chaque reboot ESP32 (re-synchronisation
prévue en P11).

Le mode console (`--mode console`, défaut) reste inchangé : prompt clavier,
plateau ASCII, logique console pure.

## Flux de données typique (cycle de jeu)

1. Le joueur **appuie sur un bouton** de la matrice 6×6 → `ButtonMatrix` détecte l'intent
2. `GameController` passe en `BUTTON_INTENT_PENDING`, allume une LED de feedback (`PENDING_FLASH`)
3. L'ESP32 envoie `MOVE_REQ <ligne> <col>` sur UART au RPi
4. Le RPi (Python) **valide le coup** via `quoridor_engine` et répond `ACK` ou `NACK`
5. Si `ACK`, l'ESP32 passe en `EXECUTING` → commande motrice (déplacement piston XY, push mur)
6. À la fin, l'ESP32 émet `DONE` → retour à l'état `CONNECTED`
7. Le RPi calcule le coup de l'IA si on est en mode joueur vs IA, et envoie `CMD MOVE <ligne> <col>` ou `CMD WALL <h|v> <ligne> <col>`

Détails de la FSM dans [05_firmware.md](05_firmware.md). Détails du protocole UART dans [06_protocole_uart.md](06_protocole_uart.md).

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
| Bibliothèques RPi | `colorama` (couleurs console), `pyserial` (UART), `pytest` (tests) |
| Langage ESP32 | Arduino C++ (PlatformIO, framework Arduino sur ESP-IDF) |
| Multitâche ESP32 | FreeRTOS (tâche moteurs sur Core 0, FSM sur Core 1) |
| Communication | UART0 à 115200 bauds (partage l'USB pour debug) |
| Format protocole | Trames texte Plan 2 avec CRC-16, seq/ack et retry CMD |
| PCB | EasyEDA, fabriquée 2026-04-28, v2 |

## Pour aller plus loin

- [03_moteur_jeu.md](03_moteur_jeu.md) — API et concepts du moteur Python
- [04_ia.md](04_ia.md) — Détails de l'IA Minimax
- [05_firmware.md](05_firmware.md) — FSM, watchdog, modules ESP32
- [07_hardware.md](07_hardware.md) — PCB et électronique
- [jeu/comprendre_le_code.md](jeu/comprendre_le_code.md) — Vue pédagogique de l'architecture
