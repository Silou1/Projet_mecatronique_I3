# 🤖 Logique de l'Intelligence Artificielle

Ce diagramme détaille le fonctionnement de l'IA du Quoridor, basée sur l'algorithme **Minimax avec élagage Alpha-Bêta**.

---

## Vue d'Ensemble de l'IA

```mermaid
flowchart TD
    ENTRY(["find_best_move(state)"]) --> RESET["Réinitialiser caches<br/>et compteurs"]
    RESET --> GEN["Générer tous les coups possibles<br/>_get_all_possible_moves()"]
    GEN --> SORT["Trier par promesse<br/>(Move Ordering)"]

    SORT --> LOOP["Pour chaque coup"]
    LOOP --> SIM["Simuler le coup<br/>_apply_move()"]
    SIM --> MINIMAX["Appel Minimax<br/>_minimax(state, depth-1,<br/>α, +∞, False)"]

    MINIMAX --> COMPARE{"score > <br/>meilleur ?"}
    COMPARE -->|Oui| NEW_BEST["Nouveau meilleur coup<br/>best_moves = coup"]
    COMPARE -->|"Égal"| ADD["Ajouter aux<br/>meilleurs coups"]
    COMPARE -->|Non| NEXT

    NEW_BEST --> NEXT["Coup suivant"]
    ADD --> NEXT
    NEXT --> MORE{"Encore des<br/>coups ?"}
    MORE -->|Oui| LOOP
    MORE -->|Non| CHOOSE

    CHOOSE["🎲 Choix aléatoire parmi<br/>les meilleurs coups<br/>(variété de jeu)"] --> RETURN(["Retourner le meilleur coup"])

    style ENTRY fill:#E91E63,color:#fff
    style RETURN fill:#4CAF50,color:#fff
    style MINIMAX fill:#9C27B0,color:#fff
```

---

## Algorithme Minimax avec Alpha-Bêta

```mermaid
flowchart TD
    START(["_minimax(state, depth, α, β, is_max)"]) --> NODES["nodes_explored += 1"]

    NODES --> CACHE{"État dans la<br/>table de<br/>transposition ?"}
    CACHE -->|"Oui (depth ≥ actuelle)"| CACHE_HIT(["↩ Retourner<br/>score caché"])
    CACHE -->|Non| LEAF

    LEAF{"Feuille ?<br/>(depth = 0 ou<br/>partie finie)"}
    LEAF -->|Oui| EVAL["Évaluer position<br/>_evaluate_state()"]
    EVAL --> STORE_EVAL["Stocker dans cache"] --> RETURN_EVAL(["↩ Retourner score"])

    LEAF -->|Non| GEN_MOVES["Générer les coups<br/>_get_all_possible_moves()"]

    GEN_MOVES --> IS_MAX{"is_maximizing ?"}

    %% --- Branche MAX ---
    IS_MAX -->|"Oui (tour IA)"| MAX_INIT["max_eval = -∞"]
    MAX_INIT --> MAX_LOOP["Pour chaque coup"]
    MAX_LOOP --> MAX_SIM["Simuler le coup"]
    MAX_SIM --> MAX_REC["Appel récursif<br/>minimax(..., False)"]
    MAX_REC --> MAX_UPDATE["max_eval = max(max_eval, score)<br/>α = max(α, score)"]
    MAX_UPDATE --> MAX_PRUNE{"β ≤ α ?"}
    MAX_PRUNE -->|"Oui ✂️"| MAX_CUT["ÉLAGAGE !<br/>Couper la branche"]
    MAX_CUT --> MAX_STORE
    MAX_PRUNE -->|Non| MAX_NEXT{"Coup suivant ?"}
    MAX_NEXT -->|Oui| MAX_LOOP
    MAX_NEXT -->|Non| MAX_STORE["Stocker dans cache"]
    MAX_STORE --> MAX_RETURN(["↩ Retourner max_eval"])

    %% --- Branche MIN ---
    IS_MAX -->|"Non (tour adversaire)"| MIN_INIT["min_eval = +∞"]
    MIN_INIT --> MIN_LOOP["Pour chaque coup"]
    MIN_LOOP --> MIN_SIM["Simuler le coup"]
    MIN_SIM --> MIN_REC["Appel récursif<br/>minimax(..., True)"]
    MIN_REC --> MIN_UPDATE["min_eval = min(min_eval, score)<br/>β = min(β, score)"]
    MIN_UPDATE --> MIN_PRUNE{"β ≤ α ?"}
    MIN_PRUNE -->|"Oui ✂️"| MIN_CUT["ÉLAGAGE !<br/>Couper la branche"]
    MIN_CUT --> MIN_STORE
    MIN_PRUNE -->|Non| MIN_NEXT{"Coup suivant ?"}
    MIN_NEXT -->|Oui| MIN_LOOP
    MIN_NEXT -->|Non| MIN_STORE["Stocker dans cache"]
    MIN_STORE --> MIN_RETURN(["↩ Retourner min_eval"])

    style START fill:#9C27B0,color:#fff
    style MAX_CUT fill:#f44336,color:#fff
    style MIN_CUT fill:#f44336,color:#fff
    style CACHE_HIT fill:#FF9800,color:#fff
```

---

## Fonction d'Évaluation Heuristique

```mermaid
flowchart TD
    EVAL_START(["_evaluate_state(state)"]) --> GAME_OVER{"Partie<br/>terminée ?"}

    GAME_OVER -->|"IA gagne"| WIN(["↩ +1000"])
    GAME_OVER -->|"IA perd"| LOSE(["↩ -1000"])
    GAME_OVER -->|"En cours"| CALC

    CALC --> BFS_IA["BFS Inversé<br/>distances IA → but"]
    CALC --> BFS_ADV["BFS Inversé<br/>distances Adversaire → but"]

    BFS_IA --> METRICS
    BFS_ADV --> METRICS

    METRICS["Calcul des métriques"] --> CRITERIA

    CRITERIA --> C1["📏 Distance L1<br/>dist_adversaire - dist_IA<br/>(× poids fort)"]
    CRITERIA --> C2["🛡️ Robustesse<br/>Nb de chemins<br/>alternatifs"]
    CRITERIA --> C3["🧱 Murs restants<br/>Bonus si l'adversaire<br/>approche du but"]
    CRITERIA --> C4["🚶 Mobilité<br/>Nb de déplacements<br/>immédiats possibles"]

    C1 --> COMBINE
    C2 --> COMBINE
    C3 --> COMBINE
    C4 --> COMBINE

    COMBINE["Score = Σ (critère × poids)"] --> RETURN_SCORE(["↩ Retourner score"])

    style EVAL_START fill:#FF5722,color:#fff
    style WIN fill:#4CAF50,color:#fff
    style LOSE fill:#f44336,color:#fff
```

---

## Optimisations de l'IA

```mermaid
flowchart LR
    subgraph "🚀 Optimisations"
        direction TB
        OPT1["<b>Move Ordering</b><br/>Trier les coups par score<br/>pour élaguer plus tôt"]
        OPT2["<b>Table de Transposition</b><br/>Cache des états déjà<br/>évalués (hash → score)"]
        OPT3["<b>Lazy Wall Validation</b><br/>Vérifier si le mur coupe<br/>le chemin courant d'abord"]
        OPT4["<b>BFS Inversé</b><br/>Calculer toutes les distances<br/>en un seul parcours"]
        OPT5["<b>Murs Stratégiques</b><br/>Ne considérer que ~20 murs<br/>proches des chemins"]
    end

    OPT1 --- OPT2 --- OPT3 --- OPT4 --- OPT5

    style OPT1 fill:#2196F3,color:#fff
    style OPT2 fill:#FF9800,color:#fff
    style OPT3 fill:#4CAF50,color:#fff
    style OPT4 fill:#9C27B0,color:#fff
    style OPT5 fill:#E91E63,color:#fff
```

---

> **Complexité :** Sans Alpha-Bêta → O(b^d). Avec Alpha-Bêta → O(b^(d/2)). Profondeur typique : 2 à 5 selon la difficulté.
