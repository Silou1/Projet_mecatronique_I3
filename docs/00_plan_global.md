# Plan global — Quoridor Interactif

> **Statut** : 🚧 *Document en cours de rédaction. Sera finalisé après la session de brainstorm sur les phases globales du projet.*

Ce document est la **source de vérité unique** pour suivre l'avancement du projet. Toutes les autres docs (architecture, firmware, hardware, tests) sont des annexes techniques qui détaillent une phase.

## Vue d'ensemble

Le projet vise à construire un **plateau Quoridor physique interactif** où un joueur humain affronte une intelligence artificielle. L'expérience repose sur deux processeurs :

- **Raspberry Pi 3/4** : moteur de jeu Python, IA Minimax, orchestration des tours
- **ESP32-WROOM** : firmware Arduino C++, contrôle hardware (moteurs XY, LEDs WS2812B, matrice boutons 6×6, servo)
- **Communication** : UART0 entre les deux, à 115200 bauds

## Phases du projet

*🚧 À définir lors du brainstorm. Le squelette ci-dessous est une proposition de départ, pas la version finale.*

| # | Phase | État | Dépendances | Référence |
|---|---|---|---|---|
| P1 | Moteur de jeu Python | ✅ | — | [03_moteur_jeu.md](03_moteur_jeu.md) |
| P2 | Intelligence artificielle | ✅ | P1 | [04_ia.md](04_ia.md) |
| P3 | Interface console | ✅ | P1 | [main.py](../main.py) |
| P4 | Tests Python | ✅ | P1, P2 | [08_tests.md](08_tests.md) |
| P5 | Firmware squelette ESP32 (Plan 1) | ✅ | — | [05_firmware.md](05_firmware.md) |
| P6 | Protocole UART RPi ↔ ESP32 | 📋 | P5 | [06_protocole_uart.md](06_protocole_uart.md) |
| P7 | Drivers hardware (I2C, A4988, FastLED, servo) | 📋 | P5 | *à écrire* |
| P8 | Intégration RPi ↔ ESP32 (client UART Python) | 📋 | P6 | *à écrire* |
| P9 | Mise sous tension PCB & calibration | 📋 | P7, hardware soudé | [07_hardware.md](07_hardware.md) |
| P10 | Tests d'intégration bout-en-bout | 📋 | P8, P9 | *à écrire* |
| P11 | Démo finale & livrable | 📋 | P10 | *à écrire* |

**Légende** : ✅ fait · 🚧 en cours · 📋 à faire

## Prochaine action

Brainstormer la version définitive de ce plan : ordre des phases, dépendances, granularité, jalons (deadlines, présentations), rôles dans l'équipe de 6.
