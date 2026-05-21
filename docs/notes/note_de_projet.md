# Note de Projet — Quoridor Interactif

> Version à jour au **2026-05-21**. Pour la vision initiale du projet
> (plateau autonome avec boutons + RPi), voir l'historique git de ce
> fichier et le registre [`../decisions.md`](../decisions.md).

---

## 1. Contexte et objectifs du projet

- **Projet** : projet de mécatronique mené par une équipe de six élèves
  ICAM en 3ᵉ année, semestre 2025-2026.
- **Concept** : recréer le jeu de société **Quoridor** sous une forme
  mécatronique hybride : un plateau physique animé associé à une
  interface logicielle.
- **Objectif principal** : permettre à un joueur humain d'affronter une
  intelligence artificielle (IA Minimax avec élagage alpha-bêta), avec
  un retour visuel et mécanique sur un plateau réel.
- **Expérience visée** : un Quoridor 6×6 jouable en démonstration sur un
  smartphone, avec les murs qui se lèvent physiquement sur le plateau
  au fur et à mesure des coups.
- **Règles du jeu** : règles classiques du Quoridor conservées sans
  modification, sur un plateau 6×6 (au lieu du 9×9 standard, pour
  contraintes de fabrication mécanique).

---

## 2. Interaction utilisateur

L'interface de jeu est une **webapp** servie par FastAPI, accessible
depuis n'importe quel navigateur (smartphone, ordinateur) connecté au
même réseau que le Mac.

- **Saisie des coups** : clic sur les cases (déplacement) ou les arêtes
  inter-cases (pose de mur) directement dans l'interface SVG.
- **Validation** : le moteur de jeu Python (`quoridor_engine`) valide
  chaque coup contre les règles, y compris la garantie BFS qu'un chemin
  reste possible pour chaque joueur après pose d'un mur.
- **Retour visuel double** :
  - Sur la **webapp** : plateau SVG mis à jour en temps réel (polling
    HTTP 500 ms).
  - Sur le **plateau physique** : strip LED WS2812B (36 LEDs) qui
    affiche les positions des pions et les coups légaux du joueur
    courant.
- **Retour mécanique** : pour chaque pose de mur, un piston monté sur
  un chariot CoreXY se déplace sous la position du mur et le lève
  physiquement via un servo.

**Pas de boutons sur le plateau.** L'idée initiale d'une matrice de
boutons 6×6 (un par case) a été abandonnée le 2026-05-21 ; voir
[`../decisions.md`](../decisions.md) pour les raisons. Le plateau est
désormais un **miroir physique** des coups joués sur la webapp.

---

## 3. Conception mécanique (système des murs)

Le plateau est conçu en plusieurs niveaux superposés :

- **Niveau 1 — Chariot CoreXY** : un système à deux moteurs pas à pas
  NEMA17 (architecture CoreXY) déplace un piston unique dans le plan XY
  sous le plateau. Le piston est aligné précisément avec chacune des
  positions de murs.
- **Niveau 2 — Stockage des murs** : tous les murs non posés y sont
  stockés à plat, prêts à être poussés vers le haut par le piston.
- **Niveau 3 — Murs verrouillés** : quand le piston pousse un mur vers
  le haut, le mur arrive à ce niveau et y est maintenu par des
  **loquets mécaniques** intégrés. Le piston peut alors redescendre
  sans que le mur retombe.
- **Niveau 4 — Plateau visible** : la surface où sont visibles les
  pions (représentés par les LEDs) et les murs (une fois levés).

**Simplification volontaire** : un mur Quoridor occupe normalement deux
cases adjacentes. Plutôt qu'un mécanisme à mur long, le système utilise
**deux murs d'une case** levés successivement par le piston. La
commande firmware `WALL <H|V> <row> <col>` orchestre les deux levées
consécutives.

**Réinitialisation des murs** : à la fin d'une partie, un mécanisme
manuel (poignée externe) déplace légèrement le niveau 3 pour désengager
tous les loquets et faire retomber les murs au niveau 2 simultanément.

---

## 4. Conception électronique

Source de vérité pour le pinout :
[`../hardware/pinout.md`](../hardware/pinout.md).

### Composants

| Composant | Rôle |
|---|---|
| **ESP32-WROOM** (Freenove DevKit) | Microcontrôleur unique. Gère tout le hardware du plateau via commandes texte reçues du Mac. |
| **2× L298N** | Ponts en H pour les 2 steppers NEMA17 du CoreXY. |
| **2× NEMA17** | Steppers des axes X et Y. |
| **1× SG90** | Servo pour la levée du piston (0° = levé, 180° = repos). |
| **2× fins de course** | Capteurs de homing X et Y (`INPUT_PULLUP`, contact = LOW). |
| **Strip WS2812B 36 LEDs** | Affichage des pions et coups légaux sur la grille 6×6. |
| **Alimentation 12 V** | Puissance moteurs (les LEDs et le servo passent par un step-down 5 V). |

### Câblage

Prototype **breadboard** (la PCB v2 a été abandonnée le 2026-05-19, cf.
[`../decisions.md`](../decisions.md)). Le breadboard est l'état final
pour la démo et la soutenance.

---

## 5. Système de contrôle (cerveau du projet)

### Architecture deux-machines

- **Contrôleur principal — Mac de l'utilisateur (Python 3.12)** :
  exécute le moteur de jeu Quoridor, l'IA Minimax, et la webapp FastAPI
  (port 8000). Source unique de vérité pour les règles et l'état de
  partie.
- **Microcontrôleur temps réel — ESP32-WROOM (Arduino C++)** :
  exécute le sketch
  [`bringup_l298n_complet.cpp`](../../firmware/src/bringup_l298n_complet.cpp).
  Gère le pilotage des moteurs CoreXY, le servo, les fins de course
  (homing) et la strip LED.

### Liaison Mac ↔ ESP32

Deux transports interchangeables, **identiques au niveau protocole** :

- **USB-série 115200 bauds** (mode développement) : câble USB-C direct.
- **Wi-Fi mode AP** (mode démo) : l'ESP32 héberge le réseau
  `Quoridor-ESP32` (WPA2, IP `192.168.4.1`, TCP port 3333). Le Mac s'y
  connecte. Aucun accès Internet requis pour la démo.

Bascule à chaud entre les deux via une route HTTP `POST /api/transport/switch`.

### Justification de la séparation

- Le **Mac** apporte la puissance de calcul pour l'IA, la souplesse du
  développement Python (debug, tests, hot-reload) et l'écosystème
  bureautique pour la démo (navigateur, partage smartphone).
- L'**ESP32** apporte le contrôle hardware fiable (GPIO directs, PWM,
  timing déterministe) et le Wi-Fi natif intégré pour la démo sans
  câble.

Cette répartition a été choisie après pivot le 2026-05-20 (l'architecture
initialement prévue, avec une Raspberry Pi 3/4 comme contrôleur
principal et un protocole UART CRC-16, a été abandonnée pour gain de
souplesse et de fiabilité ; cf. [`../decisions.md`](../decisions.md)).

---

## 6. Pour aller plus loin

| Document | Contenu |
|---|---|
| [`../01_projet.md`](../01_projet.md) | Présentation générale du projet et règles Quoridor |
| [`../02_architecture.md`](../02_architecture.md) | Vue d'ensemble des composants logiciels et matériels |
| [`../decisions.md`](../decisions.md) | Registre des décisions et pivots du projet |
| [`../flowcharts/01_vue_generale.md`](../flowcharts/01_vue_generale.md) | Architecture en diagrammes |
| [`../hardware/pinout.md`](../hardware/pinout.md) | Pinout ESP32 complet |
