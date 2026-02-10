# 🎲 Logique et Règles du Jeu

Ce diagramme détaille comment le moteur de jeu valide et applique chaque coup selon les règles du Quoridor.

---

## Déroulement d'un coup

```mermaid
flowchart TD
    ENTRY(["Le joueur soumet un coup"]) --> SAVE["Sauvegarder l'état actuel<br/>(pour pouvoir annuler)"]
    SAVE --> TYPE{"Quel type<br/>de coup ?"}

    TYPE -->|"Déplacement"| MOVE["Vérifier et déplacer<br/>le pion"]
    TYPE -->|"Mur"| WALL["Vérifier et placer<br/>le mur"]
    TYPE -->|"Inconnu"| ERR_TYPE["❌ Type de coup<br/>non reconnu"]

    MOVE --> SUCCESS
    WALL --> SUCCESS

    SUCCESS{"Le coup est<br/>valide ?"}
    SUCCESS -->|Oui| NEXT["Appliquer le coup<br/>Passer au joueur suivant"] --> DONE(["✅ Coup joué"])
    SUCCESS -->|Non| ROLLBACK["Annuler la sauvegarde<br/>(rien n'a changé)"]
    ROLLBACK --> ERROR(["❌ Coup refusé<br/>avec explication"])
    ERR_TYPE --> ROLLBACK

    style ENTRY fill:#2196F3,color:#fff
    style DONE fill:#4CAF50,color:#fff
    style ERROR fill:#f44336,color:#fff
```

---

## Validation d'un déplacement de pion

```mermaid
flowchart TD
    MOVE_START(["Le joueur veut<br/>déplacer son pion"]) --> TURN{"C'est bien<br/>son tour ?"}
    TURN -->|Non| ERR1(["❌ Ce n'est pas<br/>votre tour"])
    TURN -->|Oui| POSSIBLE["Calculer toutes les cases<br/>où le pion peut aller"]

    POSSIBLE --> CHECK{"La case demandée<br/>est accessible ?"}
    CHECK -->|Non| ERR2(["❌ Déplacement<br/>impossible"])
    CHECK -->|Oui| CREATE["Créer le nouvel état<br/>avec le pion déplacé"]
    CREATE --> SWITCH["Passer au tour<br/>de l'autre joueur"]
    SWITCH --> RETURN(["✅ Pion déplacé"])

    style MOVE_START fill:#2196F3,color:#fff
    style RETURN fill:#4CAF50,color:#fff
    style ERR1 fill:#f44336,color:#fff
    style ERR2 fill:#f44336,color:#fff
```

---

## Comment sont calculées les cases accessibles

```mermaid
flowchart TD
    START(["Quelles cases sont<br/>accessibles pour ce pion ?"]) --> POS["Repérer la position<br/>du pion et de l'adversaire"]

    POS --> DIR["Examiner chaque direction :<br/>↑ Haut, ↓ Bas, ← Gauche, → Droite"]
    DIR --> BOUNDS{"La case voisine<br/>est dans le<br/>plateau ?"}
    BOUNDS -->|Non| SKIP["Ignorer cette<br/>direction"]
    BOUNDS -->|Oui| WALL_CHECK{"Un mur bloque<br/>le passage ?"}
    WALL_CHECK -->|Oui| SKIP
    WALL_CHECK -->|Non| OCC{"L'adversaire<br/>est sur cette<br/>case ?"}

    OCC -->|"Non → Case libre"| ADD["✅ Case accessible"]

    OCC -->|"Oui → Adversaire présent"| JUMP_CALC["Peut-on sauter<br/>par-dessus lui ?"]
    JUMP_CALC --> JUMP_OK{"Pas de mur<br/>derrière lui<br/>et dans les<br/>limites ?"}
    JUMP_OK -->|Oui| ADD_JUMP["✅ Saut par-dessus<br/>l'adversaire"]
    JUMP_OK -->|"Non → Bloqué"| DIAG["Peut-on contourner<br/>en diagonale ?"]

    DIAG --> DIAG_CHECK{"Cases diagonales<br/>accessibles ?<br/>(pas de mur)"}
    DIAG_CHECK -->|Oui| ADD_DIAG["✅ Saut en<br/>diagonale"]
    DIAG_CHECK -->|Non| SKIP

    ADD --> NEXT["Direction suivante"]
    ADD_JUMP --> NEXT
    ADD_DIAG --> NEXT
    SKIP --> NEXT

    NEXT --> MORE{"Encore des<br/>directions ?"}
    MORE -->|Oui| DIR
    MORE -->|Non| RETURN(["Retourner la liste<br/>des cases accessibles"])

    style START fill:#2196F3,color:#fff
    style RETURN fill:#4CAF50,color:#fff
    style ADD fill:#81C784
    style ADD_JUMP fill:#FFB74D
    style ADD_DIAG fill:#CE93D8
```

---

## Validation du placement d'un mur

```mermaid
flowchart TD
    WALL_START(["Le joueur veut<br/>poser un mur"]) --> W_TURN{"C'est bien<br/>son tour ?"}
    W_TURN -->|Non| W_ERR1(["❌ Pas votre tour"])
    W_TURN -->|Oui| W_WALLS{"Il lui reste<br/>des murs ?<br/>(max 10)"}
    W_WALLS -->|Non| W_ERR2(["❌ Plus de murs<br/>disponibles"])
    W_WALLS -->|Oui| VALIDATE

    VALIDATE["Vérifier les règles<br/>de placement"] --> V1{"Le mur est<br/>entièrement dans<br/>le plateau ?"}
    V1 -->|Non| V_ERR1(["❌ Hors limites"])
    V1 -->|Oui| V2{"Un mur identique<br/>existe déjà ?"}
    V2 -->|Oui| V_ERR2(["❌ Mur déjà posé<br/>à cet endroit"])
    V2 -->|Non| V3{"Le mur chevauche<br/>un mur parallèle<br/>existant ?"}
    V3 -->|Oui| V_ERR3(["❌ Chevauchement<br/>de murs"])
    V3 -->|Non| V4{"Le mur croise<br/>un mur existant<br/>perpendiculaire ?"}
    V4 -->|Oui| V_ERR4(["❌ Croisement<br/>de murs"])
    V4 -->|Non| PATH_CHECK

    PATH_CHECK["Vérifier que les chemins<br/>restent ouverts"] --> BFS1{"Le Joueur 1<br/>peut encore<br/>atteindre son but ?"}
    BFS1 -->|Non| P_ERR(["❌ Bloque Joueur 1"])
    BFS1 -->|Oui| BFS2{"Le Joueur 2<br/>peut encore<br/>atteindre son but ?"}
    BFS2 -->|Non| P_ERR2(["❌ Bloque Joueur 2"])
    BFS2 -->|Oui| PLACE["✅ Placer le mur<br/>Retirer 1 mur au joueur<br/>Passer au joueur suivant"]
    PLACE --> W_RETURN(["✅ Mur posé"])

    style WALL_START fill:#FF9800,color:#fff
    style W_RETURN fill:#4CAF50,color:#fff
    style V_ERR1 fill:#f44336,color:#fff
    style V_ERR2 fill:#f44336,color:#fff
    style V_ERR3 fill:#f44336,color:#fff
    style V_ERR4 fill:#f44336,color:#fff
    style P_ERR fill:#f44336,color:#fff
    style P_ERR2 fill:#f44336,color:#fff
    style W_ERR1 fill:#f44336,color:#fff
    style W_ERR2 fill:#f44336,color:#fff
```

---

## Recherche de chemin (un joueur peut-il encore gagner ?)

Cette vérification est cruciale : un mur ne peut **jamais** enfermer complètement un joueur.

```mermaid
flowchart TD
    BFS_START(["Un chemin existe-t-il<br/>vers l'objectif ?"]) --> INIT["Partir de la position<br/>actuelle du joueur"]

    INIT --> EMPTY{"Encore des<br/>cases à<br/>explorer ?"}
    EMPTY -->|"Non → aucune case restante"| NO_PATH(["❌ Aucun chemin<br/>Le mur est interdit"])
    EMPTY -->|Oui| DEQUEUE["Prendre la prochaine<br/>case à examiner"]

    DEQUEUE --> GOAL{"Cette case est<br/>sur la ligne<br/>d'arrivée ?"}
    GOAL -->|Oui| FOUND(["✅ Chemin trouvé<br/>Le mur est autorisé"])
    GOAL -->|Non| EXPLORE["Examiner les 4 voisins<br/>↑ ↓ ← →"]

    EXPLORE --> NEIGHBOR{"Le voisin est<br/>accessible ?<br/>• Dans le plateau<br/>• Pas déjà visité<br/>• Pas de mur"}
    NEIGHBOR -->|Oui| ENQUEUE["Ajouter à la file<br/>d'exploration"]
    NEIGHBOR -->|Non| NEXT_N["Voisin suivant"]
    ENQUEUE --> NEXT_N
    NEXT_N --> MORE_N{"Encore des<br/>voisins ?"}
    MORE_N -->|Oui| NEIGHBOR
    MORE_N -->|Non| EMPTY

    style BFS_START fill:#9C27B0,color:#fff
    style FOUND fill:#4CAF50,color:#fff
    style NO_PATH fill:#f44336,color:#fff
```

---

> **Principe clé :** Chaque coup crée un **nouvel état du jeu** sans modifier le précédent. Cela permet d'annuler facilement un coup et à l'IA de simuler des parties futures sans risque.
