# 🖥️ Gestion et Affichage du Plateau

Ce diagramme explique comment l'état du jeu est structuré, stocké et affiché dans le terminal.

---

## Structure de l'État du Jeu

Toutes les informations d'une partie sont regroupées dans un **état de jeu** immuable (non modifiable une fois créé).

```mermaid
flowchart TD
    GS(["État du Jeu<br/>(immuable)"]) --> POS["Position des pions<br/>Joueur 1 : case de départ en bas<br/>Joueur 2 : case de départ en haut"]
    GS --> WALLS["Murs posés<br/>Liste de tous les murs<br/>présents sur le plateau"]
    GS --> PW["Murs restants<br/>Chaque joueur commence<br/>avec 6 murs"]
    GS --> CP["Tour actuel<br/>Quel joueur doit jouer"]

    subgraph "Représentation d'un Mur"
        WALL_DEF["Chaque mur est défini par :<br/>orientation + position"]
        WALL_H["Horizontal ━━━<br/>bloque les déplacements verticaux"]
        WALL_V["Vertical ┃<br/>bloque les déplacements horizontaux"]
        WALL_DEF --> WALL_H
        WALL_DEF --> WALL_V
    end

    WALLS -.-> WALL_DEF

    subgraph "Système de Coordonnées"
        COORD_DEF["Chaque case a une<br/>position (ligne, colonne)"]
        COORD_EX["Exemples :<br/>a1 = coin haut-gauche<br/>d3 = centre du plateau<br/>f6 = coin bas-droite"]
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

## Gestion de l'Historique (Annuler un coup)

Le jeu conserve un historique de tous les états précédents, ce qui permet d'annuler des coups.

```mermaid
flowchart LR
    subgraph "Mémoire du Jeu"
        HISTORY["Historique<br/>(pile d'états passés)"]
        CURRENT["État actuel"]
    end

    subgraph "Quand on joue un coup"
        direction TB
        SAVE["1. Sauvegarder l'état<br/>actuel dans l'historique"]
        PLAY["2. Créer un nouvel état<br/>avec le coup appliqué"]
        UPDATE["3. Le nouvel état<br/>devient l'état actuel"]
        SAVE --> PLAY --> UPDATE
    end

    subgraph "Quand on annule"
        direction TB
        POP["1. Récupérer le dernier<br/>état de l'historique"]
        RESTORE["2. Cet état redevient<br/>l'état actuel"]
        POP --> RESTORE
    end

    HISTORY --> POP
    CURRENT --> SAVE
```

---

## Conversion des Coordonnées

Le joueur utilise une notation intuitive (type échecs), que le programme convertit en coordonnées internes.

```mermaid
flowchart LR
    subgraph "Ce que tape le joueur"
        USER_N["'e5'<br/>lettre (colonne) + chiffre (ligne)"]
    end

    subgraph "Conversion → Interne"
        PARSE_COL["Colonne : e → 5ème colonne"]
        PARSE_ROW["Ligne : 5 → 5ème ligne"]
    end

    subgraph "Ce que le programme utilise"
        INTERNAL["(4, 4)<br/>indices à partir de 0"]
    end

    subgraph "Conversion → Affichage"
        BACK_COL["5ème colonne → e"]
        BACK_ROW["5ème ligne → 5"]
    end

    USER_N -->|"Saisie joueur"| PARSE_COL
    PARSE_COL --> INTERNAL
    PARSE_ROW --> INTERNAL
    INTERNAL -->|"Affichage"| BACK_COL
    BACK_COL --> USER_N
    BACK_ROW --> USER_N
```

---

## Comment le Plateau est Affiché

Le plateau de 6×6 cases est converti en une grille de 11×11 caractères pour pouvoir dessiner les murs entre les cases.

```mermaid
flowchart TD
    START(["Afficher le plateau"]) --> STATE["Récupérer l'état<br/>actuel du jeu"]

    STATE --> STEP1

    subgraph "Étape 1 : Créer la grille vide"
        STEP1["Grille de 11×11 espaces<br/>(6 cases × 2 - 1 = 11)"]
    end

    STEP1 --> STEP2

    subgraph "Étape 2 : Placer les cases"
        STEP2["Dessiner '·' pour<br/>chaque case du plateau"]
    end

    STEP2 --> STEP3

    subgraph "Étape 3 : Dessiner les murs"
        STEP3{"Pour chaque<br/>mur posé"}
        STEP3 --> H_WALL["Mur horizontal → '━━━'<br/>sur une ligne entre deux rangées"]
        STEP3 --> V_WALL["Mur vertical → '┃' × 3<br/>sur une colonne entre deux colonnes"]
    end

    H_WALL --> STEP4
    V_WALL --> STEP4

    subgraph "Étape 4 : Placer les pions"
        STEP4["Joueur 1 → '1' en bleu<br/>Joueur 2 → '2' en rouge"]
    end

    STEP4 --> STEP5

    subgraph "Étape 5 : Afficher le résultat"
        STEP5["Effacer l'écran"]
        STEP5 -->         HEADER["Dessiner le titre du jeu<br/>+ légende des colonnes (a-f)"]
        HEADER --> ROWS["Afficher ligne par ligne :<br/>• Lignes avec cases (numérotées 1-6)<br/>• Lignes avec murs (entre les cases)"]
        ROWS --> INFO["Afficher les murs restants<br/>de chaque joueur"]
    end

    INFO --> DONE(["✅ Plateau affiché"])

    style START fill:#2196F3,color:#fff
    style DONE fill:#4CAF50,color:#fff
```

---

## Pourquoi 11×11 au lieu de 6×6 ?

```mermaid
flowchart LR
    subgraph "Plateau logique (6×6)"
        L1["Case A"]
        L2["Case B (à droite)"]
        L3["Case C (en dessous)"]
    end

    subgraph "Grille d'affichage (11×11)"
        G1["Position 0 → Case A"]
        G12["Position 1 → Espace mur ?"]
        G2["Position 2 → Case B"]
        G13["Position 3 → Espace mur ?"]
        G3["Position 4 → Case C"]
    end

    L1 -->|"× 2"| G1
    L2 -->|"× 2"| G2
    L3 -->|"× 2"| G3
    L1 -.->|"entre les cases"| G12
    L1 -.->|"entre les cases"| G13

    style G12 fill:#FFA726,color:#fff
    style G13 fill:#FFA726,color:#fff
```

> Les positions **paires** contiennent les cases, les positions **impaires** sont réservées aux murs. C'est ce qui permet d'afficher les murs entre les cases.

---

> **Principe clé :** La grille 11×11 intercale les cases et les espaces pour murs, permettant un rendu ASCII élégant où chaque mur est visible entre les cases qu'il bloque.
