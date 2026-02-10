# 🎮 Vue Générale du Programme

Ce diagramme présente le flux principal du programme Quoridor, de son lancement à la fin de partie.

---

## Architecture des Modules

```mermaid
graph LR
    subgraph Interface
        MAIN["Interface Console<br/>(Affichage + Saisie)"]
    end

    subgraph Moteur
        CORE["Moteur de Jeu<br/>(Règles + État)"]
        AI_MOD["Intelligence Artificielle<br/>(Stratégie + Décision)"]
    end

    USER["👤 Joueur"] <-->|Commandes / Affichage| MAIN
    MAIN -->|Transmettre les coups<br/>Récupérer l'état| CORE
    MAIN -->|Demander le meilleur coup| AI_MOD
    AI_MOD -->|Simuler des coups<br/>Vérifier les règles| CORE
```

---

## Flux Principal du Programme

```mermaid
flowchart TD
    START(["▶ Lancement du jeu"]) --> MODE

    MODE{"Choix du mode<br/>de jeu"}
    MODE -->|"1"| PVP["Joueur vs Joueur"]
    MODE -->|"2"| PVIA["Joueur vs IA"]
    PVIA --> DIFF{"Choix de la<br/>difficulté"}
    DIFF -->|"Facile"| EASY["IA rapide, peu stratégique"]
    DIFF -->|"Normal"| NORMAL["IA équilibrée"]
    DIFF -->|"Difficile"| HARD["IA lente mais redoutable"]
    EASY --> INIT
    NORMAL --> INIT
    HARD --> INIT
    PVP --> INIT

    INIT["Créer une nouvelle partie<br/>Plateau vierge, pions au centre"] --> WELCOME["Afficher les règles<br/>et les objectifs"]
    WELCOME --> LOOP

    LOOP{"La partie<br/>est-elle<br/>terminée ?"}
    LOOP -->|Non| DISPLAY["Afficher le plateau<br/>avec pions et murs"]
    LOOP -->|Oui| END_GAME

    DISPLAY --> WHO{"À qui<br/>le tour ?"}
    WHO -->|"Tour de l'IA"| AI_TURN
    WHO -->|"Tour du Joueur"| HUMAN_TURN

    %% --- Tour IA ---
    AI_TURN["🤖 L'IA analyse la situation<br/>et choisit le meilleur coup"] --> AI_PLAY["Appliquer le coup de l'IA"]
    AI_PLAY --> AI_DISPLAY["Afficher quel coup<br/>l'IA a joué"]
    AI_DISPLAY --> LOOP

    %% --- Tour Humain ---
    HUMAN_TURN["Attendre la commande<br/>du joueur"] --> PARSE{"Que veut faire<br/>le joueur ?"}

    PARSE -->|"Déplacer<br/>son pion"| MOVE_CMD["Déplacer vers<br/>la case indiquée"]
    PARSE -->|"Poser<br/>un mur"| WALL_CMD["Placer un mur<br/>à l'endroit choisi"]
    PARSE -->|"Annuler"| UNDO_CMD["Revenir au<br/>coup précédent"]
    PARSE -->|"Voir les<br/>coups possibles"| SHOW_MOVES["Afficher les cases<br/>accessibles"]
    PARSE -->|"Aide"| HELP["Afficher les<br/>commandes"]
    PARSE -->|"Quitter"| QUIT_CONFIRM{"Confirmer<br/>l'abandon ?"}

    MOVE_CMD --> TRY_PLAY
    WALL_CMD --> TRY_PLAY
    TRY_PLAY["Vérifier et appliquer<br/>le coup"] --> VALID{"Le coup respecte<br/>les règles ?"}
    VALID -->|Oui| LOOP
    VALID -->|Non| ERROR["❌ Afficher pourquoi<br/>le coup est invalide"] --> LOOP

    UNDO_CMD --> LOOP
    SHOW_MOVES --> HUMAN_TURN
    HELP --> HUMAN_TURN
    QUIT_CONFIRM -->|Oui| ABANDON(["Partie abandonnée"])
    QUIT_CONFIRM -->|Non| HUMAN_TURN

    %% --- Fin de partie ---
    END_GAME["🎉 Annoncer le gagnant"] --> END_SCREEN(["Fin du programme"])

    %% --- Styles ---
    style START fill:#4CAF50,color:#fff
    style END_SCREEN fill:#f44336,color:#fff
    style ABANDON fill:#ff9800,color:#fff
    style AI_TURN fill:#E91E63,color:#fff
    style HUMAN_TURN fill:#2196F3,color:#fff
```

---

> **Légende :** Le programme alterne entre l'affichage du plateau et la gestion des tours (joueur humain ou IA) jusqu'à ce qu'un joueur atteigne le côté opposé du plateau.
