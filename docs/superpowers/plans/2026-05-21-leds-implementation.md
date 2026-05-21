# Sous-système LED — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implémenter le sous-système LED 36×WS2812B sur plateau Quoridor, intelligence côté Python (Mac), firmware bête sur ESP32, déclenché à chaque mutation de `GameState` via 4 nouvelles commandes texte (`LED`/`LEDSHOW`/`LEDCLEAR`/`LEDBRIGHT`).

**Architecture:** Firmware Arduino C++ étend `bringup_l298n_complet.cpp` avec lib `Adafruit_NeoPixel` sur GPIO 15. Côté Mac, nouveau module `webapp/leds.py` (mapping engine↔strip pur + classe `LedRenderer` avec diff). Hook dans `QuoridorService` après chaque mutation. Diff côté Python pour minimiser le trafic Wi-Fi. Spec validée : [`docs/superpowers/specs/2026-05-21-leds-design.md`](../specs/2026-05-21-leds-design.md).

**Tech Stack:** Python 3.12 + pytest, Arduino C++ + PlatformIO, lib `adafruit/Adafruit NeoPixel`, GPIO 15 sortie digitale.

---

## File Structure

**Files to create:**
- `webapp/leds.py` — module mapping + rendu + renderer (200-250 lignes)
- `tests/test_leds.py` — tests unitaires Python pur
- `tests/devkit/test_leds_serial.py` — test devkit USB du protocole
- `tools/led_test.py` — outil CLI pour bring-up hardware (script Python qui envoie des séquences via Serial)

**Files to modify:**
- `firmware/platformio.ini` — ajout dépendance `adafruit/Adafruit NeoPixel`
- `firmware/src/bringup_l298n_complet.cpp` — init strip + 4 commandes dans `traiter()`
- `webapp/service.py` — instanciation `LedRenderer` + appels `update()` à 4 endroits
- `docs/02_architecture.md` — ajout module `webapp/leds.py` dans le tableau
- `docs/06_firmware.md` — ajout GPIO 15 + commandes LED + lib
- `docs/07_protocole.md` — nouvelle section "Commandes LED"
- `docs/hardware/pinout.md` — ajout GPIO 15

**Pas de fichiers temporaires** : tout le bring-up hardware se fait via le sketch de production + commandes texte au moniteur série ou via l'outil `tools/led_test.py`.

---

## Conventions du projet à respecter

- **Python** : 4 espaces, type hints partout, max 100 char/ligne, français pour commentaires/docstrings.
- **C++ Arduino** : pattern existant du sketch monolithique, pas de split `.h/.cpp`.
- **Tests** : pytest, fichiers `tests/test_*.py` sans hardware, `tests/devkit/test_*.py` avec marker `devkit_serial` ou `devkit_wifi`.
- **Git** : commits locaux phase par phase, push vers `origin/main` après validation utilisateur.

---

## Tâche 1 — Ajout de la lib Adafruit NeoPixel dans PlatformIO

**Files:**
- Modify: `firmware/platformio.ini`

- [ ] **Step 1 : Lire l'état actuel de `platformio.ini`**

Run: `cat firmware/platformio.ini`
Expected: voir les environnements existants (`bringup_l298n_complet`, etc.) et la section `lib_deps` actuelle.

- [ ] **Step 2 : Ajouter la dépendance Adafruit NeoPixel**

Dans la section `lib_deps` de l'environnement de production (probablement `[env:bringup_l298n_complet]`), ajouter une ligne :

```ini
lib_deps =
    madhephaestus/ESP32Servo @ ^1.1.1
    adafruit/Adafruit NeoPixel @ ^1.12.0
```

(Garder les autres dépendances existantes, ajouter juste la ligne `adafruit/Adafruit NeoPixel`.)

- [ ] **Step 3 : Forcer le téléchargement de la lib**

Run: `cd firmware && pio pkg install`
Expected: `Adafruit NeoPixel @ 1.12.x installed` dans la sortie, sans erreur de compilation.

- [ ] **Step 4 : Vérifier que la build passe encore**

Run: `cd firmware && pio run -e bringup_l298n_complet`
Expected: `========== [SUCCESS] ==========` à la fin. Le sketch existant compile sans modification.

- [ ] **Step 5 : Commit**

```bash
git add firmware/platformio.ini
git commit -m "feat(firmware): ajout lib Adafruit_NeoPixel pour sous-systeme LED"
```

---

## Tâche 2 — Init strip et 4 commandes LED dans le sketch firmware

**Files:**
- Modify: `firmware/src/bringup_l298n_complet.cpp`

**Contexte** : le sketch est monolithique. On ajoute :
1. Include + globales en haut
2. Init dans `setup()` (avant le homing existant)
3. Dispatch des 4 commandes dans `traiter()`

- [ ] **Step 1 : Lire la structure actuelle du sketch**

Run: `grep -n "^void\|^Adafruit_\|^#include\|setup()\|traiter" firmware/src/bringup_l298n_complet.cpp | head -30`
Expected: voir les fonctions principales et leur ligne (setup, loop, traiter).

- [ ] **Step 2 : Ajouter l'include et les globales en haut du fichier**

Juste après les autres `#include` (ligne ~10-15), insérer :

```cpp
#include <Adafruit_NeoPixel.h>

// === Sous-systeme LED (WS2812B sur GPIO 15) ===
#define LED_PIN     15
#define LED_COUNT   36
Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);
```

- [ ] **Step 3 : Ajouter l'init du strip au tout début de `setup()`**

Dans la fonction `setup()`, **avant tout autre init**, insérer :

```cpp
  // Init strip LED en premier (avant tout autre periph) :
  // securise l'etat des LEDs des le boot, evite affichage residuel.
  strip.begin();
  strip.setBrightness(102);  // 40% (cf. spec : marge alim + confort visuel)
  strip.clear();
  strip.show();
```

- [ ] **Step 4 : Localiser le dispatch dans `traiter()`**

Run: `grep -n 'else if.*equalsIgnoreCase\|else if.*startsWith' firmware/src/bringup_l298n_complet.cpp | head -10`
Expected: voir les chaînes de `else if` existantes (WALL, PING, GOTO, etc.).

- [ ] **Step 5 : Ajouter le dispatch des 4 commandes LED dans `traiter()`**

À la fin de la chaîne d'`else if` (juste avant le `else` final qui retourne `ERR commande inconnue`), insérer :

```cpp
  // === Commandes LED ===
  else if (cmd.equalsIgnoreCase("LEDSHOW")) {
    strip.show();
    out->println("OK");
  }
  else if (cmd.equalsIgnoreCase("LEDCLEAR")) {
    strip.clear();
    strip.show();
    out->println("OK");
  }
  else if (cmd.startsWith("LEDBRIGHT ")) {
    int b = cmd.substring(10).toInt();
    if (b < 0 || b > 255) {
      out->println("ERR LEDBRIGHT borne : " + String(b) + " hors [0..255]");
    } else {
      strip.setBrightness(b);
      strip.show();
      out->println("OK");
    }
  }
  else if (cmd.startsWith("LED ")) {
    // Parse : LED <idx> <r> <g> <b>
    String args = cmd.substring(4);
    int s1 = args.indexOf(' ');
    int s2 = args.indexOf(' ', s1 + 1);
    int s3 = args.indexOf(' ', s2 + 1);
    if (s1 < 0 || s2 < 0 || s3 < 0) {
      out->println("ERR syntaxe : LED <idx> <r> <g> <b>");
    } else {
      int idx = args.substring(0, s1).toInt();
      int r   = args.substring(s1 + 1, s2).toInt();
      int g   = args.substring(s2 + 1, s3).toInt();
      int b   = args.substring(s3 + 1).toInt();
      if (idx < 0 || idx >= LED_COUNT) {
        out->println("ERR LED borne : idx=" + String(idx) + " hors [0..35]");
      } else if (r < 0 || r > 255 || g < 0 || g > 255 || b < 0 || b > 255) {
        out->println("ERR LED borne : composante hors [0..255]");
      } else {
        strip.setPixelColor(idx, strip.Color(r, g, b));
        out->println("OK");
      }
    }
  }
```

**Note** : `out` est le `Stream*` paramètre de `traiter()` (gère USB et Wi-Fi indifféremment). Respecter exactement le nom de variable utilisé dans le code existant — vérifier par `grep "out->\|stream->\|Stream\* " firmware/src/bringup_l298n_complet.cpp | head -5`.

- [ ] **Step 6 : Compiler le sketch**

Run: `cd firmware && pio run -e bringup_l298n_complet`
Expected: `========== [SUCCESS] ==========`. Pas d'erreur de compile.

- [ ] **Step 7 : Flasher l'ESP32 (USB-C branché)**

Run: `cd firmware && pio run -e bringup_l298n_complet -t upload`
Expected: `Writing at 0x... [100%]` puis `Hard resetting via RTS pin...`. Pas d'erreur de flash.

- [ ] **Step 8 : Vérifier au moniteur série que le sketch boot sans crash**

Run: `cd firmware && pio device monitor -b 115200`
Expected dans les premières lignes après le reset :
```
=== Integration L298N : CoreXY + capteurs + servo ===
HOME OK. Origine (0, 0) etablie.
```
(Pas de stack trace ESP32, pas de boot loop.)

Quitter le moniteur (Ctrl+C).

- [ ] **Step 9 : Commit**

```bash
git add firmware/src/bringup_l298n_complet.cpp
git commit -m "feat(firmware): commandes LED/LEDSHOW/LEDCLEAR/LEDBRIGHT + init strip GPIO 15"
```

---

## Tâche 3 — Bring-up hardware "Hello LED 0" via moniteur série

**Files:** aucun (test manuel)

**Prérequis hardware (à vérifier physiquement avant) :**
- GPIO 15 ESP32 → DIN du strip WS2812B (1ʳᵉ LED), avec résistance 330 Ω en série si disponible
- 5V step-down → VDD strip
- **GND step-down commun avec GND ESP32** ← piège classique
- Alim 5V step-down active

- [ ] **Step 1 : Ouvrir le moniteur série**

Run: `cd firmware && pio device monitor -b 115200`
Expected: voir l'ESP32 répondre aux commandes (taper `PING` → `PONG`).

- [ ] **Step 2 : Envoyer `LEDCLEAR` pour s'assurer que toutes les LEDs sont éteintes**

Taper dans le moniteur : `LEDCLEAR` puis Entrée.
Expected dans le moniteur : `OK`. Visuellement : toutes les LEDs éteintes.

- [ ] **Step 3 : Allumer la LED 0 en bleu**

Taper : `LED 0 0 0 255` puis Entrée.
Expected : `OK`.

Taper : `LEDSHOW` puis Entrée.
Expected : `OK`. **Visuellement : la 1ʳᵉ LED en bas-gauche du plateau s'allume en bleu.**

- [ ] **Step 4 : Si rien ne s'allume — diagnostic**

Vérifier dans cet ordre :
1. GND commun ESP32 ↔ alim 5V (multimètre : continuité)
2. Polarité 5V correcte (multimètre : 5V entre VCC strip et GND)
3. Pin DIN correctement câblée sur GPIO 15 (multimètre + visuel)
4. DIN/DOUT inversé ? Le strip a un sens, vérifier la flèche sérigraphiée
5. Si tout est OK et toujours rien : ajouter une **diode 1N4148** en série sur le rail +5V de la 1ʳᵉ LED (anode côté alim, cathode côté LED) pour faire chuter VDD à ~4.3V

- [ ] **Step 5 : Tester quelques autres LEDs manuellement**

```
LED 5 0 255 0
LEDSHOW
```
Expected : LED 5 s'allume en vert (devrait être en bas-droite).

```
LED 35 255 255 255
LEDSHOW
```
Expected : LED 35 s'allume en blanc (devrait être en haut-gauche).

Si les LEDs ne sont pas aux positions attendues → noter la divergence pour ajuster le mapping dans la Tâche 7.

- [ ] **Step 6 : Tout éteindre et quitter le moniteur**

```
LEDCLEAR
```
Expected : `OK` et toutes les LEDs éteintes.

Quitter le moniteur (Ctrl+C).

**Pas de commit** (étape de validation manuelle, rien à versionner).

---

## Tâche 4 — Outil Python `tools/led_test.py` pour bring-up automatisé

**Files:**
- Create: `tools/led_test.py`

**Objectif** : automatiser les tests serpentin et 4 coins (sans avoir à taper 36 commandes à la main).

- [ ] **Step 1 : Écrire l'outil CLI**

Créer `tools/led_test.py` :

```python
"""Outil CLI pour bring-up du strip LED WS2812B via serial.

Usage :
    python tools/led_test.py serpentin     # scan LED 0 → 35 en blanc, 150 ms chacune
    python tools/led_test.py coins         # allume 4 coins + 2 positions de depart
    python tools/led_test.py clear         # eteint toutes les LEDs
    python tools/led_test.py pixel <idx> <r> <g> <b>   # une LED precise
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import serial
from serial.tools import list_ports


def find_esp32_port() -> str:
    """Trouve le port USB de l'ESP32 (macOS : /dev/cu.usbserial-*)."""
    for port in list_ports.comports():
        if "usbserial" in port.device or "SLAB" in (port.description or ""):
            return port.device
    raise SystemExit("ESP32 introuvable sur /dev/cu.usbserial-*")


def send(ser: serial.Serial, line: str) -> str:
    """Envoie une ligne, attend la reponse (max 2 s)."""
    ser.reset_input_buffer()
    ser.write((line + "\n").encode())
    ser.flush()
    deadline = time.monotonic() + 2.0
    buf = ""
    while time.monotonic() < deadline:
        chunk = ser.read(ser.in_waiting or 1).decode(errors="replace")
        if chunk:
            buf += chunk
            if "\n" in buf:
                return buf.split("\n")[0].strip()
    return "(timeout)"


def cmd_clear(ser: serial.Serial) -> None:
    print(send(ser, "LEDCLEAR"))


def cmd_pixel(ser: serial.Serial, idx: int, r: int, g: int, b: int) -> None:
    print(send(ser, f"LED {idx} {r} {g} {b}"))
    print(send(ser, "LEDSHOW"))


def cmd_serpentin(ser: serial.Serial) -> None:
    """Allume LED 0 a 35 en blanc, 150 ms chacune. Permet de valider l'ordre du serpentin."""
    send(ser, "LEDCLEAR")
    for idx in range(36):
        send(ser, f"LED {idx} 80 80 80")  # blanc dim
        send(ser, "LEDSHOW")
        time.sleep(0.15)
        send(ser, f"LED {idx} 0 0 0")     # eteindre avant la suivante
    send(ser, "LEDSHOW")
    print("Serpentin termine.")


def cmd_coins(ser: serial.Serial) -> None:
    """Allume les 4 coins + 2 positions de depart des pions."""
    send(ser, "LEDCLEAR")
    cases = [
        (0,  255, 0,   0,   "LED 0  bas-gauche  rouge"),
        (5,  0,   255, 0,   "LED 5  bas-droite  vert"),
        (30, 255, 255, 0,   "LED 30 haut-droite jaune"),
        (35, 255, 255, 255, "LED 35 haut-gauche blanc"),
        (3,  0,   0,   255, "LED 3  bas-centre  bleu (depart J1)"),
        (32, 255, 0,   0,   "LED 32 haut-centre rouge (depart J2)"),
    ]
    for idx, r, g, b, label in cases:
        send(ser, f"LED {idx} {r} {g} {b}")
        print(label)
    send(ser, "LEDSHOW")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serpentin")
    sub.add_parser("coins")
    sub.add_parser("clear")
    p_pix = sub.add_parser("pixel")
    p_pix.add_argument("idx", type=int)
    p_pix.add_argument("r", type=int)
    p_pix.add_argument("g", type=int)
    p_pix.add_argument("b", type=int)
    args = parser.parse_args()

    port = find_esp32_port()
    print(f"Connexion a {port} ...")
    with serial.Serial(port, 115200, timeout=2) as ser:
        time.sleep(2)  # laisser l'ESP32 finir son boot
        if args.cmd == "serpentin":
            cmd_serpentin(ser)
        elif args.cmd == "coins":
            cmd_coins(ser)
        elif args.cmd == "clear":
            cmd_clear(ser)
        elif args.cmd == "pixel":
            cmd_pixel(ser, args.idx, args.r, args.g, args.b)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2 : Vérifier que l'outil tourne (avec ESP32 branché)**

Run: `python tools/led_test.py clear`
Expected:
```
Connexion a /dev/cu.usbserial-XXXX ...
OK
```
Et toutes les LEDs éteintes.

- [ ] **Step 3 : Tester le serpentin**

Run: `python tools/led_test.py serpentin`
Expected visuellement : un point blanc qui parcourt **toutes les 36 LEDs en zigzag** (rangée du bas gauche-à-droite, puis 2ᵉ rangée droite-à-gauche, etc.) en ~5 secondes.

**Validation** : si le scan se fait bien en serpentin de **bas en haut**, l'orientation hardware correspond au mapping prévu. Si le scan se fait dans l'ordre inverse (haut en bas, ou colonnes au lieu de rangées) → noter la divergence pour ajuster la formule de mapping dans la Tâche 7.

- [ ] **Step 4 : Tester les coins et positions de départ**

Run: `python tools/led_test.py coins`
Expected visuellement :
- Coin bas-gauche : rouge
- Coin bas-droite : vert
- Coin haut-droite : jaune
- Coin haut-gauche : blanc
- Bas-centre : bleu (où J1 commence)
- Haut-centre : rouge (où J2 commence)

Si **toutes les positions sont correctes** : le mapping du spec est validé sur 6 points clés. Si une position diverge → corriger soit le câblage soit la formule au moment de la Tâche 7.

- [ ] **Step 5 : Nettoyer**

Run: `python tools/led_test.py clear`

- [ ] **Step 6 : Commit**

```bash
git add tools/led_test.py
git commit -m "tools: led_test.py pour bring-up hardware (serpentin + coins)"
```

---

## Tâche 5 — Test devkit USB du protocole LED

**Files:**
- Create: `tests/devkit/test_leds_serial.py`

**Contexte** : pytest avec marker `devkit_serial`, similaire aux tests existants. Vérifie que le firmware répond correctement aux 4 commandes LED via USB.

- [ ] **Step 1 : Vérifier la structure des tests devkit existants**

Run: `ls tests/devkit/ && head -30 tests/devkit/test_*.py 2>/dev/null | head -50`
Expected: voir un conftest.py + au moins un autre test devkit pour s'inspirer du pattern (fixture serial, marker).

- [ ] **Step 2 : Écrire le test devkit**

Créer `tests/devkit/test_leds_serial.py` :

```python
"""Tests devkit USB des commandes LED.

Necessite un ESP32 branche en USB-C avec le firmware
bringup_l298n_complet.cpp flashe (incluant les commandes LED).

Marker : devkit_serial (filtre via pytest -m devkit_serial).
"""
from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.devkit_serial


def _send(serial_conn, line: str, timeout: float = 1.0) -> str:
    """Envoie une ligne et lit la premiere reponse."""
    serial_conn.reset_input_buffer()
    serial_conn.write((line + "\n").encode())
    serial_conn.flush()
    deadline = time.monotonic() + timeout
    buf = ""
    while time.monotonic() < deadline:
        chunk = serial_conn.read(serial_conn.in_waiting or 1).decode(errors="replace")
        if chunk:
            buf += chunk
            if "\n" in buf:
                return buf.split("\n")[0].strip()
    return ""


def test_led_set_pixel_valide(serial_conn):
    """LED <idx> <r> <g> <b> avec valeurs valides retourne OK."""
    resp = _send(serial_conn, "LED 0 0 0 255")
    assert resp == "OK", f"Reponse inattendue : {resp!r}"


def test_led_show_apres_set(serial_conn):
    """LEDSHOW pousse le buffer sans erreur."""
    _send(serial_conn, "LED 0 0 0 255")
    resp = _send(serial_conn, "LEDSHOW")
    assert resp == "OK"


def test_led_clear(serial_conn):
    """LEDCLEAR eteint toutes les LEDs et push."""
    _send(serial_conn, "LED 5 255 0 0")
    _send(serial_conn, "LEDSHOW")
    resp = _send(serial_conn, "LEDCLEAR")
    assert resp == "OK"


def test_led_idx_hors_bornes(serial_conn):
    """LED 99 ... retourne une erreur explicite."""
    resp = _send(serial_conn, "LED 99 0 0 0")
    assert resp.startswith("ERR"), f"Erreur attendue, recu : {resp!r}"
    assert "idx=99" in resp or "borne" in resp.lower()


def test_led_composante_hors_bornes(serial_conn):
    """LED 0 999 0 0 retourne une erreur explicite."""
    resp = _send(serial_conn, "LED 0 999 0 0")
    assert resp.startswith("ERR"), f"Erreur attendue, recu : {resp!r}"


def test_led_syntaxe_incomplete(serial_conn):
    """LED 0 0 (args manquants) retourne une erreur explicite."""
    resp = _send(serial_conn, "LED 0 0")
    assert resp.startswith("ERR"), f"Erreur attendue, recu : {resp!r}"


def test_led_bright_valide(serial_conn):
    """LEDBRIGHT 128 retourne OK."""
    resp = _send(serial_conn, "LEDBRIGHT 128")
    assert resp == "OK"
    # Restaurer la valeur par defaut pour ne pas affecter les autres tests
    _send(serial_conn, "LEDBRIGHT 102")


def test_led_bright_hors_bornes(serial_conn):
    """LEDBRIGHT 999 retourne une erreur."""
    resp = _send(serial_conn, "LEDBRIGHT 999")
    assert resp.startswith("ERR")


def test_led_cleanup_en_fin(serial_conn):
    """Nettoie l'etat des LEDs en fin de batch de tests."""
    resp = _send(serial_conn, "LEDCLEAR")
    assert resp == "OK"
```

**Note sur la fixture `serial_conn`** : doit être définie dans `tests/devkit/conftest.py`. Vérifier la fixture existante. Si elle s'appelle différemment, adapter (remplacer par exemple par `esp32_serial`).

- [ ] **Step 3 : Lancer les tests devkit (ESP32 branché USB)**

Run: `pytest -m devkit_serial tests/devkit/test_leds_serial.py -v`
Expected: 9 tests `PASSED`. Si la fixture s'appelle autrement, ajuster.

- [ ] **Step 4 : Commit**

```bash
git add tests/devkit/test_leds_serial.py
git commit -m "test(devkit): protocole LED via serial (set/show/clear/bright/erreurs)"
```

---

## Tâche 6 — Module Python `webapp/leds.py` : mapping (TDD)

**Files:**
- Create: `webapp/leds.py`
- Create: `tests/test_leds.py`

- [ ] **Step 1 : Écrire le test du mapping**

Créer `tests/test_leds.py` :

```python
"""Tests unitaires du sous-systeme LED (webapp/leds.py).

Tests purs Python, sans hardware. Couvrent le mapping engine -> strip,
la fonction de rendu, et la classe LedRenderer (avec mock du PlateauBridge).
"""
from __future__ import annotations

import pytest

from webapp.leds import engine_to_strip_index


class TestEngineToStripIndex:
    """Mapping (row engine, col engine) -> index 0-35 sur le strip serpentin."""

    @pytest.mark.parametrize("row, col, expected", [
        # 4 coins (cf. spec section 5)
        (5, 0, 0),   # bas-gauche  (entree DIN)
        (5, 5, 5),   # bas-droite
        (0, 5, 30),  # haut-droite
        (0, 0, 35),  # haut-gauche (sortie strip)
        # Positions de depart des pions
        (5, 3, 3),   # depart J1 : bas-centre
        (0, 3, 32),  # depart J2 : haut-centre
    ])
    def test_coins_et_departs(self, row, col, expected):
        assert engine_to_strip_index(row, col) == expected

    def test_tous_les_36_indices_uniques(self):
        """Les 36 coordonnees engine doivent donner 36 indices distincts."""
        indices = [
            engine_to_strip_index(row, col)
            for row in range(6) for col in range(6)
        ]
        assert sorted(indices) == list(range(36))

    @pytest.mark.parametrize("row, col, expected_row_phys, expected_parite", [
        (5, 2, 0, "paire"),   # rangee bas : 0 -> gauche-droite
        (4, 2, 1, "impaire"), # 2eme rangee : 1 -> droite-gauche
        (3, 2, 2, "paire"),   # 3eme rangee : 2 -> gauche-droite
    ])
    def test_serpentin_alternance(self, row, col, expected_row_phys, expected_parite):
        """Verifie que la formule serpentin alterne bien selon la parite de row_phys."""
        idx = engine_to_strip_index(row, col)
        row_phys_calc = idx // 6
        assert row_phys_calc == expected_row_phys
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue (module n'existe pas)**

Run: `pytest tests/test_leds.py -v`
Expected: `ImportError: cannot import name 'engine_to_strip_index' from 'webapp.leds'` (ou erreur de module introuvable).

- [ ] **Step 3 : Implémenter `webapp/leds.py` (mapping seul)**

Créer `webapp/leds.py` :

```python
"""Sous-systeme LED : mapping engine <-> strip + rendu de GameState.

Le strip WS2812B physique forme un serpentin 6x6 sur le plateau, avec l'entree
DIN en bas-gauche. Les rangees physiques alternent : rangee 0 (bas) va de gauche
a droite, rangee 1 va de droite a gauche, etc.

L'engine Quoridor utilise sa propre convention : (row, col) avec row=0 en haut,
col=0 a gauche. Ce module fait la traduction.

Voir spec : docs/superpowers/specs/2026-05-21-leds-design.md
"""
from __future__ import annotations


def engine_to_strip_index(row: int, col: int) -> int:
    """Convertit une coordonnee engine (row, col) en index 0-35 sur le strip.

    Engine : row=0 en haut, row=5 en bas, col=0 a gauche, col=5 a droite.
    Strip  : LED 0 = entree DIN bas-gauche ; serpentin alterne par rangee physique.

    Args:
        row: ligne engine (0-5)
        col: colonne engine (0-5)

    Returns:
        Index 0-35 sur le strip serpentin.
    """
    row_phys = 5 - row              # inversion verticale engine -> physique
    if row_phys % 2 == 0:           # rangee paire : gauche -> droite
        return row_phys * 6 + col
    return row_phys * 6 + (5 - col)  # rangee impaire : droite -> gauche
```

- [ ] **Step 4 : Lancer les tests pour vérifier PASS**

Run: `pytest tests/test_leds.py -v`
Expected: `5 passed` (les 4 coins/departs paramétrés + le test des 36 indices uniques + 3 tests d'alternance = 6 + 3 = wait, recompter : test_coins_et_departs a 6 params = 6 tests, test_tous_les_36_indices_uniques = 1, test_serpentin_alternance a 3 params = 3 tests, total = 10 passed).

- [ ] **Step 5 : Commit**

```bash
git add webapp/leds.py tests/test_leds.py
git commit -m "feat(leds): mapping engine -> strip serpentin + tests unitaires"
```

---

## Tâche 7 — Validation physique du mapping (vs résultats Tâche 4)

**Files:** aucun (juste vérification croisée)

**Contexte** : à la Tâche 4 (step 3 et 4) on a vérifié physiquement le serpentin et les 4 coins. On compare maintenant avec le mapping codé à la Tâche 6 pour s'assurer que la formule du code matche la réalité physique.

- [ ] **Step 1 : Comparer**

Si à la Tâche 4 :
- ✅ Serpentin OK + coins OK → **rien à faire**, passer à la Tâche 8.
- ⚠️ Serpentin inversé (rangée 0 va droite-gauche au lieu de gauche-droite) → modifier `engine_to_strip_index` :
  ```python
  if row_phys % 2 == 0:
      return row_phys * 6 + (5 - col)  # invert : paire devient droite-gauche
  return row_phys * 6 + col
  ```
  Puis ajuster les valeurs attendues dans `tests/test_leds.py` (les 6 cas de référence). Relancer `pytest tests/test_leds.py -v`.

- ⚠️ Si l'orientation verticale est inversée (LED 0 en haut-gauche au lieu de bas-gauche) → remplacer `row_phys = 5 - row` par `row_phys = row`. Idem ajuster les tests.

- [ ] **Step 2 : Si ajustement → commit**

```bash
git add webapp/leds.py tests/test_leds.py
git commit -m "fix(leds): ajustement formule mapping suite validation hardware"
```

---

## Tâche 8 — Module `webapp/leds.py` : palette + render_state (TDD)

**Files:**
- Modify: `webapp/leds.py`
- Modify: `tests/test_leds.py`

- [ ] **Step 1 : Ajouter les tests `render_state` dans `tests/test_leds.py`**

Ajouter à la fin du fichier `tests/test_leds.py` :

```python
from quoridor_engine.core import create_new_game, move_pawn, PLAYER_ONE, PLAYER_TWO
from webapp.leds import (
    LedColor, RenderOptions, render_state,
    COLOR_OFF, COLOR_PLAYER_ONE, COLOR_PLAYER_TWO, COLOR_LEGAL_MOVE,
)


class TestRenderState:
    """Conversion GameState -> liste de 36 LedColor (frame)."""

    def test_partie_initiale_pions_seuls(self):
        """Au depart : J1 en bas-centre (LED 3) bleu, J2 en haut-centre (LED 32) rouge."""
        state = create_new_game()
        frame = render_state(state, RenderOptions(show_legal_moves=False))

        assert len(frame) == 36
        assert frame[3] == COLOR_PLAYER_ONE   # J1 bas-centre
        assert frame[32] == COLOR_PLAYER_TWO  # J2 haut-centre
        # Toutes les autres LEDs eteintes
        for idx, color in enumerate(frame):
            if idx in (3, 32):
                continue
            assert color == COLOR_OFF, f"LED {idx} devrait etre eteinte"

    def test_apres_un_coup_j1(self):
        """J1 bouge de (5,3) a (4,3) -> LED 8 (4,3) bleu, LED 3 eteinte."""
        state = create_new_game()
        state = move_pawn(state, PLAYER_ONE, (4, 3))

        frame = render_state(state, RenderOptions(show_legal_moves=False))
        assert frame[3] == COLOR_OFF
        assert frame[8] == COLOR_PLAYER_ONE
        assert frame[32] == COLOR_PLAYER_TWO

    def test_coups_legaux_actives(self):
        """Avec show_legal_moves=True, les cases atteignables apparaissent en cyan."""
        state = create_new_game()
        # J1 demarre en (5,3). Cases atteignables : (4,3), (5,2), (5,4).
        # Index strip : (4,3)=LED 8, (5,2)=LED 2, (5,4)=LED 4.
        frame = render_state(state, RenderOptions(show_legal_moves=True))

        assert frame[3] == COLOR_PLAYER_ONE  # pion J1
        assert frame[8] == COLOR_LEGAL_MOVE  # case (4,3) atteignable
        assert frame[2] == COLOR_LEGAL_MOVE  # case (5,2)
        assert frame[4] == COLOR_LEGAL_MOVE  # case (5,4)

    def test_coups_legaux_desactives_par_defaut(self):
        """RenderOptions par defaut : pas de coups legaux."""
        state = create_new_game()
        frame = render_state(state, RenderOptions())  # defaut
        # Aucune LED ne devrait etre COLOR_LEGAL_MOVE
        assert COLOR_LEGAL_MOVE not in frame

    def test_pion_ecrase_coup_legal_si_meme_case(self):
        """Defense en profondeur : si un pion et un coup legal sont au meme idx,
        c'est la couleur du pion qui gagne (peint en dernier)."""
        # Construction artificielle : on ne peut pas atteindre ce cas dans une partie reelle,
        # mais on teste l'ordre de peinture pour robustesse future.
        state = create_new_game()
        frame = render_state(state, RenderOptions(show_legal_moves=True))
        # Le pion J1 en (5,3)=LED 3 n'est pas dans ses propres coups legaux
        # donc frame[3] reste COLOR_PLAYER_ONE.
        assert frame[3] == COLOR_PLAYER_ONE
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run: `pytest tests/test_leds.py::TestRenderState -v`
Expected: `ImportError: cannot import name 'LedColor'` (ou les autres symboles).

- [ ] **Step 3 : Étendre `webapp/leds.py` avec la palette et `render_state`**

Ajouter à la fin de `webapp/leds.py` :

```python
from dataclasses import dataclass, field
from quoridor_engine.core import GameState, get_possible_pawn_moves, PLAYER_ONE, PLAYER_TWO


@dataclass(frozen=True)
class LedColor:
    """Couleur RGB d'une LED, composantes 0-255 (nominales avant atténuation firmware)."""
    r: int
    g: int
    b: int


# Palette (valeurs nominales, le firmware applique setBrightness(102) = 40%)
COLOR_OFF        = LedColor(0,   0,   0  )  # fond eteint
COLOR_PLAYER_ONE = LedColor(0,   0,   255)  # J1 humain : bleu
COLOR_PLAYER_TWO = LedColor(255, 0,   0  )  # J2 IA : rouge
COLOR_LEGAL_MOVE = LedColor(0,   64,  64 )  # coups legaux : cyan dim (P1 bonus)


@dataclass(frozen=True)
class RenderOptions:
    """Options de rendu (extensibles pour scope futur)."""
    show_legal_moves: bool = False


def render_state(state: GameState, opts: RenderOptions) -> list[LedColor]:
    """Convertit un GameState en frame complete de 36 couleurs.

    Fonction pure : sortie totalement determinee par les inputs, pas de side effect.

    Args:
        state: etat de la partie en cours
        opts: options de rendu (P0/P1 toggles)

    Returns:
        Liste de 36 LedColor, index = position sur le strip serpentin.
    """
    frame: list[LedColor] = [COLOR_OFF] * 36

    # P1 (bonus) : coups legaux peints EN PREMIER (ecrases par les pions ensuite)
    if opts.show_legal_moves:
        for row, col in get_possible_pawn_moves(state, state.current_player):
            frame[engine_to_strip_index(row, col)] = COLOR_LEGAL_MOVE

    # P0 : pions peints EN DERNIER pour ecraser tout coup legal au meme endroit
    r1, c1 = state.player_positions[PLAYER_ONE]
    r2, c2 = state.player_positions[PLAYER_TWO]
    frame[engine_to_strip_index(r1, c1)] = COLOR_PLAYER_ONE
    frame[engine_to_strip_index(r2, c2)] = COLOR_PLAYER_TWO

    return frame
```

- [ ] **Step 4 : Lancer les tests pour vérifier PASS**

Run: `pytest tests/test_leds.py -v`
Expected: tous les tests `TestEngineToStripIndex` ET `TestRenderState` passent (~15 total).

- [ ] **Step 5 : Commit**

```bash
git add webapp/leds.py tests/test_leds.py
git commit -m "feat(leds): palette + render_state(GameState) + tests"
```

---

## Tâche 9 — Module `webapp/leds.py` : classe `LedRenderer` avec diff (TDD)

**Files:**
- Modify: `webapp/leds.py`
- Modify: `tests/test_leds.py`

- [ ] **Step 1 : Écrire les tests `LedRenderer`**

Ajouter à la fin de `tests/test_leds.py` :

```python
from unittest.mock import MagicMock

from webapp.leds import LedRenderer


class TestLedRenderer:
    """LedRenderer : envoi diff vers PlateauBridge + reconnexion."""

    def _make_bridge(self, available: bool = True):
        """Cree un mock de PlateauBridge avec transport.write_line mockable."""
        bridge = MagicMock()
        bridge.available = available
        bridge.transport = MagicMock()
        return bridge

    def _lines_sent(self, bridge) -> list[str]:
        """Recupere la sequence de lignes envoyees via transport.write_line."""
        return [call.args[0] for call in bridge.transport.write_line.call_args_list]

    def test_update_premier_appel_pousse_full_frame(self):
        """Premier update : LEDCLEAR + toutes les LEDs allumees + LEDSHOW."""
        bridge = self._make_bridge()
        renderer = LedRenderer(bridge)

        state = create_new_game()
        renderer.update(state)

        lines = self._lines_sent(bridge)
        assert lines[0] == "LEDCLEAR"
        assert lines[-1] == "LEDSHOW"
        # 2 pions allumes (J1 LED 3 bleu + J2 LED 32 rouge)
        assert "LED 3 0 0 255" in lines
        assert "LED 32 255 0 0" in lines
        # Aucune LED OFF n'est envoyee (le LEDCLEAR a deja tout eteint)
        leds_off = [l for l in lines if l.endswith("0 0 0") and l.startswith("LED ")]
        assert leds_off == []

    def test_update_deuxieme_appel_envoie_diff(self):
        """Deuxieme update apres mouvement : seulement les LEDs changees + LEDSHOW."""
        bridge = self._make_bridge()
        renderer = LedRenderer(bridge)

        state = create_new_game()
        renderer.update(state)
        bridge.transport.write_line.reset_mock()  # oublie le full frame initial

        state = move_pawn(state, PLAYER_ONE, (4, 3))  # J1 (5,3)->(4,3)
        renderer.update(state)

        lines = self._lines_sent(bridge)
        # Diff : LED 3 eteinte (etait bleue), LED 8 allumee (nouveau J1)
        assert "LED 3 0 0 0" in lines
        assert "LED 8 0 0 255" in lines
        assert lines[-1] == "LEDSHOW"
        # Pas de LEDCLEAR (c'est un diff, pas un full frame)
        assert "LEDCLEAR" not in lines

    def test_update_sans_changement_n_envoie_rien(self):
        """Si le frame est identique au precedent, aucune commande n'est envoyee."""
        bridge = self._make_bridge()
        renderer = LedRenderer(bridge)

        state = create_new_game()
        renderer.update(state)
        bridge.transport.write_line.reset_mock()

        renderer.update(state)  # meme etat
        assert bridge.transport.write_line.call_count == 0

    def test_update_no_op_si_bridge_indisponible(self):
        """Si bridge.available est False, update est un no-op silencieux."""
        bridge = self._make_bridge(available=False)
        renderer = LedRenderer(bridge)

        state = create_new_game()
        renderer.update(state)
        assert bridge.transport.write_line.call_count == 0

    def test_on_reconnect_repush_full_frame(self):
        """on_reconnect : re-envoie le dernier frame en full (firmware a reset)."""
        bridge = self._make_bridge()
        renderer = LedRenderer(bridge)

        state = create_new_game()
        renderer.update(state)
        bridge.transport.write_line.reset_mock()

        renderer.on_reconnect()

        lines = self._lines_sent(bridge)
        assert lines[0] == "LEDCLEAR"
        assert lines[-1] == "LEDSHOW"
        assert "LED 3 0 0 255" in lines
        assert "LED 32 255 0 0" in lines

    def test_on_reconnect_no_op_si_pas_de_frame(self):
        """on_reconnect sans update prealable : rien a faire."""
        bridge = self._make_bridge()
        renderer = LedRenderer(bridge)

        renderer.on_reconnect()
        assert bridge.transport.write_line.call_count == 0
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run: `pytest tests/test_leds.py::TestLedRenderer -v`
Expected: `ImportError: cannot import name 'LedRenderer'`.

- [ ] **Step 3 : Implémenter `LedRenderer` dans `webapp/leds.py`**

Ajouter à la fin de `webapp/leds.py` :

```python
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from webapp.plateau import PlateauBridge

log = logging.getLogger(__name__)


class LedRenderer:
    """Maintient l'etat des LEDs et envoie les diffs au firmware via PlateauBridge.

    Le rendu est declenche manuellement via update(state) apres chaque mutation
    de GameState. La classe garde le dernier frame en memoire et ne pousse que
    les LEDs qui ont change (diff). En cas de reconnexion du bridge (firmware
    reboote), on_reconnect() force un re-push complet.
    """

    def __init__(self, bridge: "PlateauBridge"):
        self._bridge = bridge
        self._last_frame: list[LedColor] | None = None
        self._options = RenderOptions(show_legal_moves=False)

    def set_options(self, options: RenderOptions) -> None:
        """Modifie les options de rendu (toggle P1 par ex). Force un re-render."""
        self._options = options
        self._last_frame = None  # force full frame au prochain update

    def update(self, state: GameState) -> None:
        """Calcule le nouveau frame et envoie le diff au firmware.

        No-op silencieux si le bridge n'est pas disponible (mode autonome ou
        ESP32 hors ligne).
        """
        if not self._bridge.available:
            return
        new_frame = render_state(state, self._options)
        if self._last_frame is None:
            self._send_full_frame(new_frame)
        else:
            self._send_diff(self._last_frame, new_frame)
        self._last_frame = new_frame

    def on_reconnect(self) -> None:
        """A appeler quand le bridge recupere la connexion apres coupure.

        Le firmware a reboote, son buffer LED est a 0. On re-pousse le dernier
        frame connu pour resynchroniser.
        """
        if self._last_frame is not None:
            self._send_full_frame(self._last_frame)

    def _send_full_frame(self, frame: list[LedColor]) -> None:
        self._send_line("LEDCLEAR")
        for idx, color in enumerate(frame):
            if color != COLOR_OFF:
                self._send_line(f"LED {idx} {color.r} {color.g} {color.b}")
        self._send_line("LEDSHOW")

    def _send_diff(self, old: list[LedColor], new: list[LedColor]) -> None:
        changed = [(idx, c) for idx, (o, c) in enumerate(zip(old, new)) if o != c]
        if not changed:
            return  # rien a faire, pas de LEDSHOW non plus
        for idx, color in changed:
            self._send_line(f"LED {idx} {color.r} {color.g} {color.b}")
        self._send_line("LEDSHOW")

    def _send_line(self, line: str) -> None:
        """Envoi best-effort. Toute exception est avalee silencieusement (cf.
        pattern de _forward_to_plateau_unlocked dans service.py)."""
        try:
            self._bridge.transport.write_line(line)
        except Exception as e:  # noqa: BLE001
            log.warning("LED forward echoue (%s)", e)
```

- [ ] **Step 4 : Lancer tous les tests `tests/test_leds.py`**

Run: `pytest tests/test_leds.py -v`
Expected: tous les tests passent (~21 total : 10 mapping + 5 render + 6 renderer).

- [ ] **Step 5 : Commit**

```bash
git add webapp/leds.py tests/test_leds.py
git commit -m "feat(leds): LedRenderer avec diff + reconnexion + tests"
```

---

## Tâche 10 — Intégration dans `webapp/service.py`

**Files:**
- Modify: `webapp/service.py`

- [ ] **Step 1 : Repérer les points de mutation de `_state`**

Run: `grep -n "self\._state = \|self\._state," webapp/service.py | head -15`
Expected: trouver les endroits où `_state` est assigné (notamment dans `new_game`, `apply_user_move`, `tick_once`, `undo_move` si présent).

- [ ] **Step 2 : Ajouter l'import et l'instanciation du renderer**

Tout en haut de `webapp/service.py`, après les autres imports, ajouter :

```python
from webapp.leds import LedRenderer
```

Dans `__init__` de `QuoridorService`, juste après la création de `self._plateau = PlateauBridge(...)`, ajouter :

```python
        self._led_renderer = LedRenderer(bridge=self._plateau)
```

- [ ] **Step 3 : Ajouter le hook `update` après chaque mutation**

Identifier les 4 emplacements où le state change :

1. **`new_game`** : après `self._state = create_new_game()` (vers ligne 70), juste avant le bloc `if mode == "human_vs_ai":`. Ajouter :
   ```python
            # Pousser l'etat initial sur les LEDs
            self._led_renderer.update(self._state)
   ```

2. **`apply_user_move`** : à la fin, après la mise à jour de `self._state` (ligne à identifier), ajouter :
   ```python
            self._led_renderer.update(self._state)
   ```

3. **`tick_once`** (mouvement IA) : à la fin du bloc qui met à jour `self._state`, ajouter :
   ```python
            self._led_renderer.update(self._state)
   ```

4. **`_reset_partie`** : à la fin, ajouter un appel pour éteindre les LEDs quand on quitte la partie :
   ```python
        # Eteindre les LEDs (state est None, donc on appelle directement le LEDCLEAR)
        if hasattr(self, "_led_renderer") and self._plateau.available:
            try:
                self._plateau.transport.write_line("LEDCLEAR")
            except Exception:
                pass
   ```

**Détail** : pour `_reset_partie`, on n'a pas de GameState à rendre, donc on envoie directement `LEDCLEAR`. Le `hasattr` est nécessaire car `_reset_partie` est appelée dans `__init__` **avant** que `_led_renderer` ne soit créé (selon l'ordre exact d'init — vérifier au moment de l'implémentation et ajuster).

- [ ] **Step 4 : Vérifier qu'aucun test unitaire existant ne casse**

Run: `pytest -m "not devkit" -v`
Expected: tous les tests existants (non devkit) passent. Si un test de `service.py` casse, vérifier qu'on n'a pas perturbé une logique.

- [ ] **Step 5 : Commit**

```bash
git add webapp/service.py
git commit -m "feat(service): hook LedRenderer.update apres mutation GameState"
```

---

## Tâche 11 — Hook reconnexion du bridge

**Files:**
- Modify: `webapp/plateau.py` ou `webapp/service.py` (selon où vit la logique reconnexion)

**Objectif** : quand `PlateauBridge` se reconnecte après une coupure, déclencher `LedRenderer.on_reconnect()` pour resynchroniser les LEDs.

- [ ] **Step 1 : Localiser la logique de reconnexion**

Run: `grep -n "_reconnect_loop\|on_reconnect\|reconnect_watcher" webapp/plateau.py`
Expected: voir `_reconnect_loop` dans `PlateauBridge` (ligne ~145).

- [ ] **Step 2 : Ajouter un callback dans `PlateauBridge`**

Option 1 (simple) : exposer une liste de callbacks. Dans `PlateauBridge.__init__` (vers ligne 35-65) :

```python
        self._on_reconnect_callbacks: list = []

    def add_on_reconnect_callback(self, callback) -> None:
        """Enregistre un callback a appeler quand la connexion est rétablie."""
        self._on_reconnect_callbacks.append(callback)
```

Dans `_reconnect_loop` (vers ligne 145+), juste après que la reconnexion a réussi, ajouter :

```python
                # Notifier les abonnes (LedRenderer notamment)
                for cb in self._on_reconnect_callbacks:
                    try:
                        cb()
                    except Exception as e:  # noqa: BLE001
                        log.warning("Callback on_reconnect echoue (%s)", e)
```

- [ ] **Step 3 : S'abonner depuis `QuoridorService`**

Dans `__init__` de `QuoridorService`, juste après l'instanciation de `_led_renderer`, ajouter :

```python
        self._plateau.add_on_reconnect_callback(self._led_renderer.on_reconnect)
```

- [ ] **Step 4 : Lancer les tests existants**

Run: `pytest -m "not devkit" -v`
Expected: aucun test ne casse.

- [ ] **Step 5 : Commit**

```bash
git add webapp/plateau.py webapp/service.py
git commit -m "feat(plateau): callback reconnexion + abonnement LedRenderer"
```

---

## Tâche 12 — Test bout-en-bout manuel (avec hardware)

**Files:** aucun (validation manuelle).

**Prérequis** : ESP32 flashé, plateau LEDs câblé, alim 5V active.

- [ ] **Step 1 : Lancer la webapp en mode USB**

Run: `QUORIDOR_TRANSPORT=serial python -m webapp.server`
Expected: la webapp démarre sur `http://localhost:8000`. Dans les logs : confirmation que le bridge est OPEN sur `/dev/cu.usbserial-*`.

- [ ] **Step 2 : Ouvrir le navigateur**

Ouvrir `http://localhost:8000` dans Safari.

- [ ] **Step 3 : Démarrer une nouvelle partie**

Choisir "Humain vs IA", difficulté quelconque, cocher "mode plateau" si disponible. Cliquer "Nouvelle partie".

**Sortie attendue** :
- LED 3 (bas-centre) s'allume en bleu (pion J1)
- LED 32 (haut-centre) s'allume en rouge (pion J2)
- Toutes les autres LEDs sont éteintes
- Latence visible : < 200 ms entre le clic et l'allumage

- [ ] **Step 4 : Déplacer J1 d'une case**

Cliquer une case adjacente au pion bleu (ex. la case immédiatement au-dessus).

**Sortie attendue** :
- L'ancienne LED bleue s'éteint
- La nouvelle LED s'allume en bleu
- L'IA répond rapidement → la LED rouge bouge à son tour
- Pas de flicker visible (push atomique via LEDSHOW)

- [ ] **Step 5 : Quitter la partie**

Cliquer "Quitter" ou "Nouvelle partie" pour revenir à l'écran d'accueil.

**Sortie attendue** : toutes les LEDs s'éteignent (effet du LEDCLEAR dans `_reset_partie`).

- [ ] **Step 6 : Tester la reconnexion**

Pendant une partie en cours, **débrancher physiquement l'USB de l'ESP32** pendant 5 secondes, puis rebrancher.

**Sortie attendue** :
- Les LEDs s'éteignent au reset de l'ESP32 (normal, buffer remis à 0)
- Le bridge détecte la coupure puis se reconnecte (~10 s max)
- Les LEDs se rallument automatiquement à leur état antérieur

- [ ] **Step 7 : Tester en Wi-Fi**

Quitter la webapp (Ctrl+C). Relancer en mode Wi-Fi (basculer le Wi-Fi du Mac sur `Quoridor-ESP32` au préalable) :

Run: `python tools/wifi_switch.py to-esp32 --save-current ICAM && QUORIDOR_TRANSPORT=wifi python -m webapp.server`
Expected: même comportement qu'en USB, latence légèrement supérieure (~20-50 ms) mais imperceptible.

Restaurer le Wi-Fi normal à la fin :
Run: `python tools/wifi_switch.py restore`

- [ ] **Step 8 : Pas de commit nécessaire**

C'est une validation manuelle. Si quelque chose ne marche pas, débugger avant de passer à la doc.

---

## Tâche 13 — Documentation

**Files:**
- Modify: `docs/07_protocole.md`
- Modify: `docs/06_firmware.md`
- Modify: `docs/02_architecture.md`
- Modify: `docs/hardware/pinout.md`

- [ ] **Step 1 : Mettre à jour `docs/07_protocole.md`**

Ajouter à la fin du fichier (avant la section "Logs verbeux du firmware" si elle existe, sinon à la fin) une section :

```markdown
---

## Commandes LED (phase 5b)

Le sous-système LED expose 4 commandes texte additionnelles, identiques sur USB et Wi-Fi.
Détail dans la spec `docs/superpowers/specs/2026-05-21-leds-design.md`.

### Commandes Mac → ESP32

| Commande | Réponse | Description |
|---|---|---|
| `LED <idx> <r> <g> <b>` | `OK` ou `ERR <msg>` | Met à jour le pixel `idx` dans le buffer firmware. Ne push pas sur le strip. |
| `LEDSHOW` | `OK` | Push atomique du buffer interne vers le strip. |
| `LEDCLEAR` | `OK` | Buffer remis à 0 + push immédiat. Toutes les LEDs éteintes. |
| `LEDBRIGHT <0..255>` | `OK` ou `ERR <msg>` | Modifie la luminosité globale. Persistant jusqu'au reset. Défaut : 102 (40 %). |

### Bornes

| Champ | Bornes | Erreur |
|---|---|---|
| `idx` | `[0..35]` | `ERR LED borne : idx=X hors [0..35]` |
| `r`, `g`, `b` | `[0..255]` | `ERR LED borne : composante hors [0..255]` |
| `LEDBRIGHT` | `[0..255]` | `ERR LEDBRIGHT borne : X hors [0..255]` |

### Exemple de session

\`\`\`
> LED 3 0 0 0          ← éteindre l'ancienne position J1
< OK
> LED 8 0 0 255        ← allumer la nouvelle position J1 (bleu)
< OK
> LED 7 0 64 64        ← case atteignable (cyan dim, P1 bonus)
< OK
> LEDSHOW              ← push atomique
< OK
\`\`\`
```

(Remplacer les `\`\`\`` par de vrais triples backticks dans le fichier — l'échappement est pour l'embarquage ici.)

- [ ] **Step 2 : Mettre à jour `docs/06_firmware.md`**

Dans la section "Mapping GPIO", ajouter une ligne :

```markdown
| LED strip WS2812B (DIN) | 15 |
```

Dans la liste des commandes mode webapp, ajouter à la fin du tableau :

```markdown
| `LED <idx> <r> <g> <b>` | `OK` ou `ERR <msg>` |
| `LEDSHOW` | `OK` |
| `LEDCLEAR` | `OK` |
| `LEDBRIGHT <0..255>` | `OK` ou `ERR <msg>` |
```

Ajouter une note sous la table : "Sous-système LED documenté en détail dans `docs/07_protocole.md` et `docs/superpowers/specs/2026-05-21-leds-design.md`."

- [ ] **Step 3 : Mettre à jour `docs/02_architecture.md`**

Dans le tableau de `webapp/` (section "Composants logiciels"), ajouter une ligne :

```markdown
| `leds.py` | Mapping engine↔strip serpentin + classe `LedRenderer` avec diff. Hook après mutation de `GameState`. |
```

- [ ] **Step 4 : Mettre à jour `docs/hardware/pinout.md`**

Ajouter une section après "Servo SG90" :

```markdown
## Strip LED WS2812B (36 LEDs)

| Signal | GPIO ou alim |
|---|---|
| DIN (data) | 15 |
| VDD | alimentation 5 V externe (step-down du 12 V général) |
| GND | commun avec ESP32 GND (impératif) |

Strapping pin sans risque (pull-up interne, état HIGH par défaut au boot).
Pin libérée comme GPIO normal après le boot. Cf. spec :
`docs/superpowers/specs/2026-05-21-leds-design.md`.
```

- [ ] **Step 5 : Commit**

```bash
git add docs/
git commit -m "docs(leds): MAJ protocole, firmware, architecture, pinout (commandes LED + GPIO 15)"
```

---

## Tâche 14 — (P1 bonus, si temps) Activation des coups légaux

**Files:**
- Modify: `webapp/service.py` (ou ajout d'une option de config)
- Modify: `tests/test_leds.py` (vérifier les tests P1 déjà écrits restent verts)

**Objectif** : activer `show_legal_moves=True` dans `LedRenderer.set_options()` pour que les cases atteignables s'allument en cyan.

- [ ] **Step 1 : Ajouter un appel `set_options` dans `__init__` ou `new_game`**

Dans `QuoridorService.__init__`, juste après l'instanciation du renderer, ajouter :

```python
        from webapp.leds import RenderOptions
        self._led_renderer.set_options(RenderOptions(show_legal_moves=True))
```

Ou : exposer un endpoint `/api/led/options` qui permet de toggler à la volée (plus de travail, à voir selon le temps disponible).

- [ ] **Step 2 : Lancer les tests pour vérifier que la palette est propre**

Run: `pytest tests/test_leds.py -v`
Expected: tous les tests passent toujours (les tests P1 vérifient déjà la palette cyan).

- [ ] **Step 3 : Validation manuelle**

Run: `QUORIDOR_TRANSPORT=serial python -m webapp.server`
Démarrer une partie, observer que les cases atteignables du joueur courant s'allument en cyan dim au début de chaque tour.

- [ ] **Step 4 : Commit**

```bash
git add webapp/service.py
git commit -m "feat(leds): activation P1 affichage des coups legaux en cyan"
```

---

## Récapitulatif final

Après les 14 tâches :

- **Code Python ajouté** : ~250 lignes (`webapp/leds.py`) + ~200 lignes de tests (`tests/test_leds.py`)
- **Code firmware ajouté** : ~60 lignes dans `bringup_l298n_complet.cpp`
- **Tests unitaires** : ~21 cas
- **Tests devkit** : ~9 cas
- **Doc mise à jour** : 4 fichiers
- **Commits attendus** : ~13 (un par tâche, sauf Tâches 3, 12 qui sont des validations manuelles)

### Critères de succès (rappel du spec)

1. ✅ `pytest -m "not devkit"` vert
2. ✅ `pytest -m devkit_serial` vert (ESP32 branché)
3. ✅ En partie réelle, les LEDs suivent les pions en < 100 ms perçues
4. ✅ Coupure/reconnexion → LEDs reviennent automatiquement
5. ✅ Doc projet mise à jour (4 fichiers)
