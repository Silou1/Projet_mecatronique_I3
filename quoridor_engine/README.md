# quoridor_engine — Moteur de jeu Quoridor

Package Python contenant toute la logique du jeu Quoridor : règles, état, déplacements, murs et intelligence artificielle.

## Fichiers

| Fichier | Rôle |
|---------|------|
| `core.py` | Moteur de jeu complet : constantes, `GameState` (état immuable), validation des déplacements et des murs, `QuoridorGame` (orchestration + historique) |
| `ai.py` | Intelligence artificielle : algorithme Minimax avec élagage alpha-bêta, BFS inversé pour le pathfinding, classe `AI` avec 3 niveaux de difficulté |
| `__init__.py` | Exports publics du package |

## Constantes clés (`core.py`)

```python
BOARD_SIZE = 6            # Plateau 6×6
MAX_WALLS_PER_PLAYER = 6  # Murs par joueur en début de partie
PLAYER_ONE = 'j1'         # Démarre en (5, 3), objectif : ligne 0
PLAYER_TWO = 'j2'         # Démarre en (0, 3), objectif : ligne 5
```

## Exports publics

```python
from quoridor_engine import QuoridorGame, GameState, InvalidMoveError, AI
```

| Symbole | Type | Description |
|---------|------|-------------|
| `QuoridorGame` | classe | Point d'entrée pour jouer : `play_move()`, `undo_move()`, `is_game_over()` |
| `GameState` | dataclass (frozen) | Snapshot immuable d'une partie : positions, murs, joueur courant |
| `InvalidMoveError` | exception | Levée si un coup viole les règles |
| `AI` | classe | IA avec `find_best_move(state)`, niveaux `facile` / `normal` / `difficile` |

## Exemple d'utilisation

```python
from quoridor_engine import QuoridorGame, AI, PLAYER_TWO

partie = QuoridorGame()
ia = AI(PLAYER_TWO, difficulty='normal')

# Joueur 1 avance
partie.play_move(('deplacement', (4, 3)))

# L'IA joue pour le joueur 2
meilleur_coup = ia.find_best_move(partie.get_current_state())
partie.play_move(meilleur_coup)

# Vérifier la fin de partie
fini, gagnant = partie.is_game_over()
```

## Format des coups (`Move`)

```python
('deplacement', (ligne, colonne))          # Déplacer le pion
('mur', ('h'|'v', ligne, colonne, 2))      # Poser un mur horizontal ou vertical
```

## Format des murs (`Wall`)

```python
('h', 2, 3, 2)   # Mur horizontal : ligne 2, colonne 3, longueur 2
('v', 1, 4, 2)   # Mur vertical   : ligne 1, colonne 4, longueur 2
```

Positions valides pour un mur : `0 ≤ ligne < 5` et `0 ≤ colonne < 5` (le mur doit tenir dans le plateau).
