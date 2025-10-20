# -*- coding: utf-8 -*-
"""
Fichier principal pour lancer une partie de Quoridor en mode console.
Utilise le moteur de jeu défini dans quoridor_engine/core.py.
"""

import os
import time
from typing import Tuple, Optional
from quoridor_engine.core import (
    QuoridorGame, 
    InvalidMoveError, 
    PLAYER_ONE, 
    PLAYER_TWO, 
    BOARD_SIZE,
    Move
)
from quoridor_engine.ai import AI

# Tentative d'import de colorama pour les couleurs (optionnel)
try:
    from colorama import Fore, Style, init
    init(autoreset=True)
    COLORS_ENABLED = True
except ImportError:
    COLORS_ENABLED = False
    # Définir des constantes vides si colorama n'est pas installé
    class Fore:
        BLUE = ''
        RED = ''
        GREEN = ''
        YELLOW = ''
    
    class Style:
        RESET_ALL = ''


def _parse_coord(s: str) -> Optional[Tuple[int, int]]:
    """
    Convertit une notation 'e2' en coordonnées (ligne, colonne) -> (1, 4).
    
    Args:
        s: Notation échecs (ex: 'e2')
    
    Returns:
        Tuple (ligne, colonne) ou None si invalide
    """
    if len(s) != 2 or not s[0].isalpha() or not s[1].isdigit():
        return None
    
    col = ord(s[0].lower()) - ord('a')
    row = int(s[1]) - 1
    
    if 0 <= col < BOARD_SIZE and 0 <= row < BOARD_SIZE:
        return (row, col)
    return None


def _coord_to_notation(coord: Tuple[int, int]) -> str:
    """
    Convertit (ligne, col) en notation 'e2'.
    
    Args:
        coord: Tuple (ligne, colonne)
    
    Returns:
        Notation échecs (ex: 'e2')
    """
    return f"{chr(ord('a') + coord[1])}{coord[0] + 1}"


def clear_screen():
    """Efface l'écran du terminal."""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_help():
    """Affiche l'aide des commandes."""
    print(f"\n{Fore.GREEN}=== AIDE ==={Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}d <case>{Style.RESET_ALL}        : Déplacer le pion (ex: 'd e5')")
    print(f"  {Fore.YELLOW}m <h|v> <case>{Style.RESET_ALL}  : Placer un mur horizontal(h) ou vertical(v) (ex: 'm h e3')")
    print(f"  {Fore.YELLOW}undo{Style.RESET_ALL}            : Annuler le dernier coup")
    print(f"  {Fore.YELLOW}moves / ?{Style.RESET_ALL}       : Afficher les coups possibles")
    print(f"  {Fore.YELLOW}help / h{Style.RESET_ALL}        : Afficher cette aide")
    print(f"  {Fore.YELLOW}quit / q{Style.RESET_ALL}        : Quitter la partie")
    print(f"{Fore.GREEN}============{Style.RESET_ALL}\n")


def display_board(game: QuoridorGame, ai_mode: bool = False):
    """
    Affiche l'état actuel du plateau de jeu dans la console.
    
    Args:
        game: Instance de QuoridorGame
        ai_mode: True si on joue contre l'IA
    """
    state = game.get_current_state()
    
    # Crée une grille de caractères plus grande pour dessiner les murs
    # Chaque case est un caractère, chaque mur est un caractère
    grid_size = BOARD_SIZE * 2 - 1
    grid = [[' ' for _ in range(grid_size)] for _ in range(grid_size)]

    # Place les points pour les cases
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            grid[r * 2][c * 2] = '·'

    # Place les murs
    for wall in state.walls:
        orientation, r, c, _ = wall
        if orientation == 'h':
            # Mur horizontal : 3 caractères (couvre 2 cases)
            grid[r * 2 + 1][c * 2] = '━'
            grid[r * 2 + 1][c * 2 + 1] = '━'
            grid[r * 2 + 1][c * 2 + 2] = '━'
        else:  # 'v'
            # Mur vertical : 3 caractères (couvre 2 cases)
            grid[r * 2][c * 2 + 1] = '┃'
            grid[r * 2 + 1][c * 2 + 1] = '┃'
            grid[r * 2 + 2][c * 2 + 1] = '┃'

    # Place les pions avec couleurs
    pos_j1 = state.player_positions[PLAYER_ONE]
    grid[pos_j1[0] * 2][pos_j1[1] * 2] = f'{Fore.BLUE}1{Style.RESET_ALL}' if COLORS_ENABLED else '1'
    
    pos_j2 = state.player_positions[PLAYER_TWO]
    grid[pos_j2[0] * 2][pos_j2[1] * 2] = f'{Fore.RED}2{Style.RESET_ALL}' if COLORS_ENABLED else '2'

    # Affiche la grille
    clear_screen()
    print(f"\n{Fore.GREEN}{'=' * 40}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}   🎮  QUORIDOR - Partie en cours  🎮{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'=' * 40}{Style.RESET_ALL}\n")
    
    print("   a b c d e f g h i")
    print("  " + "━" * (grid_size))
    for i, row in enumerate(grid):
        if i % 2 == 0:
            print(f"{i // 2 + 1}┃{''.join(row)}┃")
        else:
            print(f" ┃{''.join(row)}┃")
    print("  " + "━" * (grid_size))
    
    # Affiche les informations sur les joueurs
    j1_color = f'{Fore.BLUE}Joueur 1{Style.RESET_ALL}' if COLORS_ENABLED else 'Joueur 1'
    
    if ai_mode:
        j2_color = f'{Fore.RED}IA{Style.RESET_ALL}' if COLORS_ENABLED else 'IA'
    else:
        j2_color = f'{Fore.RED}Joueur 2{Style.RESET_ALL}' if COLORS_ENABLED else 'Joueur 2'
    
    print(f"\n  Murs restants: {j1_color} [{state.player_walls[PLAYER_ONE]}]   {j2_color} [{state.player_walls[PLAYER_TWO]}]")
    print(f"  Tapez '{Fore.YELLOW}help{Style.RESET_ALL}' pour voir les commandes disponibles")
    print("-" * 40)


def prompt_for_move(game: QuoridorGame) -> Optional[Move]:
    """
    Demande un coup au joueur courant et le retourne au format Move.
    
    Args:
        game: Instance de QuoridorGame
    
    Returns:
        Tuple Move ou None pour quitter
    """
    player = game.get_current_player()
    player_num = player[-1]
    player_color = Fore.BLUE if player == PLAYER_ONE else Fore.RED
    
    while True:
        prompt_text = f"{player_color}Tour du Joueur {player_num}{Style.RESET_ALL}. Entrez votre coup: "
        action = input(prompt_text).strip().lower()
        parts = action.split()
        
        if not parts:
            continue

        # Commande undo
        if parts[0] == 'undo':
            return ('undo', None)
        
        # Commande quit
        if parts[0] == 'quit' or parts[0] == 'q':
            confirm = input(f"{Fore.YELLOW}Êtes-vous sûr de vouloir quitter ? (o/n): {Style.RESET_ALL}").strip().lower()
            if confirm in ['o', 'oui', 'y', 'yes']:
                return None
            continue
        
        # Commande help
        if parts[0] == 'help' or parts[0] == 'h':
            print_help()
            continue
        
        # Commande moves
        if parts[0] == 'moves' or parts[0] == '?':
            possible_moves = game.get_possible_moves()
            if possible_moves:
                coords = [_coord_to_notation(move[1]) for move in possible_moves if move[0] == 'deplacement']
                print(f"{Fore.GREEN}Coups possibles : {', '.join(coords)}{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}Aucun coup disponible.{Style.RESET_ALL}")
            input("Appuyez sur Entrée pour continuer...")
            continue

        if len(parts) < 2:
            print(f"{Fore.RED}Commande invalide. Format: 'd <case>' ou 'm <h|v> <case>'{Style.RESET_ALL}")
            continue
            
        move_type_str, move_data_str = parts[0], parts[1:]
        
        # Déplacement
        if move_type_str == 'd' and len(move_data_str) == 1:
            coord = _parse_coord(move_data_str[0])
            if coord:
                return ('deplacement', coord)
            else:
                print(f"{Fore.RED}Coordonnée invalide: '{move_data_str[0]}'. Utilisez 'a1' à 'i9'.{Style.RESET_ALL}")
        
        # Mur
        elif move_type_str == 'm' and len(move_data_str) == 2:
            orientation, coord_str = move_data_str[0], move_data_str[1]
            if orientation not in ['h', 'v']:
                print(f"{Fore.RED}Orientation de mur invalide: '{orientation}'. Utilisez 'h' ou 'v'.{Style.RESET_ALL}")
                continue
            
            coord = _parse_coord(coord_str)
            if coord:
                # La coordonnée d'un mur est son coin supérieur gauche
                return ('mur', (orientation, coord[0], coord[1], 2))
            else:
                print(f"{Fore.RED}Coordonnée invalide: '{coord_str}'.{Style.RESET_ALL}")
        
        else:
            print(f"{Fore.RED}Commande invalide. Format: 'd <case>' ou 'm <h|v> <case>'{Style.RESET_ALL}")


def select_game_mode() -> Tuple[str, Optional[AI]]:
    """
    Menu de sélection du mode de jeu.
    
    Returns:
        Tuple (mode, ia) où mode est 'pvp' ou 'pvia' et ia est l'instance d'IA ou None
    """
    clear_screen()
    print(f"\n{Fore.GREEN}{'=' * 40}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}  QUORIDOR - Sélection du mode{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'=' * 40}{Style.RESET_ALL}\n")
    print(f"  {Fore.YELLOW}1{Style.RESET_ALL} - Joueur vs Joueur")
    print(f"  {Fore.YELLOW}2{Style.RESET_ALL} - Joueur vs IA\n")
    
    while True:
        choice = input(f"Choisissez un mode (1 ou 2): ").strip()
        
        if choice == '1':
            return 'pvp', None
        
        elif choice == '2':
            # Sélection de la difficulté
            print(f"\n{Fore.GREEN}Niveau de difficulté :{Style.RESET_ALL}")
            print(f"  {Fore.YELLOW}1{Style.RESET_ALL} - Facile (rapide)")
            print(f"  {Fore.YELLOW}2{Style.RESET_ALL} - Normal (équilibré)")
            print(f"  {Fore.YELLOW}3{Style.RESET_ALL} - Difficile (lent mais fort)\n")
            
            while True:
                diff_choice = input(f"Choisissez la difficulté (1, 2 ou 3): ").strip()
                
                if diff_choice == '1':
                    ia = AI(PLAYER_TWO, difficulty='facile')
                    return 'pvia', ia
                elif diff_choice == '2':
                    ia = AI(PLAYER_TWO, difficulty='normal')
                    return 'pvia', ia
                elif diff_choice == '3':
                    ia = AI(PLAYER_TWO, difficulty='difficile')
                    return 'pvia', ia
                else:
                    print(f"{Fore.RED}Choix invalide. Entrez 1, 2 ou 3.{Style.RESET_ALL}")
        
        else:
            print(f"{Fore.RED}Choix invalide. Entrez 1 ou 2.{Style.RESET_ALL}")


def display_ai_move(move: Move, thinking_time: float):
    """
    Affiche le coup joué par l'IA de manière claire.
    
    Args:
        move: Le coup joué par l'IA
        thinking_time: Temps de réflexion en secondes
    """
    move_type, move_data = move
    
    if move_type == 'deplacement':
        coord_notation = _coord_to_notation(move_data)
        print(f"\n{Fore.RED}🤖 L'IA se déplace en {Fore.YELLOW}{coord_notation}{Style.RESET_ALL}")
    else:  # 'mur'
        orientation, r, c, _ = move_data
        coord_notation = _coord_to_notation((r, c))
        orientation_str = "horizontal" if orientation == 'h' else "vertical"
        print(f"\n{Fore.RED}🤖 L'IA place un mur {orientation_str} en {Fore.YELLOW}{coord_notation}{Style.RESET_ALL}")
    
    print(f"   {Fore.GREEN}(Temps de réflexion: {thinking_time:.1f}s){Style.RESET_ALL}")


def main():
    """Fonction principale pour lancer et gérer la partie."""
    try:
        # Sélection du mode de jeu
        mode, ia = select_game_mode()
        
        clear_screen()
        print(f"\n{Fore.GREEN}{'=' * 40}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}  Bienvenue dans QUORIDOR !{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{'=' * 40}{Style.RESET_ALL}\n")
        
        if mode == 'pvp':
            print(f"  {Fore.CYAN}Mode : Joueur vs Joueur{Style.RESET_ALL}")
        else:
            print(f"  {Fore.CYAN}Mode : Joueur vs IA{Style.RESET_ALL}")
        
        print(f"\n  {Fore.BLUE}Joueur 1{Style.RESET_ALL} (Vous) commence en haut (ligne 1)")
        
        if mode == 'pvia':
            print(f"  {Fore.RED}IA{Style.RESET_ALL} joue en bas (ligne 9)")
        else:
            print(f"  {Fore.RED}Joueur 2{Style.RESET_ALL} commence en bas (ligne 9)")
        
        print(f"\n  Objectif : {Fore.BLUE}Joueur 1{Style.RESET_ALL} → atteindre la ligne 9")
        
        if mode == 'pvia':
            print(f"            {Fore.RED}IA{Style.RESET_ALL} → atteindre la ligne 1")
        else:
            print(f"            {Fore.RED}Joueur 2{Style.RESET_ALL} → atteindre la ligne 1")
        
        print(f"\n  Tapez '{Fore.YELLOW}help{Style.RESET_ALL}' à tout moment pour voir les commandes\n")
        input("Appuyez sur Entrée pour commencer...")
        
        partie = QuoridorGame()
        
        while not partie.is_game_over()[0]:
            display_board(partie, ai_mode=(mode == 'pvia'))
            
            # Tour de l'IA
            if mode == 'pvia' and partie.get_current_player() == PLAYER_TWO:
                print(f"\n{Fore.RED}🤖 L'IA réfléchit...{Style.RESET_ALL}")
                
                start_time = time.time()
                ai_move = ia.find_best_move(partie.get_current_state(), verbose=False)
                thinking_time = time.time() - start_time
                
                display_ai_move(ai_move, thinking_time)
                
                try:
                    partie.play_move(ai_move)
                except InvalidMoveError as e:
                    print(f"\n{Fore.RED}!!! ERREUR IA: {e} !!!{Style.RESET_ALL}")
                    print("L'IA a fait un coup invalide (cela ne devrait pas arriver).")
                    break
                
                input("Appuyez sur Entrée pour continuer...")
                continue
            
            # Tour du joueur humain
            move = prompt_for_move(partie)
            
            # Quit
            if move is None:
                print(f"\n{Fore.YELLOW}Partie abandonnée. Au revoir !{Style.RESET_ALL}\n")
                break
            
            # Undo
            if move[0] == 'undo':
                if mode == 'pvia':
                    # En mode IA, annuler 2 coups (joueur + IA)
                    if partie.undo_move() and partie.undo_move():
                        print(f"{Fore.GREEN}✓ Vos 2 derniers coups annulés{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}Impossible d'annuler, pas assez de coups dans l'historique.{Style.RESET_ALL}")
                else:
                    # En mode PvP, annuler 1 coup
                    if partie.undo_move():
                        print(f"{Fore.GREEN}✓ Coup annulé{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}Impossible d'annuler, aucun coup dans l'historique.{Style.RESET_ALL}")
                input("Appuyez sur Entrée pour continuer...")
                continue
            
            # Jouer le coup
            try:
                partie.play_move(move)
            except InvalidMoveError as e:
                print(f"\n{Fore.RED}!!! COUP INVALIDE: {e} !!!{Style.RESET_ALL}")
                input("Appuyez sur Entrée pour continuer...")

        # Fin de la partie (si victoire, pas abandon)
        if partie.is_game_over()[0]:
            display_board(partie, ai_mode=(mode == 'pvia'))
            winner = partie.get_winner()
            winner_color = Fore.BLUE if winner == PLAYER_ONE else Fore.RED
            
            print(f"\n{Fore.GREEN}{'=' * 40}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}  🎉 PARTIE TERMINÉE ! 🎉{Style.RESET_ALL}")
            
            if mode == 'pvia':
                if winner == PLAYER_ONE:
                    print(f"{winner_color}  🏆 VOUS AVEZ GAGNÉ ! 🏆{Style.RESET_ALL}")
                else:
                    print(f"{winner_color}  🤖 L'IA A GAGNÉ ! 🤖{Style.RESET_ALL}")
            else:
                winner_num = winner[-1]
                print(f"{winner_color}  Victoire du Joueur {winner_num} !{Style.RESET_ALL}")
            
            print(f"{Fore.GREEN}{'=' * 40}{Style.RESET_ALL}\n")
    
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}Partie interrompue. Au revoir !{Style.RESET_ALL}\n")
    
    except Exception as e:
        print(f"\n{Fore.RED}!!! ERREUR CRITIQUE: {e} !!!{Style.RESET_ALL}\n")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()

