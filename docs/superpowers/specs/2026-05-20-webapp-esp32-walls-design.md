# Spec — Connexion webapp ↔ ESP32 pour levée physique des murs

**Date** : 2026-05-20
**Auteur** : Silouane (brainstorming Claude Code)
**Statut** : Draft, en revue avant écriture du plan d'implémentation
**Cible** : démo Quoridor avec plateau physique partiel

## 1. Contexte et objectif

### Situation actuelle

- Le moteur de jeu Quoridor et l'IA tournent en Python sur Mac (et plus tard sur RPi).
- Une webapp FastAPI (`webapp/`) expose le moteur à un navigateur (port 8000/8001).
- Un bring-up ESP32 fonctionnel pilote un système CoreXY + servo qui peut lever des murs sur un plateau physique ([`firmware/src/bringup_l298n_complet.cpp`](../../../firmware/src/bringup_l298n_complet.cpp)).
- La matrice des positions physiques de murs est partiellement remplie : 18 cases mesurées sur 60 ([`bringup_l298n_complet.cpp:140-177`](../../../firmware/src/bringup_l298n_complet.cpp#L140-L177)).

### Objectif

Quand l'utilisateur ou l'IA pose un mur dans la webapp, et si la (les) case(s) physique(s) correspondante(s) sont mesurées dans la matrice ESP32, le piston va à la position et lève le mur physiquement. Si une case n'est pas mesurée, on l'ignore silencieusement et le jeu continue normalement côté logique.

### Non-objectifs

- Pas de déplacement physique des pions (le système ne supporte que les murs).
- Pas d'indicateur UI "ce mur est levable physiquement".
- Pas de reconnexion automatique si l'USB est débranché en cours de partie.
- Pas de file d'attente custom côté Python (on s'appuie sur le buffer série natif).
- Pas de feedback ACK consommé côté Python (les retours du firmware sont loggués sur Serial uniquement, pour debug humain).

## 2. Architecture

```
┌──────────────┐    HTTP/WiFi    ┌──────────────────┐    UART/USB    ┌────────┐
│  Téléphone   │────────────────▶│  Mac (ou RPi)    │───câble USB───▶│ ESP32  │
│  (Safari)    │                 │  Python+FastAPI  │                │        │
└──────────────┘                 └──────────────────┘                └────────┘
                                          │                              │
                                  3 couches Python                 firmware C++
                                  (server.py → service.py          bring-up texte
                                   → uart_bridge.py)                brut sur Serial
                                                                       │
                                                                       ▼
                                                                  CoreXY + servo
```

### Décisions structurantes

- **Texte brut sur UART** (115200 bauds, terminateur `\n`), pas le protocole structuré "Plan 2" implémenté dans [`quoridor_engine/uart_client.py`](../../../quoridor_engine/uart_client.py). Justification : le firmware bring-up ne parle pas Plan 2 (frames, CRC, seq, HELLO/HELLO_ACK), refondre le firmware pour Plan 2 est hors scope et inutile pour ce démo.
- **`webapp/uart_bridge.py` est refondu** : on n'importe plus `UartClient`, on utilise `pyserial` directement.
- **Communication fire-and-forget** côté Python. Le firmware traite les commandes en série naturellement via son `loop()` Serial.
- **Le moteur Quoridor (Python) reste l'autorité du jeu**. Le plateau physique est purement un effet visuel.

## 3. Mapping coordonnées Quoridor ↔ matrice firmware

### Repères

| | Webapp / engine Quoridor | Firmware ESP32 |
|---|---|---|
| Origine | (0,0) en **haut-gauche** | HOME en **bas-gauche** |
| Axe vertical | row 0 (haut) → row 5 (bas) | j=0 (bas) → j max (haut) |
| Axe horizontal | col 0 (gauche) → col 5 (droite) | i=0 (gauche) → i max (droite) |

### Convention des murs Quoridor

- Mur H `('h', row, col, 2)` : sépare les rangs `row` et `row+1`, s'étend horizontalement sur les colonnes `col` et `col+1`. Domaine : `row, col ∈ [0..4]` (vérifié contre [`quoridor_engine/core.py:236-294`](../../../quoridor_engine/core.py#L236-L294)).
- Mur V `('v', row, col, 2)` : sépare les colonnes `col` et `col+1`, s'étend verticalement sur les rangs `row` et `row+1`. Domaine : `row, col ∈ [0..4]`.

### Formules de conversion

**Mur horizontal** `('h', row, col)` → 2 cases firmware :

```
j = 4 - row              (j ∈ [0..4], MUR_H_NB_J=5)
i ∈ {col, col + 1}       (i ∈ [0..5], MUR_H_NB_I=6)
→ cases : MURS_H[4 - row][col]  et  MURS_H[4 - row][col + 1]
```

**Mur vertical** `('v', row, col)` → 2 cases firmware :

```
i = col                  (i ∈ [0..4], MUR_V_NB_I=5)
j ∈ {5 - row, 4 - row}   (j ∈ [0..5], MUR_V_NB_J=6)
→ cases : MURS_V[5 - row][col]  et  MURS_V[4 - row][col]
```

### Vérification par exemples

| Mur webapp | Cases firmware | Mesurées ? | Action attendue |
|---|---|---|---|
| `('h', 0, 0)` (haut-gauche) | `MURS_H[4][0]={109,777}` et `MURS_H[4][1]=_NA` | 1/2 | 1 case levée |
| `('h', 1, 2)` (milieu haut) | `MURS_H[3][2]=_NA` et `MURS_H[3][3]=_NA` | 0/2 | aucune case, log silencieux |
| `('v', 0, 0)` (haut-gauche) | `MURS_V[5][0]={34,707}` et `MURS_V[4][0]=_NA` | 1/2 | 1 case levée |

### Couverture théorique avec la matrice actuelle

- **Murs H levables ≥ 1 case** : `row ∈ {0, 2, 4}` × `col ∈ {0, 2, 3, 4}` = **12 murs H**.
- **Murs V levables ≥ 1 case** : `col ∈ {0, 2, 4}` × `row ∈ {0, 1, 2, 4}` = **12 murs V**.
- **Total : 24 murs sur 50** ont au moins 1 case levable physiquement.
- **Aucun mur n'a ses 2 cases mesurées** : sur l'axe `i` de MURS_H, les valeurs mesurées sont {0, 3, 5} → pas de paire adjacente. Idem sur l'axe `j` de MURS_V : {0, 3, 5}. Conséquence : tous les murs levables seront "demi-mur" (1 case sur 2).

Si on souhaite pouvoir lever des murs complets pour le démo, mesurer 2-3 cases supplémentaires aux indices `i=1` ou `i=4` (MURS_H) et `j=1` ou `j=4` (MURS_V) suffirait. **Hors scope de cette spec.**

## 4. Protocole UART texte brut

### Direction webapp → ESP32

Toutes les commandes sont terminées par `\n`, ASCII, majuscules.

#### `PING`

Sonde de détection au boot. Pas d'argument. Le firmware répond `PONG\n`.

```
PING\n
```

#### `WALL <H|V> <row> <col>`

Demande la levée d'un mur Quoridor.

- `orientation` : `H` ou `V` (majuscule).
- `row, col` : entiers décimaux dans `[0..4]`.

Exemples :
```
WALL H 0 0\n
WALL V 2 3\n
```

### Direction ESP32 → webapp (loggué uniquement)

Le firmware émet ces messages sur `Serial.println(...)` pour le debug humain. **La webapp ne les attend pas** et ne fait pas de parsing.

```
PONG                                          # réponse à PING
WALL OK <H|V> <row> <col> raised=<n>          # n ∈ {0, 1, 2}
WALL ERR <message>                            # parsing/borne KO, ou orientation invalide
```

Exemples de logs firmware attendus :
```
WALL OK H 0 0 raised=1
WALL OK H 1 2 raised=0
WALL ERR borne : row=7 col=2 hors [0..4]
WALL ERR orientation : H ou V attendu
```

### Pourquoi pas le protocole "Plan 2"

[`quoridor_engine/uart_client.py`](../../../quoridor_engine/uart_client.py) implémente un protocole structuré avec frames `<TYPE args|seq=N|crc=XXXX>`, handshake `HELLO`/`HELLO_ACK` versionné, ACK/NACK/DONE. Le firmware bring-up actuel ne parle **pas** ce protocole, et l'implémenter en C++ est plusieurs jours de travail. **Cette spec choisit délibérément la voie texte brut** pour rester cohérente avec le bring-up validé et tenir l'objectif démo. `UartClient` reste utilisable pour un futur firmware Plan 2, mais n'est pas utilisé ici.

## 5. Modifications firmware

### 5.1 Fichier : `firmware/src/bringup_l298n_complet.cpp`

Aucune modification des commandes existantes (`HOME`, `GOTO`, `X F/B`, `Y F/B`, `M1/M2`, `LEVER`, `BAISSER`, `SERVO`, `MUR H/V`, `TOUR`, `DEMO`, etc.). Tout reste fonctionnel pour le debug manuel.

### 5.2 Ajout 1 : commande `PING`

À placer dans `traiter(String s)`, près du début (priorité haute, parsing court) :

```cpp
if (s == "PING") {
    Serial.println("PONG");
    return;
}
```

### 5.3 Ajout 2 : commande `WALL`

À placer dans `traiter()`, juste avant le bloc `s.startsWith("MUR ")` pour éviter les collisions (les deux commencent par M sinon W).

Pseudo-code (la version finale est dans le plan d'implémentation) :

```cpp
if (s.startsWith("WALL ")) {
    String r = s.substring(5); r.trim();
    if (r.length() < 5 || (r.charAt(0) != 'H' && r.charAt(0) != 'V')) {
        Serial.println("WALL ERR orientation : H ou V attendu");
        return;
    }
    char orient = r.charAt(0);
    String reste = r.substring(2); reste.trim();
    int sp = reste.indexOf(' ');
    if (sp < 0) {
        Serial.println("WALL ERR syntaxe : WALL <H|V> <row> <col>");
        return;
    }
    int row = reste.substring(0, sp).toInt();
    int col = reste.substring(sp + 1).toInt();
    if (row < 0 || row > 4 || col < 0 || col > 4) {
        Serial.print("WALL ERR borne : row="); Serial.print(row);
        Serial.print(" col="); Serial.print(col);
        Serial.println(" hors [0..4]");
        return;
    }
    int raised = wall_lever(orient, row, col);
    Serial.print("WALL OK "); Serial.print(orient);
    Serial.print(" "); Serial.print(row); Serial.print(" "); Serial.print(col);
    Serial.print(" raised="); Serial.println(raised);
    return;
}
```

### 5.4 Ajout 3 : helper `wall_lever(char, int, int) → int`

Effectue le mapping (orientation, row, col) → 2 cases firmware, puis pour chaque case mesurée : GOTO + LEVER + BAISSER. Retourne le nombre de cases effectivement levées.

```cpp
static constexpr uint32_t WALL_DELAI_LEVE_MS = 400;
static constexpr uint32_t WALL_DELAI_BAISSE_MS = 400;

static int wall_lever_case(int32_t x, int32_t y) {
    goto_xy(x, y);
    servo.write(SERVO_LEVER_DEG);
    delay(WALL_DELAI_LEVE_MS);
    servo.write(SERVO_REPOS_DEG);
    delay(WALL_DELAI_BAISSE_MS);
    return 1;
}

static int wall_lever(char orientation, int row, int col) {
    int raised = 0;
    int32_t x, y;

    if (orientation == 'H') {
        int j = 4 - row;
        if (position_mur_h(col, j, x, y))     raised += wall_lever_case(x, y);
        if (position_mur_h(col + 1, j, x, y)) raised += wall_lever_case(x, y);
    } else {  // 'V'
        int i = col;
        if (position_mur_v(i, 5 - row, x, y)) raised += wall_lever_case(x, y);
        if (position_mur_v(i, 4 - row, x, y)) raised += wall_lever_case(x, y);
    }
    return raised;
}
```

Note : `position_mur_h(i, j, &x, &y)` et `position_mur_v(i, j, &x, &y)` existent déjà ([`bringup_l298n_complet.cpp:352-366`](../../../firmware/src/bringup_l298n_complet.cpp#L352-L366)) et retournent `false` si la case est `_NA`. Donc le filtrage "case mesurée ?" est gratuit.

### 5.5 Mise à jour de `afficher_aide()`

Ajouter dans le `HELP` :
```cpp
Serial.println("  PING              repond PONG (detection webapp)");
Serial.println("  WALL <H|V> <r> <c>   lever mur Quoridor (r,c dans [0..4])");
```

## 6. Modifications Python

### 6.1 Fichier : `webapp/uart_bridge.py`

**Refonte complète.** L'ancien code utilisait `UartClient` (protocole Plan 2). Le nouveau code utilise `pyserial` en texte brut.

Nouveau contenu cible (~80 lignes) :

```python
"""Wrapper texte brut autour de pyserial pour mirroir les coups au plateau.

Détection au boot : ouvre le port série du DevKit ESP32 et fait un PING/PONG.
Si PONG reçu dans le délai, le bridge est actif. Sinon, init() retourne None
et la webapp reste en mode autonome.

Erreur en cours de partie : log + désactivation locale (available=False).
Pas de tentative de reconnexion (cohérent avec spec demo §10.4).
"""
from __future__ import annotations

import glob
import logging
import platform
import time
from typing import Optional

import serial

log = logging.getLogger(__name__)

PING_TIMEOUT_S = 5.0
PING_RETRY_INTERVAL_S = 0.5


def _find_devkit_port() -> Optional[str]:
    """Cherche le port série du DevKit ESP32."""
    system = platform.system()
    if system == "Darwin":
        ports = sorted(glob.glob("/dev/cu.usbserial-*"))
    else:
        ports = sorted(glob.glob("/dev/ttyUSB*"))
        if not ports:
            ports = sorted(glob.glob("/dev/ttyAMA*"))
    return ports[0] if ports else None


def _open_and_handshake(port: str) -> Optional[serial.Serial]:
    """Ouvre le port et fait un PING/PONG. Retourne serial ouvert ou None."""
    try:
        s = serial.Serial(port, 115200, timeout=PING_RETRY_INTERVAL_S, write_timeout=1.0)
    except Exception as e:
        log.warning("UartBridge: ouverture port %s echouee : %s", port, e)
        return None

    deadline = time.monotonic() + PING_TIMEOUT_S
    while time.monotonic() < deadline:
        try:
            s.reset_input_buffer()
            s.write(b"PING\n")
            s.flush()
            line = s.readline()
            if b"PONG" in line:
                return s
        except Exception as e:
            log.warning("UartBridge: PING echoue (%s)", e)
            try:
                s.close()
            except Exception:
                pass
            return None

    log.info("UartBridge: aucun PONG recu sur %s apres %.1fs.", port, PING_TIMEOUT_S)
    try:
        s.close()
    except Exception:
        pass
    return None


def init() -> Optional["UartBridge"]:
    """Tente de détecter et d'ouvrir le port UART."""
    port = _find_devkit_port()
    if port is None:
        log.info("UartBridge: aucun port detecte, mode autonome.")
        return None
    s = _open_and_handshake(port)
    if s is None:
        return None
    log.info("UartBridge: connecte sur %s.", port)
    return UartBridge(s)


class UartBridge:
    """Mirror best-effort des coups vers le firmware ESP32 (texte brut)."""

    def __init__(self, serial_obj: serial.Serial):
        self._serial = serial_obj
        self.available: bool = True

    def forward_move(self, move: tuple) -> None:
        """Envoie un coup au plateau. No-op si indisponible ou si déplacement de pion.

        En cas d'erreur, log et désactive `available`. Ne lève PAS.
        """
        if not self.available:
            return
        move_type, payload = move
        try:
            if move_type == "mur":
                orientation = payload["orientation"].upper()
                row = int(payload["row"])
                col = int(payload["col"])
                line = f"WALL {orientation} {row} {col}\n"
                self._serial.write(line.encode("ascii"))
                self._serial.flush()
            elif move_type == "deplacement":
                # No-op : pas de système physique de déplacement de pion pour ce démo.
                return
            else:
                log.warning("UartBridge: type de coup inconnu %r, ignore.", move_type)
        except Exception as e:
            log.warning("UartBridge: forward echoue (%s), desactivation mirroring.", e)
            self.available = False

    def close(self) -> None:
        try:
            self._serial.close()
        except Exception:
            pass
```

### 6.2 Fichiers non modifiés

- `webapp/server.py` : pas de changement, le contrat `init() → UartBridge|None` reste identique.
- `webapp/service.py` : pas de changement, `forward_move(move)` garde la même signature et le même contrat (no-op si indisponible, ne lève pas).
- `webapp/schemas.py` : pas de changement.
- Frontend (`webapp/static/`) : pas de changement.

### 6.3 Tests à mettre à jour

- `tests/webapp/test_uart_bridge.py` : à réécrire. Les mocks sur `_open_client` n'ont plus de sens. Nouveau jeu de tests :
  - `test_init_no_port` : `_find_devkit_port` retourne `None` → `init()` retourne `None`.
  - `test_init_no_pong` : port trouvé, mais `serial.Serial.readline` ne retourne jamais `PONG` → `init()` retourne `None`, port fermé.
  - `test_init_pong_received` : `readline` retourne `b"PONG\n"` au premier essai → `init()` retourne un `UartBridge`.
  - `test_forward_wall_writes_correct_line` : `forward_move(("mur", {"orientation": "h", "row": 2, "col": 3}))` → écrit `b"WALL H 2 3\n"` sur le serial.
  - `test_forward_wall_uppercase_v` : `orientation="v"` → écrit `WALL V ...`.
  - `test_forward_pawn_noop` : `forward_move(("deplacement", {"target": [4, 2]}))` → aucun appel à `serial.write`.
  - `test_forward_handles_serial_exception` : `serial.write` lève → `available` passe à `False`, pas d'exception propagée.
- `tests/webapp/test_service.py` reste valide : il mocke `UartBridge` au niveau de l'interface `forward_move`/`available` qui ne change pas.

## 7. Gestion d'erreurs et cas limites

### 7.1 Détection au boot

- Si aucun port série détecté → `init()` retourne `None`, mode autonome forcé. La webapp démarre normalement.
- Si port trouvé mais pas de `PONG` après 5 s → `init()` retourne `None`, mode autonome. Log explicite.
- Si `PONG` reçu → bridge actif, l'utilisateur peut activer le toggle "mode plateau" dans l'UI.

### 7.2 Panne UART en cours de partie

Le contrat existant est préservé : si `serial.write` lève (port débranché), `available` passe à `False`, et `_forward_to_plateau_unlocked` ([`webapp/service.py:336-340`](../../../webapp/service.py#L336-L340)) détecte le changement et écrit dans `_last_error` :

```python
self._last_error = {
    "code": "PLATEAU_LOST",
    "message": "Plateau déconnecté, partie en mode app.",
}
```

L'UI affiche ce message. Pas de tentative de reconnexion automatique.

### 7.3 ESP32 sans HOME valide

Si le HOME automatique du firmware échoue au boot (capteur défectueux, blocage mécanique), `position_connue = false`. Toute commande `WALL` héritera du refus de `goto_xy` ([`bringup_l298n_complet.cpp:521-524`](../../../firmware/src/bringup_l298n_complet.cpp#L521-L524)) qui imprime `GOTO refuse : HOME requis.`. Côté Python : aucune action visible, l'UI continue normalement.

**Détection manuelle** : l'opérateur surveille la console série (PlatformIO monitor) au démarrage. Si HOME échoue, relancer manuellement via `HOME` en série, ou redémarrer l'ESP32.

### 7.4 Mur hors matrice (les 42/60 non mesurés)

Le firmware itère sur les 2 cases et n'agit que sur celles mesurées. `WALL OK ... raised=0` est loggué sur Serial. La webapp ne sait pas et continue normalement.

### 7.5 Bornes invalides

Côté Python, aucun cas attendu : `place_wall` filtre avant l'envoi UART. Côté firmware, la vérif `row, col ∈ [0..4]` AVANT le mapping évite un crash d'indexation (`j = 4 - 5 = -1`).

### 7.6 Quitter une partie pendant l'exécution physique

Si l'utilisateur quitte alors que le chariot est en train d'exécuter une commande `WALL`, le firmware finit la commande en cours puis attend la suivante. Aucune commande supplémentaire n'arrive. Pas de race condition.

### 7.7 Multi-clients simultanés

`forward_move` est appelé depuis l'intérieur du `_lock` de `QuoridorService`. Donc un seul thread Python à la fois écrit dans le port série, même avec plusieurs navigateurs connectés.

## 8. Tests

### 8.1 Tests automatisés (côté Python, pas de hardware)

Cf. §6.3. Tous les tests touchent `webapp/uart_bridge.py` via mock de `serial.Serial`. Aucun test n'instancie de vrai port série. Exécutés via `pytest tests/webapp/`.

### 8.2 Validation manuelle (smoke test du démo)

Pré-requis : ESP32 branché en USB au Mac, firmware mis à jour (avec `PING` et `WALL`).

**Ordre des opérations important** : brancher l'ESP32 d'abord, attendre que le HOME soit terminé (~10-20 s, visible sur la console série), puis lancer la webapp. Si la webapp démarre pendant le HOME, le PING timeout à 5 s et le mode autonome sera forcé. Ce n'est pas un crash, juste un mode dégradé.

| # | Action | Résultat attendu |
|---|---|---|
| 1 | Brancher USB | `/dev/cu.usbserial-*` apparaît côté Mac |
| 2 | Surveiller la console série de l'ESP32 (`pio device monitor`) | Voir le boot : banner, puis `HOME OK. Origine (0, 0) etablie.` Attendre cette ligne avant de continuer. |
| 3 | Lancer la webapp (`python -m webapp.server` ou équivalent port 8001) | Log Python : `UartBridge: connecte sur /dev/cu.usbserial-*` |
| 4 | Ouvrir webapp depuis téléphone (`http://<ip-mac>:<port>`) | UI charge, toggle "mode plateau" disponible |
| 5 | Activer mode plateau dans l'UI | État `plateau.connected = true` |
| 6 | Nouvelle partie + poser mur `(h, 0, 0)` | Console firmware : `WALL OK H 0 0 raised=1`. Chariot va à `(109, 777)`, lève + baisse. |
| 7 | Poser mur `(h, 1, 2)` | Console firmware : `WALL OK H 1 2 raised=0`. Aucun mouvement. Jeu continue. |
| 8 | Poser mur `(v, 0, 0)` | Console firmware : `WALL OK V 0 0 raised=1`. Chariot va à `(34, 707)`. |
| 9 | Laisser l'IA jouer plusieurs murs | Chaque mur IA déclenche la séquence physique correspondante (avec retard de quelques secondes acceptable côté plateau) |
| 10 | Pion IA bouge | **Aucune commande sur Serial**, aucun mouvement physique |
| 11 | Débrancher USB en cours de partie | UI affiche `PLATEAU_LOST`, jeu continue en pur autonome |
| 12 | Toggle "mode plateau" OFF | Les murs suivants ne sont plus envoyés à l'ESP32 (vérifiable sur console série : plus de lignes `WALL ...`) |

### 8.3 Tests non couverts (volontairement)

- Pas de test de stress IA vs IA en mode "rapide" (saturation potentielle du buffer série, hors scope démo).
- Pas de test de reconnexion après débranchement.
- Pas de test de l'effet mécanique réel sur le plateau (validation visuelle uniquement).

## 9. Critères d'acceptation

Le démo est validé si **tous** les critères ci-dessous sont satisfaits :

- ✅ Au boot avec ESP32 branché, la webapp affiche `plateau.available = true` et `plateau.connected = true` après activation du toggle.
- ✅ Au moins 3 murs Quoridor distincts (à différentes positions) posés depuis le téléphone déclenchent une animation physique sur le plateau.
- ✅ Le moteur Quoridor et l'IA tournent normalement sans freeze, sans latence visible côté UI, même quand le plateau physique est en retard.
- ✅ Aucun crash firmware ni Python pendant 5 minutes d'un match humain vs IA avec mode plateau actif.
- ✅ Débrancher l'USB en cours de partie ne crashe rien côté Python et l'UI passe en mode autonome avec message `PLATEAU_LOST`.
- ✅ Les déplacements de pions (humain et IA) ne génèrent **aucun** trafic UART.

## 10. Hors scope explicite

- Indicateur UI "ce mur est physiquement levable" (à ajouter plus tard si désiré).
- Animation de pions physique.
- Retour ACK consommé côté Python (les logs firmware restent humains-only).
- Reconnexion automatique après débranchement.
- File d'attente Python custom (on s'appuie sur le buffer série natif).
- Migration vers le protocole "Plan 2" structuré.
- Refonte du firmware pour les pions/boutons/LEDs.

## 11. Limitations connues du démo

À mentionner à l'opérateur du démo et/ou à documenter dans le README :

- **Ne pas couper l'alimentation ESP32 en cours de partie** : provoque un reboot avec re-HOME automatique, pendant lequel les commandes `WALL` envoyées par la webapp sont perdues sans alerte côté Python.
- **Si HOME échoue au boot** (capteur défectueux, blocage mécanique) : pas de notification UI. À surveiller via la console série PlatformIO.
- **Désynchronisation logique / physique** : un mur perdu côté UART (rare, mais possible en cas de saturation extrême) reste visible côté UI mais pas physique. Pas de mécanisme de réconciliation.
- **Tous les murs levables sont "partiels"** (1 case sur 2) avec la matrice 18/60 actuelle. Pour des murs complets, mesurer 2-3 cases supplémentaires.
- **Ordre de démarrage strict** : brancher l'ESP32 et attendre la fin du HOME *avant* de lancer la webapp. Si la webapp démarre pendant le HOME, le PING timeout à 5 s et la webapp passe en mode autonome (réversible : il faut redémarrer la webapp après HOME terminé).

## 12. Annexes

### 12.1 Points à vérifier en début d'implémentation

- ✅ `pyserial 3.5` installé sur le Mac (vérifié 2026-05-20).
- ✅ pyserial installé sur le RPi (mentionné dans `webapp/README.md`).
- ✅ Convention de payload `forward_move` confirmée : dict avec `orientation` (str minuscule), `row` (int), `col` (int).
- ⚠️ Vérifier que les tests existants `tests/webapp/test_uart_bridge.py` peuvent être réécrits sans casser les autres tests (`test_service.py`, `test_api.py`).

### 12.2 Estimation de la latence physique

- GOTO max : 700 pas × 2 axes × 10000 µs/pas = ~14 s pire cas. Typique : 3-5 s.
- LEVER + 400 ms + BAISSER + 400 ms = ~1 s.
- Total par case : 4-6 s. Par mur (2 cases) : 8-12 s.
- Tolérance acceptable pour un démo où la webapp continue son rythme normal et le plateau rattrape avec retard.

### 12.3 Références

- [`firmware/src/bringup_l298n_complet.cpp`](../../../firmware/src/bringup_l298n_complet.cpp) — sketch de production actuel.
- [`quoridor_engine/core.py`](../../../quoridor_engine/core.py) — moteur Quoridor (convention murs).
- [`webapp/service.py`](../../../webapp/service.py) — service principal de la webapp.
- [`webapp/uart_bridge.py`](../../../webapp/uart_bridge.py) — fichier à refondre.
- [`docs/superpowers/specs/2026-05-20-bringup-breadboard-validation.md`](2026-05-20-bringup-breadboard-validation.md) — validation bring-up précédent.
- [`docs/superpowers/specs/2026-05-18-webapp-demo-quoridor-design.md`](2026-05-18-webapp-demo-quoridor-design.md) — spec webapp originelle.
