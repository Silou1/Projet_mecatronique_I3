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

## ⏸️ Note d'avancement — 2026-05-01

Le DevKit ESP32 n'est pas disponible avant **lundi 2026-05-04** (prêté à un camarade). Pour ne pas perdre le week-end, on **suspend P6** et on **bascule sur P8** (Protocole UART Plan 2), entièrement réalisable sans hardware :

- **P8.1–P8.5** sont du design + code Python + compilation firmware (pas besoin de flasher)
- **P8.6** (tests d'intégration sur vrai port série) reste reporté à lundi avec P6 et P7

Ordre de travail temporaire : **P8.1 → P8.2 → P8.4 → P8.3 → P8.5**, puis on revient sur P6 / P7 / P8.6 au retour du DevKit.

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

### P6 — Setup environnement firmware ⏸️

> But : pouvoir compiler, flasher et observer la sortie série du DevKit depuis le Mac.
>
> **En pause** jusqu'au retour du DevKit (lundi 2026-05-04). Voir note d'avancement ci-dessus.

- [ ] **P6.1** Brancher l'ESP32 DevKit au Mac via USB
- [ ] **P6.2** Installer le driver USB-série (CP210x ou CH340 selon le module)
- [ ] **P6.3** Vérifier la détection du port (`pio device list`)
- [ ] **P6.4** Compiler et flasher Plan 1 (`cd firmware && pio run -t upload`)
- [ ] **P6.5** Ouvrir le Serial Monitor (`pio device monitor`) et observer la séquence de boot

### P7 — Validation Plan 1 sur cible 📋

> But : exécuter les 7 scénarios FSM Plan 1 sur un DevKit branché, corriger les éventuels bugs résiduels, et marquer le Plan 1 comme validé bout-en-bout.
> Les scénarios sont décrits dans [docs/superpowers/plans/2026-04-28-firmware-esp32-plan-1-squelette.md](superpowers/plans/2026-04-28-firmware-esp32-plan-1-squelette.md) (Task 9). Le harness `firmware/TESTS_PENDING.md` a été retiré lors du cleanup 2026-05-19 (cf. `firmware/archive_plan1_pcb_v2/`).

- [ ] **P7.1** Scénario 1 — boot nominal vers `DEMO`
- [ ] **P7.2** Scénario 2 — boot nominal vers `CONNECTED` (`HELLO_ACK`)
- [ ] **P7.3** Scénario 3 — cycle de jeu simulé complet (`BTN`, `ACK`, `NACK`, `CMD MOVE`)
- [ ] **P7.4** Scénario 4 — perte UART en `CONNECTED` (3 s de silence)
- [ ] **P7.5** Scénario 5 — escalade timeout intent (3 timeouts → `ERROR`)
- [ ] **P7.6** Scénario 6 — récupération depuis `ERROR` (`RESET`)
- [ ] **P7.7** Scénario 7 — watchdog (provocation contrôlée)
- [ ] **P7.8** Couverture du spec (Scénario 8) — cocher tous les états et transitions
- [ ] **P7.9** Identifier et corriger les bugs trouvés (commits de correctifs)
- [ ] **P7.10** Commit `test(firmware): plan 1 valide en bout-en-bout sur cible`

### P8 — Protocole UART Plan 2 ✅

> But : remplacer le protocole texte stub du Plan 1 par un protocole final (binaire ou texte enrichi avec framing + intégrité), implémenté côté ESP32 *et* côté Python.

- [x] **P8.1** Designer le protocole final — trancher : framing (COBS, SLIP, longueur fixe ?), intégrité (CRC-8/16, checksum XOR ?), versioning, ID de séquence (questions ouvertes dans [06_protocole_uart.md](06_protocole_uart.md))
- [x] **P8.2** Documenter le protocole arrêté dans [06_protocole_uart.md](06_protocole_uart.md)
- [x] **P8.3** Refactor [firmware/src/UartLink.{cpp,h}](../firmware/src/) pour implémenter le protocole final
- [x] **P8.4** Créer un module Python client UART (probablement `quoridor_engine/uart_client.py` ou `interface/uart.py`)
- [x] **P8.5** Tests unitaires côté Python (avec serial loopback ou ESP32 DevKit en mode echo)
- [x] **P8.6** Tests d'intégration ESP32 DevKit ↔ Python : envoi/réception de toutes les trames *(sc 1-8 valides via `firmware/tests_devkit/run_p86_manual.py` puis portes en pytest dans [`tests/integration/test_uart_devkit.py`](../tests/integration/test_uart_devkit.py) avec marqueur `@pytest.mark.devkit` — 2026-05-06)*

### P9 — Intégration logicielle RPi ↔ ESP32 🚧

> But : faire dialoguer `quoridor_engine` avec l'ESP32 DevKit via UART. Mode plateau-physique-en-simulation, sans périphériques réels.
>
> **Note d'avancement — 2026-05-04 :** P9 est implémentée côté logiciel testable sans matériel : P9.1 à P9.4 et P9.6 sont complètes. Le détail suit [`docs/superpowers/plans/2026-05-03-p9-integration-rpi-esp32.md`](superpowers/plans/2026-05-03-p9-integration-rpi-esp32.md). **P9.5** reste ouverte : tests E2E sur DevKit physique, checklist dans [`firmware/archive_plan1_pcb_v2/INTEGRATION_TESTS_PENDING.md`](../firmware/archive_plan1_pcb_v2/INTEGRATION_TESTS_PENDING.md) (archivée lors du cleanup 2026-05-19 mais toujours valable comme référence des scénarios).

- [x] **P9.1** Adapter [main.py](../main.py) pour offrir un mode « plateau physique » en plus du mode console
- [x] **P9.2** Implémenter le flux entrant : Python attend `MOVE_REQ` → valide via `QuoridorGame` → renvoie `ACK` ou `NACK`
- [x] **P9.3** Implémenter le flux sortant : Python envoie `CMD MOVE` / `CMD WALL` pour les coups joués par l'IA, puis `CMD GAMEOVER`
- [x] **P9.4** Côté ESP32 (DevKit), conserver les boutons en mode injection (commande `BTN x y` via Serial) et les LEDs/moteurs en stub (logs uniquement)
- [ ] **P9.5** Tests d'intégration end-to-end : partie complète PvIA via UART avec ESP32 DevKit *(hardware requis)*
- [x] **P9.6** Mettre à jour [02_architecture.md](02_architecture.md) et [06_protocole_uart.md](06_protocole_uart.md)

---

## Bloc Hardware — bring-up breadboard

> **2026-05-19** : PCB v2 abandonnée (postmortem dans [hardware/archive/pcb-v2-2026-04-28-ABANDONNEE/POSTMORTEM.md](../hardware/archive/pcb-v2-2026-04-28-ABANDONNEE/POSTMORTEM.md)). Pivot vers breadboard avec composants conservés.

### P10 — Bring-up breadboard 🚧

> But : valider la chaîne moteurs / servo / fins de course sur breadboard, sans la PCB. Périmètre minimal pour démontrer la mécanique.
>
> Spec et procédure détaillées : [docs/superpowers/specs/2026-05-19-bringup-breadboard-design.md](superpowers/specs/2026-05-19-bringup-breadboard-design.md).

- [ ] **P10.1** Câblage breadboard : rails 12V / GND, A4988 M1 (+ condo 100 µF), réglage Vref, A4988 M2, servo, 2 fins de course
- [ ] **P10.2** Sketch de test isolé dans `firmware/test_bringup/` (env `[env:test_bringup]` PlatformIO), piloté par commandes série
- [ ] **P10.3** Test M1 — rotation 200 pas avant/arrière, vérifier sens et absence de pas perdus
- [ ] **P10.4** Test M2 — idem
- [ ] **P10.5** Test servo — positions 0° / 90° / 180°, course angulaire de désengagement des loquets
- [ ] **P10.6** Test fin de course 1 — appui main → lecture LOW, polarité confirmée
- [ ] **P10.7** Test fin de course 2 — idem
- [ ] **P10.8** Mettre à jour [07_hardware.md](07_hardware.md) avec les pins réellement utilisées et les Vref mesurés

### P11 — Drivers firmware intégrés au GameController 📋

> But : porter le sketch bring-up en modules réutilisables (`MotionControl`, `Servo`, `LimitSwitch`) intégrés dans la FSM existante.

- [ ] **P11.1** Réécrire `firmware/src/MotionControl.cpp` pour piloter réellement les 2× A4988 (interface `Command` / `Result` conservée)
- [ ] **P11.2** Ajouter module servo dans le firmware
- [ ] **P11.3** Ajouter lecture des fins de course (interrupt-driven ou polling)
- [ ] **P11.4** Routine de homing complète (recul après détection)
- [ ] **P11.5** Mapping mm → pas, vitesse, accélération, calibration sur mécanique 3D réelle
- [ ] **P11.6** Coordonnées XY de chaque slot de mur (table de lookup)
- [ ] **P11.7** Mettre à jour [05_firmware.md](05_firmware.md) avec l'architecture des nouveaux modules

### P12 — Logique de jeu complète sur plateau 📋

> But : assembler tous les morceaux. Le flux complet « commande IA → moteurs → mur monte → servo réinitialise » fonctionne bout-en-bout sur breadboard + mécanique 3D.

- [ ] **P12.1** Sur `CMD MOVE` reçu : ESP32 commande déplacement piston via `MotionControl::postCommand`
- [ ] **P12.2** Sur `CMD WALL` : déplacement + push mur via servo
- [ ] **P12.3** Tour de l'IA : Python envoie `CMD` → ESP32 exécute
- [ ] **P12.4** Gestion fin de partie : déclenchement servo de réinitialisation des murs
- [ ] **P12.5** Mode démo PvIA fluide bout-en-bout
- [ ] **P12.6** (Optionnel) ajouter scan boutons et LEDs si calendrier le permet

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
- ⏸️ **en pause** — démarrée mais bloquée (hardware indisponible, dépendance externe…)
- 📋 **à faire** — pas encore démarrée

## Suivi

Mettre à jour les cases `[ ]` → `[x]` au fur et à mesure que les sous-tâches sont validées. Quand toutes les sous-tâches d'une phase sont cochées, changer le statut de la phase de 📋 → ✅ et passer la suivante en 🚧.
