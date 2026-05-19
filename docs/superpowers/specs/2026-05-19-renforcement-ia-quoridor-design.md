# Renforcement de l'IA Quoridor — Spec de design

**Date** : 2026-05-19
**Statut** : Validé pour implémentation
**Scope** : `quoridor_engine/ai.py`, `tests/test_ai.py`, documentation associée
**Hors scope** : `quoridor_engine/core.py`, webapp, firmware ESP32, protocole UART

---

## 1. Motivation

L'IA actuelle ([quoridor_engine/ai.py](../../../quoridor_engine/ai.py)) produit occasionnellement des coups visiblement absurdes pendant une partie : murs sans intérêt stratégique, pion qui recule en fin de partie sans raison. Le retour utilisateur indique 1 à 2 coups suspects par partie longue, dans tous les niveaux de difficulté.

Diagnostic technique : ces coups ne viennent pas d'un manque de profondeur d'analyse, mais de **trois sources d'aléatoire injectées dans l'algorithme** combinées à un **bug d'horizon** sur la fonction d'évaluation des victoires :

1. `random.choice` final sur les coups à score égal ([ai.py:1121](../../../quoridor_engine/ai.py#L1121))
2. `random.shuffle` des murs candidats avant le cap à 20 ([ai.py:778](../../../quoridor_engine/ai.py#L778))
3. Score de victoire constant (`20000`) indépendant de la distance au mat, donc victoire en 1 coup et victoire en 5 coups indistinguables ([ai.py:464-466](../../../quoridor_engine/ai.py#L464-L466))

Au-delà de ces bugs, on profite de la refonte pour renforcer l'IA via iterative deepening, ce qui élève le plafond de force sur "normal" et "difficile" sans modifier l'API publique.

## 2. Objectifs et critères d'acceptation

### Calibration cible des trois niveaux

| Niveau | Profil joueur cible |
|---|---|
| `facile` | Joueur lambda gagne sans se concentrer particulièrement |
| `normal` | Joueur attentif doit réfléchir pour gagner. Niveau d'usage principal. |
| `difficile` | Seuls les joueurs très expérimentés gagnent |

### Critères d'acceptation fonctionnels

1. **Zéro coup aléatoire visible** : deux appels successifs de `find_best_move` sur la même position retournent le même coup (déterminisme strict).
2. **Pas de recul sans cause** : sur une position où avancer et reculer donnent un score minimax égal, l'IA avance.
3. **Mate-in-1 systématique** : sur une position où l'IA peut gagner en 1 coup, elle joue ce coup (jamais un détour à 2-3 coups même si tous mènent à la victoire).
4. **Murs candidats préservés** : un mur "évident" (qui rallonge significativement le chemin adverse) n'est jamais éjecté par le cap des murs candidats.
5. **Calibration empirique des budgets temps** : après implémentation, les valeurs `TIME_BUDGETS` sont ajustées par tests de jeu jusqu'à matcher la calibration cible ci-dessus.

### Critères d'acceptation techniques

6. **API publique préservée** : `AI(player, difficulty='...')` et `ai.find_best_move(state, verbose=False)` ont la même signature. Les 4 consommateurs existants compilent et fonctionnent sans modification.
7. **Non-régression** : les ~278 tests existants passent (sauf 3 explicitement refondus).
8. **Tests ajoutés** : 4 nouveaux tests couvrent les critères 1, 2, 3, 4 ci-dessus.

## 3. État actuel

### Architecture existante

L'IA utilise **Minimax avec élagage Alpha-Bêta** à profondeur fixe. La profondeur est définie par la `difficulty` passée au constructeur :

```
'facile'    → depth = 2
'normal'    → depth = 4
'difficile' → depth = 5
```

Optimisations existantes (à conserver) :
- Table de transposition ([ai.py:397](../../../quoridor_engine/ai.py#L397))
- BFS inversé pour distances ([ai.py:78](../../../quoridor_engine/ai.py#L78))
- Cache de distances et de chemins par appel ([ai.py:401-405](../../../quoridor_engine/ai.py#L401-L405))
- Validation paresseuse des murs ([ai.py:551](../../../quoridor_engine/ai.py#L551))
- Move ordering ([ai.py:639](../../../quoridor_engine/ai.py#L639))

### Consommateurs de la classe `AI`

| Fichier | Ligne | Usage |
|---|---|---|
| [main.py](../../../main.py) | 500-508 | CLI, mode console |
| [webapp/service.py](../../../webapp/service.py) | 63-66 | Backend FastAPI |
| [quoridor_engine/game_session.py](../../../quoridor_engine/game_session.py) | 137 | Session unifiée (CLI + firmware) |
| [firmware/tests_devkit/run_p95_e2e.py](../../../firmware/tests_devkit/run_p95_e2e.py) | 71 | Harness test E2E |
| [tests/test_game_session.py](../../../tests/test_game_session.py) | divers | Tests + `FakeAI` mock |

L'API publique utilisée se réduit à : `AI(player, difficulty)` et `find_best_move(state, verbose)`. Tout changement interne reste invisible pour ces consommateurs.

## 4. Approche générale

L'IA passe de **"minimax à profondeur fixe avec aléatoire"** à **"minimax avec iterative deepening sous budget temps, déterministe"**.

```
AI.__init__(player, difficulty)
    ├─ TIME_BUDGETS = { 'facile': X, 'normal': Y, 'difficile': Z }  # à calibrer
    └─ DEPTH_MAX = 12  # garde-fou contre explosion mémoire

AI.find_best_move(state)
    └─ Iterative deepening : pour depth = 1, 2, 3, ... DEPTH_MAX :
         lancer minimax à cette profondeur
         si terminé dans le budget → mémoriser best_move_finalized
         si timeout pendant la recherche → s'arrêter et retourner best_move_finalized
    └─ Si plusieurs coups à score égal → tie-break déterministe (jamais random)
```

Les caches existants (distances, paths, transposition) sont conservés et bénéficient à toutes les profondeurs successives de l'iterative deepening (gain de performance net).

## 5. Modifications détaillées

### 5.1 Suppression des trois sources d'aléatoire

| Fichier:Ligne | Actuel | Cible |
|---|---|---|
| [ai.py:778](../../../quoridor_engine/ai.py#L778) | `random.shuffle(strategic_walls); return [:20]` | Trier les murs par proximité au chemin adverse, **puis** couper à `MAX_WALL_CANDIDATES = 30` |
| [ai.py:1121](../../../quoridor_engine/ai.py#L1121) | `random.choice(best_moves)` | Tie-break déterministe (cf. §5.4) |
| [ai.py:1128](../../../quoridor_engine/ai.py#L1128) | `random.choice(pawn_moves)` (fallback) | Premier coup déterministe |

L'import `random` peut être retiré entièrement après ces changements (à vérifier qu'aucun autre usage ne subsiste).

### 5.2 Mate-in-N : préférer gagner vite, perdre tard

Modification de `_evaluate_state` ([ai.py:454](../../../quoridor_engine/ai.py#L454)) :

```python
# Avant
if winner == self.player:
    return 20000
if winner == self.opponent:
    return -20000

# Après (depth_from_root passé en argument depuis _minimax)
if winner == self.player:
    return 20000 - depth_from_root
if winner == self.opponent:
    return -20000 + depth_from_root
```

**Propagation de `depth_from_root`** :
- Nouveau paramètre de `_minimax` : `depth_from_root: int` (default 0 à la racine)
- À chaque appel récursif : `_minimax(..., depth_from_root + 1, ...)`
- Passé à `_evaluate_state` uniquement quand `is_game_over` est True

**Interaction avec la transposition table** :
Les scores `20000 - depth_from_root` dépendent de la position racine, donc ne peuvent pas être cachés tels quels. Solution simple : **ne pas mettre en cache les états terminaux** (when `is_game_over()` returns True). Ces états sont peu fréquents et évalués en O(1), impact perf nul. Le cache reste utilisé pour tous les autres états.

### 5.3 Iterative deepening avec interruption propre

Remplacement de `find_best_move` ([ai.py:1057](../../../quoridor_engine/ai.py#L1057)).

**Algorithme** :

```python
def find_best_move(self, state, verbose=False):
    self._reset_per_search_caches()
    deadline = time.monotonic() + TIME_BUDGETS[self.difficulty]

    best_move_finalized = None
    completed_depth = 0

    for depth in range(1, DEPTH_MAX + 1):
        try:
            best_move_at_depth = self._search_at_depth(state, depth, deadline)
            best_move_finalized = best_move_at_depth
            completed_depth = depth
        except SearchTimeout:
            break  # On garde best_move_finalized de la profondeur N-1

        # Garantie minimale : ne pas casser avant depth=1
        if depth >= 1 and time.monotonic() > deadline:
            break

    if best_move_finalized is None:
        # Edge case : depth=1 elle-même a timeout (improbable)
        return self._fallback_move(state)
    return best_move_finalized
```

**Mécanisme d'interruption** :
- Exception `SearchTimeout(Exception)` définie dans `ai.py`
- Check à l'entrée de chaque appel récursif `_minimax` : `if time.monotonic() > deadline: raise SearchTimeout()`
- Capture uniquement au niveau racine (boucle d'iterative deepening)
- **Garantie critique** : `best_move_finalized` est mise à jour uniquement après que la profondeur N soit **entièrement** terminée. Jamais d'un résultat partiel (biais sur les premiers coups évalués).
- **Garantie minimale** : la profondeur 1 est toujours autorisée à se terminer même si le budget est dépassé (depth=1 prend <50ms en pratique, garantit qu'on retourne toujours quelque chose de raisonnable).

**Garde-fou `DEPTH_MAX = 12`** : empêche une boucle d'aller à l'infini sur position triviale + budget large. En pratique on n'y arrive jamais sur un plateau 6x6, mais sécurité.

**Caches** :
- `_distance_cache` et `_path_cache` : reset au début de `find_best_move` (nouvelle position racine), conservés entre les profondeurs successives de l'iterative deepening (gain de perf).
- `transposition_table` : **non resetée** entre les coups (réutilisation transverse), conservée entre les profondeurs.

### 5.4 Tie-break déterministe

Quand `_minimax` retourne le même `board_value` pour plusieurs coups, on les départage dans cet ordre (premier critère qui distingue tranche) :

1. **Avance vers le but** : préférer un déplacement avec `improvement > 0` (rapproche du but) sur un déplacement avec `improvement ≤ 0`. `improvement = distance_avant - distance_apres`.
2. **Impact mur** : pour les murs, préférer celui qui rallonge le plus le chemin adverse. Calculable rapidement via `distances_opp_avant - distances_opp_apres`.
3. **Distance au centre** : préférer la colonne plus centrale (mobilité supérieure).
4. **Ordre canonique** : tri lexicographique du coup converti en string. Élimine tout résidu d'aléa et garantit le déterminisme strict du critère 1.

**Implémentation** : nouvelle méthode privée `_tie_break(state, candidate_moves) -> Move` qui applique ces 4 critères en cascade. Appelée dans `find_best_move` uniquement si `len(best_moves) > 1`.

**Important** : ce tie-break **ne s'applique qu'aux coups réellement à égalité** après minimax. Si minimax voit une différence de score, elle prime.

### 5.5 Rééquilibrage du move ordering

Actuellement ([ai.py:639-716](../../../quoridor_engine/ai.py#L639-L716)) :
- Déplacements : score base `1000 + improvement * 100`
- Murs : score base `500 + bonus_proximite`

Conséquence : un mur stratégique excellent (qui rallonge l'adversaire de 3 cases) passe systématiquement après tous les déplacements, même un déplacement médiocre. Sous-pondère les murs dans l'ordre d'exploration, dégrade l'élagage alpha-bêta.

**Cible** : score murs basé sur l'impact réel sur la distance adverse :

```python
# Pour un mur candidat
delta_opp = L1_opp_apres_mur - L1_opp_avant_mur  # estimation rapide
score_mur = 700 + delta_opp * 150
```

Calibrage : un mur qui rallonge l'adversaire de 2 cases (`delta_opp = 2`) obtient `score_mur = 1000`, soit équivalent à un déplacement neutre. Un mur qui rallonge de 3 cases passe devant tous les déplacements neutres. Reste cohérent avec le score gagnant à 10000.

L'estimation `L1_opp_apres_mur` nécessite un mini-BFS, mais limité aux murs déjà validés (≤30 murs candidats) → coût acceptable. Si trop coûteux en pratique, fallback sur l'heuristique actuelle de proximité.

### 5.6 Cap des murs candidats

Modification de `_get_strategic_walls` ([ai.py:718](../../../quoridor_engine/ai.py#L718)) :

```python
# Avant
strategic_walls = list(strategic_walls)
random.shuffle(strategic_walls)
return strategic_walls[:20]

# Après
strategic_walls = list(strategic_walls)
strategic_walls.sort(key=lambda w: _wall_priority(w, opp_pos, my_pos), reverse=True)
return strategic_walls[:MAX_WALL_CANDIDATES]  # 30
```

Constante `MAX_WALL_CANDIDATES = 30` en haut du module.

`_wall_priority` : nouvelle fonction utilitaire qui retourne un score de priorité simple (distance Manhattan au plus proche des deux pions, inverse). Pas besoin de BFS à ce stade — c'est juste un pré-filtre.

### 5.7 Nettoyage

- Supprimer `print(f"IA initialisée pour le joueur ...")` dans `__init__` ([ai.py:420](../../../quoridor_engine/ai.py#L420)). Pollue stdout en tests et webapp.
- Conserver les `print` dans `find_best_move` qui sont déjà conditionnés sur `verbose`.
- Si `random` n'est plus importé nulle part dans `ai.py`, retirer l'import ([ai.py:51](../../../quoridor_engine/ai.py#L51)).

## 6. Constantes à exposer en haut de module

Pour faciliter la calibration sans replonger dans le code :

```python
# En haut de ai.py, après les imports
TIME_BUDGETS = {
    'facile':    None,  # à calibrer empiriquement
    'normal':    None,  # à calibrer empiriquement
    'difficile': None,  # à calibrer empiriquement
}
DEPTH_MAX = 12
MAX_WALL_CANDIDATES = 30
WIN_SCORE = 20000
```

Méthodologie de calibration : après implémentation, jouer 5-10 parties contre chaque niveau et ajuster les budgets jusqu'à matcher la calibration cible du §2. Documenter les valeurs retenues dans le code et dans `docs/04_ia.md`.

## 7. Tests

### 7.1 Tests existants à refondre

| Test | Fichier:Ligne | Problème | Action |
|---|---|---|---|
| `test_difficulty_levels` | [test_ai.py:74-80](../../../tests/test_ai.py#L74-L80) | Vérifie `depth_facile < depth_normal < depth_difficile`, mais depth n'a plus de sens fixe | Remplacer par vérification que `TIME_BUDGETS['facile'] < TIME_BUDGETS['normal'] < TIME_BUDGETS['difficile']` |
| `test_nodes_explored_increases_with_depth` | [test_ai.py:359-373](../../../tests/test_ai.py#L359-L373) | Devient flaky avec ID (dépend du temps) | **Remplacer** par : sur position identique, difficulté `difficile` avec budget temps complet explore strictement plus de nœuds que difficulté `facile`. Ne pas supprimer (test utile contre régression de profondeur effective). |
| `test_create_ai` | [test_ai.py:65-72](../../../tests/test_ai.py#L65-L72) | Vérifie `ia.depth == 2` pour facile | Adapter : vérifier que `ia.difficulty == 'facile'` et que les budgets sont définis |

### 7.2 Tests à ajouter

Nouvelle classe `TestDeterminism` :

```python
def test_same_position_same_move():
    """Deux appels successifs sur même état → même coup."""
    game = create_new_game()
    ia = AI(PLAYER_TWO, difficulty='normal')
    move1 = ia.find_best_move(game, verbose=False)
    ia.clear_cache()
    move2 = ia.find_best_move(game, verbose=False)
    assert move1 == move2
```

Nouvelle classe `TestNoBacktracking` :

```python
def test_no_useless_backtrack():
    """L'IA n'avance pas en arrière quand avancer donne le même score."""
    # Position symétrique calibrée où minimax donne égalité
    # Vérifier que le coup choisi a improvement >= 0
```

Nouvelle classe `TestMateInN` :

```python
def test_prefers_immediate_win():
    """Sur position avec mat-en-1 et mat-en-3 disponibles, choisit mat-en-1."""
    # Position calibrée où l'IA a deux branches gagnantes
    # Vérifier que move = coup qui gagne en 1
```

Nouvelle classe `TestWallCandidates` :

```python
def test_critical_wall_not_dropped():
    """Un mur évident de blocage n'est pas éjecté par le cap des candidats."""
    # Position où un mur précis rallonge l'adversaire de 3+ cases
    # Vérifier que ce mur est dans la liste retournée par _get_strategic_walls
```

### 7.3 Critères de non-régression

- Tous les tests de [tests/test_ai.py](../../../tests/test_ai.py) hors les 3 refondus passent
- Tous les tests de [tests/test_game_session.py](../../../tests/test_game_session.py) passent (contrat `find_best_move` préservé)
- Tous les autres tests du projet (`test_core.py`, `test_moves.py`, `test_walls.py`, `test_game.py`, `test_uart_client.py`, `tests/webapp/*`) passent sans modification

Commande de validation : `pytest` complet, attendu ~3-4 minutes.

## 8. Documentation à mettre à jour

Après validation de l'implémentation :

| Fichier | Section à mettre à jour |
|---|---|
| [docs/04_ia.md](../../04_ia.md) | "Niveaux de difficulté", "Profondeur typique", "Optimisations" (ajouter iterative deepening et tie-break) |
| [docs/flowcharts/02_logique_ia.md](../../flowcharts/02_logique_ia.md) | Diagramme de flux à adapter pour la boucle ID |
| [docs/jeu/comprendre_le_code.md](../../jeu/comprendre_le_code.md) | Section IA (Minimax/Alpha-Bêta) : mentionner iterative deepening, déterminisme, mate-in-N |

## 9. Hors scope (dette technique future)

Listé ici pour mémoire, **n'est pas réalisé dans ce spec** :

- **Quiescence search** : ne pas s'arrêter dans une position "instable" (un coup gagnant à 1 ply)
- **Vraie robustesse** : évaluer l'existence d'un 2e chemin disjoint (pas juste L2-L1)
- **Table Zobrist proper** : avec flags `exact` / `lower_bound` / `upper_bound` pour réutiliser le cache avec fenêtres alpha-beta différentes
- **Cap mémoire** sur la transposition table (actuellement croît sans borne)
- **Book d'ouverture** : coups préprogrammés pour les premiers tours
- **Killer moves** et **history heuristic** dans le move ordering
- **Recherche parallèle** sur multi-cœurs (utile sur RPi3+ qui a 4 cœurs)

## 10. Risques et mitigations

| Risque | Probabilité | Impact | Mitigation |
|---|---|---|---|
| Iterative deepening introduit régression sur position où alpha-bêta classique était mieux ordonné | Faible | Moyen | Tests de non-régression complets + tests "mate-in-N" et "déterminisme" |
| Budgets temps mal calibrés (trop lents / trop rapides) | Élevé | Faible | Constantes en haut de module, ajustables en 1 ligne sans replonger dans le code |
| Cache transposition pollué par scores cachés avec mate-in-N | Moyen | Élevé | Ne pas cacher les états terminaux (`is_game_over=True`) — décision explicite §5.2 |
| `_tie_break` introduit lui-même un biais (préfère toujours le centre) | Faible | Faible | Tests de non-régression + critère final lexicographique pour garantir le déterminisme strict |
| Calcul `delta_opp` pour le tri des murs (§5.5) trop coûteux | Moyen | Moyen | Fallback prévu sur l'heuristique de proximité actuelle si benchmark dégradé |
| Comportement différent sur Mac (dev) vs RPi3 (déploiement) à cause des budgets temps | Élevé | Moyen | Recalibrer les budgets sur RPi3 quand disponible, documenter dans `04_ia.md` |

## 11. Livrable attendu

1. `quoridor_engine/ai.py` modifié selon §5 et §6
2. `tests/test_ai.py` modifié selon §7
3. `docs/04_ia.md`, `docs/flowcharts/02_logique_ia.md`, `docs/jeu/comprendre_le_code.md` mis à jour selon §8
4. Suite `pytest` complète qui passe
5. Calibration empirique des `TIME_BUDGETS` documentée dans le code

---

**Validation** : ce spec a été co-conçu avec brainstorming superpowers. Approbation utilisateur requise avant rédaction du plan d'implémentation via writing-plans.
