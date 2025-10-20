# 🎮 Quoridor Interactif - Moteur de Jeu Python

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-pytest-orange.svg)](tests/)

> Moteur de jeu Quoridor en Python pur avec Intelligence Artificielle (Minimax + Alpha-Beta) et interface console interactive.
> 
> **Projet mécatronique ICAM 2025-2026** - Année 3

---

## 📖 Table des matières

- [À propos](#à-propos)
- [Fonctionnalités](#fonctionnalités)
- [Installation](#installation)
- [Utilisation](#utilisation)
- [Architecture](#architecture)
- [Tests](#tests)
- [Roadmap](#roadmap)
- [Contributeurs](#contributeurs)

---

## 🎯 À propos

Ce projet consiste à développer un **moteur de jeu Quoridor** complet et modulaire en Python. Le moteur est conçu comme une "boîte noire" indépendante, prête à être intégrée dans différents contextes : interface console, interface graphique, ou plateau physique avec Raspberry Pi.

### Qu'est-ce que Quoridor ?

Quoridor est un jeu de stratégie abstrait pour 2 joueurs où chacun doit atteindre le côté opposé du plateau tout en plaçant des murs pour ralentir l'adversaire.

**Règles principales :**
- Plateau de 9×9 cases
- Chaque joueur a 10 murs à placer
- Un mur fait 2 cases de long
- Interdiction de bloquer complètement un joueur

---

## ✨ Fonctionnalités

### ✅ Déjà implémenté

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
  - Couverture complète avec pytest
  - Tests pour toutes les règles du jeu
  - Tests de l'IA et des cas limites

### 🚧 En développement

- 🔌 **Interface matérielle** (Raspberry Pi 5)
- 🎨 **Interface graphique** (Pygame/Tkinter)
- 📊 **Statistiques de jeu**

---

## 🚀 Installation

### Prérequis

- Python 3.8 ou supérieur
- pip (gestionnaire de paquets Python)

### Étapes

1. **Cloner le repository**
   ```bash
   git clone https://github.com/Silou1/Projet_mecatronique_I3.git
   cd Projet_m-catronique_I3
   ```

2. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

3. **Lancer le jeu**
   ```bash
   python main.py
   ```

---

## 🎮 Utilisation

### Démarrer une partie

```bash
python main.py
```

Vous serez invité à choisir le mode de jeu :
- **1** : Joueur vs Joueur (local)
- **2** : Joueur vs IA (3 niveaux de difficulté)

### Commandes en jeu

| Commande | Description | Exemple |
|----------|-------------|---------|
| `d <case>` | Déplacer votre pion | `d e5` |
| `m <h\|v> <case>` | Placer un mur horizontal (h) ou vertical (v) | `m h e3` |
| `undo` | Annuler le dernier coup | `undo` |
| `moves` ou `?` | Afficher les coups possibles | `moves` |
| `help` ou `h` | Afficher l'aide | `help` |
| `quit` ou `q` | Quitter la partie | `quit` |

### Exemple de partie

```
   a b c d e f g h i
  ━━━━━━━━━━━━━━━━━
1┃· · · · 1 · · · ·┃
 ┃                 ┃
2┃· · · · · · · · ·┃
 ┃                 ┃
...
9┃· · · · 2 · · · ·┃
  ━━━━━━━━━━━━━━━━━

Murs restants: Joueur 1 [10]   Joueur 2 [10]

Tour du Joueur 1. Entrez votre coup: d e2
```

---

## 🏗️ Architecture

```
.
├── main.py                    # Point d'entrée (interface console)
├── requirements.txt           # Dépendances Python
├── README.md                  # Documentation
├── .gitignore                 # Fichiers ignorés par Git
│
├── quoridor_engine/           # Moteur de jeu (module principal)
│   ├── __init__.py            # Exports publics
│   ├── core.py                # Logique centrale (GameState, règles)
│   └── ai.py                  # Intelligence artificielle (Minimax)
│
└── tests/                     # Suite de tests
    ├── test_core.py           # Tests des structures de base
    ├── test_moves.py          # Tests des déplacements
    ├── test_walls.py          # Tests des murs
    ├── test_game.py           # Tests de partie complète
    └── README_TESTS.md        # Documentation des tests
```

### Principes de conception

1. **Modularité** : Le moteur est indépendant de toute interface
2. **Immuabilité** : Chaque coup retourne un nouvel état (facilite l'IA et l'undo)
3. **Testabilité** : Couverture de tests complète pour garantir la robustesse

---

## 🧪 Tests

### Lancer tous les tests

```bash
pytest
```

### Lancer avec couverture de code

```bash
pytest --cov=quoridor_engine --cov-report=html
```

### Lancer des tests spécifiques

```bash
# Tests des déplacements uniquement
pytest tests/test_moves.py

# Tests de l'IA uniquement
pytest tests/test_game.py -k "test_ai"
```

### Statistiques de tests

- **144 tests** au total
- **100%** de couverture du moteur de jeu
- **Tous les cas limites** couverts

---

## 🗺️ Roadmap

### Phase 1 : Moteur de jeu ✅
- [x] Structures de données
- [x] Règles de déplacement
- [x] Validation des murs
- [x] Pathfinding (BFS)
- [x] Détection de victoire

### Phase 2 : IA ✅
- [x] Algorithme Minimax
- [x] Élagage Alpha-Beta
- [x] Fonction d'évaluation
- [x] 3 niveaux de difficulté

### Phase 3 : Interface Console ✅
- [x] Affichage du plateau
- [x] Mode PvP
- [x] Mode PvIA
- [x] Système d'aide

### Phase 4 : Tests ✅
- [x] Tests unitaires (pytest)
- [x] Couverture complète
- [x] Documentation des tests

### Phase 5 : Interface Matérielle 🚧
- [ ] Communication Raspberry Pi 5
- [ ] Contrôle GPIO (LEDs, moteurs)
- [ ] Capteurs tactiles
- [ ] Calibration automatique

### Phase 6 : Améliorations 📋
- [ ] Interface graphique (Pygame)
- [ ] Sauvegarde/chargement de parties
- [ ] Mode multijoueur en réseau
- [ ] Statistiques et classement

---

## 👥 Contributeurs

### Développeur principal
- **Silouane Chaumais** - [@Silou1](https://github.com/Silou1)

### Projet académique
- **École** : ICAM - Institut Catholique d'Arts et Métiers
- **Formation** : Année 3 - Ingénierie Mécatronique
- **Période** : 2025-2026

---

## 📄 License

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

## 🙏 Remerciements

- Jeu Quoridor original par **Mirko Marchesi** (Gigamic)
- Algorithme Minimax inspiré des travaux de **Claude Shannon** (théorie des jeux)
- Communauté Python pour les excellentes bibliothèques (pytest, colorama)

---

## 📞 Contact

Pour toute question ou suggestion :
- **GitHub Issues** : [Créer une issue](https://github.com/Silou1/Projet_mecatronique_I3/issues)
- **Email** : [Contacter via GitHub](https://github.com/Silou1)

---

<div align="center">
  
**⭐ N'oubliez pas de mettre une étoile si ce projet vous plaît ! ⭐**

Made with ❤️ by [@Silou1](https://github.com/Silou1)

</div>
