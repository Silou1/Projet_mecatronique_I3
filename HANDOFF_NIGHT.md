# HANDOFF — nuit du 2026-05-18 → 2026-05-19

Web app de démo Quoridor exécutée pendant la nuit. Backend complet et testé (278 tests verts), frontend codé et serveur opérationnel. **Phase 5 (tests manuels Safari Mac + iPhone) reste à faire avec toi**, c'est ce que tu fais en premier au réveil.

## Branche

`feat/webapp-demo` — **non mergée sur `main`**. 14 commits propres pendant la nuit.

```bash
git log --oneline main..HEAD
```

## Ce qui est fait ✅

### Backend Python (Phases 0, 1, 2, 3)

- **`webapp/__init__.py`** (vide)
- **`webapp/schemas.py`** — modèles Pydantic (NewGamePayload, MovePayload, etc.)
- **`webapp/service.py`** — `QuoridorService` singleton thread-safe avec :
  - `new_game()`, `apply_user_move()`, `set_wall_mode()`, `pause()`, `resume()`, `set_speed()`, `quit_to_home()`
  - `tick_once()` + `start_tick_thread()` (thread daemon qui fait jouer l'IA avec délais artificiels)
  - `to_dict()` pour sérialiser l'état
  - Lock libéré pendant `find_best_move()` (HTTP ne bloque pas pendant la réflexion IA)
  - Guard anti-race quit_to_home/tick_once
  - Notification `PLATEAU_LOST` quand le bridge UART se désactive
- **`webapp/uart_bridge.py`** — wrapper autour de `UartClient` avec fallback gracieux
- **`webapp/server.py`** — FastAPI + 9 routes :
  - `GET /` (HTML), `GET /api/state`, `POST /api/new-game`, `POST /api/move`, `POST /api/pause`, `POST /api/resume`, `POST /api/speed`, `POST /api/wall-mode`, `POST /api/quit`
  - Erreurs en JSON uniforme `{detail: {code, message}}`

### Frontend (Phase 4)

- **`webapp/static/index.html`** — page unique 2 vues (#view-home, #view-game) + modal fin + toast + overlay reconnexion
- **`webapp/static/style.css`** — palette C2 affinée (beige/bois subtil + rigueur iOS), mobile-first
- **`webapp/static/app.js`** — polling 500ms, render SVG, gestion clics cases/intersections, modes mur H/V, animations, sync chip vitesse, gestion erreurs (avec fix anti-spam toast)

### Tests

```bash
pytest -m "not devkit" -q
# 278 passed (baseline 236 + 42 nouveaux webapp)
```

Détail webapp :
- `tests/webapp/test_schemas.py` — 10 tests
- `tests/webapp/test_service.py` — 23 tests
- `tests/webapp/test_uart_bridge.py` — 8 tests (mocks, pas de hardware)
- `tests/webapp/test_api.py` — 11 tests (TestClient FastAPI)

### Smoke test E2E réussi pendant la nuit

J'ai lancé `python -m webapp.server`, fait une partie humain vs IA via curl :
- Nouvelle partie → status=playing, current=j1 ✅
- Coup humain (4,3) → j1.pos=[4,3], turn=1 ✅
- Attente 3s → l'IA a joué (turn=2, current=j1) ✅
- POST /api/quit → HTTP 200 ✅

Le backend tourne et accepte tous les coups via HTTP. **L'IA répond. Les délais sont respectés.**

## Ce qui reste à faire au réveil 🛠️

### Phase 5 — Tests manuels (impossible sans toi)

Procédure complète dans le plan ([`docs/superpowers/plans/2026-05-18-webapp-demo-quoridor.md`](docs/superpowers/plans/2026-05-18-webapp-demo-quoridor.md) sections Task 5.1, 5.2, 5.3).

**Test rapide — golden path :**

```bash
cd /Users/silouanechaumais/Documents/01_ICAM/2025-2026_Année_3/Projet_mécatronique/programmation
lsof -ti:8000 | xargs -r kill -9   # libère le port au cas où
python -m webapp.server
```

Puis Safari Mac → `http://localhost:8000`. Vérifie :

1. **Vue accueil** s'affiche (titre Quoridor + chips mode/difficulté/toggle plateau grisé + bouton orange "Commencer la partie →").
2. **Mode "Humain vs IA", difficulté "Facile"**, tap "Commencer" → bascule sur vue jeu, plateau dessiné, pion bleu en bas (J1), pion rouge en haut (J2).
3. **Tape la case juste au-dessus du pion bleu** → il bouge avec animation 400ms.
4. **Attends 1-2s** → l'IA réfléchit puis le pion rouge bouge (ou un mur apparaît).
5. **Boutons "Mur H" / "Mur V"** : tap → le bouton devient orange + petites cibles oranges sur les intersections du plateau. Tap une intersection → mur posé, compteur J1 passe de 6 à 5.
6. **Mode "IA vs IA"** depuis l'accueil → 2 IA jouent automatiquement avec délais (~1.5s par coup en vitesse Normal). Slider vitesse en bas + bouton Pause.
7. **Modal fin de partie** quand quelqu'un gagne → boutons "Rejouer" / "Retour accueil".
8. **Reload page** (Cmd+R) pendant une partie → la partie reprend là où elle était (état côté serveur).

**Test iPhone** (cf. Task 5.2 du plan) : `ipconfig getifaddr en0` pour récupérer l'IP du Mac, puis Safari iPhone sur `http://<ip-mac>:8000`. Test : tap responsivité, viewport bien dimensionné, plateau lisible.

### Points de vigilance à valider au test manuel

1. **Animation pion** : 400ms ease-out sur cx/cy du `<circle>` SVG. Doit être fluide. Si saccade, on ajustera.
2. **Toast d'erreur** : un fix a été appliqué pour éviter qu'il se réaffiche en boucle (avant : il se réaffichait à chaque poll de state). Maintenant : 1 toast par code d'erreur unique.
3. **Mode placement mur** : les intersections cibles sont des cercles à l'intersection des 4 cases. Selon l'orientation choisie (H ou V), le mur s'étend correctement. À tester visuellement.
4. **Test plateau physique** : Task 5.3 du plan. Nécessite que tu branches le DevKit Freenove. Pas urgent — fallback gracieux déjà testé en mocks (8 tests UartBridge verts).

### Phase 6 — Déploiement RPi

`webapp/README.md` documente déjà la procédure complète (transfert code, installation deps, lancement, config réseau, plateau physique optionnel). On la fera ensemble quand tu seras prêt.

## Compromis assumés pendant la nuit

1. **Pas de spec/quality review formel sur Phases 2/4/6** vu qu'une déconnexion a coûté ~5 minutes en début de Phase 2. J'ai relu moi-même les diffs et ajouté un fix toast (cf. commit `2d70207`). Le code suit le plan à l'identique.
2. **`UartBridge.forward_move()` envoie `send_cmd("PAWN", "r c")` et `send_cmd("WALL", "h r c")`** — je n'ai pas pu vérifier que c'est exactement le format attendu côté firmware ESP32 (Plan 2). Les tests le valident via mocks, mais le premier test avec le DevKit réel risque de demander un ajustement de format. À faire ensemble lors du test plateau Phase 5.3.
3. **`tests/webapp/`** s'ajoute aux 236 tests existants — pas de modification du moteur, pas de risque de régression sur la couche métier Quoridor.

## Pour reprendre

Coller dans la nouvelle session :

```
Reprends la web app Quoridor de la nuit dernière.
Lis HANDOFF_NIGHT.md à la racine du repo. On enchaîne avec la Phase 5
(tests manuels Safari Mac + iPhone) selon les instructions du HANDOFF.
```

Tu peux aussi voir l'avancée commit par commit :

```bash
git log --oneline main..feat/webapp-demo
```

Bonne journée ! Au boulot 🚀
