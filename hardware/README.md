# Hardware -- PCB Quoridor

Source de vérité pour la carte électronique commandée par Jean (jeanrdc) le **2026-04-28**.

## Fichiers

| Fichier | Rôle |
|---------|------|
| [PCB_PCB_mecatronique_2026-04-28.json](PCB_PCB_mecatronique_2026-04-28.json) | Export EasyEDA de la PCB commandée -- source de vérité |
| [AUDIT_PCB_V2.md](AUDIT_PCB_V2.md) | Audit détaillé v2 (mapping pins, anomalies relevées, BOM, comparatif v1/v2) |

## État de la carte

- PCB v2, identique au JSON ci-dessus, **commandée telle quelle**
- Architecture : ESP32-WROOM (Freenove) + Raspberry Pi via UART, MCP23017 pour 2× A4988 + NEMA 17, servo SG90, LEDs WS2812B, matrice boutons 6×6
- Anomalies de l'audit : **validées par Jean d'après la datasheet ESP32** (pin 27 = GPIO output-capable, GPIO0 acceptable avec pull-up interne, polarité condo OK, A4988 ENABLE flottant = activé par défaut)

## Source de vérité ESP32

Pour toute question sur les GPIO, périphériques, strapping pins, ADC, RTC, capacités output/input, fréquences PWM : consulter le NotebookLM dédié plutôt que les mappings de cartes tierces.

- **NotebookLM** : `ESP32 Development Board Pinout Reference Map` (3 datasheets ESP32)
- **ID** : `7d0bccd1-df3f-456d-99a0-1192766043ba`
- **MCP** : `mcp__notebooklm-mcp__notebook_query`

## Vérifications physiques à la mise sous tension

Même si Jean a validé sur datasheet, les contrôles suivants restent à faire au premier branchement, en guise de filet de sécurité :

1. **Polarité physique du condensateur 10 µF** : bande blanche (`-`) côté GND. Si inversé, dessouder/retourner avant alimentation.
2. **GPIO de la pin 27 (LED data)** : flasher un sketch qui toggle GPIO25 et observer le pad. Confirmation finale du mapping.
3. **GPIO0 (BOUTON1) -- mode boot** : ne pas presser BOUTON1 au démarrage. Si comportement instable, ajouter une résistance pull-up 10 kΩ vers 3.3V en fil volant.
