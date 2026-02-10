# 🖥️ Gestion et Affichage du Plateau

Ce diagramme explique comment l'état du jeu est structuré, stocké, et affiché dans le terminal.

---

## Structure de Données : GameState

```mermaid
flowchart TD
    GS(["GameState<br/>(immuable)"]) --> POS["player_positions<br/>{'j1': (8,4), 'j2': (0,4)}"]
    GS --> WALLS["walls<br/>frozenset de murs posés<br/>ex: ('h', 3, 4, 2)"]
    GS --> PW["player_walls<br/>{'j1': 10, 'j2': 10}<br/>murs restants"]
    GS --> CP["current_player<br/>'j1' ou 'j2'"]

    subgraph "Représentation d'un Mur"
        WALL_DEF["(orientation, ligne, colonne, longueur)"]
        WALL_H["'h' → Horizontal ━━━"]
        WALL_V["'v' → Vertical ┃"]
        WALL_DEF --> WALL_H
        WALL_DEF --> WALL_V
    end

    WALLS -.-> WALL_DEF

    subgraph "Coordonnées"
        COORD_DEF["(ligne, colonne)<br/>0-indexé"]
        COORD_EX["(0,0) = a1 coin haut-gauche<br/>(4,4) = e5 centre<br/>(8,8) = i9 coin bas-droite"]
        COORD_DEF --> COORD_EX
    end

    POS -.-> COORD_DEF

    style GS fill:#2196F3,color:#fff
    style POS fill:#42A5F5,color:#fff
    style WALLS fill:#FFA726,color:#fff
    style PW fill:#66BB6A,color:#fff
    style CP fill:#AB47BC,color:#fff
```

---

## Gestion de l'Historique (Undo)

```mermaid
flowchart LR
    subgraph "QuoridorGame"
        HISTORY["_history : List"]
        CURRENT["_current_state"]
    end

    subgraph "play_move()"
        direction TB
        SAVE["1. Sauvegarder état<br/>actuel dans _history"]
        PLAY["2. Créer nouvel état<br/>(immuable)"]
        UPDATE["3. _current_state =<br/>nouvel état"]
        SAVE --> PLAY --> UPDATE
    end

    subgraph "undo_move()"
        direction TB
        POP["1. Récupérer dernier<br/>état de _history"]
        RESTORE["2. _current_state =<br/>état précédent"]
        POP --> RESTORE
    end

    HISTORY --> POP
    CURRENT --> SAVE
```

---

## Conversion Coordonnées

```mermaid
flowchart LR
    subgraph "Notation Utilisateur"
        USER_N["'e5'<br/>lettre + chiffre"]
    end

    subgraph "_parse_coord()"
        PARSE_COL["col = ord('e') - ord('a') = 4"]
        PARSE_ROW["row = 5 - 1 = 4"]
    end

    subgraph "Coordonnées Internes"
        INTERNAL["(4, 4)<br/>(ligne, colonne)"]
    end

    subgraph "_coord_to_notation()"
        BACK_COL["chr(ord('a') + 4) = 'e'"]
        BACK_ROW["4 + 1 = 5"]
    end

    USER_N -->|"_parse_coord()"| PARSE_COL
    PARSE_COL --> INTERNAL
    PARSE_ROW --> INTERNAL
    INTERNAL -->|"_coord_to_notation()"| BACK_COL
    BACK_COL --> USER_N
    BACK_ROW --> USER_N
```

---

## Processus d'Affichage du Plateau

```mermaid
flowchart TD
    START(["display_board(game)"]) --> STATE["Récupérer l'état<br/>game.get_current_state()"]

    STATE --> STEP1

    subgraph "Étape 1 : Grille Vide"
        STEP1["Créer grille 17×17<br/>(9 cases × 2 - 1)"]
    end

    STEP1 --> STEP2

    subgraph "Étape 2 : Cases"
        STEP2["Placer '·' sur chaque case<br/>position (r×2, c×2)"]
    end

    STEP2 --> STEP3

    subgraph "Étape 3 : Murs"
        STEP3{"Pour chaque mur<br/>dans state.walls"}
        STEP3 --> H_WALL["Horizontal :<br/>3× '━' sur ligne impaire"]
        STEP3 --> V_WALL["Vertical :<br/>3× '┃' sur colonne impaire"]
    end

    H_WALL --> STEP4
    V_WALL --> STEP4

    subgraph "Étape 4 : Pions"
        STEP4["Placer '1' (bleu) en J1<br/>Placer '2' (rouge) en J2"]
    end

    STEP4 --> STEP5

    subgraph "Étape 5 : Rendu"
        STEP5["Effacer l'écran<br/>clear_screen()"]
        STEP5 --> HEADER["Titre + en-tête colonnes<br/>a b c d e f g h i"]
        HEADER --> ROWS["Afficher chaque ligne :<br/>• Paire → numéro + cases<br/>• Impaire → espaces murs"]
        ROWS --> INFO["Murs restants + aide"]
    end

    INFO --> DONE(["✅ Affichage terminé"])

    style START fill:#2196F3,color:#fff
    style DONE fill:#4CAF50,color:#fff
```

---

## Correspondance Grille 9×9 → Grille 17×17

```mermaid
flowchart LR
    subgraph "Plateau logique 9×9"
        L1["Case (0,0)"]
        L2["Case (0,1)"]
        L3["Case (1,0)"]
    end

    subgraph "Grille d'affichage 17×17"
        G1["Position (0,0) → '·'"]
        G2["Position (0,2) → '·'"]
        G3["Position (2,0) → '·'"]
        G12["Position (0,1) → mur vertical ?"]
        G13["Position (1,0) → mur horizontal ?"]
    end

    L1 -->|"r×2, c×2"| G1
    L2 -->|"r×2, c×2"| G2
    L3 -->|"r×2, c×2"| G3
    L1 -.->|"entre cases"| G12
    L1 -.->|"entre cases"| G13

    style G12 fill:#FFA726,color:#fff
    style G13 fill:#FFA726,color:#fff
```

---

> **Principe clé :** La grille 17×17 intercale les cases (positions paires) et les espaces pour murs (positions impaires), permettant un rendu ASCII élégant avec murs visibles.
