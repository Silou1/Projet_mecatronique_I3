# Présentation du projet

## Vision

Le projet consiste à réaliser une version jouable du jeu de société **Quoridor** sur un plateau
physique mécatronique 6×6. La vue principale est une **webapp** servie par un serveur FastAPI,
accessible depuis un navigateur sur le même réseau local. Le plateau physique constitue un miroir
physique de la partie : un chariot CoreXY déplace un servo qui lève ou abaisse mécaniquement les
murs au bon emplacement lorsqu'un joueur en pose un.

Deux modes de jeu sont disponibles : **Joueur vs Joueur** (deux humains sur la même interface) et
**Joueur vs IA** (l'adversaire est un moteur Minimax avec élagage Alpha-Bêta). La webapp fonctionne
en **mode autonome** (sans plateau physique) ou en **mode hybride** lorsque l'ESP32 est connecté via
USB-série. Le fallback est gracieux : si le câble série est absent, la partie se joue normalement
sans miroir physique.

L'objectif du rendu final est de démontrer, sur plateau physique et webapp simultanément, une partie
complète de Quoridor avec levée automatique des murs. Le tout constitue un livrable intégrant
conception logicielle, intelligence artificielle et commande de systèmes mécatroniques.

---

## Contexte ICAM

Ce projet est réalisé dans le cadre de la **3e année de cycle ingénieur** spécialité mécatronique à
l'ICAM. Il réunit une équipe de **6 étudiants** et s'étend sur le second semestre 2025-2026. Il vise
une présentation finale devant jury avec livrable fonctionnel.

Le projet illustre l'intégration de plusieurs disciplines enseignées : algorithmique (moteur de jeu,
IA), développement logiciel (Python, API REST, frontend web), systèmes embarqués (firmware Arduino
C++ sur ESP32), mécanique (architecture CoreXY) et électronique de puissance (pilotage de moteurs
pas-à-pas et servo). C'est un projet volontairement pluridisciplinaire, conçu pour relier des
compétences qui restent souvent cloisonnées.

---

## Règles du jeu Quoridor

### Plateau et pions

- Plateau **6×6 cases**.
- **2 joueurs**, chacun avec un pion et **6 murs** disponibles.
- **Joueur 1 (J1)** : démarre en `d6` (ligne du bas), doit atteindre la **ligne 1**.
- **Joueur 2 (J2)** : démarre en `d1` (ligne du haut), doit atteindre la **ligne 6**.
- La **victoire** revient au premier joueur dont le pion atteint n'importe quelle case de sa ligne
  d'arrivée.

### Notation des cases

Les cases sont désignées par une **lettre** (colonne) et un **chiffre** (ligne) :

```
   a b c d e f
  ━━━━━━━━━━━
1┃· · · 2 · ·┃   ← ligne 1 (haut)  — ligne d'arrivée de J1
 ┃           ┃
2┃· · · · · ·┃
 ┃           ┃
3┃· · · · · ·┃
 ┃           ┃
4┃· · · · · ·┃
 ┃           ┃
5┃· · · · · ·┃
 ┃           ┃
6┃· · · 1 · ·┃   ← ligne 6 (bas)   — ligne d'arrivée de J2
  ━━━━━━━━━━━
```

- Colonnes : `a` à `f` (gauche → droite)
- Lignes : `1` à `6` (haut → bas dans l'affichage)

### Déplacements

À son tour, un joueur peut **déplacer son pion d'une case** dans l'une des quatre directions
orthogonales (haut, bas, gauche, droite), sauf si un mur bloque le passage.

**Saut par-dessus l'adversaire** : si le pion adverse est adjacent et qu'aucun mur ne se trouve
derrière lui, le joueur peut sauter par-dessus et atterrir de l'autre côté. Si un mur bloque le
saut direct, il est possible de sauter en diagonale (latéralement par rapport au pion adverse).

Commande en jeu : `d <case>` — exemple : `d c5`

### Murs

À son tour, un joueur peut **poser un mur** plutôt que de déplacer son pion. Un mur bloque le
passage entre **2 cases adjacentes** sur toute sa longueur :

- **Mur horizontal (`h`)** : bloque le passage entre une ligne et la suivante, sur 2 colonnes.
- **Mur vertical (`v`)** : bloque le passage entre une colonne et la suivante, sur 2 lignes.

**Contrainte fondamentale** : on ne peut pas poser un mur qui **couperait totalement** le chemin
d'un joueur vers sa ligne d'arrivée. Il doit toujours exister au moins un chemin possible (vérifié
par BFS à chaque placement).

Commande en jeu : `m <h|v> <case>` — exemple : `m h c3` (mur horizontal ancré en c3)

### Résumé des commandes

| Commande          | Description                              | Exemple    |
|-------------------|------------------------------------------|------------|
| `d <case>`        | Déplacer le pion                         | `d c5`     |
| `m <h\|v> <case>` | Poser un mur horizontal ou vertical      | `m v e4`   |
| `undo`            | Annuler le dernier coup                  | `undo`     |
| `moves` ou `?`    | Afficher les coups légaux disponibles    | `moves`    |
| `help` ou `h`     | Afficher l'aide                          | `help`     |
| `quit` ou `q`     | Quitter la partie                        | `quit`     |

---

## Objectifs pédagogiques

| Domaine              | Ce que le projet met en œuvre                                           |
|----------------------|-------------------------------------------------------------------------|
| Algorithmique        | Minimax avec Alpha-Bêta, iterative deepening, BFS pathfinding           |
| Développement Python | FastAPI, frontend SVG vanilla, architecture en couches, tests pytest    |
| Embarqué             | Firmware Arduino C++ sur ESP32-WROOM, protocole UART texte, FSM        |
| Mécanique            | Architecture CoreXY (2 steppers NEMA17), homing par fins de course      |
| Électronique         | Pilotage L298N, commande servo SG90, alimentation 12 V                  |
| Intégration          | Communication PC ↔ ESP32 via USB-série, fallback gracieux               |

---

## Contraintes

### Calendrier

Le projet s'inscrit dans le semestre ICAM avec une date de présentation finale fixe. Le développement
suit un ordre de priorité strict : webapp autonome (mode sans matériel) → intégration UART →
validation plateau physique → démonstration finale.

### Équipe

6 personnes en parallèle. Les responsabilités sont réparties entre firmware embarqué, moteur de jeu
Python, webapp frontend/backend, et intégration hardware.

### Matériel disponible

| Composant                | Rôle                                          |
|--------------------------|-----------------------------------------------|
| ESP32-WROOM (Freenove)   | Contrôleur embarqué (firmware C++)            |
| 2× L298N                 | Ponts en H pour les steppers                  |
| 2× stepper NEMA17        | Axes X et Y du chariot CoreXY                 |
| 1× servo SG90            | Levée/baisse mécanique des murs               |
| 2× fins de course        | Homing des axes (position zéro)               |
| Alimentation 12 V        | Puissance moteurs                             |
| Breadboard + câblage     | Prototype (pas de PCB en production)          |
