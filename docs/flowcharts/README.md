# flowcharts — Documentation visuelle

Diagrammes Mermaid décrivant l'architecture, la logique logicielle et la chaîne matérielle du projet Quoridor mécatronique. Lisibles directement dans GitHub, VSCode (extension Markdown Preview Mermaid) ou tout éditeur avec rendu Mermaid.

## Fichiers

| Fichier | Contenu | Couche |
|---------|---------|--------|
| `01_vue_generale.md` | Architecture globale RPi + ESP32 + webapp. Les trois modes (console, webapp, plateau). Boucle de jeu commune. | Système complet |
| `02_logique_ia.md` | Algorithme Minimax + élagage alpha-bêta + iterative deepening. Fonction d'évaluation heuristique. Table de transposition. Optimisations. | IA Python |
| `03_logique_jeu.md` | Validation des déplacements (avec sauts et diagonales). Validation des murs (géométrie + BFS chemin). Condition de victoire. | Moteur Python |
| `04_plateau.md` | Structure de `GameState` immuable. Historique pour l'undo. Conversion notation utilisateur ↔ interne. Affichage ASCII 11×11. | Représentation données |
| `05_firmware_esp32.md` | Bring-up CoreXY (boot auto, HOME X/Y, boucle commandes série). Cycle de placement d'un mur. Pins et contraintes. | Firmware Arduino C++ |
| `06_protocole_uart.md` | Format des trames + CRC-16. Handshake HELLO/HELLO_ACK. Cycle coup IA / coup humain. Catalogue NACK. Gestion des erreurs. | Communication |
| `07_webapp_flux.md` | Architecture FastAPI + frontend SVG. Endpoints HTTP. Flux coup humain et coup IA via tick thread. Mode hybride avec plateau. | Webapp |

## Ordre de lecture conseillé

1. `01_vue_generale.md` — pour comprendre l'ensemble du système
2. `03_logique_jeu.md` — pour comprendre les règles et le moteur Python
3. `04_plateau.md` — pour comprendre la représentation des données
4. `02_logique_ia.md` — pour comprendre l'intelligence artificielle
5. `07_webapp_flux.md` — pour comprendre la couche webapp (mode démo principal)
6. `05_firmware_esp32.md` — pour comprendre le bas niveau (ESP32 + moteurs)
7. `06_protocole_uart.md` — pour comprendre le dialogue RPi ↔ ESP32

## Pour exporter en image (rapport)

Pour intégrer ces diagrammes en PNG/SVG dans un rapport Word ou LibreOffice :

- **mermaid.live** : coller le bloc ``` mermaid ``` et exporter en PNG/SVG.
- **VSCode** : extension *Markdown PDF* avec rendu Mermaid activé.
- **CLI** : `mermaid-cli` (`mmdc -i flowchart.md -o flowchart.png`).
