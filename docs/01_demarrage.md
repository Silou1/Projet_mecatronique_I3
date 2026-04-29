# Démarrage rapide

Comment installer le projet, lancer le jeu en mode console, et résoudre les problèmes courants.

## Prérequis

- **Python 3.10+** (le code utilise des type hints modernes incompatibles avec 3.9)
- **pip** (gestionnaire de paquets Python)
- *Optionnel* : un terminal moderne pour les couleurs (iTerm2, Hyper, terminal macOS récent)

## Installation

```bash
git clone https://github.com/Silou1/Projet_mecatronique_I3.git
cd Projet_mecatronique_I3
pip install -r requirements.txt
```

## Lancement

```bash
python main.py
```

Le programme demande de choisir le mode :
- **1** — Joueur vs Joueur (local)
- **2** — Joueur vs IA (3 niveaux : facile, normal, difficile)

## Commandes en jeu

| Commande | Description | Exemple |
|---|---|---|
| `d <case>` | Déplacer le pion | `d d3` |
| `m <h\|v> <case>` | Placer un mur horizontal (`h`) ou vertical (`v`) | `m h c2` |
| `undo` | Annuler le dernier coup | `undo` |
| `moves` ou `?` | Afficher les coups possibles | `moves` |
| `help` ou `h` | Afficher l'aide | `help` |
| `quit` ou `q` | Quitter | `quit` |

### Notation des cases

- Colonnes : `a` à `f` (gauche → droite)
- Lignes : `1` à `6` (haut → bas)
- Joueur 1 démarre en `d6`, doit atteindre la ligne `1`
- Joueur 2 démarre en `d1`, doit atteindre la ligne `6`

### Aperçu d'une partie

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
```

## Lancer les tests

```bash
pytest                                          # tous les tests (~3,5 min)
pytest --cov=quoridor_engine --cov-report=html  # avec couverture
pytest tests/test_moves.py                      # un fichier précis
pytest tests/test_ai.py -v                      # mode verbeux
```

Plus de détails dans [08_tests.md](08_tests.md).

## Dépannage

### `ModuleNotFoundError: No module named 'quoridor_engine'`

```bash
cd Projet_mecatronique_I3                # bon répertoire
pip install -r requirements.txt          # dépendances installées
export PYTHONPATH="${PYTHONPATH}:$(pwd)" # si le problème persiste
```

### Caractères étranges au lieu des couleurs

```bash
pip install colorama                     # nécessaire sous Windows
```

Sous Linux/macOS, vérifier que le terminal supporte ANSI.

### Tests qui échouent

```bash
python --version                         # vérifier Python ≥ 3.10
pip install --upgrade -r requirements.txt
pytest -v                                # mode verbeux pour identifier le test fautif
```

### IA trop lente

- Choisir le niveau `facile` au lancement
- Sur Raspberry Pi, réduire la profondeur dans [quoridor_engine/ai.py](../quoridor_engine/ai.py)

### `ValueError: Le joueur n'a plus de murs`

Vous avez déjà placé vos 6 murs. Utilisez `moves` pour voir les déplacements possibles.

### `ValueError: Ce mur bloquerait complètement un joueur`

Règle Quoridor : un mur ne peut pas couper totalement le chemin de l'adversaire. Essayez un autre emplacement.

---

**Pour aller plus loin** : [02_architecture.md](02_architecture.md) (vue d'ensemble du projet hardware + software).
