# 🤖 Logique de l'Intelligence Artificielle

Ce diagramme détaille comment l'IA du Quoridor réfléchit et choisit son coup. Elle utilise l'algorithme **Minimax avec élagage Alpha-Bêta**.

---

## Comment l'IA choisit son coup

```mermaid
flowchart TD
    ENTRY(["C'est au tour de l'IA"]) --> RESET["Préparer la réflexion<br/>(vider la mémoire)"]
    RESET --> GEN["Lister tous les coups<br/>possibles (déplacements + murs)"]
    GEN --> SORT["Trier les coups :<br/>les plus prometteurs en premier"]

    SORT --> LOOP["Prendre un coup"]
    LOOP --> SIM["Imaginer le jeu<br/>après ce coup"]
    SIM --> MINIMAX["Simuler les tours suivants<br/>pour prédire le résultat"]

    MINIMAX --> COMPARE{"Ce coup est<br/>meilleur que<br/>les précédents ?"}
    COMPARE -->|"Oui"| NEW_BEST["Retenir ce coup<br/>comme le meilleur"]
    COMPARE -->|"Aussi bon"| ADD["L'ajouter à la liste<br/>des meilleurs"]
    COMPARE -->|"Non"| NEXT

    NEW_BEST --> NEXT["Passer au<br/>coup suivant"]
    ADD --> NEXT
    NEXT --> MORE{"Encore des<br/>coups à<br/>évaluer ?"}
    MORE -->|Oui| LOOP
    MORE -->|Non| CHOOSE

    CHOOSE["🎲 Choisir aléatoirement<br/>parmi les meilleurs coups<br/>(pour varier le jeu)"] --> RETURN(["Jouer le coup choisi"])

    style ENTRY fill:#E91E63,color:#fff
    style RETURN fill:#4CAF50,color:#fff
    style MINIMAX fill:#9C27B0,color:#fff
```

---

## Simulation des tours futurs (Minimax)

L'IA imagine les coups futurs en alternant entre **son point de vue** (maximiser son avantage) et celui de **l'adversaire** (minimiser l'avantage de l'IA).

```mermaid
flowchart TD
    START(["Simuler les tours futurs"]) --> NODES["Compter les positions explorées"]

    NODES --> CACHE{"Position déjà<br/>analysée<br/>en mémoire ?"}
    CACHE -->|"Oui"| CACHE_HIT(["↩ Réutiliser le<br/>résultat mémorisé"])
    CACHE -->|"Non"| LEAF

    LEAF{"Fin de la<br/>simulation ?<br/>(profondeur max<br/>ou victoire)"}
    LEAF -->|Oui| EVAL["Évaluer la position :<br/>qui a l'avantage ?"]
    EVAL --> STORE_EVAL["Mémoriser le résultat"] --> RETURN_EVAL(["↩ Retourner le score"])

    LEAF -->|Non| GEN_MOVES["Lister les coups possibles"]

    GEN_MOVES --> IS_MAX{"Qui joue<br/>dans cette<br/>simulation ?"}

    %% --- Branche MAX ---
    IS_MAX -->|"L'IA"| MAX_LOOP["Pour chaque coup possible"]
    MAX_LOOP --> MAX_SIM["Simuler le coup"]
    MAX_SIM --> MAX_REC["Simuler le tour suivant<br/>(point de vue adversaire)"]
    MAX_REC --> MAX_UPDATE["Retenir le meilleur score"]
    MAX_UPDATE --> MAX_PRUNE{"Peut-on ignorer<br/>le reste des coups ?<br/>(élagage)"}
    MAX_PRUNE -->|"Oui ✂️"| MAX_CUT["Couper : l'adversaire<br/>ne choisira jamais<br/>cette branche"]
    MAX_CUT --> MAX_RETURN
    MAX_PRUNE -->|"Non"| MAX_NEXT{"Coup suivant ?"}
    MAX_NEXT -->|Oui| MAX_LOOP
    MAX_NEXT -->|Non| MAX_RETURN(["↩ Retourner le<br/>meilleur score (IA)"])

    %% --- Branche MIN ---
    IS_MAX -->|"L'Adversaire"| MIN_LOOP["Pour chaque coup possible"]
    MIN_LOOP --> MIN_SIM["Simuler le coup"]
    MIN_SIM --> MIN_REC["Simuler le tour suivant<br/>(point de vue IA)"]
    MIN_REC --> MIN_UPDATE["Retenir le pire score<br/>(du point de vue de l'IA)"]
    MIN_UPDATE --> MIN_PRUNE{"Peut-on ignorer<br/>le reste des coups ?<br/>(élagage)"}
    MIN_PRUNE -->|"Oui ✂️"| MIN_CUT["Couper : l'IA<br/>ne choisira jamais<br/>cette branche"]
    MIN_CUT --> MIN_RETURN
    MIN_PRUNE -->|"Non"| MIN_NEXT{"Coup suivant ?"}
    MIN_NEXT -->|Oui| MIN_LOOP
    MIN_NEXT -->|Non| MIN_RETURN(["↩ Retourner le<br/>pire score (adversaire)"])

    style START fill:#9C27B0,color:#fff
    style MAX_CUT fill:#f44336,color:#fff
    style MIN_CUT fill:#f44336,color:#fff
    style CACHE_HIT fill:#FF9800,color:#fff
```

---

## Comment l'IA évalue une position

Quand l'IA ne peut pas simuler plus loin, elle donne un **score** à la position. Ce score reflète à quel point la situation est favorable.

```mermaid
flowchart TD
    EVAL_START(["Évaluer la position actuelle"]) --> GAME_OVER{"Quelqu'un<br/>a gagné ?"}

    GAME_OVER -->|"L'IA gagne"| WIN(["↩ Score très élevé<br/>(victoire !)"])
    GAME_OVER -->|"L'IA perd"| LOSE(["↩ Score très bas<br/>(défaite)"])
    GAME_OVER -->|"Partie en cours"| CALC

    CALC --> BFS_IA["Calculer la distance<br/>de l'IA à son objectif"]
    CALC --> BFS_ADV["Calculer la distance<br/>de l'adversaire à son objectif"]

    BFS_IA --> METRICS
    BFS_ADV --> METRICS

    METRICS["Combiner les critères"] --> CRITERIA

    CRITERIA --> C1["📏 <b>Distance</b><br/>L'IA est-elle plus proche<br/>du but que l'adversaire ?"]
    CRITERIA --> C2["🛡️ <b>Sécurité</b><br/>L'IA a-t-elle plusieurs<br/>chemins alternatifs ?"]
    CRITERIA --> C3["🧱 <b>Murs restants</b><br/>L'IA peut-elle encore<br/>bloquer l'adversaire ?"]
    CRITERIA --> C4["🚶 <b>Mobilité</b><br/>L'IA a-t-elle beaucoup<br/>de cases accessibles ?"]

    C1 --> COMBINE
    C2 --> COMBINE
    C3 --> COMBINE
    C4 --> COMBINE

    COMBINE["Calculer le score final<br/>= somme pondérée des critères"] --> RETURN_SCORE(["↩ Retourner le score"])

    style EVAL_START fill:#FF5722,color:#fff
    style WIN fill:#4CAF50,color:#fff
    style LOSE fill:#f44336,color:#fff
```

---

## Astuces d'optimisation de l'IA

```mermaid
flowchart LR
    subgraph "🚀 Comment l'IA accélère sa réflexion"
        direction TB
        OPT1["<b>Tri des coups</b><br/>Évaluer les coups prometteurs<br/>en premier pour couper plus vite"]
        OPT2["<b>Mémoire des positions</b><br/>Ne jamais recalculer une<br/>position déjà analysée"]
        OPT3["<b>Validation rapide des murs</b><br/>Vérifier d'abord si le mur<br/>gêne un chemin existant"]
        OPT4["<b>Calcul de distances en bloc</b><br/>Calculer toutes les distances<br/>en un seul parcours du plateau"]
        OPT5["<b>Sélection de murs malins</b><br/>Ne considérer que les murs<br/>proches des chemins des joueurs"]
    end

    OPT1 --- OPT2 --- OPT3 --- OPT4 --- OPT5

    style OPT1 fill:#2196F3,color:#fff
    style OPT2 fill:#FF9800,color:#fff
    style OPT3 fill:#4CAF50,color:#fff
    style OPT4 fill:#9C27B0,color:#fff
    style OPT5 fill:#E91E63,color:#fff
```

---

> **En résumé :** L'IA imagine les prochains coups à l'avance, suppose que l'adversaire joue au mieux, et choisit le coup qui lui donne le plus d'avantage. Plus la difficulté est élevée, plus elle anticipe de coups (2 à 5 coups d'avance).
