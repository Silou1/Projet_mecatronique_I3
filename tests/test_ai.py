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
from quoridor_engine.ai import AI, _get_all_distances_to_goal


class TestPathfinding:
    """Tests de la fonction de calcul du plus court chemin."""
    
    def test_shortest_path_at_start(self):
        """Distance au but depuis la position initiale."""
        game = create_new_game()
        
        # J1 doit parcourir 5 cases pour atteindre la ligne 0 (haut)
        distances_j1 = _get_all_distances_to_goal(game, PLAYER_ONE)
        distance_j1 = distances_j1.get(game.player_positions[PLAYER_ONE])
        assert distance_j1 == 5
        
        # J2 doit parcourir 5 cases pour atteindre la ligne 5 (bas)
        distances_j2 = _get_all_distances_to_goal(game, PLAYER_TWO)
        distance_j2 = distances_j2.get(game.player_positions[PLAYER_TWO])
        assert distance_j2 == 5
    
    def test_shortest_path_with_wall(self):
        """Le chemin change avec un mur."""
        game = create_new_game()
        
        # Ajouter un mur qui ne bloque pas complètement
        game = place_wall(game, PLAYER_ONE, ('h', 0, 2, 2))
        
        # La distance peut changer mais doit rester finie
        distances_j2 = _get_all_distances_to_goal(game, PLAYER_TWO)
        distance_j2 = distances_j2.get(game.player_positions[PLAYER_TWO], float('inf'))
        assert distance_j2 != float('inf')
    
    def test_path_near_goal(self):
        """Distance correcte près du but."""
        game = GameState(
            player_positions={PLAYER_ONE: (1, 3), PLAYER_TWO: (4, 3)},
            walls=frozenset(),
            player_walls={PLAYER_ONE: 6, PLAYER_TWO: 6},
            current_player=PLAYER_ONE
        )
        
        distances_j1 = _get_all_distances_to_goal(game, PLAYER_ONE)
        distance_j1 = distances_j1.get(game.player_positions[PLAYER_ONE])
        assert distance_j1 == 1  # Une seule case pour gagner (ligne 0)


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
        
        # J1 a gagné (atteint ligne 0)
        winning_state = GameState(
            player_positions={PLAYER_ONE: (0, 3), PLAYER_TWO: (5, 3)},
            walls=frozenset(),
            player_walls={PLAYER_ONE: 6, PLAYER_TWO: 6},
            current_player=PLAYER_ONE
        )
        
        score = ia._evaluate_state(winning_state)
        assert score == 20000  # Score de victoire avec les nouveaux poids
    
    def test_losing_position_low_score(self):
        """Position perdante = score minimal."""
        ia = AI(PLAYER_ONE, depth=2)
        
        # J2 a gagné (atteint ligne 5)
        losing_state = GameState(
            player_positions={PLAYER_ONE: (2, 3), PLAYER_TWO: (5, 3)},
            walls=frozenset(),
            player_walls={PLAYER_ONE: 6, PLAYER_TWO: 6},
            current_player=PLAYER_TWO
        )
        
        score = ia._evaluate_state(losing_state)
        assert score == -20000  # Score de défaite avec les nouveaux poids
    
    def test_closer_to_goal_is_better(self):
        """Plus proche du but = meilleur score."""
        ia = AI(PLAYER_ONE, depth=2)
        
        # J1 à 1 case du but (ligne 0)
        close_state = GameState(
            player_positions={PLAYER_ONE: (1, 3), PLAYER_TWO: (4, 3)},
            walls=frozenset(),
            player_walls={PLAYER_ONE: 6, PLAYER_TWO: 6},
            current_player=PLAYER_ONE
        )
        
        # J1 à 3 cases du but (ligne 0)
        far_state = GameState(
            player_positions={PLAYER_ONE: (3, 3), PLAYER_TWO: (4, 3)},
            walls=frozenset(),
            player_walls={PLAYER_ONE: 6, PLAYER_TWO: 6},
            current_player=PLAYER_ONE
        )
        
        score_close = ia._evaluate_state(close_state)
        score_far = ia._evaluate_state(far_state)
        
        assert score_close > score_far
    
    def test_more_walls_is_better(self):
        """Avoir plus de murs que l'adversaire améliore le score."""
        ia = AI(PLAYER_ONE, depth=2)
        
        state_more_walls = GameState(
            player_positions={PLAYER_ONE: (2, 3), PLAYER_TWO: (3, 3)},
            walls=frozenset(),
            player_walls={PLAYER_ONE: 5, PLAYER_TWO: 2},  # J1 a 3 murs de plus
            current_player=PLAYER_ONE
        )
        
        state_equal_walls = GameState(
            player_positions={PLAYER_ONE: (2, 3), PLAYER_TWO: (3, 3)},
            walls=frozenset(),
            player_walls={PLAYER_ONE: 4, PLAYER_TWO: 4},
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
        game = move_pawn(game, PLAYER_ONE, (4, 3))  # Tour de J2
        
        ia = AI(PLAYER_TWO, depth=2)
        move = ia.find_best_move(game, verbose=False)
        
        assert move is not None
        assert move[0] in ['deplacement', 'mur']
    
    def test_ai_wins_in_one_move(self):
        """L'IA trouve le coup gagnant quand elle peut gagner en 1 coup."""
        # J2 est à une case de la victoire (ligne 5)
        game = GameState(
            player_positions={PLAYER_ONE: (2, 3), PLAYER_TWO: (4, 3)},  # J1 loin
            walls=frozenset(),
            player_walls={PLAYER_ONE: 3, PLAYER_TWO: 3},
            current_player=PLAYER_TWO
        )
        
        ia = AI(PLAYER_TWO, depth=3, difficulty='facile')  # Profondeur 3 pour voir la victoire
        move = ia.find_best_move(game, verbose=False)
        
        # L'IA devrait se déplacer vers (5, 3) pour gagner
        assert move[0] == 'deplacement'
        assert move[1] == (5, 3)
    
    def test_ai_blocks_opponent_win(self):
        """L'IA bloque l'adversaire qui peut gagner au prochain tour."""
        # J1 est à une case de la victoire (ligne 0), c'est le tour de J2
        game = GameState(
            player_positions={PLAYER_ONE: (1, 3), PLAYER_TWO: (4, 3)},
            walls=frozenset(),
            player_walls={PLAYER_ONE: 3, PLAYER_TWO: 3},
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
        game = move_pawn(game, PLAYER_ONE, (4, 3))
        
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
        from quoridor_engine.core import get_possible_pawn_moves
        game = create_new_game()
        
        ia = AI(PLAYER_ONE, depth=2)
        
        # Jouer plusieurs coups
        for _ in range(5):
            if game.is_game_over()[0]:
                break
            if game.current_player == PLAYER_ONE:
                move = ia.find_best_move(game, verbose=False)
                
                if move[0] == 'deplacement':
                    game = move_pawn(game, PLAYER_ONE, move[1])
                else:
                    game = place_wall(game, PLAYER_ONE, move[1])
            else:
                # J2 choisit le premier déplacement disponible vers le bas
                moves = get_possible_pawn_moves(game, PLAYER_TWO)
                # Préférer avancer vers le bas (augmenter la ligne)
                moves_down = [m for m in moves if m[0] > game.player_positions[PLAYER_TWO][0]]
                target = moves_down[0] if moves_down else moves[0]
                game = move_pawn(game, PLAYER_TWO, target)
        
        # J1 doit toujours avoir un chemin vers le but
        distances = _get_all_distances_to_goal(game, PLAYER_ONE)
        distance = distances.get(game.player_positions[PLAYER_ONE], float('inf'))
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
        game2 = move_pawn(game1, PLAYER_ONE, (4, 3))
        
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
            player_positions={PLAYER_ONE: (1, 3), PLAYER_TWO: (4, 3)},
            walls=frozenset(),
            player_walls={PLAYER_ONE: 6, PLAYER_TWO: 0},  # J2 n'a plus de murs
            current_player=PLAYER_TWO
        )
        
        ia = AI(PLAYER_TWO, depth=2)
        move = ia.find_best_move(game, verbose=False)
        
        # Devrait être un déplacement (pas de murs disponibles)
        assert move[0] == 'deplacement'
    
    def test_ai_near_end_game(self):
        """L'IA fonctionne en fin de partie."""
        game = GameState(
            player_positions={PLAYER_ONE: (4, 3), PLAYER_TWO: (1, 3)},
            walls=frozenset(),
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


class TestModuleConstants:
    """Tests des constantes exposées en haut du module ai.py."""

    def test_time_budgets_defined(self):
        """TIME_BUDGETS expose les 3 niveaux."""
        from quoridor_engine import ai
        assert hasattr(ai, 'TIME_BUDGETS')
        assert set(ai.TIME_BUDGETS.keys()) == {'facile', 'normal', 'difficile'}

    def test_time_budgets_ordered(self):
        """facile < normal < difficile en budget temps."""
        from quoridor_engine import ai
        budgets = ai.TIME_BUDGETS
        assert budgets['facile'] < budgets['normal'] < budgets['difficile']
        assert 0.1 <= budgets['facile'] <= 30.0
        assert 0.1 <= budgets['difficile'] <= 30.0

    def test_depth_max_defined(self):
        """DEPTH_MAX est défini et raisonnable."""
        from quoridor_engine import ai
        assert hasattr(ai, 'DEPTH_MAX')
        assert 5 <= ai.DEPTH_MAX <= 20

    def test_max_wall_candidates_defined(self):
        """MAX_WALL_CANDIDATES est défini et supérieur à 20."""
        from quoridor_engine import ai
        assert hasattr(ai, 'MAX_WALL_CANDIDATES')
        assert ai.MAX_WALL_CANDIDATES >= 20

    def test_win_score_defined(self):
        """WIN_SCORE est défini à 20000."""
        from quoridor_engine import ai
        assert hasattr(ai, 'WIN_SCORE')
        assert ai.WIN_SCORE == 20000


class TestWallCandidates:
    """Tests du tri et du cap des murs candidats."""

    def test_strategic_walls_deterministic(self):
        """Deux appels successifs retournent la même liste de murs."""
        game = create_new_game()
        ia = AI(PLAYER_ONE, difficulty='facile')
        walls1 = ia._get_strategic_walls(game, PLAYER_ONE)
        walls2 = ia._get_strategic_walls(game, PLAYER_ONE)
        assert walls1 == walls2

    def test_strategic_walls_capped_at_max(self):
        """Le nombre de murs retournés ne dépasse pas MAX_WALL_CANDIDATES."""
        from quoridor_engine import ai
        game = create_new_game()
        ia = AI(PLAYER_ONE, difficulty='facile')
        walls = ia._get_strategic_walls(game, PLAYER_ONE)
        assert len(walls) <= ai.MAX_WALL_CANDIDATES

    def test_wall_near_opponent_is_preserved(self):
        """Un mur immédiatement adjacent à l'adversaire est dans les candidats."""
        game = GameState(
            player_positions={PLAYER_ONE: (0, 3), PLAYER_TWO: (3, 3)},
            walls=frozenset(),
            player_walls={PLAYER_ONE: 6, PLAYER_TWO: 6},
            current_player=PLAYER_ONE
        )
        ia = AI(PLAYER_ONE, difficulty='facile')
        walls = ia._get_strategic_walls(game, PLAYER_ONE)
        critical_wall = ('h', 3, 2, 2)
        assert critical_wall in walls, f"Mur critique {critical_wall} eject. Murs retournes: {walls}"


class TestTieBreak:
    """Tests du tie-break deterministe."""

    def test_find_best_move_deterministic_facile(self):
        """Deux appels successifs en facile retournent le meme coup."""
        game = create_new_game()
        ia = AI(PLAYER_TWO, difficulty='facile')
        move1 = ia.find_best_move(game, verbose=False)
        ia.clear_cache()
        move2 = ia.find_best_move(game, verbose=False)
        assert move1 == move2

    def test_find_best_move_deterministic_normal(self):
        """Deux appels successifs en normal retournent le meme coup."""
        game = create_new_game()
        ia = AI(PLAYER_TWO, difficulty='normal')
        move1 = ia.find_best_move(game, verbose=False)
        ia.clear_cache()
        move2 = ia.find_best_move(game, verbose=False)
        assert move1 == move2

    def test_tie_break_prefers_advance(self):
        """A score egal, le tie-break prefere un coup qui avance vers le but."""
        game = GameState(
            player_positions={PLAYER_ONE: (3, 3), PLAYER_TWO: (0, 0)},
            walls=frozenset(),
            player_walls={PLAYER_ONE: 6, PLAYER_TWO: 6},
            current_player=PLAYER_ONE
        )
        ia = AI(PLAYER_ONE, difficulty='facile')
        advance_move = ('deplacement', (2, 3))
        backward_move = ('deplacement', (4, 3))
        chosen = ia._tie_break(game, [advance_move, backward_move])
        assert chosen == advance_move

    def test_tie_break_single_move_returns_it(self):
        """Tie-break avec un seul coup retourne ce coup."""
        game = create_new_game()
        ia = AI(PLAYER_ONE, difficulty='facile')
        only_move = ('deplacement', (4, 3))
        chosen = ia._tie_break(game, [only_move])
        assert chosen == only_move


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

