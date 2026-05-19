# Plan d'implémentation — UX placement de murs (webapp démo)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre fonctionnel et lisible le mode placement de murs dans la webapp Quoridor (cibles visibles, preview au hover desktop, animation au placement) — pour la démo de fin de Phase 5.

**Architecture:** Modifications frontend exclusivement (HTML statique, CSS, JS vanilla). Aucun changement Python — le contrat HTTP `/api/move` reste identique. Trois fichiers touchés : `webapp/static/index.html`, `webapp/static/style.css`, `webapp/static/app.js`.

**Tech Stack:** HTML5 + SVG inline, CSS3 (animations, `matchMedia`), JavaScript vanilla (pas de framework), FastAPI Python en backend (non touché).

**Référence design** : [docs/superpowers/specs/2026-05-19-walls-ux-improvement-design.md](../specs/2026-05-19-walls-ux-improvement-design.md)

**Tests** : Pas de test JS automatisé existant dans le projet, et conformément au scope du spec aucun n'est ajouté. La validation est manuelle (Safari Mac + iPhone) en Task 6. La non-régression backend (278 tests Python) est vérifiée par `pytest -m "not devkit" -q` également en Task 6.

**Pré-requis serveur** : le serveur webapp tourne déjà sur :8000 (lancé au début de session). Si arrêté entre-temps, relancer avec :
```bash
lsof -ti:8000 | xargs -r kill -9
python -m webapp.server
```

---

## Structure des fichiers

| Fichier | Responsabilité | Changement |
|---|---|---|
| `webapp/static/index.html` | Markup statique + SVG board | Retirer `class="hidden"` du `<g id="intersections">` ; ajouter `<g id="ghost"></g>` |
| `webapp/static/style.css` | Styles globaux et par composant | Refonte block `.intersection`, ajout `.ghost-wall`, `.wall.appearing`, keyframes `pulse-target` et `wall-appear`, ajout règle `#intersections { display: none; }` |
| `webapp/static/app.js` | Logique UI vanilla + polling | Constante `HAS_HOVER` au top-level ; `renderIntersections()` modifié (r=9 + listeners hover conditionnels) ; nouvelles fonctions `addGhost()` / `clearGhost()` ; `renderWalls()` modifié (diff oldKeys/newKeys pour animation) ; `renderWallMode()` modifié (clearGhost au changement) ; `handleIntersectionClick()` modifié (clearGhost succès et catch) |

Aucun fichier nouveau, aucune modification Python.

---

## Task 1 — Fix bug racine : rendre les intersections visibles

**Objectif** : déboucher le bug `.hidden` `!important` qui empêche les cibles d'apparaître en mode placement. À la fin de cette task, on doit voir **les cibles existantes** (r=7, opacité 0.35) — moches mais présentes. Ça valide que le fix CSS est correct avant de styliser.

**Files:**
- Modify: `webapp/static/index.html` (ligne 102)
- Modify: `webapp/static/style.css` (ajout après ligne 35)

- [ ] **Step 1.1 : Retirer `class="hidden"` du `<g id="intersections">` dans index.html**

Dans [webapp/static/index.html](../../webapp/static/index.html), ligne 102, remplacer :
```html
        <g id="intersections" class="hidden"></g>
```
par :
```html
        <g id="intersections"></g>
```

- [ ] **Step 1.2 : Ajouter règle `#intersections { display: none; }` dans style.css**

Dans [webapp/static/style.css](../../webapp/static/style.css), juste après la règle `.hidden` (ligne 35), ajouter :
```css
#intersections { display: none; }
```

La règle existante `body.wall-placement #intersections { display: block; }` (ligne 235 du CSS) va maintenant gagner par spécificité (1 classe + 1 id + 1 type vs 1 id seul), sans nécessiter `!important`.

- [ ] **Step 1.3 : Vérifier visuellement dans Safari Mac**

Recharger http://localhost:8000 (Cmd+R), démarrer une partie Humain vs IA, taper "Mur H".

Attendu :
- Les cases s'assombrissent (opacity 0.6, comportement existant)
- **De petits cercles orange à 35% d'opacité (r=7) apparaissent aux intersections** (5×5 = 25 points)
- Ces points étaient invisibles avant cette task

Si invisibles encore : vérifier la console DevTools, possiblement cache CSS. Hard reload : Cmd+Shift+R.

- [ ] **Step 1.4 : Pas de commit ici** — la task suivante va styliser ces cibles, on commit le tout ensemble en Task 2.

---

## Task 2 — Style des cibles (Package A½B)

**Objectif** : refonte du style `.intersection` selon les specs (r=9, opacité 0.85, halo blanc, pulse 1.8s, hover state agrandi).

**Files:**
- Modify: `webapp/static/style.css` (block `.intersection` ligne 169-173)
- Modify: `webapp/static/app.js` (fonction `renderIntersections()` ligne 53-77, ligne 70 `r=7` → `r=9`)

- [ ] **Step 2.1 : Remplacer le block `.intersection` dans style.css**

Dans [webapp/static/style.css](../../webapp/static/style.css), remplacer les lignes 169-173 :
```css
.intersection {
  fill: var(--primary); opacity: 0.35; cursor: pointer;
  transition: opacity 0.15s;
}
.intersection:active { opacity: 0.8; }
```
par :
```css
.intersection {
  fill: var(--primary);
  opacity: 0.85;
  stroke: var(--bg);
  stroke-width: 1.5;
  cursor: pointer;
  animation: pulse-target 1.8s ease-in-out infinite;
  transition: r 0.15s, stroke-width 0.15s;
}
.intersection.hovered {
  r: 11;
  opacity: 1;
  animation-play-state: paused;
}
.intersection:active { opacity: 1; }

@keyframes pulse-target {
  0%, 100% { opacity: 0.85; }
  50% { opacity: 0.65; }
}
```

- [ ] **Step 2.2 : Augmenter le rayon dans `renderIntersections()`**

Dans [webapp/static/app.js](../../webapp/static/app.js), ligne 70, remplacer :
```js
      dot.setAttribute("r", 7);
```
par :
```js
      dot.setAttribute("r", 9);
```

- [ ] **Step 2.3 : Vérifier visuellement dans Safari Mac**

Hard reload (Cmd+Shift+R), démarrer une partie Humain vs IA, taper "Mur H".

Attendu :
- 25 cibles orange visibles, **plus grosses** (r=9), avec **halo blanc** autour (stroke 1.5px sur fond bg)
- **Pulse doux** (1.8s) : l'opacité oscille entre 0.85 et 0.65 — visible mais pas crispant
- Cliquer une cible → mur posé (comportement existant). Le mur apparaît instantanément (l'animation viendra en Task 5).

Si pas de pulse : vérifier que `@keyframes pulse-target` est bien dans le CSS. Si halo invisible : vérifier `--bg` (devrait être `#faf6ee`).

- [ ] **Step 2.4 : Commit intermédiaire**

```bash
git add webapp/static/index.html webapp/static/style.css webapp/static/app.js
git commit -m "$(cat <<'EOF'
fix(webapp): cibles murs visibles + style affordance forte

- retire class="hidden" sur #intersections (bug !important)
- refonte CSS .intersection : r=9, opacite 0.85, halo blanc 1.5px, pulse 1.8s
- ajout .intersection.hovered (r=11) en preparation du ghost wall

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3 — Ghost wall : preview au hover desktop

**Objectif** : ajouter le calque `<g id="ghost">`, les fonctions `addGhost()` / `clearGhost()` et les listeners hover (desktop uniquement, via `matchMedia`).

**Files:**
- Modify: `webapp/static/index.html` (SVG board, ajout `<g id="ghost">`)
- Modify: `webapp/static/style.css` (ajout règle `.ghost-wall`)
- Modify: `webapp/static/app.js` (constante `HAS_HOVER`, fonctions `addGhost`/`clearGhost`, listeners hover dans `renderIntersections()`)

- [ ] **Step 3.1 : Ajouter `<g id="ghost"></g>` dans le SVG board**

Dans [webapp/static/index.html](../../webapp/static/index.html), ligne 101-102, transformer :
```html
        <g id="walls-layer"></g>
        <g id="intersections"></g>
```
en :
```html
        <g id="walls-layer"></g>
        <g id="ghost"></g>
        <g id="intersections"></g>
```

L'ordre est important : ghost sous les intersections (pour ne pas bloquer le clic via `pointer-events`), au-dessus de walls-layer (pour rester visible).

- [ ] **Step 3.2 : Ajouter règle `.ghost-wall` dans style.css**

Dans [webapp/static/style.css](../../webapp/static/style.css), ajouter après la règle `.wall { fill: url(#wallGrad); }` (ligne 167) :
```css
.ghost-wall {
  fill: url(#wallGrad);
  opacity: 0.42;
  stroke: var(--primary);
  stroke-width: 1;
  stroke-dasharray: 3, 2;
  pointer-events: none;
}
```

`pointer-events: none` est crucial : sinon le ghost intercepterait le clic destiné à l'intersection en dessous.

- [ ] **Step 3.3 : Ajouter la constante `HAS_HOVER` au top-level de app.js**

Dans [webapp/static/app.js](../../webapp/static/app.js), juste après la déclaration `let pendingWallMode = null;` (ligne 10), ajouter :
```js
const HAS_HOVER = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
```

Cette constante est figée au chargement de la page. Sur Mac/PC : `true`. Sur iPhone/iPad tactile : `false`. Sur iPad avec trackpad : `true`.

- [ ] **Step 3.4 : Ajouter les fonctions `addGhost()` et `clearGhost()`**

Dans [webapp/static/app.js](../../webapp/static/app.js), ajouter juste après la fonction `renderWalls()` (après ligne 103) :
```js
function addGhost(orientation, row, col) {
  const layer = document.getElementById("ghost");
  const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  rect.setAttribute("class", "ghost-wall");
  if (orientation === "h") {
    const { x, y } = cellTopLeftXY(row + 1, col);
    rect.setAttribute("x", x);
    rect.setAttribute("y", y - 3);
    rect.setAttribute("width", CELL * 2);
    rect.setAttribute("height", 6);
  } else {
    const { x, y } = cellTopLeftXY(row, col + 1);
    rect.setAttribute("x", x - 3);
    rect.setAttribute("y", y);
    rect.setAttribute("width", 6);
    rect.setAttribute("height", CELL * 2);
  }
  rect.setAttribute("rx", "2");
  layer.replaceChildren(rect);
}

function clearGhost() {
  document.getElementById("ghost").replaceChildren();
}
```

`replaceChildren(rect)` remplace tout le contenu du `<g>` par le nouveau rect — pas de risque d'accumulation si appelé deux fois de suite.

- [ ] **Step 3.5 : Attacher les listeners hover conditionnels dans `renderIntersections()`**

Dans [webapp/static/app.js](../../webapp/static/app.js), modifier `renderIntersections()` (ligne 53-77). Juste après la ligne `dot.addEventListener("click", () => handleIntersectionClick(r, c));` (ligne 73), ajouter :
```js
      if (HAS_HOVER) {
        dot.addEventListener("mouseenter", () => {
          if (!state || !state.wall_placement_mode) return;
          if (state.current_player !== "j1") return;
          dot.classList.add("hovered");
          addGhost(state.wall_placement_mode, r, c);
        });
        dot.addEventListener("mouseleave", () => {
          dot.classList.remove("hovered");
          clearGhost();
        });
      }
```

Les gardes (`!state.wall_placement_mode`, `current_player !== "j1"`) évitent d'afficher un ghost quand ce n'est pas pertinent (mode déplacement actif, tour IA, etc.).

- [ ] **Step 3.6 : Vérifier visuellement dans Safari Mac**

Hard reload, démarrer partie Humain vs IA, taper "Mur H".

Attendu :
- Survoler une intersection → cible grossit (r=11), pulse s'arrête, **ghost wall semi-transparent (op 0.42) avec contour pointillé apparaît** à l'endroit du futur mur (horizontalement, longueur 2 cases)
- Bouger la souris vers une autre intersection → le ghost suit, pas d'accumulation
- Sortir du board → le ghost disparaît
- Cliquer une intersection → mur posé (toujours pas d'animation : Task 5)

- [ ] **Step 3.7 : Test mode "Mur V"**

Taper "Mur V", survoler une intersection.

Attendu : le ghost est **vertical** (longueur 2 cases verticalement), au bon endroit.

- [ ] **Step 3.8 : Commit**

```bash
git add webapp/static/index.html webapp/static/style.css webapp/static/app.js
git commit -m "$(cat <<'EOF'
feat(webapp): ghost wall preview au hover desktop

- ajoute <g id=\"ghost\"> entre walls-layer et intersections
- CSS .ghost-wall : op 0.42 + contour pointille, pointer-events none
- detection HAS_HOVER via matchMedia
- listeners mouseenter/leave conditionnels sur intersections

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4 — Resets propres du ghost wall

**Objectif** : s'assurer que le ghost est nettoyé dans 3 cas (changement de mode H/V, click validé, click échoué). Sinon le ghost peut rester collé à l'écran.

**Files:**
- Modify: `webapp/static/app.js` (fonction `renderWallMode()` + fonction `handleIntersectionClick()`)

- [ ] **Step 4.1 : Tracker l'orientation précédente et clearGhost au changement**

Dans [webapp/static/app.js](../../webapp/static/app.js), juste avant la fonction `renderWallMode()` (ligne 166), ajouter :
```js
let _prevWallMode = null;
```

Puis remplacer la fonction `renderWallMode()` (lignes 166-170) :
```js
function renderWallMode(state) {
  document.body.classList.toggle("wall-placement", !!state.wall_placement_mode);
  document.getElementById("btn-wall-h").classList.toggle("active", state.wall_placement_mode === "h");
  document.getElementById("btn-wall-v").classList.toggle("active", state.wall_placement_mode === "v");
}
```
par :
```js
function renderWallMode(state) {
  document.body.classList.toggle("wall-placement", !!state.wall_placement_mode);
  document.getElementById("btn-wall-h").classList.toggle("active", state.wall_placement_mode === "h");
  document.getElementById("btn-wall-v").classList.toggle("active", state.wall_placement_mode === "v");
  if (_prevWallMode !== state.wall_placement_mode) {
    clearGhost();
    _prevWallMode = state.wall_placement_mode;
  }
}
```

- [ ] **Step 4.2 : Modifier `handleIntersectionClick()` pour clearGhost succès ET catch**

Dans [webapp/static/app.js](../../webapp/static/app.js), remplacer la fonction `handleIntersectionClick()` (lignes 260-275) :
```js
async function handleIntersectionClick(row, col) {
  if (!state || !state.wall_placement_mode) return;
  if (state.current_player !== "j1") return;
  const orientation = state.wall_placement_mode;
  try {
    const next = await api("POST", "/api/move", {
      type: "mur",
      orientation,
      row,
      col,
    });
    render(next);
  } catch (e) {
    showToast(`Coup impossible : ${e.message}`);
  }
}
```
par :
```js
async function handleIntersectionClick(row, col) {
  if (!state || !state.wall_placement_mode) return;
  if (state.current_player !== "j1") return;
  const orientation = state.wall_placement_mode;
  try {
    const next = await api("POST", "/api/move", {
      type: "mur",
      orientation,
      row,
      col,
    });
    clearGhost();
    render(next);
  } catch (e) {
    clearGhost();
    showToast(`Coup impossible : ${e.message}`);
  }
}
```

- [ ] **Step 4.3 : Vérifier visuellement le changement d'orientation**

Hard reload, partie Humain vs IA, taper "Mur H", survoler une intersection (ghost H affiché), **sans cliquer** taper "Mur V".

Attendu :
- Le ghost H disparaît immédiatement
- Au prochain mouseenter sur une intersection, un ghost V apparaît (vertical)

- [ ] **Step 4.4 : Vérifier visuellement le clearGhost après click**

Survoler une intersection (ghost affiché), cliquer.

Attendu :
- Le ghost disparaît
- Le mur réel apparaît (toujours pas d'animation : Task 5)
- Si on bouge ensuite la souris, un nouveau ghost peut apparaître à la nouvelle position (normal, mode toujours actif)

- [ ] **Step 4.5 : Vérifier visuellement le clearGhost après erreur**

Provoquer une erreur : taper "Mur H", survoler le coin haut-droit (intersection 0,4), cliquer. Le serveur devrait accepter (ou refuser selon position, peu importe). Provoquer une vraie erreur : poser plusieurs murs dans la même ligne pour finir par bloquer un chemin.

Plus simple à reproduire : poser un mur H valide, puis re-taper exactement au même endroit → erreur "intersection occupée".

Attendu :
- Toast "Coup impossible : ..."
- Le ghost a disparu (pas collé à l'écran)
- Le mode placement est resté actif

- [ ] **Step 4.6 : Commit**

```bash
git add webapp/static/app.js
git commit -m "$(cat <<'EOF'
feat(webapp): clearGhost lors des transitions d'etat

- renderWallMode track _prevWallMode pour clear au changement H/V/null
- handleIntersectionClick clearGhost succes ET catch

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5 — Animation `.appearing` au placement de mur

**Objectif** : à chaque nouveau mur posé (humain ou IA), jouer une animation 200ms scale + opacity. Donne un feedback visuel clair que le mur a été placé, en particulier sur mobile (pas de ghost).

**Files:**
- Modify: `webapp/static/style.css` (ajout keyframes + classe `.wall.appearing`)
- Modify: `webapp/static/app.js` (fonction `renderWalls()` ligne 79-103)

- [ ] **Step 5.1 : Ajouter keyframes `wall-appear` et classe `.wall.appearing` dans style.css**

Dans [webapp/static/style.css](../../webapp/static/style.css), juste après la règle `.wall { fill: url(#wallGrad); }` (ligne 167) — donc avant `.ghost-wall` ajouté en Task 3 —, ajouter :
```css
@keyframes wall-appear {
  from { opacity: 0; transform: scale(0.85); }
  to { opacity: 1; transform: scale(1); }
}
.wall.appearing {
  animation: wall-appear 200ms ease-out;
  transform-box: fill-box;
  transform-origin: center;
}
```

`transform-box: fill-box` est essentiel pour que `transform-origin: center` scale depuis le centre du `<rect>` et pas depuis le coin (0,0) du SVG.

- [ ] **Step 5.2 : Modifier `renderWalls()` pour diff oldKeys/newKeys**

Dans [webapp/static/app.js](../../webapp/static/app.js), remplacer la fonction `renderWalls()` (lignes 79-103) :
```js
function renderWalls(walls) {
  const layer = document.getElementById("walls-layer");
  layer.innerHTML = "";
  for (const w of walls) {
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("class", "wall");
    if (w.orientation === "h") {
      // Mur horizontal entre row w.row et w.row+1, couvre cols w.col et w.col+1
      const { x, y } = cellTopLeftXY(w.row + 1, w.col);
      rect.setAttribute("x", x);
      rect.setAttribute("y", y - 3);
      rect.setAttribute("width", CELL * 2);
      rect.setAttribute("height", 6);
    } else {
      // Mur vertical entre col w.col et w.col+1, couvre rows w.row et w.row+1
      const { x, y } = cellTopLeftXY(w.row, w.col + 1);
      rect.setAttribute("x", x - 3);
      rect.setAttribute("y", y);
      rect.setAttribute("width", 6);
      rect.setAttribute("height", CELL * 2);
    }
    rect.setAttribute("rx", "2");
    layer.appendChild(rect);
  }
}
```
par :
```js
function renderWalls(walls) {
  const layer = document.getElementById("walls-layer");
  const oldKeys = new Set([...layer.children].map(c => c.dataset.key));
  layer.innerHTML = "";
  for (const w of walls) {
    const key = `${w.orientation}-${w.row}-${w.col}`;
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("class", "wall" + (oldKeys.has(key) ? "" : " appearing"));
    rect.dataset.key = key;
    if (w.orientation === "h") {
      // Mur horizontal entre row w.row et w.row+1, couvre cols w.col et w.col+1
      const { x, y } = cellTopLeftXY(w.row + 1, w.col);
      rect.setAttribute("x", x);
      rect.setAttribute("y", y - 3);
      rect.setAttribute("width", CELL * 2);
      rect.setAttribute("height", 6);
    } else {
      // Mur vertical entre col w.col et w.col+1, couvre rows w.row et w.row+1
      const { x, y } = cellTopLeftXY(w.row, w.col + 1);
      rect.setAttribute("x", x - 3);
      rect.setAttribute("y", y);
      rect.setAttribute("width", 6);
      rect.setAttribute("height", CELL * 2);
    }
    rect.setAttribute("rx", "2");
    layer.appendChild(rect);
  }
}
```

Le `oldKeys` est capturé **avant** `layer.innerHTML = ""` (sinon il serait toujours vide). Pour les murs déjà présents au tick précédent, pas d'animation. Pour les nouveaux, classe `.appearing` qui joue l'animation 200ms.

- [ ] **Step 5.3 : Vérifier visuellement sur Mac**

Hard reload, partie Humain vs IA, taper "Mur H", cliquer une intersection.

Attendu :
- Le mur apparaît avec **animation 200ms** : démarre légèrement plus petit (scale 0.85), grossit jusqu'à scale 1, opacité 0 → 1
- Sur les ticks de polling suivants (500ms après), le mur ne rejoue pas l'animation (`oldKeys` contient sa clé)

- [ ] **Step 5.4 : Vérifier que l'IA bénéficie aussi de l'animation**

Attendre que l'IA pose un mur (peut prendre plusieurs tours, ou tester en mode "IA vs IA" qui en pose souvent).

Attendu : les murs IA apparaissent aussi avec l'animation 200ms (bénéfice secondaire de la feature).

- [ ] **Step 5.5 : Vérifier reload Cmd+R en cours de partie**

Avec quelques murs posés, recharger la page.

Attendu : tous les murs réapparaissent **avec l'animation** (au premier render, tous sont "nouveaux" car `oldKeys` est vide). C'est acceptable visuellement (effet de "draw-in" au chargement).

- [ ] **Step 5.6 : Commit**

```bash
git add webapp/static/style.css webapp/static/app.js
git commit -m "$(cat <<'EOF'
feat(webapp): animation .appearing 200ms a la pose d'un mur

- keyframes wall-appear : scale 0.85->1 + opacity 0->1
- renderWalls diff oldKeys/newKeys via data-key sur <rect>
- bonus : murs IA profitent aussi de l'animation

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6 — Validation manuelle complète + non-régression

**Objectif** : exécuter la checklist du spec section 6, vérifier qu'aucun test backend n'est cassé.

**Files:** aucun fichier modifié dans cette task — pure validation.

- [ ] **Step 6.1 : Lancer pytest backend (non-régression)**

```bash
cd /Users/silouanechaumais/Documents/01_ICAM/2025-2026_Année_3/Projet_mécatronique/programmation
pytest -m "not devkit" -q
```

Attendu : `278 passed` (baseline d'avant cette session). Si un test échoue, c'est une régression — vérifier la cause (improbable car aucun fichier Python touché).

- [ ] **Step 6.2 : Tests Safari Mac — Tableau 1 (mode placement)**

Vérifier chaque ligne ci-dessous (issu de la section 6.1 du spec). Pour chaque ligne, noter ✅ ou ❌.

| # | Action | Résultat attendu |
|---|---|---|
| 1 | Démarrer Humain vs IA, taper "Mur H" | Cases assombries, **25 cibles orange r=9 + halo blanc** visibles, pulse 1.8s |
| 2 | Survoler une intersection sans cliquer | Cible r=11, op 1, pulse pausé, **ghost wall pointillé** apparaît à l'endroit du futur mur H |
| 3 | Bouger la souris vers une autre intersection | Ghost suit sans accumulation, cible précédente revient à r=9 |
| 4 | Sortir du board avec la souris | Ghost disparaît, toutes cibles à r=9 + pulse |
| 5 | Survoler puis cliquer | Ghost s'efface, mur réel apparaît avec animation 200ms, J1 : 6 → 5 |
| 6 | Re-taper "Mur H" alors qu'il est actif | Mode désactivé, cibles cachées, cases retrouvent opacité normale |
| 7 | "Mur H" actif, survoler, taper "Mur V" sans cliquer | Ghost H s'efface, mouseenter suivant régénère un ghost V |
| 8 | Tenter un mur invalide (rejouer même position 2 fois) | Toast d'erreur, ghost effacé, mode placement reste actif |
| 9 | Reload Cmd+R en mode placement | Page recharge, mode placement remis, cibles visibles |

- [ ] **Step 6.3 : Tests iPhone Safari — Tableau 2 (mobile)**

Vérifier IP locale avec :
```bash
ipconfig getifaddr en0
```

Sur iPhone, ouvrir `http://<ip-mac>:8000` (même Wi-Fi). Vérifier :

| # | Action | Résultat attendu |
|---|---|---|
| 1 | Démarrer partie, taper "Mur H" | Cibles visibles, pulse 1.8s OK |
| 2 | Taper directement une intersection | **Pas de ghost** (pas de hover), mur réel apparaît avec animation 200ms |
| 3 | Fiabilité du tap sur cible r=9 + halo | Aucun mistap perçu |
| 4 | Tenter mur invalide via tap | Toast erreur, mode reste actif |

Si problème de tap (mistap récurrent) : noter pour follow-up éventuel (hitbox invisible mentionnée dans le spec §7.1).

- [ ] **Step 6.4 : Tests non-régression UI — Tableau 3**

Sur Safari Mac uniquement :

| # | Action | Résultat attendu |
|---|---|---|
| 1 | Mode déplacement (cases cliquables) | Toujours fonctionnel, animation pion 400ms intacte |
| 2 | Mode IA vs IA | Boutons Mur H/V invisibles, murs IA s'affichent avec animation 200ms |
| 3 | Fin de partie | Modal s'affiche normalement, boutons Rejouer/Accueil OK |
| 4 | Mur invalide répété (même position 3 fois) | Toast affiché 1 seule fois (anti-spam existant intact) |

- [ ] **Step 6.5 : Si tout passe, dernière étape — confirmation textuelle de validation**

Si toutes les cases du tableau précédent sont ✅ ET pytest est vert, l'implémentation est validée. Pas de commit additionnel ici (tout a été committé task par task).

Si une case échoue : noter le numéro, analyser le problème, soit corriger inline avec un nouveau commit `fix(webapp): ...`, soit reporter au prochain cycle si bénin.

---

## Vérification de couverture du spec

Self-check des 8 sections du spec :

| Section spec | Couvert par task |
|---|---|
| §1 Contexte (bug racine + 2 autres symptômes) | T1 (bug racine), T2 (visibilité), T3 (feedback) |
| §2 Scope (niveau 2, pattern A, style A½B) | T1-T5 (implémentation), T6 (validation) |
| §3 Architecture (3 fichiers, HAS_HOVER, ordre layers) | T3.1 (`<g id="ghost">`), T3.3 (HAS_HOVER) |
| §4.1 Cibles d'intersection | T1+T2 |
| §4.2 Ghost wall | T3 |
| §4.3 Animation tap mobile (`.appearing`) | T5 |
| §4.4 Resets clearGhost (3 cas) | T4 (cas 2+3), T3.5 (cas 1 = mouseleave) |
| §5 Data flow (desktop + mobile + edge cases) | Validé en T6 |
| §6 Plan validation manuelle | T6 |
| §7 Suivis potentiels (hitbox, pulse décalé) | Notés dans T6.3 si problème |
| §8 Hors scope (rappel) | Aucune task pour ces points (correct) |

Tous les éléments du spec sont couverts par au moins une task.

---

## Notes pour l'engineer qui exécute

- **Pas de framework JS** : tout est vanilla DOM API + SVG. Pas de React/Vue.
- **Pas de bundler** : les fichiers `static/*` sont servis tels quels par FastAPI. Pas de `npm run build`. Hard reload Cmd+Shift+R pour bypasser le cache.
- **Polling 500ms** : le state se rafraîchit toutes les 500ms via `/api/state`. Toutes les fonctions `renderXxx()` sont idempotentes par design.
- **Pas de routing client** : une seule page, deux vues togglées par la classe `.hidden` (qui utilise `!important` partout). Attention : si tu réintroduis `.hidden` quelque part dans le SVG, tu retombes sur le bug racine de T1.
- **Frontend testing** : aucun test JS dans le projet. Tu peux ajouter `console.log` ad libitum pour débugger, ils s'afficheront dans la console DevTools du browser. Pense à les retirer avant le commit final.
- **Commits** : fréquents, un par task. Sauf T1 qui se commit avec T2 (T1 seul = état intermédiaire moche pas worth a commit).
