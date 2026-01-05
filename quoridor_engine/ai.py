# -*- coding: utf-8 -*-
"""
=============================================================================
INTELLIGENCE ARTIFICIELLE POUR QUORIDOR (ai.py)
=============================================================================

Ce module implémente une IA capable de jouer au Quoridor de manière compétitive.

ALGORITHME PRINCIPAL : MINIMAX avec ÉLAGAGE ALPHA-BÊTA
======================================================

L'algorithme Minimax est un algorithme de théorie des jeux utilisé pour les
jeux à deux joueurs à somme nulle (ce que l'un gagne, l'autre le perd).

PRINCIPE DU MINIMAX :
---------------------
L'IA simule tous les coups possibles, puis les coups de l'adversaire, puis
ses propres réponses, etc. À chaque niveau :
- L'IA (MAX) cherche à MAXIMISER son score
- L'adversaire (MIN) cherche à MINIMISER le score de l'IA

C'est comme jouer aux échecs en pensant : "Si je joue ça, il jouera ça,
alors je pourrai jouer ça..."

ÉLAGAGE ALPHA-BÊTA :
--------------------
Optimisation qui évite d'explorer des branches de l'arbre de jeu qui ne
peuvent pas influencer la décision finale. Cela réduit drastiquement le
nombre de positions à évaluer.

- Alpha = meilleur score garanti pour MAX (l'IA)
- Bêta = meilleur score garanti pour MIN (l'adversaire)
- Si beta <= alpha, on peut "couper" la branche (élagage)

FONCTION D'ÉVALUATION HEURISTIQUE :
-----------------------------------
Pour évaluer les positions intermédiaires (pas de victoire), on utilise
plusieurs critères pondérés :
- Distance au but (le plus important)
- Nombre de murs restants
- Mobilité (cases accessibles)
- Position centrale

TABLE DE TRANSPOSITION :
------------------------
Cache qui stocke les évaluations déjà calculées pour éviter de recalculer
les mêmes positions plusieurs fois. Accélère significativement l'IA.
"""

import math
import random
from typing import List, Tuple, Dict
from collections import deque
from dataclasses import replace

from .core import (
    GameState, 
    Move, 
    Coord,
    PLAYER_ONE, 
    PLAYER_TWO, 
    BOARD_SIZE,
    get_possible_pawn_moves,
    move_pawn,
    place_wall,
    InvalidMoveError,
    _is_wall_between,
    _path_exists,
    _validate_wall_placement
)


# =============================================================================
# FONCTION UTILITAIRE : Calcul du plus court chemin
# =============================================================================

def _get_all_distances_to_goal(state: GameState, player: str) -> Dict[Tuple[int, int], int]:
    """
    Calcule la distance de CHAQUE case du plateau vers l'objectif du joueur.
    
    OPTIMISATION PAR BFS INVERSÉ :
    ------------------------------
    Au lieu de lancer un BFS depuis la position du joueur (qui donne une seule
    distance), on lance un BFS depuis TOUTE la ligne d'objectif.
    
    Cela permet de calculer en UNE SEULE PASSE la distance de n'importe quelle
    case vers l'objectif. C'est crucial pour le calcul du "chemin de réserve".
    
    PRINCIPE :
    ----------
    1. Initialiser toutes les cases de la ligne d'objectif avec distance = 0
    2. Propager les distances vers l'intérieur du plateau
    3. Chaque case reçoit la distance minimale pour atteindre l'objectif
    
    EXEMPLE pour J1 (objectif = ligne 0) :
    --------------------------------------
    Distances résultantes (sans murs) :
        0 0 0 0 0 0 0 0 0   ← Ligne objectif (distance 0)
        1 1 1 1 1 1 1 1 1
        2 2 2 2 2 2 2 2 2
        3 3 3 3 3 3 3 3 3
        ...
    
    Args:
        state: L'état actuel du jeu (pour connaître les murs)
        player: Le joueur dont on calcule les distances ('j1' ou 'j2')
    
    Returns:
        Dictionnaire {(ligne, colonne): distance} pour chaque case accessible
        Les cases inaccessibles ne sont pas dans le dictionnaire
    """
    distances: Dict[Tuple[int, int], int] = {}
    
    # Déterminer la ligne d'objectif selon le joueur
    # J1 veut atteindre la ligne 0, J2 veut atteindre la ligne 8
    goal_row = 0 if player == PLAYER_ONE else BOARD_SIZE - 1
    
    # File BFS : initialiser avec toutes les cases de la ligne d'objectif
    q = deque()
    for col in range(BOARD_SIZE):
        goal_pos = (goal_row, col)
        distances[goal_pos] = 0
        q.append(goal_pos)
    
    # BFS : propager les distances depuis l'objectif vers le reste du plateau
    while q:
        current_pos = q.popleft()
        current_dist = distances[current_pos]
        
        # Explorer les 4 voisins
        r, c = current_pos
        neighbors = [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]
        
        for neighbor in neighbors:
            # Conditions : dans les limites, pas encore visité, pas de mur
            if (neighbor not in distances and
                0 <= neighbor[0] < BOARD_SIZE and
                0 <= neighbor[1] < BOARD_SIZE and
                not _is_wall_between(state, current_pos, neighbor)):
                distances[neighbor] = current_dist + 1
                q.append(neighbor)
    
    return distances


def _compute_metrics_from_distances(state: GameState, pos: Coord, distances: Dict[Coord, int]) -> Tuple[int, int, int]:
    """Calcule L1, L2 et la fragilité à partir d'un dictionnaire de distances pré-calculé."""
    r, c = pos
    
    # Si le joueur est déjà sur l'objectif
    if pos in distances and distances[pos] == 0:
        return (0, 0, 0)
    
    # Trouver tous les voisins accessibles et leurs distances
    neighbors = [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]
    neighbor_distances = []
    
    for neighbor in neighbors:
        if (0 <= neighbor[0] < BOARD_SIZE and
            0 <= neighbor[1] < BOARD_SIZE and
            not _is_wall_between(state, pos, neighbor) and
            neighbor in distances):
            neighbor_distances.append(distances[neighbor])
    
    if not neighbor_distances:
        return (float('inf'), float('inf'), 0)
    
    neighbor_distances.sort()
    L1 = neighbor_distances[0] + 1
    
    if len(neighbor_distances) >= 2:
        L2 = neighbor_distances[1] + 1
    else:
        L2 = L1 + 10
    
    fragility = L2 - L1
    return (L1, L2, fragility)


# =============================================================================
# CLASSE PRINCIPALE : Intelligence Artificielle
# =============================================================================

class AI:
    """
    Intelligence Artificielle pour jouer au Quoridor.
    
    Cette classe implémente un adversaire informatique capable de jouer
    de manière stratégique en utilisant l'algorithme Minimax.
    
    FONCTIONNEMENT GÉNÉRAL :
    ------------------------
    1. L'IA reçoit l'état actuel du jeu
    2. Elle génère tous les coups possibles (déplacements + murs stratégiques)
    3. Pour chaque coup, elle simule le jeu plusieurs coups à l'avance
    4. Elle évalue chaque position finale avec une fonction heuristique
    5. Elle choisit le coup qui mène à la meilleure position
    
    PARAMÈTRES DE DIFFICULTÉ :
    --------------------------
    - Facile (profondeur 2) : L'IA "voit" 2 coups à l'avance → rapide mais prévisible
    - Normal (profondeur 4) : L'IA "voit" 4 coups à l'avance → équilibré
    - Difficile (profondeur 5) : L'IA "voit" 5 coups à l'avance → lent mais fort
    
    Plus la profondeur est grande, plus l'IA est forte mais plus elle est lente
    car le nombre de positions à évaluer croît exponentiellement.
    
    ATTRIBUTS :
    -----------
    player : str
        Le joueur contrôlé par l'IA ('j1' ou 'j2')
    opponent : str
        L'adversaire de l'IA
    depth : int
        Profondeur de recherche (nombre de coups simulés à l'avance)
    transposition_table : Dict
        Cache des positions déjà évaluées (optimisation)
    nodes_explored : int
        Compteur de positions explorées (pour les statistiques)
    """
    
    def __init__(self, player: str, depth: int = 4, difficulty: str = 'normal'):
        """
        Initialise l'IA pour un joueur donné.
        
        Args:
            player: Le joueur que l'IA contrôle ('j1' ou 'j2')
            depth: Profondeur de recherche initiale (sera ajustée selon la difficulté)
            difficulty: Niveau de difficulté ('facile', 'normal', 'difficile')
        
        NOTE SUR LA PROFONDEUR :
        ------------------------
        La profondeur contrôle combien de coups l'IA simule à l'avance.
        - Profondeur 2 : ~100 positions à évaluer
        - Profondeur 4 : ~10 000 positions à évaluer
        - Profondeur 6 : ~1 000 000 positions à évaluer
        
        C'est pourquoi on utilise l'élagage Alpha-Bêta pour réduire ce nombre.
        """
        self.player = player
        self.opponent = PLAYER_TWO if player == PLAYER_ONE else PLAYER_ONE
        self.depth = depth
        self.difficulty = difficulty
        
        # Table de transposition : cache des positions déjà évaluées
        # Clé = hash de l'état, Valeur = (profondeur, score)
        self.transposition_table: Dict[int, Tuple[int, float]] = {}
        
        # Cache pour les distances (BFS) au sein d'une même réflexion
        self._distance_cache: Dict[Tuple[int, str], Dict[Coord, int]] = {}
        
        # Compteur pour les statistiques
        self.nodes_explored = 0
        
        # ═══════════════════════════════════════════════════════════════════
        # Ajuster la profondeur selon le niveau de difficulté
        # ═══════════════════════════════════════════════════════════════════
        if difficulty == 'facile':
            self.depth = 2   # Rapide mais pas très malin
        elif difficulty == 'normal':
            self.depth = 4   # Bon équilibre vitesse/intelligence
        elif difficulty == 'difficile':
            self.depth = 5   # Lent mais redoutable
        
        print(f"IA initialisée pour le joueur {self.player} (niveau: {difficulty}, profondeur: {self.depth})")

    def _get_cached_distances(self, state: GameState, player: str) -> Dict[Coord, int]:
        """Récupère les distances depuis le cache ou les calcule."""
        state_hash = self._state_hash(state)
        cache_key = (state_hash, player)
        if cache_key not in self._distance_cache:
            self._distance_cache[cache_key] = _get_all_distances_to_goal(state, player)
        return self._distance_cache[cache_key]

    def _evaluate_state(self, state: GameState) -> float:
        """
        FONCTION D'ÉVALUATION HEURISTIQUE AMÉLIORÉE - Le "cerveau" de l'IA.
        """
        # ═══════════════════════════════════════════════════════════════════
        # CRITÈRE 1 : Vérifier si la partie est déjà terminée
        # ═══════════════════════════════════════════════════════════════════
        is_over, winner = state.is_game_over()
        if is_over:
            if winner == self.player:
                return 20000   # VICTOIRE ! Score maximum
            if winner == self.opponent:
                return -20000  # DÉFAITE ! Score minimum
        
        # ═══════════════════════════════════════════════════════════════════
        # CRITÈRE 2 & 3 : Distance et Robustesse
        # ═══════════════════════════════════════════════════════════════════
        # Utiliser le cache pour les distances
        distances_ia = self._get_cached_distances(state, self.player)
        distances_opp = self._get_cached_distances(state, self.opponent)
        
        # Récupérer les métriques de chemin pour les deux joueurs
        L1_ia, _, fragility_ia = _compute_metrics_from_distances(state, state.player_positions[self.player], distances_ia)
        L1_opp, _, fragility_opp = _compute_metrics_from_distances(state, state.player_positions[self.opponent], distances_opp)
        
        # Cas extrêmes : si un joueur est bloqué (ne devrait pas arriver)
        if L1_ia == float('inf'):
            return -20000  # L'IA est bloquée → catastrophe
        if L1_opp == float('inf'):
            return 20000   # L'adversaire est bloqué → victoire assurée
        
        # Score de base : différence de distance (L1)
        # Plus l'adversaire est loin et plus l'IA est proche, mieux c'est
        score = 150 * (L1_opp - L1_ia)
        
        # Score de robustesse : on veut être robuste et que l'adversaire soit fragile
        # Fragilité faible = bonne position (plusieurs chemins viables)
        # Fragilité haute = mauvaise position (un seul chemin, facile à bloquer)
        score -= 25 * fragility_ia   # Pénalité si on est fragile
        score += 25 * fragility_opp  # Bonus si l'adversaire est fragile
        
        # ═══════════════════════════════════════════════════════════════════
        # CRITÈRE 4 : Bonus de fin de partie (zone critique)
        # ═══════════════════════════════════════════════════════════════════
        # Quand on approche du but, chaque case compte énormément
        if L1_ia <= 3:
            score += 500  # Bonus massif si l'IA est proche de gagner
        if L1_opp <= 3:
            score -= 500  # Malus massif si l'adversaire est proche de gagner
        
        # Bonus progressif : plus on est proche, mieux c'est
        if L1_ia <= 2:
            score += 200
        if L1_opp <= 2:
            score -= 200
        
        # ═══════════════════════════════════════════════════════════════════
        # CRITÈRE 5 : Avantage en murs restants (valeur contextuelle)
        # ═══════════════════════════════════════════════════════════════════
        my_walls = state.player_walls[self.player]
        opp_walls = state.player_walls[self.opponent]
        
        # Score de base pour les murs
        score += 15 * (my_walls - opp_walls)
        
        # Bonus contextuel : les murs ont plus de valeur en fin de partie
        # Si l'adversaire est proche du but, nos murs sont précieux pour le bloquer
        if L1_opp <= 4 and my_walls > 0:
            score += 30 * my_walls  # Chaque mur vaut beaucoup plus
        
        # Si on est proche du but, les murs adverses sont menaçants
        if L1_ia <= 4 and opp_walls > 0:
            score -= 30 * opp_walls
        
        # ═══════════════════════════════════════════════════════════════════
        # CRITÈRE 6 : Mobilité (nombre de déplacements possibles)
        # ═══════════════════════════════════════════════════════════════════
        my_moves = len(get_possible_pawn_moves(state, self.player))
        opp_moves = len(get_possible_pawn_moves(state, self.opponent))
        score += 8 * (my_moves - opp_moves)
        
        # ═══════════════════════════════════════════════════════════════════
        # CRITÈRE 7 : Contrôle du centre (horizontal)
        # ═══════════════════════════════════════════════════════════════════
        my_pos = state.player_positions[self.player]
        opp_pos = state.player_positions[self.opponent]
        
        # Distance au centre (colonne 4)
        my_center_dist = abs(my_pos[1] - 4)
        opp_center_dist = abs(opp_pos[1] - 4)
        
        # Bonus pour être au centre, malus pour l'adversaire au centre
        score -= 5 * my_center_dist
        score += 5 * opp_center_dist
        
        return score

    def _is_wall_valid(self, state: GameState, player: str, wall: Tuple) -> bool:
        """
        Vérifie rapidement si un mur peut être placé légalement.
        
        Cette fonction est utilisée pour FILTRER les murs candidats avant
        de les évaluer dans Minimax. Elle doit être rapide.
        
        VÉRIFICATIONS EFFECTUÉES :
        --------------------------
        1. Règles géométriques (via _validate_wall_placement)
           - Mur dans les limites du plateau
           - Pas de collision avec un mur existant
           - Pas de chevauchement ou croisement
        
        2. Règle de non-blocage
           - Le mur ne doit pas empêcher un joueur d'atteindre son objectif
        
        Args:
            state: L'état actuel du jeu
            player: Le joueur qui placerait le mur
            wall: Le mur à tester (orientation, ligne, colonne, longueur)
        
        Returns:
            True si le mur est légal, False sinon
        """
        try:
            # Étape 1 : Vérifier les règles géométriques
            _validate_wall_placement(state, wall)
            
            # Étape 2 : Créer un état temporaire avec le mur
            temp_walls = state.walls.copy()
            temp_walls.add(wall)
            temp_state = replace(state, walls=temp_walls)
            
            # Étape 3 : Vérifier que les deux joueurs peuvent encore gagner
            goal_j1 = lambda pos: pos[0] == 0              # J1 doit atteindre le haut
            goal_j2 = lambda pos: pos[0] == BOARD_SIZE - 1  # J2 doit atteindre le bas
            
            if not _path_exists(temp_state, temp_state.player_positions[PLAYER_ONE], goal_j1):
                return False  # J1 serait bloqué
            if not _path_exists(temp_state, temp_state.player_positions[PLAYER_TWO], goal_j2):
                return False  # J2 serait bloqué
            
            return True
            
        except InvalidMoveError:
            # Une règle géométrique est violée
            return False

    def _get_strategic_walls(self, state: GameState, player: str, max_walls: int = 20) -> List[Tuple]:
        """
        Génère une liste de murs STRATÉGIQUES à considérer.
        
        PROBLÈME :
        ----------
        Il y a potentiellement ~128 positions de murs possibles sur le plateau.
        Tester tous ces murs à chaque niveau de Minimax serait trop lent.
        
        SOLUTION : HEURISTIQUE DE SÉLECTION
        -----------------------------------
        On génère uniquement les murs "intéressants" :
        - Murs AUTOUR DE L'ADVERSAIRE → pour le bloquer/ralentir
        - Murs AUTOUR DE SOI → pour protéger son chemin
        
        La zone "autour" est définie comme un carré de 5x5 cases centré
        sur le joueur (décalage de -2 à +2 en ligne et colonne).
        
        POURQUOI MÉLANGER ?
        -------------------
        On mélange aléatoirement les murs pour :
        - Varier le jeu (l'IA ne joue pas toujours pareil)
        - À score égal, choisir différents murs à chaque partie
        
        Args:
            state: L'état actuel du jeu
            player: Le joueur qui place les murs
            max_walls: Nombre maximum de murs à retourner (limite le calcul)
        
        Returns:
            Liste de tuples Wall stratégiques
        """
        strategic_walls = set()  # Set pour éviter les doublons
        opponent = PLAYER_TWO if player == PLAYER_ONE else PLAYER_ONE
        
        # ═══════════════════════════════════════════════════════════════════
        # STRATÉGIE 1 : Murs autour de l'ADVERSAIRE (pour le bloquer)
        # ═══════════════════════════════════════════════════════════════════
        opp_pos = state.player_positions[opponent]
        for dr in range(-2, 3):      # -2, -1, 0, 1, 2
            for dc in range(-2, 3):  # -2, -1, 0, 1, 2
                for orientation in ['h', 'v']:
                    r, c = opp_pos[0] + dr, opp_pos[1] + dc
                    # Vérifier que le mur serait dans les limites
                    if 0 <= r < BOARD_SIZE - 1 and 0 <= c < BOARD_SIZE - 1:
                        strategic_walls.add((orientation, r, c, 2))
        
        # ═══════════════════════════════════════════════════════════════════
        # STRATÉGIE 2 : Murs autour de SOI (pour protéger son chemin)
        # ═══════════════════════════════════════════════════════════════════
        my_pos = state.player_positions[player]
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                for orientation in ['h', 'v']:
                    r, c = my_pos[0] + dr, my_pos[1] + dc
                    if 0 <= r < BOARD_SIZE - 1 and 0 <= c < BOARD_SIZE - 1:
                        strategic_walls.add((orientation, r, c, 2))
        
        # Convertir en liste, mélanger pour varier, et limiter le nombre
        strategic_walls = list(strategic_walls)
        random.shuffle(strategic_walls)
        return strategic_walls[:max_walls]

    def _get_all_possible_moves(self, state: GameState) -> List[Move]:
        """
        Génère tous les coups que l'IA peut considérer à cet état.
        
        COUPS GÉNÉRÉS :
        ---------------
        1. TOUS les déplacements de pion possibles (généralement 2-4 coups)
        2. Les murs STRATÉGIQUES valides (jusqu'à ~20 murs)
        
        Cette fonction est le "générateur de coups" pour Minimax.
        Elle est appelée à chaque noeud de l'arbre de recherche.
        
        Args:
            state: L'état actuel du jeu
        
        Returns:
            Liste de coups au format Move : [('deplacement', coord), ('mur', wall), ...]
        """
        player = state.current_player
        moves: List[Move] = []

        # ═══════════════════════════════════════════════════════════════════
        # ÉTAPE 1 : Ajouter tous les déplacements de pion
        # ═══════════════════════════════════════════════════════════════════
        # Les déplacements sont TOUJOURS considérés car ils sont peu nombreux
        # et essentiels (on ne peut pas gagner sans se déplacer !)
        pawn_moves = get_possible_pawn_moves(state, player)
        for coord in pawn_moves:
            moves.append(('deplacement', coord))
        
        # ═══════════════════════════════════════════════════════════════════
        # ÉTAPE 2 : Ajouter les murs stratégiques (si on en a encore)
        # ═══════════════════════════════════════════════════════════════════
        if state.player_walls[player] > 0:
            # Récupérer les murs candidats
            strategic_walls = self._get_strategic_walls(state, player)
            
            # Ne garder que les murs VALIDES
            for wall in strategic_walls:
                if self._is_wall_valid(state, player, wall):
                    moves.append(('mur', wall))
        
        return moves

    def _state_hash(self, state: GameState) -> int:
        """
        Crée une empreinte unique (hash) pour un état de jeu.
        
        UTILITÉ : TABLE DE TRANSPOSITION
        ---------------------------------
        Pendant la recherche Minimax, on peut atteindre la même position
        par des chemins différents. Sans cache, on recalculerait le score
        plusieurs fois.
        
        La table de transposition stocke : hash → (profondeur, score)
        Si on retombe sur un état déjà évalué à une profondeur suffisante,
        on réutilise le score sans recalculer.
        
        COMPOSITION DU HASH :
        ---------------------
        Le hash est calculé à partir de :
        - Positions des deux joueurs
        - Ensemble des murs posés
        - Joueur courant
        
        On utilise frozenset car les set normaux ne sont pas hashables.
        
        Args:
            state: L'état à identifier
        
        Returns:
            Entier unique identifiant cet état
        """
        return hash((
            frozenset(state.player_positions.items()),  # Positions figées
            frozenset(state.walls),                     # Murs figés
            state.current_player                        # À qui le tour
        ))

    def _apply_move(self, state: GameState, move: Move) -> GameState:
        """
        Applique un coup et retourne le nouvel état (sans modifier l'original).
        
        Cette fonction est utilisée dans Minimax pour simuler les coups
        et explorer l'arbre de jeu.
        
        Args:
            state: L'état actuel
            move: Le coup à appliquer : ('deplacement', coord) ou ('mur', wall)
        
        Returns:
            Nouvel état GameState après le coup
        
        Raises:
            InvalidMoveError: Si le coup est invalide (ne devrait pas arriver
            si _get_all_possible_moves filtre correctement)
        """
        player = state.current_player
        move_type, move_data = move
        
        if move_type == 'deplacement':
            return move_pawn(state, player, move_data)
        else:  # 'mur'
            return place_wall(state, player, move_data)

    def _minimax(self, state: GameState, depth: int, alpha: float, beta: float, is_maximizing: bool) -> float:
        r"""
        ALGORITHME MINIMAX AVEC ÉLAGAGE ALPHA-BÊTA
        
        C'est le coeur de l'IA ! Cet algorithme explore l'arbre de jeu pour
        trouver le meilleur coup en supposant que l'adversaire joue optimalement.
        
        PRINCIPE DU MINIMAX :
        ---------------------
        L'algorithme alterne entre deux types de noeuds :
        
        - MAXIMIZING (tour de l'IA) : L'IA choisit le coup qui MAXIMISE son score
        - MINIMIZING (tour de l'adversaire) : L'adversaire choisit le coup qui
          MINIMISE le score de l'IA (il joue contre nous !)
        
        VISUALISATION DE L'ARBRE :
        --------------------------
                        [État Initial]  ← MAX (IA joue)
                       /      |       \
                    [A]      [B]      [C]  ← MIN (adversaire joue)
                   / | \    / | \    / | \
                 [scores après évaluation]  ← Feuilles évaluées
        
        L'IA remonte les scores :
        - Niveau MIN : prend le minimum (l'adversaire nous fait du mal)
        - Niveau MAX : prend le maximum (on choisit le meilleur)
        
        ÉLAGAGE ALPHA-BÊTA :
        --------------------
        Optimisation CRUCIALE qui évite d'explorer des branches inutiles.
        
        - Alpha = meilleur score GARANTI pour MAX (initialement -∞)
        - Beta = meilleur score GARANTI pour MIN (initialement +∞)
        
        RÈGLE D'ÉLAGAGE : Si beta <= alpha, on COUPE la branche !
        
        Pourquoi ? Si l'adversaire a déjà trouvé un coup qui lui donne un
        score de 5 (beta=5), et qu'on explore une branche où on peut avoir
        au moins 10 (alpha=10), l'adversaire ne choisira JAMAIS cette branche.
        Donc inutile de continuer à l'explorer.
        
        GAIN : L'élagage peut réduire le nombre de noeuds de O(b^d) à O(b^(d/2))
        où b = nombre de coups et d = profondeur. C'est ÉNORME !
        
        Args:
            state: L'état actuel du jeu
            depth: Profondeur restante à explorer (décrémente à chaque niveau)
            alpha: Meilleur score garanti pour MAX (l'IA) jusqu'ici
            beta: Meilleur score garanti pour MIN (l'adversaire) jusqu'ici
            is_maximizing: True si c'est au tour de l'IA (MAX), False sinon
        
        Returns:
            Le score de cet état (remonté depuis les feuilles ou le cache)
        """
        # Compteur pour les statistiques
        self.nodes_explored += 1
        
        # ═══════════════════════════════════════════════════════════════════
        # OPTIMISATION 1 : Vérifier la table de transposition (cache)
        # ═══════════════════════════════════════════════════════════════════
        state_hash = self._state_hash(state)
        if state_hash in self.transposition_table:
            cached_depth, cached_value = self.transposition_table[state_hash]
            # On peut réutiliser le cache seulement si la profondeur explorée
            # était >= la profondeur actuelle (plus de détail = plus fiable)
            if cached_depth >= depth:
                return cached_value
        
        # ═══════════════════════════════════════════════════════════════════
        # CONDITIONS D'ARRÊT : Feuille de l'arbre
        # ═══════════════════════════════════════════════════════════════════
        is_over, _ = state.is_game_over()
        if depth == 0 or is_over:
            # On est à une feuille : évaluer la position
            eval_score = self._evaluate_state(state)
            # Stocker dans le cache pour les prochaines fois
            self.transposition_table[state_hash] = (depth, eval_score)
            return eval_score

        # Générer tous les coups possibles depuis cet état
        possible_moves = self._get_all_possible_moves(state)
        
        # ═══════════════════════════════════════════════════════════════════
        # CAS MAXIMIZING : C'est le tour de l'IA, on cherche le MAXIMUM
        # ═══════════════════════════════════════════════════════════════════
        if is_maximizing:
            max_eval = -math.inf  # On part du pire score possible
            
            for move in possible_moves:
                try:
                    # Simuler le coup
                    next_state = self._apply_move(state, move)
                    
                    # Appel RÉCURSIF : après notre coup, c'est à l'adversaire (MIN)
                    evaluation = self._minimax(next_state, depth - 1, alpha, beta, False)
                    
                    # Garder le meilleur score
                    max_eval = max(max_eval, evaluation)
                    
                    # Mettre à jour alpha (meilleur score garanti pour MAX)
                    alpha = max(alpha, evaluation)
                    
                    # ═══════════════════════════════════════════════════════
                    # ÉLAGAGE BETA : Si beta <= alpha, couper !
                    # ═══════════════════════════════════════════════════════
                    if beta <= alpha:
                        break  # L'adversaire ne choisira jamais cette branche
                        
                except InvalidMoveError:
                    continue  # Coup invalide, passer au suivant
            
            # Stocker le résultat dans le cache
            self.transposition_table[state_hash] = (depth, max_eval)
            return max_eval
        
        # ═══════════════════════════════════════════════════════════════════
        # CAS MINIMIZING : C'est le tour de l'adversaire, on cherche le MINIMUM
        # ═══════════════════════════════════════════════════════════════════
        else:
            min_eval = math.inf  # On part du meilleur score possible (pour l'IA)
            
            for move in possible_moves:
                try:
                    next_state = self._apply_move(state, move)
                    
                    # Appel RÉCURSIF : après le coup adverse, c'est à nous (MAX)
                    evaluation = self._minimax(next_state, depth - 1, alpha, beta, True)
                    
                    # L'adversaire garde le pire score (pour nous)
                    min_eval = min(min_eval, evaluation)
                    
                    # Mettre à jour beta (meilleur score garanti pour MIN)
                    beta = min(beta, evaluation)
                    
                    # ═══════════════════════════════════════════════════════
                    # ÉLAGAGE ALPHA : Si beta <= alpha, couper !
                    # ═══════════════════════════════════════════════════════
                    if beta <= alpha:
                        break  # Nous ne choisirons jamais cette branche
                        
                except InvalidMoveError:
                    continue
            
            self.transposition_table[state_hash] = (depth, min_eval)
            return min_eval

    def find_best_move(self, state: GameState, verbose: bool = True) -> Move:
        """
        POINT D'ENTRÉE PRINCIPAL : Trouve le meilleur coup à jouer.
        """
        # Réinitialiser le compteur de positions explorées et les caches
        self.nodes_explored = 0
        self._distance_cache.clear()
        
        best_move = None
        best_value = -math.inf  # On cherche à maximiser
        
        # Générer et mélanger les coups possibles
        possible_moves = self._get_all_possible_moves(state)
        random.shuffle(possible_moves)  # Varier le jeu !

        if verbose:
            print(f"IA réfléchit... ({len(possible_moves)} coups à évaluer)")

        # ═══════════════════════════════════════════════════════════════════
        # Évaluer chaque coup au niveau racine
        # ═══════════════════════════════════════════════════════════════════
        for move in possible_moves:
            try:
                # Simuler le coup
                temp_state = self._apply_move(state, move)
                
                # Lancer Minimax depuis cette position
                # - depth - 1 car on a déjà joué un coup
                # - is_maximizing = False car après notre coup, c'est à l'adversaire
                # - alpha = -∞, beta = +∞ (pas encore de contraintes)
                board_value = self._minimax(temp_state, self.depth - 1, -math.inf, math.inf, False)
                
                # Est-ce le meilleur coup trouvé jusqu'ici ?
                if board_value > best_value:
                    best_value = board_value
                    best_move = move
                    
            except InvalidMoveError:
                continue  # Coup invalide, passer au suivant
        
        if verbose:
            print(f"IA a exploré {self.nodes_explored} positions (score: {best_value:.1f})")
        
        # ═══════════════════════════════════════════════════════════════════
        # FALLBACK : Si aucun coup n'est trouvé (ne devrait pas arriver)
        # ═══════════════════════════════════════════════════════════════════
        if best_move is None:
            # En dernier recours, faire un déplacement aléatoire
            pawn_moves = get_possible_pawn_moves(state, state.current_player)
            if pawn_moves:
                best_move = ('deplacement', random.choice(pawn_moves))
            else:
                raise InvalidMoveError("L'IA ne trouve aucun coup valide !")
        
        return best_move

    def clear_cache(self):
        """
        Vide la table de transposition.
        
        À appeler entre les parties pour libérer la mémoire et éviter
        que d'anciennes positions interfèrent avec les nouvelles.
        """
        self.transposition_table.clear()
