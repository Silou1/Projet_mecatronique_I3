# -*- coding: utf-8 -*-
"""
Tests unitaires pour la pose et validation des murs.
"""

import pytest
from quoridor_engine.core import (
    GameState,
    create_new_game,
    place_wall,
    interpret_double_click,
    InvalidMoveError,
    PLAYER_ONE,
    PLAYER_TWO
)


class TestWallPlacement:
    """Tests de placement de murs."""
    
    def test_place_valid_wall(self):
        """Placer un mur valide."""
        game = create_new_game()
        wall = ('h', 1, 4, 2)
        
        new_game = place_wall(game, PLAYER_ONE, wall)
        
        assert wall in new_game.walls
        assert new_game.player_walls[PLAYER_ONE] == 9
        assert new_game.current_player == PLAYER_TWO
    
    def test_place_horizontal_wall(self):
        """Placer un mur horizontal."""
        game = create_new_game()
        wall = ('h', 2, 3, 2)
        
        new_game = place_wall(game, PLAYER_ONE, wall)
        
        assert wall in new_game.walls
    
    def test_place_vertical_wall(self):
        """Placer un mur vertical."""
        game = create_new_game()
        wall = ('v', 3, 2, 2)
        
        new_game = place_wall(game, PLAYER_ONE, wall)
        
        assert wall in new_game.walls
    
    def test_wall_count_decreases(self):
        """Le nombre de murs diminue après placement."""
        game = create_new_game()
        wall = ('h', 1, 4, 2)
        
        new_game = place_wall(game, PLAYER_ONE, wall)
        
        assert new_game.player_walls[PLAYER_ONE] == 9
        assert new_game.player_walls[PLAYER_TWO] == 10


class TestWallValidation:
    """Tests de validation des murs."""
    
    def test_cannot_place_out_of_bounds(self):
        """Impossible de placer un mur hors limites."""
        game = create_new_game()
        
        # Mur trop haut
        with pytest.raises(InvalidMoveError, match="limites"):
            place_wall(game, PLAYER_ONE, ('h', -1, 4, 2))
        
        # Mur trop bas
        with pytest.raises(InvalidMoveError, match="limites"):
            place_wall(game, PLAYER_ONE, ('h', 8, 4, 2))
    
    def test_cannot_place_duplicate_wall(self):
        """Impossible de placer deux fois le même mur."""
        game = create_new_game()
        wall = ('h', 1, 4, 2)
        
        game = place_wall(game, PLAYER_ONE, wall)
        
        with pytest.raises(InvalidMoveError, match="existe déjà"):
            place_wall(game, PLAYER_TWO, wall)
    
    def test_cannot_place_overlapping_walls(self):
        """Impossible de placer des murs qui se chevauchent."""
        game = create_new_game()
        wall1 = ('h', 2, 3, 2)  # Couvre colonnes 3 et 4
        game = place_wall(game, PLAYER_ONE, wall1)
        
        # Mur qui chevauche (couvre colonnes 4 et 5)
        wall2 = ('h', 2, 4, 2)
        
        with pytest.raises(InvalidMoveError, match="chevauche"):
            place_wall(game, PLAYER_TWO, wall2)
    
    def test_cannot_place_crossing_walls(self):
        """Impossible de placer des murs qui se croisent."""
        game = create_new_game()
        wall1 = ('h', 2, 3, 2)  # Horizontal
        game = place_wall(game, PLAYER_ONE, wall1)
        
        # Mur vertical qui croise
        wall2 = ('v', 2, 3, 2)
        
        with pytest.raises(InvalidMoveError, match="croise"):
            place_wall(game, PLAYER_TWO, wall2)
    
    def test_cannot_place_without_walls_left(self):
        """Impossible de placer un mur si on n'en a plus."""
        game = GameState(
            player_positions={PLAYER_ONE: (0, 4), PLAYER_TWO: (8, 4)},
            walls=set(),
            player_walls={PLAYER_ONE: 0, PLAYER_TWO: 10},  # Plus de murs pour J1
            current_player=PLAYER_ONE
        )
        
        with pytest.raises(InvalidMoveError, match="plus de murs"):
            place_wall(game, PLAYER_ONE, ('h', 1, 4, 2))
    
    def test_wrong_player_turn(self):
        """Impossible de placer un mur hors de son tour."""
        game = create_new_game()
        
        with pytest.raises(InvalidMoveError):
            place_wall(game, PLAYER_TWO, ('h', 6, 4, 2))


class TestWallBlocking:
    """Tests de la règle interdisant de bloquer complètement un joueur."""
    
    def test_cannot_block_player_completely(self):
        """Impossible de bloquer complètement le chemin d'un joueur."""
        # Créer une situation où J1 est presque coincé
        # J1 est en (8, 0), son but est la ligne 0
        game = GameState(
            player_positions={PLAYER_ONE: (8, 0), PLAYER_TWO: (0, 4)},
            walls={('v', 7, 1, 2)},  # Mur vertical à droite
            player_walls={PLAYER_ONE: 10, PLAYER_TWO: 9},
            current_player=PLAYER_TWO
        )
        
        # Tenter de bloquer la dernière sortie (au-dessus de J1)
        blocking_wall = ('h', 7, 0, 2)
        
        with pytest.raises(InvalidMoveError, match="bloque.*chemin"):
            place_wall(game, PLAYER_TWO, blocking_wall)
    
    def test_wall_must_leave_path_for_both_players(self):
        """Un mur doit laisser un chemin pour les deux joueurs."""
        game = GameState(
            player_positions={PLAYER_ONE: (7, 1), PLAYER_TWO: (1, 7)},
            walls=set(),
            player_walls={PLAYER_ONE: 10, PLAYER_TWO: 10},
            current_player=PLAYER_ONE
        )
        
        # Un mur qui ne bloque personne devrait passer
        valid_wall = ('h', 4, 4, 2)
        new_game = place_wall(game, PLAYER_ONE, valid_wall)
        
        assert valid_wall in new_game.walls


class TestDoubleClick:
    """Tests de la fonction interpret_double_click."""
    
    def test_horizontal_wall_from_adjacent_cells(self):
        """Double-clic horizontal crée un mur horizontal."""
        case1 = (2, 3)
        case2 = (2, 4)
        
        wall = interpret_double_click(case1, case2)
        
        assert wall == ('h', 2, 3, 2)
    
    def test_vertical_wall_from_adjacent_cells(self):
        """Double-clic vertical crée un mur vertical."""
        case1 = (3, 2)
        case2 = (4, 2)
        
        wall = interpret_double_click(case1, case2)
        
        assert wall == ('v', 3, 2, 2)
    
    def test_order_doesnt_matter(self):
        """L'ordre des clics ne change pas le résultat."""
        case1 = (2, 3)
        case2 = (2, 4)
        
        wall1 = interpret_double_click(case1, case2)
        wall2 = interpret_double_click(case2, case1)
        
        assert wall1 == wall2
    
    def test_non_adjacent_cells_raises_error(self):
        """Cases non adjacentes lèvent une erreur."""
        case1 = (2, 3)
        case2 = (2, 5)  # Pas adjacentes
        
        with pytest.raises(InvalidMoveError, match="adjacentes"):
            interpret_double_click(case1, case2)
    
    def test_diagonal_cells_raises_error(self):
        """Cases en diagonale lèvent une erreur."""
        case1 = (2, 3)
        case2 = (3, 4)  # En diagonale
        
        with pytest.raises(InvalidMoveError, match="adjacentes"):
            interpret_double_click(case1, case2)


class TestWallStrategies:
    """Tests de scénarios stratégiques avec des murs."""
    
    def test_multiple_walls_placed(self):
        """Placer plusieurs murs successivement."""
        game = create_new_game()
        
        # J1 place un mur
        game = place_wall(game, PLAYER_ONE, ('h', 1, 2, 2))
        assert game.player_walls[PLAYER_ONE] == 9
        
        # J2 place un mur
        game = place_wall(game, PLAYER_TWO, ('v', 6, 5, 2))
        assert game.player_walls[PLAYER_TWO] == 9
        
        # J1 place un autre mur
        game = place_wall(game, PLAYER_ONE, ('h', 3, 4, 2))
        assert game.player_walls[PLAYER_ONE] == 8
    
    def test_wall_affects_pathfinding(self):
        """Un mur change les chemins disponibles."""
        game = create_new_game()
        
        # Placer un mur qui pourrait affecter le chemin
        wall = ('h', 0, 4, 2)
        game = place_wall(game, PLAYER_ONE, wall)
        
        # Le mur doit être présent
        assert wall in game.walls


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

