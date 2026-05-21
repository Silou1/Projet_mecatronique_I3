# Positions des murs mesurées

> ⚠️ **INVARIANT — Source de vérité : matrices `MURS_H[j][i]` et `MURS_V[j][i]`
> dans `firmware/src/bringup_l298n_complet.cpp`.**
>
> Valeurs validées au **2026-05-21** : **60 / 60 positions mesurées** (30 H + 30 V)
> via la commande `CALIB V` / `CALIB H` après inversion physique des moteurs et
> des capteurs de fin de course X / Y.

## Convention plateau

- Origine (0, 0) : **bas-gauche** du plateau, établie par HOME automatique au boot.
- Axe X : croissant vers la droite.
- Axe Y : croissant vers le haut (vers l'adversaire).
- Unité : pas full-step (1 cm = 50 pas, voir [calibration.md](calibration.md)).
- Plateau Quoridor 6 × 6 cases, parité paire qui crée l'alternance suivante en y :
  - **Murs V** (rectangles **debouts** entre 2 cases horizontalement adjacentes) :
    5 par rangée × 6 rangées = 30, alignés sur les **centres** des rangées de cases.
  - **Murs H** (rectangles **couchés** entre 2 cases verticalement adjacentes) :
    6 par rangée × 5 rangées = 30, alignés sur les **frontières** entre rangées.

## Murs verticaux — `MURS_V[j][i]` (30 / 30 mesurés)

Indices : `i ∈ [0..4]` (colonne, i=0 à gauche), `j ∈ [0..5]` (ligne, j=0 en bas).
Pitch moyen : 150 pas en x, 150 pas en y.

| j ↓ \ i → | i=0       | i=1       | i=2       | i=3       | i=4       |
|---|---|---|---|---|---|
| j=5 (haut) | (117, 787) | (262, 787) | (415, 787) | (562, 787) | (712, 787) |
| j=4 | (107, 636) | (257, 636) | (409, 636) | (552, 636) | (707, 636) |
| j=3 | (107, 487) | (258, 487) | (409, 487) | (556, 487) | (707, 487) |
| j=2 | (112, 341) | (258, 341) | (409, 341) | (556, 341) | (707, 336) |
| j=1 | (102, 190) | (253, 190) | (404, 190) | (556, 190) | (707, 190) |
| j=0 (bas)  | (102,  35) | (253,  35) | (404,  35) | (551,  35) | (702,  35) |

## Murs horizontaux — `MURS_H[j][i]` (30 / 30 mesurés)

Indices : `i ∈ [0..5]` (colonne, i=0 à gauche), `j ∈ [0..4]` (ligne, j=0 en bas).
Pitch moyen : 150 pas en x, 150 pas en y.

| j ↓ \ i → | i=0       | i=1       | i=2       | i=3       | i=4       | i=5       |
|---|---|---|---|---|---|---|
| j=4 (haut) | ( 35, 717) | (189, 712) | (338, 712) | (488, 712) | (637, 702) | (787, 702) |
| j=3 | ( 30, 567) | (184, 562) | (333, 562) | (483, 562) | (632, 557) | (782, 552) |
| j=2 | ( 30, 417) | (179, 412) | (333, 412) | (483, 412) | (632, 407) | (782, 407) |
| j=1 | ( 30, 272) | (179, 262) | (333, 262) | (483, 262) | (632, 262) | (777, 262) |
| j=0 (bas)  | ( 30, 112) | (189, 112) | (328, 112) | (488, 112) | (627, 112) | (777, 112) |

## Procédure de mesure (`CALIB V` et `CALIB H`)

Deux commandes série dédiées (disponibles dans le sketch de production après HOME) :

```
CALIB V         # parcourt les 30 emplacements de MURS_V
CALIB H         # parcourt les 30 emplacements de MURS_H
```

À chaque mur :
1. Le piston se déplace à la position théorique calculée par interpolation linéaire
   sur la grille régulière (coins définis par les constantes `CALIB_V_*` / `CALIB_H_*`
   du sketch, calibrées sur les valeurs mesurées).
2. Affichage : `=== Mur N/30 (matrice V|H) : [j=X][i=Y] ===` + position théorique cible.
3. Ajuster manuellement avec `X F/B <n>` / `Y F/B <n>` pour centrer le piston pile
   sous le trou du mur.
4. `STATUS` pour relire la position vraie en pas.
5. `NEXT` pour passer au mur suivant non mesuré (les positions déjà remplies dans la
   matrice sont sautées automatiquement, ce qui permet de reprendre une session interrompue).
6. `STOP` à tout moment pour interrompre.

Après mesure complète, éditer le sketch et remplacer les `_NA` par `{x, y}` dans les
matrices `MURS_H` / `MURS_V`. Recompiler et reuploader. `LIST` affiche le statut de
remplissage à jour.

## Notes hardware

- L'inversion physique des moteurs et des capteurs X / Y du 2026-05-21 a invalidé
  les anciennes valeurs (notamment le doute de saisie H ↔ V signalé dans la version
  précédente de ce document).
- Les valeurs ci-dessus sont les **mesures réelles après inversion**, pas une grille
  théorique. Léger jitter visible (±5 pas) sur certaines colonnes, sans impact sur
  la levée des murs.
