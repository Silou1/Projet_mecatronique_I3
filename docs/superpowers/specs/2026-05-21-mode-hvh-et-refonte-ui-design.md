# Mode Humain vs Humain + Refonte UI — Design

| | |
|---|---|
| **Date** | 2026-05-21 |
| **Statut** | Validé par l'utilisateur, prêt pour implémentation |
| **Phase** | Améliorations webapp post-LEDs (avant démo finale) |
| **Hors scope** | Refonte de la bannière "Plateau injoignable" (style et boutons Réessayer USB/Wifi gardés tels quels) ; refonte du modal "Statut Plateau" ; refonte du modal de fin de partie ; orientation paysage ; mode multi-téléphones (le HvH est strictement local sur un même téléphone). |

## Objectif

Ajouter un troisième mode de jeu **Humain vs Humain** où deux joueurs s'affrontent
sur le même téléphone, à tour de rôle, et profiter du chantier pour quelques
améliorations ciblées de l'interface :

- pop-up de transition entre les tours pour éviter qu'un joueur joue à la place
  de l'autre,
- rotation 180° du plateau au tour du joueur 2 pour qu'il voie son pion devant
  lui,
- halo coloré sur le pion du joueur courant pour la lisibilité,
- plateau plus grand (bord à bord) et boutons mieux répartis,
- suppression du bouton "Partager sur téléphone" devenu inutile une fois le QR
  imprimé.

Le mode HvH s'intègre **sans rupture** dans :

- le moteur de jeu (`quoridor_engine` — aucun changement),
- le protocole texte ligne par ligne avec l'ESP32 (`WALL`, `LED…`, identiques
  USB et Wi-Fi),
- l'architecture service singleton thread-safe (`QuoridorService`),
- les modes existants `human_vs_ai` et `ai_vs_ai` (régression nulle).

## Critères de succès

À la fin de l'implémentation :

1. **`pytest -m "not devkit"`** vert — tests existants + 4 nouveaux tests HvH.
2. En partie réelle (webapp + ESP32 en USB ou Wi-Fi), un mur placé par J2 en
   mode HvH est physiquement levé par le plateau et affiché sur les LEDs comme
   pour J1.
3. Sur iPhone (Safari), une partie HvH complète se déroule sans confusion :
   chaque joueur sait quand c'est à lui de jouer, voit son pion dans la moitié
   basse de l'écran au moment de jouer, et n'est jamais bloqué.
4. Les modes `human_vs_ai` et `ai_vs_ai` continuent à fonctionner exactement
   comme avant (aucune régression visible).
5. Le plateau de jeu occupe visiblement plus de surface qu'avant sur iPhone.

## 1. Architecture des changements

Le périmètre touche **trois zones** du code, avec des changements proportionnés
à leur rôle :

### Backend (`webapp/`) — changements minimes

- `schemas.py` : élargir `Mode = Literal["human_vs_ai", "ai_vs_ai", "human_vs_human"]`.
- `service.py` :
  - `new_game()` : en mode HvH, aucune IA n'est instanciée (`_ai_j1 = _ai_j2 = None`).
  - `apply_user_move()` : retirer la check `if mode == "ai_vs_ai": raise`,
    redondante avec la check `_is_ai_turn_unlocked()` qui suit.

**Aucun changement** dans : `transport.py`, `plateau.py`, `leds.py`, `qr.py`,
`ai.py`, `core.py`, `server.py`.

### Frontend HvH (`webapp/static/`)

- Nouvelle modal `#modal-transition` ("À toi J1/J2, prêt ?" + bouton OK).
- Rotation 180° du SVG du plateau quand `current_player === "j2"` en mode HvH,
  via `transform: rotate(180deg)` sur le `<svg>`.
- Halo pulse sur le pion du joueur courant (CSS animation `drop-shadow`).
- Logique JS : déclenche la modal après application visuelle du coup, avec
  délai 500 ms pour laisser voir l'animation du mur et du pion.

### Frontend refonte UI (`webapp/static/`)

- Accueil : 3 chips (HvAI, HvH, AIvAI), bloc difficulté caché en HvH, bouton
  "Partager sur téléphone" supprimé (avec son modal QR).
- Plateau de jeu : SVG bord à bord (`max-width: 360px` retiré du `.board-wrap`,
  padding latéral de la vue jeu réduit à 8 px).
- Status-bar et game-bar : paddings réduits pour gagner ~25 px verticaux sans
  changer la structure HTML.
- Couleur dynamique du `#turn-indicator` selon le joueur (bleu / rouge).

## 2. Backend — détail

### 2.1 `webapp/schemas.py`

```python
Mode = Literal["human_vs_ai", "ai_vs_ai", "human_vs_human"]
```

### 2.2 `webapp/service.py`

**(a) `new_game()`** — ajouter la branche HvH :

```python
if mode == "human_vs_ai":
    self._ai_j2 = AI(player=PLAYER_TWO, difficulty=difficulty)
elif mode == "ai_vs_ai":
    self._ai_j1 = AI(player=PLAYER_ONE, difficulty=difficulty)
    self._ai_j2 = AI(player=PLAYER_TWO, difficulty=difficulty)
elif mode == "human_vs_human":
    pass  # aucune IA, les deux joueurs poussent leurs coups via apply_user_move
```

**(b) `apply_user_move()`** — supprimer la check spécifique `ai_vs_ai` :

```python
# À SUPPRIMER (lignes ~177-180) :
if self._mode == "ai_vs_ai":
    raise InvalidMoveError(
        "Pas de coup humain en mode IA vs IA.", NackCode.WRONG_TURN
    )
```

**Pourquoi c'est safe** : la check juste en dessous
(`if self._is_ai_turn_unlocked(): raise WRONG_TURN`) couvre déjà le cas AIvAI
(les deux IAs existent, donc `_is_ai_turn_unlocked()` est toujours True). On
retire un test redondant qui devient faux en HvH (où aucune IA n'existe, donc
`_is_ai_turn_unlocked()` est toujours False et les deux joueurs humains peuvent
pousser leurs coups).

**(c) Aucun autre changement de logique** dans le service — `_to_dict_unlocked()`,
`tick_once()`, `_check_game_over_unlocked()`, `_forward_to_plateau_unlocked()`
marchent déjà correctement en HvH par construction : aucun chemin de code n'est
spécifique à HvAI/AIvAI, tout est piloté par `current_player` et la
présence/absence des objets `_ai_jX`.

### 2.3 Tests à ajouter (`tests/test_service.py`)

- **`test_hvh_no_ai_created`** : après `new_game(mode="human_vs_human")`,
  `service._ai_j1 is None` et `service._ai_j2 is None`.
- **`test_hvh_both_players_move`** : créer une partie HvH, jouer un déplacement
  J1, vérifier `current_player == "j2"`, jouer un déplacement J2, vérifier
  `current_player == "j1"` et `turn_count == 2`.
- **`test_hvh_tick_noop`** : `tick_once()` retourne `False` en HvH même après
  délai (pas d'IA à faire jouer).
- **`test_hvh_wall_forwarded`** : `plateau_mode=True`, un mur posé par J2
  envoie la commande `WALL` au transport (vérifie qu'on n'a pas régressé sur
  le forwarding des coups J2).

## 3. Frontend HvH — détail

### 3.1 Helper `isHumanTurn(state)`

Aujourd'hui `app.js` est en dur sur "J1 = humain" :

```js
if (state.current_player !== "j1") return;  // dans handleCellClick, etc.
```

À remplacer par :

```js
function isHumanTurn(state) {
  if (!state || state.status !== "playing") return false;
  return !state.players[state.current_player].is_ai;
}
```

Trois call sites à mettre à jour :
- `handleCellClick(row, col)` — remplacer la check actuelle.
- `handleIntersectionClick(row, col)` — idem.
- Le `mouseenter` dans `renderIntersections()` — idem.

### 3.2 `renderHeader()` — texte du tour générique

Réécriture du switch interne :

```js
if (state.status === "paused") {
  ind.textContent = "Pause";
  ind.classList.remove("ai-thinking");
} else if (state.ai_thinking) {
  ind.textContent = "IA réfléchit";
  ind.classList.add("ai-thinking");
} else if (state.mode === "ai_vs_ai") {
  ind.textContent = `Tour de ${state.current_player.toUpperCase()}`;
  ind.classList.remove("ai-thinking");
} else if (state.mode === "human_vs_human") {
  ind.textContent = `AU TOUR DE ${state.current_player.toUpperCase()}`;
  ind.classList.remove("ai-thinking");
} else /* human_vs_ai */ {
  ind.textContent = state.current_player === "j1" ? "TON TOUR" : "IA joue";
  ind.classList.remove("ai-thinking");
}
```

Plus une classe CSS dynamique `turn-j1` / `turn-j2` pour la colorer (voir §4.4).

### 3.3 Modal de transition

**HTML** — à ajouter dans `index.html` à côté de `#modal-end` :

```html
<div id="modal-transition" class="modal hidden">
  <div class="modal-card">
    <div class="trophy">🎮</div>
    <h2 id="transition-text">À toi J2 !</h2>
    <p class="status-detail">Passe le téléphone et tape pour démarrer.</p>
    <div class="modal-actions">
      <button id="btn-transition-ok" class="btn-primary">Je suis prêt</button>
    </div>
  </div>
</div>
```

**Handler** dans `initHandlers()` :

```js
document.getElementById("btn-transition-ok").addEventListener("click", () => {
  document.getElementById("modal-transition").classList.add("hidden");
});
```

**Logique de déclenchement** — un seul point d'appel depuis `render()`, avec
tracking du dernier `turn_count` affiché pour éviter les re-déclenchements lors
du polling toutes les 500 ms :

```js
let _lastTransitionTurn = -1;

function maybeShowTransition(state) {
  if (state.mode !== "human_vs_human") return;
  if (state.status === "waiting") {
    _lastTransitionTurn = -1;  // reset au retour à l'accueil
    return;
  }
  if (state.status !== "playing") return;
  if (state.turn_count === _lastTransitionTurn) return;
  _lastTransitionTurn = state.turn_count;
  const delayMs = state.turn_count === 0 ? 0 : 500;
  document.getElementById("transition-text").textContent =
    `À toi ${state.current_player.toUpperCase()} !`;
  setTimeout(() => {
    if (state.status === "playing") {
      document.getElementById("modal-transition").classList.remove("hidden");
    }
  }, delayMs);
}
```

Appel dans `render()` après `renderModal()`.

**Comportements clés** :
- **Premier tour** (`turn_count === 0`) : délai 0, modal apparaît immédiatement
  pour J1.
- **Tours suivants** : délai 500 ms — laisse voir l'animation du mur (200 ms)
  et du pion (400 ms) avant la modal.
- **Polling 500 ms** : ne re-déclenche pas la modal (même `turn_count`).
- **Quitter pendant le délai** : le `setTimeout` vérifie à nouveau
  `state.status === "playing"` avant d'afficher.
- **Quitter / nouvelle partie** : `_lastTransitionTurn` reset à `-1` quand on
  retombe en `waiting`.
- **Fin de partie** : `status === "finished"` → la modal de fin prend le
  relais, la modal de transition ne s'affiche pas.
- **Coup invalide** : `turn_count` n'a pas changé → pas de modal de transition,
  toast d'erreur normal.

### 3.4 Rotation 180° du plateau au tour de J2

**CSS** sur le `<svg id="board">` :

```css
#board {
  transition: transform 0.6s ease-in-out;
}
#board.flipped {
  transform: rotate(180deg);
}
```

**JS** dans `render()` :

```js
const board = document.getElementById("board");
const flip = state.mode === "human_vs_human" && state.current_player === "j2";
board.classList.toggle("flipped", flip);
```

**Notes** :
- Les clics sur les cases et intersections fonctionnent nativement après
  rotation CSS — le navigateur applique la transformation aux events. Pas de
  remapping de coordonnées nécessaire.
- Seul le SVG du plateau pivote. La status-bar, la game-bar et les boutons
  restent dans l'orientation normale de l'app pour la lisibilité du texte.
- Le pop-up de transition est en `position: fixed` dans le DOM, donc pas
  affecté par la rotation du SVG.
- La transition de 600 ms se déclenche dans `render()`, donc le plateau pivote
  pendant que la modal de transition est cachée puis affichée 500 ms après. Au
  moment où J2 tape "Je suis prêt", le plateau a déjà pivoté.

### 3.5 Halo pulse sur le pion du joueur courant

**CSS** :

```css
@keyframes pawn-pulse {
  0%, 100% { filter: drop-shadow(0 0 0 transparent); }
  50%      { filter: drop-shadow(0 0 8px var(--halo)); }
}
.pawn.current { animation: pawn-pulse 1.4s ease-in-out infinite; }
#pawn-j1.current { --halo: #5b9fd9; }
#pawn-j2.current { --halo: #e57a6c; }
```

**JS** dans `render()` :

```js
document.getElementById("pawn-j1").classList.toggle(
  "current", state.current_player === "j1" && state.status === "playing"
);
document.getElementById("pawn-j2").classList.toggle(
  "current", state.current_player === "j2" && state.status === "playing"
);
```

Actif pour tous les modes (HvAI, AIvAI, HvH) — utile partout pour voir qui
doit jouer.

## 4. Frontend refonte UI — détail

### 4.1 Accueil

**HTML** :

**(a)** Ajouter le chip "Humain vs Humain" :

```html
<div class="chip-group" data-field="mode">
  <button class="chip selected" data-value="human_vs_ai">Humain vs IA</button>
  <button class="chip" data-value="human_vs_human">Humain vs Humain</button>
  <button class="chip" data-value="ai_vs_ai">IA vs IA</button>
</div>
```

**(b)** Encapsuler le bloc "Difficulté" dans un wrapper :

```html
<div id="difficulty-block">
  <label class="field-label">Difficulté</label>
  <div class="chip-group" data-field="difficulty">
    <button class="chip" data-value="facile">Facile</button>
    <button class="chip selected" data-value="normal">Normal</button>
    <button class="chip" data-value="difficile">Difficile</button>
  </div>
</div>
```

**(c)** Supprimer le bouton "Partager sur téléphone" et son modal QR :
- Retirer `<button id="btn-share">📱 Partager sur téléphone</button>` (ligne 52).
- Retirer le bloc complet `<div id="modal-share" class="modal hidden">…</div>`
  (lignes 57-74).
- Retirer l'appel `initShareUI();` dans le `DOMContentLoaded` (`app.js`).
- Retirer la fonction `initShareUI()` entière dans `app.js`.
- La route serveur `/api/qr-code` et `/api/qr-code/url` **reste** (impression
  manuelle via URL directe si besoin).

**JS** — étendre la conditionnelle dans `initHandlers()` :

```js
if (field === "mode") {
  document.getElementById("speed-block").classList.toggle("hidden", value !== "ai_vs_ai");
  document.getElementById("difficulty-block").classList.toggle("hidden", value === "human_vs_human");
}
```

### 4.2 Plateau plus grand (bord à bord)

**CSS** :

```css
.board-wrap {
  width: 100%;
  /* on retire : max-width: 360px; */
  aspect-ratio: 1;
  margin: 0 auto;
}

#view-game {
  padding-left: 8px;
  padding-right: 8px;
}
```

**Effet attendu** : sur iPhone (~390 px de large), le plateau passe de ~320 px
(avec marges 20 px) à ~374 px (avec marges 8 px). +50 px, soit ~16 % plus
grand. Les cases passent de ~45 px à ~52 px de côté — plus faciles à toucher
au doigt.

### 4.3 Status-bar et game-bar compactes

```css
.game-bar { padding: 4px 4px 8px; }     /* avant : 8px 4px 16px */
.status-bar { padding: 0 6px 8px; }     /* avant : 0 6px 12px */
```

Gain ~25 px verticaux. Pas de changement HTML (on garde `J1 · 6 murs | AU TOUR
DE J1 | J2 · 6 murs` qui reste clair).

### 4.4 Couleur dynamique du `#turn-indicator`

**CSS** :

```css
#turn-indicator.turn-j1 { background: rgba(31, 95, 143, 0.15); color: #1f5f8f; }
#turn-indicator.turn-j2 { background: rgba(156, 47, 35, 0.15); color: #9c2f23; }
```

**JS** dans `renderHeader()` (déjà couvert en §3.2) :

```js
ind.classList.toggle("turn-j1", state.current_player === "j1" && !state.ai_thinking);
ind.classList.toggle("turn-j2", state.current_player === "j2" && !state.ai_thinking);
```

## 5. Récap des fichiers touchés

| Fichier | Changements |
|---|---|
| `webapp/schemas.py` | `Mode` literal étendu (1 ligne). |
| `webapp/service.py` | branche HvH dans `new_game()` (3 lignes ajoutées), check redondante supprimée dans `apply_user_move()` (4 lignes retirées). |
| `webapp/static/index.html` | chip HvH ajouté, wrapper `#difficulty-block` ajouté, bouton `#btn-share` supprimé, modal `#modal-share` supprimé, modal `#modal-transition` ajouté. |
| `webapp/static/app.js` | helper `isHumanTurn()`, `renderHeader()` réécrit, `maybeShowTransition()` ajoutée, rotation 180° ajoutée, halo pulse JS ajouté, `initShareUI()` supprimée entièrement, appel `initShareUI()` retiré du DOMContentLoaded, 3 call sites mis à jour pour utiliser `isHumanTurn()`. |
| `webapp/static/style.css` | halo pulse (keyframes + classes), rotation board (transition + flipped), padding accueil/jeu réduits, board sans `max-width`, couleurs `turn-j1` / `turn-j2`. |
| `tests/test_service.py` (ou équivalent existant) | 4 tests HvH ajoutés. |

## 6. Edge cases et comportements attendus

| Situation | Comportement attendu |
|---|---|
| Polling `/api/state` re-render avec même état | Modal transition affichée seulement quand `turn_count` change ; jamais en re-render (tracking `_lastTransitionTurn`). |
| Quitter via ← pendant la modal de transition affichée | Modal se ferme (parce que `render()` détecte `status !== "playing"`) ; `_lastTransitionTurn` reset à `-1` au retour `waiting`. |
| Rejouer (`btn-replay`) après fin de partie HvH | Nouvelle partie démarre, `turn_count = 0`, modal "À toi J1" s'affiche immédiatement (délai 0). |
| Coup HvH invalide (toast d'erreur) | Pas de modal transition (`turn_count` inchangé), halo reste sur le même joueur, rotation inchangée. |
| Plateau ESP32 lâche pendant partie HvH | Banner dégradée apparaît, partie continue côté app, rotation / halo / transition continuent à marcher. |
| `setTimeout(500)` puis user a quitté entre temps | Au moment d'afficher la modal, re-vérifier `state.status === "playing"`. |
| Mode `human_vs_ai` régression | Pas de modal transition (mode != HvH), pas de rotation, halo sur le pion courant comme avant. |
| Mode `ai_vs_ai` régression | Pas de modal transition, pas de rotation, halo sur le pion courant. Le texte du tour reste `Tour de J1` / `Tour de J2` comme avant. |

## 7. Plan de validation

### 7.1 Tests automatisés

- `pytest -m "not devkit"` → tous les tests verts (existants + 4 nouveaux HvH).

### 7.2 Tests manuels (Safari iOS et Chrome desktop)

**Accueil**
- [ ] Chip HvH apparaît, sélection alterne avec les 2 autres.
- [ ] Sélection HvH → bloc difficulté disparaît.
- [ ] Sélection HvAI → bloc difficulté réapparaît, bloc vitesse caché.
- [ ] Sélection AIvAI → bloc difficulté visible, bloc vitesse visible.
- [ ] Bouton "Partager sur téléphone" absent.

**HvH partie**
- [ ] "Commencer la partie" en HvH → modal de transition "À toi J1" apparaît immédiatement.
- [ ] Tap "Je suis prêt" → modal se ferme, J1 peut cliquer.
- [ ] J1 déplace son pion → animation du pion → ~500 ms → modal "À toi J2".
- [ ] Plateau a pivoté de 180° (J2 voit son pion en bas de l'écran).
- [ ] Halo bleu sur le pion J1 quand c'est son tour, rouge sur J2.
- [ ] J2 pose un mur → mur envoyé au plateau physique (LED + mécanique si plateau connecté).
- [ ] Quitter en cours via icône ← → modal de transition ne s'affiche pas au retour suivant.
- [ ] Rejouer après fin de partie HvH → modal "À toi J1" réapparaît.

**HvAI (régression)**
- [ ] Mode HvAI fonctionne pareil qu'avant (pas de modal de transition, pas de rotation, halo OK sur le pion courant).
- [ ] "TON TOUR" / "IA joue" / "IA réfléchit" s'affichent normalement.

**AIvAI (régression)**
- [ ] AIvAI fonctionne pareil qu'avant (Tour J1/J2 alterne, pas de modal transition, pas de rotation, halo sur le pion courant).

**Plateau plus grand**
- [ ] Sur iPhone, plateau visiblement plus grand qu'avant, cases plus faciles à toucher au doigt.

### 7.3 Validation hardware (si plateau ESP32 dispo)

- `QUORIDOR_TRANSPORT=wifi python -m webapp.server` → tester la chaîne complète
  en HvH : mur posé par J1 → mécanique du plateau + LED bleue. Mur posé par J2
  → mécanique du plateau + LED rouge.
- `QUORIDOR_TRANSPORT=serial python -m webapp.server` → idem en USB.
