# Documentation — Quoridor Interactif

Index global de la documentation du projet. Pour le pitch et l'installation rapide, voir le [README racine](../README.md).

## Plan global

- [00_plan_global.md](00_plan_global.md) — **ROADMAP maître** : toutes les phases du projet, état d'avancement, dépendances

## Pour démarrer

- [01_demarrage.md](01_demarrage.md) — Installation, premier lancement, commandes en jeu, dépannage

## Architecture

- [02_architecture.md](02_architecture.md) — Vue d'ensemble : Raspberry Pi (Python/IA) ↔ ESP32 (firmware C++) via UART
- [03_moteur_jeu.md](03_moteur_jeu.md) — Moteur Python : `GameState`, règles, API publique
- [04_ia.md](04_ia.md) — Intelligence artificielle : Minimax, alpha-bêta, heuristiques
- [05_firmware.md](05_firmware.md) — Firmware ESP32 : FSM 7 états, watchdog, FreeRTOS, modules
- [06_protocole_uart.md](06_protocole_uart.md) — Protocole de communication RPi ↔ ESP32 *(Plan 2 figé et implémenté ; tests d'intégration sur DevKit reportés au 2026-05-04)*
- [07_hardware.md](07_hardware.md) — Carte électronique PCB v2 (renvoi vers `hardware/`)

## Tests

- [08_tests.md](08_tests.md) — Stratégie de tests : Python (pytest) + firmware (scénarios manuels)

## Notes & règles

- [jeu/comprendre_le_code.md](jeu/comprendre_le_code.md) — Explication pédagogique du fonctionnement du code (architecture en couches, IA détaillée)
- [notes/note_de_projet.md](notes/note_de_projet.md) — Note de projet mécatronique (système de murs 4 niveaux, mécanique XY)
- [flowcharts/](flowcharts/) — Diagrammes de flux : vue générale, IA, logique de jeu, plateau

## Artefacts de session

- [superpowers/](superpowers/) — Specs (décisions de design figées) et plans (étapes d'implémentation TDD) générés par sessions Claude Code. Voir [superpowers/README.md](superpowers/README.md) pour l'index complet et le statut de chaque artefact. **À nettoyer en fin de projet (P14.4).**

---

**Convention** : tous les documents du projet sont rédigés en français. Le code conserve les noms anglais pour les classes (PascalCase), français pour variables et commentaires.
