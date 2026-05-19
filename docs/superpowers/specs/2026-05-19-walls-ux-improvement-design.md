# Spec — Amélioration UX placement de murs (webapp démo)

**Date** : 2026-05-19
**Branche** : `feat/webapp-demo` (continuation, pas de nouvelle branche)
**Statut** : conçu — en attente de relecture utilisateur avant plan d'implémentation
**Phase** : suite Phase 5 du plan webapp ([`docs/superpowers/plans/2026-05-18-webapp-demo-quoridor.md`](../plans/2026-05-18-webapp-demo-quoridor.md))

---

## 1. Contexte

Lors des tests manuels Safari Mac de la webapp démo Quoridor, l'utilisateur a constaté que le mode "placement de mur" est cassé : taper sur "Mur H" ou "Mur V" active visiblement quelque chose (les cases s'assombrissent légèrement), mais **les cibles d'intersection sont invisibles** — impossible de comprendre où cliquer pour poser un mur. Trois symptômes superposés :

1. **Bug racine CSS** (caché par les autres) : dans [webapp/static/index.html:102](../../../webapp/static/index.html#L102), `<g id="intersections" class="hidden">` est combiné avec `.hidden { display: none !important; }` ([style.css:35](../../../webapp/static/style.css#L35)) et `body.wall-placement #intersections { display: block; }` ([style.css:235](../../../webapp/static/style.css#L235)). Le `!important` de `.hidden` bat `display: block`. **Conclusion : les cibles ne sont jamais visibles, quel que soit le mode.**
2. **Cibles sous-dimensionnées** : `r=7` sur cellule de 50 unités SVG (= 14 % de la cellule), opacité 0.35 sur couleur primary fondue dans le fond beige.
3. **Aucun feedback sur le placement** : pas de preview du mur avant clic, pas d'animation de pose, pas de hint texte.

L'utilisateur a proposé "cliquer 2 cases pour poser un mur (comme sur le plateau physique)" — rejeté car mathématiquement ambigu : un mur Quoridor sépare 4 cases, deux clics ne suffisent pas à le définir sans convention arbitraire. On garde le paradigme actuel (mode H/V + clic intersection) et on en améliore l'affordance.

## 2. Scope

### Niveau d'ambition retenu

**Niveau 2** (sur 3 envisagés) : cibles visibles + preview du mur au hover desktop. Pas de hint texte (niveau 3 écarté pour rester focus démo).

### Pattern de validation retenu

**Pattern A** : desktop hover affiche un ghost wall ; mobile tap = placement direct + animation 200ms "draw" du mur. Pas de double-tap obligatoire (frustration sur coups rapides), pas d'undo (non implémenté côté serveur).

### Style visuel retenu

Compromis "A½B" entre minimal-élégant et affordance-forte :

| Élément | Spécification |
|---|---|
| Cible rayon (idle) | `r=9` |
| Cible opacité | `0.85` |
| Cible halo blanc | `stroke=var(--bg)`, `stroke-width=1.5` |
| Cible hover | `r=11`, `opacity=1`, `animation-play-state: paused` |
| Pulse animation | 1.8s ease-in-out, opacity 0.85↔0.65 |
| Ghost wall opacité | `0.42` |
| Ghost wall contour | dashed `3,2`, stroke 1px primary |
| Animation mur posé | 200ms ease-out, scale 0.85→1 + opacity 0→1 |

### Hors scope (YAGNI démo)

- Undo / annulation d'un mur posé
- Navigation clavier sur les intersections
- Accessibilité screen reader poussée (rôles aria étendus)
- Validation côté client du mur (chemin, collision) — le serveur tranche, on affiche le toast en cas d'erreur
- Tests JS automatisés ajoutés (aucun n'existe dans le projet ; validation = test manuel Safari Mac + iPhone)
- Hint texte d'aide ("Touche entre 4 cases pour…") — niveau 3 écarté

## 3. Architecture

**Modifications frontend uniquement.** Backend (Python), schémas Pydantic, route `POST /api/move`, et contrat HTTP `{type: "mur", orientation, row, col}` : **aucun changement**.

### Fichiers touchés

| Fichier | Nature du changement |
|---|---|
| [webapp/static/index.html](../../../webapp/static/index.html) | Retire `class="hidden"` du `<g id="intersections">` ; ajoute `<g id="ghost"></g>` dans le SVG board entre `walls-layer` et `intersections` (1 ligne) |
| [webapp/static/style.css](../../../webapp/static/style.css) | Refonte du block `.intersection` ; ajout `.intersection.hovered`, `.ghost-wall`, `.wall.appearing` ; keyframes `pulse-target` et `wall-appear` ; ajout `#intersections { display: none; }` sans `!important` |
| [webapp/static/app.js](../../../webapp/static/app.js) | `renderIntersections()` : `r=9` + listeners hover conditionnels ; nouvelles fonctions `addGhost()` / `clearGhost()` ; `renderWalls()` modifié pour détecter les nouveaux murs (animation `.appearing`) ; `renderWallMode()` appelle `clearGhost()` au changement de mode ; `handleIntersectionClick()` appelle `clearGhost()` succès ET catch ; constante `HAS_HOVER` au top-level |

Pas de fichier nouveau, pas de dépendance ajoutée, pas de modification Python.

### Détection desktop vs mobile

```js
const HAS_HOVER = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
```

Évalué une seule fois au top-level de `app.js`. Pas l'user-agent (trompeur), pas la taille d'écran (faux pour iPad+clavier). Sur iPad avec trackpad : `HAS_HOVER=true`. Sur iPhone : `false`. Sur Mac : `true`.

### Ordre des couches SVG (board)

```
<g id="cells">       (fond, cellules)
<g id="walls-layer"> (murs réels)
<g id="ghost">       (NOUVEAU — ghost wall en preview)
<g id="intersections">
pawn-j1, pawn-j2     (pions au-dessus)
```

Ghost sous les intersections pour ne pas bloquer le clic ; au-dessus des cells/walls pour rester visible ; sous les pions pour ne pas les masquer.

## 4. Composants détaillés

### 4.1 — Cibles d'intersection

**HTML** (modification) :
```html
<!-- avant -->
<g id="intersections" class="hidden"></g>
<!-- après -->
<g id="intersections"></g>
```

**CSS** :
```css
#intersections { display: none; }
body.wall-placement #intersections { display: block; }

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
.intersection:active { opacity: 1; }  /* feedback tap mobile */

@keyframes pulse-target {
  0%, 100% { opacity: 0.85; }
  50% { opacity: 0.65; }
}
```

**app.js — `renderIntersections()` (modifié)** :
- Passe `r=7` à `r=9` à la création du `<circle>`.
- Ajoute conditionnellement (si `HAS_HOVER`) listeners `mouseenter` → `dot.classList.add("hovered")` + `addGhost(state.wall_placement_mode, r, c)` et `mouseleave` → `dot.classList.remove("hovered")` + `clearGhost()`.
- Sur mobile (`!HAS_HOVER`), aucun listener hover attaché (le tap continue de fonctionner via le listener `click` existant).

**Nombre de cibles** : 5×5 = **25 intersections internes** sur un plateau 6×6.

### 4.2 — Ghost wall (preview hover desktop)

**HTML** (ajout) — dans le `<svg id="board">`, juste avant `<g id="intersections">` :
```html
<g id="ghost"></g>
```

**CSS** :
```css
.ghost-wall {
  fill: url(#wallGrad);
  opacity: 0.42;
  stroke: var(--primary);
  stroke-width: 1;
  stroke-dasharray: 3, 2;
  pointer-events: none;  /* ne bloque pas le clic sur intersection */
}
```

**app.js — nouvelles fonctions** :
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
  layer.replaceChildren(rect);  // remplace au lieu d'append → pas d'accumulation
}

function clearGhost() {
  document.getElementById("ghost").replaceChildren();
}
```

Les dimensions et le positionnement sont **identiques** à `renderWalls()` pour que le ghost matche pixel-perfect le futur mur réel.

### 4.3 — Animation tap mobile / mur posé

**CSS** :
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

**app.js — `renderWalls()` (modifié)** :
```js
function renderWalls(walls) {
  const layer = document.getElementById("walls-layer");
  const oldKeys = new Set([...layer.children].map(c => c.dataset.key));  // AVANT innerHTML=""
  layer.innerHTML = "";
  for (const w of walls) {
    const key = `${w.orientation}-${w.row}-${w.col}`;
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("class", "wall" + (oldKeys.has(key) ? "" : " appearing"));
    rect.dataset.key = key;
    // ... reste du positionnement inchangé
    layer.appendChild(rect);
  }
}
```

Bénéfice secondaire : les murs posés par l'IA en mode "IA vs IA" profitent aussi de l'animation.

### 4.4 — Resets et changements d'état

**Trois cas où `clearGhost()` est appelé** :
1. `mouseleave` sur une intersection (nominal).
2. Changement de `wall_placement_mode` (orientation modifiée ou sortie du mode) → appel depuis `renderWallMode()`, en comparant avec une valeur précédente trackée.
3. Coup validé OU coup rejeté → appel **explicite** dans le success et le catch de `handleIntersectionClick()`, avant `render()` / `showToast()`.

**`renderWallMode()` (modifié)** :
```js
let _prevWallMode = null;

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

## 5. Data flow

### 5.1 — Flow desktop nominal

```
Tap "Mur H"
  → POST /api/wall-mode {orientation:"h"} → state.wall_placement_mode = "h"
  → render() → renderWallMode() → body.wall-placement actif
  → CSS rend les 25 cibles visibles (pulse 1.8s)

Survol intersection (r,c)
  → mouseenter → .hovered (r=11, op=1, pulse pausé)
  → addGhost("h", r, c) → <rect ghost-wall> dans <g id="ghost">

Déplacement souris → autre intersection (r',c')
  → mouseleave (r,c) → clearGhost() + retire .hovered
  → mouseenter (r',c') → addGhost("h", r', c') + .hovered

Click sur intersection
  → handleIntersectionClick(r', c')
  → POST /api/move {type:"mur", orientation:"h", row:r', col:c'}
  → success : clearGhost() puis render(next)
  → renderWalls() diff oldKeys → nouveau mur reçoit .appearing
  → animation 200ms scale + opacity → mur intégré
```

### 5.2 — Flow mobile nominal

```
Tap "Mur H" → mode actif → 25 cibles visibles (pulse)
Tap intersection (r,c)
  → handleIntersectionClick déclenché (pas de hover, pas de ghost)
  → POST /api/move → render(next) → mur posé avec animation .appearing 200ms
```

### 5.3 — Edge cases

**E1. Coup invalide (chemin bloqué, collision, hors limites)**
- Backend → HTTP 4xx avec `{detail:{code, message}}`
- `handleIntersectionClick` catch → `clearGhost()` + `showToast("Coup impossible : …")`
- Mode placement reste actif, l'utilisateur peut retenter

**E2. Changement d'orientation pendant un hover en cours**
- Ghost H affiché, user tap "Mur V" → state.wall_placement_mode passe à "v"
- `renderWallMode()` détecte le changement → `clearGhost()`
- Prochain mouseenter régénère un ghost V

**E3. Quit pendant placement**
- Confirm → POST /api/quit → state.status = "waiting"
- wall_placement_mode passe à null → `renderWallMode()` → `clearGhost()`
- View bascule sur accueil

**E4. Reconnexion pendant placement**
- HTTP down 3+ ticks → overlay reconnexion affiché (z-index 150, au-dessus du board)
- Le ghost reste affiché derrière l'overlay. Pas grave : à la reconnexion, render() rejoue, l'état serveur fait foi, et le mouseleave naturel (quand l'user bouge la souris) nettoie.

**E5. IA pose un mur pendant que je hover**
- Impossible : en mode "IA vs IA", `#game-actions` est caché ([app.js:159](../../../webapp/static/app.js#L159)) donc impossible d'activer le mode placement. En "Humain vs IA", le tour IA n'est joué que quand `current_player === "j2"`, et le clic intersection vérifie `state.current_player !== "j1"` pour bloquer.

**E6. Mur ghost qui chevauche un mur existant**
- Le ghost s'affiche au survol même si la position est invalide (collision, chemin bloqué, etc.). C'est cohérent avec "le serveur valide" : à la confirmation par clic, l'erreur revient en toast (E1) et le ghost s'efface.
- Justification : valider localement nécessiterait de dupliquer la logique de pathfinding côté JS — coût hors scope démo.

**E7. Compatibilité Safari ancien**
- `r` animable via CSS sur `<circle>` : Safari ≥ 6.1 OK.
- `transform-box: fill-box` : Safari ≥ 11 OK.
- iOS Safari ≥ 11 OK. Mac Safari récent OK.
- Fallback dégradé pour Safari < 11 : pas d'animation de scale (acceptable).

## 6. Plan de validation manuelle

Validation entièrement manuelle (pas de tests JS auto dans le projet). Les 278 tests backend restent verts (aucun changement Python).

### 6.1 — Tests Safari Mac (priorité 1)

| # | Action | Résultat attendu |
|---|---|---|
| 1 | Démarrer Humain vs IA, taper "Mur H" | Cases s'assombrissent (op 0.6), **25 cibles orange r=9 avec halo blanc** visibles aux intersections, pulse doux 1.8s |
| 2 | Survoler une intersection sans cliquer | Cible grossit (r=11) + opacité plein + pulse pausé, **ghost wall semi-transparent en pointillé** apparaît à l'endroit du futur mur H |
| 3 | Bouger la souris vers une autre intersection | Ghost suit sans accumulation, cibles précédentes reviennent à r=9 |
| 4 | Sortir du board avec la souris | Ghost disparaît, toutes cibles à r=9 + pulse |
| 5 | Survoler puis cliquer | Ghost s'efface, mur réel apparaît avec animation 200ms scale+fade, compteur J1 : 6 → 5 |
| 6 | Re-taper "Mur H" alors qu'il est actif | Mode désactivé, cibles cachées, cases retrouvent opacité normale |
| 7 | Activer "Mur H", survoler, puis taper "Mur V" sans cliquer d'abord | Ghost H s'efface au tap "Mur V", mouseenter suivant régénère un ghost V |
| 8 | Tenter un mur invalide (chemin coupé / collision) | Toast d'erreur, **ghost effacé** (pas collé), mode placement reste actif |
| 9 | Reload Cmd+R en mode placement | Page recharge, mode placement remis automatiquement (state serveur), cibles visibles |

### 6.2 — Tests iPhone Safari (priorité 1)

| # | Action | Résultat attendu |
|---|---|---|
| 1 | Démarrer partie, taper "Mur H" | Cibles visibles (mêmes specs visuelles), pulse 1.8s OK |
| 2 | Taper directement une intersection | **Pas de ghost** (pas de hover), mur réel apparaît avec animation 200ms |
| 3 | Vérifier fiabilité du tap sur cible r=9 + halo | Aucun mistap perçu, zone tactile acceptable |
| 4 | Tenter mur invalide via tap | Toast erreur, mode reste actif |

### 6.3 — Tests non-régression (priorité 2)

| # | Action | Résultat attendu |
|---|---|---|
| 1 | Mode déplacement (cases cliquables) | Toujours fonctionnel, animation pion 400ms intacte |
| 2 | Mode IA vs IA | Boutons Mur H/V invisibles (mode placement non activable), murs IA s'affichent avec animation 200ms |
| 3 | Fin de partie | Modal s'affiche normalement, boutons Rejouer / Accueil |
| 4 | Toast anti-spam après mur invalide répété | Une seule fois par code d'erreur (fix existant intact) |

### 6.4 — Critère "go" pour merge sur `main`

- Tous les tests Mac + iPhone passent
- Aucune régression observée
- Performance fluide (pas de lag pulse / animation), pas besoin de désactiver une feature pour rendre l'app utilisable

## 7. Suivis potentiels (non-blockers)

Risques connus, à évaluer à la validation manuelle. Aucun n'est obligatoire pour shipper :

1. **Tap mobile < 44pt HIG**
   La cible r=9 + halo fait ≈21px de diamètre, sous le minimum Apple HIG pour les zones tactiles. Acceptable pour la démo (les murs sont des coups posément réfléchis, peu de mistaps), mais si l'utilisateur signale des taps ratés au test, follow-up = ajouter un `<circle r=20>` invisible (`fill:transparent`, `pointer-events:all`) **au-dessus** de la cible visuelle pour élargir le hitbox sans changer le visuel.

2. **Pulse synchrone sur 25 cibles**
   Toutes les cibles pulsent en phase. Risque d'effet "boum-boum" fatiguant à l'œil. Si signalé au test, follow-up = `animation-delay: calc((var(--r) + var(--c)) * 0.1s)` via CSS custom properties par cible (décalage diagonal léger).

3. **Validation locale du mur**
   Actuellement, le ghost s'affiche même sur positions invalides. Un user expérimenté pourrait être troublé. Follow-up possible : exposer côté serveur une liste de moves légaux dans `/api/state`, et faire que le ghost ne s'affiche qu'aux intersections autorisées. Coût modéré, bénéfice marginal pour la démo.

4. **Test plateau physique (Phase 5.3)**
   Indépendant de cette spec. Le bridge UART (`UartBridge.forward_move()`) n'est pas concerné par les changements UX murs.

## 8. Hors scope (rappel)

Voir Section 2. En particulier : pas d'undo, pas de navigation clavier, pas de support screen reader poussé, pas de tests JS auto ajoutés.
