# -*- coding: utf-8 -*-
"""
Tests unitaires pour les déplacements des pions.
"""

import pytest
from quoridor_engine.core import (
    GameState,
    create_new_game,
    get_possible_pawn_moves,
    move_pawn,
    InvalidMoveError,
    PLAYER_ONE,
    PLAYER_TWO
)


class TestBasicMoves:
    """Tests des déplacements de base."""
    
    def test_initial_moves_player_one(self):
        """Joueur 1 peut se déplacer dans 3 directions au début."""
        game = create_new_game()
        moves = get_possible_pawn_moves(game, PLAYER_ONE)
        
        assert len(moves) == 3
        assert (7, 4) in moves  # Haut (vers l'objectif)
        assert (8, 3) in moves  # Gauche
        assert (8, 5) in moves  # Droite
    
    def test_move_changes_position(self):
        """Déplacer un pion change sa position."""
        game = create_new_game()
        new_game = move_pawn(game, PLAYER_ONE, (7, 4))
        
        assert new_game.player_positions[PLAYER_ONE] == (7, 4)
        assert new_game.player_positions[PLAYER_TWO] == game.player_positions[PLAYER_TWO]
    
    def test_move_changes_turn(self):
        """Déplacer un pion change le joueur courant."""
        game = create_new_game()
        new_game = move_pawn(game, PLAYER_ONE, (7, 4))
        
        assert game.current_player == PLAYER_ONE
        assert new_game.current_player == PLAYER_TWO
    
    def test_cannot_move_out_of_bounds(self):
        """Impossible de sortir du plateau."""
        game = create_new_game()
        moves = get_possible_pawn_moves(game, PLAYER_ONE)
        
        # Pas de mouvement vers le bas (hors limites)
        assert (9, 4) not in moves
    
    def test_invalid_move_raises_error(self):
        """Un mouvement invalide lève une exception."""
        game = create_new_game()
        
        with pytest.raises(InvalidMoveError):
            move_pawn(game, PLAYER_ONE, (5, 5))  # Trop loin
    
    def test_wrong_player_turn_raises_error(self):
        """Jouer hors de son tour lève une exception."""
        game = create_new_game()
        
        with pytest.raises(InvalidMoveError):
            move_pawn(game, PLAYER_TWO, (1, 4))  # C'est le tour de J1


class TestWallBlocking:
    """Tests des murs qui bloquent les déplacements."""
    
    def test_horizontal_wall_blocks_movement(self):
        """Un mur horizontal bloque le passage vertical."""
        game = GameState(
            player_positions={PLAYER_ONE: (8, 4), PLAYER_TWO: (0, 4)},
            walls={('h', 7, 4, 2)},  # Mur horizontal au-dessus de J1
            player_walls={PLAYER_ONE: 9, PLAYER_TWO: 10},
            current_player=PLAYER_ONE
        )
        
        moves = get_possible_pawn_moves(game, PLAYER_ONE)
        
        assert (7, 4) not in moves  # Bloqué par le mur
        assert (8, 3) in moves      # Peut aller à gauche
        assert (8, 5) in moves      # Peut aller à droite
    
    def test_vertical_wall_blocks_movement(self):
        """Un mur vertical bloque le passage horizontal."""
        game = GameState(
            player_positions={PLAYER_ONE: (4, 4), PLAYER_TWO: (0, 4)},
            walls={('v', 4, 4, 2)},  # Mur vertical à droite de J1
            player_walls={PLAYER_ONE: 9, PLAYER_TWO: 10},
            current_player=PLAYER_ONE
        )
        
        moves = get_possible_pawn_moves(game, PLAYER_ONE)
        
        assert (4, 5) not in moves  # Bloqué par le mur
        assert (4, 3) in moves      # Peut aller à gauche


class TestJumps:
    """Tests des sauts par-dessus l'adversaire."""
    
    def test_simple_jump(self):
        """Saut simple par-dessus l'adversaire."""
        game = GameState(
            player_positions={PLAYER_ONE: (3, 4), PLAYER_TWO: (4, 4)},
            walls=set(),
            player_walls={PLAYER_ONE: 10, PLAYER_TWO: 10},
            current_player=PLAYER_ONE
        )
        
        moves = get_possible_pawn_moves(game, PLAYER_ONE)
        
        assert (5, 4) in moves  # Saut simple vers le bas
        assert (4, 4) not in moves  # Ne peut pas occuper la case de l'adversaire
    
    def test_diagonal_jump_when_blocked(self):
        """Saut diagonal si le saut simple est bloqué."""
        game = GameState(
            player_positions={PLAYER_ONE: (3, 4), PLAYER_TWO: (4, 4)},
            walls={('h', 4, 4, 2)},  # Mur derrière J2
            player_walls={PLAYER_ONE: 9, PLAYER_TWO: 10},
            current_player=PLAYER_ONE
        )
        
        moves = get_possible_pawn_moves(game, PLAYER_ONE)
        
        assert (5, 4) not in moves  # Saut simple bloqué
        assert (4, 3) in moves      # Saut diagonal gauche
        assert (4, 5) in moves      # Saut diagonal droite
    
    def test_horizontal_face_off(self):
        """Face-à-face horizontal."""
        game = GameState(
            player_positions={PLAYER_ONE: (4, 3), PLAYER_TWO: (4, 4)},
            walls=set(),
            player_walls={PLAYER_ONE: 10, PLAYER_TWO: 10},
            current_player=PLAYER_ONE
        )
        
        moves = get_possible_pawn_moves(game, PLAYER_ONE)
        
        assert (4, 5) in moves  # Saut simple horizontal
    
    def test_jump_at_board_edge(self):
        """Saut diagonal quand l'adversaire est au bord."""
        game = GameState(
            player_positions={PLAYER_ONE: (7, 4), PLAYER_TWO: (8, 4)},
            walls=set(),
            player_walls={PLAYER_ONE: 10, PLAYER_TWO: 10},
            current_player=PLAYER_ONE
        )
        
        moves = get_possible_pawn_moves(game, PLAYER_ONE)
        
        # Saut simple impossible (hors limites), donc sauts diagonaux
        assert (8, 3) in moves  # Diagonal gauche
        assert (8, 5) in moves  # Diagonal droite


class TestComplexScenarios:
    """Tests de scénarios complexes."""
    
    def test_surrounded_by_walls(self):
        """Pion avec des murs autour (mais pas complètement bloqué)."""
        game = GameState(
            player_positions={PLAYER_ONE: (4, 4), PLAYER_TWO: (8, 4)},
            walls={
                ('h', 3, 4, 2),  # Mur horizontal au-dessus
                ('h', 4, 4, 2),  # Mur horizontal en dessous
            },
            player_walls={PLAYER_ONE: 8, PLAYER_TWO: 8},
            current_player=PLAYER_ONE
        )
        
        moves = get_possible_pawn_moves(game, PLAYER_ONE)
        
        # Peut encore aller à gauche et à droite
        assert (4, 3) in moves  # Gauche
        assert (4, 5) in moves  # Droite
        # Mais pas haut ou bas (bloqués par les murs)
        assert (3, 4) not in moves
        assert (5, 4) not in moves
    
    def test_corner_position(self):
        """Mouvements depuis un coin."""
        game = GameState(
            player_positions={PLAYER_ONE: (0, 0), PLAYER_TWO: (8, 8)},
            walls=set(),
            player_walls={PLAYER_ONE: 10, PLAYER_TWO: 10},
            current_player=PLAYER_ONE
        )
        
        moves = get_possible_pawn_moves(game, PLAYER_ONE)
        
        assert len(moves) == 2  # Seulement 2 directions possibles depuis un coin
        assert (1, 0) in moves  # Bas
        assert (0, 1) in moves  # Droite


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

