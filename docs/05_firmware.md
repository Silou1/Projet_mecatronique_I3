# Firmware ESP32

Firmware Arduino C++ qui tourne sur l'ESP32-WROOM et contrôle tout le hardware du plateau (moteurs XY, LEDs, matrice boutons, servo).

> **Code source** : [firmware/](../firmware/) · **Configuration** : [firmware/platformio.ini](../firmware/platformio.ini)

## Statut actuel

| Phase | État |
|---|---|
| **Plan 1 — Squelette + FSM + watchdog (PCB v2)** | ⛔ Archivé 2026-05-20 (`firmware/archive_plan1_pcb_v2/src_plan2/`). PCB v2 abandonnée. |
| **Plan 2 — Protocole UART** | ⛔ Archivé 2026-05-20 (`firmware/archive_plan1_pcb_v2/src_plan2/UartLink.*`). Sera réutilisé en P11. |
| **Bring-up breadboard L298N (CoreXY + servo + matrices murs)** | ✅ Validé 2026-05-20. Sketch de production : [bringup_l298n_complet.cpp](../firmware/src/bringup_l298n_complet.cpp). Spec validation : [2026-05-20-bringup-breadboard-validation.md](superpowers/specs/2026-05-20-bringup-breadboard-validation.md). |
| **Plan 3 — Intégration RPi ↔ ESP32 via UART** | 📋 À faire (P11). |

## Architecture (état au 2026-05-20)

Le firmware courant n'est plus structuré en modules `.h/.cpp`. Le bring-up breadboard a abouti à des sketches monolithiques dans `firmware/src/` qui pilotent directement CoreXY + servo + capteurs. C'est l'état "production validée" qui sert de référence pour la suite (Plan 3).

| Sketch | Rôle |
|---|---|
| [bringup_l298n_complet.cpp](../firmware/src/bringup_l298n_complet.cpp) | **Production validée** : HOME auto, GOTO, LEVER/BAISSER, MUR H/V, TOUR, STATUS, matrices `MURS_H` + `MURS_V` |
| [bringup_l298n_indep.cpp](../firmware/src/bringup_l298n_indep.cpp) | Contrôle bas niveau indépendant (M1/M2/servo/capteurs) — diagnostic |
| [bringup_motors_and_limits.cpp](../firmware/src/bringup_motors_and_limits.cpp) | CoreXY + capteurs sans servo (jalon intermédiaire) |
| [bringup_motor1_l298n.cpp](../firmware/src/bringup_motor1_l298n.cpp) | Test M1 isolé |
| [bringup_servo.cpp](../firmware/src/bringup_servo.cpp) | Test servo isolé |
| [bringup_limit_switch.cpp](../firmware/src/bringup_limit_switch.cpp) | Test fin de course isolé |

### Modules Plan 2 archivés

L'architecture modules (`GameController`, `UartLink`, `MotionControl`, `ButtonMatrix`, `LedDriver`, `LedAnimator`) est dans [firmware/archive_plan1_pcb_v2/src_plan2/](../firmware/archive_plan1_pcb_v2/src_plan2/). Raisons de l'archivage :

1. **PCB v2 abandonnée** (2026-05-19) : mapping `Pins.h` invalide.
2. **Split GPIO** (2026-05-20) : RPi pilote désormais les 36 boutons + 36 LEDs WS2812 (`ButtonMatrix`, `LedDriver`, `LedAnimator` ESP32 obsolètes).
3. **`MotionControl` était un stub** (sleep + DONE), jamais validé sur cible. À refaire en Plan 3 sur la base du sketch `bringup_l298n_complet.cpp`.
4. **`UartLink`** reste pertinent (protocole Plan 2 validé en pytest avec MockSerial). Sera la base de Plan 3.

## FSM Plan 2 (archivée)

La FSM 7 états (`BOOT`, `WAITING_RPI`, `DEMO`, `CONNECTED`, `BUTTON_INTENT_PENDING`, `EXECUTING`, `ERROR_STATE`) est documentée dans [firmware/archive_plan1_pcb_v2/src_plan2/GameController.cpp](../firmware/archive_plan1_pcb_v2/src_plan2/GameController.cpp) et [superpowers/specs/2026-04-28-firmware-esp32-architecture-globale-design.md](superpowers/specs/2026-04-28-firmware-esp32-architecture-globale-design.md). À reprendre/adapter en Plan 3.

## Multitâche FreeRTOS

Architecture Plan 2 archivée. Le sketch `bringup_l298n_complet.cpp` actuel tourne en monothread (boucle Arduino classique) car les mouvements moteurs bloquent volontairement (génération de pas par `delayMicroseconds`). À refactoriser en Plan 3 si besoin (queue de commandes côté Core 0 pour ne pas bloquer la réception UART sur Core 1).

## Watchdog

- Watchdog hardware ESP32, période **5 secondes**
- Armé sur la `loop()` principale **et** sur la tâche `MotionControl`
- Si l'un des deux ne kick pas le watchdog dans les 5 s, l'ESP32 reboote en sortant un nouveau `BOOT_START` sur UART

## Compilation et flash

```bash
cd firmware

# Sketch de production (par défaut)
pio run                                          # ou : pio run -e esp32dev
pio run -t upload                                # flash
pio device monitor                               # 115200 bauds, LF

# Sketch de production explicite (équivalent)
pio run -e bringup_l298n_complet -t upload
pio device monitor -e bringup_l298n_complet

# Autres envs disponibles : bringup_limit_switch, bringup_servo,
# bringup_motor1_l298n, bringup_motors_and_limits, bringup_l298n_indep
```

## Tests d'intégration

Les tests manuels Plan 1 (7 scénarios FSM) sont obsolètes (PCB v2 + Plan 2 archivés). Les tests d'intégration Plan 3 (UART RPi ↔ ESP32 breadboard) seront définis dans la spec P11 à venir. Le harness pytest `tests/integration/test_uart_devkit.py` (8 scénarios validés en MockSerial) reste utilisable.

## Mapping GPIO (validé 2026-05-20)

Source de vérité : commentaires d'entête de [firmware/src/bringup_l298n_complet.cpp](../firmware/src/bringup_l298n_complet.cpp). Détaillé dans [07_hardware.md](07_hardware.md) et [docs/superpowers/specs/2026-05-20-bringup-breadboard-validation.md](superpowers/specs/2026-05-20-bringup-breadboard-validation.md).

| Fonction | GPIO |
|---|---|
| M1 (L298N #1) IN1/IN2/IN3/IN4/ENA/ENB | 14, 27, 26, 25, 33, 32 |
| M2 (L298N #2) IN1/IN2/IN3/IN4/ENA/ENB | 16, 17, 21, 22, 19, 23 |
| Capteur fin de course X | 13 (INPUT_PULLUP) |
| Capteur fin de course Y | 18 (INPUT_PULLUP) |
| Servo SG90 (Signal) | 4 |
| LED debug intégrée | 2 |

Pour toute question sur les capacités d'un GPIO ESP32, consulter le NotebookLM dédié (cf. [hardware/README.md](../hardware/README.md)).
