# Sous-système LED — Design

| | |
|---|---|
| **Date** | 2026-05-21 |
| **Statut** | Validé par l'utilisateur, prêt pour implémentation |
| **Phase** | 5b — LEDs (post-Wi-Fi, pré-démo finale) |
| **Hors scope** | Animations (transitions, pulse, victoire) ; affichage des murs sur LEDs ; mode fond blanc faible (option β). Le sous-système boutons mentionné initialement comme « plus tard » a été **abandonné définitivement** le 2026-05-21 — cf. `docs/decisions.md`. |

## Objectif

Donner un miroir lumineux du jeu sur le plateau physique : à chaque mouvement de pion,
les LEDs du plateau 6×6 indiquent les positions des deux joueurs (J1 humain bleu,
J2 IA rouge). En bonus si temps avant démo, indiquer en cyan les cases atteignables
par le joueur courant.

Le sous-système doit s'intégrer **sans rupture** dans :
- l'architecture existante (Mac = cerveau, ESP32 = actionneur bête) ;
- le protocole texte ligne par ligne (USB et Wi-Fi identiques) ;
- le sketch monolithique `bringup_l298n_complet.cpp` (pas de split `.h/.cpp`).

## Critères de succès

À la fin de l'implémentation :

1. **`pytest -m "not devkit"`** vert — tests unitaires de `webapp/leds.py` à 100 %.
2. **`pytest -m devkit_serial`** vert — au moins un test devkit qui envoie
   `LED 0 0 0 255` + `LEDSHOW` via USB et vérifie la réponse `OK`.
3. En partie réelle (webapp + ESP32 en USB ou Wi-Fi), à chaque déplacement de
   pion les LEDs correspondantes s'allument/s'éteignent en < 100 ms perçues.
4. Coupure puis reconnexion de l'ESP32 pendant une partie : les LEDs reviennent
   automatiquement à l'état attendu sans intervention utilisateur.
5. La doc projet (`docs/02_architecture.md`, `docs/06_firmware.md`,
   `docs/07_protocole.md`, `docs/hardware/pinout.md`) est mise à jour.

## 1. Scope et palette

### Périmètre obligatoire (P0)

- 36 LEDs WS2812B (NeoPixel) câblées en serpentin sur le plateau, entrée DIN
  en bas-gauche, alternance gauche↔droite par rangée physique.
- Affichage de la **position des deux pions** :
  - J1 (humain) : bleu `(0, 0, 255)`
  - J2 (IA) : rouge `(255, 0, 0)`
- Fond par défaut : **éteint** `(0, 0, 0)` pour les 34 autres LEDs.
- Pas d'animation. État statique entre deux mutations de `GameState`.
- Mise à jour automatique sur chaque mutation (déplacement, nouvelle partie,
  undo, fin de partie).

### Périmètre bonus si temps (P1)

- Affichage des **coups légaux** du joueur courant : cyan dim `(0, 64, 64)`.
- Activable / désactivable runtime via une option `RenderOptions.show_legal_moves`.

### Hors scope

- Animations (transitions fade, pulse pendant le tour, animation de victoire).
- Indication des murs sur les LEDs adjacentes.
- Mode fond blanc faible.
- Tout ce qui relève des boutons : **système abandonné définitivement** le
  2026-05-21 (cf. `docs/decisions.md`). L'interaction se fait via la webapp,
  pas par le plateau.

## 2. Hardware et câblage

### Affectation GPIO

| Signal | GPIO | Rôle |
|---|---|---|
| LED_DIN | **15** | Sortie data du strip WS2812B (entrée DIN de la 1ʳᵉ LED) |

**Justification GPIO 15** (validé via NotebookLM, datasheet ESP32) :

- Strapping pin avec pull-up interne (HIGH par défaut au boot). Aucun risque
  de bloquer le démarrage.
- Effet secondaire **uniquement si tirée LOW au boot** : désactivation des
  logs UART0 boot. Cas qui ne se présente pas car la pin n'est configurée
  qu'après `Serial.begin()` dans `setup()`.
- ADC2_CH3 mais usage purement digital → aucun conflit avec le Wi-Fi actif.
- Compatible avec le RMT de l'ESP32 (DMA hardware) si on bascule un jour
  de `Adafruit_NeoPixel` vers `FastLED`.

### Alimentation

```
Alim générale 12V (existante)
   │
   ├─── 12V → moteurs CoreXY (existant)
   │
   └─── Step-down 12V → 5V (existant chez l'utilisateur)
           │
           ├─── 5V → VDD du strip WS2812B (1ʳᵉ LED)
           │
           └─── GND → commun avec ESP32 GND (impératif)
```

**Points critiques** :

1. **GND commun obligatoire** entre ESP32 et le 5V du strip. Sans référence
   commune, le signal data est aléatoire.
2. **Ne jamais alimenter les 36 LEDs depuis le 5V de l'ESP32**. Le rail 5V
   interne supporte ~500 mA ; 36 LEDs WS2812 à pleine intensité tirent
   jusqu'à 2.16 A. → toujours via le step-down 5V dédié.
3. **Bench USB-C** : si les 36 LEDs sont déjà câblées sur le plateau avec
   le step-down 5V externe, on peut tester en USB sans souci de courant —
   l'ESP32 ne fournit que le signal data sur GPIO 15.

### Limite logicielle d'intensité

Le firmware applique `strip.setBrightness(102)` (40 % de 255) au boot.

- En partie typique : 2 pions + ~5 coups légaux = 7 LEDs max allumées.
  À 100 % blanc équivalent ce serait 420 mA, à 40 % ce sera 168 mA.
  Aucune chance de saturer l'alim.
- Les couleurs gardent leur saturation (bleu reste bleu vif), seule la
  luminosité globale est plafonnée.
- Évite la fatigue visuelle à travers le plexi transparent.
- Ajustable runtime via la commande `LEDBRIGHT <0..255>`.

### Composants additionnels (recommandés, non bloquants)

| Composant | Position | Pourquoi | Plan |
|---|---|---|---|
| Résistance **330 Ω** | en série entre GPIO 15 et DIN de la 1ʳᵉ LED | Limite les transitoires, protège le buffer interne | Recommandé si fil > 20 cm |
| Condensateur **1000 µF / 10V** | entre 5V et GND, au plus près de la 1ʳᵉ LED | Lisse les pics de courant lors des changements simultanés | Recommandé si l'alim n'est pas déjà filtrée |
| Diode **1N4148** | en série sur le rail +5V de la 1ʳᵉ LED uniquement (anode côté alim) | Plan B si scintillement : VDD chute à ~4.3V, seuil VIH passe à 3.0V, signal 3.3V devient nominal | Optionnel, à ajouter si scintillement observé |
| Level shifter **74HCT125** | entre GPIO 15 et DIN | Plan B alternatif à la diode, plus propre | Optionnel, dernier recours si la diode ne suffit pas |

### Précautions de manipulation

- **Toujours débrancher l'alim 5V avant de manipuler les fils du strip.**
  Les WS2812B sont sensibles à l'ESD, un branchement à chaud peut griller
  la 1ʳᵉ LED.
- **Ordre de mise sous tension** : 5V du strip avant (ou en même temps que)
  l'ESP32. Sinon l'ESP32 envoie du data sur DIN sans VDD côté LED, ce qui
  force un courant via le buffer interne de la LED.

## 3. Architecture logicielle

### Vue d'ensemble

```
┌─────────────────────────────────────────────────────────┐
│  Mac — webapp/                                          │
│                                                         │
│  ┌──────────────┐    ┌──────────────────────────────┐   │
│  │ service.py   │───▶│  leds.py  (NOUVEAU)          │   │
│  │ (orchest.)   │    │   - engine_to_strip_index    │   │
│  │              │    │   - render_state             │   │
│  │              │    │   - LedRenderer              │   │
│  └──────────────┘    └────────────┬─────────────────┘   │
│                                   │ diff + commandes   │
│                                   ▼                     │
│                      ┌──────────────────────────────┐   │
│                      │  plateau.py (PlateauBridge)  │   │
│                      │   - send LED commands        │   │
│                      └────────────┬─────────────────┘   │
└───────────────────────────────────┼─────────────────────┘
                                    │ texte ligne par ligne
                                    ▼
┌─────────────────────────────────────────────────────────┐
│  ESP32 — bringup_l298n_complet.cpp                      │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  traiter(cmd, Stream*) — dispatch existant       │   │
│  │   ├─ PING/WALL/HOME/... (existant)               │   │
│  │   └─ LED/LEDSHOW/LEDCLEAR/LEDBRIGHT (NOUVEAU)    │   │
│  └──────────────────┬───────────────────────────────┘   │
│                     ▼                                   │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Adafruit_NeoPixel.show() → push sur GPIO 15     │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Choix d'architecture : firmware "bête", intelligence côté Python

L'intelligence du rendu LED vit **entièrement côté Mac** (option 1 du
brainstorm). Le firmware ne fait qu'écrire dans un buffer et pousser le
buffer sur le strip à la demande. Raisons :

1. **Cohérence** avec le pattern existant (ESP32 = actionneur, connaît
   les coordonnées physiques pas les règles du jeu).
2. **Évolutivité** : tout ajout (animations, modes, couleurs personnalisées)
   se fait côté Python sans reflasher l'ESP32.
3. **Debug** : on peut tester chaque LED individuellement au moniteur série
   en tapant `LED 0 0 0 255` puis `LEDSHOW`.
4. **Surcoût négligeable** : ~250 bytes par tour de jeu sur Wi-Fi local,
   < 10 ms aller-retour.

### Choix de librairie firmware

**`Adafruit_NeoPixel`** plutôt que `FastLED` :

- API simple, doc claire, parfaitement adapté à notre cas (un `show()` par
  tour de jeu).
- `FastLED` utiliserait le RMT (DMA) et serait théoriquement plus propre
  côté interrupts Wi-Fi, mais bénéfice nul à notre fréquence d'usage
  (un `show()` par minute en moyenne).
- Lib ajoutée dans `firmware/platformio.ini` : `adafruit/Adafruit NeoPixel`.

Configuration : `NEO_GRB + NEO_KHZ800` (ordre canonique pour WS2812B,
timing standard 800 kHz).

### Responsabilités du module `webapp/leds.py`

Trois pièces internes :

1. **`engine_to_strip_index(row, col) → int`** : fonction pure de mapping.
   Convertit une coordonnée engine en index 0-35 sur le strip. Détaillée
   en section 5.

2. **`render_state(state, options) → list[LedColor]`** : fonction pure
   de rendu. Prend l'état complet du jeu et retourne la liste des 36
   couleurs cible (fond inclus). Aucun side effect. Détaillée en section 5.

3. **`LedRenderer`** : classe stateful qui maintient le frame précédent,
   reçoit un nouveau frame, calcule le **diff**, et envoie uniquement les
   LEDs modifiées via `PlateauBridge.send_line()`.

### Modifications minimales dans `service.py`

Hook unique : à chaque mutation de `GameState` (déplacement, mur, nouvelle
partie, undo, fin de partie), appel à `self.led_renderer.update(self.state)`
après les appels existants à `plateau_bridge.forward()`. Une seule ligne
ajoutée à 4-5 endroits.

### Modifications minimales dans `bringup_l298n_complet.cpp`

1. **Include `Adafruit_NeoPixel.h`**.
2. **Globale** :
   ```cpp
   #define LED_PIN 15
   #define LED_COUNT 36
   Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);
   ```
3. **`setup()`** (au tout début, avant le homing) :
   ```cpp
   strip.begin();
   strip.setBrightness(102);  // 40%
   strip.clear();
   strip.show();
   ```
4. **`traiter()`** : ajout du dispatch pour `LED`, `LEDSHOW`, `LEDCLEAR`,
   `LEDBRIGHT`. Détail en section 4.

**Pas de nouveau fichier .cpp/.h.** On reste sur le sketch monolithique
conformément au pattern existant.

### Stratégie de diff côté Python

Un tour de jeu typique change 1 à 7 LEDs (1 pion bouge + 5 coups légaux
changent). Sans diff on enverrait 36 commandes `LED`. Avec diff : 5-7
commandes. Latence Wi-Fi divisée par 5.

Implémentation : `LedRenderer` garde `self._last_frame: list[LedColor]`.
À chaque `update()`, on compare le nouveau frame au précédent et on
n'envoie que les indices dont la couleur a changé, suivis d'un seul
`LEDSHOW` atomique.

### Gestion de la reconnexion

Si le `PlateauBridge` perd la connexion (Wi-Fi coupé, ESP32 reset) et
revient, le buffer côté firmware est revenu à zéro après reset mais le
`LedRenderer` garde son `last_frame`. Solution :

- `LedRenderer` expose une méthode `on_reconnect()` qui force un re-push
  complet (`LEDCLEAR` + toutes les LEDs allumées du `last_frame` + `LEDSHOW`).
- Hook attaché à l'événement de reconnexion existant de `PlateauBridge`.

### Comportement si bridge indisponible

Si `bridge.available` est `False` (mode autonome ou ESP32 hors ligne),
`LedRenderer.update()` est un **no-op silencieux**. Comportement cohérent
avec le reste de la webapp (fallback gracieux, partie continue côté UI).

## 4. Protocole texte — nouvelles commandes

Toutes les commandes suivent le pattern existant : texte ligne par ligne
terminée par `\n`, identique sur USB et Wi-Fi, UTF-8, casse insensible
côté parser, tokens séparés par espaces.

### Commandes Mac → ESP32

| Commande | Réponse | Description |
|---|---|---|
| `LED <idx> <r> <g> <b>` | `OK` ou `ERR <msg>` | Met à jour le pixel `idx` dans le buffer firmware. **Ne push pas** sur le strip. |
| `LEDSHOW` | `OK` | Push atomique du buffer interne vers le strip (`strip.show()`). |
| `LEDCLEAR` | `OK` | Buffer remis à 0 + push immédiat. Toutes les LEDs éteintes. |
| `LEDBRIGHT <0..255>` | `OK` ou `ERR <msg>` | Modifie la luminosité globale. Persistant jusqu'au reset. Défaut : 102 (40 %). |

### Bornes et validations

| Champ | Type | Bornes | Erreur si dépassement |
|---|---|---|---|
| `idx` | entier | `[0..35]` | `ERR LED borne : idx=X hors [0..35]` |
| `r`, `g`, `b` | entier | `[0..255]` | `ERR LED borne : composante=X hors [0..255]` |
| `LEDBRIGHT` | entier | `[0..255]` | `ERR LEDBRIGHT borne : X hors [0..255]` |
| Syntaxe `LED` | — | 3 args obligatoires | `ERR syntaxe : LED <idx> <r> <g> <b>` |

### Exemple de session (un tour de jeu typique avec P1 actif)

```
> LED 3 0 0 0          ← éteindre l'ancienne position J1 engine (5,3)
< OK
> LED 8 0 0 255        ← allumer la nouvelle position J1 engine (4,3) bleu
< OK
> LED 7 0 64 64        ← case atteignable engine (4,4) cyan dim
< OK
> LED 9 0 64 64        ← case atteignable engine (4,2) cyan dim
< OK
> LED 15 0 64 64       ← case atteignable engine (3,3) cyan dim
< OK
> LEDSHOW              ← push atomique
< OK
```

Total : 6 lignes, ~80 bytes, ~10 ms aller-retour Wi-Fi local.

### Pourquoi séparer `LED` (set buffer) et `LEDSHOW` (push)

Permet de changer plusieurs LEDs **sans flicker intermédiaire** : on
prépare tout dans le buffer, puis on commit en une fois. Sans cette
séparation, chaque commande déclencherait un push et on verrait
l'animation se faire LED par LED.

### Extensibilité future (hors scope actuel)

Le protocole peut être étendu sans casser l'existant :

- `LEDFILL <r> <g> <b>` : remplir toutes les LEDs d'une couleur (utile
  pour Option β fond blanc faible).
- `LEDANIM <type>` : animations préprogrammées côté firmware.
- `LEDMODE <off|game|debug>` : modes d'usage.

## 5. Mapping engine ↔ strip et fonction de rendu

### Conventions de coordonnées

| Système | Origine | Convention |
|---|---|---|
| **Engine** (`quoridor_engine/core.py`) | `(0, 0)` en **haut-gauche** | `(row, col)` ; J1 démarre `(5, 3)` bas-centre ; J2 démarre `(0, 3)` haut-centre |
| **Physique** (plateau) | `(0, 0)` en **bas-gauche** | `(row_phys, col_phys)` ; row_phys = 0 en bas, croît vers le haut |
| **Strip** | LED 0 = entrée DIN bas-gauche | index 0..35 selon l'ordre du serpentin (alternance pair/impair) |

### Algorithme `engine_to_strip_index`

```python
def engine_to_strip_index(row: int, col: int) -> int:
    """Convertit une coordonnée engine (row, col) en index 0-35 sur le strip.

    Engine : row=0 en haut, row=5 en bas, col=0 à gauche.
    Strip  : LED 0 en bas-gauche, serpentin alterné par rangée physique.
    """
    row_phys = 5 - row              # inversion verticale engine -> physique
    if row_phys % 2 == 0:           # rangée paire physique : gauche -> droite
        return row_phys * 6 + col
    else:                           # rangée impaire physique : droite -> gauche
        return row_phys * 6 + (5 - col)
```

### Vérification du mapping

| Engine | Position visuelle | row_phys | parité | Calcul | Index attendu |
|---|---|---|---|---|---|
| `(5, 0)` | bas-gauche (entrée DIN) | 0 | paire | 0×6+0 | **0** |
| `(5, 5)` | bas-droite | 0 | paire | 0×6+5 | **5** |
| `(0, 5)` | haut-droite | 5 | impaire | 5×6+(5−5) | **30** |
| `(0, 0)` | haut-gauche (sortie strip) | 5 | impaire | 5×6+(5−0) | **35** |
| `(5, 3)` | bas-centre (départ J1) | 0 | paire | 0×6+3 | **3** |
| `(0, 3)` | haut-centre (départ J2) | 5 | impaire | 5×6+(5−3) | **32** |

### Palette de couleurs (P0 + P1)

```python
@dataclass(frozen=True)
class LedColor:
    r: int
    g: int
    b: int

COLOR_OFF        = LedColor(0,   0,   0  )  # fond éteint
COLOR_PLAYER_ONE = LedColor(0,   0,   255)  # J1 humain : bleu
COLOR_PLAYER_TWO = LedColor(255, 0,   0  )  # J2 IA : rouge
COLOR_LEGAL_MOVE = LedColor(0,   64,  64 )  # coups légaux : cyan dim (P1)
```

Les valeurs sont **nominales** (avant atténuation). Le firmware applique
`setBrightness(102)` qui scale tout par 40 %. Pour changer la luminosité
de démo, ajuster le seul paramètre `LEDBRIGHT` côté firmware, pas la
palette.

### Algorithme `render_state`

```python
@dataclass(frozen=True)
class RenderOptions:
    show_legal_moves: bool = False  # active P1 si True

def render_state(state: GameState, opts: RenderOptions) -> list[LedColor]:
    """Convertit l'état de jeu en frame complète (36 couleurs).

    Pure : aucun side effect, sortie totalement déterminée par les inputs.
    """
    frame = [COLOR_OFF] * 36

    # P1 (bonus) : coups légaux, peints EN PREMIER (écrasés par les pions ensuite)
    if opts.show_legal_moves:
        for row, col in state.get_legal_moves(state.current_player):
            frame[engine_to_strip_index(row, col)] = COLOR_LEGAL_MOVE

    # P0 : pions, peints EN DERNIER pour écraser tout coup légal au même endroit
    r1, c1 = state.player_positions[PLAYER_ONE]
    r2, c2 = state.player_positions[PLAYER_TWO]
    frame[engine_to_strip_index(r1, c1)] = COLOR_PLAYER_ONE
    frame[engine_to_strip_index(r2, c2)] = COLOR_PLAYER_TWO

    return frame
```

**Note** : le nom exact de la méthode pour lister les coups légaux
(`get_legal_moves`, `legal_moves`, …) est à confirmer pendant
l'implémentation contre `quoridor_engine/core.py`. C'est un détail
d'API, pas de design.

### Classe `LedRenderer`

```python
class LedRenderer:
    def __init__(self, bridge: PlateauBridge):
        self._bridge = bridge
        self._last_frame: list[LedColor] | None = None
        self._options = RenderOptions(show_legal_moves=False)

    def update(self, state: GameState) -> None:
        """Calcule le nouveau frame et envoie le diff au firmware."""
        if not self._bridge.available:
            return  # no-op silencieux : mode autonome ou bridge HS
        new_frame = render_state(state, self._options)
        if self._last_frame is None:
            self._send_full_frame(new_frame)
        else:
            self._send_diff(self._last_frame, new_frame)
        self._last_frame = new_frame

    def on_reconnect(self) -> None:
        """Re-push complet après reconnexion (le firmware a rebooté, buffer à 0)."""
        if self._last_frame is not None:
            self._send_full_frame(self._last_frame)

    def _send_full_frame(self, frame: list[LedColor]) -> None:
        self._bridge.send_line("LEDCLEAR")
        for idx, color in enumerate(frame):
            if color != COLOR_OFF:
                self._bridge.send_line(f"LED {idx} {color.r} {color.g} {color.b}")
        self._bridge.send_line("LEDSHOW")

    def _send_diff(self, old: list[LedColor], new: list[LedColor]) -> None:
        changed = [(idx, c) for idx, (o, c) in enumerate(zip(old, new)) if o != c]
        if not changed:
            return
        for idx, color in changed:
            self._bridge.send_line(f"LED {idx} {color.r} {color.g} {color.b}")
        self._bridge.send_line("LEDSHOW")
```

### Tests prévus

**`tests/test_leds.py`** (sans hardware) :

1. **`engine_to_strip_index` exhaustif** : on s'assure que chaque (row, col)
   donne un index unique et que les 6 valeurs de la table de vérification
   (4 coins + 2 départs de pions) matchent.
2. **`render_state` sur 5-6 GameState typiques** : position de départ,
   après 1 coup J1, après 1 coup J2, après une dizaine de coups, partie
   finie. On compare au frame attendu hardcodé.
3. **`LedRenderer.update` séquentiel** : on mocke `PlateauBridge.send_line`,
   on appelle `update` 3 fois sur 3 états différents, on vérifie que la
   séquence de lignes correspond au diff.
4. **`LedRenderer.on_reconnect`** : on vérifie qu'un re-push complet est
   émis.
5. **`LedRenderer.update` avec bridge indisponible** : on vérifie le no-op
   silencieux.

**`tests/devkit/test_leds_serial.py`** (devkit USB, ESP32 branché) :

1. Test du parser : envoyer `LED 0 0 0 255` puis `LEDSHOW`, attendre `OK`.
2. Test des bornes : envoyer `LED 99 0 0 0`, attendre `ERR LED borne ...`.
3. Test de `LEDCLEAR` après plusieurs `LED`.
4. Test de `LEDBRIGHT` avec valeur valide et invalide.

## 6. Plan de bring-up incrémental

Pas un plan d'implémentation détaillé (cf. spec `writing-plans` à venir),
mais l'**ordre logique** dans lequel valider le sous-système. Chaque étape
débloque la suivante et donne un point de vérification physique.

### Étape 0 — Préparation hardware

- Brancher GPIO 15 → DIN du strip (résistance 330 Ω en série si disponible,
  entre GPIO 15 et la broche DIN de la 1ʳᵉ LED).
- Brancher 5V step-down → VDD strip.
- **Brancher GND step-down → GND ESP32** (piège classique, à ne pas oublier).
- Vérifier visuellement la chaîne complète des 36 LEDs (pas de soudure
  froide visible).

### Étape 1 — Hello LED 0 (firmware minimal hardcodé)

Sketch temporaire qui allume la LED 0 en bleu 1 s, l'éteint 1 s, en boucle.

- **Objectif** : valider câblage, GPIO, lib.
- **Sortie attendue** : la 1ʳᵉ LED en bas-gauche clignote en bleu.
- **Si rien ne s'allume** : GND non commun, DIN/DOUT inversé, mauvaise
  pin, ou signal 3.3V trop faible → essayer la diode 1N4148 en série sur
  le rail +5V de la 1ʳᵉ LED uniquement (anode côté alim, cathode côté
  LED) pour faire chuter VDD à ~4.3V.

### Étape 2 — Test du serpentin

Boucle qui allume successivement LED 0, 1, 2, …, 35 en blanc pendant
150 ms chacune, en boucle.

- **Objectif** : valider visuellement l'ordre du serpentin.
- **Sortie attendue** : un "scan" qui parcourt le plateau de bas en haut
  en alternant gauche-droite par rangée.
- **Si l'ordre est inversé** : ajuster la formule de mapping dans
  `engine_to_strip_index` (par exemple si le serpentin commence par une
  rangée impaire physique au lieu de paire).

### Étape 3 — Test des 4 coins et positions de départ

Sketch qui allume simultanément :

- LED 0 (bas-gauche) en rouge
- LED 5 (bas-droite) en vert
- LED 30 (haut-droite) en jaune
- LED 35 (haut-gauche) en blanc
- LED 3 (bas-centre, départ J1) en bleu
- LED 32 (haut-centre, départ J2) en rouge

- **Objectif** : valider la table de vérification du mapping.
- **Sortie attendue** : les 6 LEDs s'allument aux positions prévues.

### Étape 4 — Protocole texte (firmware production)

Intégrer `LED`, `LEDSHOW`, `LEDCLEAR`, `LEDBRIGHT` dans `traiter()`. Tester
depuis le moniteur série avec des commandes manuelles.

- **Objectif** : valider le parser, les bornes, le push.
- **Sortie attendue** : `LED 0 0 0 255` + `LEDSHOW` → LED 0 en bleu.

### Étape 5 — Module Python `webapp/leds.py`

Implémenter `engine_to_strip_index`, `render_state`, `LedRenderer` avec
tests unitaires.

- **Objectif** : couche Python testable, sans dépendance hardware.
- **Validation** : `pytest tests/test_leds.py` à 100 %.

### Étape 6 — Intégration `service.py`

Ajout du hook `led_renderer.update(self.state)` après chaque mutation.

- **Objectif** : faire vivre les LEDs en miroir du jeu.
- **Validation** : lancer une partie en webapp, déplacer les pions, voir
  les LEDs suivre en temps réel.

### Étape 7 — Test reconnexion

Couper l'alim ESP32 pendant une partie, attendre reconnexion auto, vérifier
que les LEDs reviennent à l'état antérieur.

- **Objectif** : valider `on_reconnect()`.
- **Validation** : visuellement les LEDs reviennent identiques.

### Étape 8 — Documentation

Mise à jour de :

- `docs/07_protocole.md` : ajout section "Commandes LED" (tableau + exemple).
- `docs/06_firmware.md` : ajout lib Adafruit_NeoPixel, GPIO 15, commandes.
- `docs/02_architecture.md` : ajout du module `webapp/leds.py`.
- `docs/hardware/pinout.md` : ajout du GPIO 15.

### Étape 9 (P1 bonus) — Coups légaux

Activer `show_legal_moves: True` dans `RenderOptions`. Ajouter un toggle
UI dans la webapp si voulu (bouton ou checkbox).

- **Objectif** : aide visuelle pour le joueur.
- **Validation** : à chaque tour, les cases atteignables s'allument en cyan.

### Pourquoi cet ordre

- **Étapes 1-3** = firmware seul, pas de Mac. On isole hardware et timing
  WS2812B des couches supérieures.
- **Étape 4** = protocole sans intégration jeu. On valide le contrat texte
  indépendamment du moteur.
- **Étape 5** = Python pur. Pytest valide la logique sans plateau.
- **Étape 6** = intégration full stack. Plumbing simple à ce stade.
- **Étape 7** = robustesse. Important pour démo en conditions réelles.
- **Étape 9** = bonus à temps perdu. Ajout incrémental sans risque sur P0.

## Décisions clés (récapitulatif)

| Décision | Choix | Raison |
|---|---|---|
| Niveau d'ambition | A (pions seuls) puis C (coups légaux) | P0 obligatoire, P1 si temps |
| Où vit l'intelligence | Côté Mac (Python) | Cohérence avec ESP32 = actionneur bête |
| Style de protocole | Primitives bas niveau (`LED idx r g b` + `LEDSHOW`) | Évolutif, debuggable au moniteur série |
| GPIO | **15** | Strapping pin sans risque boot, validée NotebookLM |
| Alim | 5V step-down depuis 12V général | Capacité 2+ A, GND commun |
| Lib firmware | `Adafruit_NeoPixel` | Simple, suffisant pour fréquence d'usage |
| Luminosité par défaut | 40 % (102/255) | Marge alim + confort visuel à travers plexi |
| Fond par défaut | Éteint | Lisibilité, économie courant |
| Diff côté Python | Oui (last_frame mémorisé) | Réduit le trafic Wi-Fi d'un facteur ~5 |
| Reconnexion | Re-push complet via `on_reconnect()` | Firmware a rebooté, buffer à 0 |
| Fallback bridge HS | No-op silencieux | Cohérent avec mode autonome existant |
