# Démarrage — installation, lancement et dépannage

Comment installer le projet, lancer la webapp, connecter l'ESP32 et résoudre les problèmes courants.

---

## Prérequis

- **Python 3.10+** (type hints modernes incompatibles avec 3.9)
- **Homebrew** (Mac) — pour les outils système (`brew install python@3.12`, `brew install pio`, etc.)
- **Câble USB-C** — uniquement si le plateau physique (ESP32) doit être connecté
- *Optionnel* : PlatformIO CLI (`brew install platformio`) pour flasher ou monitorer l'ESP32

---

## Installation

```bash
git clone https://github.com/Silou1/Projet_mecatronique_I3.git
cd Projet_mecatronique_I3
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Lancer la webapp en mode autonome (sans ESP32)

Mode local : le jeu tourne entièrement sur le Mac, sans plateau physique. Idéal pour développer ou tester l'IA.

```bash
source .venv/bin/activate
python -m webapp.server
```

Ouvrir `http://localhost:8000` dans un navigateur. Deux modes disponibles : humain vs humain, humain vs IA.

La webapp détecte automatiquement l'absence d'ESP32 et démarre en mode autonome (fallback gracieux).

---

## Connecter l'ESP32 en USB-série

Brancher le câble USB-C entre le Mac et l'ESP32. Le port apparaît comme :

- `/dev/tty.usbserial-*` (Mac Intel)
- `/dev/tty.usbmodem*` (Apple Silicon, parfois)

La webapp détecte automatiquement le port via `webapp/uart_bridge.py`. Si plusieurs ports série sont
visibles, forcer la sélection via variable d'environnement :

```bash
QUORIDOR_SERIAL_PORT=/dev/tty.usbserial-XXX python -m webapp.server
```

Pour vérifier que l'ESP32 répond correctement avant de lancer la webapp :

```bash
# Avec PlatformIO :
pio device monitor -b 115200
# Taper PING, attendre PONG
```

---

## Connecter l'ESP32 en Wi-Fi (prévu, non implémenté à ce jour)

Sera implémenté en phase 5. Topologie cible : l'ESP32 démarre en mode AP (SSID `Quoridor-ESP32`).
Le Mac rejoint ce réseau Wi-Fi. La webapp utilisera l'env var `QUORIDOR_TRANSPORT=wifi`
(placeholder, non actif aujourd'hui).

---

## Mode dev (sessions de codage actuelles)

Pour garder Internet sur le Mac pendant le développement avec l'ESP32 branché en USB-série :

1. Brancher l'iPhone en USB-C au Mac.
2. Activer "Partage de connexion" sur l'iPhone.
3. Le Mac reconnaît une nouvelle interface réseau `iPhone USB` — utilisée pour Internet.
4. Quand le Wi-Fi de l'ESP32 sera implémenté (phase 5), le Wi-Fi du Mac restera libre pour s'y connecter.

---

## Mode démo (cible vendredi)

1. Débrancher le câble USB-C entre l'iPhone et le Mac.
2. Mode USB-série actuel : l'ESP32 reste branché en USB-C au Mac ; la webapp s'affiche sur l'écran du Mac.
3. Mode Wi-Fi (phase 5, non implémenté) : le téléphone rejoint le Wi-Fi de l'ESP32, puis ouvre
   `http://<ip-du-mac-sur-le-réseau-ESP32>:8000` (typiquement `192.168.4.2:8000`). Pas d'Internet requis.
4. Fallback si Wi-Fi non disponible : USB-C Mac ↔ ESP32, webapp affichée localement.

---

## Lancer les tests

```bash
pytest                              # tous les tests
pytest -m "not devkit"              # exclut les tests qui requièrent un ESP32 branché
pytest tests/test_moves.py -v       # un fichier spécifique
pytest --cov=quoridor_engine        # couverture de code
```

---

## Dépannage

### Python introuvable

```bash
brew install python@3.12
```

### `ModuleNotFoundError`

Vérifier que le venv est activé et que les dépendances sont installées :

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Si le problème persiste après activation :

```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### `pyserial` introuvable

```bash
pip install pyserial
```

### Port ESP32 introuvable

```bash
ls /dev/tty.usbserial-* /dev/tty.usbmodem*
```

Si rien n'apparaît : essayer un autre câble USB-C (certains câbles sont charge-only),
tester un autre port USB du Mac.

### La webapp ne démarre pas (port 8000 occupé)

```bash
lsof -i :8000
# identifier le PID et le terminer si nécessaire
kill <PID>
```

### L'ESP32 ne répond pas à `PING`

- Vérifier que le sketch `bringup_l298n_complet.cpp` est bien flashé :
  ```bash
  pio run -t upload
  ```
- Vérifier le baudrate : **115200**, fin de ligne **LF (`\n`)**.
- Reset matériel : maintenir le bouton **BOOT**, appuyer sur **EN**, relâcher **BOOT**.

### Tests qui échouent

```bash
python3 --version                        # vérifier Python ≥ 3.10
pip install --upgrade -r requirements.txt
pytest -v                                # mode verbeux pour identifier le test fautif
```

---

**Pour aller plus loin** : [02_architecture.md](02_architecture.md) — vue d'ensemble software + hardware.
