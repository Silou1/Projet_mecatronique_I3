# -*- coding: utf-8 -*-
"""
Tests unitaires pour les structures de données et fonctions de base du moteur Quoridor.
"""

import pytest
from quoridor_engine.core import (
    GameState,
    create_new_game,
    InvalidMoveError,
    NackCode,
    PLAYER_ONE,
    PLAYER_TWO,
    BOARD_SIZE,
    MAX_WALLS_PER_PLAYER,
    move_pawn,
    place_wall,
    interpret_double_click,
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
        
        # Joueur 1 en bas au centre (ligne 5)
        pos_j1 = game.player_positions[PLAYER_ONE]
        expected_j1 = (BOARD_SIZE - 1, BOARD_SIZE // 2)
        assert pos_j1 == expected_j1, f"J1 devrait être en {expected_j1}, mais est en {pos_j1}"
        
        # Joueur 2 en haut au centre (ligne 0)
        pos_j2 = game.player_positions[PLAYER_TWO]
        expected_j2 = (0, BOARD_SIZE // 2)
        assert pos_j2 == expected_j2, f"J2 devrait être en {expected_j2}, mais est en {pos_j2}"
    
    def test_initial_walls(self):
        """Test du nombre initial de murs."""
        game = create_new_game()
        
        assert game.player_walls[PLAYER_ONE] == MAX_WALLS_PER_PLAYER, f"J1 devrait avoir {MAX_WALLS_PER_PLAYER} murs"
        assert game.player_walls[PLAYER_TWO] == MAX_WALLS_PER_PLAYER, f"J2 devrait avoir {MAX_WALLS_PER_PLAYER} murs"


class TestGameOver:
    """Tests de détection de fin de partie."""
    
    def test_game_not_over_at_start(self):
        """La partie n'est pas terminée au début."""
        game = create_new_game()
        is_over, winner = game.is_game_over()
        
        assert is_over is False
        assert winner is None
    
    def test_player_one_wins(self):
        """Joueur 1 gagne en atteignant la ligne 0."""
        game = GameState(
            player_positions={PLAYER_ONE: (0, 3), PLAYER_TWO: (5, 3)},
            walls=frozenset(),
            player_walls={PLAYER_ONE: 6, PLAYER_TWO: 6},
            current_player=PLAYER_ONE
        )
        
        is_over, winner = game.is_game_over()
        
        assert is_over is True, "La partie devrait être terminée"
        assert winner == PLAYER_ONE, f"Le gagnant devrait être {PLAYER_ONE}, pas {winner}"
    
    def test_player_two_wins(self):
        """Joueur 2 gagne en atteignant la ligne 5."""
        game = GameState(
            player_positions={PLAYER_ONE: (2, 3), PLAYER_TWO: (5, 3)},  # J1 pas à la fin
            walls=frozenset(),
            player_walls={PLAYER_ONE: 6, PLAYER_TWO: 6},
            current_player=PLAYER_TWO
        )
        
        is_over, winner = game.is_game_over()
        
        assert is_over is True, "La partie devrait être terminée"
        assert winner == PLAYER_TWO, f"Le gagnant devrait être {PLAYER_TWO}, pas {winner}"
    
    def test_game_continues_near_end(self):
        """La partie continue même si un joueur est proche de la fin."""
        game = GameState(
            player_positions={PLAYER_ONE: (1, 3), PLAYER_TWO: (4, 3)},
            walls=frozenset(),
            player_walls={PLAYER_ONE: 3, PLAYER_TWO: 3},
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
    
    def test_walls_is_immutable(self):
        """Les murs doivent être dans un frozenset immuable."""
        game = create_new_game()
        
        # Vérifier que walls est un frozenset (immuable)
        assert isinstance(game.walls, frozenset)
        
        # Vérifier qu'on ne peut pas modifier le frozenset
        # (frozenset n'a pas de méthode add, contrairement à set)
        assert not hasattr(game.walls, 'add') or not callable(getattr(game.walls, 'add', None))
        
        # Vérifier que l'état est hashable grâce à frozenset
        assert hash(game) is not None


class TestConstants:
    """Tests des constantes du jeu."""
    
    def test_board_size(self):
        """Le plateau doit faire 6x6."""
        assert BOARD_SIZE == 6
    
    def test_max_walls(self):
        """Chaque joueur doit avoir 6 murs."""
        assert MAX_WALLS_PER_PLAYER == 6
    
    def test_player_constants(self):
        """Vérification des identifiants de joueurs."""
        assert PLAYER_ONE == 'j1'
        assert PLAYER_TWO == 'j2'


class TestNackCode:
    """Tests de l'enum NackCode aligné sur le catalogue NACK du protocole UART §4.4."""

    def test_nack_code_values_aligned_with_uart_protocol(self):
        """NackCode.X.value doit correspondre exactement aux codes du spec UART §4.4."""
        assert NackCode.ILLEGAL.value == "ILLEGAL"
        assert NackCode.OUT_OF_BOUNDS.value == "OUT_OF_BOUNDS"
        assert NackCode.WRONG_TURN.value == "WRONG_TURN"
        assert NackCode.WALL_BLOCKED.value == "WALL_BLOCKED"
        assert NackCode.NO_WALLS_LEFT.value == "NO_WALLS_LEFT"
        assert NackCode.INVALID_FORMAT.value == "INVALID_FORMAT"

    def test_nack_code_is_str_enum(self):
        """NackCode hérite de str pour permettre `nack.value` direct dans les trames."""
        assert isinstance(NackCode.ILLEGAL, str)
        assert isinstance(NackCode.ILLEGAL.value, str)


class TestInvalidMoveError:
    """Tests de la signature InvalidMoveError (message, code: NackCode)."""

    def test_invalid_move_error_requires_code(self):
        """InvalidMoveError doit imposer un argument code obligatoire."""
        # match="code" garantit qu'on capture bien l'absence de l'argument `code`,
        # pas un TypeError incident provenant d'une autre cause.
        with pytest.raises(TypeError, match="code"):
            InvalidMoveError("message sans code")

    def test_invalid_move_error_exposes_code_attribute(self):
        """L'attribut .code est accessible après levée."""
        err = InvalidMoveError("test", NackCode.ILLEGAL)
        assert err.code == NackCode.ILLEGAL
        assert err.code.value == "ILLEGAL"
        assert str(err) == "test"


class TestInvalidMoveErrorCodes:
    """Vérifie que chaque site de InvalidMoveError porte le bon NackCode.

    Couvre les 6 codes distincts levés par core.py :
    WRONG_TURN, ILLEGAL, OUT_OF_BOUNDS, WALL_BLOCKED, NO_WALLS_LEFT, INVALID_FORMAT.
    """

    def test_wrong_turn_on_pawn_move(self):
        """move_pawn lève WRONG_TURN si on agit pour le mauvais joueur."""
        state = create_new_game()  # current_player = 'j1'
        with pytest.raises(InvalidMoveError) as exc:
            move_pawn(state, "j2", (1, 3))  # j2 essaie de jouer alors que c'est j1
        assert exc.value.code == NackCode.WRONG_TURN

    def test_illegal_pawn_move_target(self):
        """move_pawn lève ILLEGAL pour une cible non-adjacente."""
        state = create_new_game()  # j1 en (5, 3), peut aller (4, 3)
        with pytest.raises(InvalidMoveError) as exc:
            move_pawn(state, "j1", (3, 3))  # cible non-adjacente
        assert exc.value.code == NackCode.ILLEGAL

    def test_wall_out_of_bounds(self):
        """place_wall lève OUT_OF_BOUNDS si le mur sort du plateau."""
        state = create_new_game()
        with pytest.raises(InvalidMoveError) as exc:
            place_wall(state, "j1", ("h", 10, 10, 2))
        assert exc.value.code == NackCode.OUT_OF_BOUNDS

    def test_wall_already_exists_blocked(self):
        """place_wall lève WALL_BLOCKED si un mur identique existe."""
        state1 = create_new_game()
        state2 = place_wall(state1, "j1", ("h", 2, 2, 2))
        # state2 a maintenant le mur ; current_player passe à j2
        with pytest.raises(InvalidMoveError) as exc:
            place_wall(state2, "j2", ("h", 2, 2, 2))
        assert exc.value.code == NackCode.WALL_BLOCKED

    def test_no_walls_left(self):
        """place_wall lève NO_WALLS_LEFT quand le joueur n'a plus de murs."""
        # GameState direct, current_player=j1, j1 a 0 murs restants
        state = GameState(
            player_positions={"j1": (5, 3), "j2": (0, 3)},
            walls=frozenset(),
            player_walls={"j1": 0, "j2": 6},
            current_player="j1",
        )
        with pytest.raises(InvalidMoveError) as exc:
            place_wall(state, "j1", ("h", 0, 0, 2))
        assert exc.value.code == NackCode.NO_WALLS_LEFT

    def test_invalid_format_double_click_non_adjacent(self):
        """interpret_double_click lève INVALID_FORMAT pour 2 cases non-adjacentes."""
        with pytest.raises(InvalidMoveError) as exc:
            interpret_double_click((0, 0), (5, 5))
        assert exc.value.code == NackCode.INVALID_FORMAT


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

