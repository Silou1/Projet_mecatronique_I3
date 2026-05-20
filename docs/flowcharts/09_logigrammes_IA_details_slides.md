# Logigrammes IA détaillés — slides

Deux logigrammes complémentaires de la vue d'ensemble, format paysage compact pour slides.

## 1 — Minimax avec élagage alpha-bêta

```mermaid
flowchart LR
    IN([État à évaluer]) --> END{Feuille ?<br/>profondeur 0<br/>ou victoire}
    END -->|Oui| EVAL[Évaluer position]
    END -->|Non| WHO{Tour de qui ?}

    WHO -->|IA = MAX| MAX[Pour chaque coup :<br/>simuler + récursion<br/>garder le MAX]
    WHO -->|Adversaire = MIN| MIN[Pour chaque coup :<br/>simuler + récursion<br/>garder le MIN]

    MAX --> PRUNE_M{β ≤ α ?}
    MIN --> PRUNE_m{β ≤ α ?}

    PRUNE_M -->|Oui| CUT[Élagage<br/>couper la branche]
    PRUNE_m -->|Oui| CUT
    PRUNE_M -->|Non| OUT_M([Retour score MAX])
    PRUNE_m -->|Non| OUT_m([Retour score MIN])

    CUT --> OUT_cut([Retour anticipé])
    EVAL --> OUT_E([Retour score])

    style IN fill:#4CAF50,color:#fff
    style EVAL fill:#FF9800,color:#fff
    style MAX fill:#9C27B0,color:#fff
    style MIN fill:#3F51B5,color:#fff
    style CUT fill:#f44336,color:#fff
    style OUT_M fill:#E91E63,color:#fff
    style OUT_m fill:#E91E63,color:#fff
    style OUT_E fill:#E91E63,color:#fff
    style OUT_cut fill:#E91E63,color:#fff
```

## 2 — Fonction d'évaluation heuristique

```mermaid
flowchart LR
    POS([Position à évaluer]) --> OVER{Partie<br/>terminée ?}

    OVER -->|IA gagne| WIN([+ 20 000])
    OVER -->|IA perd| LOSE([- 20 000])
    OVER -->|En cours| BFS[BFS inversé :<br/>distances vers but<br/>pour IA et adversaire]

    BFS --> C1[Distance L1<br/>poids 150]
    BFS --> C2[Fragilité L2−L1<br/>poids 25]
    BFS --> C3[Murs restants<br/>contextuels]
    BFS --> C4[Mobilité<br/>poids 8]
    BFS --> C5[Contrôle centre<br/>poids 5]

    C1 --> SUM[Somme pondérée]
    C2 --> SUM
    C3 --> SUM
    C4 --> SUM
    C5 --> SUM

    SUM --> SCORE([Score final])

    style POS fill:#4CAF50,color:#fff
    style BFS fill:#9C27B0,color:#fff
    style WIN fill:#4CAF50,color:#fff
    style LOSE fill:#f44336,color:#fff
    style SCORE fill:#E91E63,color:#fff
    style SUM fill:#FF9800,color:#fff
```
