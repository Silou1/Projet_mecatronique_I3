# Web app de démo Quoridor

Web app servie par le RPi (ou par le Mac en dev) pour démontrer le moteur
Quoridor et l'IA depuis un navigateur (iPhone Safari prioritaire).

- Spec : [`../docs/superpowers/specs/2026-05-18-webapp-demo-quoridor-design.md`](../docs/superpowers/specs/2026-05-18-webapp-demo-quoridor-design.md)
- Plan : [`../docs/superpowers/plans/2026-05-18-webapp-demo-quoridor.md`](../docs/superpowers/plans/2026-05-18-webapp-demo-quoridor.md)

## Lancement local (Mac)

```bash
uv pip install fastapi "uvicorn[standard]" httpx
python -m webapp.server
# → http://localhost:8000
```

Pour tester depuis l'iPhone (même Wi-Fi que le Mac) :

```bash
ipconfig getifaddr en0   # récupérer l'IP du Mac (essayer en1, en2 si vide)
# Puis Safari iPhone : http://<ip-mac>:8000
```

## Tests

```bash
pytest tests/webapp/ -v
# Pas de hardware requis pour ces tests.
```

## Déploiement RPi 3

### 1. Transfert du code

Trois options (à choisir avec Silouane le jour J) :

a. **SSH + git pull** : RPi sur le réseau, `ssh pi@<rpi>` puis `git pull` dans
   le repo cloné. Demande SSH + git config OK sur le RPi.

b. **scp depuis le Mac** :
   ```bash
   scp -r webapp/ pi@<rpi-ip>:/home/pi/quoridor/
   ```

c. **Clé USB + ssh / clavier-écran** : copie manuelle.

### 2. Dépendances Python sur le RPi

```bash
pip3 install fastapi "uvicorn[standard]" pyserial httpx
```

### 3. Lancement

```bash
cd /home/pi/quoridor
python3 -m webapp.server
# Serveur écoute sur 0.0.0.0:8000
```

### 4. Réseau pour la démo

**Recommandé : partage de connexion iPhone.**

1. iPhone : Réglages → Partage de connexion → activer.
2. RPi : se connecter au Wi-Fi de l'iPhone (configuré une fois dans
   `/etc/wpa_supplicant/wpa_supplicant.conf` ou via `raspi-config`).
3. iPhone : Réglages → Partage de connexion → "Personnes connectées" affiche
   le RPi avec son IP locale (généralement `172.20.10.x`).
4. Safari iPhone : `http://172.20.10.X:8000`.

### 5. Plateau physique (optionnel)

Si la PCB ou le DevKit Freenove est branché au RPi via USB :

```bash
ls /dev/ttyUSB* /dev/ttyAMA*  # vérifier qu'un port est détecté
```

Le serveur le détecte automatiquement au démarrage. Le toggle "Plateau
physique" devient activable sur l'écran d'accueil.

## Architecture

- **`webapp/server.py`** — point d'entrée FastAPI + uvicorn. 8 routes API + `GET /` sert le HTML.
- **`webapp/service.py`** — `QuoridorService` (singleton thread-safe). Détient l'état partie, instancie l'IA, gère le thread daemon de tick.
- **`webapp/uart_bridge.py`** — wrapper optionnel autour de `UartClient`. Détection auto au boot, fallback gracieux si KO.
- **`webapp/schemas.py`** — modèles Pydantic pour payloads et réponses.
- **`webapp/static/`** — frontend (HTML + CSS + JS vanilla + SVG inline).

## Stack technique

- Backend : Python 3.12, FastAPI 0.110+, uvicorn (standard).
- Transport : HTTP polling 500 ms (pas de WebSocket — choisi pour la fiabilité).
- Frontend : HTML5, CSS3, JavaScript vanilla (zéro framework, zéro build).
- Plateau : SVG inline, animations CSS transitions sur cx/cy.

## Réutilisation du moteur existant

Aucune modification de `quoridor_engine/` ni du firmware. La web app appelle :

- `quoridor_engine.core.create_new_game()` pour l'état initial
- `move_pawn(state, player, target)`, `place_wall(state, player, wall)` pour les coups
- `AI(player, difficulty)` + `find_best_move(state)` pour l'IA
- `UartClient.send_cmd(type, args)` pour le miroir plateau (mode optionnel)
