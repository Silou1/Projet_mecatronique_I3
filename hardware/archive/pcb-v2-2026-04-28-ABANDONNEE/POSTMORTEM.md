# Postmortem PCB v2 — abandon 2026-05-19

## Date d'abandon

**2026-05-19**, soit 21 jours après la commande EasyEDA (2026-04-28).

## Raisons concrètes de l'abandon

### 1. Erreur de composant — PCA9548A au lieu de MCP23017

La breakout HW-617 montée sur la PCB porte la sérigraphie **PCA9548A** (multiplexeur I2C 8 canaux), pas un MCP23017 (GPIO expander 16 bits comme prévu au design).

- **MCP23017** : reçoit des commandes I2C et pilote 16 GPIO en sortie. Peut commander STEP/DIR/ENABLE des A4988.
- **PCA9548A** : reçoit un bus I2C maître et le redirige vers un canal parmi 8 (SCx/SDx). N'a pas de GPIO de sortie. **Inutilisable pour piloter des A4988.**

Conséquence : toute la chaîne moteur prévue dans le schéma EasyEDA est invalide. Le PCA9548A ne peut servir que pour démultiplexer plusieurs périphériques I2C ayant la même adresse — usage hors scope du projet actuel.

### 2. Conflits de pins ESP32 sur le routage v2

Documentés dans [AUDIT_PCB_V2.md](AUDIT_PCB_V2.md) :

- **GPIO27** partagé entre la ligne LED data (WS2812B) et ROW_2 de la matrice boutons → impossible d'utiliser les deux.
- **GPIO16/17 (UART2)** consommés par les colonnes de la matrice boutons → impossible de garder UART2 pour le link RPi.
- **A4988 ENABLE non connecté** sur la PCB → moteurs alimentés en permanence, échauffement.
- **GPIO0 (strapping pin)** intégré à la matrice boutons → blocage du boot si un bouton est pressé au reset.
- **Polarité possiblement inversée** sur un condensateur (anomalie #9 de l'audit).

### 3. MotionControl jamais validé

Le firmware Plan 1 (`firmware/src/MotionControl.cpp` au moment de l'abandon) était un stub : la "tâche moteur" faisait `vTaskDelay(100ms) × 10` puis renvoyait `DONE`. Aucun pilotage A4988 réel n'a été écrit ni testé sur cible. La validation moteurs aurait nécessité un nouveau cycle dev complet.

### 4. Calendrier

Démo P0 webapp à J-2. Re-spinning d'une PCB v3 + nouveau cycle dev moteurs incompatibles avec la deadline. Pivot vers breadboard pour valider au moins la chaîne moteurs/servo/fins de course en standalone.

## Lessons learned hardware

1. **Toujours vérifier la sérigraphie du chip avant achat**, pas seulement le nom de la breakout board. HW-617 est ambigu (utilisé pour plusieurs chips).
2. **Valider physiquement chaque pin du PCB contre la datasheet ESP32 officielle** (consulter le NotebookLM `ESP32 Development Board Pinout Reference Map` plutôt que les pinouts Freenove tiers qui peuvent diverger).
3. **Ne pas router des signaux temps-critique (STEP) à travers un GPIO expander I2C**. La latence I2C (~200 µs minimum à 400 kHz) est incompatible avec la fréquence de STEP des A4988 (qq kHz typiques). GPIO direct ESP32 obligatoire pour STEP.
4. **Ne pas câbler de strapping pins (GPIO0/2/5/12/15) dans une matrice boutons** : risque de blocage du boot, courant de fuite, flash 1.8V.
5. **Toujours câbler ENABLE des drivers steppers** (pas de tirage à GND définitif) : sinon les moteurs restent alimentés, chauffent, et consomment du courant inutilement.
6. **Vérification physique avant power-up** : polarité des condensateurs, court-circuits visibles, soudures froides.
7. **Faire un bring-up breadboard avant de spinner une PCB**. Si on avait validé la chaîne A4988 + fins de course sur breadboard d'abord, on aurait détecté que le MCP23017 n'était pas adapté pour STEP avant de commander le PCB.

## Ce qui reste valable de l'expérience PCB v2

À ne pas reperdre lors du redémarrage breadboard :

- **Architecture FSM 7 états** (`firmware/src/GameController.cpp`) : BOOT / WAITING_RPI / DEMO / CONNECTED / BUTTON_INTENT_PENDING / EXECUTING / ERROR_STATE. Validée pytest (scénarios 1–8). À conserver intacte.
- **Protocole UART CRC-16 CCITT** (`firmware/src/UartLink.cpp` + `quoridor_engine/uart_client.py`) : framing, dédup seq, reemission ERR, mutex. Validé pytest.
- **Watchdog FreeRTOS 5 s** (loop principale + tâche moteurs).
- **Idempotence CMD avec dédup seq** dans le protocole UART.
- **Spec d'architecture firmware** (`docs/superpowers/specs/2026-04-28-firmware-esp32-architecture-globale-design.md`) : reste la référence pour la couche logique.
- **Helpers Python tests E2E** (`firmware/tests_devkit/_uart_helpers.py`) : `crc16`, `find_devkit_port`, `make_frame`, `read_for`, `wait_for`, `reset_esp`. Génériques, réutilisables sur breadboard.

## Composants physiques

### Conservés (réutilisés sur breadboard)

- 1× ESP32-WROOM (DevKit Freenove)
- 2× drivers A4988
- 2× moteurs steppers NEMA17 (un visible "StepperOnline")
- 1× servo (modèle à confirmer, probablement SG90 ou MG90S)
- 2× fins de course (1 câblé au moment de l'abandon, le 2e dispo)
- 1× alimentation 12V via transformateur
- Châssis CoreXY (cadre alu + courroies + chariots imprimés)

### Mis de côté

- **PCA9548A (breakout HW-617)** : usage futur incertain. Pourrait servir si plusieurs périphériques I2C avec adresses conflictuelles. Pas prévu actuellement.
- **PCB v2 physique** : conservée pour récupération éventuelle de connecteurs, sinon mise au rebut.

## Pointeurs

- [AUDIT_PCB_V2.md](AUDIT_PCB_V2.md) : audit technique détaillé (303 lignes, 9 anomalies analysées contre datasheet ESP32)
- [PCB_PCB_mecatronique_2026-04-28.json](PCB_PCB_mecatronique_2026-04-28.json) : source EasyEDA brute (508 KB) — utile si on veut récupérer une portion de routage
- `../../../firmware/archive_plan1_pcb_v2/Pins.h.original` : mapping pins ESP32 au moment de l'abandon
- `../../../docs/superpowers/specs/2026-05-19-bringup-breadboard-design.md` : spec du nouveau câblage breadboard
