# 🤝 Guide de Contribution

Merci de votre intérêt pour contribuer au projet Quoridor Interactif ! Ce document vous guidera à travers le processus de contribution.

## 📋 Table des matières

- [Code de conduite](#code-de-conduite)
- [Comment contribuer](#comment-contribuer)
- [Structure du projet](#structure-du-projet)
- [Développement local](#développement-local)
- [Tests](#tests)
- [Style de code](#style-de-code)
- [Processus de Pull Request](#processus-de-pull-request)

---

## 🤝 Code de conduite

Ce projet adhère à un code de conduite simple :
- Soyez respectueux et constructif
- Accueillez les nouvelles idées
- Concentrez-vous sur ce qui est le mieux pour le projet

## 🚀 Comment contribuer

Il existe plusieurs façons de contribuer :

### 🐛 Signaler des bugs
- Vérifiez d'abord que le bug n'a pas déjà été signalé dans les [Issues](https://github.com/Silou1/Projet_mecatronique_I3/issues)
- Créez une nouvelle issue avec le label `bug`
- Décrivez le problème de manière détaillée :
  - Étapes pour reproduire
  - Comportement attendu vs comportement observé
  - Version de Python utilisée
  - Messages d'erreur complets

### ✨ Proposer des fonctionnalités
- Créez une issue avec le label `enhancement`
- Expliquez pourquoi cette fonctionnalité serait utile
- Proposez une implémentation si possible

### 📝 Améliorer la documentation
- Corrections de fautes de frappe
- Clarifications
- Exemples supplémentaires
- Traductions

### 💻 Contribuer au code
Voir les sections ci-dessous pour les détails techniques.

---

## 🏗️ Structure du projet

```
.
├── quoridor_engine/      # Moteur de jeu principal
│   ├── core.py           # Logique du jeu, règles, GameState
│   └── ai.py             # Intelligence artificielle
├── tests/                # Tests unitaires
│   ├── test_core.py
│   ├── test_moves.py
│   ├── test_walls.py
│   └── test_game.py
├── main.py               # Interface console
└── requirements.txt      # Dépendances
```

---

## 🛠️ Développement local

### 1. Fork et Clone

```bash
# Fork le projet sur GitHub, puis :
git clone https://github.com/VOTRE-USERNAME/Projet_mecatronique_I3.git
cd Projet_mecatronique_I3
```

### 2. Créer un environnement virtuel

```bash
# Créer l'environnement
python -m venv venv

# Activer (Linux/Mac)
source venv/bin/activate

# Activer (Windows)
venv\Scripts\activate
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 4. Créer une branche

```bash
git checkout -b feature/ma-nouvelle-fonctionnalite
# ou
git checkout -b fix/correction-bug
```

---

## 🧪 Tests

### Lancer tous les tests

```bash
pytest
```

### Lancer avec couverture

```bash
pytest --cov=quoridor_engine --cov-report=html
```

### Tester un fichier spécifique

```bash
pytest tests/test_core.py
```

### Règles importantes
- ✅ **Tous les tests doivent passer** avant de soumettre une PR
- ✅ **Ajoutez des tests** pour toute nouvelle fonctionnalité
- ✅ **Maintenez la couverture** au-dessus de 90%

---

## 🎨 Style de code

### Conventions Python (PEP 8)

```python
# ✅ Bon
def calculer_distance(position_a: Tuple[int, int], 
                     position_b: Tuple[int, int]) -> int:
    """
    Calcule la distance de Manhattan entre deux positions.
    
    Args:
        position_a: Première position (ligne, colonne)
        position_b: Deuxième position (ligne, colonne)
    
    Returns:
        Distance en nombre de cases
    """
    return abs(position_a[0] - position_b[0]) + abs(position_a[1] - position_b[1])

# ❌ Mauvais
def calc(a,b):
    return abs(a[0]-b[0])+abs(a[1]-b[1])
```

### Règles générales
- **Noms de variables** : `snake_case` en français
- **Noms de classes** : `PascalCase` en anglais
- **Constantes** : `MAJUSCULES_SNAKE_CASE`
- **Docstrings** : Format Google ou NumPy
- **Type hints** : Utilisez-les autant que possible
- **Commentaires** : En français, clairs et concis

### Vérifier le style

```bash
# Installer les outils (optionnel)
pip install flake8 black mypy

# Vérifier
flake8 quoridor_engine/
mypy quoridor_engine/

# Formater automatiquement
black quoridor_engine/
```

---

## 📤 Processus de Pull Request

### 1. Préparer votre branche

```bash
# S'assurer d'être à jour avec main
git checkout main
git pull origin main

# Rebaser votre branche
git checkout feature/ma-fonctionnalite
git rebase main
```

### 2. Vérifications avant PR

- [ ] Tous les tests passent
- [ ] Nouveau code testé (couverture > 90%)
- [ ] Code formaté (PEP 8)
- [ ] Documentation mise à jour
- [ ] Pas de conflits avec main
- [ ] Commits clairs et atomiques

### 3. Créer la Pull Request

```bash
git push origin feature/ma-fonctionnalite
```

Puis sur GitHub :
1. Cliquez sur "Compare & pull request"
2. Remplissez le template de PR :

```markdown
## 📝 Description
Décrivez vos changements en détail.

## 🎯 Type de changement
- [ ] 🐛 Bug fix
- [ ] ✨ Nouvelle fonctionnalité
- [ ] 📝 Documentation
- [ ] 🎨 Style/refactoring
- [ ] ⚡ Performance

## 🧪 Tests
Décrivez les tests ajoutés/modifiés.

## 📸 Captures d'écran (si applicable)
```

### 4. Review et Merge

- Un mainteneur reviewera votre PR
- Répondez aux commentaires et ajustez si nécessaire
- Une fois approuvée, elle sera mergée !

---

## 🎯 Bonnes pratiques des commits

### Format des messages

```
<emoji> <type>: <description courte>

<description détaillée si nécessaire>
```

### Emojis recommandés

| Emoji | Code | Utilisation |
|-------|------|-------------|
| ✨ | `:sparkles:` | Nouvelle fonctionnalité |
| 🐛 | `:bug:` | Correction de bug |
| 📝 | `:memo:` | Documentation |
| 🎨 | `:art:` | Style/formatage |
| ⚡ | `:zap:` | Performance |
| ♻️ | `:recycle:` | Refactoring |
| 🧪 | `:test_tube:` | Tests |
| 🔧 | `:wrench:` | Configuration |
| 🚀 | `:rocket:` | Déploiement |

### Exemples

```bash
git commit -m "✨ Ajouter validation des murs diagonaux"
git commit -m "🐛 Corriger le pathfinding pour les coins"
git commit -m "📝 Améliorer la documentation de l'IA"
git commit -m "⚡ Optimiser l'algorithme Minimax avec cache"
```

---

## 🤔 Questions ?

Si vous avez des questions :
- 💬 Ouvrez une [Discussion](https://github.com/Silou1/Projet_mecatronique_I3/discussions)
- 📧 Contactez via [GitHub](https://github.com/Silou1)

---

## 🙏 Merci !

Merci de prendre le temps de contribuer au projet Quoridor Interactif !

Chaque contribution, aussi petite soit-elle, est précieuse. 💚

