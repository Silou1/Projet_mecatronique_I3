# flowcharts — Documentation visuelle

Diagrammes Mermaid décrivant l'architecture, la logique logicielle et la
chaîne matérielle du projet Quoridor mécatronique. Lisibles directement
dans GitHub, VSCode (extension Markdown Preview Mermaid) ou tout éditeur
avec rendu Mermaid.

Reflète l'architecture **après les pivots du 2026-05-20 et 2026-05-21**
(Mac + ESP32 + Wi-Fi/USB + UI 100 % webapp). Pour les flowcharts
historiques (architecture RPi + Plan 2 UART CRC-16 + boutons), voir
[`archive/pre-2026-05-20/`](archive/pre-2026-05-20/).

## Fichiers

| Fichier | Contenu | Couche |
|---------|---------|--------|
| `01_vue_generale.md` | Architecture globale Mac + ESP32 + webapp. Les quatre modes (autonome, dev, démo, console). Boucle de jeu commune. | Système complet |
| `02_logique_ia.md` | Algorithme Minimax + élagage alpha-bêta + iterative deepening. Fonction d'évaluation heuristique. Table de transposition. Optimisations. | IA Python |
| `03_logique_jeu.md` | Validation des déplacements (avec sauts et diagonales). Validation des murs (géométrie + BFS chemin). Condition de victoire. | Moteur Python |
| `04_plateau.md` | Structure de `GameState` immuable. Historique pour l'undo. Conversion notation utilisateur ↔ interne. Affichage ASCII 11×11. | Représentation données |
| `05_firmware_esp32.md` | Bring-up CoreXY (boot auto, HOME X/Y, boucle de commandes Serial+Wi-Fi). Cycle de placement d'un mur. Pinout. | Firmware Arduino C++ |
| `06_protocole.md` | Protocole texte ligne par ligne, identique USB et Wi-Fi. Handshake PING/PONG, commande WALL, commandes LED, gestion d'erreurs. | Communication |
| `07_webapp_flux.md` | Architecture FastAPI en couches. Routes HTTP. Flux coup humain et coup IA via tick thread. Bascule transport à chaud. | Webapp |

## Ordre de lecture conseillé

1. `01_vue_generale.md` — pour comprendre l'ensemble du système
2. `03_logique_jeu.md` — pour comprendre les règles et le moteur Python
3. `04_plateau.md` — pour comprendre la représentation des données
4. `02_logique_ia.md` — pour comprendre l'intelligence artificielle
5. `07_webapp_flux.md` — pour comprendre la couche webapp (interface
   principale)
6. `05_firmware_esp32.md` — pour comprendre le bas niveau (ESP32 +
   moteurs)
7. `06_protocole.md` — pour comprendre le dialogue Mac ↔ ESP32

## Pour exporter en image (rapport)

Pour intégrer ces diagrammes en PNG/SVG dans un rapport Word ou
LibreOffice :

- **mermaid.live** : coller le bloc ` ```mermaid ` et exporter en PNG/SVG.
- **VSCode** : extension *Markdown PDF* avec rendu Mermaid activé.
- **CLI** : `mermaid-cli` (`mmdc -i flowchart.md -o flowchart.png`).
