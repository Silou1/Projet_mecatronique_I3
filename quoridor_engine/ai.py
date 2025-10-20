# -*- coding: utf-8 -*-
"""
Module pour l'Intelligence Artificielle du jeu Quoridor.
Implémente l'algorithme Minimax avec élagage Alpha-Bêta.
"""

import math
import random
from typing import List, Tuple, Dict
from collections import deque
from dataclasses import replace

from .core import (
    GameState, 
    Move, 
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


def _get_shortest_path_length(state: GameState, player: str) -> int:
    """
    Calcule la longueur du plus court chemin pour un joueur en utilisant BFS.
    
    Args:
        state: L'état actuel du jeu
        player: Le joueur dont on calcule le chemin
    
    Returns:
        Longueur du plus court chemin (ou inf si aucun chemin)
    """
    start_pos = state.player_positions[player]
    is_goal = (lambda pos: pos[0] == BOARD_SIZE - 1) if player == PLAYER_ONE else (lambda pos: pos[0] == 0)

    q = deque([(start_pos, 0)])  # (position, distance)
    visited = {start_pos}

    while q:
        current_pos, dist = q.popleft()
        if is_goal(current_pos):
            return dist
        
        r, c = current_pos
        potential_moves = [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]
        
        for move in potential_moves:
            if (move not in visited and 
                0 <= move[0] < BOARD_SIZE and 
                0 <= move[1] < BOARD_SIZE and 
                not _is_wall_between(state, current_pos, move)):
                visited.add(move)
                q.append((move, dist + 1))
                
    return float('inf')  # Si aucun chemin n'est trouvé


class AI:
    """
    Classe qui encapsule la logique de l'IA pour le jeu Quoridor.
    
    Utilise l'algorithme Minimax avec élagage Alpha-Bêta pour choisir les meilleurs coups.
    """
    
    def __init__(self, player: str, depth: int = 4, difficulty: str = 'normal'):
        """
        Initialise l'IA.
        
        Args:
            player: Le joueur contrôlé par l'IA ('j1' ou 'j2')
            depth: Profondeur de recherche Minimax (2-6 recommandé)
            difficulty: Niveau de difficulté ('facile', 'normal', 'difficile')
        """
        self.player = player
        self.opponent = PLAYER_TWO if player == PLAYER_ONE else PLAYER_ONE
        self.depth = depth
        self.difficulty = difficulty
        self.transposition_table: Dict[int, Tuple[int, float]] = {}
        self.nodes_explored = 0
        
        # Ajuster la profondeur selon la difficulté
        if difficulty == 'facile':
            self.depth = 2
        elif difficulty == 'normal':
            self.depth = 4
        elif difficulty == 'difficile':
            self.depth = 5
        
        print(f"IA initialisée pour le joueur {self.player} (niveau: {difficulty}, profondeur: {self.depth})")

    def _evaluate_state(self, state: GameState) -> float:
        """
        Fonction d'évaluation heuristique améliorée.
        
        Calcule un score pour un état de jeu donné en combinant plusieurs critères :
        - Distance au but (plus court chemin)
        - Avantage en murs restants
        - Mobilité (nombre de cases accessibles)
        - Position centrale
        
        Args:
            state: L'état à évaluer
        
        Returns:
            Score positif si favorable à l'IA, négatif sinon
        """
        # 1. Vérifier la victoire
        is_over, winner = state.is_game_over()
        if is_over:
            if winner == self.player:
                return 10000
            if winner == self.opponent:
                return -10000
        
        # 2. Distance au but (critère principal)
        path_ia = _get_shortest_path_length(state, self.player)
        path_opponent = _get_shortest_path_length(state, self.opponent)
        
        if path_ia == float('inf'):
            return -10000
        if path_opponent == float('inf'):
            return 10000
        
        score = 100 * (path_opponent - path_ia)
        
        # 3. Avantage en murs restants
        score += 10 * (state.player_walls[self.player] - state.player_walls[self.opponent])
        
        # 4. Mobilité (nombre de cases accessibles)
        my_moves = len(get_possible_pawn_moves(state, self.player))
        opp_moves = len(get_possible_pawn_moves(state, self.opponent))
        score += 5 * (my_moves - opp_moves)
        
        # 5. Bonus position centrale (surtout en début de partie)
        my_pos = state.player_positions[self.player]
        center_distance = abs(my_pos[1] - 4)  # Distance à la colonne centrale (e)
        score -= 2 * center_distance
        
        return score

    def _is_wall_valid(self, state: GameState, player: str, wall: Tuple) -> bool:
        """
        Vérifie si un mur peut être placé légalement.
        
        Args:
            state: L'état actuel du jeu
            player: Le joueur qui place le mur
            wall: Le mur à tester
        
        Returns:
            True si le mur est valide, False sinon
        """
        try:
            # Vérifier les règles de base
            _validate_wall_placement(state, wall)
            
            # Créer un état temporaire avec le mur
            temp_walls = state.walls.copy()
            temp_walls.add(wall)
            temp_state = replace(state, walls=temp_walls)
            
            # Vérifier qu'aucun joueur n'est bloqué
            goal_j1 = lambda pos: pos[0] == BOARD_SIZE - 1
            goal_j2 = lambda pos: pos[0] == 0
            
            if not _path_exists(temp_state, temp_state.player_positions[PLAYER_ONE], goal_j1):
                return False
            if not _path_exists(temp_state, temp_state.player_positions[PLAYER_TWO], goal_j2):
                return False
            
            return True
        except InvalidMoveError:
            return False

    def _get_strategic_walls(self, state: GameState, player: str, max_walls: int = 20) -> List[Tuple]:
        """
        Génère une liste de murs stratégiques à tester.
        
        Au lieu de tester tous les murs possibles (trop coûteux), on génère
        seulement les murs autour des joueurs.
        
        Args:
            state: L'état actuel du jeu
            player: Le joueur qui place les murs
            max_walls: Nombre maximum de murs à générer
        
        Returns:
            Liste de murs stratégiques
        """
        strategic_walls = set()
        opponent = PLAYER_TWO if player == PLAYER_ONE else PLAYER_ONE
        
        # Murs autour de l'adversaire (pour le bloquer)
        opp_pos = state.player_positions[opponent]
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                for orientation in ['h', 'v']:
                    r, c = opp_pos[0] + dr, opp_pos[1] + dc
                    if 0 <= r < BOARD_SIZE - 1 and 0 <= c < BOARD_SIZE - 1:
                        strategic_walls.add((orientation, r, c, 2))
        
        # Murs sur notre chemin optimal (pour se protéger)
        my_pos = state.player_positions[player]
        for dr in range(-2, 3):
            for dc in range(-2, 3):
                for orientation in ['h', 'v']:
                    r, c = my_pos[0] + dr, my_pos[1] + dc
                    if 0 <= r < BOARD_SIZE - 1 and 0 <= c < BOARD_SIZE - 1:
                        strategic_walls.add((orientation, r, c, 2))
        
        # Convertir en liste, mélanger et limiter
        strategic_walls = list(strategic_walls)
        random.shuffle(strategic_walls)
        return strategic_walls[:max_walls]

    def _get_all_possible_moves(self, state: GameState) -> List[Move]:
        """
        Génère tous les coups possibles (déplacements + murs stratégiques).
        
        Args:
            state: L'état actuel du jeu
        
        Returns:
            Liste des coups possibles
        """
        player = state.current_player
        moves: List[Move] = []

        # 1. Tous les déplacements possibles
        pawn_moves = get_possible_pawn_moves(state, player)
        for coord in pawn_moves:
            moves.append(('deplacement', coord))
        
        # 2. Murs stratégiques (si on en a)
        if state.player_walls[player] > 0:
            strategic_walls = self._get_strategic_walls(state, player)
            for wall in strategic_walls:
                if self._is_wall_valid(state, player, wall):
                    moves.append(('mur', wall))
        
        return moves

    def _state_hash(self, state: GameState) -> int:
        """
        Crée un hash unique pour un état de jeu (pour la table de transposition).
        
        Args:
            state: L'état à hasher
        
        Returns:
            Hash de l'état
        """
        return hash((
            frozenset(state.player_positions.items()),
            frozenset(state.walls),
            state.current_player
        ))

    def _apply_move(self, state: GameState, move: Move) -> GameState:
        """
        Applique un coup et retourne le nouvel état.
        
        Args:
            state: L'état actuel
            move: Le coup à appliquer
        
        Returns:
            Nouvel état après le coup
        """
        player = state.current_player
        move_type, move_data = move
        
        if move_type == 'deplacement':
            return move_pawn(state, player, move_data)
        else:  # 'mur'
            return place_wall(state, player, move_data)

    def _minimax(self, state: GameState, depth: int, alpha: float, beta: float, is_maximizing: bool) -> float:
        """
        Algorithme Minimax avec élagage Alpha-Bêta et table de transposition.
        
        Args:
            state: L'état actuel
            depth: Profondeur restante à explorer
            alpha: Meilleur score garanti pour le maximiseur
            beta: Meilleur score garanti pour le minimiseur
            is_maximizing: True si c'est le tour du maximiseur (IA)
        
        Returns:
            Score de l'état
        """
        self.nodes_explored += 1
        
        # Vérifier le cache (table de transposition)
        state_hash = self._state_hash(state)
        if state_hash in self.transposition_table:
            cached_depth, cached_value = self.transposition_table[state_hash]
            if cached_depth >= depth:
                return cached_value
        
        # Condition d'arrêt
        is_over, _ = state.is_game_over()
        if depth == 0 or is_over:
            eval_score = self._evaluate_state(state)
            self.transposition_table[state_hash] = (depth, eval_score)
            return eval_score

        possible_moves = self._get_all_possible_moves(state)
        
        if is_maximizing:
            max_eval = -math.inf
            for move in possible_moves:
                try:
                    next_state = self._apply_move(state, move)
                    evaluation = self._minimax(next_state, depth - 1, alpha, beta, False)
                    max_eval = max(max_eval, evaluation)
                    alpha = max(alpha, evaluation)
                    if beta <= alpha:
                        break  # Élagage Beta
                except InvalidMoveError:
                    continue
            
            self.transposition_table[state_hash] = (depth, max_eval)
            return max_eval
        else:  # Minimizing
            min_eval = math.inf
            for move in possible_moves:
                try:
                    next_state = self._apply_move(state, move)
                    evaluation = self._minimax(next_state, depth - 1, alpha, beta, True)
                    min_eval = min(min_eval, evaluation)
                    beta = min(beta, evaluation)
                    if beta <= alpha:
                        break  # Élagage Alpha
                except InvalidMoveError:
                    continue
            
            self.transposition_table[state_hash] = (depth, min_eval)
            return min_eval

    def find_best_move(self, state: GameState, verbose: bool = True) -> Move:
        """
        Trouve le meilleur coup à jouer en utilisant Minimax.
        
        Args:
            state: L'état actuel du jeu
            verbose: Si True, affiche des informations de débogage
        
        Returns:
            Le meilleur coup trouvé
        """
        self.nodes_explored = 0
        best_move = None
        best_value = -math.inf
        
        possible_moves = self._get_all_possible_moves(state)
        random.shuffle(possible_moves)  # Pour varier les coups à score égal

        if verbose:
            print(f"IA réfléchit... ({len(possible_moves)} coups à évaluer)")

        for move in possible_moves:
            try:
                temp_state = self._apply_move(state, move)
                board_value = self._minimax(temp_state, self.depth - 1, -math.inf, math.inf, False)
                
                if board_value > best_value:
                    best_value = board_value
                    best_move = move
            except InvalidMoveError:
                continue
        
        if verbose:
            print(f"IA a exploré {self.nodes_explored} positions (score: {best_value:.1f})")
        
        # Fallback : si aucun coup n'est trouvé, déplacement aléatoire
        if best_move is None:
            pawn_moves = get_possible_pawn_moves(state, state.current_player)
            if pawn_moves:
                best_move = ('deplacement', random.choice(pawn_moves))
            else:
                raise InvalidMoveError("L'IA ne trouve aucun coup valide !")
        
        return best_move

    def clear_cache(self):
        """Vide la table de transposition (à appeler entre les parties)."""
        self.transposition_table.clear()
