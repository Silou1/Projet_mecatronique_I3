# Portage pytest des scénarios P8.6 — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Porter les 8 scénarios d'intégration UART P8.6 (`firmware/tests_devkit/run_p86_manual.py`) en suite pytest dans `tests/integration/test_uart_devkit.py`, avec marqueur `@pytest.mark.devkit` qui skippe automatiquement quand le DevKit n'est pas branché.

**Architecture:** Helpers protocole/serial extraits dans `firmware/tests_devkit/_uart_helpers.py` (DRY entre harness manuel et pytest). Trois fixtures pytest dans `tests/integration/conftest.py` : `serial_port` (session-scoped, ouvre/skip), `raw_devkit` (function, reset hardware seul), `connected_devkit` (function, reset + handshake). 8 fonctions `test_sc_*` portées 1:1 depuis `scenario_*` avec `assert` à la place de `return False, msg`.

**Tech Stack:** Python 3.12, pytest 9.0.3, pyserial 3.5, DevKit ESP32 Freenove (CH340) sur `/dev/cu.usbserial-*`.

**Spec source:** [`docs/superpowers/specs/2026-05-06-pytest-port-p86-design.md`](../specs/2026-05-06-pytest-port-p86-design.md).

**Note méthodologique** : ce projet est un *portage* de tests qui existent et passent déjà via `run_p86_manual.py`. Le TDD strict ne s'applique pas (on n'invente pas de comportement). À la place, chaque tâche suit : écrire le test pytest → le lancer contre le DevKit → vérifier qu'il PASS (puisque la logique sous-jacente est validée) → commit. Plus la non-régression du harness manuel après le refactor des helpers.

**Pré-requis avant de commencer :**

- DevKit ESP32 branché sur USB, port visible via `ls /dev/cu.usbserial-*`.
- Firmware Plan 2 + stubs P9 flashés (cf. `firmware/INTEGRATION_TESTS_PENDING.md` préparatifs).
- Suite verte : `pytest` doit retourner 226 PASSED avant de commencer.
- `pyserial` installé dans `.venv` : `python -c "import serial; print(serial.__version__)"` doit afficher `3.5`.

---

### Task 1: Extraire les helpers dans `_uart_helpers.py`

**Files:**
- Create: `firmware/tests_devkit/_uart_helpers.py`
- Modify: `firmware/tests_devkit/run_p86_manual.py` (lignes 11-102 supprimées, remplacées par un import ; ligne 18 `PORT = ...` adaptée)

- [ ] **Step 1.1: Créer `_uart_helpers.py` avec les helpers extraits**

```python
# firmware/tests_devkit/_uart_helpers.py
"""Helpers protocole + serial pour les tests P8.6 (harness manuel + pytest).

Module privé au dossier firmware/tests_devkit/. Importé par :
- run_p86_manual.py (harness interactif, exécutable directement)
- tests/integration/conftest.py (fixtures pytest)
"""

import binascii
import glob
import re
import time

import serial

PORT_GLOB = "/dev/cu.usbserial-*"
BAUD = 115200


def find_devkit_port() -> str | None:
    """Retourne le premier port DevKit détecté (ordre lexico) ou None."""
    matches = sorted(glob.glob(PORT_GLOB))
    return matches[0] if matches else None


# --- Helpers protocole ---


def crc16(data: str) -> str:
    """CRC-16 CCITT-FALSE sur la zone CRC, retourne hex 4 chars majuscules."""
    return f"{binascii.crc_hqx(data.encode('ascii'), 0xFFFF):04X}"


def make_frame(type_, args="", seq=0, ack=None, version=None) -> bytes:
    body = type_
    if args:
        body += " " + args
    body += f"|seq={seq}"
    if ack is not None:
        body += f"|ack={ack}"
    if version is not None:
        body += f"|v={version}"
    return f"<{body}|crc={crc16(body)}>\n".encode("ascii")


FRAME_RE = re.compile(r"<([^>]+)>")


def parse_frames(text: str):
    out = []
    for m in FRAME_RE.finditer(text):
        body = m.group(1)
        parts = body.split("|")
        head = parts[0].split(" ", 1)
        type_ = head[0]
        args = head[1] if len(head) > 1 else ""
        fields = {}
        for p in parts[1:]:
            if "=" in p:
                k, v = p.split("=", 1)
                fields[k] = v
        crc_recv = fields.pop("crc", None)
        zone = body.rsplit("|crc=", 1)[0]
        crc_calc = crc16(zone)
        crc_ok = (crc_recv == crc_calc)
        out.append({"type": type_, "args": args, "crc_ok": crc_ok, "raw": m.group(0), **fields})
    return out


# --- Helpers serial ---


def reset_esp(s: serial.Serial) -> None:
    s.dtr = False  # GPIO0 high (boot Flash)
    s.rts = True   # EN low (reset)
    time.sleep(0.1)
    s.reset_input_buffer()
    s.rts = False  # EN high (run)


def keepalive(s: serial.Serial) -> None:
    """Trame KEEPALIVE valide pour rafraichir le watchdog UART (3 s) du firmware."""
    s.write(make_frame("KEEPALIVE", seq=0))


def read_for(s: serial.Serial, duration: float) -> str:
    start = time.time()
    buf = bytearray()
    while time.time() - start < duration:
        chunk = s.read(4096)
        if chunk:
            buf.extend(chunk)
    return buf.decode("ascii", errors="replace")


def wait_for(s: serial.Serial, pattern: str, timeout: float = 5.0) -> str:
    start = time.time()
    buf = bytearray()
    rx = re.compile(pattern)
    while time.time() - start < timeout:
        chunk = s.read(2048)
        if chunk:
            buf.extend(chunk)
            if rx.search(buf.decode("ascii", errors="replace")):
                return buf.decode("ascii", errors="replace")
    return buf.decode("ascii", errors="replace")
```

- [ ] **Step 1.2: Refactorer `run_p86_manual.py` pour importer depuis `_uart_helpers`**

Remplacer les lignes 1-102 (de la docstring jusqu'à la fonction `wait_for` incluse) par :

```python
#!/usr/bin/env python3
"""Validation P8.6 - protocole UART Plan 2 sur DevKit ESP32.

Joue les 8 scenarios de firmware/INTEGRATION_TESTS_PENDING.md en sequence,
stop on first FAIL. Pas un test pytest : outil hardware-dependent qui
necessite le DevKit branche sur /dev/cu.usbserial-*.

Pour la version pytest automatique, voir tests/integration/test_uart_devkit.py.
"""

import re
import sys
import time

import serial

from _uart_helpers import (
    BAUD,
    crc16,
    find_devkit_port,
    keepalive,
    make_frame,
    read_for,
    reset_esp,
    wait_for,
)

PORT = find_devkit_port() or "/dev/cu.usbserial-110"
```

Garder intact le reste du fichier (lignes 105-314 : scénarios + main).

- [ ] **Step 1.3: Vérifier non-régression du harness manuel**

Run: `python firmware/tests_devkit/run_p86_manual.py 1`

Expected: le scénario 1 (handshake) tourne et affiche `[PASS] Scenario 1 - Handshake nominal : transition CONNECTED ok`.

Si KO, vérifier que les imports de `_uart_helpers` sont bien résolus depuis `firmware/tests_devkit/`.

- [ ] **Step 1.4: Vérifier que sc 5 fonctionne aussi (test passif, plus subtil)**

Run: `python firmware/tests_devkit/run_p86_manual.py 5`

Expected: `[FAIL]` au sc 5 attendu si on lance isolé (pas d'état CONNECTED). On valide juste que le harness ne crashe pas en imports. Le résumé doit afficher au moins une ligne, sans `Traceback` ni `ImportError`.

Note : sc 5 isolé peut échouer car il suppose CONNECTED. C'est OK, on cherche juste la non-régression du chargement.

- [ ] **Step 1.5: Vérifier la suite complète (8 scénarios) — sanity check**

Run: `python firmware/tests_devkit/run_p86_manual.py`

Expected: les 8 scénarios PASS comme dans le commit `033a64d`. Si un seul échoue, c'est une régression du refactor — investiguer avant de continuer.

- [ ] **Step 1.6: Commit**

```bash
git add firmware/tests_devkit/_uart_helpers.py firmware/tests_devkit/run_p86_manual.py
git commit -m "refactor(devkit): extraire helpers UART dans _uart_helpers.py"
```

---

### Task 2: Créer `pyproject.toml` minimal

**Files:**
- Create: `pyproject.toml`

- [ ] **Step 2.1: Créer le fichier**

```toml
# pyproject.toml
[project]
name = "quoridor-mecatronique"
version = "0.1.0"
description = "Moteur de jeu Quoridor 6x6 + intégration ESP32 (projet mécatronique ICAM 3A)"
requires-python = ">=3.12"

[project.optional-dependencies]
devkit = ["pyserial>=3.5"]

[tool.pytest.ini_options]
markers = [
  "devkit: tests qui requièrent le DevKit ESP32 branché (skipés sinon)",
]
testpaths = ["tests"]
```

- [ ] **Step 2.2: Vérifier que pytest découvre toujours les 226 tests existants**

Run: `pytest --collect-only -q 2>&1 | tail -5`

Expected: ligne finale type `226 tests collected in 0.XXs`. Aucun test ne doit avoir disparu suite à `testpaths = ["tests"]`.

- [ ] **Step 2.3: Vérifier qu'aucun warning de marqueur inconnu n'apparaît**

Run: `pytest -m "not devkit" tests/ --collect-only -q 2>&1 | grep -i "warning\|unknown"`

Expected: aucune ligne en sortie (le marqueur `devkit` est désormais enregistré, donc pas de `PytestUnknownMarkWarning`).

- [ ] **Step 2.4: Lancer la suite verte complète, doit rester verte**

Run: `pytest -q`

Expected: `226 passed in XX.XXs`. Aucun changement de comportement vs avant le refactor.

- [ ] **Step 2.5: Commit**

```bash
git add pyproject.toml
git commit -m "build: ajouter pyproject.toml avec config pytest et marqueur devkit"
```

---

### Task 3: Créer la structure `tests/integration/` + fixtures

**Files:**
- Create: `tests/integration/__init__.py` (vide)
- Create: `tests/integration/conftest.py`

- [ ] **Step 3.1: Créer le package `tests/integration/`**

```bash
mkdir -p tests/integration
touch tests/integration/__init__.py
```

- [ ] **Step 3.2: Créer `tests/integration/conftest.py` avec les 3 fixtures**

```python
# tests/integration/conftest.py
"""Fixtures pour les tests d'intégration nécessitant le DevKit ESP32 branché.

Skippe automatiquement les tests si aucun port /dev/cu.usbserial-* n'est détecté.
"""

import re
import sys
from pathlib import Path

import pytest
import serial

# Permet l'import de _uart_helpers depuis firmware/tests_devkit/
# (ce dossier n'est pas un package Python, c'est volontaire — script direct).
_TESTS_DEVKIT = Path(__file__).resolve().parents[2] / "firmware" / "tests_devkit"
sys.path.insert(0, str(_TESTS_DEVKIT))

from _uart_helpers import (  # noqa: E402
    BAUD,
    find_devkit_port,
    make_frame,
    reset_esp,
    wait_for,
)


@pytest.fixture(scope="session")
def serial_port():
    """Ouvre le port DevKit pour toute la session pytest. Skip si non détecté."""
    port = find_devkit_port()
    if port is None:
        pytest.skip("DevKit ESP32 non détecté (aucun /dev/cu.usbserial-*)")
    s = serial.Serial(port, BAUD, timeout=0.1)
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def raw_devkit(serial_port):
    """Reset hardware uniquement. Pour sc 1 qui teste le handshake lui-même."""
    reset_esp(serial_port)
    return serial_port


@pytest.fixture
def connected_devkit(serial_port):
    """Reset + handshake complet. Pour sc 2-8 qui partent de l'état CONNECTED."""
    reset_esp(serial_port)
    out = wait_for(serial_port, r"<HELLO\|seq=(\d+)\|v=1\|crc=", timeout=4.0)
    m = re.search(r"<HELLO\|seq=(\d+)\|v=1\|crc=", out)
    assert m, "fixture connected_devkit : pas de HELLO reçu après reset"
    serial_port.write(make_frame("HELLO_ACK", seq=0, ack=int(m.group(1))))
    out2 = wait_for(serial_port, r"\[FSM\] -> state 3", timeout=2.0)
    assert "state 3" in out2, "fixture connected_devkit : pas de transition CONNECTED"
    return serial_port
```

- [ ] **Step 3.3: Vérifier que le conftest se charge sans erreur**

Run: `pytest tests/integration/ --collect-only -q`

Expected: `no tests collected` (pas encore de test_*.py dans `tests/integration/`), aucune erreur d'import. Les imports de `_uart_helpers` doivent être résolus.

Si erreur `ModuleNotFoundError: No module named '_uart_helpers'`, vérifier le `sys.path.insert` et le chemin relatif.

- [ ] **Step 3.4: Vérifier que la suite globale reste verte**

Run: `pytest -q`

Expected: `226 passed`. Le nouveau conftest local ne doit pas affecter les tests unitaires.

- [ ] **Step 3.5: Commit**

```bash
git add tests/integration/__init__.py tests/integration/conftest.py
git commit -m "test(integration): ajouter fixtures pytest pour DevKit ESP32"
```

---

### Task 4: Test de fumée — vérifier que les fixtures marchent

**Files:**
- Create: `tests/integration/test_uart_devkit.py` (avec un seul test minimal de smoke)

- [ ] **Step 4.1: Créer le fichier avec un test placeholder qui valide la fixture**

```python
# tests/integration/test_uart_devkit.py
"""Tests d'intégration P8.6 — protocole UART Plan 2 sur DevKit ESP32 réel.

Portage 1:1 des 8 scénarios de firmware/tests_devkit/run_p86_manual.py.
Marqueur @pytest.mark.devkit : skippé si aucun /dev/cu.usbserial-* présent.
"""

import re

import pytest

from _uart_helpers import crc16, make_frame, read_for, wait_for


@pytest.mark.devkit
def test_smoke_fixture_connected(connected_devkit):
    """Smoke test : la fixture connected_devkit doit fournir un port en état CONNECTED."""
    assert connected_devkit.is_open, "port doit être ouvert"
```

- [ ] **Step 4.2: Lancer le test avec DevKit branché**

Run: `pytest tests/integration/test_uart_devkit.py::test_smoke_fixture_connected -v -s`

Expected: `1 passed` en ~3-4 s (temps du reset + handshake de la fixture).

Si fail au handshake : vérifier le port (`ls /dev/cu.usbserial-*`), le firmware flashé (Plan 2), et relancer.

- [ ] **Step 4.3: Vérifier le skip sans hardware (optionnel mais utile)**

Si tu peux débrancher le DevKit temporairement :

Run: `pytest tests/integration/test_uart_devkit.py::test_smoke_fixture_connected -v`

Expected: `1 skipped` avec raison `DevKit ESP32 non détecté (aucun /dev/cu.usbserial-*)`.

Rebrancher le DevKit avant la suite.

- [ ] **Step 4.4: Vérifier que `pytest -m "not devkit"` ignore ce test**

Run: `pytest -m "not devkit" -q`

Expected: `226 passed, 1 deselected` (les 226 tests existants + le smoke test exclu).

- [ ] **Step 4.5: Commit**

```bash
git add tests/integration/test_uart_devkit.py
git commit -m "test(integration): ajouter smoke test de la fixture connected_devkit"
```

---

### Task 5: Porter sc 1 — Handshake nominal

**Files:**
- Modify: `tests/integration/test_uart_devkit.py` (ajouter `test_sc_1_handshake`, supprimer le smoke test devenu redondant)

- [ ] **Step 5.1: Remplacer le smoke test par le vrai sc 1**

Remplacer `test_smoke_fixture_connected` par :

```python
@pytest.mark.devkit
def test_sc_1_handshake(raw_devkit):
    """Sc 1 — Handshake nominal : BOOT_START → HELLO → HELLO_ACK → state 3."""
    out = wait_for(raw_devkit, r"<HELLO\|seq=(\d+)\|v=1\|crc=", timeout=4.0)
    m = re.search(r"<HELLO\|seq=(\d+)\|v=1\|crc=", out)
    assert m, "aucun HELLO reçu"
    raw_devkit.write(make_frame("HELLO_ACK", seq=0, ack=int(m.group(1))))
    out2 = wait_for(raw_devkit, r"\[FSM\] -> state 3", timeout=2.0)
    assert "state 3" in out2, "pas de transition vers state 3 (CONNECTED)"
```

- [ ] **Step 5.2: Lancer le test**

Run: `pytest tests/integration/test_uart_devkit.py::test_sc_1_handshake -v -s`

Expected: `1 passed` en ~3 s.

- [ ] **Step 5.3: Commit**

```bash
git add tests/integration/test_uart_devkit.py
git commit -m "test(integration): porter sc 1 P8.6 (handshake nominal)"
```

---

### Task 6: Porter sc 2 — Cycle nominal humain (BTN)

**Files:**
- Modify: `tests/integration/test_uart_devkit.py`

- [ ] **Step 6.1: Ajouter le test sc 2 à la fin du fichier**

```python
@pytest.mark.devkit
def test_sc_2_btn_humain(connected_devkit):
    """Sc 2 — BTN x y → MOVE_REQ → ACK → EXECUTING → DONE."""
    connected_devkit.reset_input_buffer()
    connected_devkit.write(b"BTN 3 4\n")
    out = wait_for(connected_devkit, r"<MOVE_REQ 3 4\|seq=(\d+)\|crc=", timeout=2.0)
    m = re.search(r"<MOVE_REQ 3 4\|seq=(\d+)\|crc=([0-9A-F]+)>", out)
    assert m, "pas de MOVE_REQ 3 4 émis"
    move_seq = int(m.group(1))
    crc_recv = m.group(2)
    crc_calc = crc16(f"MOVE_REQ 3 4|seq={move_seq}")
    assert crc_recv == crc_calc, f"CRC MOVE_REQ invalide (recu {crc_recv}, calculé {crc_calc})"
    connected_devkit.write(make_frame("ACK", seq=0, ack=move_seq))
    out2 = wait_for(connected_devkit, r"\[FSM\] -> state 5", timeout=2.0)
    assert "state 5" in out2, "pas de transition state 5 (EXECUTING)"
    out3 = wait_for(connected_devkit, rf"<DONE\|seq=\d+\|ack={move_seq}\|crc=", timeout=4.0)
    assert "DONE" in out3, "pas de DONE reçu"
```

- [ ] **Step 6.2: Lancer le test**

Run: `pytest tests/integration/test_uart_devkit.py::test_sc_2_btn_humain -v -s`

Expected: `1 passed` en ~5-6 s (fixture handshake + cycle BTN complet).

- [ ] **Step 6.3: Commit**

```bash
git add tests/integration/test_uart_devkit.py
git commit -m "test(integration): porter sc 2 P8.6 (cycle humain BTN)"
```

---

### Task 7: Porter sc 3 — Cycle nominal IA (CMD MOVE)

**Files:**
- Modify: `tests/integration/test_uart_devkit.py`

- [ ] **Step 7.1: Ajouter le test sc 3**

```python
@pytest.mark.devkit
def test_sc_3_cmd_ia(connected_devkit):
    """Sc 3 — CMD MOVE r c → DONE."""
    connected_devkit.reset_input_buffer()
    cmd_seq = 10
    connected_devkit.write(make_frame("CMD", "MOVE 2 5", seq=cmd_seq))
    out = wait_for(connected_devkit, rf"<DONE\|seq=\d+\|ack={cmd_seq}\|crc=", timeout=4.0)
    assert "DONE" in out, "pas de DONE reçu pour CMD MOVE"
```

- [ ] **Step 7.2: Lancer le test**

Run: `pytest tests/integration/test_uart_devkit.py::test_sc_3_cmd_ia -v -s`

Expected: `1 passed` en ~5 s.

- [ ] **Step 7.3: Commit**

```bash
git add tests/integration/test_uart_devkit.py
git commit -m "test(integration): porter sc 3 P8.6 (cycle IA CMD MOVE)"
```

---

### Task 8: Porter sc 4 — Idempotence CMD

**Files:**
- Modify: `tests/integration/test_uart_devkit.py`

- [ ] **Step 8.1: Ajouter le test sc 4**

```python
@pytest.mark.devkit
def test_sc_4_idempotence(connected_devkit):
    """Sc 4 — Replay même CMD avec même seq → DONE renvoyé sans re-exécution."""
    connected_devkit.reset_input_buffer()
    cmd_seq = 20
    frame = make_frame("CMD", "MOVE 1 1", seq=cmd_seq)
    connected_devkit.write(frame)
    out1 = wait_for(connected_devkit, rf"<DONE\|seq=\d+\|ack={cmd_seq}\|crc=", timeout=4.0)
    assert "DONE" in out1, "pas de DONE pour 1ère émission"
    # 2e émission, même frame
    connected_devkit.reset_input_buffer()
    connected_devkit.write(frame)
    out2 = wait_for(connected_devkit, rf"<DONE\|seq=\d+\|ack={cmd_seq}\|crc=", timeout=2.0)
    assert "DONE" in out2, "pas de DONE renvoyé sur replay"
    n_exec_2 = out2.count("[MOT] exec command")
    assert n_exec_2 == 0, f"commande re-executée ({n_exec_2}x) au lieu d'être idempotente"
```

- [ ] **Step 8.2: Lancer le test**

Run: `pytest tests/integration/test_uart_devkit.py::test_sc_4_idempotence -v -s`

Expected: `1 passed` en ~7 s (2 cycles CMD + handshake fixture).

- [ ] **Step 8.3: Commit**

```bash
git add tests/integration/test_uart_devkit.py
git commit -m "test(integration): porter sc 4 P8.6 (idempotence CMD)"
```

---

### Task 9: Porter sc 5 — CRC corrompu

**Files:**
- Modify: `tests/integration/test_uart_devkit.py`

- [ ] **Step 9.1: Ajouter l'import `keepalive` et le test sc 5**

Remplacer la ligne d'import existante par :

```python
from _uart_helpers import crc16, keepalive, make_frame, read_for, wait_for
```

Ajouter le test :

```python
@pytest.mark.devkit
def test_sc_5_crc_corrompu(connected_devkit):
    """Sc 5 — Trame avec CRC bidon → rejet silencieux (pas d'ACK/ERR/transition)."""
    keepalive(connected_devkit)  # rafraîchir watchdog avant test passif
    connected_devkit.reset_input_buffer()
    connected_devkit.write(b"<KEEPALIVE|seq=0|crc=0000>\n")
    out = read_for(connected_devkit, 1.0)
    assert "<ACK" not in out, "trame CRC bidon a déclenché un ACK"
    assert "<ERR" not in out, "trame CRC bidon a déclenché un ERR"
    assert "[FSM] ->" not in out, "trame CRC bidon a déclenché une transition d'état"
    keepalive(connected_devkit)  # éviter expiration watchdog avant prochain test
```

- [ ] **Step 9.2: Lancer le test**

Run: `pytest tests/integration/test_uart_devkit.py::test_sc_5_crc_corrompu -v -s`

Expected: `1 passed` en ~5 s.

- [ ] **Step 9.3: Commit**

```bash
git add tests/integration/test_uart_devkit.py
git commit -m "test(integration): porter sc 5 P8.6 (CRC corrompu)"
```

---

### Task 10: Porter sc 6 — Trame > 80 octets

**Files:**
- Modify: `tests/integration/test_uart_devkit.py`

- [ ] **Step 10.1: Ajouter le test sc 6**

```python
@pytest.mark.devkit
def test_sc_6_trame_longue(connected_devkit):
    """Sc 6 — Trame > 80 octets → rejet silencieux."""
    keepalive(connected_devkit)
    connected_devkit.reset_input_buffer()
    payload = b"<" + b"A" * 95 + b">\n"
    connected_devkit.write(payload)
    out = read_for(connected_devkit, 1.0)
    assert "<ACK" not in out, "trame longue a déclenché un ACK"
    assert "<ERR" not in out, "trame longue a déclenché un ERR"
    assert "[FSM] ->" not in out, "trame longue a déclenché une transition d'état"
    keepalive(connected_devkit)
```

- [ ] **Step 10.2: Lancer le test**

Run: `pytest tests/integration/test_uart_devkit.py::test_sc_6_trame_longue -v -s`

Expected: `1 passed` en ~5 s.

- [ ] **Step 10.3: Commit**

```bash
git add tests/integration/test_uart_devkit.py
git commit -m "test(integration): porter sc 6 P8.6 (trame > 80 octets)"
```

---

### Task 11: Porter sc 7 — BTN sans framing

**Files:**
- Modify: `tests/integration/test_uart_devkit.py`

- [ ] **Step 11.1: Ajouter le test sc 7**

```python
@pytest.mark.devkit
def test_sc_7_btn_sans_framing(connected_devkit):
    """Sc 7 — Mode injection BTN x y (sans <>) → MOVE_REQ x y émis."""
    connected_devkit.reset_input_buffer()
    connected_devkit.write(b"BTN 5 5\n")
    out = wait_for(connected_devkit, r"<MOVE_REQ 5 5\|seq=(\d+)\|crc=", timeout=2.0)
    m = re.search(r"<MOVE_REQ 5 5\|seq=(\d+)\|crc=", out)
    assert m, "pas de MOVE_REQ 5 5 après BTN injection"
    move_seq = int(m.group(1))
    # Répondre ACK pour ne pas laisser la FSM dans un état sale
    connected_devkit.write(make_frame("ACK", seq=0, ack=move_seq))
    wait_for(connected_devkit, rf"<DONE\|seq=\d+\|ack={move_seq}", timeout=4.0)
```

- [ ] **Step 11.2: Lancer le test**

Run: `pytest tests/integration/test_uart_devkit.py::test_sc_7_btn_sans_framing -v -s`

Expected: `1 passed` en ~6 s.

- [ ] **Step 11.3: Commit**

```bash
git add tests/integration/test_uart_devkit.py
git commit -m "test(integration): porter sc 7 P8.6 (BTN sans framing)"
```

---

### Task 12: Porter sc 8 — ERR + CMD_RESET

**Files:**
- Modify: `tests/integration/test_uart_devkit.py`

- [ ] **Step 12.1: Ajouter le test sc 8**

```python
@pytest.mark.devkit
def test_sc_8_err_reset(connected_devkit):
    """Sc 8 — ERR initial → réémission 1Hz → CMD_RESET → BOOT_START.

    Note : dans le stub MotionControl, (99,99) est accepté ; l'ERR observée
    vient du watchdog UART (3 s sans trame valide pendant la phase passive),
    pas d'une erreur métier. Validation par erreur métier reportée à P11.
    """
    connected_devkit.reset_input_buffer()
    cmd_seq = 30
    connected_devkit.write(make_frame("CMD", "MOVE 99 99", seq=cmd_seq))
    out = wait_for(connected_devkit, r"<ERR ", timeout=4.0)
    assert "<ERR " in out, "pas de ERR initial reçu"
    # Réémission ERR pendant 2.5 s (informatif, on ne fail pas si pas vu)
    out2 = read_for(connected_devkit, 2.5)
    err_reemissions = re.findall(r"<ERR [^>]+>", out2)
    err_no_ack = [e for e in err_reemissions if "|ack=" not in e]
    # CMD_RESET → BOOT_START
    connected_devkit.reset_input_buffer()
    connected_devkit.write(make_frame("CMD_RESET", seq=0))
    out3 = wait_for(connected_devkit, r"<BOOT_START\|seq=0", timeout=4.0)
    assert "<BOOT_START" in out3, "pas de reboot après CMD_RESET"
    # Trace info pour debug si besoin (visible avec -s)
    print(f"[sc 8] ERR ré-émis sans ack : {len(err_no_ack)}")
```

- [ ] **Step 12.2: Lancer le test**

Run: `pytest tests/integration/test_uart_devkit.py::test_sc_8_err_reset -v -s`

Expected: `1 passed` en ~10-12 s (handshake + watchdog 3s + observation 2.5s + reset).

- [ ] **Step 12.3: Commit**

```bash
git add tests/integration/test_uart_devkit.py
git commit -m "test(integration): porter sc 8 P8.6 (ERR + CMD_RESET)"
```

---

### Task 13: Validation finale et mise à jour de la documentation

**Files:**
- Modify: `firmware/INTEGRATION_TESTS_PENDING.md` (cocher sc 9, ajuster l'introduction)
- Modify: `docs/00_plan_global.md` (cocher P8.6 entièrement, passer P8 à ✅)

- [ ] **Step 13.1: Lancer la suite complète des 8 scénarios**

Run: `pytest tests/integration/test_uart_devkit.py -v -s`

Expected: `8 passed in 50-60s`. Si un seul fail, investiguer (probablement état FSM résiduel ou timing).

- [ ] **Step 13.2: Vérifier la sélection isolée**

Run: `pytest tests/integration/test_uart_devkit.py::test_sc_5_crc_corrompu -v`

Expected: `1 passed`. Confirme l'isolation par fixture (sc 5 marche tout seul, sans dépendre de sc 1-4).

- [ ] **Step 13.3: Vérifier la suite globale (existants + integration)**

Run: `pytest -q`

Expected: `234 passed in XX.XXs` (226 existants + 8 nouveaux).

- [ ] **Step 13.4: Vérifier le filtre marker**

Run: `pytest -m "not devkit" -q`

Expected: `226 passed, 8 deselected`. Les 8 tests devkit sont bien exclus.

- [ ] **Step 13.5: (Optionnel, si DevKit débranchable) Vérifier le skip**

Débrancher le DevKit, puis :

Run: `pytest tests/integration/ -v`

Expected: `8 skipped` avec raison `DevKit ESP32 non détecté (aucun /dev/cu.usbserial-*)`.

Rebrancher avant la suite.

- [ ] **Step 13.6: Vérifier la non-régression du harness manuel**

Run: `python firmware/tests_devkit/run_p86_manual.py`

Expected: 8 PASS comme avant le refactor. Aucune régression introduite par l'extraction des helpers.

- [ ] **Step 13.7: Mettre à jour `firmware/INTEGRATION_TESTS_PENDING.md`**

Modifier la section sc 9 (lignes 89-96) pour la cocher :

```markdown
### 9. Test Python ↔ ESP32 réel (script automatisé)

- [x] Créer `tests/integration/test_uart_devkit.py` qui ouvre le port série réel
  et joue les scénarios 1-8 ci-dessus en automatique.

> **Statut :** ✅ portage pytest réalisé le 2026-05-06. Les 8 scénarios sont
> exécutables via `pytest tests/integration/test_uart_devkit.py -v` (avec DevKit
> branché) et auto-skippés sinon (marqueur `@pytest.mark.devkit`).
> `firmware/tests_devkit/run_p86_manual.py` reste utilisable pour debug
> interactif (`python firmware/tests_devkit/run_p86_manual.py 5` pour un sc isolé).
```

Modifier l'encadré du début (lignes 1-8) pour refléter le nouvel état :

```markdown
# Tests d'intégration P8.6 — pending DevKit

> **Cible :** lundi 2026-05-04, retour du DevKit ESP32. À exécuter avant de cocher P8.6 dans le plan global.
>
> **Mise à jour 2026-05-06 :** P8.6 sc 1-8 validés via le script automatisé
> `firmware/tests_devkit/run_p86_manual.py` puis portés en pytest dans
> `tests/integration/test_uart_devkit.py` (commits du même jour). Sc 9 (test
> pytest dans `tests/integration/`) **terminé**. Voir aussi la section P9.5 plus
> bas pour les tests E2E.
```

- [ ] **Step 13.8: Mettre à jour `docs/00_plan_global.md`**

Le format exact du fichier dépend de son état actuel. Procéder en deux temps :

1. Repérer les lignes :

```bash
grep -n "P8\." docs/00_plan_global.md
grep -n "^## P8\|^### P8\|🚧.*P8\|✅.*P8" docs/00_plan_global.md
```

2. Lire la section P8 puis appliquer ces deux modifications avec l'outil Edit :
   - Cocher P8.6 sc 9 (`- [ ] sc 9 ...` → `- [x] sc 9 ...`).
   - Passer le statut global de P8 de 🚧 à ✅.

Si le format observé diffère trop (ex: tableau Markdown au lieu de checklist), s'inspirer de la modif faite en commit `033a64d` qui a déjà coché P8.6 sc 1-8 et adapter à l'identique.

- [ ] **Step 13.9: Commit final**

```bash
git add firmware/INTEGRATION_TESTS_PENDING.md docs/00_plan_global.md
git commit -m "docs(p86): cocher sc 9 (portage pytest) et marquer P8 termine"
```

- [ ] **Step 13.10: (Optionnel) Mise à jour de la mémoire de session**

Le memory `project_brainstorm_progress.md` mentionne sc 9 P8.6 comme différé. Si le user le demande, mettre à jour cette mémoire pour refléter le nouvel état (sc 9 done, prochaine étape = breadboard avant PCB v2 le 10 mai).

---

## Récapitulatif

| # | Tâche | Output | Commit |
|---|---|---|---|
| 1 | Extraire helpers | `_uart_helpers.py` + refactor `run_p86_manual.py` | `refactor(devkit): extraire helpers UART` |
| 2 | `pyproject.toml` | Config pytest + marker | `build: ajouter pyproject.toml` |
| 3 | Structure `tests/integration/` | `__init__.py` + `conftest.py` | `test(integration): ajouter fixtures pytest` |
| 4 | Smoke test | Vérification fixture | `test(integration): ajouter smoke test` |
| 5 | sc 1 | `test_sc_1_handshake` | `test(integration): porter sc 1` |
| 6 | sc 2 | `test_sc_2_btn_humain` | `test(integration): porter sc 2` |
| 7 | sc 3 | `test_sc_3_cmd_ia` | `test(integration): porter sc 3` |
| 8 | sc 4 | `test_sc_4_idempotence` | `test(integration): porter sc 4` |
| 9 | sc 5 | `test_sc_5_crc_corrompu` | `test(integration): porter sc 5` |
| 10 | sc 6 | `test_sc_6_trame_longue` | `test(integration): porter sc 6` |
| 11 | sc 7 | `test_sc_7_btn_sans_framing` | `test(integration): porter sc 7` |
| 12 | sc 8 | `test_sc_8_err_reset` | `test(integration): porter sc 8` |
| 13 | Validation + docs | Cocher sc 9, P8 ✅ | `docs(p86): cocher sc 9` |

**Total estimé** : 13 commits, ~1h30 d'exécution avec DevKit (incluant les ~50-60 s de runtime de la suite finale × quelques relances).
