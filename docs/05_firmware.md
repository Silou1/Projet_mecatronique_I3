# Firmware ESP32

Firmware Arduino C++ qui tourne sur l'ESP32-WROOM et contrôle tout le hardware du plateau (moteurs XY, LEDs, matrice boutons, servo).

> **Code source** : [firmware/](../firmware/) · **Configuration** : [firmware/platformio.ini](../firmware/platformio.ini)

## Statut actuel

| Phase | État |
|---|---|
| **Plan 1 — Squelette + FSM + watchdog** | ✅ Implémenté, compile sans erreur (`pio run` SUCCESS), RAM 6,6%, Flash 21,1% |
| **Tests d'intégration sur cible** | 🚧 Reportés tant que l'ESP32 / PCB n'est pas branché — voir [firmware/TESTS_PENDING.md](../firmware/TESTS_PENDING.md) |
| **Plan 2 — Protocole UART réel** | 📋 À écrire |
| **Plan 3 — Drivers hardware (FastLED, MCP23017, A4988, servo)** | 📋 À écrire |

## Architecture des modules

| Module | Fichier(s) | Rôle |
|---|---|---|
| **GameController** | [firmware/src/GameController.{cpp,h}](../firmware/src/) | FSM principale, orchestration, watchdog |
| **UartLink** | [firmware/src/UartLink.{cpp,h}](../firmware/src/) | Serial UART0 vers RPi (texte Plan 1, binaire Plan 2) |
| **ButtonMatrix** | [firmware/src/ButtonMatrix.{cpp,h}](../firmware/src/) | Scan matrice 6×6, détection intents joueur |
| **MotionControl** | [firmware/src/MotionControl.{cpp,h}](../firmware/src/) | Tâche FreeRTOS Core 0, queue de commandes (HOMING / MOVE_TO_WALL_SLOT / PUSH_WALL), pilotage A4988 via MCP23017 |
| **LedDriver** | [firmware/src/LedDriver.{cpp,h}](../firmware/src/) | Interface WS2812B (stub Plan 1, FastLED Plan 3) |
| **LedAnimator** | [firmware/src/LedAnimator.{cpp,h}](../firmware/src/) | Patterns visuels : `PENDING_FLASH`, `TIMEOUT_FLASH`, `NACK_FLASH`, `ERROR_PATTERN`, `EXECUTING_SPINNER` |
| **Pins** | [firmware/src/Pins.h](../firmware/src/Pins.h) | Mapping GPIO complet (audité contre PCB v2) |

## FSM — 7 états

```
                          ┌──────┐
                          │ BOOT │  selfTest, homing
                          └──┬───┘
                             ▼
                   ┌──────────────────┐
                   │   WAITING_RPI    │  émet HELLO toutes les 200 ms
                   └────┬─────────┬───┘
                        │         │ HELLO_ACK reçu
              timeout 3s│         ▼
                        ▼   ┌───────────┐
                   ┌────────│ CONNECTED │◄─────────┐
                   │ DEMO   └────┬──────┘          │
                   │ (terminal)  │                 │
                   └─────────────┤                 │
                                 ▼                 │
                  ┌───────────────────────────┐    │
                  │  BUTTON_INTENT_PENDING    │    │
                  │  (3 timeouts → ERROR)     │    │
                  └────────┬──────────────────┘    │
                           │ ACK                   │
                           ▼                       │
                   ┌────────────┐  DONE            │
                   │ EXECUTING  │──────────────────┘
                   └────────────┘
                                                  ┌──────────┐
                  UART_LOST ou 3 timeouts ────────►│  ERROR   │
                                                  └────┬─────┘
                                                       │ RESET
                                                       ▼
                                                    BOOT
```

Détails complets des transitions dans [superpowers/specs/2026-04-28-firmware-esp32-architecture-globale-design.md](superpowers/specs/2026-04-28-firmware-esp32-architecture-globale-design.md) §2.4.

## Multitâche FreeRTOS

- **Core 1 (par défaut)** : `loop()` Arduino → FSM `GameController`, UART, scan boutons, animations LED
- **Core 0** : tâche `MotionControl` dédiée → consomme une queue de commandes motrices, ne bloque jamais la FSM principale
- **Synchronisation** : queues FreeRTOS (commandes + résultats) entre les deux cores

## Watchdog

- Watchdog hardware ESP32, période **5 secondes**
- Armé sur la `loop()` principale **et** sur la tâche `MotionControl`
- Si l'un des deux ne kick pas le watchdog dans les 5 s, l'ESP32 reboote en sortant un nouveau `BOOT_START` sur UART

## Compilation et flash

```bash
cd firmware
pio run                                  # compile
pio run -t upload                        # flash via USB
pio device monitor                       # ouvrir le moniteur série (115200 bauds, LF)
```

Configuration moniteur : 115200 bauds, fin de ligne `LF` (pas `CRLF`). Filtre `direct` déjà fixé dans `platformio.ini`.

## Tests d'intégration

7 scénarios manuels via Serial Monitor sont décrits dans [firmware/TESTS_PENDING.md](../firmware/TESTS_PENDING.md) :

1. Boot nominal vers `DEMO`
2. Boot nominal vers `CONNECTED` (`HELLO_ACK`)
3. Cycle de jeu simulé complet (`BTN`, `ACK`, `NACK`, `CMD MOVE`)
4. Perte UART en `CONNECTED` (3 s de silence)
5. Escalade timeout intent (3 timeouts → `ERROR`)
6. Récupération depuis `ERROR` (`RESET`)
7. Watchdog (provocation contrôlée, **modification non commitée**)

À exécuter dès que l'ESP32 est branché. Si tous passent, supprimer `TESTS_PENDING.md` et faire un commit `test(firmware): plan 1 valide en bout-en-bout sur cible`.

## Mapping GPIO

Source de vérité : [firmware/src/Pins.h](../firmware/src/Pins.h), audité contre la PCB v2 — voir [hardware/AUDIT_PCB_V2.md](../hardware/AUDIT_PCB_V2.md).

⚠️ **UART2 (GPIO16/17) n'est PAS disponible** sur cette carte : ces pins sont consommées par la matrice boutons. Le lien RPi utilise donc **UART0** (partagée avec l'USB de debug).

Pour toute question sur les capacités d'un GPIO ESP32, consulter le NotebookLM dédié (cf. [hardware/README.md](../hardware/README.md)) plutôt que des mappings de cartes tierces.
