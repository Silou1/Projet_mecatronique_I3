# Web app de démo Quoridor — design

**Date :** 2026-05-18
**Auteur :** Silouane (brainstorming assisté)
**Statut :** validé, prêt pour planification d'implémentation
**Portée :** spécification d'une web app servie par le Raspberry Pi qui permet de jouer au Quoridor depuis un navigateur (iPhone Safari prioritaire) en mode autonome (humain vs IA, IA vs IA) et, optionnellement, de piloter le plateau physique si la PCB est branchée. Couvre l'architecture backend (FastAPI + service singleton), le frontend (HTML/CSS/JS vanilla + SVG inline), le format des données échangées, l'UX des écrans, la gestion d'erreurs, les tests et le déploiement. **Hors scope :** comptes utilisateurs, multijoueur distant, persistance disque, déploiement web public, refactor du moteur de jeu.
**Source amont :** session de brainstorming du 2026-05-18 (cf. memory `project_pivot_webapp_demo.md`). État hardware quasi-nul (PCB pas soudée, LEDs cassées, moteurs non calibrés) → pivot du plateau physique vers une démo logicielle.
**Phase couverte :** nouvelle phase **P13 — Web app de démo** (hors plan global initial, ajoutée en sauvetage J-2 avant deadline du 2026-05-20).

---

## Table des matières

1. [Contexte](#1-contexte)
2. [Objectifs et non-objectifs](#2-objectifs-et-non-objectifs)
3. [Vue d'ensemble](#3-vue-densemble)
4. [Décisions clés](#4-décisions-clés)
5. [Structure des fichiers](#5-structure-des-fichiers)
6. [Backend Python](#6-backend-python)
7. [Frontend](#7-frontend)
8. [Format des données échangées](#8-format-des-données-échangées)
9. [UX et comportements](#9-ux-et-comportements)
10. [Mode plateau physique avec fallback](#10-mode-plateau-physique-avec-fallback)
11. [Gestion d'erreurs](#11-gestion-derreurs)
12. [Tests](#12-tests)
13. [Déploiement](#13-déploiement)
14. [Risques et limitations](#14-risques-et-limitations)
15. [Hors scope explicite](#15-hors-scope-explicite)

---

## 1. Contexte

À J-2 de la deadline (démo prévue le 2026-05-20), l'état hardware du plateau Quoridor est quasi-nul :

- PCB v2 réceptionnée mais **non soudée**, donc non testable.
- LEDs WS2812B : soudures cassées par d'autres membres de l'équipe, à reprendre.
- Moteurs Nema 17 : non calibrés au plateau.
- Matrice de boutons 6×6 sur la PCB : inopérante tant que la PCB n'est pas soudée.

Conséquence pratique : on **ne peut pas s'appuyer sur le plateau physique** pour démontrer l'IA au jury. Or la partie logicielle (moteur de jeu + IA Minimax + protocole UART Plan 2) est complète et testée (234 tests verts).

Le projet a donc pivoté vers une **web app servie par le RPi**, accessible depuis n'importe quel navigateur (iPhone Safari prioritaire). Le téléphone devient l'**interface homme-machine principale** de la démo : on configure et on joue depuis Safari, et si la PCB redevient fonctionnelle d'ici la démo, le plateau physique se synchronise en miroir via UART.

Cette spec décrit ce qu'on construit en 2 jours pour transformer le moteur Python existant en démo présentable.

---

## 2. Objectifs et non-objectifs

### Objectifs

1. **Démontrer l'IA fonctionne** au jury, sans dépendre du hardware.
2. **Jouer humain vs IA** depuis Safari sur iPhone, avec un plateau virtuel visuel.
3. **Spectacle IA vs IA** automatique, ralenti artificiellement pour être watchable.
4. **Mode plateau physique** activable depuis l'app si la PCB devient fonctionnelle (fallback gracieux si non).
5. **Fiabilité avant tout** : aucune fonctionnalité qui pourrait planter pendant la démo.
6. Réutiliser au maximum le code Python existant (`quoridor_engine`, `AI`, `GameSession`, `UartClient`).

### Non-objectifs

- Pas de multijoueur distant (un seul client à la fois suffit).
- Pas de comptes / login / autorisation.
- Pas de persistance disque (l'état part en RAM, perdu au reboot — OK pour démo).
- Pas de joli design "pro" type production (on vise du C2 affiné, propre mais pas pixel-perfect).
- Pas de tests E2E web (manuel suffit à 2 jours).
- Pas de mode hors-ligne / PWA installable.

---

## 3. Vue d'ensemble

```
┌──────────────┐    WiFi · HTTP    ┌─────────────────────┐   UART · 115200   ┌──────────────┐
│  iPhone      │ ◄──── poll ────►  │  Raspberry Pi 3     │ ◄── opt. ────►    │  ESP32 +     │
│  (Safari)    │  GET /api/state   │                     │   CMD / ACK       │  plateau     │
│              │  POST /api/move   │  FastAPI server     │   (si détecté)    │  (optionnel) │
│  page        │  ...              │  QuoridorService    │                   │              │
│  HTML/JS/SVG │                   │  UartBridge (opt.)  │                   │  firmware    │
└──────────────┘                   └─────────────────────┘                   │  Plan 2      │
                                                                              └──────────────┘
                                            ▲
                                            │
                                       moteur de jeu
                                       Python existant
                                       (réutilisé tel quel)
```

Trois acteurs, deux transports :

- **HTTP polling** (toujours actif) : le client Safari poll `GET /api/state` toutes les 500 ms et envoie ses actions via `POST /api/...`.
- **UART** (conditionnel) : si le port série de l'ESP32 est détecté au boot, le `UartBridge` est instancié et chaque coup est mirrored vers le firmware. Sinon, le toggle "Plateau physique" reste désactivé dans l'écran d'accueil.

---

## 4. Décisions clés

| # | Décision | Pourquoi |
|---|---|---|
| 1 | Web app servie par RPi, pas d'app iOS native. | Simulateur iOS ne fait pas Bluetooth, GATT server custom = non trivial, Web Bluetooth absent de Safari iOS. 2 jours c'est trop court pour iOS natif. |
| 2 | FastAPI (pas Flask). | Async natif, support routes + static files + threadpool intégré pour les long-running calls IA, dépendance unique. Tout aussi mature que Flask sur 6 ans de prod. |
| 3 | Polling HTTP (pas WebSocket). | Fiabilité avant fluidité : iPhone qui se verrouille, Wi-Fi qui sautote, RPi 3 vieux. Polling est stateless, chaque requête est indépendante. Latence ~250 ms en moyenne, invisible vu les délais artificiels d'IA. |
| 4 | HTML/CSS/JS vanilla + Alpine.js optionnel. | Pas de build, pas de npm, pas de bundler. Alpine.js (10 KB, CDN ou local) ajouté seulement si la réactivité fine est nécessaire. |
| 5 | SVG inline pour le plateau (pas Canvas). | Permet d'attacher des `onclick` directement sur les cases et intersections. Rendu net responsive iPhone/desktop. Animations via CSS transition sur `cx`/`cy`. |
| 6 | État de la partie côté serveur (singleton Python). | Source de vérité unique. Reload Safari = restoration immédiate via `GET /api/state`. Robuste aux fermetures d'onglet, verrouillages, plantages client. |
| 7 | Mode plateau physique avec fallback gracieux automatique. | Détection UART au boot du serveur. Si KO → toggle grisé dans l'UI. Si OK → toggle activable, échec d'un coup en cours de partie = log + désactivation du mirroring pour la suite, démo continue. |
| 8 | Humain = J1 toujours, IA = J2 toujours (mode H vs IA). | Pas de choix d'attribution dans l'écran d'accueil. YAGNI à 2 jours. J1 commence (cf. `core.py`). |
| 9 | Style visuel C2 affiné. | Validé en brainstorming : palette beige/bois subtile + rigueur iOS (typo système, ombres douces, gradients fins). Pas de bitmap, tout en SVG/CSS. |
| 10 | Configuration réseau démo = partage de connexion iPhone. | Plus simple que mode AP sur RPi (qui demande hostapd + dnsmasq). iPhone partage sa 4G, RPi rejoint ce hotspot, iPhone voit l'IP du RPi et la tape dans Safari. |

---

## 5. Structure des fichiers

Nouveau module à la racine du repo. Pas de modification des modules existants (`quoridor_engine`, `firmware`, etc.).

```
webapp/
├── __init__.py
├── server.py              # FastAPI app + uvicorn entrypoint
├── service.py             # QuoridorService (singleton, état + IA + thread tick)
├── uart_bridge.py         # UartBridge optionnel (wrapper GameSession + UartClient)
├── schemas.py             # Pydantic models pour les payloads API
└── static/
    ├── index.html         # Page unique avec 2 vues (#view-home, #view-game)
    ├── style.css          # Styles C2 affiné, mobile-first
    ├── app.js             # Logique : polling, rendu SVG, actions, animations
    └── alpine.min.js      # (optionnel, si réactivité fine nécessaire — sinon supprimé)
```

Dépendances ajoutées dans `requirements.txt` :

```
fastapi>=0.110
uvicorn[standard]>=0.27
pyserial>=3.5         # déjà présent en optional dep [devkit], promu en requis si UART utilisé
```

---

## 6. Backend Python

### 6.1 `webapp/server.py` — point d'entrée FastAPI

Définit l'app FastAPI, monte les fichiers statiques, déclare les routes API, instancie le `QuoridorService` au démarrage, lance le thread `tick`, lance `uvicorn` sur le port 8000.

**Routes** :

| Méthode | Chemin | Description |
|---|---|---|
| GET | `/` | Sert `static/index.html` (avec headers no-cache) |
| GET | `/static/*` | Sert les autres fichiers statiques |
| GET | `/api/state` | Retourne l'état courant complet (cf. §8.1) |
| POST | `/api/new-game` | Démarre une nouvelle partie avec les paramètres fournis |
| POST | `/api/move` | Applique un coup utilisateur (déplacement ou mur) |
| POST | `/api/pause` | Met en pause (IA vs IA uniquement) |
| POST | `/api/resume` | Reprend |
| POST | `/api/speed` | Change la vitesse IA vs IA (lent/normal/rapide) |
| POST | `/api/wall-mode` | Active/désactive le mode placement de mur (h/v/null) |
| POST | `/api/quit` | Retour à l'accueil (clear l'état partie, garde les réglages) |

**Pas de routes de debug exposées en prod** (pas de `/api/reset` qui pourrait être appelée par erreur).

### 6.2 `webapp/service.py` — QuoridorService

Classe unique, **singleton** instanciée au démarrage du serveur. Détient :

- `state: GameState | None` — l'état de jeu courant (None si pas de partie)
- `ai_j1: AI | None`, `ai_j2: AI | None` — instances IA selon mode
- `mode: Literal["human_vs_ai", "ai_vs_ai"]`
- `difficulty: Literal["facile", "normal", "difficile"]`
- `speed: Literal["lent", "normal", "rapide"]` — délai IA vs IA
- `status: Literal["waiting", "playing", "paused", "finished"]`
- `winner: str | None`
- `turn_count: int`
- `plateau_mode: bool` — si l'utilisateur a activé le miroir plateau
- `last_error: dict | None` — pour transmettre une erreur récupérable au front
- `_lock: threading.Lock` — protège l'état contre les concurrences thread/API
- `_last_ai_move_at: float` — timestamp du dernier coup IA, pour le délai

**Méthodes principales** :

```python
def new_game(mode, difficulty, plateau_mode) -> dict: ...
def apply_user_move(move: Move) -> dict: ...
def pause(), resume(), set_speed(speed), quit_to_home(): ...
def to_dict() -> dict: ...  # sérialisation pour /api/state
```

**Thread `tick`** : daemon démarré au boot du serveur. Boucle à 10 Hz. À chaque tick :

```python
with self._lock:
    if self.status == "playing" and self._is_ai_turn():
        elapsed = time.monotonic() - self._last_ai_move_at
        if elapsed >= self._delay_for_speed():
            move = self._current_ai().find_best_move(self.state, verbose=False)
            self.state = self._apply_move(move)
            self._last_ai_move_at = time.monotonic()
            self._check_game_over()
            if self.plateau_mode and uart_bridge.available:
                uart_bridge.forward_move(move)  # best-effort, exception → désactive mirroring
```

**Pourquoi un thread, pas une coroutine async** : `find_best_move()` est CPU-bound, bloquerait l'event loop. Un thread daemon contourne ça proprement sans réécrire l'IA en async.

### 6.3 `webapp/uart_bridge.py` — couche optionnelle

Wrapper léger autour de `GameSession` + `UartClient`. Au boot du serveur :

```python
def init() -> UartBridge | None:
    port = find_devkit_port()  # glob /dev/cu.usbserial-* (Mac) ou /dev/ttyUSB* (Linux)
    if not port:
        log.info("UART bridge: aucun port détecté, mode autonome")
        return None
    try:
        client = UartClient(port)
        client.connect()  # handshake Plan 2
        return UartBridge(client)
    except UartError as e:
        log.warning(f"UART bridge: échec connexion ({e}), mode autonome")
        return None
```

`UartBridge.forward_move(move)` :

```python
def forward_move(self, move: Move) -> None:
    if not self.available:
        return
    try:
        # convertit le move Python en trame UART CMD selon Plan 2
        # exemple : ('mur', ('h', 2, 3, 2)) → CMD_WALL frame
        self._client.send_command(move)
        self._client.wait_for_ack(timeout=2.0)
    except UartError as e:
        log.warning(f"UART bridge: échec forward ({e}), désactivation mirroring")
        self.available = False
```

**Pas de blocage en cas d'erreur** : si l'UART meurt en plein match, on log, on désactive le miroir, mais l'état Python du jeu continue. Le client est informé via le flag `plateau_connected: false` dans `/api/state`.

---

## 7. Frontend

### 7.1 `static/index.html`

Une seule page. Deux vues affichées en alternance par toggle de classe `.hidden` :

- `#view-home` : écran d'accueil (titre, mode, difficulté, toggle plateau, slider vitesse conditionnel, bouton "Commencer")
- `#view-game` : écran de jeu (barre supérieure, plateau SVG, barre info, boutons d'action, modals)

Pas de routing serveur. Pas de fragment URL. Bascule pilotée par `app.js` selon `status` reçu de `/api/state`.

### 7.2 `static/style.css`

Variables CSS pour la palette C2 affinée :

```css
:root {
  --bg: #faf6ee;
  --board-bg: #ead9b8;
  --cell-light: #fbf3df;
  --cell-dark: #f5ead0;
  --grid: #c9a96e;
  --wood-dark: #5a3818;
  --primary: #b86b3a;
  --text: #2c1810;
  --text-soft: #6b5a44;
  --pawn-blue-1: #5b9fd9;
  --pawn-blue-2: #1f5f8f;
  --pawn-red-1: #e57a6c;
  --pawn-red-2: #9c2f23;
}
```

Pas de framework CSS. Styles écrits à la main, mobile-first (`min-width` queries pour desktop).

### 7.3 `static/app.js`

Pas de framework. Une seule fonction `poll()` lancée toutes les 500 ms :

```javascript
async function poll() {
  try {
    const state = await fetch('/api/state').then(r => r.json());
    render(state);
    consecutiveErrors = 0;
  } catch (e) {
    consecutiveErrors++;
    if (consecutiveErrors >= 3) showReconnectingOverlay();
  } finally {
    setTimeout(poll, 500);
  }
}
```

`render(state)` met à jour le DOM : positions des pions (CSS transition sur cx/cy), liste des murs, info de tour, indicateur "IA réfléchit", visibilité des vues, etc.

Gestionnaires onclick attachés une fois au démarrage sur les cases SVG et les boutons.

### 7.4 Plateau SVG

Structure :

```svg
<svg viewBox="0 0 360 360">
  <defs>... (gradients pour cases, pions, murs)</defs>
  <rect class="board-bg" ... />
  <g class="cells">
    <!-- 36 cases avec data-row, data-col, onclick="handleCellClick(this)" -->
  </g>
  <g class="walls">
    <!-- Murs posés, rendus dynamiquement à chaque render -->
  </g>
  <g class="intersections">
    <!-- 25 intersections invisibles, visible seulement en mode placement mur -->
  </g>
  <circle class="pawn pawn-j1" cx="..." cy="..." r="22" />
  <circle class="pawn pawn-j2" cx="..." cy="..." r="22" />
</svg>
```

Animation : `circle.pawn { transition: cx 0.4s ease-out, cy 0.4s ease-out; }`.

---

## 8. Format des données échangées

### 8.1 `GET /api/state` — schéma de réponse

```json
{
  "mode": "human_vs_ai",
  "difficulty": "normal",
  "speed": "normal",
  "status": "playing",
  "turn_count": 7,
  "current_player": "j1",
  "ai_thinking": false,
  "players": {
    "j1": {
      "position": [4, 3],
      "walls_remaining": 5,
      "is_ai": false,
      "is_winner": false
    },
    "j2": {
      "position": [1, 2],
      "walls_remaining": 4,
      "is_ai": true,
      "is_winner": false
    }
  },
  "walls": [
    {"orientation": "h", "row": 2, "col": 2}
  ],
  "winner": null,
  "plateau": {
    "available": true,
    "mode_active": true,
    "connected": true
  },
  "last_error": null,
  "wall_placement_mode": null
}
```

- `position: [row, col]` — coordonnées plateau (0,0 = haut-gauche)
- `walls: list[{orientation: "h"|"v", row, col}]` — longueur 2 implicite
- `plateau.available` : un port UART a été détecté au boot
- `plateau.mode_active` : l'utilisateur a activé le toggle
- `plateau.connected` : la connexion UART est encore vivante (peut passer à `false` en cours de partie)
- `wall_placement_mode: "h" | "v" | null` — l'utilisateur est en mode placement de mur (info purement UI, mais centralisée côté serveur pour cohérence multi-onglets éventuels)

### 8.2 `POST /api/new-game` — payload

```json
{
  "mode": "human_vs_ai" | "ai_vs_ai",
  "difficulty": "facile" | "normal" | "difficile",
  "plateau_mode": true | false
}
```

Réponse : 200 + nouveau state, ou 400 + raison (ex : `plateau_mode=true` demandé mais `plateau.available=false`).

### 8.3 `POST /api/move` — payload

Déplacement de pion :
```json
{"type": "deplacement", "target": [3, 2]}
```

Placement de mur :
```json
{"type": "mur", "orientation": "h", "row": 2, "col": 3}
```

Réponse : 200 + nouveau state, ou 400 + `{"code": "INVALID_MOVE", "message": "..."}`.

### 8.4 Autres POST

- `POST /api/pause` — `{}` → 200 + state (status devient `"paused"`)
- `POST /api/resume` — `{}` → 200 + state
- `POST /api/speed` — `{"speed": "lent" | "normal" | "rapide"}` → 200 + state
- `POST /api/quit` — `{}` → 200 + state vide (status `"waiting"`)
- `POST /api/wall-mode` — `{"orientation": "h" | "v" | null}` → 200 + state (active/désactive le mode placement)

---

## 9. UX et comportements

### 9.1 Écran d'accueil

Sections empilées verticalement, mobile-first :

1. **Titre** "Quoridor" + sous-titre "Choisis ton mode".
2. **Mode** (chips toggleables) : "Humain vs IA" / "IA vs IA".
3. **Difficulté** (chips toggleables) : "Facile" / "Normal" / "Difficile".
4. **Vitesse IA vs IA** (chips, visible seulement si mode = IA vs IA) : "Lent" / "Normal" / "Rapide".
5. **Plateau physique** (toggle iOS-style). Grisé si `plateau.available=false`, avec libellé "Plateau non détecté".
6. **Bouton primary** "Commencer la partie →".

Tap sur "Commencer" → `POST /api/new-game` → bascule sur `#view-game`.

### 9.2 Écran de jeu

Structure verticale :

1. **Barre supérieure** : flèche ← (retour accueil, demande confirmation si partie en cours), titre "Quoridor · Tour N", bouton ⋯ (menu compact : pause/resume si IA vs IA, reset).
2. **Barre d'état** : "J1 (toi) · 5 murs", indicateur tour central avec animation ("Ton tour" / "IA réfléchit…"), "J2 (IA) · 4 murs".
3. **Plateau SVG** centré, max 90 % largeur écran sur mobile, fixé sur desktop.
4. **Boutons d'action** (en mode humain) : "Mur H" / "Mur V" / (auto-déplacement par tap sur case).
5. **Slider vitesse** (en mode IA vs IA, en bas) : 3 chips Lent/Normal/Rapide.
6. **Bouton Pause/Reprendre** (en mode IA vs IA, sous le plateau).

### 9.3 Placement de mur

Détail UX retenu :

1. Utilisateur tape "Mur H" → l'écran entre en **mode placement horizontal**. Le bouton devient highlight, les **intersections valides** sur le plateau deviennent visibles (petits points discrets ou rectangles fantômes là où un mur H pourrait être placé).
2. Tap sur une intersection → `POST /api/move {type: "mur", orientation: "h", row, col}`. Si OK, le mur apparaît, le mode sort automatiquement. Si KO (déjà occupé / bloque tout chemin), toast "Coup impossible" + le mode reste actif.
3. Re-tap "Mur H" pour sortir manuellement, ou tap "Mur V" pour basculer.

Cohérence multi-onglets : le mode est stocké côté serveur (`wall_placement_mode` dans le state), donc même comportement sur tous les clients qui regarderaient.

### 9.4 Déplacement de pion

- Tap direct sur une case adjacente valide → `POST /api/move {type: "deplacement", target: [r, c]}`.
- Les cases accessibles sont mises en surbrillance (léger halo) quand c'est le tour de l'utilisateur.
- Tap sur une case invalide → ignoré silencieusement côté UI (pas de toast), mais le serveur retournera 400 si le POST part quand même (sécurité). On filtre côté client pour éviter le bruit.

### 9.5 Fin de partie

Modal centré semi-transparent par-dessus le plateau :

```
🏆
J1 gagne en 23 tours !

[Rejouer]  [Retour accueil]
```

"Rejouer" → `POST /api/new-game` avec les mêmes paramètres.
"Retour accueil" → `POST /api/quit` → vue accueil.

### 9.6 IA vs IA : délai et vitesse

Tableau des délais :

| Vitesse | Délai mini entre coups |
|---|---|
| Lent | 2.5 s |
| Normal | 1.5 s |
| Rapide | 0.7 s |

Le délai est mesuré depuis le timestamp du dernier coup IA. Si `find_best_move()` met plus longtemps que le délai (cas en difficile), le coup est joué dès qu'il est calculé.

L'animation pion (0.4 s) tourne en parallèle, ne bloque pas le délai.

### 9.7 Réglages persistés entre parties

Mode, difficulté, vitesse, plateau_mode → conservés dans `QuoridorService` après une partie terminée. Le bouton "Rejouer" depuis la modale de fin réutilise ces réglages. Le `POST /api/quit` les conserve aussi (l'écran d'accueil rebondira sur les dernières valeurs).

---

## 10. Mode plateau physique avec fallback

### 10.1 Détection au boot

`webapp/server.py` au démarrage :

```python
uart_bridge = uart_bridge_module.init()  # tente find_devkit_port + handshake
# uart_bridge est None si pas détecté
quoridor_service = QuoridorService(uart_bridge=uart_bridge)
```

`uart_bridge.available` (propriété, pas un attribut figé) reflète l'état actuel :
- `True` si `init()` a réussi ET aucune erreur depuis
- `False` si `init()` a échoué OU une erreur s'est produite en cours

### 10.2 Activation par l'utilisateur

L'écran d'accueil reflète `plateau.available` dans le state :
- `available=false` → toggle grisé, libellé "Plateau non détecté"
- `available=true` → toggle activable

Tap sur "Commencer la partie" avec toggle ON → `plateau_mode=true` dans le payload `new-game`. Le service note ce flag et appellera `uart_bridge.forward_move()` après chaque coup.

### 10.3 Échec en cours de partie

Si `forward_move()` lève une `UartError` (timeout watchdog, port débranché, etc.) :

1. Log côté serveur.
2. `uart_bridge.available` passe à `false`.
3. `last_error` du service devient `{"code": "PLATEAU_LOST", "message": "Plateau déconnecté, partie en mode app."}`.
4. Client poll → reçoit le `last_error` + `plateau.connected=false`, affiche un toast et continue normalement.

**La partie Python continue normalement.** L'IA joue ses coups, l'utilisateur joue les siens, le plateau physique n'est juste plus tenu au courant.

### 10.4 Pas de tentative de reconnexion auto

Si le plateau meurt en plein match, on ne tente PAS de reconnect. Trop fragile, trop de cas tordus (le firmware peut être dans un état incohérent). L'utilisateur doit revenir à l'accueil et redémarrer.

---

## 11. Gestion d'erreurs

| Cas | Côté serveur | Côté client |
|---|---|---|
| Coup invalide envoyé | Retour 400 + `{code, message}` | Toast discret "Coup impossible", `wall_placement_mode` reste actif si applicable |
| Plateau déconnecté en jeu | Désactivation mirroring + `last_error` | Toast "Plateau déconnecté, partie en mode app" |
| Polling échoue 3 fois | (rien — c'est côté client) | Overlay "Reconnexion…" qui disparaît au premier poll réussi |
| `find_best_move()` lève exception | Log + retour à l'accueil avec `last_error="AI_CRASH"` | Modal "Erreur IA, partie interrompue. [Retour accueil]" |
| `POST /api/new-game` avec `plateau_mode=true` mais `plateau.available=false` | Retour 400 `{code: "PLATEAU_UNAVAILABLE"}` | Toggle se remet automatiquement à OFF, toast d'avertissement |
| Partie déjà en cours, nouveau `POST /api/new-game` | Accepte (écrase l'ancienne) | Pas de confirmation côté UI (l'utilisateur a explicitement tapé "Rejouer") |

Toutes les routes retournent un JSON, jamais un HTML d'erreur Flask/FastAPI par défaut (handler global).

---

## 12. Tests

### 12.1 Backend

Nouveau dossier `tests/webapp/` :

- `test_service.py` (~10-15 tests) : `QuoridorService.new_game()`, `apply_user_move()`, transitions de status, comportement du thread tick (testé via méthode `tick_once()` exposée pour les tests), choix du délai selon vitesse.
- `test_api.py` (~5-8 tests) : utilise `fastapi.testclient.TestClient`, vérifie les routes (status codes, schémas de réponse, gestion des payloads invalides).
- `test_uart_bridge.py` (~3-5 tests) : utilise des mocks (pas de hardware), vérifie `init()` retourne None si pas de port, `forward_move()` désactive `available` sur erreur.

Pas de test E2E (Selenium / Playwright). Vu les 2 jours, manuel suffit.

### 12.2 Frontend

Test manuel uniquement, dans cet ordre :

1. Safari Mac sur `localhost:8000` (golden path : nouvelle partie H vs IA Normal, jouer 3-4 coups, gagner ou abandonner).
2. Safari Mac : mode IA vs IA, vérifier que les délais sont visibles.
3. Safari iPhone (sur Wi-Fi partagé du Mac ou hotspot iPhone) sur l'IP du Mac/RPi : refaire les mêmes tests.
4. Test fallback plateau : activer toggle alors qu'aucun ESP32 branché (doit être grisé), brancher DevKit et redémarrer le serveur (doit être activable), débrancher en cours de partie (doit afficher toast et continuer).

Critères de succès :
- Aucun bug visible
- Animations fluides (60 fps sur iPhone récent, 30 fps acceptable sur RPi 3 si on sert depuis là)
- Pas de plantage sur 10 minutes d'utilisation continue

### 12.3 Pas de régression sur la suite existante

`pytest` global doit toujours afficher 234 tests verts (les nouveaux tests s'ajoutent, ne remplacent pas).

---

## 13. Déploiement

### 13.1 Sur le Mac (dev)

```bash
cd /Users/silouanechaumais/Documents/01_ICAM/2025-2026_Année_3/Projet_mécatronique/programmation
uv pip install fastapi "uvicorn[standard]"
python -m webapp.server
# → ouvre http://localhost:8000 dans Safari
```

Pour tester depuis l'iPhone sur le même Wi-Fi : récupérer l'IP du Mac (`ipconfig getifaddr en0`), taper `http://<ip-mac>:8000` dans Safari iPhone.

### 13.2 Sur le RPi 3 (démo)

**Procédure de transfert à formaliser ensemble** (cf. memory `project_pivot_webapp_demo.md`). Trois options à évaluer :

a. **Ethernet direct Mac ↔ RPi avec IP statique + SSH** : nécessite adaptateur Ethernet sur Mac USB-C, configuration IP statique des deux côtés. Robuste mais setup non maîtrisé actuellement.

b. **RPi et Mac sur le même Wi-Fi** : RPi tape une commande `git pull` ou `scp`. Suppose un réseau Wi-Fi commun.

c. **Clé USB + clavier+écran sur le RPi** : copie manuelle. Fastidieux mais zéro setup réseau.

Une fois le code copié sur le RPi :

```bash
cd /home/pi/quoridor-webapp
pip3 install fastapi "uvicorn[standard]" pyserial
python3 -m webapp.server
# Le serveur écoute sur 0.0.0.0:8000
```

**Configuration réseau démo** (validée) : partage de connexion iPhone activé. RPi se connecte automatiquement à ce hotspot (réseau pré-configuré dans `wpa_supplicant.conf`). iPhone voit l'IP du RPi dans Réglages → Partage de connexion. Tap cette IP suivi de `:8000` dans Safari.

### 13.3 Lancement automatique

Pas de service systemd à 2 jours. Le serveur est lancé à la main via SSH depuis le Mac. Si crash en démo, on peut relancer en 5 secondes.

---

## 14. Risques et limitations

### 14.1 Risques techniques

| Risque | Probabilité | Mitigation |
|---|---|---|
| RPi trop lent pour servir + IA en parallèle | Moyenne | Tester sur RPi tôt. Fallback : servir depuis Mac, RPi sert juste à montrer "ça tourne sur Linux embarqué". |
| `find_best_move()` en difficile (profondeur 5) prend >3 s sur RPi 3 | Moyenne | Limiter par défaut à "Normal" pour démo, garder "Difficile" comme option non recommandée. |
| Safari iOS reload de page perd le contexte | Faible | État côté serveur = restoration automatique. Testé. |
| Partage de connexion iPhone instable | Faible | Avoir un Wi-Fi de secours (ICAM ou hotspot Mac). |
| PCB soudée à la dernière minute mais firmware buggé | Élevée | Fallback gracieux fait son boulot : démo continue sans plateau si UART meurt. |

### 14.2 Limitations connues acceptées

- Pas de persistance disque : reboot RPi en plein milieu de démo = partie perdue.
- Un seul utilisateur effectif à la fois (techniquement, plusieurs onglets verraient la même partie mais le second pourrait poster un coup conflictuel — pas de protection).
- Pas d'auth : quiconque sur le réseau peut taper l'IP et jouer / forcer un reset.
- L'animation pion sur RPi 3 peut saccader si le CPU est occupé par l'IA — visuel uniquement, n'affecte pas la logique.

---

## 15. Hors scope explicite

- App iOS native (rejetée en brainstorming).
- WebSocket (rejeté pour la fiabilité).
- Bluetooth (incompatible Safari iOS).
- Comptes, login, sessions multi-utilisateurs.
- Persistance disque, historique des parties.
- Mode hors-ligne / PWA installable.
- Mode "spectateur" séparé du mode joueur.
- Tests E2E automatisés.
- Service systemd, déploiement permanent.
- Refactor de `quoridor_engine`, `firmware`, ou du protocole UART Plan 2.
- Adaptation du firmware aux changements récents boutons/LEDs (sujet séparé, traité quand on touchera au firmware).

---

## Suite

Une fois cette spec validée par l'utilisateur, on enchaîne avec le **skill writing-plans** pour produire le plan d'implémentation détaillé (découpe en tâches, ordre, critères de validation par étape). Le plan vivra dans `docs/superpowers/plans/2026-05-18-webapp-demo-quoridor.md`.
