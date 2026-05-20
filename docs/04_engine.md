# Moteur de jeu et IA — `quoridor_engine`

Module Python qui regroupe toute la logique Quoridor : règles, état, validation, pathfinding, undo,
et intelligence artificielle. Réutilisé par `main.py` (CLI console) et `webapp/` (interface web).

Fichiers sources :
- `quoridor_engine/core.py` — structures, règles, validation, BFS
- `quoridor_engine/ai.py` — IA Minimax avec élagage Alpha-Bêta

---

## Vue d'ensemble

```
quoridor_engine/
  __init__.py   → exports publics : QuoridorGame, GameState, InvalidMoveError, AI
  core.py       → GameState (frozen dataclass), règles, validation, BFS
  ai.py         → classe AI — Minimax + Alpha-Bêta + optimisations
```

`QuoridorGame` est la façade mutable qui encapsule un historique de `GameState` immuables.
Toute la logique de règles vit dans des fonctions module-level dans `core.py`.

---

## Constantes du jeu

```python
BOARD_SIZE = 6             # Plateau 6×6
MAX_WALLS = 6              # Murs par joueur en début de partie
PLAYER_ONE = 'j1'          # Démarre en (5, 3), objectif : ligne 0
PLAYER_TWO = 'j2'          # Démarre en (0, 3), objectif : ligne 5
```

Coordonnées : `(0, 0)` = coin top-left, `(5, 5)` = coin bottom-right (repère Python interne).
J1 monte (ligne 5 → ligne 0), J2 descend (ligne 0 → ligne 5).

---

## API publique

```python
from quoridor_engine import QuoridorGame, AI, GameState, InvalidMoveError

# --- Partie ---
game = QuoridorGame()
state = game.get_current_state()          # GameState immuable (snapshot)
moves = game.get_possible_moves()         # liste des coups légaux pour le joueur courant

game.play_move(('deplacement', (4, 3)))
game.play_move(('mur', ('h', 2, 3, 2)))
game.undo_move()                          # annule le dernier coup

fini, gagnant = game.is_game_over()       # (False, None) ou (True, 'j1'|'j2')

# --- IA ---
ai = AI(joueur='j2', difficulty='normal')          # 'facile' | 'normal' | 'difficile'
best_move = ai.find_best_move(game.get_current_state())
game.play_move(best_move)
```

| Symbole | Type | Rôle |
|---|---|---|
| `QuoridorGame` | classe (façade) | Point d'entrée : `play_move`, `undo_move`, `is_game_over` |
| `GameState` | dataclass frozen | Snapshot immuable d'une position |
| `InvalidMoveError` | exception | Levée si un coup viole les règles |
| `AI` | classe | IA Minimax (voir section ci-dessous) |

---

## Format des coups

**Déplacement :**
```python
('deplacement', (ligne, colonne))
```
Le pion du joueur courant est déplacé vers `(ligne, colonne)`.

**Mur :**
```python
('mur', ('h' | 'v', ligne, colonne, 2))
```
- `'h'` = mur horizontal, `'v'` = mur vertical.
- `(ligne, colonne)` = case de départ du mur (coin top-left du mur).
- `2` = longueur du mur (2 cases, valeur fixe).
- Contrainte de validité : `0 ≤ ligne < 5` et `0 ≤ colonne < 5`.

---

## Choix de conception

### Immutabilité de `GameState`

`GameState` est un `@dataclass(frozen=True)`. Chaque appel à `play_move` retourne un nouvel état,
l'ancien est conservé dans l'historique de `QuoridorGame`. Avantages :
- Undo trivial : dépiler l'historique.
- Recherche d'arbre dans l'IA sans backtrack manuel.
- Hash stable → utilisable comme clé dans la table de transposition.

### Murs en `FrozenSet[Wall]`

Structure hashable avec lookup O(1). Nécessaire pour que `GameState` soit hashable et puisse
alimenter la table de transposition de l'IA.

### Pathfinding BFS

La fonction module-level `_path_exists()` vérifie qu'aucun mur ne bloque totalement un joueur.
L'IA utilise un BFS inversé (partant de la ligne d'arrivée) pour calculer en un seul passage
la distance de toutes les cases vers l'objectif.

### Façade `QuoridorGame`

Encapsule l'état mutable (historique) au-dessus du `GameState` immuable. Toute la logique
de règles reste dans des fonctions module-level dans `core.py` (facilitent les tests unitaires).

---

## Intelligence artificielle

### Algorithme

Minimax avec élagage Alpha-Bêta et iterative deepening sous budget temps.
L'IA lance des recherches Minimax de profondeur croissante (1, 2, 3, …) et s'arrête quand le
budget temps est dépassé — elle retourne le meilleur coup de la dernière profondeur entièrement
terminée.

### Niveaux de difficulté

| Niveau | Profondeur typique | Budget temps |
|---|---|---|
| `'facile'` | 2-3 plis | court |
| `'normal'` | 4-5 plis | moyen |
| `'difficile'` | 6-8 plis | long |

Les budgets exacts sont configurables via `TIME_BUDGETS` en tête de `quoridor_engine/ai.py`.

### Fonction d'évaluation heuristique

Appliquée aux nœuds feuilles ou intermédiaires quand la profondeur max est atteinte.

| Critère | Description |
|---|---|
| Distance BFS | Distance de chaque pion vers sa ligne d'arrivée (via BFS inversé, pas Manhattan brute). |
| Différentiel | Score = distance_adversaire − distance_IA. Positif si l'IA est en avance. |
| Robustesse | Détection des chemins uniques (fragiles) vs multiples alternatives. |
| Murs restants | Bonus pour les murs non posés, surtout quand l'adversaire approche du but. |
| Mobilité | Nombre de déplacements immédiats possibles. |

### Optimisations

**BFS inversé :** un seul BFS depuis la ligne d'arrivée calcule la distance de toutes les cases
en O(N²). Chaque pion lit sa distance en O(1).

**Validation paresseuse des murs :** `_path_exists` n'est appelé que si le mur est
syntaxiquement valide et coupe le chemin actuel — évite les BFS inutiles.

**Table de transposition :** cache `hash(GameState) → évaluation`. Les positions identiques
atteintes par des permutations de coups différents ne sont calculées qu'une fois.

**Tri des coups (move ordering) :** les déplacements vers l'objectif sont évalués en premier.
L'élagage Alpha-Bêta est d'autant plus efficace que les bons coups sont testés tôt.

### Déterminisme

Deux appels de `find_best_move` sur la même position retournent toujours le même coup :
- Tri déterministe des coups candidats (proximité aux pions, ordre canonique).
- Tie-break lexicographique à score Minimax égal.
- Pénalité mate-in-N : à victoire équivalente, l'IA préfère gagner vite ; à défaite équivalente,
  l'IA préfère perdre tard.

Pour les tests, `find_best_move(state, max_depth_override=N)` force un Minimax classique
à profondeur fixe sans iterative deepening.

### Complexité

- Théorique : O(b^d) avec `b` = facteur de branchement (~30-50 coups en mid-game), `d` = profondeur.
- Alpha-Bêta avec bon ordonnancement : ~O(b^(d/2)) dans le meilleur cas.
- Table de transposition + tri des coups réduisent encore davantage le nombre de nœuds effectifs.

---

## Tests

| Fichier | Couverture |
|---|---|
| `tests/test_core.py` | Structures, `GameState`, constantes |
| `tests/test_moves.py` | Validation déplacements (orthogonaux, sauts, blocage par murs) |
| `tests/test_walls.py` | Pose de murs, chevauchement, blocage total (BFS) |
| `tests/test_game.py` | Scénarios de partie, undo, fin de partie |
| `tests/test_ai.py` | Heuristique, déterminisme, mate-in-N, iterative deepening, performance |

Couverture cible : `core.py` ~75 %, `ai.py` ~90 %, global ~80 %.

Commandes :
```bash
pytest                                            # tous les tests (~3.5 min)
pytest tests/test_ai.py -v                        # IA uniquement
pytest --cov=quoridor_engine --cov-report=html    # avec couverture
```

Voir [08_tests.md](08_tests.md) pour les détails des commandes pytest.
