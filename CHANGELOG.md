# Changelog

Tous les changements notables de ce projet seront documentés dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet adhère au [Semantic Versioning](https://semver.org/lang/fr/).

## [Non publié]

### Ajouté
- Configuration CI/CD avec GitHub Actions
- Support de Python 3.10 à 3.12
- Cache des dépendances pip dans le workflow CI/CD
- Badges dynamiques pour les tests et la couverture de code
- Documentation complète du projet (README, CONTRIBUTING, tests)

### Modifié
- Correction des URLs du repository
- Amélioration de la structure de la documentation
- Nettoyage du formatage de la note de projet

## [1.0.0] - 2025-10-20

### Ajouté
- 🎲 **Moteur de jeu complet**
  - Gestion de l'état du jeu (positions, murs, tours)
  - Validation complète des coups (déplacements et murs)
  - Détection des situations de victoire
  - Historique des coups avec fonction "undo"
  
- 🤖 **Intelligence Artificielle**
  - Algorithme Minimax avec élagage Alpha-Beta
  - 3 niveaux de difficulté (Facile, Normal, Difficile)
  - Fonction d'évaluation heuristique sophistiquée
  - Pathfinding optimisé (BFS)

- 🖥️ **Interface Console**
  - Affichage ASCII avec couleurs (via colorama)
  - Mode Joueur vs Joueur
  - Mode Joueur vs IA
  - Commandes intuitives et aide interactive

- 🧪 **Tests Unitaires**
  - 65 tests unitaires complets
  - 75% de couverture du moteur principal (core.py)
  - Tests pour toutes les règles du jeu
  - Tests de l'IA et des cas limites

- 📚 **Documentation**
  - README complet avec exemples
  - Guide de contribution (CONTRIBUTING.md)
  - Documentation détaillée des tests
  - Note de projet pour l'équipe

### En cours de développement
- 🔌 Interface matérielle (Raspberry Pi 5)
- 🎨 Interface graphique (Pygame/Tkinter)
- 📊 Statistiques de jeu

---

## Types de changements

- **Ajouté** : pour les nouvelles fonctionnalités
- **Modifié** : pour les changements aux fonctionnalités existantes
- **Déprécié** : pour les fonctionnalités qui seront bientôt supprimées
- **Supprimé** : pour les fonctionnalités supprimées
- **Corrigé** : pour les corrections de bugs
- **Sécurité** : en cas de vulnérabilités

