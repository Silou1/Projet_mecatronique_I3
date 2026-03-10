# 🎮 Quoridor Interactif - Moteur de Jeu Python

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://github.com/Silou1/Projet_mecatronique_I3/actions/workflows/tests.yml/badge.svg)](https://github.com/Silou1/Projet_mecatronique_I3/actions)
[![Codecov](https://codecov.io/gh/Silou1/Projet_mecatronique_I3/branch/main/graph/badge.svg)](https://codecov.io/gh/Silou1/Projet_mecatronique_I3)

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
- Plateau de 6×6 cases
- Chaque joueur a 6 murs à placer
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

- Python 3.10 ou supérieur
- pip (gestionnaire de paquets Python)

### Étapes

1. **Cloner le repository**
   ```bash
   git clone https://github.com/Silou1/Projet_mecatronique_I3.git
   cd Projet_mecatronique_I3
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
python3 main.py
```

Vous serez invité à choisir le mode de jeu :
- **1** : Joueur vs Joueur (local)
- **2** : Joueur vs IA (3 niveaux de difficulté)

### Commandes en jeu

| Commande | Description | Exemple |
|----------|-------------|---------|
| `d <case>` | Déplacer votre pion | `d d3` |
| `m <h\|v> <case>` | Placer un mur horizontal (h) ou vertical (v) | `m h c2` |
| `undo` | Annuler le dernier coup | `undo` |
| `moves` ou `?` | Afficher les coups possibles | `moves` |
| `help` ou `h` | Afficher l'aide | `help` |
| `quit` ou `q` | Quitter la partie | `quit` |

### Exemple de partie

```
   a b c d e f
  ━━━━━━━━━━━
1┃· · · 2 · ·┃
 ┃           ┃
2┃· · · · · ·┃
 ┃           ┃
3┃· · · · · ·┃
 ┃           ┃
4┃· · · · · ·┃
 ┃           ┃
5┃· · · · · ·┃
 ┃           ┃
6┃· · · 1 · ·┃
  ━━━━━━━━━━━

Murs restants: Joueur 1 [6]   Joueur 2 [6]

Tour du Joueur 1. Entrez votre coup: d d5
```

---

## 💻 Utilisation Programmatique

Vous pouvez utiliser le moteur Quoridor dans vos propres projets Python :

### Exemple basique

```python
from quoridor_engine import QuoridorGame

# Créer une nouvelle partie
game = QuoridorGame()

# Jouer un coup (déplacement vers le haut)
game.play_move(('deplacement', (4, 3)))

# Jouer un mur horizontal
game.play_move(('mur', ('h', 4, 3, 2)))

# Vérifier si la partie est terminée
is_over, winner = game.is_game_over()
if is_over:
    print(f"Le joueur {winner} a gagné !")
```

### Exemple avec l'IA

```python
from quoridor_engine.core import QuoridorGame
from quoridor_engine.ai import AI

# Créer une partie
game = QuoridorGame()

# Tour du joueur humain (J1 avance vers le haut)
game.play_move(('deplacement', (4, 3)))

# Tour de l'IA (difficulé normale)
ia = AI('j2', difficulty='normal')
ai_move = ia.find_best_move(game.get_current_state())
game.play_move(ai_move)
```

### Exemple avec annulation

```python
from quoridor_engine import QuoridorGame

game = QuoridorGame()

# Jouer plusieurs coups
game.play_move(('deplacement', (4, 3)))
game.play_move(('deplacement', (1, 3)))
game.play_move(('mur', ('h', 4, 3, 2)))

# Annuler le dernier coup
game.undo_move()

# Voir l'historique
print(f"Nombre de coups dans l'historique : {len(game._history)}")
```

### Obtenir les coups possibles

```python
from quoridor_engine import QuoridorGame

game = QuoridorGame()

# Obtenir tous les coups possibles (déplacements) pour le joueur actuel
possible_moves = game.get_possible_moves()

print(f"Nombre de déplacements possibles : {len(possible_moves)}")
for move_type, move_data in possible_moves:
    print(f"  - {move_type}: {move_data}")
```

### Vérifier l'état du jeu

```python
from quoridor_engine import QuoridorGame

game = QuoridorGame()

# Accéder à l'état actuel
state = game.get_current_state()

print(f"Position joueur 1 : {state.player_positions['j1']}")
print(f"Position joueur 2 : {state.player_positions['j2']}")
print(f"Murs restants J1 : {state.player_walls['j1']}")
print(f"Murs restants J2 : {state.player_walls['j2']}")
print(f"Tour actuel : {state.current_player}")
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
    ├── test_ai.py             # Tests de l'Intelligence Artificielle
    └── README.md              # Documentation des tests
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
pytest tests/test_ai.py

# Tests du moteur de jeu uniquement
pytest tests/test_core.py tests/test_moves.py tests/test_walls.py
```

### Statistiques de tests

- **90 tests** au total (100% de réussite)
- **82%** de couverture globale
  - `core.py` : 75% (moteur de jeu)
  - `ai.py` : 92% (intelligence artificielle)
- **Tests complets** : règles, déplacements, murs, victoire, IA, performance
- **Temps d'exécution** : ~3,5 minutes

📖 Voir [tests/README.md](tests/README.md) pour plus de détails

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

## 🔧 Troubleshooting

### Problèmes courants et solutions

#### 1. Erreur d'importation du module

**Problème :** `ModuleNotFoundError: No module named 'quoridor_engine'`

**Solution :**
```bash
# Assurez-vous d'être dans le bon répertoire
cd Projet_mecatronique_I3

# Installez les dépendances
pip install -r requirements.txt

# Si le problème persiste, ajoutez le répertoire au PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

#### 2. Les couleurs ne s'affichent pas correctement

**Problème :** Caractères étranges au lieu des couleurs dans le terminal

**Solution :**
```bash
# Sur Windows, installez colorama
pip install colorama

# Sur Linux/Mac, utilisez un terminal moderne (iTerm2, Hyper, etc.)
```

#### 3. Les tests échouent

**Problème :** Certains tests ne passent pas

**Solution :**
```bash
# Vérifiez la version de Python (minimum 3.10)
python --version

# Réinstallez les dépendances
pip install --upgrade -r requirements.txt

# Lancez les tests avec verbose
pytest -v
```

#### 4. L'IA est trop lente

**Problème :** L'IA met trop de temps à calculer son coup

**Solution :**
- Réduisez la profondeur de recherche dans `ai.py`
- Choisissez le niveau "facile" pour un jeu plus rapide
- Sur un Raspberry Pi, optimisez les paramètres de profondeur

#### 5. Erreur "No walls left"

**Problème :** `ValueError: Le joueur n'a plus de murs`

**Solution :**
- Vérifiez que vous n'avez pas déjà placé vos 6 murs
- Utilisez la commande `moves` pour voir vos options disponibles

#### 6. Erreur de chemin bloqué

**Problème :** `ValueError: Ce mur bloquerait complètement un joueur`

**Solution :**
- Cette règle empêche de bloquer totalement un joueur
- Essayez un autre emplacement pour votre mur
- Le jeu vérifie automatiquement qu'un chemin reste accessible

#### 7. Problèmes de performance sur Raspberry Pi

**Problème :** Le jeu est lent sur Raspberry Pi

**Solution :**
```bash
# Utilisez Python 3.10+ pour de meilleures performances
# Réduisez la profondeur de l'IA
# Désactivez les tests de couverture en production
```

### Besoin d'aide supplémentaire ?

Si votre problème n'est pas listé ici :
1. Consultez les [Issues GitHub](https://github.com/Silou1/Projet_mecatronique_I3/issues)
2. Créez une nouvelle issue avec le template approprié
3. Incluez :
   - Version de Python (3.10+)
   - Système d'exploitation
   - Message d'erreur complet
   - Étapes pour reproduire le problème

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
