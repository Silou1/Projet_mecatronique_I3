# -*- coding: utf-8 -*-
"""
=============================================================================
INTERFACE CONSOLE POUR QUORIDOR (main.py)
=============================================================================

Ce fichier est le POINT D'ENTRÉE du jeu. Il gère :
- L'interface utilisateur en mode console (texte)
- L'affichage du plateau de jeu
- La saisie et le parsing des commandes du joueur
- La boucle de jeu principale

ARCHITECTURE DU PROJET :
------------------------
Ce fichier fait le lien entre l'utilisateur et le moteur de jeu :

    [Utilisateur] ←→ [main.py (Interface)] ←→ [core.py (Moteur)]
                                          ←→ [ai.py (IA)]

Le fichier main.py ne contient PAS de logique de jeu (règles, validations).
Il se contente de :
1. Afficher l'état du jeu (plateau, scores)
2. Lire les commandes de l'utilisateur
3. Transmettre les coups au moteur de jeu
4. Afficher les résultats et erreurs

COMMANDES DISPONIBLES :
-----------------------
- d <case>      : Déplacer le pion (ex: 'd e5')
- m <h|v> <case>: Placer un mur (ex: 'm h e3')
- undo          : Annuler le dernier coup
- moves / ?     : Afficher les coups possibles
- help / h      : Afficher l'aide
- quit / q      : Quitter la partie

NOTATION DES CASES :
--------------------
On utilise la notation "échecs" : lettre (colonne) + chiffre (ligne)
- Colonnes : a à f (gauche à droite)
- Lignes : 1 à 6 (haut en bas)
Exemple : 'd3' = colonne centrale, ligne du milieu
"""

import os
import time
from typing import Tuple, Optional

# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTS DU MOTEUR DE JEU
# ═══════════════════════════════════════════════════════════════════════════════
from quoridor_engine.core import (
    QuoridorGame,      # Classe principale pour gérer une partie
    InvalidMoveError,  # Exception pour les coups invalides
    PLAYER_ONE,        # Identifiant du joueur 1 ('j1')
    PLAYER_TWO,        # Identifiant du joueur 2 ('j2')
    BOARD_SIZE,        # Taille du plateau (6)
    Move               # Type pour représenter un coup
)
from quoridor_engine.ai import AI  # Intelligence Artificielle

# ═══════════════════════════════════════════════════════════════════════════════
# GESTION DES COULEURS DANS LE TERMINAL
# ═══════════════════════════════════════════════════════════════════════════════
# La bibliothèque 'colorama' permet d'afficher du texte en couleur dans le terminal.
# Elle est OPTIONNELLE : si elle n'est pas installée, le jeu fonctionne quand même
# (mais en noir et blanc).
#
# Pour installer colorama : pip install colorama
try:
    from colorama import Fore, Style, init
    init(autoreset=True)  # Reset automatique des couleurs après chaque print
    COLORS_ENABLED = True
except ImportError:
    # Si colorama n'est pas installé, on définit des constantes vides
    # pour que le code fonctionne sans modification
    COLORS_ENABLED = False
    
    class Fore:
        """Classe factice si colorama n'est pas installé."""
        BLUE = ''
        RED = ''
        GREEN = ''
        YELLOW = ''
        CYAN = ''
    
    class Style:
        """Classe factice si colorama n'est pas installé."""
        RESET_ALL = ''


# =============================================================================
# FONCTIONS UTILITAIRES : Conversion de coordonnées
# =============================================================================
#
# Le jeu utilise deux systèmes de coordonnées :
# 1. NOTATION UTILISATEUR : 'e5' (comme aux échecs) - plus intuitif
# 2. COORDONNÉES INTERNES : (4, 4) = (ligne, colonne) - pour le moteur
#
# Ces fonctions font la conversion entre les deux systèmes.

def _parse_coord(s: str) -> Optional[Tuple[int, int]]:
    """
    Convertit une notation utilisateur ('e5') en coordonnées internes (4, 4).
    
    SYSTÈME DE NOTATION :
    ---------------------
    - Première lettre (a-f) → colonne (0-5)
    - Chiffre (1-6) → ligne (0-5)
    
    EXEMPLES :
    ----------
    'a1' → (0, 0)  = coin haut-gauche
    'd3' → (2, 3)  = centre du plateau
    'f6' → (5, 5)  = coin bas-droite
    
    CALCUL :
    --------
    - Colonne : ord('d') - ord('a') = 100 - 97 = 3
    - Ligne : int('3') - 1 = 2  (car on indexe à partir de 0)
    
    Args:
        s: Chaîne de caractères en notation échecs (ex: 'e5')
    
    Returns:
        Tuple (ligne, colonne) si valide, None sinon
    """
    # Vérifier le format : exactement 2 caractères, lettre puis chiffre
    if len(s) != 2 or not s[0].isalpha() or not s[1].isdigit():
        return None
    
    # Convertir la lettre en numéro de colonne (a=0, b=1, ..., i=8)
    col = ord(s[0].lower()) - ord('a')
    
    # Convertir le chiffre en numéro de ligne (1→0, 2→1, ..., 9→8)
    row = int(s[1]) - 1
    
    # Vérifier que les coordonnées sont dans les limites du plateau
    if 0 <= col < BOARD_SIZE and 0 <= row < BOARD_SIZE:
        return (row, col)
    return None


def _coord_to_notation(coord: Tuple[int, int]) -> str:
    """
    Convertit des coordonnées internes (4, 4) en notation utilisateur ('e5').
    
    C'est la fonction inverse de _parse_coord.
    
    CALCUL :
    --------
    - Colonne 4 → chr(ord('a') + 4) = chr(101) = 'e'
    - Ligne 4 → 4 + 1 = 5
    → Résultat : 'e5'
    
    Args:
        coord: Tuple (ligne, colonne)
    
    Returns:
        Notation échecs (ex: 'e5')
    """
    return f"{chr(ord('a') + coord[1])}{coord[0] + 1}"


# =============================================================================
# FONCTIONS D'AFFICHAGE
# =============================================================================

def clear_screen():
    """
    Efface l'écran du terminal pour un affichage propre.
    
    Utilise la commande système appropriée selon le système d'exploitation :
    - Windows : 'cls'
    - Linux/Mac : 'clear'
    """
    os.system('cls' if os.name == 'nt' else 'clear')


def print_help():
    """
    Affiche l'aide des commandes disponibles.
    
    Cette fonction est appelée quand l'utilisateur tape 'help' ou 'h'.
    """
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
    Affiche le plateau de jeu dans la console avec les pions et les murs.
    
    TECHNIQUE D'AFFICHAGE :
    -----------------------
    Le plateau de jeu 6x6 est affiché sur une grille 11x11 caractères.
    Pourquoi ? Car on doit afficher les cases ET les espaces entre elles (pour les murs).
    
    Correspondance :
    - Case (0,0) → position (0,0) dans la grille
    - Case (0,1) → position (0,2) dans la grille
    - Case (1,0) → position (2,0) dans la grille
    
    Formule : case (r, c) → grille (r*2, c*2)
    
    Les positions impaires de la grille sont réservées aux murs :
    - Lignes impaires : espaces pour murs horizontaux
    - Colonnes impaires : espaces pour murs verticaux
    
    CARACTÈRES UTILISÉS :
    ---------------------
    - '·' : Case vide
    - '1' : Pion du joueur 1 (bleu)
    - '2' : Pion du joueur 2 (rouge)
    - '━' : Mur horizontal
    - '┃' : Mur vertical
    
    Args:
        game: Instance de QuoridorGame contenant l'état actuel
        ai_mode: True si on joue contre l'IA (pour adapter l'affichage)
    """
    state = game.get_current_state()
    
    # ═══════════════════════════════════════════════════════════════════════
    # ÉTAPE 1 : Créer une grille de caractères vide
    # ═══════════════════════════════════════════════════════════════════════
    # Taille : 6 cases * 2 - 1 = 11 caractères par dimension
    grid_size = BOARD_SIZE * 2 - 1
    grid = [[' ' for _ in range(grid_size)] for _ in range(grid_size)]

    # ═══════════════════════════════════════════════════════════════════════
    # ÉTAPE 2 : Placer les points pour représenter les cases vides
    # ═══════════════════════════════════════════════════════════════════════
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            # Chaque case est à une position paire dans la grille
            grid[r * 2][c * 2] = '·'

    # ═══════════════════════════════════════════════════════════════════════
    # ÉTAPE 3 : Dessiner les murs
    # ═══════════════════════════════════════════════════════════════════════
    for wall in state.walls:
        orientation, r, c, _ = wall
        
        if orientation == 'h':
            # Mur HORIZONTAL : occupe 3 caractères sur une ligne impaire
            # Position : entre les lignes r et r+1, colonnes c et c+1
            #
            # Exemple : mur ('h', 2, 3, 2)
            # → Dessiner sur la ligne 2*2+1 = 5 de la grille
            # → Colonnes 3*2, 3*2+1, 3*2+2 = 6, 7, 8
            grid[r * 2 + 1][c * 2] = '━'
            grid[r * 2 + 1][c * 2 + 1] = '━'
            grid[r * 2 + 1][c * 2 + 2] = '━'
            
        else:  # 'v' - Mur VERTICAL
            # Mur VERTICAL : occupe 3 caractères sur une colonne impaire
            # Position : entre les colonnes c et c+1, lignes r et r+1
            grid[r * 2][c * 2 + 1] = '┃'
            grid[r * 2 + 1][c * 2 + 1] = '┃'
            grid[r * 2 + 2][c * 2 + 1] = '┃'

    # ═══════════════════════════════════════════════════════════════════════
    # ÉTAPE 4 : Placer les pions des joueurs (avec couleurs si disponibles)
    # ═══════════════════════════════════════════════════════════════════════
    pos_j1 = state.player_positions[PLAYER_ONE]
    grid[pos_j1[0] * 2][pos_j1[1] * 2] = f'{Fore.BLUE}1{Style.RESET_ALL}' if COLORS_ENABLED else '1'
    
    pos_j2 = state.player_positions[PLAYER_TWO]
    grid[pos_j2[0] * 2][pos_j2[1] * 2] = f'{Fore.RED}2{Style.RESET_ALL}' if COLORS_ENABLED else '2'

    # ═══════════════════════════════════════════════════════════════════════
    # ÉTAPE 5 : Afficher la grille complète
    # ═══════════════════════════════════════════════════════════════════════
    clear_screen()
    
    # En-tête décoratif
    print(f"\n{Fore.GREEN}{'=' * 40}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}   🎮  QUORIDOR - Partie en cours  🎮{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'=' * 40}{Style.RESET_ALL}\n")
    
    # Légende des colonnes (a à f)
    print("   a b c d e f")
    print("  " + "━" * (grid_size))
    
    # Afficher chaque ligne de la grille
    for i, row in enumerate(grid):
        if i % 2 == 0:
            # Ligne paire = ligne avec des cases → afficher le numéro de ligne
            print(f"{i // 2 + 1}┃{''.join(row)}┃")
        else:
            # Ligne impaire = espace pour les murs horizontaux
            print(f" ┃{''.join(row)}┃")
    print("  " + "━" * (grid_size))
    
    # ═══════════════════════════════════════════════════════════════════════
    # ÉTAPE 6 : Afficher les informations des joueurs
    # ═══════════════════════════════════════════════════════════════════════
    j1_color = f'{Fore.BLUE}Joueur 1{Style.RESET_ALL}' if COLORS_ENABLED else 'Joueur 1'
    
    # Adapter l'affichage selon le mode (PvP ou PvIA)
    if ai_mode:
        j2_color = f'{Fore.RED}IA{Style.RESET_ALL}' if COLORS_ENABLED else 'IA'
    else:
        j2_color = f'{Fore.RED}Joueur 2{Style.RESET_ALL}' if COLORS_ENABLED else 'Joueur 2'
    
    print(f"\n  Murs restants: {j1_color} [{state.player_walls[PLAYER_ONE]}]   {j2_color} [{state.player_walls[PLAYER_TWO]}]")
    print(f"  Tapez '{Fore.YELLOW}help{Style.RESET_ALL}' pour voir les commandes disponibles")
    print("-" * 40)


def prompt_for_move(game: QuoridorGame) -> Optional[Move]:
    """
    Demande un coup au joueur et parse sa commande.
    
    Cette fonction implémente la BOUCLE DE SAISIE : elle continue à demander
    une commande jusqu'à ce que le joueur entre un coup valide (ou quitte).
    
    PATTERN READ-EVAL-LOOP :
    ------------------------
    1. READ : Lire la commande de l'utilisateur
    2. EVAL : Parser et valider la commande
    3. LOOP : Si invalide, afficher une erreur et recommencer
    
    COMMANDES RECONNUES :
    ---------------------
    - 'd <case>' : Déplacement (ex: 'd e5')
    - 'm <h|v> <case>' : Placement de mur (ex: 'm h e3')
    - 'undo' : Annuler le dernier coup
    - 'moves' ou '?' : Afficher les coups possibles
    - 'help' ou 'h' : Afficher l'aide
    - 'quit' ou 'q' : Quitter la partie
    
    Args:
        game: Instance de QuoridorGame
    
    Returns:
        - Tuple Move pour un déplacement ou mur
        - ('undo', None) pour annuler
        - None pour quitter la partie
    """
    player = game.get_current_player()
    player_num = player[-1]  # Extraire '1' ou '2' de 'j1' ou 'j2'
    player_color = Fore.BLUE if player == PLAYER_ONE else Fore.RED
    
    # ═══════════════════════════════════════════════════════════════════════
    # BOUCLE DE SAISIE : Continue jusqu'à obtenir un coup valide
    # ═══════════════════════════════════════════════════════════════════════
    while True:
        prompt_text = f"{player_color}Tour du Joueur {player_num}{Style.RESET_ALL}. Entrez votre coup: "
        action = input(prompt_text).strip().lower()
        parts = action.split()  # Découper la commande en mots
        
        # Ignorer les entrées vides
        if not parts:
            continue

        # ═══════════════════════════════════════════════════════════════════
        # COMMANDE : UNDO (annuler le dernier coup)
        # ═══════════════════════════════════════════════════════════════════
        if parts[0] == 'undo':
            return ('undo', None)  # Signal spécial pour annuler
        
        # ═══════════════════════════════════════════════════════════════════
        # COMMANDE : QUIT (quitter la partie)
        # ═══════════════════════════════════════════════════════════════════
        if parts[0] == 'quit' or parts[0] == 'q':
            # Demander confirmation pour éviter les quitter accidentels
            confirm = input(f"{Fore.YELLOW}Êtes-vous sûr de vouloir quitter ? (o/n): {Style.RESET_ALL}").strip().lower()
            if confirm in ['o', 'oui', 'y', 'yes']:
                return None  # Signal pour quitter
            continue  # Annulé, redemander un coup
        
        # ═══════════════════════════════════════════════════════════════════
        # COMMANDE : HELP (afficher l'aide)
        # ═══════════════════════════════════════════════════════════════════
        if parts[0] == 'help' or parts[0] == 'h':
            print_help()
            continue  # Redemander un coup après l'aide
        
        # ═══════════════════════════════════════════════════════════════════
        # COMMANDE : MOVES (afficher les coups possibles)
        # ═══════════════════════════════════════════════════════════════════
        if parts[0] == 'moves' or parts[0] == '?':
            possible_moves = game.get_possible_moves()
            if possible_moves:
                # Convertir les coordonnées en notation utilisateur
                coords = [_coord_to_notation(move[1]) for move in possible_moves if move[0] == 'deplacement']
                print(f"{Fore.GREEN}Coups possibles : {', '.join(coords)}{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}Aucun coup disponible.{Style.RESET_ALL}")
            input("Appuyez sur Entrée pour continuer...")
            continue

        # ═══════════════════════════════════════════════════════════════════
        # PARSING DES COMMANDES DE JEU (d ou m)
        # ═══════════════════════════════════════════════════════════════════
        if len(parts) < 2:
            print(f"{Fore.RED}Commande invalide. Format: 'd <case>' ou 'm <h|v> <case>'{Style.RESET_ALL}")
            continue
            
        move_type_str, move_data_str = parts[0], parts[1:]
        
        # ───────────────────────────────────────────────────────────────────
        #     COMMANDE : DÉPLACEMENT ('d <case>')
        # Exemple : 'd d3' → se déplacer vers la case d3
        # ───────────────────────────────────────────────────────────────────
        if move_type_str == 'd' and len(move_data_str) == 1:
            coord = _parse_coord(move_data_str[0])
            if coord:
                return ('deplacement', coord)
            else:
                print(f"{Fore.RED}Coordonnée invalide: '{move_data_str[0]}'. Utilisez 'a1' à 'f6'.{Style.RESET_ALL}")
        
        # ───────────────────────────────────────────────────────────────────
        # COMMANDE : MUR ('m <h|v> <case>')
        # Exemple : 'm h e3' → mur horizontal en e3
        # ───────────────────────────────────────────────────────────────────
        elif move_type_str == 'm' and len(move_data_str) == 2:
            orientation, coord_str = move_data_str[0], move_data_str[1]
            
            # Valider l'orientation
            if orientation not in ['h', 'v']:
                print(f"{Fore.RED}Orientation de mur invalide: '{orientation}'. Utilisez 'h' ou 'v'.{Style.RESET_ALL}")
                continue
            
            # Parser la coordonnée
            coord = _parse_coord(coord_str)
            if coord:
                # Construire le tuple mur : (orientation, ligne, colonne, longueur)
                # La longueur est toujours 2 (un mur couvre 2 cases)
                return ('mur', (orientation, coord[0], coord[1], 2))
            else:
                print(f"{Fore.RED}Coordonnée invalide: '{coord_str}'.{Style.RESET_ALL}")
        
        # ───────────────────────────────────────────────────────────────────
        # COMMANDE NON RECONNUE
        # ───────────────────────────────────────────────────────────────────
        else:
            print(f"{Fore.RED}Commande invalide. Format: 'd <case>' ou 'm <h|v> <case>'{Style.RESET_ALL}")


def select_game_mode() -> Tuple[str, Optional[AI]]:
    """
    Affiche le menu de sélection du mode de jeu et retourne le choix.
    
    MODES DISPONIBLES :
    -------------------
    1. PvP (Player vs Player) : Deux joueurs humains
    2. PvIA (Player vs IA) : Un joueur humain contre l'ordinateur
    
    Si le mode IA est choisi, l'utilisateur peut aussi sélectionner
    le niveau de difficulté.
    
    Returns:
        Tuple (mode, ia) où :
        - mode = 'pvp' ou 'pvia'
        - ia = instance de la classe AI, ou None en mode PvP
    """
    clear_screen()
    
    # Afficher le menu principal
    print(f"\n{Fore.GREEN}{'=' * 40}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}  QUORIDOR - Sélection du mode{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'=' * 40}{Style.RESET_ALL}\n")
    print(f"  {Fore.YELLOW}1{Style.RESET_ALL} - Joueur vs Joueur")
    print(f"  {Fore.YELLOW}2{Style.RESET_ALL} - Joueur vs IA\n")
    
    while True:
        choice = input(f"Choisissez un mode (1 ou 2): ").strip()
        
        # ───────────────────────────────────────────────────────────────────
        # MODE 1 : Joueur vs Joueur
        # ───────────────────────────────────────────────────────────────────
        if choice == '1':
            return 'pvp', None  # Pas d'IA en mode PvP
        
        # ───────────────────────────────────────────────────────────────────
        # MODE 2 : Joueur vs IA (avec sélection de difficulté)
        # ───────────────────────────────────────────────────────────────────
        elif choice == '2':
            # Sous-menu pour la difficulté
            print(f"\n{Fore.GREEN}Niveau de difficulté :{Style.RESET_ALL}")
            print(f"  {Fore.YELLOW}1{Style.RESET_ALL} - Facile (rapide)")
            print(f"  {Fore.YELLOW}2{Style.RESET_ALL} - Normal (équilibré)")
            print(f"  {Fore.YELLOW}3{Style.RESET_ALL} - Difficile (lent mais fort)\n")
            
            while True:
                diff_choice = input(f"Choisissez la difficulté (1, 2 ou 3): ").strip()
                
                if diff_choice == '1':
                    # IA facile : profondeur 2, réponse rapide
                    ia = AI(PLAYER_TWO, difficulty='facile')
                    return 'pvia', ia
                elif diff_choice == '2':
                    # IA normale : profondeur 4, bon équilibre
                    ia = AI(PLAYER_TWO, difficulty='normal')
                    return 'pvia', ia
                elif diff_choice == '3':
                    # IA difficile : profondeur 5, plus lente mais redoutable
                    ia = AI(PLAYER_TWO, difficulty='difficile')
                    return 'pvia', ia
                else:
                    print(f"{Fore.RED}Choix invalide. Entrez 1, 2 ou 3.{Style.RESET_ALL}")
        
        else:
            print(f"{Fore.RED}Choix invalide. Entrez 1 ou 2.{Style.RESET_ALL}")


def display_ai_move(move: Move, thinking_time: float):
    """
    Affiche le coup joué par l'IA de manière lisible.
    
    Cette fonction traduit le coup interne de l'IA en message
    compréhensible pour l'utilisateur.
    
    Args:
        move: Le coup joué au format Move
        thinking_time: Temps de réflexion de l'IA en secondes
    """
    move_type, move_data = move
    
    if move_type == 'deplacement':
        # Convertir les coordonnées en notation utilisateur
        coord_notation = _coord_to_notation(move_data)
        print(f"\n{Fore.RED}🤖 L'IA se déplace en {Fore.YELLOW}{coord_notation}{Style.RESET_ALL}")
    else:  # 'mur'
        orientation, r, c, _ = move_data
        coord_notation = _coord_to_notation((r, c))
        orientation_str = "horizontal" if orientation == 'h' else "vertical"
        print(f"\n{Fore.RED}🤖 L'IA place un mur {orientation_str} en {Fore.YELLOW}{coord_notation}{Style.RESET_ALL}")
    
    # Afficher le temps de réflexion (intéressant pour voir la difficulté)
    print(f"   {Fore.GREEN}(Temps de réflexion: {thinking_time:.1f}s){Style.RESET_ALL}")


# =============================================================================
# FONCTION PRINCIPALE : Boucle de jeu
# =============================================================================

def main():
    """
    FONCTION PRINCIPALE - Lance et gère une partie complète de Quoridor.
    
    STRUCTURE DE LA FONCTION :
    --------------------------
    1. INITIALISATION
       - Sélection du mode de jeu (PvP ou PvIA)
       - Affichage des règles et instructions
       - Création de l'objet QuoridorGame
    
    2. BOUCLE DE JEU PRINCIPALE
       Tant que la partie n'est pas terminée :
       - Afficher le plateau
       - Si c'est le tour de l'IA : calculer et jouer son coup
       - Si c'est le tour d'un humain : demander et jouer son coup
       - Gérer les commandes spéciales (undo, quit)
    
    3. FIN DE PARTIE
       - Afficher le plateau final
       - Annoncer le gagnant
    
    GESTION DES ERREURS :
    ---------------------
    - KeyboardInterrupt (Ctrl+C) : Quitter proprement
    - InvalidMoveError : Coup invalide, redemander
    - Exception générale : Afficher l'erreur et quitter
    """
    try:
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 1 : INITIALISATION
        # ═══════════════════════════════════════════════════════════════════
        
        # Sélection du mode de jeu via le menu
        mode, ia = select_game_mode()
        
        # Afficher l'écran de bienvenue avec les règles
        clear_screen()
        print(f"\n{Fore.GREEN}{'=' * 40}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}  Bienvenue dans QUORIDOR !{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{'=' * 40}{Style.RESET_ALL}\n")
        
        # Afficher le mode sélectionné
        if mode == 'pvp':
            print(f"  {Fore.CYAN}Mode : Joueur vs Joueur{Style.RESET_ALL}")
        else:
            print(f"  {Fore.CYAN}Mode : Joueur vs IA{Style.RESET_ALL}")
        
        # Rappel des positions de départ
        print(f"\n  {Fore.BLUE}Joueur 1{Style.RESET_ALL} (Vous) commence en bas (ligne 6)")
        
        if mode == 'pvia':
            print(f"  {Fore.RED}IA{Style.RESET_ALL} joue en haut (ligne 1)")
        else:
            print(f"  {Fore.RED}Joueur 2{Style.RESET_ALL} commence en haut (ligne 1)")
        
        # Rappel des objectifs
        print(f"\n  Objectif : {Fore.BLUE}Joueur 1{Style.RESET_ALL} → atteindre la ligne 1 (monter)")
        
        if mode == 'pvia':
            print(f"            {Fore.RED}IA{Style.RESET_ALL} → atteindre la ligne 6 (descendre)")
        else:
            print(f"            {Fore.RED}Joueur 2{Style.RESET_ALL} → atteindre la ligne 6 (descendre)")
        
        print(f"\n  Tapez '{Fore.YELLOW}help{Style.RESET_ALL}' à tout moment pour voir les commandes\n")
        input("Appuyez sur Entrée pour commencer...")
        
        # Créer une nouvelle partie
        partie = QuoridorGame()
        
        # ═══════════════════════════════════════════════════════════════════
        # PHASE 2 : BOUCLE DE JEU PRINCIPALE
        # ═══════════════════════════════════════════════════════════════════
        # Cette boucle continue tant que personne n'a gagné
        
        while not partie.is_game_over()[0]:
            # Afficher l'état actuel du plateau
            display_board(partie, ai_mode=(mode == 'pvia'))
            
            # ───────────────────────────────────────────────────────────────
            # CAS 1 : Tour de l'IA
            # ───────────────────────────────────────────────────────────────
            if mode == 'pvia' and partie.get_current_player() == PLAYER_TWO:
                print(f"\n{Fore.RED}🤖 L'IA réfléchit...{Style.RESET_ALL}")
                
                # Mesurer le temps de réflexion (intéressant à afficher)
                start_time = time.time()
                ai_move = ia.find_best_move(partie.get_current_state(), verbose=False)
                thinking_time = time.time() - start_time
                
                # Afficher le coup choisi par l'IA
                display_ai_move(ai_move, thinking_time)
                
                # Jouer le coup de l'IA
                try:
                    partie.play_move(ai_move)
                except InvalidMoveError as e:
                    # Cela ne devrait JAMAIS arriver si l'IA est bien codée
                    print(f"\n{Fore.RED}!!! ERREUR IA: {e} !!!{Style.RESET_ALL}")
                    print("L'IA a fait un coup invalide (cela ne devrait pas arriver).")
                    break
                
                input("Appuyez sur Entrée pour continuer...")
                continue  # Passer au tour suivant
            
            # ───────────────────────────────────────────────────────────────
            # CAS 2 : Tour du joueur humain
            # ───────────────────────────────────────────────────────────────
            move = prompt_for_move(partie)
            
            # Gestion de la commande QUIT
            if move is None:
                print(f"\n{Fore.YELLOW}Partie abandonnée. Au revoir !{Style.RESET_ALL}\n")
                break
            
            # Gestion de la commande UNDO
            if move[0] == 'undo':
                if mode == 'pvia':
                    # En mode IA, il faut annuler 2 coups pour revenir à son tour
                    # (notre coup + le coup de l'IA)
                    if partie.undo_move() and partie.undo_move():
                        print(f"{Fore.GREEN}✓ Vos 2 derniers coups annulés{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}Impossible d'annuler, pas assez de coups dans l'historique.{Style.RESET_ALL}")
                else:
                    # En mode PvP, annuler seulement 1 coup
                    if partie.undo_move():
                        print(f"{Fore.GREEN}✓ Coup annulé{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}Impossible d'annuler, aucun coup dans l'historique.{Style.RESET_ALL}")
                input("Appuyez sur Entrée pour continuer...")
                continue
            
            # ───────────────────────────────────────────────────────────────
            # Jouer le coup du joueur
            # ───────────────────────────────────────────────────────────────
            try:
                partie.play_move(move)
            except InvalidMoveError as e:
                # Le coup est invalide : afficher l'erreur et redemander
                print(f"\n{Fore.RED}!!! COUP INVALIDE: {e} !!!{Style.RESET_ALL}")
                input("Appuyez sur Entrée pour continuer...")
                # La boucle va recommencer et redemander un coup

        # ═══════════════════════════════════════════════════════════════════
        # PHASE 3 : FIN DE PARTIE
        # ═══════════════════════════════════════════════════════════════════
        # On arrive ici si quelqu'un a gagné (pas si abandon)
        
        if partie.is_game_over()[0]:
            # Afficher le plateau final
            display_board(partie, ai_mode=(mode == 'pvia'))
            
            # Déterminer et afficher le gagnant
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
                winner_num = winner[-1]  # Extraire '1' ou '2' de 'j1' ou 'j2'
                print(f"{winner_color}  Victoire du Joueur {winner_num} !{Style.RESET_ALL}")
            
            print(f"{Fore.GREEN}{'=' * 40}{Style.RESET_ALL}\n")
    
    # ═══════════════════════════════════════════════════════════════════════
    # GESTION DES ERREURS
    # ═══════════════════════════════════════════════════════════════════════
    
    except KeyboardInterrupt:
        # L'utilisateur a appuyé sur Ctrl+C
        print(f"\n\n{Fore.YELLOW}Partie interrompue. Au revoir !{Style.RESET_ALL}\n")
    
    except Exception as e:
        # Erreur inattendue : afficher les détails pour le débogage
        print(f"\n{Fore.RED}!!! ERREUR CRITIQUE: {e} !!!{Style.RESET_ALL}\n")
        import traceback
        traceback.print_exc()


# =============================================================================
# POINT D'ENTRÉE DU PROGRAMME
# =============================================================================
# Ce bloc s'exécute uniquement si le fichier est lancé directement
# (pas s'il est importé comme module)

if __name__ == '__main__':
    main()

