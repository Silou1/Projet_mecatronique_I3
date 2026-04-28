# Changelog

Tous les changements notables de ce projet seront documentés dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet adhère au [Semantic Versioning](https://semver.org/lang/fr/).

## [Non publié]

### Ajouté
- Audit complet du PCB v2 (hardware/AUDIT_PCB_V2.md)
- Guide de modifications PCB pour EasyEDA (Word, envoye a Jean)
- Diagrammes Mermaid pour l'architecture (docs/flowcharts/)
- Documentation du jeu et de l'IA (docs/comprendre_le_jeu.md)
- Configuration CI/CD avec GitHub Actions

### Modifié
- Passage du plateau de 9x9 a 6x6 (2 joueurs, 6 murs chacun)
- 90 tests unitaires, 82% de couverture
- Correction commentaire main.py (taille plateau 9 → 6)
- Nettoyage des fichiers electronique obsoletes (ancien audit v1)
- Reorganisation du repo : regroupement docs/ et hardware/, suppression des dossiers Schema_PCB/ et electronique/

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
  - 90 tests unitaires complets
  - 82% de couverture du moteur principal (core.py)
  - Tests pour toutes les règles du jeu
  - Tests de l'IA et des cas limites

- 📚 **Documentation**
  - README complet avec exemples
  - Guide de contribution (CONTRIBUTING.md)
  - Documentation détaillée des tests
  - Note de projet pour l'équipe

### En cours de développement
- 🔌 Interface materielle ESP32-WROOM + Raspberry Pi (PCB en cours)
- 📡 Communication UART ESP32 <-> RPi

---

## Types de changements

- **Ajouté** : pour les nouvelles fonctionnalités
- **Modifié** : pour les changements aux fonctionnalités existantes
- **Déprécié** : pour les fonctionnalités qui seront bientôt supprimées
- **Supprimé** : pour les fonctionnalités supprimées
- **Corrigé** : pour les corrections de bugs
- **Sécurité** : en cas de vulnérabilités

