# Hardware

## État actuel — pivot breadboard (2026-05-19)

La PCB v2 commandée le 2026-04-28 a été **abandonnée** après réception. Le pivot se fait sur **breadboard** avec les composants physiques conservés.

**Raisons de l'abandon** (détails complets dans [hardware/archive/pcb-v2-2026-04-28-ABANDONNEE/POSTMORTEM.md](../hardware/archive/pcb-v2-2026-04-28-ABANDONNEE/POSTMORTEM.md)) :

- Confusion **PCA9548A** (mux I2C 8 canaux, reçu) vs **MCP23017** (GPIO expander 16 bits, spécifié). Le PCA9548A ne peut pas piloter STEP/DIR/EN des A4988.
- Conflits de pins ESP32 sur le routage v2 : GPIO27 partagé LED data / ROW_2 matrice, GPIO16/17 (UART2) consommés par la matrice boutons, A4988 ENABLE non câblé, GPIO0 strapping dans la matrice.
- `MotionControl` du firmware Plan 1 jamais validé sur cible (stub `sleep(1s)` + DONE).
- Calendrier démo incompatible avec un nouveau spinning PCB v3.

## Périmètre du bring-up breadboard

| Composant | Quantité | Rôle |
|---|---|---|
| ESP32-WROOM (Freenove DevKit) | 1 | Microcontrôleur principal, UART0 vers RPi |
| Driver A4988 | 2 | Pilotage des steppers |
| Moteur stepper NEMA17 | 2 | Système CoreXY (déplacement piston sous plateau) |
| Servo (SG90 ou équivalent) | 1 | Mécanisme de placement / réinitialisation des murs |
| Fin de course | 2 | Limite haute / basse du chariot CoreXY |
| Alimentation 12V (via transfo) | 1 | V_MOT des A4988 |

**Mis de côté** : PCA9548A (usage futur incertain), PCB v2 physique (récupération éventuelle de connecteurs).

## Mapping pins ESP32 (proposé pour la session bring-up)

Voir [docs/superpowers/specs/2026-05-19-bringup-breadboard-design.md](superpowers/specs/2026-05-19-bringup-breadboard-design.md) (créée pour la session bring-up). Choix sans strapping pins, sans pin USB partagée, avec pull-up interne pour les fins de course.

| Fonction | GPIO | Note |
|---|---|---|
| STEP M1 | 14 | output safe |
| DIR M1 | 27 | output safe |
| STEP M2 | 26 | output safe |
| DIR M2 | 25 | output safe |
| ENABLE (commun M1+M2) | 33 | actif LOW |
| SERVO (PWM/LEDC) | 32 | |
| LIMIT 1 | 13 | INPUT_PULLUP, switch → GND |
| LIMIT 2 | 18 | INPUT_PULLUP, switch → GND |
| LED debug intégrée | 2 | Pour diagnostics visuels (cf. `Pins.h`) |

## Règles critiques au câblage A4988

À répéter à chaque montage breadboard :

1. **Condensateur 100 µF entre VMOT et GND** par A4988 — obligatoire, sinon spike de tension au démarrage peut tuer le driver.
2. **Régler Vref AVANT** de brancher le moteur. Moteur déconnecté, alim 12V on, mesurer entre la vis du potentiomètre et GND, viser ~0,4 V (≈ 0,5 A par bobine) pour les tests à vide. Couper l'alim avant de brancher le moteur.
3. **Ne JAMAIS débrancher ou rebrancher un moteur quand 12V est ON** — back-EMF, driver fritté instantanément.
4. **Masses communes** : GND ESP32 et GND alim 12V doivent être reliés sur le même rail. Sinon le STEP/DIR n'a pas de référence.
5. **Câbler ENABLE** (pas le laisser flottant) : sinon les moteurs restent alimentés en permanence et chauffent.

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

## Pour aller plus loin

- [05_firmware.md](05_firmware.md) — architecture FSM du firmware (la couche logique reste valide)
- [02_architecture.md](02_architecture.md) — vue d'ensemble système (RPi ↔ ESP32 via UART)
- [hardware/archive/pcb-v2-2026-04-28-ABANDONNEE/](../hardware/archive/pcb-v2-2026-04-28-ABANDONNEE/) — archive complète PCB v2 (audit + JSON EasyEDA + postmortem)
