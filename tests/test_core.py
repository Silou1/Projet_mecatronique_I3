# -*- coding: utf-8 -*-
"""
Tests unitaires pour les structures de données et fonctions de base du moteur Quoridor.
"""

import pytest
from quoridor_engine.core import (
    GameState,
    create_new_game,
    InvalidMoveError,
    PLAYER_ONE,
    PLAYER_TWO,
    BOARD_SIZE,
    MAX_WALLS_PER_PLAYER
)


class TestGameStateInitialization:
    """Tests d'initialisation de l'état du jeu."""
    
    def test_create_new_game(self):
        """Test de création d'une nouvelle partie."""
        game = create_new_game()
        
        assert isinstance(game, GameState)
        assert game.current_player == PLAYER_ONE
        assert len(game.walls) == 0
        
    def test_initial_positions(self):
        """Test des positions initiales des joueurs."""
        game = create_new_game()
        
        # Joueur 1 en haut au centre
        assert game.player_positions[PLAYER_ONE] == (0, BOARD_SIZE // 2)
        
        # Joueur 2 en bas au centre
        assert game.player_positions[PLAYER_TWO] == (BOARD_SIZE - 1, BOARD_SIZE // 2)
    
    def test_initial_walls(self):
        """Test du nombre initial de murs."""
        game = create_new_game()
        
        assert game.player_walls[PLAYER_ONE] == MAX_WALLS_PER_PLAYER
        assert game.player_walls[PLAYER_TWO] == MAX_WALLS_PER_PLAYER


class TestGameOver:
    """Tests de détection de fin de partie."""
    
    def test_game_not_over_at_start(self):
        """La partie n'est pas terminée au début."""
        game = create_new_game()
        is_over, winner = game.is_game_over()
        
        assert is_over is False
        assert winner is None
    
    def test_player_one_wins(self):
        """Joueur 1 gagne en atteignant la ligne 8."""
        game = GameState(
            player_positions={PLAYER_ONE: (8, 4), PLAYER_TWO: (0, 4)},
            walls=set(),
            player_walls={PLAYER_ONE: 10, PLAYER_TWO: 10},
            current_player=PLAYER_ONE
        )
        
        is_over, winner = game.is_game_over()
        
        assert is_over is True
        assert winner == PLAYER_ONE
    
    def test_player_two_wins(self):
        """Joueur 2 gagne en atteignant la ligne 0."""
        game = GameState(
            player_positions={PLAYER_ONE: (4, 4), PLAYER_TWO: (0, 4)},  # J1 pas à la fin
            walls=set(),
            player_walls={PLAYER_ONE: 10, PLAYER_TWO: 10},
            current_player=PLAYER_TWO
        )
        
        is_over, winner = game.is_game_over()
        
        assert is_over is True
        assert winner == PLAYER_TWO
    
    def test_game_continues_near_end(self):
        """La partie continue même si un joueur est proche de la fin."""
        game = GameState(
            player_positions={PLAYER_ONE: (7, 4), PLAYER_TWO: (1, 4)},
            walls=set(),
            player_walls={PLAYER_ONE: 5, PLAYER_TWO: 5},
            current_player=PLAYER_ONE
        )
        
        is_over, winner = game.is_game_over()
        
        assert is_over is False
        assert winner is None


class TestGameStateImmutability:
    """Tests de l'immuabilité de GameState."""
    
    def test_gamestate_is_frozen(self):
        """GameState doit être immuable (frozen)."""
        game = create_new_game()
        
        with pytest.raises(Exception):  # dataclass frozen raises FrozenInstanceError
            game.current_player = PLAYER_TWO
    
    def test_walls_set_is_copied(self):
        """Les murs doivent être copiés, pas partagés."""
        game = create_new_game()
        walls_before = game.walls.copy()
        
        # Tenter de modifier l'ensemble (ne devrait pas affecter l'état)
        new_wall = ('h', 1, 1, 2)
        walls_before.add(new_wall)
        
        # L'état du jeu ne doit pas avoir changé
        assert new_wall not in game.walls


class TestConstants:
    """Tests des constantes du jeu."""
    
    def test_board_size(self):
        """Le plateau doit faire 9x9."""
        assert BOARD_SIZE == 9
    
    def test_max_walls(self):
        """Chaque joueur doit avoir 10 murs."""
        assert MAX_WALLS_PER_PLAYER == 10
    
    def test_player_constants(self):
        """Vérification des identifiants de joueurs."""
        assert PLAYER_ONE == 'j1'
        assert PLAYER_TWO == 'j2'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

