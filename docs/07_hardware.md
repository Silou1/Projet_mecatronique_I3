# Hardware

## État actuel — pivot breadboard (2026-05-19, validé 2026-05-20)

La PCB v2 commandée le 2026-04-28 a été **abandonnée** après réception. Le pivot se fait sur **breadboard** avec les composants physiques conservés.

**Raisons de l'abandon** (détails complets dans [hardware/archive/pcb-v2-2026-04-28-ABANDONNEE/POSTMORTEM.md](../hardware/archive/pcb-v2-2026-04-28-ABANDONNEE/POSTMORTEM.md)) :

- Erreur de composant (expander reçu non compatible avec le pilotage STEP/DIR/EN des drivers steppers initialement spécifiés). Détails dans le postmortem.
- Conflits de pins ESP32 sur le routage v2 : GPIO27 partagé LED data / ROW_2 matrice, GPIO16/17 (UART2) consommés par la matrice boutons, driver stepper ENABLE non câblé, GPIO0 strapping dans la matrice.
- `MotionControl` du firmware Plan 1 jamais validé sur cible (stub `sleep(1s)` + DONE).
- Calendrier démo incompatible avec un nouveau spinning PCB v3.

## Périmètre du bring-up breadboard

| Composant | Quantité | Rôle |
|---|---|---|
| ESP32-WROOM (Freenove DevKit) | 1 | Microcontrôleur principal, UART0 vers RPi |
| Driver L298N | 2 | Pilotage des steppers (full-step 4-phase, ENA/ENB PWM) |
| Moteur stepper NEMA17 | 2 | Système CoreXY (déplacement piston sous plateau) |
| Servo (SG90 ou équivalent) | 1 | Mécanisme de placement / réinitialisation des murs |
| Fin de course | 2 | Limite haute / basse du chariot CoreXY |
| Alimentation 12V (via transfo) | 1 | V_MOT des L298N |

**Mis de côté** : composants PCB v2 (PCB physique conservée pour récupération éventuelle de connecteurs).

## Mapping pins ESP32 (validé 2026-05-20)

| Fonction | GPIO | Note |
|---|---|---|
| M1 (L298N #1) IN1 | 14 | bobine A |
| M1 (L298N #1) IN2 | 27 | bobine A |
| M1 (L298N #1) IN3 | 26 | bobine B |
| M1 (L298N #1) IN4 | 25 | bobine B |
| M1 (L298N #1) ENA | 33 | PWM duty pour limitation courant |
| M1 (L298N #1) ENB | 32 | PWM duty pour limitation courant |
| M2 (L298N #2) IN1 | 16 | bobine A |
| M2 (L298N #2) IN2 | 17 | bobine A |
| M2 (L298N #2) IN3 | 21 | bobine B |
| M2 (L298N #2) IN4 | 22 | bobine B |
| M2 (L298N #2) ENA | 19 | PWM duty pour limitation courant |
| M2 (L298N #2) ENB | 23 | PWM duty pour limitation courant |
| Capteur fin de course X | 13 | INPUT_PULLUP, switch → GND |
| Capteur fin de course Y | 18 | INPUT_PULLUP, switch → GND |
| Servo SG90 (Signal) | 4 | V+ alim 5V externe, GND commun |
| LED debug intégrée | 2 | Diagnostics visuels |

## Conventions machine (validées 2026-05-20)

| Convention | Détail |
|---|---|
| Mouvement X pur | M1 et M2 sens **OPPOSÉS** (capteur X- = GPIO 13) |
| Mouvement Y pur | M1 et M2 **MÊME** sens (capteur Y- = GPIO 18) |
| Position servo REPOS (piston bas) | 180° |
| Position servo MUR LEVÉ (piston haut) | 0° |

## Calibration (validée 2026-05-20)

- **100 pas full-step = 2 cm** pile (X et Y, mesuré au mètre ruban)
- 1 cm = 50 pas
- 1 mm = 5 pas
- Course X mesurée : ~110 mm
- Course Y mesurée : ~101 mm

## Règles critiques au câblage L298N

À répéter à chaque montage breadboard :

1. **Jumpers ENA et ENB retirés** sur les 2 L298N — sans ça, l'ENA/ENB est court-circuité à 5V et le contrôle PWM ne marche pas.
2. **Jumper 5V_EN en place** sur les 2 L298N — alimente le régulateur 5V interne depuis le 12V VMOT.
3. **Alim 12V partagée** entre les 2 L298N, avec un condo 100 µF par L298N entre VMOT et GND si possible (sécurité spike).
4. **Masses communes** : GND ESP32 + GND alim 12V + GND alim 5V servo doivent être reliés sur le même rail.
5. **Tentative DRV8825** (matin 2026-05-20) : abandonnée après 2 cartes mortes sur 3. Sketches archivés dans `firmware/src/archive/drv8825-2026-05-20/`. Si tu réessaies un jour avec de nouveaux drivers : Vref = I × 5 × R_sense (R100 → Vref = I × 0.5), SLP/RST pontés au 3.3V, VDD non câblé (clones DRV8825 self-power via V3P3OUT interne).

## Source de vérité ESP32

Pour toute question sur les GPIO, périphériques, strapping pins, ADC, RTC, ou capacités output/input/PWM, consulter le NotebookLM dédié plutôt que les mappings de cartes tierces (Freenove DevKitC) qui peuvent diverger du SoC.

- **Notebook** : `ESP32 Development Board Pinout Reference Map`
- **ID** : `7d0bccd1-df3f-456d-99a0-1192766043ba`
- **MCP** : `mcp__notebooklm-mcp__notebook_query`

## Mécanique — Système de murs

Le mécanisme physique des murs est conçu en 4 niveaux empilés. Détails complets dans [notes/note_de_projet.md](notes/note_de_projet.md).

- **Niveau 1** : système CoreXY (2 moteurs NEMA 17 fixes, courroies croisées), porte un piston unique qui se déplace sous le plateau
- **Niveau 2** : stockage des murs non posés
- **Niveau 3** : verrouillage par loquets (murs poussés vers le haut, partiellement visibles)
- **Niveau 4** : surface de jeu (plateau visible)
- **Réinitialisation** : le servo désengage tous les loquets en fin de partie

### Matrices de positions des murs (sketch de production)

Le sketch [firmware/src/bringup_l298n_complet.cpp](../firmware/src/bringup_l298n_complet.cpp) contient deux matrices hand-fillable pour les 60 positions de murs du plateau 6×6 :

- `MURS_H[5][6]` : 30 positions de murs horizontaux (6 colonnes × 5 lignes entre les rangées)
- `MURS_V[6][5]` : 30 positions de murs verticaux (5 colonnes × 6 lignes entre les colonnes)

Chaque cellule contient les coordonnées (x, y) en pas full-step depuis l'origine HOME. Les positions non mesurées sont marquées `_NA` (sentinelle `{-1, -1}`). Au 2026-05-20, 18 positions sont mesurées (les 8 coins + 4 centres + 6 autres), 42 restent à mesurer manuellement.

Workflow de mesure : flash → HOME auto → naviguer manuellement avec commandes `X F/B <n>` et `Y F/B <n>` → `STATUS` → noter coordonnées → éditer le code → recompiler. Détails dans [docs/superpowers/specs/2026-05-20-bringup-breadboard-validation.md](superpowers/specs/2026-05-20-bringup-breadboard-validation.md).

## Pour aller plus loin

- [docs/superpowers/specs/2026-05-20-bringup-breadboard-validation.md](superpowers/specs/2026-05-20-bringup-breadboard-validation.md) — état validé bring-up 2026-05-20
- [05_firmware.md](05_firmware.md) — architecture FSM du firmware (la couche logique reste valide)
- [02_architecture.md](02_architecture.md) — vue d'ensemble système (RPi ↔ ESP32 via UART)
- [hardware/archive/pcb-v2-2026-04-28-ABANDONNEE/](../hardware/archive/pcb-v2-2026-04-28-ABANDONNEE/) — archive complète PCB v2 (audit + JSON EasyEDA + postmortem)
