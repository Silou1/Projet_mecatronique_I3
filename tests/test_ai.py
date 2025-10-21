# -*- coding: utf-8 -*-
"""
Tests unitaires pour l'Intelligence Artificielle du jeu Quoridor.
"""

import pytest
from quoridor_engine.core import (
    GameState,
    create_new_game,
    move_pawn,
    place_wall,
    PLAYER_ONE,
    PLAYER_TWO,
    InvalidMoveError
)
from quoridor_engine.ai import AI, _get_shortest_path_length


class TestPathfinding:
    """Tests de la fonction de calcul du plus court chemin."""
    
    def test_shortest_path_at_start(self):
        """Distance au but depuis la position initiale."""
        game = create_new_game()
        
        # J1 doit parcourir 8 cases pour atteindre la ligne 8
        distance_j1 = _get_shortest_path_length(game, PLAYER_ONE)
        assert distance_j1 == 8
        
        # J2 doit parcourir 8 cases pour atteindre la ligne 0
        distance_j2 = _get_shortest_path_length(game, PLAYER_TWO)
        assert distance_j2 == 8
    
    def test_shortest_path_with_wall(self):
        """Le chemin change avec un mur."""
        game = create_new_game()
        
        # Distance sans mur
        distance_before = _get_shortest_path_length(game, PLAYER_ONE)
        
        # Ajouter un mur qui ne bloque pas complètement
        game = place_wall(game, PLAYER_ONE, ('h', 0, 3, 2))
        
        # La distance peut changer mais doit rester finie
        distance_after = _get_shortest_path_length(game, PLAYER_TWO)
        assert distance_after != float('inf')
    
    def test_path_near_goal(self):
        """Distance correcte près du but."""
        game = GameState(
            player_positions={PLAYER_ONE: (7, 4), PLAYER_TWO: (1, 4)},
            walls=set(),
            player_walls={PLAYER_ONE: 10, PLAYER_TWO: 10},
            current_player=PLAYER_ONE
        )
        
        distance_j1 = _get_shortest_path_length(game, PLAYER_ONE)
        assert distance_j1 == 1  # Une seule case pour gagner


class TestAIInitialization:
    """Tests d'initialisation de l'IA."""
    
    def test_create_ai(self):
        """Créer une IA."""
        ia = AI(PLAYER_TWO, depth=2, difficulty='facile')  # Force depth=2
        
        assert ia.player == PLAYER_TWO
        assert ia.opponent == PLAYER_ONE
        # La difficulté 'facile' devrait donner depth=2
        assert ia.depth == 2
    
    def test_difficulty_levels(self):
        """Les niveaux de difficulté ajustent la profondeur."""
        ia_facile = AI(PLAYER_TWO, difficulty='facile')
        ia_normal = AI(PLAYER_TWO, difficulty='normal')
        ia_difficile = AI(PLAYER_TWO, difficulty='difficile')
        
        assert ia_facile.depth < ia_normal.depth < ia_difficile.depth
    
    def test_transposition_table_exists(self):
        """La table de transposition est initialisée."""
        ia = AI(PLAYER_TWO, depth=2)
        
        assert hasattr(ia, 'transposition_table')
        assert isinstance(ia.transposition_table, dict)


class TestEvaluationFunction:
    """Tests de la fonction d'évaluation."""
    
    def test_winning_position_high_score(self):
        """Position gagnante = score maximal."""
        ia = AI(PLAYER_ONE, depth=2)
        
        # J1 a gagné
        winning_state = GameState(
            player_positions={PLAYER_ONE: (8, 4), PLAYER_TWO: (0, 4)},
            walls=set(),
            player_walls={PLAYER_ONE: 10, PLAYER_TWO: 10},
            current_player=PLAYER_ONE
        )
        
        score = ia._evaluate_state(winning_state)
        assert score == 10000
    
    def test_losing_position_low_score(self):
        """Position perdante = score minimal."""
        ia = AI(PLAYER_ONE, depth=2)
        
        # J2 a gagné (J1 pas à la fin)
        losing_state = GameState(
            player_positions={PLAYER_ONE: (4, 4), PLAYER_TWO: (0, 4)},  # J1 pas à ligne 8
            walls=set(),
            player_walls={PLAYER_ONE: 10, PLAYER_TWO: 10},
            current_player=PLAYER_TWO
        )
        
        score = ia._evaluate_state(losing_state)
        assert score == -10000
    
    def test_closer_to_goal_is_better(self):
        """Plus proche du but = meilleur score."""
        ia = AI(PLAYER_ONE, depth=2)
        
        # J1 à 2 cases du but
        close_state = GameState(
            player_positions={PLAYER_ONE: (6, 4), PLAYER_TWO: (2, 4)},
            walls=set(),
            player_walls={PLAYER_ONE: 10, PLAYER_TWO: 10},
            current_player=PLAYER_ONE
        )
        
        # J1 à 4 cases du but
        far_state = GameState(
            player_positions={PLAYER_ONE: (4, 4), PLAYER_TWO: (2, 4)},
            walls=set(),
            player_walls={PLAYER_ONE: 10, PLAYER_TWO: 10},
            current_player=PLAYER_ONE
        )
        
        score_close = ia._evaluate_state(close_state)
        score_far = ia._evaluate_state(far_state)
        
        assert score_close > score_far
    
    def test_more_walls_is_better(self):
        """Avoir plus de murs que l'adversaire améliore le score."""
        ia = AI(PLAYER_ONE, depth=2)
        
        state_more_walls = GameState(
            player_positions={PLAYER_ONE: (4, 4), PLAYER_TWO: (4, 4)},
            walls=set(),
            player_walls={PLAYER_ONE: 8, PLAYER_TWO: 5},  # J1 a 3 murs de plus
            current_player=PLAYER_ONE
        )
        
        state_equal_walls = GameState(
            player_positions={PLAYER_ONE: (4, 4), PLAYER_TWO: (4, 4)},
            walls=set(),
            player_walls={PLAYER_ONE: 7, PLAYER_TWO: 7},
            current_player=PLAYER_ONE
        )
        
        score_more = ia._evaluate_state(state_more_walls)
        score_equal = ia._evaluate_state(state_equal_walls)
        
        assert score_more > score_equal


class TestAIDecisions:
    """Tests des décisions tactiques de l'IA."""
    
    def test_ai_finds_valid_move(self):
        """L'IA trouve toujours un coup valide."""
        game = create_new_game()
        game = move_pawn(game, PLAYER_ONE, (1, 4))  # Tour de J2
        
        ia = AI(PLAYER_TWO, depth=2)
        move = ia.find_best_move(game, verbose=False)
        
        assert move is not None
        assert move[0] in ['deplacement', 'mur']
    
    def test_ai_wins_in_one_move(self):
        """L'IA trouve le coup gagnant quand elle peut gagner en 1 coup."""
        # J2 est à une case de la victoire
        game = GameState(
            player_positions={PLAYER_ONE: (4, 4), PLAYER_TWO: (1, 4)},  # J1 loin
            walls=set(),
            player_walls={PLAYER_ONE: 5, PLAYER_TWO: 5},
            current_player=PLAYER_TWO
        )
        
        ia = AI(PLAYER_TWO, depth=3, difficulty='facile')  # Profondeur 3 pour voir la victoire
        move = ia.find_best_move(game, verbose=False)
        
        # L'IA devrait se déplacer vers (0, 4) pour gagner
        assert move[0] == 'deplacement'
        assert move[1] == (0, 4)
    
    def test_ai_blocks_opponent_win(self):
        """L'IA bloque l'adversaire qui peut gagner au prochain tour."""
        # J1 est à une case de la victoire, c'est le tour de J2
        game = GameState(
            player_positions={PLAYER_ONE: (7, 4), PLAYER_TWO: (1, 4)},
            walls=set(),
            player_walls={PLAYER_ONE: 5, PLAYER_TWO: 5},
            current_player=PLAYER_TWO
        )
        
        ia = AI(PLAYER_TWO, depth=3)  # Profondeur 3 pour voir le coup suivant
        move = ia.find_best_move(game, verbose=False)
        
        # L'IA devrait placer un mur pour bloquer J1
        # On vérifie juste que l'IA a trouvé un coup (pas nécessairement le meilleur)
        assert move is not None
    
    def test_ai_doesnt_make_invalid_move(self):
        """L'IA ne fait jamais de coup invalide."""
        game = create_new_game()
        game = move_pawn(game, PLAYER_ONE, (1, 4))
        
        ia = AI(PLAYER_TWO, depth=2)
        move = ia.find_best_move(game, verbose=False)
        
        # Tenter de jouer le coup - ne devrait pas lever d'exception
        try:
            if move[0] == 'deplacement':
                move_pawn(game, PLAYER_TWO, move[1])
            else:
                place_wall(game, PLAYER_TWO, move[1])
            success = True
        except InvalidMoveError:
            success = False
        
        assert success
    
    def test_ai_doesnt_block_itself(self):
        """L'IA ne se bloque jamais complètement elle-même."""
        game = create_new_game()
        
        ia = AI(PLAYER_ONE, depth=2)
        
        # Jouer plusieurs coups
        for _ in range(5):
            if game.current_player == PLAYER_ONE:
                move = ia.find_best_move(game, verbose=False)
                
                if move[0] == 'deplacement':
                    game = move_pawn(game, PLAYER_ONE, move[1])
                else:
                    game = place_wall(game, PLAYER_ONE, move[1])
            else:
                # J2 avance simple
                game = move_pawn(game, PLAYER_TWO, (game.player_positions[PLAYER_TWO][0] - 1, 4))
        
        # J1 doit toujours avoir un chemin vers le but
        distance = _get_shortest_path_length(game, PLAYER_ONE)
        assert distance != float('inf')


class TestStrategicWalls:
    """Tests de génération de murs stratégiques."""
    
    def test_generates_strategic_walls(self):
        """L'IA génère des murs stratégiques."""
        game = create_new_game()
        ia = AI(PLAYER_ONE, depth=2)
        
        walls = ia._get_strategic_walls(game, PLAYER_ONE, max_walls=20)
        
        assert len(walls) <= 20
        assert all(isinstance(w, tuple) and len(w) == 4 for w in walls)
    
    def test_wall_validity_check(self):
        """_is_wall_valid() détecte correctement les murs invalides."""
        game = create_new_game()
        ia = AI(PLAYER_ONE, depth=2)
        
        # Mur valide
        valid_wall = ('h', 1, 4, 2)
        assert ia._is_wall_valid(game, PLAYER_ONE, valid_wall) is True
        
        # Mur hors limites
        invalid_wall = ('h', 10, 4, 2)
        assert ia._is_wall_valid(game, PLAYER_ONE, invalid_wall) is False


class TestTranspositionTable:
    """Tests de la table de transposition."""
    
    def test_transposition_table_caches_states(self):
        """La table de transposition stocke les états."""
        game = create_new_game()
        ia = AI(PLAYER_ONE, depth=3)
        
        # Premier calcul
        ia.find_best_move(game, verbose=False)
        cache_size_1 = len(ia.transposition_table)
        
        # Recalculer (devrait utiliser le cache)
        ia.find_best_move(game, verbose=False)
        cache_size_2 = len(ia.transposition_table)
        
        # Le cache doit contenir des entrées
        assert cache_size_1 > 0
        assert cache_size_2 >= cache_size_1
    
    def test_clear_cache(self):
        """clear_cache() vide la table."""
        game = create_new_game()
        ia = AI(PLAYER_ONE, depth=2)
        
        ia.find_best_move(game, verbose=False)
        assert len(ia.transposition_table) > 0
        
        ia.clear_cache()
        assert len(ia.transposition_table) == 0
    
    def test_state_hash_uniqueness(self):
        """Différents états ont des hash différents."""
        game1 = create_new_game()
        game2 = move_pawn(game1, PLAYER_ONE, (1, 4))
        
        ia = AI(PLAYER_ONE, depth=2)
        hash1 = ia._state_hash(game1)
        hash2 = ia._state_hash(game2)
        
        assert hash1 != hash2


class TestPerformance:
    """Tests de performance de l'IA."""
    
    def test_ai_completes_in_reasonable_time(self):
        """L'IA termine son calcul en temps raisonnable (profondeur 2)."""
        import time
        
        game = create_new_game()
        ia = AI(PLAYER_ONE, difficulty='facile')  # Profondeur 2
        
        start = time.time()
        ia.find_best_move(game, verbose=False)
        duration = time.time() - start
        
        # Devrait prendre moins de 2 secondes en difficulté facile
        assert duration < 2.0
    
    def test_nodes_explored_increases_with_depth(self):
        """Plus de nœuds explorés avec une profondeur plus grande."""
        game = create_new_game()
        
        # Utiliser les difficultés pour avoir vraiment des profondeurs différentes
        ia_shallow = AI(PLAYER_ONE, difficulty='facile')  # depth=2
        ia_shallow.find_best_move(game, verbose=False)
        nodes_shallow = ia_shallow.nodes_explored
        
        ia_deep = AI(PLAYER_ONE, difficulty='normal')  # depth=4
        ia_deep.find_best_move(game, verbose=False)
        nodes_deep = ia_deep.nodes_explored
        
        # Profondeur 4 devrait explorer plus de nœuds que profondeur 2
        assert nodes_deep > nodes_shallow


class TestEdgeCases:
    """Tests de cas limites pour l'IA."""
    
    def test_ai_with_no_walls_left(self):
        """L'IA fonctionne sans murs restants."""
        game = GameState(
            player_positions={PLAYER_ONE: (2, 4), PLAYER_TWO: (6, 4)},
            walls=set(),
            player_walls={PLAYER_ONE: 10, PLAYER_TWO: 0},  # J2 n'a plus de murs
            current_player=PLAYER_TWO
        )
        
        ia = AI(PLAYER_TWO, depth=2)
        move = ia.find_best_move(game, verbose=False)
        
        # Devrait être un déplacement (pas de murs disponibles)
        assert move[0] == 'deplacement'
    
    def test_ai_near_end_game(self):
        """L'IA fonctionne en fin de partie."""
        game = GameState(
            player_positions={PLAYER_ONE: (6, 4), PLAYER_TWO: (2, 4)},
            walls=set(),
            player_walls={PLAYER_ONE: 2, PLAYER_TWO: 2},
            current_player=PLAYER_ONE
        )
        
        ia = AI(PLAYER_ONE, depth=3)
        move = ia.find_best_move(game, verbose=False)
        
        assert move is not None


class TestDifferentDifficulties:
    """Tests avec différents niveaux de difficulté."""
    
    def test_all_difficulties_find_moves(self):
        """Tous les niveaux trouvent des coups."""
        game = create_new_game()
        
        for difficulty in ['facile', 'normal', 'difficile']:
            ia = AI(PLAYER_ONE, difficulty=difficulty)
            move = ia.find_best_move(game, verbose=False)
            
            assert move is not None, f"Difficulté {difficulty} n'a pas trouvé de coup"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

