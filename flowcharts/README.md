# flowcharts — Documentation visuelle

Diagrammes Mermaid décrivant l'architecture et la logique du projet Quoridor. Lisibles directement dans GitHub, VSCode (extension Markdown Preview) ou tout éditeur avec rendu Mermaid.

## Fichiers

| Fichier | Contenu |
|---------|---------|
| `01_vue_generale.md` | Flux complet du programme : du lancement à la fin de partie, boucle de jeu, gestion PvP et PvIA |
| `02_logique_ia.md` | Algorithme Minimax avec élagage alpha-bêta, fonction d'évaluation heuristique, table de transposition |
| `03_logique_jeu.md` | Règles du jeu, validation des déplacements, validation des murs, condition de victoire |
| `04_plateau.md` | Structure de `GameState`, système de coordonnées, conversion notation utilisateur ↔ interne, affichage ASCII 11×11 |

## Ordre de lecture conseillé

1. `01_vue_generale.md` — pour comprendre le programme dans son ensemble
2. `03_logique_jeu.md` — pour comprendre les règles et le moteur
3. `04_plateau.md` — pour comprendre la représentation des données
4. `02_logique_ia.md` — pour comprendre l'intelligence artificielle
