# Positions des murs mesurées

> ⚠️ **INVARIANT — Source de vérité : matrices `MURS_H[j][i]` et `MURS_V[j][i]`
> dans `firmware/src/bringup_l298n_complet.cpp` (lignes 140-147 et 169-177).**
>
> Valeurs gelées au **2026-05-20** : 18 positions mesurées sur 60 (9 H + 9 V).
> Les 42 positions manquantes sont marquées `_NA` dans le sketch.
>
> **À revalider physiquement le 2026-05-21** : doute de saisie possible sur certaines
> coordonnées entre matrices H et V. Procédure : flasher le sketch, lancer `LIST` pour
> voir le statut de remplissage, puis `TOUR` pour parcourir tous les murs mesurés et
> vérifier le centrage de chaque cible.

## Convention plateau

- Origine (0, 0) : **bas-gauche** du plateau, établie par HOME automatique au boot.
- Axe X : croissant vers la droite.
- Axe Y : croissant vers le haut.
- Unité : pas full-step (1 cm = 50 pas, voir [calibration.md](calibration.md)).
- Plateau Quoridor : 6 × 6 cases, 30 murs horizontaux + 30 murs verticaux = 60 positions.

## Murs horizontaux — `MURS_H[j][i]` (9 / 30 mesurés)

Indices : `i ∈ [0..5]` (colonne, i=0 à gauche), `j ∈ [0..4]` (ligne, j=0 en bas).

| (i, j) | (x, y) en pas |
|---|---|
| (0, 0) | (102, 35) |
| (3, 0) | (406, 35) |
| (5, 0) | (709, 35) |
| (0, 2) | (105, 486) |
| (3, 2) | (482, 406) |
| (5, 2) | (709, 485) |
| (0, 4) | (109, 777) |
| (3, 4) | (409, 777) |
| (5, 4) | (709, 777) |

Les 21 autres positions H sont à mesurer après la démo.

## Murs verticaux — `MURS_V[j][i]` (9 / 30 mesurés)

Indices : `i ∈ [0..4]` (colonne, i=0 à gauche), `j ∈ [0..5]` (ligne, j=0 en bas).

| (i, j) | (x, y) en pas |
|---|---|
| (0, 0) | (32, 110) |
| (2, 0) | (330, 107) |
| (4, 0) | (779, 105) |
| (0, 3) | (33, 408) |
| (2, 3) | (407, 479) |
| (4, 3) | (782, 400) |
| (0, 5) | (34, 707) |
| (2, 5) | (339, 711) |
| (4, 5) | (784, 705) |

Les 21 autres positions V sont à mesurer après la démo.

## Procédure de mesure (pour les 42 positions manquantes)

1. Flasher `bringup_l298n_complet.cpp`. Le HOME s'effectue automatiquement au boot.
2. Avec `X F/B <n>` et `Y F/B <n>`, naviguer le piston pile sous un mur non mesuré.
3. Taper `STATUS` au moniteur série et noter la position (x, y) affichée.
4. Éditer le sketch : remplacer `_NA` par `{x, y}` dans la cellule correspondante.
5. Recompiler et reuploader. Taper `LIST` pour voir le statut de remplissage à jour.
6. Taper `TOUR` pour parcourir tous les murs mesurés et vérifier le centrage.

Penser à **synchroniser ce fichier** avec les nouvelles valeurs lors d'une session
de calibration.
