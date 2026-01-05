# -*- coding: utf-8 -*-
"""
=============================================================================
MOTEUR DE JEU QUORIDOR - Module Principal (core.py)
=============================================================================

Ce fichier contient toute la logique du jeu Quoridor :
- Les structures de données pour représenter l'état du jeu
- Les règles de déplacement des pions
- Les règles de placement des murs
- La gestion d'une partie complète

QUORIDOR - RÈGLES DU JEU :
--------------------------
Le Quoridor est un jeu de stratégie pour 2 joueurs sur un plateau 9x9.
Chaque joueur possède un pion et 10 murs.

OBJECTIF :
- Joueur 1 (j1) : Partir de la ligne 1 et atteindre la ligne 9
- Joueur 2 (j2) : Partir de la ligne 9 et atteindre la ligne 1

À CHAQUE TOUR, un joueur peut :
- Soit déplacer son pion d'une case (haut, bas, gauche, droite)
- Soit placer un mur pour bloquer le chemin de l'adversaire

CONTRAINTE IMPORTANTE :
Un mur ne peut jamais bloquer complètement le chemin d'un joueur vers son objectif.
"""

from dataclasses import dataclass, replace
from typing import Set, Dict, Tuple, Literal, List, Callable, Any
from collections import deque

# =============================================================================
# CONSTANTES ET TYPES DE BASE
# =============================================================================

# Type pour représenter une coordonnée sur le plateau (ligne, colonne)
# Exemple : (0, 4) = ligne 0 (première ligne), colonne 4 (milieu)
# Le plateau va de (0,0) en haut à gauche à (8,8) en bas à droite
Coord = Tuple[int, int]

# Type pour représenter un mur
# Format : (orientation, ligne, colonne, longueur)
# - orientation : 'h' pour horizontal, 'v' pour vertical
# - ligne, colonne : position du coin supérieur gauche du mur
# - longueur : toujours 2 (un mur couvre 2 cases)
# Exemple : ('h', 3, 4, 2) = mur horizontal sur la ligne 3, colonne 4
Wall = Tuple[Literal['h', 'v'], int, int, int]

# Type pour représenter un coup joué
# Format : (type_de_coup, données_du_coup)
# - ('deplacement', (ligne, colonne)) : déplacer le pion vers cette case
# - ('mur', ('h', ligne, colonne, 2)) : placer un mur
Move = Tuple[str, Any]

# Identifiants des joueurs
PLAYER_ONE = 'j1'  # Joueur 1 - commence en haut, doit aller en bas
PLAYER_TWO = 'j2'  # Joueur 2 - commence en bas, doit aller en haut

# Taille du plateau (9x9 cases)
BOARD_SIZE = 9

# Nombre de murs disponibles par joueur au début de la partie
MAX_WALLS_PER_PLAYER = 10

# =============================================================================
# EXCEPTIONS PERSONNALISÉES
# =============================================================================

class InvalidMoveError(Exception):
    """
    Exception levée quand un coup ne respecte pas les règles du jeu.
    
    Exemples de cas où cette exception est levée :
    - Déplacement vers une case inaccessible (hors plateau, bloquée par un mur)
    - Placement d'un mur qui chevauche un mur existant
    - Placement d'un mur qui bloquerait complètement un joueur
    - Tentative de jouer alors que ce n'est pas son tour
    """
    pass


# =============================================================================
# STRUCTURE DE DONNÉES PRINCIPALE : GameState
# =============================================================================

@dataclass(frozen=True)
class GameState:
    """
    Représente l'état complet d'une partie de Quoridor à un instant T.
    
    Cette classe utilise le décorateur @dataclass avec frozen=True, ce qui signifie :
    - Les attributs sont automatiquement générés à partir des annotations de type
    - L'objet est IMMUABLE (on ne peut pas modifier ses attributs après création)
    - Cela permet d'utiliser le pattern "immutable state" pour l'historique des coups
    
    ATTRIBUTS :
    -----------
    player_positions : Dict[str, Coord]
        Position de chaque joueur sur le plateau.
        Exemple : {'j1': (0, 4), 'j2': (8, 4)}
        
    walls : Set[Wall]
        Ensemble des murs posés sur le plateau.
        Utilise un Set pour éviter les doublons et permettre une recherche rapide O(1).
        
    player_walls : Dict[str, int]
        Nombre de murs restants pour chaque joueur.
        Exemple : {'j1': 8, 'j2': 10} = j1 a utilisé 2 murs, j2 n'en a utilisé aucun
        
    current_player : str
        Le joueur dont c'est le tour ('j1' ou 'j2').
    """
    player_positions: Dict[str, Coord]
    walls: Set[Wall]
    player_walls: Dict[str, int]
    current_player: str

    def is_game_over(self) -> Tuple[bool, str | None]:
        """
        Vérifie si la partie est terminée (un joueur a atteint son objectif).
        
        CONDITIONS DE VICTOIRE :
        - Joueur 1 gagne s'il atteint la ligne 8 (index 8, dernière ligne du plateau)
        - Joueur 2 gagne s'il atteint la ligne 0 (première ligne du plateau)
        
        Returns:
            Tuple (partie_terminée, gagnant)
            - (True, 'j1') si le joueur 1 a gagné
            - (True, 'j2') si le joueur 2 a gagné
            - (False, None) si la partie continue
        """
        pos_j1 = self.player_positions[PLAYER_ONE]
        pos_j2 = self.player_positions[PLAYER_TWO]
        
        # Joueur 1 gagne en atteignant la dernière ligne (ligne 8)
        if pos_j1[0] == BOARD_SIZE - 1:
            return True, PLAYER_ONE
        
        # Joueur 2 gagne en atteignant la première ligne (ligne 0)
        if pos_j2[0] == 0:
            return True, PLAYER_TWO
        
        # La partie continue
        return False, None


# =============================================================================
# INITIALISATION D'UNE NOUVELLE PARTIE
# =============================================================================

def create_new_game() -> GameState:
    """
    Crée et retourne un nouvel état de jeu pour le début d'une partie.
    
    CONFIGURATION INITIALE :
    - Joueur 1 : position (0, 4) = centre de la première ligne (haut)
    - Joueur 2 : position (8, 4) = centre de la dernière ligne (bas)
    - Aucun mur posé
    - Chaque joueur a 10 murs disponibles
    - C'est au tour du joueur 1
    
    Returns:
        Un nouvel objet GameState configuré pour le début de partie
    """
    return GameState(
        player_positions={
            # BOARD_SIZE // 2 = 4 = colonne centrale (e)
            PLAYER_ONE: (0, BOARD_SIZE // 2),        # Position initiale j1 : (0, 4)
            PLAYER_TWO: (BOARD_SIZE - 1, BOARD_SIZE // 2)  # Position initiale j2 : (8, 4)
        },
        walls=set(),  # Aucun mur au début
        player_walls={
            PLAYER_ONE: MAX_WALLS_PER_PLAYER,  # 10 murs pour j1
            PLAYER_TWO: MAX_WALLS_PER_PLAYER   # 10 murs pour j2
        },
        current_player=PLAYER_ONE  # Le joueur 1 commence
    )

# =============================================================================
# LOGIQUE DE DÉPLACEMENT DES PIONS
# =============================================================================
# 
# Cette section gère les règles de déplacement :
# - Un pion peut se déplacer d'une case dans les 4 directions (haut, bas, gauche, droite)
# - Un pion ne peut pas traverser un mur
# - Un pion ne peut pas aller sur la case de l'adversaire, mais peut le SAUTER
# 
# RÈGLE DE SAUT :
# Si l'adversaire est sur une case adjacente et qu'il n'y a pas de mur derrière lui,
# on peut sauter par-dessus pour atterrir de l'autre côté.
# Si un mur bloque le saut direct, on peut faire un saut diagonal.
# =============================================================================

def _is_wall_between(state: GameState, start: Coord, end: Coord) -> bool:
    """
    Vérifie si un mur bloque le passage entre deux cases ADJACENTES.
    
    Cette fonction est fondamentale pour tout le jeu : elle détermine si un
    déplacement d'une case à une autre est possible.
    
    LOGIQUE :
    ---------
    Un mur horizontal ('h') bloque les mouvements VERTICAUX (haut/bas).
    Un mur vertical ('v') bloque les mouvements HORIZONTAUX (gauche/droite).
    
    Comme un mur couvre 2 cases, il faut vérifier 2 positions possibles :
    - Le mur dont le coin est exactement à la frontière
    - Le mur décalé d'une case (qui couvre aussi cette frontière)
    
    EXEMPLE pour un mouvement vertical de (2,4) vers (3,4) :
    On vérifie si un mur horizontal existe en ('h', 2, 4, 2) ou ('h', 2, 3, 2)
    
    Args:
        state: L'état actuel du jeu
        start: Case de départ (ligne, colonne)
        end: Case d'arrivée (ligne, colonne)
    
    Returns:
        True si un mur bloque le passage, False sinon
    """
    r_start, c_start = start
    r_end, c_end = end
    
    # Mouvement VERTICAL (même colonne, lignes différentes)
    # Un mur HORIZONTAL bloque ce type de mouvement
    if c_start == c_end:
        # La ligne où serait le mur = la plus petite des deux lignes
        r_wall = min(r_start, r_end)
        
        # Vérifier le mur directement à cette position
        if ('h', r_wall, c_start, 2) in state.walls:
            return True
        
        # Vérifier le mur décalé d'une colonne à gauche (qui couvre aussi cette frontière)
        if c_start > 0 and ('h', r_wall, c_start - 1, 2) in state.walls:
            return True
    
    # Mouvement HORIZONTAL (même ligne, colonnes différentes)
    # Un mur VERTICAL bloque ce type de mouvement
    elif r_start == r_end:
        # La colonne où serait le mur = la plus petite des deux colonnes
        c_wall = min(c_start, c_end)
        
        # Vérifier le mur directement à cette position
        if ('v', r_start, c_wall, 2) in state.walls:
            return True
        
        # Vérifier le mur décalé d'une ligne vers le haut (qui couvre aussi cette frontière)
        if r_start > 0 and ('v', r_start - 1, c_wall, 2) in state.walls:
            return True
            
    return False


def get_possible_pawn_moves(state: GameState, player: str) -> List[Coord]:
    """
    Retourne la liste de toutes les cases où un joueur peut déplacer son pion.
    
    Cette fonction implémente les règles de déplacement du Quoridor :
    
    1. DÉPLACEMENT SIMPLE : Une case dans les 4 directions cardinales
       (si pas bloqué par un mur ou le bord du plateau)
    
    2. SAUT PAR-DESSUS L'ADVERSAIRE : Si l'adversaire est adjacent et qu'il n'y a
       pas de mur derrière lui, on peut sauter par-dessus.
    
    3. SAUT DIAGONAL : Si le saut direct est impossible (mur ou bord), on peut
       se déplacer en diagonale (à gauche ou droite de l'adversaire).
    
    EXEMPLE DE SAUT :
    -----------------
        . . . . .          . . . . .
        . . 1 . .    →     . . . . .
        . . 2 . .          . . 2 . .
        . . X . .          . . 1 . .  (1 saute par-dessus 2)
    
    Args:
        state: L'état actuel du jeu
        player: Le joueur qui veut se déplacer ('j1' ou 'j2')
    
    Returns:
        Liste des coordonnées accessibles [(ligne, colonne), ...]
    """
    moves = []
    current_pos = state.player_positions[player]
    
    # Identifier l'adversaire
    opponent = PLAYER_TWO if player == PLAYER_ONE else PLAYER_ONE
    opponent_pos = state.player_positions[opponent]
    
    r, c = current_pos
    
    # Les 4 cases adjacentes possibles : haut, bas, gauche, droite
    potential_moves = [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]
    
    for move in potential_moves:
        # Vérification 1 : La case est-elle dans les limites du plateau ?
        if not (0 <= move[0] < BOARD_SIZE and 0 <= move[1] < BOARD_SIZE):
            continue
        
        # Vérification 2 : Y a-t-il un mur qui bloque ?
        if _is_wall_between(state, current_pos, move):
            continue
            
        # Vérification 3 : La case est-elle occupée par l'adversaire ?
        if move == opponent_pos:
            # ═══════════════════════════════════════════════════════════════
            # LOGIQUE DE SAUT PAR-DESSUS L'ADVERSAIRE
            # ═══════════════════════════════════════════════════════════════
            
            # Calculer la position de saut (continuer dans la même direction)
            # Si on va de (2,4) vers l'adversaire en (3,4), le saut serait en (4,4)
            jump_r = opponent_pos[0] + (opponent_pos[0] - r)  # Même décalage en ligne
            jump_c = opponent_pos[1] + (opponent_pos[1] - c)  # Même décalage en colonne
            jump_pos = (jump_r, jump_c)
            
            # Essayer le SAUT DIRECT (par-dessus l'adversaire)
            if (0 <= jump_r < BOARD_SIZE and 0 <= jump_c < BOARD_SIZE):
                # Le saut est dans les limites, vérifier s'il n'y a pas de mur
                if not _is_wall_between(state, opponent_pos, jump_pos):
                    moves.append(jump_pos)
                    continue  # Saut réussi, pas besoin de tester les diagonales
            
            # ═══════════════════════════════════════════════════════════════
            # SAUT DIAGONAL (si le saut direct est impossible)
            # ═══════════════════════════════════════════════════════════════
            # Le saut direct est bloqué par un mur ou le bord du plateau
            # On peut alors se déplacer en diagonale par rapport à l'adversaire
            
            if c == opponent_pos[1]:
                # Face-à-face VERTICAL : on peut aller à gauche ou droite de l'adversaire
                for dc in [-1, 1]:  # -1 = gauche, +1 = droite
                    diag_move = (opponent_pos[0], opponent_pos[1] + dc)
                    if (0 <= diag_move[1] < BOARD_SIZE) and not _is_wall_between(state, opponent_pos, diag_move):
                        moves.append(diag_move)
                        
            elif r == opponent_pos[0]:
                # Face-à-face HORIZONTAL : on peut aller en haut ou en bas de l'adversaire
                for dr in [-1, 1]:  # -1 = haut, +1 = bas
                    diag_move = (opponent_pos[0] + dr, opponent_pos[1])
                    if (0 <= diag_move[0] < BOARD_SIZE) and not _is_wall_between(state, opponent_pos, diag_move):
                        moves.append(diag_move)
        else:
            # Case libre et accessible : c'est un mouvement valide
            moves.append(move)
            
    return moves


def move_pawn(state: GameState, player: str, target_coord: Coord) -> GameState:
    """
    Déplace le pion d'un joueur vers une nouvelle position.
    
    Cette fonction :
    1. Vérifie que c'est bien le tour du joueur
    2. Vérifie que le déplacement est légal
    3. Crée un NOUVEL état de jeu avec la position mise à jour
    4. Change le joueur courant
    
    PATTERN IMMUABLE :
    ------------------
    On ne modifie JAMAIS l'état existant. On crée un nouvel objet GameState
    avec les nouvelles valeurs. Cela permet de garder un historique des coups
    et de faciliter la fonction "annuler".
    
    Args:
        state: L'état actuel du jeu
        player: Le joueur qui se déplace
        target_coord: La case de destination (ligne, colonne)
    
    Returns:
        Un NOUVEL état de jeu avec le pion déplacé et le joueur courant changé
    
    Raises:
        InvalidMoveError: Si ce n'est pas le tour du joueur ou si le coup est invalide
    """
    # Vérification 1 : Est-ce le tour de ce joueur ?
    if player != state.current_player:
        raise InvalidMoveError(f"Ce n'est pas le tour du joueur {player}.")
    
    # Vérification 2 : Le déplacement est-il légal ?
    if target_coord not in get_possible_pawn_moves(state, player):
        raise InvalidMoveError(f"Le déplacement vers {target_coord} est invalide.")
    
    # Créer les nouvelles positions (copie pour ne pas modifier l'original)
    new_positions = state.player_positions.copy()
    new_positions[player] = target_coord
    
    # Déterminer le prochain joueur (alterner entre j1 et j2)
    next_player = PLAYER_TWO if player == PLAYER_ONE else PLAYER_ONE
    
    # Créer et retourner le nouvel état (en utilisant replace pour l'immuabilité)
    return replace(state, player_positions=new_positions, current_player=next_player)

# =============================================================================
# LOGIQUE DE PLACEMENT DES MURS
# =============================================================================
#
# Les murs sont l'élément stratégique clé du Quoridor. Un joueur peut choisir
# de placer un mur au lieu de déplacer son pion.
#
# RÈGLES DES MURS :
# -----------------
# 1. Un mur couvre TOUJOURS 2 cases (longueur = 2)
# 2. Un mur peut être horizontal ('h') ou vertical ('v')
# 3. Deux murs ne peuvent pas se chevaucher
# 4. Deux murs ne peuvent pas se croiser au même point central
# 5. Un mur ne peut JAMAIS bloquer complètement le chemin d'un joueur
#
# REPRÉSENTATION D'UN MUR :
# -------------------------
# Un mur est défini par : (orientation, ligne, colonne, longueur)
# La position (ligne, colonne) correspond au coin SUPÉRIEUR GAUCHE du mur.
#
# Exemple : ('h', 3, 4, 2) = mur horizontal
#           Commence à la ligne 3, colonne 4
#           S'étend sur 2 cases vers la droite
# =============================================================================


def _path_exists(state: GameState, start_pos: Coord, is_goal: Callable[[Coord], bool]) -> bool:
    """
    Vérifie s'il existe un chemin entre une position et un objectif.
    
    ALGORITHME UTILISÉ : BFS (Breadth-First Search / Parcours en Largeur)
    ---------------------------------------------------------------------
    Le BFS est parfait pour cette tâche car :
    - Il explore toutes les cases accessibles niveau par niveau
    - Il garantit de trouver un chemin s'il en existe un
    - Il s'arrête dès qu'il atteint l'objectif
    
    FONCTIONNEMENT :
    ----------------
    1. On part de la position de départ
    2. On explore toutes les cases adjacentes accessibles (pas de mur)
    3. Pour chaque case explorée, on vérifie si c'est l'objectif
    4. Si non, on ajoute ses voisins à la file d'attente
    5. On continue jusqu'à trouver l'objectif ou épuiser les cases
    
    COMPLEXITÉ : O(n²) où n = BOARD_SIZE (au pire, on visite toutes les cases)
    
    Args:
        state: L'état actuel du jeu (pour connaître les murs)
        start_pos: Position de départ (ligne, colonne)
        is_goal: Fonction qui retourne True si une position est l'objectif
                 Exemple : lambda pos: pos[0] == 8  (atteindre la ligne 8)
    
    Returns:
        True s'il existe un chemin, False sinon
    """
    # File d'attente (FIFO) pour le BFS - on utilise deque pour performance O(1)
    q = deque([start_pos])
    
    # Ensemble des cases déjà visitées (évite de tourner en rond)
    visited = {start_pos}
    
    while q:
        # Prendre la prochaine case à explorer (la plus ancienne dans la file)
        current_pos = q.popleft()
        
        # Vérifier si on a atteint l'objectif
        if is_goal(current_pos):
            return True
        
        # Explorer les 4 voisins (haut, bas, gauche, droite)
        r, c = current_pos
        potential_moves = [(r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)]
        
        for move in potential_moves:
            # Conditions pour explorer ce voisin :
            # 1. Pas encore visité
            # 2. Dans les limites du plateau
            # 3. Pas de mur qui bloque
            if (move not in visited and 
                0 <= move[0] < BOARD_SIZE and 
                0 <= move[1] < BOARD_SIZE and 
                not _is_wall_between(state, current_pos, move)):
                visited.add(move)
                q.append(move)
                
    # Si on a épuisé toutes les cases accessibles sans trouver l'objectif
    return False


def _validate_wall_placement(state: GameState, wall: Wall) -> None:
    """
    Vérifie qu'un mur peut être placé selon les règles géométriques.
    
    Cette fonction vérifie UNIQUEMENT les règles de placement physique du mur,
    PAS si le mur bloque un joueur (c'est fait dans place_wall).
    
    RÈGLES VÉRIFIÉES :
    ------------------
    1. LIMITES : Le mur doit être entièrement dans le plateau
       - ligne et colonne doivent être entre 0 et 7 (pas 8, car le mur a une longueur de 2)
    
    2. COLLISION : Le mur ne doit pas être identique à un mur existant
    
    3. CHEVAUCHEMENT : Le mur ne doit pas chevaucher un mur parallèle existant
       - Deux murs horizontaux ne peuvent pas se superposer
       - Deux murs verticaux ne peuvent pas se superposer
    
    4. CROISEMENT : Le mur ne doit pas croiser un mur perpendiculaire au même point
       - Un mur horizontal et un mur vertical ne peuvent pas se croiser au centre
    
    VISUALISATION DU CHEVAUCHEMENT :
    --------------------------------
    Mur existant :    ━━━━━
    Mur proposé :       ━━━━━   ← INTERDIT (chevauchement)
    
    VISUALISATION DU CROISEMENT :
    -----------------------------
    Mur existant :    ━━━━━
    Mur proposé :       ┃      ← INTERDIT (croisement au centre)
                        ┃
    
    Args:
        state: L'état actuel du jeu
        wall: Le mur à valider (orientation, ligne, colonne, longueur)
    
    Raises:
        InvalidMoveError: Si le placement viole une règle
    """
    orientation, r, c, length = wall
    
    # ═══════════════════════════════════════════════════════════════════════
    # RÈGLE 1 : Vérifier que le mur est dans les limites du plateau
    # ═══════════════════════════════════════════════════════════════════════
    # Comme un mur a une longueur de 2, il ne peut pas commencer sur la
    # dernière ligne ou colonne (indices 0 à 7 seulement, pas 8)
    if not (0 <= r < BOARD_SIZE - 1 and 0 <= c < BOARD_SIZE - 1):
        raise InvalidMoveError("Le mur est en dehors des limites de placement.")

    # ═══════════════════════════════════════════════════════════════════════
    # RÈGLE 2 : Vérifier qu'un mur identique n'existe pas déjà
    # ═══════════════════════════════════════════════════════════════════════
    if wall in state.walls:
        raise InvalidMoveError("Un mur identique existe déjà.")
    
    # ═══════════════════════════════════════════════════════════════════════
    # RÈGLE 3 : Vérifier le chevauchement avec des murs parallèles
    # ═══════════════════════════════════════════════════════════════════════
    # Un mur de longueur 2 chevauche les murs à c-1 et c+1 (horizontal)
    # ou à r-1 et r+1 (vertical)
    if orientation == 'h':
        # Pour un mur horizontal, vérifier les murs horizontaux adjacents
        overlapping = [('h', r, c - 1, 2), ('h', r, c + 1, 2)]
        for ow in overlapping:
            if ow in state.walls:
                raise InvalidMoveError("Le mur chevauche un mur existant.")
    else:
        # Pour un mur vertical, vérifier les murs verticaux adjacents
        overlapping = [('v', r - 1, c, 2), ('v', r + 1, c, 2)]
        for ow in overlapping:
            if ow in state.walls:
                raise InvalidMoveError("Le mur chevauche un mur existant.")
    
    # ═══════════════════════════════════════════════════════════════════════
    # RÈGLE 4 : Vérifier le croisement avec un mur perpendiculaire
    # ═══════════════════════════════════════════════════════════════════════
    # Un mur horizontal croise un mur vertical s'ils ont le même point central
    # Le mur perpendiculaire aurait la même position mais l'autre orientation
    intersecting = ('v', r, c, 2) if orientation == 'h' else ('h', r, c, 2)
    if intersecting in state.walls:
        raise InvalidMoveError("Le mur croise un mur existant.")


def place_wall(state: GameState, player: str, wall: Wall) -> GameState:
    """
    Place un mur sur le plateau et retourne le nouvel état de jeu.
    
    Cette fonction est le point d'entrée principal pour placer un mur.
    Elle effectue TOUTES les validations nécessaires :
    
    ÉTAPES DE VALIDATION :
    ----------------------
    1. Vérifier que c'est le tour du joueur
    2. Vérifier que le joueur a encore des murs
    3. Vérifier les règles géométriques (via _validate_wall_placement)
    4. Vérifier que le mur ne bloque pas complètement un joueur (via _path_exists)
    
    RÈGLE FONDAMENTALE DU QUORIDOR :
    --------------------------------
    Un mur ne peut JAMAIS être placé s'il bloque complètement le chemin d'un
    joueur vers son objectif. Cette règle garantit que la partie peut toujours
    se terminer (pas de blocage total).
    
    Args:
        state: L'état actuel du jeu
        player: Le joueur qui place le mur
        wall: Le mur à placer (orientation, ligne, colonne, longueur)
    
    Returns:
        Un NOUVEL état de jeu avec le mur ajouté
    
    Raises:
        InvalidMoveError: Si le placement est invalide pour n'importe quelle raison
    """
    # Vérification 1 : Est-ce le tour de ce joueur ?
    if player != state.current_player:
        raise InvalidMoveError(f"Ce n'est pas le tour du joueur {player}.")
    
    # Vérification 2 : Le joueur a-t-il encore des murs ?
    if state.player_walls[player] <= 0:
        raise InvalidMoveError("Le joueur n'a plus de murs.")
    
    # Vérification 3 : Le mur respecte-t-il les règles géométriques ?
    _validate_wall_placement(state, wall)
    
    # ═══════════════════════════════════════════════════════════════════════
    # Vérification 4 : Le mur ne bloque-t-il pas complètement un joueur ?
    # ═══════════════════════════════════════════════════════════════════════
    # On crée un état TEMPORAIRE avec le mur pour tester
    temp_walls = state.walls.copy()
    temp_walls.add(wall)
    temp_state = replace(state, walls=temp_walls)
    
    # Définir les objectifs de chaque joueur
    goal_j1 = lambda pos: pos[0] == BOARD_SIZE - 1  # J1 doit atteindre la ligne 8
    goal_j2 = lambda pos: pos[0] == 0              # J2 doit atteindre la ligne 0
    
    # Vérifier que le joueur 1 peut encore atteindre son objectif
    if not _path_exists(temp_state, temp_state.player_positions[PLAYER_ONE], goal_j1):
        raise InvalidMoveError("Le mur bloque le chemin du joueur 1.")
    
    # Vérifier que le joueur 2 peut encore atteindre son objectif
    if not _path_exists(temp_state, temp_state.player_positions[PLAYER_TWO], goal_j2):
        raise InvalidMoveError("Le mur bloque le chemin du joueur 2.")
    
    # ═══════════════════════════════════════════════════════════════════════
    # Tout est valide ! Créer le nouvel état de jeu
    # ═══════════════════════════════════════════════════════════════════════
    new_player_walls = state.player_walls.copy()
    new_player_walls[player] -= 1  # Décrémenter le compteur de murs
    
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
    
    Cette fonction est utile pour une interface graphique où l'utilisateur
    clique sur deux cases adjacentes pour indiquer où placer un mur.
    
    LOGIQUE :
    ---------
    - Si les deux cases sont sur la même LIGNE → mur HORIZONTAL
    - Si les deux cases sont sur la même COLONNE → mur VERTICAL
    
    Le mur est positionné entre les deux cases cliquées.
    
    EXEMPLE :
    ---------
    Clic 1 : (2, 3)    Clic 2 : (2, 4)
    → Même ligne (2), colonnes adjacentes (3 et 4)
    → Mur horizontal : ('h', 2, 3, 2)
    
    Args:
        case1: Première case cliquée (ligne, colonne)
        case2: Deuxième case cliquée (ligne, colonne)
    
    Returns:
        Un tuple Wall (orientation, ligne, colonne, longueur=2)
    
    Raises:
        InvalidMoveError: Si les deux cases ne sont pas adjacentes
    """
    r1, c1 = case1
    r2, c2 = case2
    
    # Cas 1 : Mur HORIZONTAL (même ligne, colonnes adjacentes)
    if r1 == r2 and abs(c1 - c2) == 1:
        col_min = min(c1, c2)
        return ('h', r1, col_min, 2)
    
    # Cas 2 : Mur VERTICAL (même colonne, lignes adjacentes)
    if c1 == c2 and abs(r1 - r2) == 1:
        ligne_min = min(r1, r2)
        return ('v', ligne_min, c1, 2)
    
    # Les cases ne sont pas adjacentes : erreur
    raise InvalidMoveError("Les deux cases cliquées doivent être adjacentes.")

# =============================================================================
# ORCHESTRATION DU JEU - Classe QuoridorGame
# =============================================================================
#
# Cette classe est le CONTRÔLEUR principal du jeu. Elle :
# - Encapsule l'état du jeu et l'historique des coups
# - Fournit une API simple et sécurisée pour jouer
# - Gère la fonction "Annuler" (undo)
#
# PATTERN UTILISÉ : Façade + Historique
# --------------------------------------
# - La classe agit comme une FAÇADE : elle simplifie l'accès aux fonctions
#   complexes du moteur de jeu (move_pawn, place_wall, etc.)
# - Elle maintient un HISTORIQUE des états pour permettre l'annulation
# =============================================================================


class QuoridorGame:
    """
    Classe principale pour gérer une partie complète de Quoridor.
    
    Cette classe est le point d'entrée pour toute interaction avec le jeu.
    Elle encapsule toute la complexité du moteur et expose une API simple.
    
    RESPONSABILITÉS :
    -----------------
    1. Créer une nouvelle partie
    2. Permettre de jouer des coups (déplacements et murs)
    3. Gérer l'historique pour la fonction "Annuler"
    4. Vérifier si la partie est terminée et qui a gagné
    
    EXEMPLE D'UTILISATION :
    -----------------------
    ```python
    # Créer une nouvelle partie
    partie = QuoridorGame()
    
    # Jouer des coups
    partie.play_move(('deplacement', (1, 4)))  # J1 avance
    partie.play_move(('mur', ('h', 6, 4, 2)))  # J2 pose un mur
    
    # Annuler le dernier coup
    partie.undo_move()
    
    # Vérifier si la partie est finie
    if partie.is_game_over()[0]:
        print(f"Gagnant : {partie.get_winner()}")
    ```
    
    ATTRIBUTS PRIVÉS :
    ------------------
    _history : List[GameState]
        Liste des états précédents (pour la fonction undo)
        Le dernier élément est l'état le plus récent avant le coup actuel
        
    _current_state : GameState
        L'état actuel du jeu
    """
    
    def __init__(self):
        """
        Initialise une nouvelle partie de Quoridor.
        
        Crée un état de jeu initial avec :
        - Les deux pions au centre de leur ligne respective
        - Aucun mur posé
        - 10 murs disponibles par joueur
        - C'est au tour du joueur 1
        """
        # Historique vide au départ (aucun coup joué)
        self._history: List[GameState] = []
        
        # Créer l'état initial du jeu
        self._current_state: GameState = create_new_game()

    def get_current_state(self) -> GameState:
        """
        Retourne l'état actuel du jeu.
        
        Cette méthode est "sûre" car GameState est immuable (frozen=True).
        L'appelant ne peut pas modifier l'état interne de la partie.
        
        Returns:
            L'objet GameState actuel (immuable)
        """
        return self._current_state
    
    def get_current_player(self) -> str:
        """
        Retourne le joueur dont c'est le tour.
        
        Returns:
            'j1' ou 'j2'
        """
        return self._current_state.current_player
    
    def get_possible_moves(self, player: str | None = None) -> List[Move]:
        """
        Retourne tous les déplacements possibles pour un joueur.
        
        NOTE : Cette méthode ne retourne que les DÉPLACEMENTS de pion,
        pas les placements de murs (trop nombreux à calculer).
        L'IA utilise sa propre logique pour générer les murs stratégiques.
        
        Args:
            player: Le joueur concerné (par défaut : le joueur courant)
        
        Returns:
            Liste de coups au format [('deplacement', (ligne, col)), ...]
        """
        if player is None:
            player = self._current_state.current_player
            
        moves: List[Move] = []
        
        # Récupérer tous les déplacements possibles pour ce joueur
        pawn_moves = get_possible_pawn_moves(self._current_state, player)
        for coord in pawn_moves:
            moves.append(('deplacement', coord))
        
        # NOTE : On ne génère pas les murs ici car :
        # 1. Il y a potentiellement des centaines de murs valides
        # 2. Calculer tous les murs valides est coûteux (O(n²) vérifications)
        # 3. L'IA a sa propre logique pour générer des murs "stratégiques"
        if self._current_state.player_walls[player] > 0:
            pass  # Les murs sont gérés séparément
        
        return moves

    def play_move(self, move: Move) -> None:
        """
        Joue un coup et met à jour l'état du jeu.
        
        Cette méthode est le point d'entrée principal pour jouer.
        Elle gère automatiquement :
        - La sauvegarde de l'état pour l'historique (undo)
        - La validation du coup
        - La mise à jour de l'état
        - Le changement de joueur courant
        
        GESTION DES ERREURS :
        ---------------------
        Si le coup est invalide, une exception est levée et l'état
        du jeu reste INCHANGÉ (rollback automatique).
        
        Args:
            move: Un tuple décrivant le coup :
                  - ('deplacement', (ligne, colonne)) pour déplacer le pion
                  - ('mur', ('h'|'v', ligne, colonne, 2)) pour poser un mur
        
        Raises:
            InvalidMoveError: Si le coup est invalide selon les règles
            ValueError: Si le type de coup n'est pas reconnu
        
        Exemples:
            partie.play_move(('deplacement', (1, 4)))  # Avancer en e2
            partie.play_move(('mur', ('h', 3, 4, 2)))  # Mur horizontal en e4
        """
        move_type, move_data = move
        player = self._current_state.current_player
        
        # ═══════════════════════════════════════════════════════════════════
        # PATTERN : Sauvegarde avant modification
        # ═══════════════════════════════════════════════════════════════════
        # On sauvegarde l'état AVANT de le modifier pour pouvoir restaurer
        # en cas d'erreur ou pour la fonction "Annuler"
        self._history.append(self._current_state)
        
        try:
            # Exécuter le coup selon son type
            if move_type == 'deplacement':
                self._current_state = move_pawn(self._current_state, player, move_data)
            elif move_type == 'mur':
                self._current_state = place_wall(self._current_state, player, move_data)
            else:
                raise ValueError(f"Type de coup inconnu: {move_type}")
                
        except (InvalidMoveError, ValueError) as e:
            # ═══════════════════════════════════════════════════════════════
            # ROLLBACK : Le coup a échoué, restaurer l'état précédent
            # ═══════════════════════════════════════════════════════════════
            self._history.pop()  # Retirer l'état qu'on venait d'ajouter
            raise  # Re-lever l'exception pour informer l'appelant

    def undo_move(self) -> bool:
        """
        Annule le dernier coup joué et restaure l'état précédent.
        
        Cette fonction implémente la fonctionnalité "Annuler" (Ctrl+Z).
        Elle utilise l'historique des états sauvegardés pour revenir
        à l'état d'avant le dernier coup.
        
        COMPORTEMENT :
        --------------
        - Si un historique existe : restaure l'état précédent et retourne True
        - Si pas d'historique (début de partie) : ne fait rien et retourne False
        
        Returns:
            True si l'annulation a réussi, False s'il n'y a rien à annuler
        
        Exemple:
            partie.play_move(('deplacement', (1, 4)))  # Joueur 1 avance
            partie.undo_move()  # Annuler → retour à l'état initial
        """
        if not self._history:
            return False  # Pas d'historique, impossible d'annuler
        
        # Restaurer le dernier état sauvegardé
        self._current_state = self._history.pop()
        return True
    
    def is_game_over(self) -> Tuple[bool, str | None]:
        """
        Vérifie si la partie est terminée.
        
        Returns:
            Tuple (partie_terminée, gagnant)
            - (True, 'j1') si le joueur 1 a gagné
            - (True, 'j2') si le joueur 2 a gagné
            - (False, None) si la partie continue
        """
        return self._current_state.is_game_over()
    
    def get_winner(self) -> str | None:
        """
        Retourne le gagnant de la partie.
        
        Returns:
            'j1' si le joueur 1 a gagné
            'j2' si le joueur 2 a gagné
            None si la partie n'est pas encore terminée
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
