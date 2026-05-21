# Archive — flowcharts pré-2026-05-20

Ce dossier contient les diagrammes Mermaid de l'architecture **avant le
pivot du 2026-05-20**. Ils décrivent une architecture qui n'est plus
utilisée dans le projet :

- **Raspberry Pi 3/4** comme contrôleur principal (Python + IA + webapp)
- **ESP32** comme firmware temps réel, relié à la RPi via **UART**
- **Protocole Plan 2** : trames texte avec CRC-16 CCITT-FALSE, séquencement,
  handshake `HELLO`/`HELLO_ACK`, codes NACK typés
- **Matrice de boutons 6×6** comme interface d'entrée principale, avec
  flux `MOVE_REQ` / `WALL_REQ` côté ESP32 → ACK / NACK côté RPi
- Fichiers Python aujourd'hui supprimés : `quoridor_engine/uart_client.py`,
  `quoridor_engine/game_session.py`

Voir [`docs/decisions.md`](../../../decisions.md) pour le détail des
pivots qui ont rendu ces flowcharts obsolètes :

- **2026-05-19** : abandon PCB v2 → retour breadboard
- **2026-05-20** : abandon RPi + Plan 2 UART CRC-16 → Mac + Wi-Fi +
  protocole texte simple
- **2026-05-21** : abandon boutons matrice → UI 100% smartphone

Pour les flowcharts à jour, voir [`docs/flowcharts/`](../../).

## Fichiers archivés

| Fichier | Contenu d'origine |
|---|---|
| `01_vue_generale.md` | Architecture RPi + ESP32 + Plan 2 UART |
| `05_firmware_esp32.md` | Firmware sous Plan 2, cycle bouton appui → MOVE_REQ |
| `06_protocole_uart.md` | Format trames CRC-16, handshake HELLO, NACK codes |
| `07_webapp_flux.md` | Webapp servie par la RPi (avant le passage Mac) |

Ces fichiers sont gardés **tels quels** comme témoins historiques. Ne pas
les éditer : pour modifier la doc actuelle, éditer les fichiers du dossier
parent.
