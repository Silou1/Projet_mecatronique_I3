# -*- coding: utf-8 -*-
"""
Fichier principal du moteur de jeu Quoridor.
Contient les structures de données et la logique du jeu.
"""

from dataclasses import dataclass, replace
from typing import Set, Dict, Tuple, Literal, List, Callable, Any
from collections import deque

# --- Constantes et Types ---

Coord = Tuple[int, int]
Wall = Tuple[Literal['h', 'v'], int, int, int]
Move = Tuple[str, Any]  # e.g., ('deplacement', (1, 4)) or ('mur', ('h', 2, 3, 2))
PLAYER_ONE = 'j1'
PLAYER_TWO = 'j2'
BOARD_SIZE = 9
MAX_WALLS_PER_PLAYER = 10

# --- Exceptions Personnalisées ---

class InvalidMoveError(Exception):
    """Levée quand un coup (déplacement ou mur) ne respecte pas les règles du jeu."""
    pass

# --- Structures de Données Principales ---

@dataclass(frozen=True)
class GameState:
    """Représente l'état complet d'une partie de Quoridor à un instant T."""
    player_positions: Dict[str, Coord]
    walls: Set[Wall]
    player_walls: Dict[str, int]
    current_player: str

    def is_game_over(self) -> Tuple[bool, str | None]:
        """Vérifie si la partie est terminée."""
        pos_j1 = self.player_positions[PLAYER_ONE]
        pos_j2 = self.player_positions[PLAYER_TWO]
        if pos_j1[0] == BOARD_SIZE - 1:
            return True, PLAYER_ONE
        if pos_j2[0] == 0:
            return True, PLAYER_TWO
        return False, None

# --- Fonctions d'Initialisation ---

def create_new_game() -> GameState:
    """Crée et retourne un nouvel état de jeu pour le début d'une partie."""
    return GameState(
        player_positions={
            PLAYER_ONE: (0, BOARD_SIZE // 2),
            PLAYER_TWO: (BOARD_SIZE - 1, BOARD_SIZE // 2)
        },
        walls=set(),
        player_walls={PLAYER_ONE: MAX_WALLS_PER_PLAYER, PLAYER_TWO: MAX_WALLS_PER_PLAYER},
        current_player=PLAYER_ONE
    )

# --- Logique de Déplacement des Pions (Phase 2) ---

def _is_wall_between(state: GameState, start: Coord, end: Coord) -> bool:
    """Vérifie si un mur bloque le passage entre deux cases adjacentes."""
    r_start, c_start = start
    r_end, c_end = end
    
    # Mouvement vertical
    if c_start == c_end:
        r_wall = min(r_start, r_end)
        if ('h', r_wall, c_start, 2) in state.walls:
            return True
        if c_start > 0 and ('h', r_wall, c_start - 1, 2) in state.walls:
            return True
    
    # Mouvement horizontal
    elif r_start == r_end:
        c_wall = min(c_start, c_end)
        if ('v', r_start, c_wall, 2) in state.walls:
            return True
        if r_start > 0 and ('v', r_start - 1, c_wall, 2) in state.walls:
            return True
            
    return False

def get_possible_pawn_moves(state: GameState, player: str) -> List[Coord]:
    """Retourne la liste des coordonnées où un joueur peut se déplacer."""
    moves = []
    current_pos = state.player_positions[player]
    opponent = PLAYER_TWO if player == PLAYER_ONE else PLAYER_ONE
    opponent_pos = state.player_positions[opponent]
    r, c = current_pos
    potential_moves = [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]
    
    for move in potential_moves:
        if not (0 <= move[0] < BOARD_SIZE and 0 <= move[1] < BOARD_SIZE):
            continue
        if _is_wall_between(state, current_pos, move):
            continue
            
        # Si la case est occupée par l'adversaire -> Logique de saut
        if move == opponent_pos:
            jump_r = opponent_pos[0] + (opponent_pos[0] - r)
            jump_c = opponent_pos[1] + (opponent_pos[1] - c)
            jump_pos = (jump_r, jump_c)
            
            # Saut simple si possible
            if (0 <= jump_r < BOARD_SIZE and 0 <= jump_c < BOARD_SIZE):
                if not _is_wall_between(state, opponent_pos, jump_pos):
                    moves.append(jump_pos)
                    continue
            
            # Sinon, sauts diagonaux
            if c == opponent_pos[1]:  # Face-à-face vertical
                for dc in [-1, 1]:
                    diag_move = (opponent_pos[0], opponent_pos[1] + dc)
                    if (0 <= diag_move[1] < BOARD_SIZE) and not _is_wall_between(state, opponent_pos, diag_move):
                        moves.append(diag_move)
            elif r == opponent_pos[0]:  # Face-à-face horizontal
                for dr in [-1, 1]:
                    diag_move = (opponent_pos[0] + dr, opponent_pos[1])
                    if (0 <= diag_move[0] < BOARD_SIZE) and not _is_wall_between(state, opponent_pos, diag_move):
                        moves.append(diag_move)
        else:
            moves.append(move)
            
    return moves

def move_pawn(state: GameState, player: str, target_coord: Coord) -> GameState:
    """Tente de déplacer un pion et retourne le nouvel état de jeu."""
    if player != state.current_player:
        raise InvalidMoveError(f"Ce n'est pas le tour du joueur {player}.")
    if target_coord not in get_possible_pawn_moves(state, player):
        raise InvalidMoveError(f"Le déplacement vers {target_coord} est invalide.")
    
    new_positions = state.player_positions.copy()
    new_positions[player] = target_coord
    next_player = PLAYER_TWO if player == PLAYER_ONE else PLAYER_ONE
    return replace(state, player_positions=new_positions, current_player=next_player)

# --- Logique de la Pose des Murs (Phase 3) ---

def _path_exists(state: GameState, start_pos: Coord, is_goal: Callable[[Coord], bool]) -> bool:
    """Vérifie s'il existe un chemin de start_pos à une case but en utilisant BFS."""
    q = deque([start_pos])
    visited = {start_pos}
    
    while q:
        current_pos = q.popleft()
        if is_goal(current_pos):
            return True
        
        r, c = current_pos
        potential_moves = [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]
        
        for move in potential_moves:
            if (move not in visited and 
                0 <= move[0] < BOARD_SIZE and 
                0 <= move[1] < BOARD_SIZE and 
                not _is_wall_between(state, current_pos, move)):
                visited.add(move)
                q.append(move)
                
    return False

def _validate_wall_placement(state: GameState, wall: Wall) -> None:
    """Lève une InvalidMoveError si le placement du mur est invalide."""
    orientation, r, c, length = wall
    
    # 1. Validation des limites
    if not (0 <= r < BOARD_SIZE - 1 and 0 <= c < BOARD_SIZE - 1):
        raise InvalidMoveError("Le mur est en dehors des limites de placement.")

    # 2. Validation de collision
    if wall in state.walls:
        raise InvalidMoveError("Un mur identique existe déjà.")
    
    # 3. Validation de chevauchement
    if orientation == 'h':
        overlapping = [('h', r, c - 1, 2), ('h', r, c + 1, 2)]
        for ow in overlapping:
            if ow in state.walls:
                raise InvalidMoveError("Le mur chevauche un mur existant.")
    else:
        overlapping = [('v', r - 1, c, 2), ('v', r + 1, c, 2)]
        for ow in overlapping:
            if ow in state.walls:
                raise InvalidMoveError("Le mur chevauche un mur existant.")
    
    # 4. Validation de croisement
    intersecting = ('v', r, c, 2) if orientation == 'h' else ('h', r, c, 2)
    if intersecting in state.walls:
        raise InvalidMoveError("Le mur croise un mur existant.")

def place_wall(state: GameState, player: str, wall: Wall) -> GameState:
    """Tente de placer un mur et retourne le nouvel état de jeu."""
    if player != state.current_player:
        raise InvalidMoveError(f"Ce n'est pas le tour du joueur {player}.")
    
    if state.player_walls[player] <= 0:
        raise InvalidMoveError("Le joueur n'a plus de murs.")
        
    _validate_wall_placement(state, wall)
    
    # Crée un état temporaire pour tester le blocage
    temp_walls = state.walls.copy()
    temp_walls.add(wall)
    temp_state = replace(state, walls=temp_walls)
    
    # Vérifie si un chemin existe toujours pour CHAQUE joueur
    goal_j1 = lambda pos: pos[0] == BOARD_SIZE - 1
    goal_j2 = lambda pos: pos[0] == 0
    
    if not _path_exists(temp_state, temp_state.player_positions[PLAYER_ONE], goal_j1):
        raise InvalidMoveError("Le mur bloque le chemin du joueur 1.")
        
    if not _path_exists(temp_state, temp_state.player_positions[PLAYER_TWO], goal_j2):
        raise InvalidMoveError("Le mur bloque le chemin du joueur 2.")
        
    # Si tout est valide, crée le nouvel état de jeu final
    new_player_walls = state.player_walls.copy()
    new_player_walls[player] -= 1
    next_player = PLAYER_TWO if player == PLAYER_ONE else PLAYER_ONE
    
    return replace(
        state,
        walls=temp_walls,
        player_walls=new_player_walls,
        current_player=next_player
    )

def interpret_double_click(case1: Coord, case2: Coord) -> Wall:
    """
    Convertit deux clics utilisateur en une spécification de mur.
    
    Args:
        case1, case2: Les deux cases cliquées par l'utilisateur (doivent être adjacentes)
    
    Returns:
        Un tuple Wall (orientation, ligne, colonne, longueur=2)
    
    Raises:
        InvalidMoveError: Si les cases ne sont pas adjacentes
    """
    r1, c1 = case1
    r2, c2 = case2
    
    # Cas horizontal (même ligne)
    if r1 == r2 and abs(c1 - c2) == 1:
        col_min = min(c1, c2)
        return ('h', r1, col_min, 2)
    
    # Cas vertical (même colonne)
    if c1 == c2 and abs(r1 - r2) == 1:
        ligne_min = min(r1, r2)
        return ('v', ligne_min, c1, 2)
    
    # Sinon, les cases ne sont pas adjacentes
    raise InvalidMoveError("Les deux cases cliquées doivent être adjacentes.")

# --- Orchestration du Jeu (Phase 4) ---

class QuoridorGame:
    """
    Classe principale pour gérer une partie de Quoridor.
    Elle encapsule l'état du jeu et fournit une API simple pour jouer des coups.
    """
    def __init__(self):
        """Initialise une nouvelle partie."""
        self._history: List[GameState] = []
        self._current_state: GameState = create_new_game()

    def get_current_state(self) -> GameState:
        """
        Retourne l'état actuel du jeu.
        
        Note: GameState étant immuable (frozen=True), il n'y a pas de risque
        de modification externe.
        """
        return self._current_state
    
    def get_current_player(self) -> str:
        """Retourne le joueur dont c'est le tour."""
        return self._current_state.current_player
    
    def get_possible_moves(self, player: str | None = None) -> List[Move]:
        """
        Retourne tous les coups possibles pour un joueur.
        
        Args:
            player: Le joueur (si None, utilise le joueur courant)
        
        Returns:
            Liste de coups au format Move
        """
        if player is None:
            player = self._current_state.current_player
            
        moves: List[Move] = []
        
        # Ajoute tous les déplacements possibles
        pawn_moves = get_possible_pawn_moves(self._current_state, player)
        for coord in pawn_moves:
            moves.append(('deplacement', coord))
        
        # Ajoute tous les murs possibles (si le joueur a des murs)
        if self._current_state.player_walls[player] > 0:
            # Pour simplifier, on ne génère pas tous les murs possibles ici
            # (ce serait très coûteux). Cette méthode est surtout utile pour l'IA.
            # L'IA pourra générer ses propres murs en appelant place_wall avec validation.
            pass
        
        return moves

    def play_move(self, move: Move) -> None:
        """
        Joue un coup (déplacement ou mur) et met à jour l'état du jeu.
        
        Args:
            move: Un tuple décrivant le coup.
                  Ex: ('deplacement', (1, 4))
                  Ex: ('mur', ('h', 2, 3, 2))
        
        Raises:
            InvalidMoveError: Si le coup est invalide.
            ValueError: Si le type de coup est inconnu.
        """
        move_type, move_data = move
        player = self._current_state.current_player
        
        # Sauvegarde l'état actuel avant de le modifier
        self._history.append(self._current_state)
        
        try:
            if move_type == 'deplacement':
                self._current_state = move_pawn(self._current_state, player, move_data)
            elif move_type == 'mur':
                self._current_state = place_wall(self._current_state, player, move_data)
            else:
                raise ValueError(f"Type de coup inconnu: {move_type}")
        except (InvalidMoveError, ValueError) as e:
            # Si le coup est invalide, restaure l'état précédent
            self._history.pop()
            raise

    def undo_move(self) -> bool:
        """
        Annule le dernier coup et retourne à l'état précédent.
        
        Returns:
            True si l'annulation a réussi, False s'il n'y a pas d'historique
        """
        if not self._history:
            return False  # Pas d'historique, impossible d'annuler
        
        self._current_state = self._history.pop()
        return True
    
    def is_game_over(self) -> Tuple[bool, str | None]:
        """Vérifie si la partie est terminée."""
        return self._current_state.is_game_over()
    
    def get_winner(self) -> str | None:
        """
        Retourne le gagnant de la partie.
        
        Returns:
            'j1', 'j2' ou None si la partie n'est pas terminée
        """
        is_over, winner = self.is_game_over()
        return winner if is_over else None


# --- Point d'entrée pour un test rapide ---
if __name__ == '__main__':
    print("=" * 60)
    print("--- Tests Rapides du Moteur Quoridor ---")
    print("=" * 60)
    
    # Tests de la Phase 2
    print("\n--- Phase 2 : Déplacements ---")
    game = create_new_game()
    moves_j1 = get_possible_pawn_moves(game, PLAYER_ONE)
    assert set(moves_j1) == {(1, 4), (0, 3), (0, 5)}
    print("✓ Mouvements de base")
    
    game = move_pawn(game, PLAYER_ONE, (1, 4))
    assert game.player_positions[PLAYER_ONE] == (1, 4)
    assert game.current_player == PLAYER_TWO
    print("✓ Déplacement et changement de joueur")
    
    # Tests de la Phase 3
    print("\n--- Phase 3 : Murs ---")
    game = create_new_game()
    wall = ('h', 1, 4, 2)
    game = place_wall(game, PLAYER_ONE, wall)
    assert wall in game.walls
    assert game.player_walls[PLAYER_ONE] == 9
    print("✓ Placement de mur")
    
    wall_test = interpret_double_click((2, 3), (2, 4))
    assert wall_test == ('h', 2, 3, 2)
    print("✓ Interprétation double-clic")
    
    # Tests de la Phase 4
    print("\n--- Phase 4 : Orchestration ---")
    partie = QuoridorGame()
    
    # Test 1: Jouer des coups
    assert partie.get_current_player() == PLAYER_ONE
    partie.play_move(('deplacement', (1, 4)))
    assert partie.get_current_player() == PLAYER_TWO
    print("✓ Jouer un déplacement")
    
    partie.play_move(('mur', ('h', 6, 4, 2)))
    assert partie.get_current_player() == PLAYER_ONE
    assert ('h', 6, 4, 2) in partie.get_current_state().walls
    print("✓ Jouer un mur")
    
    # Test 2: Annuler un coup
    partie.undo_move()
    assert partie.get_current_player() == PLAYER_TWO
    assert ('h', 6, 4, 2) not in partie.get_current_state().walls
    print("✓ Annulation de coup")
    
    # Test 3: Coup invalide
    try:
        partie.play_move(('deplacement', (1, 4)))  # Case occupée
        assert False, "Le coup invalide aurait dû être rejeté"
    except InvalidMoveError:
        assert partie.get_current_player() == PLAYER_TWO
        print("✓ Rejet de coup invalide")
    
    # Test 4: Vérifier le gagnant
    victory_state = GameState(
        player_positions={PLAYER_ONE: (8, 4), PLAYER_TWO: (0, 4)},
        walls=set(),
        player_walls={PLAYER_ONE: 10, PLAYER_TWO: 10},
        current_player=PLAYER_ONE
    )
    partie._current_state = victory_state
    assert partie.get_winner() == PLAYER_ONE
    print("✓ Détection du gagnant")
    
    # Test 5: Obtenir les coups possibles
    partie2 = QuoridorGame()
    possible = partie2.get_possible_moves()
    assert len(possible) == 3  # 3 déplacements possibles au début
    print("✓ Génération des coups possibles")
    
    print("\n" + "=" * 60)
    print("--- Tous les tests sont passés ! ---")
    print("--- Phases 1-4 complètes et fonctionnelles ---")
    print("=" * 60)
