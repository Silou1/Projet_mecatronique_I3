# Phase 5 — Transport Wi-Fi Mac ↔ ESP32 — Design

| | |
|---|---|
| **Date** | 2026-05-20 |
| **Statut** | Validé par l'utilisateur, prêt pour implémentation |
| **Échéance** | Démo finale vendredi 2026-05-22 (J-2) |
| **Phase** | 5 — transport Wi-Fi (principal) + USB-série (fallback) |
| **Hors scope** | LEDs RGB (phase 5b), WALL physique avec plateau, lancement sans terminal (phase 6) |

## Objectif

Permettre à la webapp FastAPI (Mac) et au sketch ESP32 de communiquer via Wi-Fi en mode AP,
en gardant le canal USB-série actif en parallèle pour debug et fallback démo. Le protocole
applicatif texte (`PING`/`PONG`, `WALL <H|V> <r> <c>`, `OK`/`ERR`) reste **strictement
identique** sur les deux transports.

## Critères de succès

À la fin de l'implémentation :

1. **`pytest -m "not devkit"`** vert (Niveau 1, sans hardware).
2. **`pytest -m devkit_serial`** vert (Niveau 2, USB-série, ESP32 branché).
3. **`pytest -m devkit_wifi`** vert au moins une fois manuellement (Niveau 2, Wi-Fi,
   ESP32 en mode AP, Mac basculé sur `Quoridor-ESP32`).
4. La webapp démarre avec `QUORIDOR_TRANSPORT=wifi python -m webapp.server` et le panneau
   Statut affiche "Mac ↔ ESP32 · WiFi · 192.168.4.1:3333 · dernier PONG il y a < 10 s".
5. Si l'ESP32 n'est pas joignable au démarrage, la webapp **démarre quand même** en mode
   dégradé avec une bannière persistante et un bouton "Réessayer en USB".

## 1. Architecture globale

```
┌─────────────────────────────────────────────────────────────────────┐
│ Mac (Python 3.12)                                                   │
│                                                                     │
│  ┌────────────────┐  ┌──────────────────────────────────────────┐   │
│  │ quoridor_engine│  │ webapp/                                  │   │
│  │  (moteur + IA) │◄─┤  ┌────────────────────────────────────┐  │   │
│  └────────────────┘  │  │ Transport (interface abstraite)    │  │   │
│                      │  │  ├── SerialTransport (refactor)    │  │   │
│                      │  │  ├── WiFiTransport (nouveau)       │  │   │
│                      │  │  └── NullTransport (autonome)      │  │   │
│                      │  │ Factory : env QUORIDOR_TRANSPORT   │  │   │
│                      │  └────────────────────────────────────┘  │   │
│                      │                                          │   │
│                      │  Heartbeat asyncio : PING toutes les 5s  │   │
│                      │  Lock asyncio sur le transport (sérial.) │   │
│                      │  Reconnexion auto si coupure détectée    │   │
│                      │                                          │   │
│                      │  Endpoints :                             │   │
│                      │    GET /api/status                       │   │
│                      │    POST /api/transport/switch            │   │
│                      └──────────────────────────────────────────┘   │
│                                              ▲              ▲       │
└──────────────────────────────────────────────┼──────────────┼───────┘
                                  TCP (Wi-Fi)  │              │ USB-série
                                               │              │ (115200)
                            192.168.4.1:3333   │              │
                                               ▼              ▼
                            ┌─────────────────────────────────────────┐
                            │ ESP32-WROOM                             │
                            │ bringup_l298n_complet.cpp (étendu)      │
                            │                                         │
                            │  - WiFi.softAP("Quoridor-ESP32", pwd)   │
                            │  - WiFiServer sur port 3333             │
                            │  - Politique "dernier client gagne"     │
                            │  - Watchdog client : drop si 30 s muet  │
                            │  - Parser texte EXISTANT réutilisé      │
                            │    (Stream* polymorphisme)              │
                            │  - Serial.* reste actif en parallèle    │
                            │                                         │
                            │  (LEDs RGB reportées phase 5b)          │
                            └─────────────────────────────────────────┘
```

### Points clés

- **Pas de refonte du sketch** : on étend `bringup_l298n_complet.cpp`, on ne le refait pas.
- **Les deux canaux coexistent** : USB-série actif en parallèle du Wi-Fi côté firmware.
- **Mac arbitre** : un seul transport actif côté webapp (`QUORIDOR_TRANSPORT=wifi|serial|none`).
- **Aucun changement** côté `quoridor_engine/`. Frontend HTML/JS étendu pour le panneau Statut.

## 2. Couche firmware (ESP32)

### 2.1 Démarrage Wi-Fi AP au boot

Dans `setup()`, après l'init Serial :

```cpp
WiFi.softAP("Quoridor-ESP32", "quoridor2026");  // SSID, WPA2 12 char
// IP par défaut : 192.168.4.1
server.begin();  // WiFiServer sur port 3333
```

### 2.2 Gestion du client TCP dans `loop()`

```cpp
static WiFiClient client;
static unsigned long last_rx_from_client = 0;

void loop() {
    // 1. Politique "dernier client gagne"
    if (server.hasClient()) {
        if (client && client.connected()) {
            client.stop();
        }
        client = server.available();
        last_rx_from_client = millis();
    }

    // 2. Lecture USB-série (canal existant, inchangé)
    if (Serial.available()) {
        String cmd = Serial.readStringUntil('\n');
        handle_command(cmd, &Serial);
    }

    // 3. Lecture client TCP (nouveau)
    if (client && client.connected() && client.available()) {
        String cmd = client.readStringUntil('\n');
        last_rx_from_client = millis();
        handle_command(cmd, &client);
    }

    // 4. Watchdog : drop client si 30 s sans trafic
    if (client && client.connected() && (millis() - last_rx_from_client > 30000)) {
        client.stop();
    }

    // 5. Reste de la loop existante (CoreXY, etc.)
}
```

### 2.3 Refactor `handle_command` pour `Stream*`

```cpp
void handle_command(String cmd, Stream* reply) {
    cmd.trim();
    if (cmd == "PING") {
        reply->println("PONG");
    } else if (cmd.startsWith("WALL ")) {
        // ... logique identique, reply->println au lieu de Serial.println
    }
    // ...
}
```

`Stream*` est la classe de base Arduino dont héritent `HardwareSerial` et `WiFiClient`.
**Une seule fonction `handle_command` gère les deux canaux sans duplication de code.**

### 2.4 Comportement attendu en cas de coupure

| Événement | Comportement |
|---|---|
| Mac ferme proprement la connexion | `client.connected()` repasse à `false`, attente nouveau client |
| Mac perd Wi-Fi brusquement | Détecté par `client.connected()` ou échec `client.println()` |
| Mac se reconnecte | Politique "dernier gagne" : ancien client `stop()`, nouveau prend la place |
| Mac coupé brutalement, ESP32 alim externe | ESP32 survit, watchdog 30 s libère le socket fantôme |
| Mac coupé brutalement, ESP32 alim USB-Mac | ESP32 s'éteint aussi, reboot propre quand Mac revient |
| Aucun client connecté | USB-série reste actif en parallèle |

### 2.5 Ce qui ne change pas dans le sketch

- Logique CoreXY, servo, capteurs fins de course → strictement inchangée
- Matrices `MURS_H` / `MURS_V` → inchangées
- Calibration pas ↔ mm → inchangée
- Pinout moteurs / servo / capteurs → inchangé

### 2.6 Dépendance firmware

`WiFi.h` (intégrée au framework Arduino ESP32, **aucune dépendance externe à ajouter**).

## 3. Couche Python : abstraction `Transport`

### 3.1 Interface abstraite

Nouveau fichier `webapp/transport.py` :

```python
from abc import ABC, abstractmethod

class Transport(ABC):
    """Canal bidirectionnel ligne par ligne vers l'ESP32."""

    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def write_line(self, line: str) -> None:
        """Envoie une ligne (le \\n est ajouté). Encodage UTF-8."""

    @abstractmethod
    def read_line(self, timeout: float = 1.0) -> str | None:
        """Lit une ligne (sans \\n). Retourne None si timeout."""

    @abstractmethod
    def close(self) -> None: ...

    @property
    @abstractmethod
    def is_alive(self) -> bool: ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Pour le panneau Statut. Ex: 'wifi 192.168.4.1:3333'."""


class TransportError(Exception):
    """Erreur de transport (connexion impossible, coupure, etc.)."""
```

### 3.2 Trois implémentations

| Classe | Rôle | Origine |
|---|---|---|
| `SerialTransport` | USB-série, détection auto `/dev/tty.usbserial-*` | refactor de `uart_bridge.py`, comportement applicatif inchangé |
| `WiFiTransport` | TCP vers `192.168.4.1:3333`, buffer interne ligne par ligne | nouveau |
| `NullTransport` | Mode autonome explicite, `is_alive = False` | nouveau |

### 3.3 `WiFiTransport` — buffer interne pour les lignes

`socket.recv()` retourne des chunks de bytes. Le `WiFiTransport` maintient un `bytearray`
interne, accumule les chunks et coupe sur `\n` :

```python
def read_line(self, timeout: float = 1.0) -> str | None:
    while b'\n' not in self._rx_buffer:
        self._sock.settimeout(timeout)
        try:
            chunk = self._sock.recv(256)
        except socket.timeout:
            return None
        if not chunk:
            return None
        self._rx_buffer.extend(chunk)
    line, _, rest = self._rx_buffer.partition(b'\n')
    self._rx_buffer = bytearray(rest)
    return line.decode('utf-8').rstrip('\r')
```

### 3.4 Factory pilotée par env var

```python
def make_transport() -> Transport:
    kind = os.environ.get("QUORIDOR_TRANSPORT", "wifi").lower()
    if kind == "wifi":   return WiFiTransport()
    elif kind == "serial": return SerialTransport()
    elif kind == "none": return NullTransport()
    else:
        raise ValueError(f"QUORIDOR_TRANSPORT invalide : {kind}")
```

**Défaut : `wifi`** (cible démo).

### 3.5 Lock asyncio sur le transport (critique)

Le heartbeat et les commandes (`WALL`, `HOME`, etc.) partagent la même connexion.
**Toute paire (write, attendre réponse) doit être sérialisée par un `asyncio.Lock`** :

```python
async with self._tx_lock:
    self.transport.write_line(cmd)
    response = await asyncio.to_thread(self.transport.read_line, timeout=timeout_for(cmd))
```

Sans ce lock, race conditions garanties (entrelacement de bytes sur le fil).

### 3.6 Timeouts différenciés par commande

| Commande | Timeout |
|---|---|
| `PING` | 2 s |
| `HOME` | 30 s |
| `GOTO` | 15 s |
| `WALL` | 20 s |
| Autres | 5 s par défaut |

### 3.7 Fallback gracieux au démarrage

Dans `webapp/service.py`, le `QuoridorService` essaie `transport.open()`. Si échec :

- Log : `[transport] WiFi 192.168.4.1:3333 indisponible : timeout`
- Bascule auto sur `NullTransport`
- Mémorise `startup_error: str`
- Panneau Statut + bannière webapp affichent l'erreur
- **La webapp démarre toujours, jamais ne plante.**

### 3.8 Heartbeat applicatif + reconnexion auto

Tâche asyncio lancée au démarrage :

- Toutes les 5 s, si `transport.is_alive` → envoie `PING`, attend `PONG` (timeout 2 s)
- 2 PONG ratés consécutifs (10 s) → marque transport perdu, déclenche reconnexion auto
- Reconnexion : tâche asyncio séparée, tente `transport.open()` toutes les 10 s en arrière-plan
- **Mécanisme identique** au démarrage et en cours de session

### 3.9 Encoding

UTF-8 explicite partout (`.encode('utf-8')`, `.decode('utf-8')`). Pas de défaut implicite.

### 3.10 Risque à respecter à l'implémentation

`pyserial` et `socket` sont bloquants par défaut. Toute lecture doit être enveloppée dans
`asyncio.to_thread()` pour ne pas bloquer la boucle FastAPI.

## 4. Panneau Statut Plateau + bannière dégradée

### 4.1 Endpoint `GET /api/status`

Réponse JSON :

```json
{
  "client": {
    "polling_active": true,
    "polling_interval_ms": 500
  },
  "transport": {
    "kind": "wifi",
    "description": "wifi 192.168.4.1:3333",
    "alive": true,
    "last_pong_at_iso": "2026-05-20T20:34:12+02:00",
    "last_pong_age_seconds": 3,
    "latency_avg_ms": 12,
    "startup_error": null
  },
  "plateau": {
    "homed": true,
    "ready": true
  }
}
```

- **Lecture seule**, renvoyé en < 5 ms (compteurs en mémoire, pas d'aller-retour ESP32).
- Si `transport.kind == "none"` → `description: "none (mode autonome)"` + `startup_error` explicite.

### 4.2 Endpoint `POST /api/transport/switch`

Body : `{"kind": "serial" | "wifi"}`. Bascule de transport sans redémarrer la webapp.

- **Acquiert le `asyncio.Lock`** du transport avant toute opération → attend la fin d'une
  commande en cours (`WALL`, `HOME`, etc.) avant de basculer. Aucune commande à moitié
  exécutée.
- Sous lock : ferme l'ancien transport (`close()`), crée le nouveau, tente `open()`,
  remplace la référence dans le service.
- Si `open()` échoue → bascule en `NullTransport`, met à jour `startup_error`, retourne
  l'erreur au frontend. La webapp reste vivante.
- Si succès → bannière disparaît au prochain polling `/api/status`, panneau Statut passe
  en vert.
- **Réinitialise** les compteurs heartbeat (`last_pong_at`, `latency_avg_ms`,
  `_failed_pings`) après bascule, pour ne pas afficher un statut hérité du transport
  précédent.

### 4.3 Composant Statut (frontend)

Accessible via le menu trois points existant.

```
┌─ Statut Plateau ─────────────────────────────────┐
│                                                  │
│ Navigateur ↔ Mac                                 │
│   ● Connecté · polling actif (500 ms)            │
│                                                  │
│ Mac ↔ ESP32                                      │
│   ● Connecté · WiFi · 192.168.4.1:3333           │
│   Dernier PONG : il y a 3 s                      │
│   Latence moyenne : 12 ms                        │
│                                                  │
│ Plateau                                          │
│   ● Prêt · homing effectué                       │
│                                                  │
└──────────────────────────────────────────────────┘
```

- **Polling permanent** : `GET /api/status` toutes les 2 s, **même quand le panneau n'est
  pas ouvert**, pour que la bannière dégradée (section 4.4) reste à jour. La requête est
  locale (`localhost:8000`) et négligeable en charge.
- **Code couleur** :
  - Vert : `alive && last_pong_age_seconds < 10`
  - Orange : `alive && last_pong_age_seconds >= 10`
  - Rouge : `!alive`

### 4.4 Bannière persistante (mode dégradé)

Affichée en haut de la webapp **sur toutes les pages** si `startup_error != null` OU `!alive` :

```
┌──────────────────────────────────────────────────────────────────┐
│ ⚠ Plateau injoignable                                            │
│ Vérifie le branchement USB-C entre l'ESP32 et le Mac.            │
│                                                                  │
│   [ Réessayer en USB ]    [ Réessayer en Wi-Fi ]                 │
└──────────────────────────────────────────────────────────────────┘
```

Les deux boutons appellent `POST /api/transport/switch`. **Aucune autre action utilisateur**
disponible sur le panneau Statut (pas de menu d'actions complet, pour limiter les chemins
de bug).

### 4.5 Fichiers impactés

- `webapp/server.py` : routes `GET /api/status`, `POST /api/transport/switch`
- `webapp/service.py` : compteurs heartbeat (`last_pong_at`, `latency_avg_ms`, `startup_error`),
  tâche heartbeat, tâche reconnexion auto, méthode `switch_transport(kind)`
- `webapp/schemas.py` : `StatusResponse`, `TransportSwitchRequest`, `TransportSwitchResponse`
- `webapp/transport.py` : nouveau (interface + 3 impls + factory)
- `webapp/uart_bridge.py` : **supprimé** après migration ; tout le code série passe dans
  `SerialTransport` (dans `transport.py`). Tous les imports de `uart_bridge` doivent être
  mis à jour vers `webapp.transport`.
- `webapp/static/` : HTML/CSS/JS pour bouton menu + panneau modal + bannière

## 5. Stratégie de tests

### 5.1 Niveau 1 — pytest unitaires (sans hardware)

| Fichier | Couverture |
|---|---|
| `tests/test_transport_abstract.py` | Interface, instantiation `NullTransport`, factory env vars |
| `tests/test_transport_wifi.py` | `WiFiTransport` contre faux serveur socket local (`127.0.0.1`) |
| `tests/test_transport_serial.py` | `SerialTransport` avec `unittest.mock.MagicMock` sur `serial.Serial` |
| `tests/test_service_heartbeat.py` | Heartbeat asyncio avec `Transport` mocké, scénarios coupure/reconnexion |
| `tests/test_api_status.py` | Endpoint `GET /api/status`, schéma, codes couleur |
| `tests/test_api_transport_switch.py` | Endpoint `POST /api/transport/switch`, succès et échec |

Tournent en CI / `pytest` direct, **zéro hardware**.

### 5.2 Niveau 2 — tests devkit (ESP32 branché)

Markers :

```bash
pytest -m devkit               # tout devkit (USB + Wi-Fi)
pytest -m devkit_serial        # USB seulement
pytest -m devkit_wifi          # Wi-Fi seulement (bascule réseau auto)
```

Tests :

| Fichier | Vérifie |
|---|---|
| `tests/devkit/test_handshake_serial.py` | `PING` → `PONG` via USB |
| `tests/devkit/test_handshake_wifi.py` | `PING` → `PONG` via Wi-Fi (avec fixture `wifi_fixture`) |
| `tests/devkit/test_last_client_wins.py` | Politique firmware "dernier client gagne" (Wi-Fi) |
| `tests/devkit/test_serial_and_wifi_coexist.py` | USB et Wi-Fi simultanément (régression) |
| `tests/devkit/test_wall_parser.py` | `WALL Z 9 9` → `ERR` (parser, sans plateau) |

### 5.3 Fixture `wifi_fixture` + outil `tools/wifi_switch.py`

`tools/wifi_switch.py` : CLI standalone wrappant `networksetup` :

```bash
python tools/wifi_switch.py to-esp32      # bascule sur Quoridor-ESP32
python tools/wifi_switch.py restore       # restaure le SSID précédent
python tools/wifi_switch.py status        # affiche le SSID courant
```

Sauvegarde le SSID précédent dans `/tmp/quoridor_previous_ssid`. Détecte dynamiquement le
nom de l'interface Wi-Fi via `networksetup -listallhardwareports` (ne pas hardcoder `en0`).

`wifi_fixture` (pytest) : utilise ce helper. `yield` après bascule, restaure dans le
finalizer même si le test plante.

### 5.4 Risques connus `networksetup`

1. **Premier passage GUI** : la première fois, macOS peut afficher un dialog
   "Voulez-vous rejoindre ce réseau ?". À partir de la 2e fois → silencieux. Workaround :
   faire la première bascule manuellement avant la batterie de tests.
2. **Permissions** : Réglages → Confidentialité → "Réseau". À documenter si bloque.
3. **Nom interface** : `en0` par défaut, mais détecté dynamiquement.

### 5.5 Niveau 3 — intégration plateau (hors scope cette session)

Validation manuelle avec hardware complet :

1. Plateau monté + alimenté.
2. `WALL H 3 4` via Wi-Fi → vérification visuelle.
3. `HOME` → homing OK.
4. Stress test : 20 `WALL` consécutifs sur positions différentes.

**Reporté à la session où le plateau est dispo.**

### 5.6 Couverture minimum attendue fin de session

- `pytest -m "not devkit"` vert
- `pytest -m devkit_serial` vert
- `pytest -m devkit_wifi` vert au moins une fois manuellement

## 6. Paramètres concrets

| Paramètre | Valeur |
|---|---|
| SSID AP ESP32 | `Quoridor-ESP32` |
| Mot de passe AP | `quoridor2026` (WPA2, 12 char) |
| IP ESP32 (AP) | `192.168.4.1` |
| Port TCP | `3333` |
| Baudrate USB-série | `115200` |
| Encoding | UTF-8 |
| Intervalle heartbeat | 5 s |
| Timeout PONG | 2 s |
| Échec heartbeat → coupure | 2 PONG ratés consécutifs (10 s) |
| Intervalle reconnexion auto | 10 s |
| Watchdog firmware (drop client muet) | 30 s |
| Polling frontend `/api/status` | 2 s |
| Variable env défaut | `QUORIDOR_TRANSPORT=wifi` |
| Port ESP32 attendu (USB) | `/dev/tty.usbserial-110` (détecté dynamiquement) |

## 7. Risques connus à valider à l'implémentation

1. **Boucle bloquante côté firmware** : si `bringup_l298n_complet.cpp` contient des
   `delay()` longs (typique séquences moteur), le `WiFiServer.accept()` peut être affamé.
   À vérifier en lisant le sketch avant d'écrire la couche Wi-Fi. Si bloquant → introduire
   un découpage non-bloquant ou un `yield()` coopératif.

2. **`WALL` sans plateau** : comportement du sketch quand les capteurs ne répondent pas.
   À tester en USB d'abord pour décider : (a) accepter que `WALL` n'aboutisse pas sans
   plateau, (b) ajouter un flag de compilation `DRY_RUN_WALLS` qui répond OK immédiatement.
   Décision à prendre à l'implémentation.

3. **macOS `networksetup` permissions et premier passage GUI** : détaillés section 5.4.

4. **GPIO disponibles pour les LEDs (phase 5b)** : à confirmer avec `docs/hardware/pinout.md`
   quand on attaquera la couche LED — ne pas marcher sur les GPIO moteurs/servo/capteurs.

## 8. Hors scope explicite phase 5

- **LEDs RGB** (bande adressable 36 unités, serpentin sur plateau) → phase 5b dès que le
  matériel est dispo. Vision future : afficher position pions (bleu), cases disponibles
  (vert), pion adversaire (rouge), animations connexion. Réserver 2-4 indices LED pour
  indicateurs système (AP actif, client TCP, reconnexion, erreur).
- **Test `WALL` bout-en-bout physique** → quand plateau dispo.
- **Lancement webapp sans terminal** (script `.command`, app native, alias bureau) → phase 6
  post-démo.
- **Authentification ou TLS sur Wi-Fi** → non requis, WPA2 suffit.
- **Multi-client TCP simultané** → non requis, politique "dernier gagne" simplifie le firmware.

## 9. Dépendances ajoutées

- **Python** : aucune. Tout est en stdlib (`socket`, `asyncio`, `os`) ou déjà présent
  (`pyserial`, `fastapi`, `pydantic`).
- **Firmware** : aucune. `WiFi.h` est intégré au framework Arduino ESP32.

## 10. Recommandation pratique pour la démo vendredi

**Alimenter l'ESP32 en externe (alim 12 V via régulateur ou DC-DC)** plutôt que par
l'USB Mac. Si l'USB est débranché accidentellement pendant la démo, l'ESP32 continue de
tourner et le système se recouvre via la politique "dernier client gagne" + reconnexion
auto. Décision d'organisation, pas de code, mais à respecter le jour J.
