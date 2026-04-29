# Plan global — Quoridor Interactif

> **Source de vérité unique** pour suivre l'avancement du projet. Toutes les autres docs (architecture, firmware, hardware, tests) sont des annexes techniques qui détaillent une phase.

## Vue d'ensemble

Le projet vise à construire un **plateau Quoridor physique interactif** où un joueur humain affronte une intelligence artificielle. L'expérience repose sur deux processeurs :

- **Raspberry Pi 3/4** : moteur de jeu Python, IA Minimax, orchestration des tours
- **ESP32-WROOM** : firmware Arduino C++, contrôle hardware (moteurs XY, LEDs WS2812B, matrice boutons 6×6, servo)
- **Communication** : UART0 entre les deux, à 115200 bauds

**Objectif final** : démo complète, plateau entièrement fonctionnel — appui bouton → validation Python → moteurs → mur physique qui monte → réinitialisation par servo en fin de partie.

## Règles transversales

Ces règles s'appliquent à **toutes les phases** ci-dessous.

| Icône | Règle | Détail |
|---|---|---|
| 🟢 | **Tests Python verts** | À la fin de chaque phase, `pytest` passe à 100 %. Les 90 tests existants ne régressent jamais. |
| 📝 | **Doc à jour au fil de l'eau** | Chaque phase met à jour les docs concernées dans [docs/](.). Notamment [05_firmware.md](05_firmware.md), [06_protocole_uart.md](06_protocole_uart.md), [07_hardware.md](07_hardware.md). |
| 📋 | **CHANGELOG.md tenu à jour** | Une entrée par fin de phase dans [CHANGELOG.md](../CHANGELOG.md). |
| 🛟 | **Fallback hardware** | Si PCB bloquée, continuer en simulation sur DevKit. Si mécanique 3D en retard, tester moteurs en breadboard hors plateau. |

## Phases ✅ déjà terminées

| # | Phase | Référence |
|---|---|---|
| **P1** | Moteur de jeu Python (règles, validation, undo) | [03_moteur_jeu.md](03_moteur_jeu.md), [quoridor_engine/core.py](../quoridor_engine/core.py) |
| **P2** | Intelligence artificielle Minimax + alpha-bêta | [04_ia.md](04_ia.md), [quoridor_engine/ai.py](../quoridor_engine/ai.py) |
| **P3** | Interface console | [main.py](../main.py) |
| **P4** | Tests Python (90 tests, 82 % couverture) | [08_tests.md](08_tests.md), [tests/](../tests/) |
| **P5** | Firmware ESP32 — squelette + FSM 7 états + watchdog (Plan 1) | [05_firmware.md](05_firmware.md), [firmware/src/](../firmware/src/) |

---

## Bloc DevKit

> Phases **réalisables avec un ESP32 DevKit nu**, sans dépendre de la PCB v2.

### P6 — Setup environnement firmware 🚧

> But : pouvoir compiler, flasher et observer la sortie série du DevKit depuis le Mac.

- [ ] **P6.1** Brancher l'ESP32 DevKit au Mac via USB
- [ ] **P6.2** Installer le driver USB-série (CP210x ou CH340 selon le module)
- [ ] **P6.3** Vérifier la détection du port (`pio device list`)
- [ ] **P6.4** Compiler et flasher Plan 1 (`cd firmware && pio run -t upload`)
- [ ] **P6.5** Ouvrir le Serial Monitor (`pio device monitor`) et observer la séquence de boot

### P7 — Validation Plan 1 sur cible 📋

> But : exécuter les 7 scénarios documentés dans [firmware/TESTS_PENDING.md](../firmware/TESTS_PENDING.md), corriger les éventuels bugs résiduels du Plan 1, et marquer le Plan 1 comme validé bout-en-bout.

- [ ] **P7.1** Scénario 1 — boot nominal vers `DEMO`
- [ ] **P7.2** Scénario 2 — boot nominal vers `CONNECTED` (`HELLO_ACK`)
- [ ] **P7.3** Scénario 3 — cycle de jeu simulé complet (`BTN`, `ACK`, `NACK`, `CMD MOVE`)
- [ ] **P7.4** Scénario 4 — perte UART en `CONNECTED` (3 s de silence)
- [ ] **P7.5** Scénario 5 — escalade timeout intent (3 timeouts → `ERROR`)
- [ ] **P7.6** Scénario 6 — récupération depuis `ERROR` (`RESET`)
- [ ] **P7.7** Scénario 7 — watchdog (provocation contrôlée)
- [ ] **P7.8** Couverture du spec (Scénario 8) — cocher tous les états et transitions
- [ ] **P7.9** Identifier et corriger les bugs trouvés (commits de correctifs)
- [ ] **P7.10** Supprimer [firmware/TESTS_PENDING.md](../firmware/TESTS_PENDING.md), commit `test(firmware): plan 1 valide en bout-en-bout sur cible`

### P8 — Protocole UART Plan 2 📋

> But : remplacer le protocole texte stub du Plan 1 par un protocole final (binaire ou texte enrichi avec framing + intégrité), implémenté côté ESP32 *et* côté Python.

- [ ] **P8.1** Designer le protocole final — trancher : framing (COBS, SLIP, longueur fixe ?), intégrité (CRC-8/16, checksum XOR ?), versioning, ID de séquence (questions ouvertes dans [06_protocole_uart.md](06_protocole_uart.md))
- [ ] **P8.2** Documenter le protocole arrêté dans [06_protocole_uart.md](06_protocole_uart.md)
- [ ] **P8.3** Refactor [firmware/src/UartLink.{cpp,h}](../firmware/src/) pour implémenter le protocole final
- [ ] **P8.4** Créer un module Python client UART (probablement `quoridor_engine/uart_client.py` ou `interface/uart.py`)
- [ ] **P8.5** Tests unitaires côté Python (avec serial loopback ou ESP32 DevKit en mode echo)
- [ ] **P8.6** Tests d'intégration ESP32 DevKit ↔ Python : envoi/réception de toutes les trames

### P9 — Intégration logicielle RPi ↔ ESP32 📋

> But : faire dialoguer `quoridor_engine` avec l'ESP32 DevKit via UART. Mode plateau-physique-en-simulation, sans périphériques réels.

- [ ] **P9.1** Adapter [main.py](../main.py) pour offrir un mode « plateau physique » en plus du mode console
- [ ] **P9.2** Implémenter le flux entrant : Python attend `MOVE_REQ` → valide via `QuoridorGame` → renvoie `ACK` ou `NACK`
- [ ] **P9.3** Implémenter le flux sortant : Python envoie `CMD MOVE` pour les coups joués par l'IA
- [ ] **P9.4** Côté ESP32 (DevKit), conserver les boutons en mode injection (commande `BTN x y` via Serial) et les LEDs/moteurs en stub (logs uniquement)
- [ ] **P9.5** Tests d'intégration end-to-end : partie complète PvIA via UART avec ESP32 DevKit
- [ ] **P9.6** Mettre à jour [02_architecture.md](02_architecture.md) et [06_protocole_uart.md](06_protocole_uart.md)

---

## Bloc PCB

> Phases **nécessitant la PCB v2** (réception prévue le 10 mai 2026).

### P10 — Mise sous tension PCB v2 📋

> But : alimenter la PCB pour la première fois, valider que le firmware tourne sur la vraie carte, identifier d'éventuelles divergences avec le DevKit.

- [ ] **P10.1** Vérifications physiques pré-alimentation, cf. [hardware/AUDIT_PCB_V2.md](../hardware/AUDIT_PCB_V2.md) :
   - polarité du condensateur 10 µF
   - GPIO0 (BOUTON1) non pressé au boot
   - GPIO de la pin 27 (data WS2812B) confirmé par toggle
- [ ] **P10.2** Premier branchement et alimentation
- [ ] **P10.3** Détection USB et ouverture du Serial Monitor
- [ ] **P10.4** Flash Plan 1 (déjà validé en P7) sur la PCB
- [ ] **P10.5** Rejouer scénarios 1 à 3 sur la vraie carte pour vérifier le boot, la FSM et le cycle de jeu simulé
- [ ] **P10.6** Documenter les éventuelles divergences vs DevKit (mapping pins, comportements UART, etc.)

### P11 — Drivers hardware & calibration 📋

> But : implémenter les drivers réels pour tous les périphériques de la PCB, et calibrer en parallèle ce qui doit l'être (essentiellement les moteurs et le servo).
>
> Ordre des sous-tâches : du plus simple au plus complexe, pour monter en compétence progressivement.

- [ ] **P11.1** Driver matrice boutons 6×6
   - Scan ligne/colonne réel
   - Déparasitage (debounce logiciel)
   - Test individuel de chaque bouton
- [ ] **P11.2** Driver LEDs WS2812B (FastLED)
   - Initialisation FastLED sur GPIO27
   - Implémentation des animations existantes (`PENDING_FLASH`, `EXECUTING_SPINNER`, etc.)
   - Calibration luminosité (ne pas tirer trop sur l'alim USB)
- [ ] **P11.3** Driver MCP23017 (I2C)
   - Initialisation I2C
   - Lecture/écriture des registres
   - Configuration des pins en sortie pour piloter A4988
- [ ] **P11.4** Drivers A4988 (moteurs pas-à-pas) + calibration mécanique XY
   - Commandes `step`/`dir` via MCP23017
   - Routine de homing (capteur fin de course ou butée matérielle ?)
   - Mapping mm → pas (mesure sur la mécanique 3D réelle)
   - Coordonnées XY de chaque slot de mur
   - Vitesse et accélération
- [ ] **P11.5** Driver servo SG90 + calibration
   - Commande PWM
   - Position de repos et position de réinitialisation
   - Course angulaire pour désengager les loquets
- [ ] **P11.6** Mettre à jour [05_firmware.md](05_firmware.md) et [07_hardware.md](07_hardware.md) avec les drivers réels

### P12 — Logique de jeu complète sur plateau 📋

> But : assembler tous les morceaux. Le flux complet « appui bouton → IA → moteurs → mur monte » fonctionne bout-en-bout sur la PCB et la mécanique 3D.

- [ ] **P12.1** Flux : appui bouton → ESP32 émet `MOVE_REQ` → Python valide
- [ ] **P12.2** Sur `ACK`, ESP32 commande déplacement piston (pour pion virtuel via LED) ou push de mur
- [ ] **P12.3** Tour de l'IA : Python envoie `CMD MOVE` → ESP32 visualise (LEDs + moteurs)
- [ ] **P12.4** Gestion fin de partie : déclenchement servo de réinitialisation des murs
- [ ] **P12.5** Mode démo PvIA fluide bout-en-bout

### P13 — Tests d'intégration & robustesse 📋

> But : pousser le système dans ses retranchements pour identifier les bugs résiduels avant la démo.

- [ ] **P13.1** 5+ parties complètes PvIA bout-en-bout (scénarios variés)
- [ ] **P13.2** Tests de stress : parties longues (>50 coups), saturation murs (6+6 placés)
- [ ] **P13.3** Tests de panne : perte UART pendant une partie, watchdog déclenché, récupération
- [ ] **P13.4** Tests d'erreurs : `NACK` répétés, timeouts, recovery depuis `ERROR`
- [ ] **P13.5** Identifier et corriger les bugs résiduels (commits de correctifs finaux)

### P14 — Livrable final 📋

> But : finaliser le projet sous une forme prête à présenter et à transmettre.

- [ ] **P14.1** Documentation utilisateur : mode d'emploi du plateau (allumer, jouer, réinitialiser, dépanner)
- [ ] **P14.2** Documentation technique finalisée : revue de cohérence sur l'ensemble de [docs/](.), CHANGELOG complet, README racine à jour
- [ ] **P14.3** Préparation soutenance : slides, démo prête à tourner, plan B en cas de bug imprévu
- [ ] **P14.4** Nettoyage du repo : suppression de [docs/superpowers/](superpowers/), des fichiers obsolètes, vérif `.gitignore`
- [ ] **P14.5** Tag de version finale (`git tag -a v1.0.0 -m "Démo soutenance"`, push)

---

## Légende

- ✅ **fait** — terminé et committé
- 🚧 **en cours** — phase active
- 📋 **à faire** — pas encore démarrée

## Suivi

Mettre à jour les cases `[ ]` → `[x]` au fur et à mesure que les sous-tâches sont validées. Quand toutes les sous-tâches d'une phase sont cochées, changer le statut de la phase de 📋 → ✅ et passer la suivante en 🚧.
