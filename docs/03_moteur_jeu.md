# Moteur de jeu — `quoridor_engine`

Package Python qui implémente toute la logique Quoridor : règles, état, validation, undo. Aucune dépendance vers l'IA ou l'interface.

> **Référence détaillée** : [quoridor_engine/README.md](../quoridor_engine/README.md) (API complète, signatures, format des coups).

## Constantes clés

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

| Symbole | Type | Rôle |
|---|---|---|
| `QuoridorGame` | classe (façade) | Point d'entrée pour jouer : `play_move()`, `undo_move()`, `is_game_over()` |
| `GameState` | dataclass frozen | Snapshot immuable d'une partie |
| `InvalidMoveError` | exception | Levée si un coup viole les règles |
| `AI` | classe | IA Minimax (voir [04_ia.md](04_ia.md)) |

## Format des coups

```python
('deplacement', (ligne, colonne))      # Déplacer le pion
('mur', ('h'|'v', ligne, colonne, 2))  # Poser un mur horizontal ou vertical
```

Les murs valides ont `0 ≤ ligne < 5` et `0 ≤ colonne < 5` (ils doivent tenir dans le plateau).

## Exemple — Joueur vs IA

```python
from quoridor_engine import QuoridorGame, AI

partie = QuoridorGame()
ia = AI('j2', difficulty='normal')

# Joueur 1 avance
partie.play_move(('deplacement', (4, 3)))

# L'IA joue pour J2
meilleur_coup = ia.find_best_move(partie.get_current_state())
partie.play_move(meilleur_coup)

# Vérifier la fin de partie
fini, gagnant = partie.is_game_over()
if fini:
    print(f"Le joueur {gagnant} a gagné !")
```

## Exemple — Annulation

```python
from quoridor_engine import QuoridorGame

partie = QuoridorGame()
partie.play_move(('deplacement', (4, 3)))
partie.play_move(('deplacement', (1, 3)))
partie.play_move(('mur', ('h', 4, 3, 2)))

partie.undo_move()                      # annule le dernier coup
print(len(partie._history))             # 2 coups restants
```

## Exemple — Coups possibles

```python
state = partie.get_current_state()
print(state.player_positions['j1'])     # (5, 3) au départ
print(state.player_walls['j1'])         # 6 au départ
print(state.current_player)             # 'j1' au premier tour

for type_coup, donnees in partie.get_possible_moves():
    print(type_coup, donnees)
```

## Choix de conception

1. **Immutabilité** : `GameState` est `@dataclass(frozen=True)`. Chaque coup retourne un nouvel état, le `QuoridorGame` empile l'historique. Permet l'undo trivial et nourrit l'arbre de recherche de l'IA.
2. **Murs en `FrozenSet`** : O(1) en lookup, hashable → utilisable dans la table de transposition de l'IA.
3. **Pathfinding BFS** : module-level `_path_exists()` valide qu'un mur ne bloque pas totalement un joueur. Optimisation critique pour l'IA (BFS inversé depuis la ligne d'arrivée).
4. **Façade `QuoridorGame`** : encapsule l'état mutable (l'historique) au-dessus du `GameState` immutable.

## Tests associés

| Fichier | Couvre |
|---|---|
| [tests/test_core.py](../tests/test_core.py) | Structures, immutabilité, constantes |
| [tests/test_moves.py](../tests/test_moves.py) | Déplacements, sauts, blocage par murs |
| [tests/test_walls.py](../tests/test_walls.py) | Pose, validation, blocage de chemin |
| [tests/test_game.py](../tests/test_game.py) | Orchestration, undo, fin de partie |

Voir [08_tests.md](08_tests.md) pour les commandes pytest.
