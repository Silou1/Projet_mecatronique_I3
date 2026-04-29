# Hardware

Carte électronique du plateau Quoridor, conçue sur EasyEDA et fabriquée le **2026-04-28** (commande Jean / jeanrdc).

> **Documents de référence** dans [hardware/](../hardware/) :
> - [hardware/README.md](../hardware/README.md) — entrée hardware
> - [hardware/AUDIT_PCB_V2.md](../hardware/AUDIT_PCB_V2.md) — audit détaillé (mapping pins, anomalies, BOM)
> - [hardware/PCB_PCB_mecatronique_2026-04-28.json](../hardware/PCB_PCB_mecatronique_2026-04-28.json) — export EasyEDA (source de vérité)

## Architecture matérielle

| Composant | Rôle | Bus / signal |
|---|---|---|
| **ESP32-WROOM** (Freenove) | Microcontrôleur principal | UART0 vers RPi |
| **MCP23017** | Expandeur I2C 16 GPIO | I2C vers ESP32 |
| 2× **A4988** | Drivers moteurs pas-à-pas | GPIO via MCP23017 |
| 2× **NEMA 17** | Moteurs système XY (déplacement piston) | A4988 |
| **Servo SG90** | Rotation / réinitialisation murs | PWM ESP32 |
| **WS2812B** | LEDs adressables (cases interactives) | GPIO27 (data) |
| Matrice 6×6 | Boutons capacitifs (cases tactiles) | GPIO13-33 (rows), GPIO0-18 (cols) |

⚠️ **Note importante** : la PCB référence par erreur l'ESP32-**WROVER**, mais le module utilisé est en réalité l'**ESP32-WROOM** (pas de PSRAM, GPIO16/17 disponibles physiquement, mais consommés ici par la matrice boutons).

## Source de vérité ESP32

Pour toute question sur les GPIO, périphériques, strapping pins, ADC, RTC, ou capacités output/input/PWM, consulter le NotebookLM dédié plutôt que les mappings de cartes tierces (Freenove DevKitC) qui peuvent diverger du SoC.

- **Notebook** : `ESP32 Development Board Pinout Reference Map`
- **ID** : `7d0bccd1-df3f-456d-99a0-1192766043ba`
- **MCP** : `mcp__notebooklm-mcp__notebook_query`

## Vérifications physiques au premier branchement

Jean a validé toutes les anomalies de l'audit contre la datasheet ESP32, mais **avant la première mise sous tension**, contrôler manuellement :

1. **Polarité du condensateur 10 µF** : bande blanche (`-`) côté GND. Si inversé, dessouder/retourner avant alimentation.
2. **GPIO de la pin 27 (data WS2812B)** : flasher un sketch qui toggle la pin, mesurer au pad. Confirmation finale du mapping.
3. **GPIO0 (BOUTON1) au boot** : ne pas presser BOUTON1 au démarrage (strapping pin). Si comportement instable, ajouter une résistance pull-up 10 kΩ vers 3.3 V en fil volant.

Détails et schémas dans [hardware/AUDIT_PCB_V2.md](../hardware/AUDIT_PCB_V2.md).

## Mécanique — Système de murs

Le mécanisme physique des murs est conçu en 4 niveaux empilés. Détails complets dans [notes/note_de_projet.md](notes/note_de_projet.md).

- **Niveau 1** : système corps XY (2 moteurs NEMA 17), porte un piston unique qui se déplace sous le plateau
- **Niveau 2** : stockage des murs non posés
- **Niveau 3** : verrouillage par loquets (murs poussés vers le haut, partiellement visibles)
- **Niveau 4** : surface de jeu (plateau visible)
- **Réinitialisation** : un bouton actionne le servo qui désengage tous les loquets en fin de partie

## Pour aller plus loin

- [05_firmware.md](05_firmware.md) — comment le firmware pilote tout ça
- [02_architecture.md](02_architecture.md) — vue d'ensemble système
