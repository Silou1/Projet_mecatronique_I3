# Intégration logicielle RPi ↔ ESP32 (P9) — design

**Date :** 2026-05-03
**Auteur :** Silouane (brainstorming assisté)
**Statut :** validé, prêt pour planification d'implémentation
**Portée :** spécification de la couche d'orchestration qui fait dialoguer le moteur de jeu Python (Raspberry Pi) avec le firmware ESP32 via le protocole UART Plan 2. Couvre le mode CLI « plateau », le flux entrant (intentions joueur), le flux sortant (coups IA), la gestion robuste des déconnexions, les stubs firmware nécessaires, la stratégie de tests sans hardware. **Hors scope** : implémentation des drivers réels (LEDs, moteurs, servo — phase P11), simulateur de niveau 2 (FakeESP32 sur pty — chantier P9.5 séparé), tests d'intégration sur DevKit physique (P9.5 reportée au 2026-05-04).
**Source amont :** [`2026-05-01-protocole-uart-plan-2-design.md`](2026-05-01-protocole-uart-plan-2-design.md). Ce spec en hérite directement (format de trame, codes d'erreur, séquencement, idempotence). Toute divergence apparente entre les deux est une erreur à signaler.
**Phase couverte :** P9 du [plan global](../../00_plan_global.md) (sous-tâches P9.1 à P9.4 et P9.6, réalisables sans hardware ; P9.5 reste en attente du DevKit).

---

## Table des matières

1. [Contexte](#1-contexte)
2. [Décisions architecturales (synthèse)](#2-décisions-architecturales-synthèse)
3. [CLI et orchestration `main.py`](#3-cli-et-orchestration-mainpy)
4. [Flux entrant (intention joueur → ACK/NACK)](#4-flux-entrant-intention-joueur--acknack)
5. [Flux sortant (coup IA → CMD)](#5-flux-sortant-coup-ia--cmd)
6. [Robustesse aux déconnexions](#6-robustesse-aux-déconnexions)
7. [Modifications firmware ESP32](#7-modifications-firmware-esp32)
8. [Stratégie de tests](#8-stratégie-de-tests)
9. [Observabilité et debug](#9-observabilité-et-debug)
10. [Limitations connues et reports](#10-limitations-connues-et-reports)
11. [Hors scope (specs / phases ultérieurs)](#11-hors-scope-specs--phases-ultérieurs)

---

## 1. Contexte

À l'issue de P8, les deux extrémités du protocole UART Plan 2 sont en place :
- côté ESP32 : `UartLink::sendFrame`, `tryGetFrame`, dédup CMD, ré-émission ERR, gestion handshake/keepalive.
- côté Python : `quoridor_engine/uart_client.UartClient` avec `connect`, `send_cmd` (3 essais idempotents), `send_ack`, `send_nack`, `receive`, `handle_err_received`, thread de lecture en arrière-plan.

Mais **rien ne les fait dialoguer pendant une partie**. [`main.py`](../../main.py) joue actuellement en console pure : `prompt_for_move` (clavier) ↔ `QuoridorGame` ↔ `AI`, sans aucun lien UART. Le firmware Plan 2 reçoit déjà `CMD MOVE` (implémenté en P5) mais ignore `CMD WALL` et `CMD GAMEOVER` (logs `non-impl` dans `tickConnected`).

P9 fournit la **couche d'orchestration** qui :

1. Ajoute un mode « plateau physique » à [`main.py`](../../main.py), sélectionnable par CLI, qui remplace `prompt_for_move` par une lecture de `MOVE_REQ`/`WALL_REQ` venant de l'ESP32.
2. Implémente le flux entrant : à chaque intention reçue, valider via `QuoridorGame` et répondre `ACK`/`NACK` avec un code typé.
3. Implémente le flux sortant : quand l'IA joue, envoyer la `CMD` correspondante avec retry idempotent et attendre le `DONE`.
4. Fait survivre une partie aux pertes UART transitoires (3 s sans trafic, ESP32 entre en `ERROR_STATE`, `CMD_RESET` automatique, reprise au tour courant).
5. Ajoute les **stubs firmware** pour `CMD WALL` et `CMD GAMEOVER` qui répondent `DONE` sans action mécanique (les drivers réels arrivent en P11).

**Contrainte hardware :** le DevKit ESP32 n'est disponible qu'à partir du 2026-05-04. P9.1 à P9.4 et P9.6 sont pleinement réalisables sans hardware (compilation, tests Python avec mocks). **P9.5** (tests E2E sur DevKit) reste reporté à lundi 2026-05-04, et un **simulateur de niveau 2** (FakeESP32 via pty) sera construit ensuite (chantier séparé) pour permettre des tests E2E sans hardware en cas d'indisponibilité prolongée du DevKit.

---

## 2. Décisions architecturales (synthèse)

Sept décisions de fond, prises dans l'ordre lors du brainstorming. Chacune est justifiée et défendable en soutenance.

### 2.1 Plateau « silencieux » avec mode debug optionnel

**Décision :** en mode plateau, le terminal Python n'affiche **aucun rendu de jeu** (pas de plateau ASCII, pas de prompt clavier, pas de récap des coups). Le plateau physique est l'unique interface joueur. Un flag CLI `--debug` active un mode verbeux qui imprime au terminal toutes les trames envoyées/reçues, l'état de session, le tour courant, les coups acceptés/refusés — utile pour le développement, jamais activé en démo.

**Justification :**

- Le projet **vit** dans le plateau physique : LEDs et boutons sont la seule interface en démo. Imprimer le plateau au terminal créerait une double source de vérité confusante (un joueur regarde-t-il l'écran ou le plateau ?).
- Le mode console `--mode console` (par défaut) reste intact, c'est notre fallback pour développer le moteur sans hardware. Aucun coût d'ajout d'un nouveau mode.
- `--debug` couvre le besoin de visibilité pendant le développement et le diagnostic. Activable à la volée, désactivé par défaut.

**Alternative écartée — afficher le plateau en mode plateau :** crée la double source de vérité ; en démo le terminal n'est pas devant le joueur de toute façon.
**Alternative écartée — un seul flag `--no-display` sur un mode unifié :** moins lisible que deux modes nommés (`console`, `plateau`) ; un mode plateau « sans plateau physique » serait incohérent.

### 2.2 Codes d'erreur typés via `InvalidMoveError.code` (mandatory)

**Décision :** enrichir `quoridor_engine.core.InvalidMoveError` avec un attribut **obligatoire** `code: NackCode` où `NackCode` est un `Enum` listant exactement les codes acceptés par le protocole. Tous les sites de levée dans `core.py` (12 sites) et `ai.py` (1 site) reçoivent un code explicite. La couche d'orchestration mappe `InvalidMoveError.code` → trame `NACK <code>`.

**Justification :**

- Sans typage, on retombe sur un mapping ad hoc « parser le message d'erreur français » qui est fragile et viole le découplage moteur/protocole.
- Code obligatoire (pas d'argument par défaut) garantit qu'aucun site ne sera oublié et qu'aucun nouvel ajout ne pourra omettre l'information. Le linter `pytest` détecte immédiatement une régression au niveau de la signature.
- `NackCode` est un `Enum` (`auto()` ou valeurs string). Les valeurs sont alignées **exactement** sur le catalogue §4.4 du spec protocole (`ILLEGAL`, `OUT_OF_BOUNDS`, `WRONG_TURN`, `WALL_BLOCKED`, `NO_WALLS_LEFT`, `INVALID_FORMAT`).
- Mapping site → code documenté en §4.3 ci-dessous.

**Alternative écartée — argument optionnel `code=NackCode.ILLEGAL` par défaut :** la valeur par défaut masquerait des oublis. Un assert obligatoire est plus strict pour zéro coût rédactionnel.
**Alternative écartée — parser le message d'erreur :** anti-pattern (couplage par texte, fragile au refactor, dépendant de la langue).

### 2.3 Stubs firmware uniquement pour `CMD WALL` et `CMD GAMEOVER`

**Décision :** ajouter dans [`firmware/src/GameController.cpp`](../../firmware/src/GameController.cpp), dans `tickConnected`, **deux** stubs explicites qui acceptent les CMD et répondent `DONE` sans action mécanique :

```cpp
} else if (strcmp(f.type, "CMD") == 0 && strncmp(f.args, "WALL ", 5) == 0) {
  UartLink::logf("FSM", "CMD WALL stub: %s", f.args + 5);
  UartLink::respondCmdDone(f.seq);
} else if (strcmp(f.type, "CMD") == 0 && strncmp(f.args, "GAMEOVER ", 9) == 0) {
  UartLink::logf("FSM", "CMD GAMEOVER stub: %s", f.args + 9);
  UartLink::respondCmdDone(f.seq);
}
```

**Pas de stub pour `CMD HIGHLIGHT` ni `CMD SET_TURN`** : ces deux commandes sont **purement visuelles** (LEDs) et ne sont **pas émises par P9**. P9 envoie uniquement les CMD qui modifient l'état du jeu (`MOVE`, `WALL`, `GAMEOVER`).

**Justification :**

- `CMD MOVE` est déjà géré en P5 (déplacement moteur ou stub selon la version) : aucune modification.
- `CMD WALL` doit être acceptée pour ne pas bloquer une partie où l'IA joue un mur ; sans stub, le firmware tombe dans le `else` `non-impl`, ne renvoie jamais `DONE`, le Python épuise ses 3 retries en 45 s puis lève `UartTimeoutError` → partie cassée.
- `CMD GAMEOVER` est nécessaire à la fin de chaque partie pour signaler le gagnant à l'ESP32 (en P11, déclenche servo de réinit). Même raison : sans stub, le main loop Python boucle sur le timeout.
- `CMD HIGHLIGHT` et `CMD SET_TURN` : non utilisées par P9, donc pas de stub nécessaire — éviter le code mort.
- Dédup : la macro existante `respondCmdDone(seq)` côté `UartLink.cpp` mémorise déjà le résultat dans `_lastCmdResult`. Si un retry idempotent arrive avec le même seq, la réponse `DONE` est ré-émise sans réexécuter le stub. Comportement identique à `CMD MOVE`.

**Alternative écartée — implémenter aussi `HIGHLIGHT` et `SET_TURN` :** scope creep, ces deux CMD ne sont pas envoyées en P9 ; les implémenter avant P11 serait du code mort qui pourrait dériver.
**Alternative écartée — ne rien stubber, attendre P11 :** casse toute partie où l'IA pose un mur ou la partie se termine. Inutilisable pour P9.5 et au-delà.

### 2.4 Keepalive Python via thread dédié

**Décision :** activer le thread de keepalive dans `UartClient` (actuellement dormant). Il appelle `send_keepalive()` toutes les 1 s tant que `is_connected` est `True`. Démarré dans `connect()` après le handshake réussi, stoppé dans `close()`. Modèle thread-safe via `threading.Event` pour le stop, et le mutex `_tx_seq_lock` est déjà partagé avec le thread de lecture pour les writes série.

**Justification :**

- Le firmware exige des KEEPALIVE Python toutes les 1 s : 3 manqués (3 s) → ESP32 entre en `ERROR_STATE` (`UART_LOST`). Sans thread dédié, le main loop Python doit appeler `send_keepalive()` lui-même, ce qui couple le tempo keepalive à la latence du moteur de jeu ou de l'IA. Une partie où l'IA pense > 3 s tuerait la session.
- Le thread est **trivial** (boucle `while not stop: send_keepalive(); sleep(1.0)`) et **safe** (utilise les primitives `_send_request` qui prennent le mutex `_tx_seq_lock` partagé avec le main thread).
- Idempotent : `send_keepalive()` est déjà no-op si `is_connected == False`, donc pas de risque d'envoi pendant une déconnexion.
- Thread-safety du `Serial.write` : pyserial est thread-safe pour write si on n'a pas plusieurs writers concurrents sur le **même buffer**. Toutes les écritures passent par `_send_frame` qui prend `_tx_seq_lock` → linéarisation garantie.

**Alternative écartée — keepalive depuis le main loop :** couple à la durée d'une itération de jeu, casse dès qu'une opération synchrone dépasse 3 s.
**Alternative écartée — asyncio :** sur-ingénierie pour deux threads (lecture + keepalive) qui n'ont aucune raison de partager une boucle d'événements ; le reste du moteur de jeu est synchrone et le restera.

### 2.5 Robustesse aux déconnexions — version étendue

**Décision :** P9 est robuste à un cycle de déconnexion/reconnexion complet. Cinq exigences précises :

1. **Détection thread mort :** ajouter un attribut `_reader_alive: bool` (ou utiliser `_reader_thread.is_alive()`) ; toute tentative d'envoi (`send_ack`, `send_nack`, `send_cmd`, `send_keepalive`) sur un thread de lecture mort lève immédiatement `UartError("reader thread died")`. Empêche la pourriture silencieuse.
2. **`_reset_session()` clarifié :** la méthode actuelle remet `_tx_seq` à 0, `_last_request_seq` et `_last_err_received` à `None`, **mais oublie de remettre `is_connected` à `False`**. Bug : après `BOOT_START` reçu en session active (ESP32 a rebooté de lui-même), Python continue d'envoyer des KEEPALIVE/CMD comme si tout allait bien, alors qu'aucun handshake n'a eu lieu. Correctif : `_reset_session()` met `is_connected = False`.
3. **`handle_err_received` re-handshake après `RESET_SENT` :** quand `handle_err_received` envoie `CMD_RESET` (ERR récupérable), il **doit aussi** mettre `is_connected = False` et déclencher un nouveau `connect()` côté orchestrateur. Sans cela, on reste connecté logiquement à un ESP32 qui reboote, et le prochain `MOVE_REQ` arrive avec un seq inattendu (l'ESP32 a remis son `tx_seq` à 0 après reboot mais Python continue ses réponses sur l'ancien `tx_seq`).
4. **Timeout connect 15 s (uniforme) :** le `connect()` actuel a un timeout de 3 s par défaut. Trop court pour un reboot ESP32 (boot ~2 s + I2C self-test + homing dans `tickBoot` ~5-8 s). `GameSession` appelle systématiquement `connect(timeout=15.0)` — handshake initial **et** reconnexion après ERR (cf. §6.5 pour la justification du choix uniforme).
5. **Désync d'état documentée comme limitation P9 :** si l'ESP32 reboote en cours de partie, **les LEDs et la position du pion mécanique sont remises à zéro** (par construction du firmware Plan 1, qui ne persiste rien). Le moteur Python conserve son état de jeu, mais la cohérence visuelle/mécanique est cassée. P9 **ne tente pas** de re-synchroniser : on accepte ce trou comme limitation P9, à corriger en P11 par un homing systématique au début de chaque partie + envoi d'un état initial via une CMD dédiée. Documenté en §10.

**Justification :**

- Sans (1), un crash silencieux du thread de lecture (ex : `serial.read` lève une exception non gérée et `break` la boucle) laisse le client dans un état où il pense être connecté mais ne reçoit plus rien. Symptôme : timeouts 15 s à chaque CMD avec `UartTimeoutError` mystérieux.
- Sans (2), le bug `_reset_session` mène au scénario suivant : ESP32 reboote, Python reçoit `BOOT_START`, croit avoir un client connecté, envoie un `CMD MOVE` avec un seq qui n'a aucun sens pour l'ESP32 fraîchement booté → `UartTimeoutError` après 45 s, alors qu'un re-handshake aurait pris 200 ms.
- Sans (3), `handle_err_received` envoie `CMD_RESET` mais l'orchestrateur continue de jouer des coups vers un ESP32 qui se reboote. Symptôme : tour suivant suspendu jusqu'au timeout de la prochaine CMD.
- Sans (4), un reboot ESP32 fait timeout `connect()` au bout de 3 s alors que l'ESP32 n'a même pas fini son `tickBoot`. Le timeout 15 s couvre confortablement les ~10 s max de boot ESP32 avec marge.
- (5) est honnête : remettre les LEDs et la position physique au tour courant nécessite des CMD que P9 n'a pas (`SET_BOARD_STATE` ?) et c'est sans intérêt avant P11 où la position physique commence à exister.

**Alternative écartée — pas de reconnect auto :** rend le système trop fragile pour la démo (un fil USB qui bouge = partie perdue).
**Alternative écartée — reconnect infini avec backoff exponentiel :** sur-ingénierie pour un projet de soutenance ; un seul retry (déjà couvert par la boucle `connect()` côté orchestrateur) suffit.

### 2.6 CLI argparse standard

**Décision :** [`main.py`](../../main.py) gagne un parsing `argparse` (stdlib) avec trois flags :

- `--mode {console,plateau}` : `console` par défaut.
- `--port <chemin>` : port série pour le mode plateau (ex : `/dev/ttyUSB0`, `/dev/cu.SLAB_USBtoUART`). Obligatoire si `--mode plateau`. Nom calqué sur la convention `pio device monitor --port`/pyserial.
- `--debug` : flag booléen, active le mode verbeux (cf. §2.1 et §9). Compatible avec les deux modes.
- `--difficulty <facile|normal|difficile>` : déjà géré par le moteur (valeurs alignées sur `AI.__init__(difficulty=...)` qui attend `'facile'`, `'normal'`, ou `'difficile'`), repris en CLI pour ne plus dépendre du prompt interactif quand on lance en plateau.

**Justification :**

- `argparse` est dans la stdlib : zéro dépendance ajoutée.
- `--port` (vs `--serial` ou `--device`) suit la convention pyserial et `pio` que l'utilisateur connaît. Réduit la friction.
- Validation : si `--mode plateau` sans `--port`, `argparse.error()` immédiate avec message clair.
- `--difficulty` en CLI rend les sessions reproductibles (utile pour P9.5) et compatible avec le mode plateau silencieux (aucun prompt à éviter).

**Alternative écartée — typer / click :** dépendance externe pour un parser à 4 flags. Pas justifié.
**Alternative écartée — variables d'environnement :** moins découvrable (`--help` n'aide pas). À réserver aux configs sensibles, pas le cas ici.

### 2.7 `GameSession` comme classe dédiée d'orchestration

**Décision :** créer un nouveau module [`quoridor_engine/game_session.py`](../../quoridor_engine/game_session.py) avec une classe `GameSession` qui encapsule la boucle de jeu en mode plateau. Constructeur explicite :

```python
class GameSession:
    def __init__(
        self,
        game: QuoridorGame,
        ai: AI,
        uart: UartClient,
        debug: bool = False,
    ):
        self.game = game
        self.ai = ai
        self.uart = uart
        self.debug = debug
        self._unexpected_frame_count = 0  # observabilité

    def run(self) -> None:
        """Lance la partie. Bloquant. Lève les exceptions UART non-récupérables."""
        try:
            self.uart.connect(timeout=15.0)
            self._game_loop()
            self._send_gameover()
        finally:
            self.uart.close()
```

`main.py` se contente d'instancier `GameSession(game, ai, uart, debug)` et d'appeler `session.run()`. Toute la logique de boucle (attente intention / coup IA / envoi CMD / gestion ERR) vit dans `GameSession`.

**Justification :**

- Sépare la boucle plateau de la boucle console : `main.py` reste mince (CLI parsing + dispatch), chaque mode a son module.
- Testable en isolation : on injecte un `MockSerial` dans `UartClient`, un fake `AI`, et on vérifie le comportement de `GameSession.run()` sans hardware ni vrai port série.
- `try/finally` garantit que `uart.close()` est appelé dans 100 % des chemins (Ctrl+C, exception, fin normale). Évite les ports série coincés.
- Constructeur explicite avec `game`, `ai`, `uart` séparés (pas un objet global) → facile à mocker en test, facile à refactor.

**Alternative écartée — fonction `run_plateau_session(...)` à la place d'une classe :** marche aussi, mais perd la testabilité fine (impossible d'injecter des callbacks/hooks) et les attributs internes pour l'observabilité.
**Alternative écartée — étendre `QuoridorGame` avec un mode plateau :** viole la séparation moteur/UI déjà en place ; `QuoridorGame` doit rester ignorant du transport.

---

## 3. CLI et orchestration `main.py`

### 3.1 Surface CLI

```
python main.py [--mode {console,plateau}] [--port PORT] [--difficulty {facile,normal,difficile}] [--debug]
```

**Comportements :**

- Pas d'argument → `--mode console` par défaut, prompt interactif comme aujourd'hui.
- `--mode plateau` sans `--port` → `argparse.error("--port requis en mode plateau")`. Exit code 2.
- `--mode plateau --port /dev/ttyUSB0` → ouvre le port série, instancie `UartClient`, lance `GameSession.run()`. Aucun rendu console.
- `--debug` → active les logs verbeux (cf. §9). Compatible avec les deux modes.
- `--difficulty` (3 valeurs) : passé directement à l'`AI`. Si absent en mode console, fallback sur le prompt interactif existant. En mode plateau, fallback sur `normal` par défaut (pas de prompt en mode plateau).

### 3.2 Squelette `main.py` (haut niveau)

```python
import argparse
import sys
from quoridor_engine import QuoridorGame, AI, UartClient
from quoridor_engine.game_session import GameSession
import serial  # pyserial

def parse_args():
    p = argparse.ArgumentParser(description="Quoridor — moteur Python.")
    p.add_argument("--mode", choices=["console", "plateau"], default="console")
    p.add_argument("--port", help="Port série pour le mode plateau (ex /dev/ttyUSB0)")
    p.add_argument("--difficulty", choices=["facile", "normal", "difficile"])
    p.add_argument("--debug", action="store_true")
    args = p.parse_args()
    if args.mode == "plateau" and not args.port:
        p.error("--port requis en mode plateau")
    return args

def main():
    args = parse_args()
    if args.mode == "console":
        run_console(args)        # boucle console existante, déjà en place
    else:
        run_plateau(args)

def run_plateau(args):
    ser = serial.Serial(args.port, baudrate=115200, timeout=0.05)
    uart = UartClient(ser)
    game = QuoridorGame()
    # En mode plateau : humain = j1, IA = j2 (convention figée pour P9)
    ai = AI(player="j2", difficulty=args.difficulty or "normal")
    session = GameSession(game, ai, uart, debug=args.debug)
    try:
        session.run()
    except Exception as exc:
        print(f"[ERREUR] {exc}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### 3.3 Cycle de vie strict

- `serial.Serial` est ouvert dans `run_plateau` **avant** d'instancier `UartClient`. Si le port n'existe pas, `pyserial` lève `SerialException` immédiatement, avec un message clair.
- `GameSession.run()` est responsable d'appeler `uart.connect()` (handshake) puis `uart.close()` dans son `finally`. `run_plateau` ne touche pas au cycle de vie une fois `session.run()` lancé.
- `KeyboardInterrupt` (Ctrl+C) propage proprement à travers `GameSession.run()` → `finally` ferme le port → l'interruption remonte au-delà du `except Exception` de `run_plateau` (puisque `KeyboardInterrupt` n'hérite pas de `Exception`). Le port est déjà fermé par le `finally` de `GameSession.run()` ; le programme exit avec le comportement standard de Python (code 130 sous Unix). **Pas de port coincé.**

### 3.4 Validation P9.1

- `python main.py --help` affiche les 4 flags avec descriptions claires.
- `python main.py --mode plateau` (sans `--port`) → exit 2 avec message `--port requis en mode plateau`.
- `python main.py` (sans argument) → mode console identique à avant P9 (régression zéro).
- Tests : `tests/test_main_cli.py` (nouveau, 3-4 cas) en utilisant `argparse` et `monkeypatch` pour vérifier le dispatch sans réellement ouvrir un port série.

---

## 4. Flux entrant (intention joueur → ACK/NACK)

### 4.1 Séquence type

```
ESP32                                   RPi (GameSession)
-----                                   -----------------
(joueur appuie row=3 col=4)
<MOVE_REQ 3 4|seq=42|crc=...>     →
                                        uart.receive(timeout=...)
                                        → Frame(type=MOVE_REQ, args="3 4", seq=42)
                                        try:
                                            game.play_move(("deplacement", (3,4)))
                                        except InvalidMoveError as e:
                                            uart.send_nack(42, e.code.value)
                                        else:
                                            uart.send_ack(42)
                                  ←     <ACK|seq=N|ack=42|crc=...>
                                        ou
                                  ←     <NACK ILLEGAL|seq=N|ack=42|crc=...>
```

> **Note API moteur :** `QuoridorGame.play_move(move)` (et non `deplacer_pion`) infère le joueur courant via `get_current_player()` ; pas besoin de passer le joueur en argument. Idem pour les méthodes citées ci-dessous : `get_current_player()`, `is_game_over() → (bool, str|None)`, `get_winner()`.

### 4.2 Boucle `_game_loop` (côté `GameSession`)

```python
def _game_loop(self):
    while True:
        is_over, _ = self.game.is_game_over()
        if is_over:
            return
        if self.game.get_current_player() == "j1":   # joueur humain → plateau
            self._await_player_intent()
        else:                                         # IA → coup CMD
            self._send_ai_move()
```

`_await_player_intent` :

```python
def _await_player_intent(self):
    while True:
        frame = self.uart.receive(timeout=0.5)   # poll non-bloquant
        if frame is None:
            self._check_health()                 # vérifie thread mort
            continue
        if frame.type in ("MOVE_REQ", "WALL_REQ"):
            self._process_player_intent(frame)
            return
        if frame.type == "ERR":
            self._handle_err(frame)              # cf. §6.4
            return                               # _handle_err re-handshake si récupérable
        # Frame inattendue (ex KEEPALIVE pollué, BOOT_START spontané, ...)
        self._unexpected_frame_count += 1
        if self.debug:
            print(f"[debug] frame inattendue ignorée: {frame}")
```

`_check_health` se contente de vérifier `uart._is_reader_alive()` : si le thread est mort, on lève `UartError` immédiatement (au lieu d'attendre indéfiniment dans la boucle de poll).

### 4.3 Mapping `InvalidMoveError.code` → trame `NACK <code>`

`NackCode` est un `Enum` String défini dans `quoridor_engine/core.py` (à proximité de `InvalidMoveError`) :

```python
class NackCode(str, Enum):
    ILLEGAL         = "ILLEGAL"
    OUT_OF_BOUNDS   = "OUT_OF_BOUNDS"
    WRONG_TURN      = "WRONG_TURN"
    WALL_BLOCKED    = "WALL_BLOCKED"
    NO_WALLS_LEFT   = "NO_WALLS_LEFT"
    INVALID_FORMAT  = "INVALID_FORMAT"

class InvalidMoveError(Exception):
    def __init__(self, message: str, code: NackCode):
        super().__init__(message)
        self.code = code
```

**Mapping site → code (12 sites dans `core.py`, 1 dans `ai.py`) :**

| Ligne | Contexte | Code |
|---|---|---|
| `core.py:405` | déplacement, mauvais joueur | `WRONG_TURN` |
| `core.py:409` | déplacement vers case invalide | `ILLEGAL` |
| `core.py:558` | mur hors plateau | `OUT_OF_BOUNDS` |
| `core.py:564` | mur identique existant | `WALL_BLOCKED` |
| `core.py:576` | mur chevauche | `WALL_BLOCKED` |
| `core.py:582` | mur chevauche (cas perpendiculaire) | `WALL_BLOCKED` |
| `core.py:591` | mur croise un mur existant | `WALL_BLOCKED` |
| `core.py:627` | placement mur, mauvais joueur | `WRONG_TURN` |
| `core.py:631` | plus de murs | `NO_WALLS_LEFT` |
| `core.py:650` | mur bloque j1 | `WALL_BLOCKED` |
| `core.py:654` | mur bloque j2 | `WALL_BLOCKED` |
| `core.py:716` | clic non-adjacent (parsing intention bouton) | `INVALID_FORMAT` |
| `ai.py:1129` | erreur interne IA | `ILLEGAL` (jamais émise sur le wire) |

**Règle :** la valeur `NackCode.X.value` est une chaîne MAJUSCULES qui matche **exactement** un code du catalogue §4.4 du spec protocole. Tout ajout futur de code dans le moteur **doit** ajouter aussi la valeur correspondante dans le spec protocole (sinon trame protocole invalide côté firmware).

### 4.4 `_process_player_intent` (cœur du flux entrant)

```python
def _process_player_intent(self, frame: Frame):
    coup = self._parse_intent_to_move(frame)        # MOVE_REQ → ('deplacement',...)
                                                    # WALL_REQ → ('mur',('h'|'v',r,c,2))
    if coup is None:
        self.uart.send_nack(frame.seq, NackCode.INVALID_FORMAT.value)
        return
    try:
        self.game.play_move(coup)                   # infère le joueur courant
    except InvalidMoveError as e:
        self.uart.send_nack(frame.seq, e.code.value)
        if self.debug:
            print(f"[debug] NACK {e.code.value}: {e}")
        return
    self.uart.send_ack(frame.seq)
    if self.debug:
        print(f"[debug] ACK seq={frame.seq} coup={coup}")
```

`_parse_intent_to_move` extrait `row`/`col` (et `h`/`v` pour `WALL_REQ`). Si l'extraction échoue (ex args mal formés malgré CRC valide), retour `None` → NACK `INVALID_FORMAT`.

### 4.5 Validation P9.2

- `tests/test_game_session.py` (nouveau) couvre :
  - `MOVE_REQ` valide → `ACK` envoyé, `game.get_current_player()` bascule.
  - `MOVE_REQ` invalide (mauvais joueur, hors plateau, etc.) → `NACK <code>` envoyé.
  - `WALL_REQ` valide → `ACK`, `WALL_REQ` invalide → `NACK <code>`.
  - Frame inattendue (ex `KEEPALIVE` spontané) → ignorée, `_unexpected_frame_count` incrémenté.
- Test smoke : injection manuelle `MOVE_REQ` au Serial Monitor → réception `ACK`/`NACK` ESP32 visible dans les logs FSM.

---

## 5. Flux sortant (coup IA → CMD)

### 5.1 Séquence type

```
RPi (GameSession)                       ESP32
-----------------                       -----
(tour IA, ai.find_best_move(state) → ('deplacement',(2,5)))
<CMD MOVE 2 5|seq=N|crc=...>      →
                                        tickConnected dispatch CMD MOVE
                                        enterExecutingWithCommand(...)
                                        ... motion en cours (ou stub) ...
                                  ←     <DONE|seq=M|ack=N|crc=...>
uart.send_cmd("CMD","MOVE 2 5")
→ retourne après réception du DONE
game.play_move(coup)                    # joueur courant = j2 (IA)
```

### 5.2 `_send_ai_move`

```python
def _send_ai_move(self):
    coup = self.ai.find_best_move(self.game.get_current_state(), verbose=False)
    cmd_args = self._move_to_cmd_args(coup)         # 'MOVE 2 5' ou 'WALL h 1 2'
    if self.debug:
        print(f"[debug] IA → CMD {cmd_args}")
    try:
        self.uart.send_cmd("CMD", cmd_args)         # bloquant, retry idempotent
    except UartHardwareError as e:
        # ERR avec ack=seq → erreur hardware liée à cette CMD spécifiquement.
        # On ne joue pas le coup côté Python, on remonte pour que GameSession.run()
        # propage (ou re-handshake si is_recoverable_err).
        raise
    # CMD acknowledged : commit côté Python
    self.game.play_move(coup)                       # infère le joueur courant (j2)
```

> `AI.find_best_move(state, verbose=True)` est l'API actuelle (cf. `quoridor_engine/ai.py:1056`). On passe `verbose=False` pour ne pas polluer la sortie en mode plateau silencieux.

### 5.3 Mapping coup IA → args CMD

| Coup (format moteur) | Args CMD |
|---|---|
| `('deplacement', (row, col))` | `MOVE <row> <col>` |
| `('mur', ('h', row, col, 2))` | `WALL h <row> <col>` |
| `('mur', ('v', row, col, 2))` | `WALL v <row> <col>` |

Format strictement aligné sur §4.2 du spec protocole. Une fonction helper `_move_to_cmd_args(coup) -> str` centralise le formatage.

### 5.4 Fin de partie

À la sortie de `_game_loop` (la boucle retourne quand `is_game_over()` passe à `True`), `_send_gameover` envoie une CMD finale :

```python
def _send_gameover(self):
    winner = self.game.get_winner()               # "j1", "j2" ou None
    if winner is None:
        return                                    # défensif, ne devrait pas arriver
    if self.debug:
        print(f"[debug] FIN DE PARTIE → CMD GAMEOVER {winner}")
    try:
        self.uart.send_cmd("CMD", f"GAMEOVER {winner}")
    except (UartTimeoutError, UartHardwareError) as e:
        # En fin de partie, un échec ici est moins critique : on logge et on sort.
        if self.debug:
            print(f"[debug] CMD GAMEOVER échec : {e}")
```

Le firmware répond `DONE` (stub en P9, action servo en P11). Si la CMD échoue, on n'empêche pas la partie de se terminer côté Python — on log et on continue vers `finally` qui ferme le port.

### 5.5 Validation P9.3

- Tests `tests/test_game_session.py` :
  - Tour IA → `CMD MOVE r c` envoyée, `DONE` reçu (mock), coup committé côté Python.
  - Tour IA pour mur → `CMD WALL h/v r c` envoyée.
  - `CMD` perdue 2 fois → 3e essai aboutit (`MockSerial` qui ignore les 2 premiers writes) → coup committé.
  - `CMD` perdue 3 fois → `UartTimeoutError` levée, partie interrompue.
  - Fin de partie → `CMD GAMEOVER j1` ou `j2` envoyée.

---

## 6. Robustesse aux déconnexions

### 6.1 Vue d'ensemble

P9 doit survivre à un cycle complet « ESP32 reboot ↔ Python continue ». Cinq mécanismes coopèrent :

1. **Détection thread mort** (uart_client) → `UartError` immédiat.
2. **`_reset_session()` clear `is_connected`** (uart_client) → bug silencieux corrigé.
3. **`handle_err_received` re-handshake** (uart_client + GameSession).
4. **Timeout connect 15 s uniforme** (GameSession appelle `connect(timeout=15.0)` au handshake initial **et** lors de chaque reconnexion).
5. **Désync d'état acceptée** comme limitation P9 → P11.

### 6.2 Détection thread mort

```python
# Dans UartClient
def _is_reader_alive(self) -> bool:
    return self._reader_thread is not None and self._reader_thread.is_alive()

def _send_frame(self, frame: Frame) -> None:
    if not self._is_reader_alive():
        raise UartError("reader thread died — connexion cassée")
    self._serial.write(frame.encode())
```

Tous les `_send_*` passent par `_send_frame`, donc la détection est centralisée. Coût : un attribut booléen et un check par envoi (négligeable).

### 6.3 `_reset_session` corrigé

```python
def _reset_session(self) -> None:
    """Reset complet apres reboot ESP32 (BOOT_START ou HELLO en session active)."""
    with self._tx_seq_lock:
        self._tx_seq = 0
    self._last_request_seq = None
    self._last_err_received = None
    self.is_connected = False              # ← AJOUT P9
```

Effet : après un `BOOT_START` reçu, toute tentative d'envoi (`send_keepalive`, `send_ack`, `send_cmd`) est silencieusement ignorée (les `send_*` font `if not is_connected: return`) jusqu'à ce que `GameSession` détecte la situation et relance `connect()`.

### 6.4 `handle_err_received` re-handshake

`UartClient.handle_err_received` est étendue :

```python
def handle_err_received(self, frame: Frame) -> str:
    if frame.type != "ERR":
        raise ValueError(...)
    code = frame.args or "UNKNOWN"
    if is_recoverable_err(code):
        self.send_cmd_reset()              # ← d'abord (CMD_RESET no-op si is_connected=False)
        self.is_connected = False          # ← AJOUT P9 : force re-handshake (après l'envoi)
        return "RESET_SENT"
    raise UartHardwareError(code)
```

**Ordre critique :** `send_cmd_reset()` est appelée **avant** de passer `is_connected` à `False`. Sinon `send_cmd_reset` (qui no-op si `not is_connected`) ne ferait rien et l'ESP32 resterait bloqué en `ERROR_STATE` jusqu'à un reset manuel. L'inversion serait un bug silencieux ; à protéger par un test unitaire dédié (vérifier que la trame `CMD_RESET` est bien écrite sur le serial mock avant le reset de `is_connected`).

Côté `GameSession._handle_err` :

```python
def _handle_err(self, frame: Frame):
    try:
        result = self.uart.handle_err_received(frame)
    except UartHardwareError as e:
        # Non-récupérable : on remonte
        raise
    if result == "RESET_SENT":
        if self.debug:
            print(f"[debug] ESP32 ERR récupérable {frame.args} → CMD_RESET envoyé, reconnexion…")
        self.uart.connect(timeout=15.0)    # bloque jusqu'à HELLO ou timeout
        if self.debug:
            print("[debug] reconnexion réussie, reprise au tour courant")
```

Si `connect(timeout=15.0)` échoue (`UartTimeoutError`), l'exception remonte à `GameSession.run()` → `finally` → port fermé → `main.py` affiche l'erreur et exit 1. Pas de boucle infinie.

### 6.5 Connect timeout 15 s — uniformisé

Le `connect()` actuel a un paramètre `timeout=3.0` par défaut. P9 **n'utilise plus la valeur par défaut** : `GameSession.run()` et `GameSession._handle_err` appellent tous deux `connect(timeout=15.0)` explicitement.

**Justification :** dans le scénario nominal (ESP32 déjà en `WAITING_RPI` au lancement de Python), 200 ms suffisent et le `connect()` retourne dès le premier `HELLO` reçu — peu importe le timeout maximum. Mais si Python est lancé **avant** que l'ESP32 ait fini son `tickBoot` (ex : démarrage simultané des deux processeurs alimentés ensemble), il faut couvrir les ~5-10 s de boot ESP32 (I2C self-test + homing). Idem pour la reconnexion après `ERR`. Une seule valeur (15 s) couvre les deux cas avec marge, sans coût dans le cas nominal. Plus simple, moins bug-prone qu'une valeur différente selon le contexte.

Aucune modification de la signature de `connect()` (déjà paramétrable). Modification : utiliser `timeout=15.0` côté `GameSession`.

### 6.6 Désync d'état (limitation P9)

**Symptôme :** ESP32 reboote en cours de partie. Python conserve `game.get_current_player()`, l'IA, les murs placés. ESP32 perd son LED state, sa position pion physique (P11), son `tx_seq`. Python re-handshake, reprend le main loop, mais l'ESP32 ne sait plus :
- quel joueur a le tour (LED indicateur SET_TURN éteint)
- où sont les pions sur le plateau (LEDs pions éteintes)
- quels murs sont déjà posés (LEDs murs éteintes — en P11)

**Action P9 :** **aucune**. On documente. On accepte. Le joueur voit un plateau visuellement vide, mais Python continue de répondre correctement aux MOVE_REQ/WALL_REQ → la partie peut se terminer correctement, juste sans cohérence visuelle.

**Action P11 (à prévoir, hors scope ici) :** au début de chaque partie ET après reconnect, envoyer une CMD `SET_BOARD_STATE` qui restaure l'affichage complet (positions pions, murs posés, tour courant). Implique un nouveau type de trame côté protocole. À designer dans le spec P11.

### 6.7 Validation P9 robustesse

Tests dans `tests/test_uart_client.py` :

- `_reset_session()` clear `is_connected` (test de régression du bug).
- `_reader_loop` death → `_send_frame` lève `UartError`.
- `handle_err_received` avec code récupérable → `send_cmd_reset` appelé ET `is_connected = False`.
- `handle_err_received` avec code non-récupérable → `UartHardwareError` levée, `is_connected` non touché.

Tests dans `tests/test_game_session.py` :

- Scénario `BOOT_START` reçu en session active → main loop détecte la déconnexion (au prochain envoi) → reconnect 15 s OK → reprise.
- Scénario `ERR UART_LOST` reçu → `CMD_RESET` envoyé → reconnect → reprise.
- Scénario `ERR HOMING_FAILED` reçu → exception remonte, partie terminée.

---

## 7. Modifications firmware ESP32

### 7.1 Portée exacte

**Une seule modification** : ajouter deux branches dans le `if/else if` de [`firmware/src/GameController.cpp`](../../firmware/src/GameController.cpp), fonction `tickConnected`, **uniquement** dans cet état (pas dans `tickIntentPending` ni `tickExecuting`, qui ne reçoivent jamais de CMD).

**Localisation précise :** entre la ligne 170 (closing `}` de la branche `CMD MOVE`) et la ligne 171 (catch-all `else if (strcmp(f.type, "CMD") == 0)`). L'ajout doit s'insérer **avant** le catch-all `non-impl`, sinon les nouveaux `CMD WALL`/`CMD GAMEOVER` y tomberaient.

### 7.2 Code à ajouter

```cpp
} else if (strcmp(f.type, "CMD") == 0 && strncmp(f.args, "WALL ", 5) == 0) {
  UartLink::logf("FSM", "CMD WALL stub: %s", f.args + 5);
  UartLink::respondCmdDone(f.seq);
} else if (strcmp(f.type, "CMD") == 0 && strncmp(f.args, "GAMEOVER ", 9) == 0) {
  UartLink::logf("FSM", "CMD GAMEOVER stub: %s", f.args + 9);
  UartLink::respondCmdDone(f.seq);
```

**Détails du diff :**

- **Insertion entre L170 et L171** : la branche `CMD MOVE` se termine ligne 170 par `}` ; la nouvelle branche `CMD WALL` commence par `} else if (...)`. La branche `CMD GAMEOVER` suit immédiatement.
- Le catch-all `else if (strcmp(f.type, "CMD") == 0) { UartLink::logf("FSM", "CMD non-impl: %s", f.args); }` reste intact en aval, capturant tout autre `CMD HIGHLIGHT`/`CMD SET_TURN`/`CMD ???` non implémentée — mais P9 n'en envoie aucun.
- `respondCmdDone(f.seq)` mémorise le résultat dans `_lastCmdResult` côté `UartLink.cpp` (lignes 291-307) : un retry idempotent avec le même seq déclenche la ré-émission automatique du `DONE` sans réexécuter le bloc → comportement identique à `CMD MOVE`. **Aucune modification de `UartLink.cpp` requise.**

### 7.3 Liste exhaustive des fichiers modifiés / créés (côté firmware)

| Fichier | Type | Lignes net | Justification |
|---|---|---|---|
| [`firmware/src/GameController.cpp`](../../firmware/src/GameController.cpp) | Modifié | +6 | 2 branches stub `CMD WALL` et `CMD GAMEOVER` |

**C'est tout.** Aucune modification de :
- `UartLink.cpp/h` — la dédup et `respondCmdDone` sont déjà génériques.
- `MotionControl.cpp/h` — pas de motion réelle pour `WALL`/`GAMEOVER` en P9 (P11).
- `LedAnimator.cpp/h` — pas d'animation spécifique en P9 (P11).
- `GameController.h` — pas de nouvel état FSM.
- `main.cpp` — pas de nouvelle init.

### 7.4 Validation P9.4 (firmware)

- `cd firmware && pio run` → exit 0, **aucun nouveau warning** (vérifier la sortie comparée à un `pio run` avant la modification).
- Logs FSM visibles au Serial Monitor lors d'une `CMD WALL h 2 3` injectée : `FSM CMD WALL stub: h 2 3` puis trame `<DONE|seq=...|ack=...|crc=...>` émise.
- Test idempotence (à vérifier en P9.5 sur DevKit) : 2 × `CMD WALL` avec même `seq` → 2 × `DONE` reçus, **un seul** log `FSM CMD WALL stub` (le 2e est dédoublonné par `_lastCmdResult`).
- Conformité au contrat de dédup `UartLink.cpp` lignes 291-307 (référence) — pas de réécriture, juste appel de l'API existante.

### 7.5 Pas de modification protocolaire

Aucun nouveau type de trame, aucun nouveau code d'erreur, aucun champ supplémentaire. Le spec protocole [`2026-05-01-protocole-uart-plan-2-design.md`](2026-05-01-protocole-uart-plan-2-design.md) reste **strictement** inchangé. P9 est purement une couche d'orchestration au-dessus du protocole figé.

---

## 8. Stratégie de tests

### 8.1 Tests Python (sans hardware)

**Nouveaux fichiers :**

- [`tests/test_game_session.py`](../../tests/test_game_session.py) — 9 tests planifiés (cf. liste ci-dessous).
- [`tests/test_main_cli.py`](../../tests/test_main_cli.py) — 3-4 tests sur `argparse` (mode console, mode plateau avec/sans port, --debug, --difficulty).

**Tests étendus dans fichiers existants :**

- [`tests/test_uart_client.py`](../../tests/test_uart_client.py) — 4 nouveaux tests :
  - `_reset_session` clear `is_connected` (régression bug).
  - Thread reader mort → `_send_frame` lève `UartError`.
  - `handle_err_received` récupérable → `is_connected = False`.
  - Keepalive thread démarre dans `connect()`, stoppe dans `close()`.
- [`tests/test_core.py`](../../tests/test_core.py) — étendre les tests existants pour vérifier que chaque `InvalidMoveError` levée porte bien le `code` attendu (paramétrer les tests existants).

**Cas couverts par `test_game_session.py` :**

1. Handshake nominal → `_game_loop` démarre.
2. `MOVE_REQ` valide → `ACK` envoyé, état avancé.
3. `MOVE_REQ` invalide (out_of_bounds) → `NACK OUT_OF_BOUNDS` envoyé.
4. `WALL_REQ` valide → `ACK`.
5. Tour IA → `CMD MOVE r c` → `DONE` mock → coup committé.
6. Tour IA mur → `CMD WALL h r c` → `DONE`.
7. `CMD` 3× perdues → `UartTimeoutError`.
8. Fin de partie → `CMD GAMEOVER j1` envoyée.
9. `ERR UART_LOST` reçu pendant `_await_player_intent` → reconnect 15 s mocké → reprise.

Toutes ces situations utilisent `MockSerial` (déjà présent dans `tests/test_uart_client.py`, à réutiliser ou refactor en fixture partagée).

### 8.2 Tests firmware (sans hardware)

`pio run` (compilation seule) après les modifications de [`firmware/src/GameController.cpp`](../../firmware/src/GameController.cpp) → exit 0, pas de nouveau warning. Pas de tests unitaires C++ ajoutés (le projet n'en a pas de cadre, et la modification est de 6 lignes).

### 8.3 Tests E2E (P9.5, reportés)

- Sur DevKit ESP32 connecté en USB :
  - Partie complète PvIA via `python main.py --mode plateau --port /dev/ttyUSB0` avec injection manuelle des intentions joueur via `BTN x y` au Serial Monitor.
  - Vérifier les `CMD MOVE`/`CMD WALL`/`CMD GAMEOVER` au Serial Monitor.
  - Couper le câble USB pendant 5 s → ESP32 entre en `ERROR_STATE` `UART_LOST` → Python re-handshake → partie reprend.
  - Tester `--debug` activé : toutes les trames sont imprimées au terminal.

Reporté au 2026-05-04 (retour DevKit). Tracking : à ajouter à [`firmware/INTEGRATION_TESTS_PENDING.md`](../../firmware/INTEGRATION_TESTS_PENDING.md) si le fichier existe encore, sinon créer une checklist similaire.

### 8.4 Tests E2E sans hardware (P9.5 alternative — chantier séparé)

**Hors scope de ce spec.** Si le DevKit reste indisponible au-delà du 2026-05-04, construire un simulateur de niveau 2 « FakeESP32 » qui émule le firmware côté pty Unix (`os.openpty()`) pour exécuter les mêmes tests E2E sans hardware. Spec à écrire séparément.

### 8.5 Régression non-régression

Les **90 tests Python existants** doivent rester verts à chaque commit P9. Toute régression est un blocker. La modification de `InvalidMoveError` (ajout du `code` obligatoire) est la modification la plus à risque — elle touche 12 sites dans `core.py`. Les tests existants qui font `with pytest.raises(InvalidMoveError)` doivent être **paramétrés** pour vérifier aussi le `.code` (refactor optionnel mais propre).

---

## 9. Observabilité et debug

### 9.1 `--debug` activé : sortie attendue au terminal

```
[debug] handshake → HELLO_ACK envoyé (v=1)
[debug] keepalive thread démarré (1 Hz)
[debug] tour j1 (humain) — attente intention plateau
[debug] frame inattendue ignorée: Frame(type='KEEPALIVE', ...)
[debug] ACK seq=42 coup=('deplacement', (3, 4))
[debug] tour j2 (IA) — réflexion difficulté=normal
[debug] IA → CMD MOVE 4 5
[debug] DONE reçu (ack=N)
[debug] FIN DE PARTIE → CMD GAMEOVER j1
```

### 9.2 Compteurs internes

- `GameSession._unexpected_frame_count` : nombre de frames protocolaires reçues hors contexte (ex `KEEPALIVE` reçu pendant `_await_player_intent`). Imprimé en `--debug` à la fin de partie.
- **Ajout P9 dans `UartClient`** : un compteur `_rejected_count: int` incrémenté à chaque `UartProtocolError` capturée silencieusement dans `_dispatch_line` (la branche `except UartProtocolError: pass` actuellement en place ne compte rien). Un getter `get_rejected_count()` expose la valeur. Aligné sur le côté firmware (`UartLink::getRejectedCount()`) qui existe déjà. Imprimé en `--debug` à la fin de partie.

### 9.3 Logs ESP32 visibles côté Python

`UartClient` collecte déjà les lignes ne commençant pas par `<` dans `_debug_lines` (rotatif 200 lignes). En `--debug`, imprimer ces lignes en temps réel au terminal Python (ex via un callback `on_debug_line` ou en surveillant la liste). Cette amélioration est mineure et peut être incluse dans P9.1 ou différée.

### 9.4 Pas de fichier de log

P9 n'introduit pas de `logging` Python ni de fichier `.log`. La sortie console suffit pour le projet (démo, dev). Si un besoin de log persistant émerge en P10+, à ajouter via un module séparé.

---

## 10. Limitations connues et reports

### 10.1 Désync d'état après reboot ESP32

Voir §6.6. **Documentée**, **acceptée** comme limitation P9, **traitée en P11** par homing systématique + CMD `SET_BOARD_STATE` (à designer).

### 10.2 Pas de gestion fine des erreurs hardware

Si l'ESP32 émet `ERR MOTOR_TIMEOUT` ou `ERR HOMING_FAILED` (codes non récupérables), `GameSession.run()` lève `UartHardwareError` et la partie se termine brutalement. Le joueur voit un message `[ERREUR]` au terminal, mais le plateau physique reste figé. Acceptable pour la démo (ces erreurs sont rares en conditions normales) ; à raffiner en P13 (tests de robustesse) si nécessaire.

### 10.3 `ERR` spontané pendant `send_cmd` : récupération différée jusqu'à 45 s

**Symptôme :** pendant `_send_ai_move`, `send_cmd` bloque dans sa boucle d'attente du `DONE`. Si l'ESP32 émet un `ERR UART_LOST` spontané (sans `ack=`, donc pas pour cette CMD), `send_cmd` voit la trame, ne match pas le `DONE` attendu, la **remet en queue** (`_rx_queue.put(received)`), et continue d'attendre 15 s. Au bout de 45 s (3 essais × 15 s), `UartTimeoutError` lève. Pendant ce temps, l'ERR récupérable est resté dans la queue, sans déclencher de re-handshake immédiat.

**Conséquence :** un ERR récupérable arrivé pendant un coup IA prolonge le délai de récupération de ~200 ms à ~45 s.

**Justification du choix :** ajouter une logique de détection ERR à l'intérieur de `send_cmd` complexifie la primitive bas niveau (qui doit rester focalisée sur l'idempotence d'une CMD). La probabilité concrète est faible (l'ESP32 doit perdre le KEEPALIVE pendant que l'IA réfléchit, fenêtre courte). Pour la démo, accepter ce délai est raisonnable.

**Action P13 (si nécessaire) :** ajouter un hook de pré-emption dans `send_cmd` (ex callback `on_unrelated_err` qui peut lever une exception spéciale pour interrompre l'attente). Hors scope P9.

### 10.4 Pas de mode reprise de partie

Si `GameSession.run()` lève une exception, la partie est perdue. Pas de save/load. Hors scope (pas demandé, pas de bénéfice pour la démo).

### 10.5 P9.5 reporté

Tests E2E sur DevKit → 2026-05-04 (retour DevKit). Si le DevKit reste indisponible, simulateur niveau 2 → spec et chantier séparés.

---

## 11. Hors scope (specs / phases ultérieurs)

- **Drivers réels P11** : LEDs WS2812B (pions, murs, indicateur tour, animations), moteurs A4988 via MCP23017 (déplacements XY réels), servo SG90 (réinit murs en `CMD GAMEOVER`). P9 ne fait que les stubs.
- **`CMD SET_BOARD_STATE`** : nouveau type de trame nécessaire pour synchroniser l'affichage après reconnect. Designé en P11.
- **`CMD HIGHLIGHT` et `CMD SET_TURN`** : implémentation côté firmware uniquement en P11 (LEDs réelles). Spec protocole les décrit déjà mais P9 ne les émet pas.
- **Simulateur niveau 2 (FakeESP32 sur pty)** : chantier séparé, spec à écrire si nécessaire après 2026-05-04.
- **Tests d'intégration sur PCB v2** : phases P10+, après réception PCB (~2026-05-10).
- **Logging persistant** : non requis pour la soutenance.
- **Mode multi-joueurs / multi-AI** : non envisagé.
- **Persistence de partie / save-load** : non envisagé.

---

## Annexe A — Validation finale du spec

Avant transition vers `writing-plans` :

- [ ] Toutes les décisions §2 sont défendables en soutenance avec une alternative écartée justifiée.
- [ ] Le mapping `InvalidMoveError.code` (§4.3) est exhaustif sur les 12 sites de `core.py` et le 1 site `ai.py`.
- [ ] La modification firmware §7 est minimale (6 lignes net) et réutilise les API existantes (`respondCmdDone`).
- [ ] Les 5 mécanismes de robustesse §6 sont explicites et testables sans hardware.
- [ ] La désync d'état §6.6 est documentée comme limitation P9, pas comme bug.
- [ ] Les tests §8 sont réalisables sans DevKit (les E2E P9.5 sont identifiés comme reportés).
- [ ] Aucun nouveau type de trame, aucun nouveau code d'erreur protocole — le spec UART Plan 2 reste figé.

---

## Annexe B — Chemin critique d'implémentation

À titre indicatif (le plan détaillé sera produit par `writing-plans`) :

1. **Setup** : créer `NackCode` Enum, refactor `InvalidMoveError(message, code)` partout (12 + 1 sites).
2. **`tests/test_core.py`** : paramétrer les `pytest.raises(InvalidMoveError)` pour vérifier `.code`.
3. **`UartClient` extensions** : keepalive thread, `_reset_session` corrigé, `handle_err_received` re-handshake, détection thread mort.
4. **Tests unitaires UART** : extensions `test_uart_client.py` (4 nouveaux).
5. **`game_session.py`** : créer le module et la classe `GameSession`.
6. **Tests `game_session.py`** : 9 tests.
7. **`main.py`** : argparse + dispatch console/plateau.
8. **Tests `main_cli.py`** : 3-4 tests.
9. **Firmware** : ajouter les 2 stubs dans `GameController.cpp`, vérifier `pio run`.
10. **Doc** : mettre à jour [`docs/02_architecture.md`](../../02_architecture.md), [`docs/06_protocole_uart.md`](../../06_protocole_uart.md), [`docs/00_plan_global.md`](../../00_plan_global.md), [`CHANGELOG.md`](../../../CHANGELOG.md) (à la racine du repo).

P9.5 (E2E DevKit) sera traité en commit séparé après le 2026-05-04.
