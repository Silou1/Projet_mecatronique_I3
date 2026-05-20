# Spec — Bring-up hardware breadboard

> **Status : CLOSED** — Bring-up validé le 2026-05-20.
>
> Voir [2026-05-20-bringup-breadboard-validation.md](2026-05-20-bringup-breadboard-validation.md) pour l'état final.
>
> Ce design est conservé à titre historique. Notable : la migration de drivers a fait des allers-retours (A4988 → L298N → DRV8825 → L298N final). Les sketches DRV8825 sont archivés dans `firmware/src/archive/drv8825-2026-05-20/`. Les modules Plan 2 sont archivés dans `firmware/archive_plan1_pcb_v2/src_plan2/`.

> **Date** : 2026-05-19
> **Statut** : design figé, prêt pour implémentation dans une nouvelle session
> **Branche** : à créer (ex. `feat/bringup-breadboard`) depuis `cleanup/reset-bringup-breadboard`

## Context

La PCB v2 commandée le 2026-04-28 a été abandonnée le 2026-05-19 (postmortem détaillé : [hardware/archive/pcb-v2-2026-04-28-ABANDONNEE/POSTMORTEM.md](../../../hardware/archive/pcb-v2-2026-04-28-ABANDONNEE/POSTMORTEM.md)). Causes principales : confusion PCA9548A (mux I2C 8 canaux) vs MCP23017 (GPIO expander 16 bits), conflits pins ESP32 sur le routage, MotionControl jamais validé sur cible.

Le bring-up se refait sur **breadboard** avec les composants physiques conservés et un mapping pins libre. L'objectif de cette session de bring-up est de valider la chaîne moteurs / servo / fins de course **en standalone**, sans encore intégrer le résultat dans le firmware FSM (qui reste préservé en stub).

## Périmètre

**In-scope** : 2× moteurs steppers via 2× A4988, 1× servo (mécanisme placement murs), 2× fins de course (un par axe CoreXY).

**Out-of-scope** :
- Pilotage CoreXY coordonné (mouvements en diagonale, recalage X/Y) — viendra en P11
- Homing automatique avec recul calibré — P11
- Intégration dans GameController FSM (`MotionControl::postCommand` réel) — P11
- Matrice boutons, LEDs WS2812B — pas requis pour la démo P0
- PCA9548A (mux I2C) — mis de côté, pas dans la chaîne

## Composants requis

| Composant | Quantité | Point critique |
|---|---|---|
| ESP32-WROOM (Freenove DevKit) | 1 | Câble USB-A pour flash + serial |
| Driver A4988 | 2 | **Vref à régler avant tout branchement moteur** |
| Stepper NEMA17 (4 fils) | 2 | Convention couleurs StepperOnline : noir/vert = bobine A, rouge/bleu = bobine B |
| Servo SG90 (ou MG90S) | 1 | Alim **5V**, pas 3.3V |
| Switch fin de course | 2 | NO (Normally Open) recommandé, tirage à GND quand pressé |
| Alim 12V (transfo) | 1 | Pour V_MOT des A4988 uniquement |
| **Condensateur 100 µF / 25V électrolytique** | 2 | **1 par A4988** entre VMOT et GND, polarité respectée |
| Breadboard | 1 grande (ou 2 petites) | |
| Câbles Dupont mâle-mâle + mâle-femelle | ~30 | |
| Multimètre | 1 | Indispensable pour régler Vref |
| Petit tournevis céramique/plastique | 1 | Pour régler le potentiomètre Vref sans court-circuit |

## Mapping pins ESP32 proposé

Choix sans strapping pins (0, 2, 5, 12, 15), sans pin UART USB (1, 3), pas d'input-only (34–39) pour les outputs. Inputs sur pins qui supportent le pull-up interne.

| Fonction | GPIO | Type | Note |
|---|---|---|---|
| STEP M1 | 14 | output | Safe, ni strapping ni USB |
| DIR M1 | 27 | output | Safe |
| STEP M2 | 26 | output | Safe |
| DIR M2 | 25 | output | Safe |
| ENABLE (commun M1+M2) | 33 | output | Actif LOW, drivers OFF par défaut au boot |
| SERVO | 32 | PWM (LEDC) | Tension signal 3.3V ok pour SG90 |
| LIMIT 1 | 13 | input | `INPUT_PULLUP`, switch entre GPIO et GND |
| LIMIT 2 | 18 | input | `INPUT_PULLUP`, switch entre GPIO et GND |

Total : 6 outputs + 1 PWM + 2 inputs = 9 pins ESP32. Marge confortable pour ajouter scan boutons ou LEDs plus tard.

## Procédure de câblage breadboard

### Étape 0 — Rails d'alimentation (5 min)

- Rail rouge breadboard = +12V (vers le transfo)
- Rail bleu breadboard = GND
- Brancher GND ESP32 sur le rail bleu — **masses communes obligatoires**, sinon STEP/DIR n'a pas de référence
- ⚠️ Ne PAS encore alimenter le 12V

### Étape 1 — A4988 moteur 1 (10 min)

- Plug du driver à cheval sur la breadboard, attention au sens (VMOT/GND en haut sur la plupart des modules)
- **Condensateur 100 µF entre VMOT (pin 1) et GND, polarité respectée** (+ vers VMOT)
- VMOT → rail +12V, GND (pin 2) → rail bleu
- VDD logique (pin 16) → 3.3V de l'ESP32
- GND logique (pin 15) → rail bleu
- STEP → GPIO 14, DIR → GPIO 27
- ENABLE → GPIO 33 (actif LOW)
- **MS1/MS2/MS3 non connectés** pour l'instant → full step (200 pas/tour)
- **RESET et SLEEP reliés ensemble** (jumper court) sinon le driver reste en sleep
- 1A/1B/2A/2B → les 4 fils du moteur 1, **mais NE PAS brancher le moteur encore**

### Étape 2 — Réglage Vref M1 (5 min, critique)

- Moteur **déconnecté**, alimenter 12V
- Multimètre : mesurer entre la vis du potentiomètre du A4988 et GND
- Régler à ~0,4 V avec un tournevis céramique/plastique → ~0,5 A par bobine (suffisant à vide, ne chauffe pas)
- **Couper l'alim 12V**, puis connecter le moteur

### Étape 3 — A4988 moteur 2

Idem étapes 1+2, avec STEP → GPIO 26, DIR → GPIO 25, ENABLE partagé sur GPIO 33

### Étape 4 — Servo

- Signal sur GPIO 32
- V+ sur **+5V** de l'ESP32 (pas 3.3V, le servo tire trop)
- GND sur rail bleu

### Étape 5 — Fins de course

- Chaque switch entre son GPIO (13 ou 18) et le rail GND
- Code activera `INPUT_PULLUP`
- Lecture LOW = switch pressé

## Règles critiques (à NE JAMAIS oublier)

1. **Ne JAMAIS débrancher/rebrancher un moteur stepper quand 12V est ON** → back-EMF, driver fritté instantanément.
2. **Condo 100 µF obligatoire par A4988** entre VMOT et GND.
3. **Régler Vref AVANT** de brancher le moteur. Moteur déconnecté pendant le réglage.
4. **Masses communes** : GND ESP32 + GND alim 12V sur le même rail.
5. **ENABLE câblé** (pas flottant) : sinon moteurs alimentés en permanence.

## Architecture du sketch de test

**Choix** : un sketch unique piloté par **commandes série**, flashé une seule fois. Itération uniquement en tapant des commandes dans `pio device monitor`. Beaucoup plus rapide qu'un sketch par composant.

### Commandes série

| Commande | Effet |
|---|---|
| `M1 F <n>` | Moteur 1, forward, n pas (ex. `M1 F 200`) |
| `M1 B <n>` | Moteur 1, backward, n pas |
| `M2 F <n>` / `M2 B <n>` | Idem pour moteur 2 |
| `SERVO <angle>` | Position du servo en degrés (0–180) |
| `LIMITS` | Lecture instantanée des 2 fins de course (affiche `L1=HIGH/LOW L2=HIGH/LOW`) |
| `LIMITS WATCH` | Lecture en boucle (~10 Hz), affiche les changements d'état ; Ctrl+C ou reset pour arrêter |
| `EN ON` | Active les drivers (ENABLE = LOW) |
| `EN OFF` | Désactive les drivers (ENABLE = HIGH) — état au boot |
| `SPEED <us>` | Demi-période de STEP en microsecondes (ex. `SPEED 1000` = 1 kHz, lent). Par défaut 1000. |
| `HELP` | Liste les commandes |

### Paramètres par défaut

- `EN OFF` au boot (drivers off, sécurité)
- `SPEED = 1000 µs` (1 kHz = lent, ~5 rev/s en full-step)
- Direction initiale arbitraire (sera mesurée et notée dans la doc)

### Organisation des fichiers

- **`firmware/test_bringup/`** : nouveau dossier
  - **`bringup_main.cpp`** : sketch unique (setup, loop, parser série, fonctions M1/M2/SERVO/LIMITS/EN)
  - **`README.md`** : recap mapping pins + commandes + notes de calibration mesurées (Vref M1, Vref M2, sens initiaux, etc.)
- **`firmware/platformio.ini`** : ajouter un nouvel environnement isolé :
  ```ini
  [env:test_bringup]
  platform = espressif32
  board = esp32dev
  framework = arduino
  monitor_speed = 115200
  upload_speed = 460800
  monitor_filters = direct
  src_dir = test_bringup
  ```
  L'env par défaut `[env:esp32dev]` reste sur le firmware Plan 1 (FSM, UartLink, etc.) — pas de collision.

Commandes :
- `pio run -e test_bringup -t upload` pour flasher le sketch de test
- `pio run -e esp32dev -t upload` pour rebasculer sur le firmware FSM Plan 1
- `pio device monitor` pour ouvrir le serial (115200, LF)

## Critères de succès (par étape)

À cocher au fur et à mesure pendant la session bring-up :

- [ ] **a)** `M1 F 200` fait tourner M1 d'un quart de tour visible, dans un sens. `M1 B 200` revient en arrière. Pas de pas sautés (vérification visuelle ou avec un repère collé sur l'arbre).
- [ ] **b)** Idem pour M2.
- [ ] **c)** `SERVO 0`, `SERVO 90`, `SERVO 180` font atteindre les positions correspondantes. La course angulaire couvre bien le désengagement des loquets.
- [ ] **d)** `LIMITS` au repos affiche `L1=HIGH L2=HIGH` (pull-up actif, switches relâchés). Appuyer L1 manuellement → `L1=LOW L2=HIGH`. Relâcher → `L1=HIGH`. Idem L2.
- [ ] **e)** `LIMITS WATCH` détecte les transitions à l'appui/relâchement sans bounce visible.

Si toutes les cases sont cochées : bring-up validé, on peut passer à P11 (intégration au GameController FSM).

## Sécurité électrique — résumé

Avant chaque session de test :
1. Vérifier visuellement les condensateurs (polarité, pas de fuite)
2. Vérifier le rail GND commun
3. Vérifier Vref des 2 drivers (mesure rapide multimètre, moteurs déconnectés, alim on)
4. Toujours `EN OFF` au boot (drivers neutralisés)

Avant de débrancher quoi que ce soit côté moteur : **couper l'alim 12V**. Toujours.

## Prochaines étapes après cette session

1. Mettre à jour `firmware/test_bringup/README.md` avec les valeurs réelles mesurées (Vref, sens, vitesses limites avant pas perdus, course servo)
2. Mettre à jour `docs/07_hardware.md` avec le mapping pins définitif
3. Commit `feat(firmware): bring-up breadboard validé (M1 + M2 + servo + 2 fins de course)`
4. Démarrer P11 (porter dans `MotionControl.cpp` réel, intégré au GameController FSM)

## Pointeurs

- [hardware/archive/pcb-v2-2026-04-28-ABANDONNEE/POSTMORTEM.md](../../../hardware/archive/pcb-v2-2026-04-28-ABANDONNEE/POSTMORTEM.md) : raisons de l'abandon PCB v2
- [firmware/archive_plan1_pcb_v2/Pins.h.original](../../../firmware/archive_plan1_pcb_v2/Pins.h.original) : ancien mapping pins (référence)
- [docs/05_firmware.md](../../05_firmware.md) : architecture FSM du firmware (préservée)
- [docs/06_protocole_uart.md](../../06_protocole_uart.md) : protocole UART (préservé)
- Datasheet A4988 : https://www.pololu.com/file/0J450/a4988.pdf
- Datasheet ESP32 (NotebookLM) : `ESP32 Development Board Pinout Reference Map` (id `7d0bccd1-df3f-456d-99a0-1192766043ba`)
