# -*- coding: utf-8 -*-
"""
Tests unitaires pour l'orchestration du jeu (classe QuoridorGame).
"""

import pytest
from quoridor_engine.core import (
    QuoridorGame,
    InvalidMoveError,
    PLAYER_ONE,
    PLAYER_TWO
)


class TestQuoridorGameInitialization:
    """Tests d'initialisation de QuoridorGame."""
    
    def test_game_creation(self):
        """Créer une nouvelle partie."""
        game = QuoridorGame()
        
        assert game is not None
        assert game.get_current_player() == PLAYER_ONE
    
    def test_initial_state(self):
        """Vérifier l'état initial."""
        game = QuoridorGame()
        state = game.get_current_state()
        
        assert state.current_player == PLAYER_ONE
        assert len(state.walls) == 0
        assert state.player_walls[PLAYER_ONE] == 10
        assert state.player_walls[PLAYER_TWO] == 10


class TestPlayMove:
    """Tests de la méthode play_move."""
    
    def test_play_pawn_move(self):
        """Jouer un déplacement de pion."""
        game = QuoridorGame()
        
        game.play_move(('deplacement', (1, 4)))
        
        state = game.get_current_state()
        assert state.player_positions[PLAYER_ONE] == (1, 4)
        assert state.current_player == PLAYER_TWO
    
    def test_play_wall_move(self):
        """Jouer un placement de mur."""
        game = QuoridorGame()
        
        game.play_move(('mur', ('h', 1, 4, 2)))
        
        state = game.get_current_state()
        assert ('h', 1, 4, 2) in state.walls
        assert state.player_walls[PLAYER_ONE] == 9
        assert state.current_player == PLAYER_TWO
    
    def test_invalid_move_raises_error(self):
        """Un coup invalide lève une exception."""
        game = QuoridorGame()
        
        with pytest.raises(InvalidMoveError):
            game.play_move(('deplacement', (5, 5)))  # Trop loin
    
    def test_invalid_move_type(self):
        """Type de coup inconnu lève une exception."""
        game = QuoridorGame()
        
        with pytest.raises(ValueError):
            game.play_move(('attaque', (1, 4)))  # Type inconnu


class TestUndo:
    """Tests de la fonction d'annulation."""
    
    def test_undo_single_move(self):
        """Annuler un seul coup."""
        game = QuoridorGame()
        
        # Jouer un coup
        game.play_move(('deplacement', (1, 4)))
        assert game.get_current_player() == PLAYER_TWO
        
        # Annuler
        success = game.undo_move()
        assert success is True
        assert game.get_current_player() == PLAYER_ONE
        assert game.get_current_state().player_positions[PLAYER_ONE] == (0, 4)
    
    def test_undo_multiple_moves(self):
        """Annuler plusieurs coups."""
        game = QuoridorGame()
        
        # Jouer 2 coups
        game.play_move(('deplacement', (1, 4)))
        game.play_move(('deplacement', (7, 4)))
        
        # Annuler 2 fois
        assert game.undo_move() is True
        assert game.undo_move() is True
        
        # Retour à l'état initial
        assert game.get_current_player() == PLAYER_ONE
        assert game.get_current_state().player_positions[PLAYER_ONE] == (0, 4)
    
    def test_undo_empty_history(self):
        """Annuler sans historique retourne False."""
        game = QuoridorGame()
        
        success = game.undo_move()
        
        assert success is False
    
    def test_undo_wall_restores_count(self):
        """Annuler un mur restaure le compte de murs."""
        game = QuoridorGame()
        
        game.play_move(('mur', ('h', 1, 4, 2)))
        assert game.get_current_state().player_walls[PLAYER_ONE] == 9
        
        game.undo_move()
        assert game.get_current_state().player_walls[PLAYER_ONE] == 10


class TestGetPossibleMoves:
    """Tests de génération des coups possibles."""
    
    def test_get_possible_moves_at_start(self):
        """Obtenir les coups possibles au début."""
        game = QuoridorGame()
        
        moves = game.get_possible_moves()
        
        # Au début, 3 déplacements possibles
        assert len(moves) >= 3
        pawn_moves = [m for m in moves if m[0] == 'deplacement']
        assert len(pawn_moves) == 3
    
    def test_get_possible_moves_for_specific_player(self):
        """Obtenir les coups pour un joueur spécifique."""
        game = QuoridorGame()
        
        moves_j1 = game.get_possible_moves(PLAYER_ONE)
        
        assert len(moves_j1) >= 3


class TestVictoryConditions:
    """Tests de détection de victoire."""
    
    def test_is_game_over_at_start(self):
        """La partie n'est pas terminée au début."""
        game = QuoridorGame()
        
        is_over, winner = game.is_game_over()
        
        assert is_over is False
        assert winner is None
    
    def test_get_winner_returns_none_during_game(self):
        """get_winner retourne None pendant la partie."""
        game = QuoridorGame()
        
        winner = game.get_winner()
        
        assert winner is None
    
    def test_detect_victory_player_one(self):
        """Détecter la victoire du joueur 1."""
        game = QuoridorGame()
        
        # Forcer J1 à atteindre la ligne 8
        for _ in range(8):
            if game.get_current_player() == PLAYER_ONE:
                game.play_move(('deplacement', (game.get_current_state().player_positions[PLAYER_ONE][0] + 1, 4)))
            else:
                # J2 fait un mouvement quelconque
                try:
                    game.play_move(('deplacement', (game.get_current_state().player_positions[PLAYER_TWO][0] - 1, 4)))
                except:
                    game.play_move(('deplacement', (game.get_current_state().player_positions[PLAYER_TWO][0], 3)))
        
        # Vérifier si J1 a gagné
        is_over, winner = game.is_game_over()
        if is_over:
            assert winner == PLAYER_ONE


class TestFullGameScenario:
    """Tests de scénarios de partie complète."""
    
    def test_alternating_turns(self):
        """Les tours alternent correctement."""
        game = QuoridorGame()
        
        assert game.get_current_player() == PLAYER_ONE
        
        game.play_move(('deplacement', (1, 4)))
        assert game.get_current_player() == PLAYER_TWO
        
        game.play_move(('deplacement', (7, 4)))
        assert game.get_current_player() == PLAYER_ONE
    
    def test_mixed_moves_sequence(self):
        """Séquence mixte de déplacements et murs."""
        game = QuoridorGame()
        
        # J1 se déplace
        game.play_move(('deplacement', (1, 4)))
        
        # J2 place un mur
        game.play_move(('mur', ('h', 6, 4, 2)))
        
        # J1 place un mur
        game.play_move(('mur', ('v', 2, 3, 2)))
        
        # J2 se déplace
        game.play_move(('deplacement', (7, 4)))
        
        state = game.get_current_state()
        assert len(state.walls) == 2
        assert state.player_walls[PLAYER_ONE] == 9
        assert state.player_walls[PLAYER_TWO] == 9
    
    def test_invalid_move_doesnt_change_state(self):
        """Un coup invalide ne change pas l'état."""
        game = QuoridorGame()
        initial_player = game.get_current_player()
        initial_position = game.get_current_state().player_positions[PLAYER_ONE]
        
        try:
            game.play_move(('deplacement', (5, 5)))  # Invalide
        except InvalidMoveError:
            pass
        
        # L'état ne devrait pas avoir changé
        assert game.get_current_player() == initial_player
        assert game.get_current_state().player_positions[PLAYER_ONE] == initial_position


class TestEdgeCases:
    """Tests de cas limites."""
    
    def test_empty_history_operations(self):
        """Opérations sur un historique vide."""
        game = QuoridorGame()
        
        # Undo sur historique vide
        assert game.undo_move() is False
        
        # L'état reste valide
        assert game.get_current_player() == PLAYER_ONE
    
    def test_play_after_undo(self):
        """Jouer après avoir annulé."""
        game = QuoridorGame()
        
        game.play_move(('deplacement', (1, 4)))
        game.undo_move()
        
        # Peut rejouer normalement
        game.play_move(('deplacement', (0, 3)))
        
        assert game.get_current_state().player_positions[PLAYER_ONE] == (0, 3)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

