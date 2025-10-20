# ****Note de Projet Détaillée – Quoridor Interactif****

## ****1. Contexte et Objectifs du Projet****  
  
* **Projet :** Il s’agit d’un projet de mécatronique mené par une équipe de six élèves.  
* **Concept :** L’équipe recrée le jeu de société « Le Quoridor ».  
* **Objectif Principal :** Concevoir un plateau de jeu intelligent permettant à un joueur humain d’affronter une intelligence artificielle (IA).  
* **Expérience Visée :** Offrir une expérience de jeu plus immersive et dynamique que le jeu classique.  
* **Règles du Jeu :** Les règles fondamentales du Quoridor classique sont conservées sans modification. Le projet se concentre sur l'ajout d'une dimension interactive.

## ****2. Fonctionnement et Interaction Utilisateur (Interface de Jeu)****

Le joueur interagit directement avec le plateau, qui lui fournit un retour visuel et tactile.  
  
* **Double Mode d’Action :** Le plateau dispose d’un bouton dédié pour basculer entre le « mode pion » (pour se déplacer) et le « mode mur » (pour placer un obstacle).  
    * **Déplacement des Pions :**  
        * Le joueur clique sur une seule case pour sélectionner la position désirée de son pion.  
        * Les cases sont interactives et fonctionnent comme des boutons tactiles.  
        * La position *actuelle* des pions est indiquée par des cases lumineuses (LED).  
        * Les cases sur lesquelles le joueur a le droit de se déplacer s’affichent dans une *couleur différente* pour le guider.  
        * Si le déplacement est valide, le jeu l’enregistre. Le pion se déplace alors « virtuellement » , et la case de la nouvelle position change de couleur pour fournir un retour visuel immédiat.  
    * **Placement des Murs (Joueur) :**  
        * Le joueur (en « mode mur ») clique *simultanément* sur deux cases pour indiquer l’emplacement du mur. Ce double clic valide le placement.  
        * Si le placement est autorisé par les règles, le jeu l’enregistre.  
        * Deux murs physiques monteront alors de l’intérieur du plateau pour créer la barrière.  
    * **Placement des Murs (IA) :**  
        * Les murs sont intégrés au plateau, et non des pièces amovibles.  
        * Cette intégration permet à l'IA de placer ses murs de manière fluide et stratégique, sans intervention manuelle du joueur.

## ****3. Conception Mécanique Détaillée (Système des Murs)****

Le mécanisme des murs est géré par un plateau 3D conçu en plusieurs niveaux.  
  
* **Simplification des Murs :** Pour réduire la complexité, les murs physiques ne font qu’une case de long, au lieu des deux cases traditionnelles. Pour simuler un mur classique, le mécanisme soulèvera *deux* de ces murs d’une case.  
    * **Niveau 1 : Système Corps XY**  
        * Ce niveau est composé d’un système corps XY animé par deux moteurs précis.  
        * Ce système permet le déplacement (dans toutes les directions : X et Y) d’un unique piston.  
        * Le rôle du piston est de se positionner sous les murs concernés et de les soulever pour les faire apparaître sur le plateau.  
    * **Niveau 2 : Stockage des Murs**  
        * C’est à ce niveau que tous les murs non posés sont stockés.  
    * **Niveau 3 : Murs Partiellement Visibles (Verrouillage)**  
        * Lorsqu’un mur est poussé par le piston, il monte jusqu’à ce niveau. Les murs ne sont pas complètement visibles à ce stade.  
        * Des « petits loquets ingénieux », intégrés directement aux murs, les maintiennent en place au troisième niveau.  
        * Ce système de verrouillage empêche les murs de redescendre lorsque le piston se retire pour effectuer une autre action.  
    * **Niveau 4 : Partie Visible du Plateau**  
        * C’est le plateau de jeu final, la surface sur laquelle les joueurs interagissent.  
        * C’est là que les pions et les murs (une fois soulevés) sont visibles.  
    * **Mécanisme de Réinitialisation :**  
        * À la fin de la partie, un bouton dédié permet de déplacer légèrement *tout le troisième niveau*.  
        * Ce déplacement désengage les loquets, faisant ainsi retomber tous les murs placés au deuxième niveau (stockage).  
  
## ****4. Conception Électronique et Repérage (Interface de Jeu)****  
  
* **Grille Interactive :** Le système de placement des murs et de déplacement des pions utilise la même interface de cases interactives (tactiles) et de LEDs.  
* **Optimisation du Câblage :** Les cases sont disposées en lignes et en colonnes (matrice).  
* **Objectif de l’Optimisation :** Cette disposition permet de réduire le nombre de fils nécessaires et de simplifier le circuit électrique global.  
* **Repérage :** La position du pion (et des actions) est repérée grâce à un système de coordonnées XY (ligne/colonne).  
  
## ****5. Système de Contrôle (Cerveau du Projet)****  
  
* **Contrôleur Principal :** Le jeu et le plateau sont contrôlés par une carte Raspberry Pi 5.  
* **Rôle du Raspberry Pi 5 :** Cette carte gérera tous les mécanismes complexes ainsi que la partie Intelligence Artificielle (IA).  
* **Flexibilité :** D'autres contrôleurs pourront être définis ultérieurement pour adapter le jeu à différents contextes d'utilisation.
  
  
  
