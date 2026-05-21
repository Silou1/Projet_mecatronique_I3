# Mode Humain vs Humain + Refonte UI — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter un mode de jeu Humain vs Humain (deux joueurs sur le même téléphone, à tour de rôle) avec pop-up de transition + rotation 180° du plateau au tour de J2, et profiter du chantier pour une refonte UI ciblée (plateau plus grand, halo sur pion courant, suppression du bouton QR).

**Architecture:** Backend FastAPI quasi inchangé (1 ligne dans `schemas.py`, 7 lignes nettes dans `service.py`). L'essentiel du travail est en frontend JS/CSS/HTML : nouvelle modal de transition pilotée par tracking du `turn_count`, rotation CSS du SVG, halo via `drop-shadow` animé, et refonte de l'écran d'accueil + plateau bord-à-bord.

**Tech Stack:** Python 3 + FastAPI + Pydantic (backend) ; HTML5/CSS3/JavaScript vanilla (frontend) ; pytest (tests backend). Pas de framework JS, pas de test runner JS — validation frontend manuelle.

**Spec source :** [`docs/superpowers/specs/2026-05-21-mode-hvh-et-refonte-ui-design.md`](../specs/2026-05-21-mode-hvh-et-refonte-ui-design.md)

---

## Structure des fichiers

**Modifiés :**
- `webapp/schemas.py` — élargir le `Literal Mode`
- `webapp/service.py` — branche HvH dans `new_game()`, nettoyage `apply_user_move()`
- `webapp/static/index.html` — chip HvH, wrap `#difficulty-block`, suppression QR, ajout `#modal-transition`
- `webapp/static/app.js` — helper `isHumanTurn()`, `renderHeader()` étendu, `maybeShowTransition()`, rotation, halo, suppression `initShareUI()`
- `webapp/static/style.css` — halo pulse, rotation board, padding réduits, board sans `max-width`, couleurs `turn-jX`
- `tests/webapp/test_service.py` — 4 tests HvH ajoutés

**Aucun changement :** `transport.py`, `plateau.py`, `leds.py`, `qr.py`, `ai.py`, `core.py`, `server.py`, firmware ESP32.

---

## Phase Backend (TDD strict)

### Task 1 : Étendre le Literal Mode dans schemas.py

**Files:**
- Modify: `webapp/schemas.py:6`

- [ ] **Step 1 : Écrire le test (test_schemas.py)**

Ajouter dans `tests/webapp/test_schemas.py` :

```python
def test_new_game_payload_accepte_human_vs_human():
    from webapp.schemas import NewGamePayload
    payload = NewGamePayload(mode="human_vs_human", difficulty="normal", plateau_mode=False)
    assert payload.mode == "human_vs_human"
```

- [ ] **Step 2 : Lancer le test, vérifier qu'il échoue**

Run: `pytest tests/webapp/test_schemas.py::test_new_game_payload_accepte_human_vs_human -v`
Expected: FAIL avec une erreur Pydantic `ValidationError` (mode non accepté).

- [ ] **Step 3 : Élargir le Literal**

Dans `webapp/schemas.py`, ligne 6, remplacer :

```python
Mode = Literal["human_vs_ai", "ai_vs_ai"]
```

par :

```python
Mode = Literal["human_vs_ai", "ai_vs_ai", "human_vs_human"]
```

- [ ] **Step 4 : Relancer le test, vérifier qu'il passe**

Run: `pytest tests/webapp/test_schemas.py -v`
Expected: PASS.

- [ ] **Step 5 : Commit**

```bash
git add webapp/schemas.py tests/webapp/test_schemas.py
git commit -m "feat(webapp): elargir Mode literal a human_vs_human"
```

---

### Task 2 : Branche HvH dans `new_game()` + test `_ai_jX is None`

**Files:**
- Modify: `webapp/service.py:75-99` (méthode `new_game`)
- Test: `tests/webapp/test_service.py` (nouvelle classe ou ajout)

- [ ] **Step 1 : Écrire le test**

Dans `tests/webapp/test_service.py`, ajouter au bas du fichier :

```python
class TestHumainVsHumain:
    def test_hvh_no_ai_created(self, service):
        service.new_game(mode="human_vs_human", difficulty="normal", plateau_mode=False)
        assert service._ai_j1 is None
        assert service._ai_j2 is None
        state = service.to_dict()
        assert state["mode"] == "human_vs_human"
        assert state["players"]["j1"]["is_ai"] is False
        assert state["players"]["j2"]["is_ai"] is False
        assert state["status"] == "playing"
        assert state["current_player"] == "j1"
```

- [ ] **Step 2 : Lancer le test, vérifier qu'il passe déjà (code initial OK)**

Run: `pytest tests/webapp/test_service.py::TestHumainVsHumain::test_hvh_no_ai_created -v`
Expected: PASS — le code initial ne crée pas d'IA pour les modes inconnus (branches `if/elif` sans `else`).

Ce test est un **garde-fou** pour la régression future.

- [ ] **Step 3 : Ajouter la branche explicite dans `new_game()`**

Dans `webapp/service.py`, méthode `new_game()`, après le bloc `elif mode == "ai_vs_ai":` (vers ligne 87), ajouter :

```python
            elif mode == "human_vs_human":
                pass  # aucune IA, les deux joueurs poussent leurs coups via apply_user_move
```

Le bloc complet devient :

```python
            if mode == "human_vs_ai":
                self._ai_j2 = AI(player=PLAYER_TWO, difficulty=difficulty)
            elif mode == "ai_vs_ai":
                self._ai_j1 = AI(player=PLAYER_ONE, difficulty=difficulty)
                self._ai_j2 = AI(player=PLAYER_TWO, difficulty=difficulty)
            elif mode == "human_vs_human":
                pass  # aucune IA, les deux joueurs poussent leurs coups via apply_user_move
```

- [ ] **Step 4 : Relancer le test**

Run: `pytest tests/webapp/test_service.py::TestHumainVsHumain -v`
Expected: PASS.

- [ ] **Step 5 : Commit**

```bash
git add webapp/service.py tests/webapp/test_service.py
git commit -m "feat(service): branche explicite human_vs_human dans new_game"
```

---

### Task 3 : Retirer check redondante + test "les deux joueurs peuvent jouer"

**Files:**
- Modify: `webapp/service.py:177-180` (méthode `apply_user_move`)
- Test: `tests/webapp/test_service.py::TestHumainVsHumain`

- [ ] **Step 1 : Écrire le test**

Ajouter dans `TestHumainVsHumain` :

```python
    def test_hvh_both_players_can_move(self, service):
        service.new_game(mode="human_vs_human", difficulty="normal", plateau_mode=False)
        # J1 joue
        service.apply_user_move({"type": "deplacement", "target": (4, 3)})
        state = service.to_dict()
        assert state["current_player"] == "j2"
        assert state["turn_count"] == 1
        assert state["players"]["j1"]["position"] == [4, 3]
        # J2 joue
        service.apply_user_move({"type": "deplacement", "target": (1, 3)})
        state = service.to_dict()
        assert state["current_player"] == "j1"
        assert state["turn_count"] == 2
        assert state["players"]["j2"]["position"] == [1, 3]
```

- [ ] **Step 2 : Lancer le test, vérifier qu'il passe déjà**

Run: `pytest tests/webapp/test_service.py::TestHumainVsHumain::test_hvh_both_players_can_move -v`
Expected: PASS — la check `if self._mode == "ai_vs_ai": raise` ne bloque pas HvH, et `_is_ai_turn_unlocked()` retourne `False` quand il n'y a pas d'IA.

Encore un garde-fou : sécurise le comportement actuel.

- [ ] **Step 3 : Nettoyage — retirer la check redondante**

Dans `webapp/service.py`, méthode `apply_user_move()`, supprimer les lignes (vers 176-180) :

```python
            if self._mode == "ai_vs_ai":
                raise InvalidMoveError(
                    "Pas de coup humain en mode IA vs IA.", NackCode.WRONG_TURN
                )
```

La check juste en dessous (`if self._is_ai_turn_unlocked(): raise InvalidMoveError(..., WRONG_TURN)`) couvre déjà le cas AIvAI (les deux IAs existent → `_is_ai_turn_unlocked()` est toujours `True` en AIvAI).

- [ ] **Step 4 : Relancer toute la suite test_service**

Run: `pytest tests/webapp/test_service.py -v`
Expected: PASS — y compris `test_deplacement_en_mode_ai_vs_ai_rejete` (ligne 73), qui passe maintenant via la check `_is_ai_turn_unlocked()` au lieu de la check explicite.

- [ ] **Step 5 : Commit**

```bash
git add webapp/service.py tests/webapp/test_service.py
git commit -m "refactor(service): supprimer check ai_vs_ai redondante dans apply_user_move

La check _is_ai_turn_unlocked() qui suit couvre deja le cas AIvAI
(les deux IAs existent), donc la check specifique etait redondante.
La supprimer permet aussi aux deux joueurs humains de jouer en HvH
sans cas particulier."
```

---

### Task 4 : Test `tick_once` no-op en HvH

**Files:**
- Test: `tests/webapp/test_service.py::TestHumainVsHumain`

- [ ] **Step 1 : Écrire le test (garde-fou)**

Ajouter dans `TestHumainVsHumain` :

```python
    def test_hvh_tick_noop(self, service):
        service.new_game(mode="human_vs_human", difficulty="normal", plateau_mode=False)
        service._last_ai_move_at = 0.0  # delai depasse, force la condition
        played = service.tick_once()
        assert played is False
        state = service.to_dict()
        assert state["turn_count"] == 0
        assert state["current_player"] == "j1"
```

- [ ] **Step 2 : Lancer le test**

Run: `pytest tests/webapp/test_service.py::TestHumainVsHumain::test_hvh_tick_noop -v`
Expected: PASS — `tick_once()` retourne `False` car `_is_ai_turn_unlocked()` retourne `False` quand il n'y a pas d'IA.

- [ ] **Step 3 : Commit**

```bash
git add tests/webapp/test_service.py
git commit -m "test(service): garde-fou tick_once no-op en mode HvH"
```

---

### Task 5 : Test mur de J2 forwarded au plateau

**Files:**
- Test: `tests/webapp/test_service.py::TestHumainVsHumain`

- [ ] **Step 1 : Écrire le test**

Ajouter dans `TestHumainVsHumain` :

```python
    def test_hvh_wall_de_j2_forwarded_au_plateau(self):
        """Le mur pose par J2 en HvH doit etre envoye au plateau physique
        avec inversion H<->V (convention plateau)."""
        from webapp.transport import NullTransport

        lignes_envoyees = []

        class FakeTransport(NullTransport):
            description = "fake"
            is_alive = True
            def write_line(self, line):
                lignes_envoyees.append(line)

        transport = FakeTransport()
        transport.open()
        service = QuoridorService(transport=transport)
        service.new_game(mode="human_vs_human", difficulty="normal", plateau_mode=True)
        # J1 deplace son pion (turn count 1, current player = j2)
        service.apply_user_move({"type": "deplacement", "target": (4, 3)})
        lignes_envoyees.clear()  # on ignore les HOME/autres au demarrage
        # J2 pose un mur horizontal
        service.apply_user_move({"type": "mur", "orientation": "h", "row": 1, "col": 2})
        # Verifier que la commande WALL a ete envoyee (avec inversion h->V)
        assert any(ligne.startswith("WALL V 1 2") for ligne in lignes_envoyees), \
            f"WALL non envoye, lignes: {lignes_envoyees}"
```

- [ ] **Step 2 : Lancer le test**

Run: `pytest tests/webapp/test_service.py::TestHumainVsHumain::test_hvh_wall_de_j2_forwarded_au_plateau -v`
Expected: PASS — `_forward_to_plateau_unlocked()` envoie déjà la commande pour les coups de n'importe quel joueur (le code ne discrimine pas).

- [ ] **Step 3 : Lancer toute la suite backend**

Run: `pytest -m "not devkit"`
Expected: PASS — tous les tests existants + 5 nouveaux.

- [ ] **Step 4 : Commit**

```bash
git add tests/webapp/test_service.py
git commit -m "test(service): garde-fou forward WALL J2 en mode HvH"
```

---

## Phase Frontend — Refonte accueil

### Task 6 : Chip HvH + wrapper `#difficulty-block` + JS conditionnel

**Files:**
- Modify: `webapp/static/index.html:22-31` (zone des chips)
- Modify: `webapp/static/app.js:367` (conditionnelle du toggle)

- [ ] **Step 1 : Modifier le HTML accueil**

Dans `webapp/static/index.html`, remplacer le bloc actuel (lignes 22-31 environ) :

```html
      <label class="field-label">Mode</label>
      <div class="chip-group" data-field="mode">
        <button class="chip selected" data-value="human_vs_ai">Humain vs IA</button>
        <button class="chip" data-value="ai_vs_ai">IA vs IA</button>
      </div>

      <label class="field-label">Difficulté</label>
      <div class="chip-group" data-field="difficulty">
        <button class="chip" data-value="facile">Facile</button>
        <button class="chip selected" data-value="normal">Normal</button>
        <button class="chip" data-value="difficile">Difficile</button>
      </div>
```

par :

```html
      <label class="field-label">Mode</label>
      <div class="chip-group" data-field="mode">
        <button class="chip selected" data-value="human_vs_ai">Humain vs IA</button>
        <button class="chip" data-value="human_vs_human">Humain vs Humain</button>
        <button class="chip" data-value="ai_vs_ai">IA vs IA</button>
      </div>

      <div id="difficulty-block">
        <label class="field-label">Difficulté</label>
        <div class="chip-group" data-field="difficulty">
          <button class="chip" data-value="facile">Facile</button>
          <button class="chip selected" data-value="normal">Normal</button>
          <button class="chip" data-value="difficile">Difficile</button>
        </div>
      </div>
```

- [ ] **Step 2 : Étendre la conditionnelle JS**

Dans `webapp/static/app.js`, dans `initHandlers()`, trouver le bloc (ligne ~367) :

```js
          if (field === "mode") {
            document.getElementById("speed-block").classList.toggle("hidden", value !== "ai_vs_ai");
          }
```

et le remplacer par :

```js
          if (field === "mode") {
            document.getElementById("speed-block").classList.toggle("hidden", value !== "ai_vs_ai");
            document.getElementById("difficulty-block").classList.toggle("hidden", value === "human_vs_human");
          }
```

- [ ] **Step 3 : Tester manuellement**

Run: `QUORIDOR_TRANSPORT=none python -m webapp.server`
Ouvrir `http://localhost:8000` dans un navigateur :
- Le chip "Humain vs Humain" apparaît entre HvAI et AIvAI.
- Cliquer "Humain vs Humain" → le bloc Difficulté disparaît, le bloc Vitesse reste caché.
- Cliquer "IA vs IA" → bloc Difficulté visible, bloc Vitesse visible.
- Cliquer "Humain vs IA" → bloc Difficulté visible, bloc Vitesse caché.

Arrêter le serveur (Ctrl-C).

- [ ] **Step 4 : Commit**

```bash
git add webapp/static/index.html webapp/static/app.js
git commit -m "feat(webapp): chip Humain vs Humain dans l accueil + difficulty conditionnel"
```

---

### Task 7 : Suppression du bouton et modal "Partager sur téléphone"

**Files:**
- Modify: `webapp/static/index.html:52` (bouton btn-share)
- Modify: `webapp/static/index.html:56-74` (modal-share)
- Modify: `webapp/static/app.js:529-578` (fonction initShareUI)
- Modify: `webapp/static/app.js:621` (appel initShareUI dans DOMContentLoaded)

- [ ] **Step 1 : Retirer le bouton dans index.html**

Dans `webapp/static/index.html`, supprimer la ligne (vers 52) :

```html
      <button id="btn-share" class="btn-secondary">📱 Partager sur téléphone</button>
```

- [ ] **Step 2 : Retirer le modal QR complet**

Dans `webapp/static/index.html`, supprimer le bloc complet (lignes ~56-74) :

```html
  <!-- ============ MODAL PARTAGE QR CODE ============ -->
  <div id="modal-share" class="modal hidden">
    <div class="modal-card">
      <h2>Partager sur téléphone</h2>
      <div class="chip-group" data-field="qr-mode" style="justify-content: center; margin-bottom: 12px;">
        <button class="chip selected" data-value="auto">Maintenant</button>
        <button class="chip" data-value="demo">Démo (à imprimer)</button>
      </div>
      <p id="qr-mode-hint" class="status-detail" style="text-align: center;">
        URL selon le réseau actuel du Mac.
      </p>
      <img id="qr-image" src="/api/qr-code" alt="QR code"
           style="max-width: 280px; margin: 16px auto; display: block; image-rendering: pixelated;" />
      <p id="qr-url" class="status-detail" style="text-align: center; font-family: monospace;">—</p>
      <div class="modal-actions">
        <button id="btn-share-close" class="btn-secondary" type="button">Fermer</button>
      </div>
    </div>
  </div>
```

- [ ] **Step 3 : Retirer la fonction `initShareUI()` dans app.js**

Dans `webapp/static/app.js`, supprimer la fonction entière (lignes ~529-578) :

```js
function initShareUI() {
  const btnShare = document.getElementById("btn-share");
  const modalShare = document.getElementById("modal-share");
  // ... toute la fonction ...
}
```

- [ ] **Step 4 : Retirer l'appel à `initShareUI()` dans `DOMContentLoaded`**

Dans `webapp/static/app.js`, dans le `DOMContentLoaded` (vers ligne 616-624), supprimer la ligne :

```js
  initShareUI();
```

Le bloc devient :

```js
document.addEventListener("DOMContentLoaded", () => {
  renderCells();
  renderIntersections();
  initHandlers();
  initStatusUI();
  startStatusPolling();
  poll();
});
```

- [ ] **Step 5 : Vérifier qu'aucune autre référence ne reste**

Run: `grep -rn "btn-share\|initShareUI\|modal-share\|qr-image\|qr-mode\|qr-url" webapp/static/`
Expected: aucun résultat dans `index.html` ni `app.js`. (Les routes `/api/qr-code*` restent côté serveur, c'est volontaire.)

- [ ] **Step 6 : Tester manuellement**

Run: `QUORIDOR_TRANSPORT=none python -m webapp.server`
Ouvrir `http://localhost:8000` :
- Le bouton "📱 Partager sur téléphone" n'apparaît plus sur l'accueil.
- Cliquer "Commencer la partie" → ça démarre normalement.
- Aucune erreur dans la console JS du navigateur.

Vérifier aussi (impression manuelle reste possible) :
- Ouvrir `http://localhost:8000/api/qr-code?mode=demo` → un SVG QR s'affiche encore.

Arrêter le serveur.

- [ ] **Step 7 : Commit**

```bash
git add webapp/static/index.html webapp/static/app.js
git commit -m "refactor(webapp): retirer bouton et modal QR de l accueil

Le QR code n'est utile qu'une fois pour l'impression initiale ;
encombrement inutile sur l'accueil. La route /api/qr-code reste
accessible pour reimpression manuelle."
```

---

## Phase Frontend — HvH (logique et UX)

### Task 8 : Helper `isHumanTurn()` + adapter 3 call sites

**Files:**
- Modify: `webapp/static/app.js` (zones autour de `handleCellClick`, `handleIntersectionClick`, `renderIntersections`)

- [ ] **Step 1 : Ajouter le helper en haut du fichier**

Dans `webapp/static/app.js`, juste après la section "ÉTAT GLOBAL" (vers ligne 19), ajouter :

```js
// ============ HELPERS ÉTAT ============
function isHumanTurn(state) {
  if (!state || state.status !== "playing") return false;
  return !state.players[state.current_player].is_ai;
}
```

- [ ] **Step 2 : Remplacer dans `handleCellClick`**

Dans `webapp/static/app.js`, fonction `handleCellClick` (vers ligne 294), remplacer le bloc :

```js
async function handleCellClick(row, col) {
  if (!state || state.status !== "playing") return;
  if (state.wall_placement_mode) return;  // pas en mode mur
  if (state.mode === "ai_vs_ai") return;
  if (state.current_player !== "j1") return;  // pas mon tour
```

par :

```js
async function handleCellClick(row, col) {
  if (!isHumanTurn(state)) return;
  if (state.wall_placement_mode) return;  // pas en mode mur
```

(Les checks `mode === ai_vs_ai`, `current_player !== j1`, et `status !== playing` sont toutes englobées par `isHumanTurn()`.)

- [ ] **Step 3 : Remplacer dans `handleIntersectionClick`**

Dans `webapp/static/app.js`, fonction `handleIntersectionClick` (vers ligne 307), remplacer :

```js
async function handleIntersectionClick(row, col) {
  if (!state || !state.wall_placement_mode) return;
  if (state.current_player !== "j1") return;
```

par :

```js
async function handleIntersectionClick(row, col) {
  if (!state || !state.wall_placement_mode) return;
  if (!isHumanTurn(state)) return;
```

- [ ] **Step 4 : Remplacer dans le `mouseenter` de `renderIntersections`**

Dans `webapp/static/app.js`, méthode `renderIntersections()` (vers ligne 77), remplacer :

```js
        dot.addEventListener("mouseenter", () => {
          if (!state || !state.wall_placement_mode) return;
          if (state.current_player !== "j1") return;
          dot.classList.add("hovered");
          addGhost(state.wall_placement_mode, r, c);
        });
```

par :

```js
        dot.addEventListener("mouseenter", () => {
          if (!state || !state.wall_placement_mode) return;
          if (!isHumanTurn(state)) return;
          dot.classList.add("hovered");
          addGhost(state.wall_placement_mode, r, c);
        });
```

- [ ] **Step 5 : Tester manuellement (régression HvAI)**

Run: `QUORIDOR_TRANSPORT=none python -m webapp.server`
Ouvrir `http://localhost:8000` :
- Lancer une partie HvAI → cliquer une case adjacente → le pion bouge, J2 (IA) joue son tour.
- Pendant le tour de l'IA, cliquer une case → rien ne se passe (toujours bloqué).

Arrêter le serveur.

- [ ] **Step 6 : Commit**

```bash
git add webapp/static/app.js
git commit -m "refactor(app.js): helper isHumanTurn pour generaliser autorisation des clics"
```

---

### Task 9 : `renderHeader()` adapté HvH + classes `turn-j1` / `turn-j2`

**Files:**
- Modify: `webapp/static/app.js:157-182` (fonction `renderHeader`)

- [ ] **Step 1 : Réécrire `renderHeader()`**

Dans `webapp/static/app.js`, remplacer la fonction `renderHeader()` complète par :

```js
function renderHeader(state) {
  document.getElementById("turn-count").textContent = state.turn_count;
  document.getElementById("j1-walls").textContent = state.players.j1.walls_remaining;
  document.getElementById("j2-walls").textContent = state.players.j2.walls_remaining;
  const ind = document.getElementById("turn-indicator");
  // Reset des classes
  ind.classList.remove("ai-thinking", "turn-j1", "turn-j2");
  if (state.status !== "playing" && state.status !== "paused") {
    ind.textContent = "";
    return;
  }
  if (state.status === "paused") {
    ind.textContent = "Pause";
    return;
  }
  if (state.ai_thinking) {
    ind.textContent = "IA réfléchit";
    ind.classList.add("ai-thinking");
    return;
  }
  // Couleur selon le joueur courant
  ind.classList.add(state.current_player === "j1" ? "turn-j1" : "turn-j2");
  if (state.mode === "ai_vs_ai") {
    ind.textContent = `Tour de ${state.current_player.toUpperCase()}`;
  } else if (state.mode === "human_vs_human") {
    ind.textContent = `AU TOUR DE ${state.current_player.toUpperCase()}`;
  } else /* human_vs_ai */ {
    ind.textContent = state.current_player === "j1" ? "TON TOUR" : "IA joue";
  }
}
```

- [ ] **Step 2 : Tester manuellement (régression + HvH)**

Run: `QUORIDOR_TRANSPORT=none python -m webapp.server`
- HvAI : démarre la partie → `#turn-indicator` affiche "TON TOUR" ; après un coup, "IA joue" puis "IA réfléchit" pendant la réflexion, puis "TON TOUR".
- HvH : démarre la partie → "AU TOUR DE J1" ; après un coup, "AU TOUR DE J2".
- AIvAI : démarre → "Tour de J1" alterne avec "Tour de J2".

(La couleur change déjà visuellement même sans CSS dédiée — la classe est posée, le style sera ajouté en Task 15.)

Arrêter le serveur.

- [ ] **Step 3 : Commit**

```bash
git add webapp/static/app.js
git commit -m "feat(app.js): renderHeader adapte aux 3 modes + classes turn-jX"
```

---

### Task 10 : Modal de transition (HTML + handler bouton OK)

**Files:**
- Modify: `webapp/static/index.html` (ajout du modal `#modal-transition`)
- Modify: `webapp/static/app.js` — ajout d'un handler dans `initHandlers()`

- [ ] **Step 1 : Ajouter le HTML de la modal**

Dans `webapp/static/index.html`, juste après le bloc `#modal-end` (vers ligne 155), ajouter :

```html
  <!-- ============ MODAL TRANSITION ENTRE TOURS (HvH) ============ -->
  <div id="modal-transition" class="modal hidden">
    <div class="modal-card">
      <div class="trophy">🎮</div>
      <h2 id="transition-text">À toi J1 !</h2>
      <p class="status-detail">Passe le téléphone et tape pour démarrer.</p>
      <div class="modal-actions">
        <button id="btn-transition-ok" class="btn-primary">Je suis prêt</button>
      </div>
    </div>
  </div>
```

- [ ] **Step 2 : Ajouter le handler dans `initHandlers()`**

Dans `webapp/static/app.js`, dans `initHandlers()`, juste avant la fin de la fonction (vers la ligne où `btn-home-from-end` est attaché, ligne ~427), ajouter :

```js
  // Modal de transition entre tours (HvH)
  document.getElementById("btn-transition-ok").addEventListener("click", () => {
    document.getElementById("modal-transition").classList.add("hidden");
  });
```

- [ ] **Step 3 : Tester manuellement**

Run: `QUORIDOR_TRANSPORT=none python -m webapp.server`
Ouvrir la console du navigateur, taper :

```js
document.getElementById("modal-transition").classList.remove("hidden")
```

→ la modal apparaît avec "À toi J1 !" et le bouton "Je suis prêt".
Cliquer "Je suis prêt" → modal disparaît.

Arrêter le serveur.

- [ ] **Step 4 : Commit**

```bash
git add webapp/static/index.html webapp/static/app.js
git commit -m "feat(webapp): modal de transition entre tours (HvH)"
```

---

### Task 11 : `maybeShowTransition()` + appel dans `render()`

**Files:**
- Modify: `webapp/static/app.js` (ajout fonction + appel)

- [ ] **Step 1 : Ajouter la fonction `maybeShowTransition`**

Dans `webapp/static/app.js`, juste avant la fonction `render()` (vers ligne 256), ajouter :

```js
// ============ TRANSITION HvH ============
let _lastTransitionTurn = -1;

function maybeShowTransition(state) {
  if (state.mode !== "human_vs_human") return;
  if (state.status === "waiting") {
    _lastTransitionTurn = -1;  // reset au retour a l'accueil
    return;
  }
  if (state.status !== "playing") return;
  if (state.turn_count === _lastTransitionTurn) return;
  _lastTransitionTurn = state.turn_count;
  const delayMs = state.turn_count === 0 ? 0 : 500;
  document.getElementById("transition-text").textContent =
    `À toi ${state.current_player.toUpperCase()} !`;
  setTimeout(() => {
    // Re-verifier au moment d'afficher : l'utilisateur a pu quitter entre temps
    if (state.status === "playing") {
      document.getElementById("modal-transition").classList.remove("hidden");
    }
  }, delayMs);
}
```

- [ ] **Step 2 : Appeler depuis `render()`**

Dans `webapp/static/app.js`, dans la fonction `render()`, juste après `renderModal(state);` (vers ligne 266), ajouter :

```js
  maybeShowTransition(state);
```

Le bloc devient :

```js
function render(newState) {
  state = newState;
  document.getElementById("overlay-reconnect").classList.add("hidden");
  renderViews(state);
  if (state.status !== "waiting") {
    renderWalls(state.walls);
    renderPawns(state.players);
    renderHeader(state);
    renderWallMode(state);
  }
  renderModal(state);
  maybeShowTransition(state);
  renderPlateauToggle(state);
  // ... reste inchangé
}
```

- [ ] **Step 3 : Tester manuellement**

Run: `QUORIDOR_TRANSPORT=none python -m webapp.server`
- Démarrer une partie HvH → la modal "À toi J1 !" apparaît immédiatement (delay 0).
- Tap "Je suis prêt" → modal disparaît, J1 peut jouer.
- Cliquer une case adjacente (J1 bouge) → ~500 ms après l'animation, modal "À toi J2 !".
- Tap "Je suis prêt" → modal disparaît, J2 peut jouer.
- Cliquer une case adjacente (J2 bouge) → ~500 ms après, modal "À toi J1 !".
- Important : la modal **ne réapparaît PAS** spontanément pendant le polling (vérifier en attendant 2-3 secondes après chaque tap "Je suis prêt").
- Quitter la partie via l'icône `←` → confirmer la sortie. Retour à l'accueil.
- Redémarrer une partie HvH → la modal "À toi J1 !" apparaît à nouveau (le reset de `_lastTransitionTurn` a fonctionné).

Tester aussi régression HvAI :
- Démarrer une partie HvAI → AUCUNE modal de transition ne doit s'afficher.

Arrêter le serveur.

- [ ] **Step 4 : Commit**

```bash
git add webapp/static/app.js
git commit -m "feat(webapp): pop-up de transition entre tours en mode HvH

Tracking par turn_count pour ne pas re-declencher la modal lors du
polling /api/state toutes les 500ms. Delai 500ms apres un coup pour
laisser voir l'animation du mur/pion ; delai 0 au premier tour."
```

---

### Task 12 : Rotation 180° du SVG au tour de J2 (CSS + JS)

**Files:**
- Modify: `webapp/static/style.css` (règles `#board` et `#board.flipped`)
- Modify: `webapp/static/app.js` (toggle dans `render()`)

- [ ] **Step 1 : Ajouter les règles CSS**

Dans `webapp/static/style.css`, juste après le bloc `#board { … }` existant (vers ligne 156), ajouter :

```css
#board {
  transition: transform 0.6s ease-in-out;
}
#board.flipped {
  transform: rotate(180deg);
}
```

Le bloc complet `#board` devient :

```css
#board { width: 100%; height: 100%; display: block; transition: transform 0.6s ease-in-out; }
#board.flipped { transform: rotate(180deg); }
```

- [ ] **Step 2 : Ajouter le toggle dans `render()`**

Dans `webapp/static/app.js`, dans la fonction `render()`, juste après `maybeShowTransition(state);` ajouter :

```js
  // Rotation 180 du plateau au tour de J2 en HvH
  const board = document.getElementById("board");
  const flip = state.mode === "human_vs_human" && state.current_player === "j2" && state.status === "playing";
  board.classList.toggle("flipped", flip);
```

- [ ] **Step 3 : Tester manuellement**

Run: `QUORIDOR_TRANSPORT=none python -m webapp.server`
- Démarrer une partie HvH → plateau dans son orientation normale (J1 en bas).
- J1 joue → plateau pivote de 180° (J2 voit son pion en bas de l'écran).
- J2 joue → plateau revient à l'orientation normale (J1 en bas).
- Cliquer sur une case près du pion J2 (qui apparaît en bas pour lui) → le déplacement fonctionne correctement (le navigateur gère les coords après rotation CSS).
- Régression HvAI : pas de rotation. Régression AIvAI : pas de rotation.

Arrêter le serveur.

- [ ] **Step 4 : Commit**

```bash
git add webapp/static/style.css webapp/static/app.js
git commit -m "feat(webapp): rotation 180 du plateau au tour de J2 en HvH

Seul le SVG du plateau pivote ; la status-bar et la game-bar restent
dans l'orientation normale pour la lisibilite du texte. Le navigateur
gere les coords des clics apres rotation CSS, pas de remapping
necessaire."
```

---

### Task 13 : Halo pulse sur le pion du joueur courant (CSS + JS)

**Files:**
- Modify: `webapp/static/style.css` (keyframes + classes)
- Modify: `webapp/static/app.js` (toggle dans `render()`)

- [ ] **Step 1 : Ajouter les règles CSS**

Dans `webapp/static/style.css`, juste après le bloc `.pawn { … }` existant (vers ligne 167), ajouter :

```css
@keyframes pawn-pulse {
  0%, 100% { filter: drop-shadow(0 0 0 transparent); }
  50%      { filter: drop-shadow(0 0 8px var(--halo)); }
}
.pawn.current { animation: pawn-pulse 1.4s ease-in-out infinite; }
#pawn-j1.current { --halo: #5b9fd9; }
#pawn-j2.current { --halo: #e57a6c; }
```

- [ ] **Step 2 : Ajouter le toggle dans `render()`**

Dans `webapp/static/app.js`, dans la fonction `render()`, juste après le toggle de `flipped` (Task 12), ajouter :

```js
  // Halo pulse sur le pion du joueur courant
  const isPlaying = state.status === "playing";
  document.getElementById("pawn-j1").classList.toggle(
    "current", isPlaying && state.current_player === "j1"
  );
  document.getElementById("pawn-j2").classList.toggle(
    "current", isPlaying && state.current_player === "j2"
  );
```

- [ ] **Step 3 : Tester manuellement**

Run: `QUORIDOR_TRANSPORT=none python -m webapp.server`
- HvAI : démarrer la partie → halo bleu autour du pion J1. Quand l'IA joue, halo rouge autour de J2.
- HvH : halo bleu autour de J1, puis rouge autour de J2 après le coup, alternance avec la rotation 180°.
- AIvAI : halo alterne bleu/rouge au rythme des tours.
- Fin de partie : aucun halo (status = `finished`).

Arrêter le serveur.

- [ ] **Step 4 : Commit**

```bash
git add webapp/static/style.css webapp/static/app.js
git commit -m "feat(webapp): halo pulse sur le pion du joueur courant"
```

---

## Phase Frontend — Refonte UI (CSS uniquement)

### Task 14 : Plateau bord à bord (CSS)

**Files:**
- Modify: `webapp/static/style.css` (`.board-wrap` et `#view-game`)

- [ ] **Step 1 : Retirer le `max-width: 360px` du `.board-wrap`**

Dans `webapp/static/style.css`, remplacer le bloc actuel (vers ligne 152) :

```css
.board-wrap {
  width: 100%; max-width: 360px; aspect-ratio: 1;
  margin: 0 auto;
}
```

par :

```css
.board-wrap {
  width: 100%; aspect-ratio: 1;
  margin: 0 auto;
}
```

- [ ] **Step 2 : Réduire le padding latéral de la vue jeu**

Dans `webapp/static/style.css`, ajouter après le bloc `.view` existant (vers ligne 33) :

```css
#view-game {
  padding-left: 8px;
  padding-right: 8px;
}
```

- [ ] **Step 3 : Tester manuellement sur petit écran (DevTools mobile)**

Run: `QUORIDOR_TRANSPORT=none python -m webapp.server`
Ouvrir `http://localhost:8000` dans Chrome avec DevTools en mode mobile (iPhone 12 Pro, 390 px de large) :
- Le plateau est visiblement plus large qu'avant (passe de ~320 px à ~374 px).
- Les cases sont plus grandes, plus faciles à viser au doigt.
- L'accueil reste avec son padding normal (20 px) — pas concerné par `#view-game`.

Arrêter le serveur.

- [ ] **Step 4 : Commit**

```bash
git add webapp/static/style.css
git commit -m "feat(webapp): plateau bord a bord (8px de padding en vue jeu)"
```

---

### Task 15 : Paddings game-bar/status-bar compactés + couleurs `turn-jX`

**Files:**
- Modify: `webapp/static/style.css` (paddings + couleurs)

- [ ] **Step 1 : Réduire les paddings**

Dans `webapp/static/style.css`, modifier les deux règles :

Remplacer (ligne ~121) :

```css
.game-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 4px 16px;
}
```

par :

```css
.game-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 4px 4px 8px;
}
```

Remplacer (ligne ~131) :

```css
.status-bar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0 6px 12px;
  font-size: 13px;
}
```

par :

```css
.status-bar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0 6px 8px;
  font-size: 13px;
}
```

- [ ] **Step 2 : Ajouter les couleurs `turn-j1` / `turn-j2`**

Dans `webapp/static/style.css`, juste après le bloc `#turn-indicator { … }` existant (vers ligne 146), ajouter :

```css
#turn-indicator.turn-j1 { background: rgba(31, 95, 143, 0.15); color: #1f5f8f; }
#turn-indicator.turn-j2 { background: rgba(156, 47, 35, 0.15); color: #9c2f23; }
```

- [ ] **Step 3 : Tester manuellement**

Run: `QUORIDOR_TRANSPORT=none python -m webapp.server`
- HvH : `#turn-indicator` est en bleu pâle quand "AU TOUR DE J1", en rouge pâle quand "AU TOUR DE J2".
- HvAI : `#turn-indicator` en bleu pâle pendant "TON TOUR", en rouge pâle pendant "IA joue".
- AIvAI : alternance bleu/rouge selon `current_player`.
- "IA réfléchit" (HvAI quand l'IA réfléchit) : pas de couleur de joueur (la classe `ai-thinking` reste, les classes `turn-jX` sont retirées dans `renderHeader`).
- Vue jeu prend moins de place verticale en haut (game-bar et status-bar plus compactes).

Arrêter le serveur.

- [ ] **Step 4 : Commit**

```bash
git add webapp/static/style.css
git commit -m "feat(webapp): paddings compactes en vue jeu + couleurs turn-jX du turn-indicator"
```

---

## Phase Validation finale

### Task 16 : Lancer tous les tests + checklist manuelle complète

**Files:** aucun

- [ ] **Step 1 : Lancer tous les tests backend**

Run: `pytest -m "not devkit"`
Expected: tous les tests verts, dont les 5 nouveaux tests HvH (1 schemas + 4 service).

Si un test échoue, corriger avant de poursuivre.

- [ ] **Step 2 : Test manuel — Accueil**

Run: `QUORIDOR_TRANSPORT=none python -m webapp.server`
Sur `http://localhost:8000` :
- [ ] Chip "Humain vs Humain" présent entre HvAI et AIvAI.
- [ ] Sélection HvH → bloc Difficulté disparaît.
- [ ] Sélection HvAI → bloc Difficulté visible, bloc Vitesse caché.
- [ ] Sélection AIvAI → bloc Difficulté visible, bloc Vitesse visible.
- [ ] Bouton "Partager sur téléphone" **absent**.

- [ ] **Step 3 : Test manuel — Partie HvH complète**

- [ ] "Commencer la partie" en HvH → modal "À toi J1 !" apparaît immédiatement.
- [ ] Tap "Je suis prêt" → modal se ferme.
- [ ] Halo bleu pulse autour du pion J1 (en bas).
- [ ] Indicateur de tour bleu pâle "AU TOUR DE J1".
- [ ] Cliquer une case adjacente → pion J1 bouge, ~500 ms plus tard modal "À toi J2 !".
- [ ] Plateau a pivoté de 180° (J2 voit son pion dans la moitié basse).
- [ ] Tap "Je suis prêt" → modal se ferme. Halo rouge autour du pion J2.
- [ ] Indicateur de tour rouge pâle "AU TOUR DE J2".
- [ ] Cliquer "Mur H" puis une intersection → mur posé, ~500 ms plus tard modal "À toi J1 !".
- [ ] Plateau revient à l'orientation normale.
- [ ] Cliquer icône `←` → confirmer → retour accueil. La modal de transition ne reste pas ouverte.
- [ ] Redémarrer une partie HvH → modal "À toi J1 !" réapparaît.

- [ ] **Step 4 : Test manuel — Régression HvAI**

- [ ] Démarrer une partie HvAI.
- [ ] Indicateur "TON TOUR" en bleu pâle, halo bleu sur pion J1.
- [ ] Aucune modal de transition n'apparaît.
- [ ] Pas de rotation du plateau.
- [ ] Faire un coup → "IA réfléchit" → puis "IA joue" → indicateur en rouge pâle, halo rouge sur pion J2.

- [ ] **Step 5 : Test manuel — Régression AIvAI**

- [ ] Démarrer une partie AIvAI.
- [ ] Tours alternent automatiquement, indicateur "Tour de J1" puis "Tour de J2".
- [ ] Halo alterne bleu/rouge selon le joueur en cours.
- [ ] Aucune modal de transition.
- [ ] Pas de rotation.
- [ ] Boutons "Pause" et chips de vitesse fonctionnent comme avant.

- [ ] **Step 6 : Test manuel — Plateau plus grand**

Sur Safari iOS (vrai téléphone ou DevTools Chrome iPhone 12 Pro) :
- [ ] Plateau visiblement plus large qu'avant le chantier.
- [ ] Cases plus faciles à viser au doigt.

- [ ] **Step 7 : (Optionnel) Test hardware**

Si plateau ESP32 disponible et opérationnel :

Run: `QUORIDOR_TRANSPORT=wifi python -m webapp.server` (ou `serial`)
- [ ] Mur posé par J1 en HvH → mécanique du plateau s'active, LED bleue allumée.
- [ ] Mur posé par J2 en HvH → mécanique s'active, LED rouge allumée.

Arrêter le serveur.

- [ ] **Step 8 : Commit du tag de validation (optionnel mais propre)**

Aucun fichier modifié — on n'a fait que valider. Pas de commit.

---

## Récapitulatif

**16 tasks**, environ **2h30 à 3h30** de travail au total :
- Backend (Tasks 1-5) : ~45 min — TDD strict, 5 tests ajoutés.
- Frontend logique (Tasks 8-13) : ~1h15 — helper, renderHeader, modal, transition, rotation, halo.
- Frontend refonte (Tasks 6, 7, 14, 15) : ~45 min — chip + suppression QR + CSS.
- Validation (Task 16) : ~20 min.

**16 commits** sur `main` (pas de feature branch dans ce projet).
