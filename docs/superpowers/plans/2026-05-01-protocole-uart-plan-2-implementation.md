# Protocole UART Plan 2 — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implémenter intégralement le protocole UART Plan 2 (côté Python ET ESP32) selon le spec figé dans [`2026-05-01-protocole-uart-plan-2-design.md`](../specs/2026-05-01-protocole-uart-plan-2-design.md). À la fin du plan, le firmware compile, le module Python est couvert ≥ 90 %, la documentation reflète le protocole final, et tout est prêt pour les tests d'intégration sur DevKit (P8.6) au retour du hardware lundi 2026-05-04.

**Architecture:** TDD strict côté Python (chaque comportement = test rouge → minimal code → vert → commit). Build-driven côté firmware ESP32 (modification → `pio run` → vérification compilation sans warning). Ordre privilégié : Python d'abord (auto-validable), puis firmware (seulement validable en compilation jusqu'au DevKit).

**Tech Stack:** Python 3.x + `pyserial` + `pytest` + `pytest-cov` (déjà au stack), Arduino C++ + ESP-IDF + FreeRTOS (déjà au stack), PlatformIO (`pio run` / `pio device monitor`).

**Phases couvertes du plan global :**
- ✅ P8.1 (design) — terminé (spec validé)
- 🟢 P8.2 (doc) — Task 19
- 🟢 P8.3 (refactor firmware UartLink) — Tasks 20-28
- 🟢 P8.4 (créer module Python `uart_client`) — Tasks 2-17
- 🟢 P8.5 (tests unitaires Python) — entrelacés avec Tasks 2-17 (TDD)
- 📅 P8.6 (tests intégration DevKit) — Task 30 = checklist pour lundi 2026-05-04

---

## Vue d'ensemble — fichiers créés / modifiés

### Côté Python

| Fichier | Action |
|---|---|
| `quoridor_engine/uart_client.py` | **Créer** — module client UART complet (~600 lignes attendues) |
| `quoridor_engine/__init__.py` | **Modifier** — exporter `UartClient` et les exceptions |
| `tests/test_uart_client.py` | **Créer** — tests unitaires (~800 lignes attendues) |
| `tests/conftest.py` | **Créer** — fixtures partagées (`MockSerial`, `MockClock`) |
| `requirements.txt` | **Modifier** — ajouter `pyserial>=3.5` |

### Côté firmware ESP32

| Fichier | Action |
|---|---|
| `firmware/src/UartLink.h` | **Réécrire** — nouvelle interface (sendFrame, log, tryGetFrame, dédup) |
| `firmware/src/UartLink.cpp` | **Réécrire** — implémentation complète avec CRC, mutex, FSM parser |
| `firmware/src/main.cpp` | **Modifier** — `Serial.println("BOOT_START"/"SETUP_DONE")` → `UartLink::sendFrame` |
| `firmware/src/GameController.cpp` | **Modifier** — tous les `Serial.print` → `UartLink::log` ; tous les `UartLink::sendLine` → `UartLink::sendFrame` ; intégration dédup |
| `firmware/src/ButtonMatrix.cpp` | **Modifier** — `Serial.println` → `UartLink::log("BTN", ...)` |
| `firmware/src/LedDriver.cpp` | **Modifier** — `Serial.print` → `UartLink::log("LED", ...)` |
| `firmware/src/LedAnimator.cpp` | **Modifier** — idem `UartLink::log("ANIM", ...)` |
| `firmware/src/MotionControl.cpp` | **Modifier** — idem `UartLink::log("MOT", ...)` |

### Documentation

| Fichier | Action |
|---|---|
| `docs/06_protocole_uart.md` | **Réécrire** — protocole final (P8.2) |
| `docs/00_plan_global.md` | **Modifier** — cocher P8.1, P8.2, P8.3, P8.4, P8.5 ; passer P8 ✅ |
| `CHANGELOG.md` | **Modifier** — entrée fin de phase P8 (sauf P8.6) |
| `docs/superpowers/specs/2026-05-01-protocole-uart-plan-2-design.md` | **Modifier** — figer les 3 vecteurs CRC dans §3.5 (Task 1) |

---

# Phase 1 — Python (P8.4 + P8.5 entrelacés en TDD)

## Task 1 : Figer les vecteurs CRC de référence

**Files:**
- Modify: `docs/superpowers/specs/2026-05-01-protocole-uart-plan-2-design.md` (§3.5)

- [ ] **Step 1 : Calculer les 3 vecteurs CRC en console**

Run:
```bash
python3 -c "
import binascii
for s in ['MOVE_REQ 3 4|seq=42', 'CMD MOVE 2 5|seq=43', 'KEEPALIVE|seq=0']:
    crc = binascii.crc_hqx(s.encode('ascii'), 0xFFFF)
    print(f'{s!r} -> 0x{crc:04X}')
"
```

Expected: trois lignes de la forme `'<input>' -> 0xXXXX`. Noter les 3 valeurs hexadécimales.

- [ ] **Step 2 : Mettre à jour le spec avec les 3 valeurs**

Editer `docs/superpowers/specs/2026-05-01-protocole-uart-plan-2-design.md`, dans la table §3.5 "Vecteurs de référence CRC", remplacer les `0x____` par les valeurs calculées.

- [ ] **Step 3 : Commit**

```bash
git add docs/superpowers/specs/2026-05-01-protocole-uart-plan-2-design.md
git commit -m "docs(spec): figer les 3 vecteurs CRC de reference"
```

---

## Task 2 : Squelette `uart_client.py` + hiérarchie d'exceptions

**Files:**
- Create: `quoridor_engine/uart_client.py`
- Test: `tests/test_uart_client.py`

- [ ] **Step 1 : Créer le test pour la hiérarchie d'exceptions**

Créer `tests/test_uart_client.py` :

```python
"""Tests unitaires pour le module quoridor_engine.uart_client."""

import pytest
from quoridor_engine.uart_client import (
    UartError,
    UartTimeoutError,
    UartProtocolError,
    UartVersionError,
    UartHardwareError,
)


class TestExceptionHierarchy:
    """La hierarchie d'exceptions doit refleter le spec §9.2."""

    def test_all_inherit_from_uart_error(self):
        for cls in (UartTimeoutError, UartProtocolError, UartVersionError, UartHardwareError):
            assert issubclass(cls, UartError)

    def test_uart_error_inherits_from_exception(self):
        assert issubclass(UartError, Exception)

    def test_uart_hardware_error_carries_code(self):
        err = UartHardwareError("MOTOR_TIMEOUT")
        assert err.code == "MOTOR_TIMEOUT"
        assert "MOTOR_TIMEOUT" in str(err)
```

- [ ] **Step 2 : Lancer le test (doit échouer car le module n'existe pas)**

Run: `pytest tests/test_uart_client.py::TestExceptionHierarchy -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'quoridor_engine.uart_client'`.

- [ ] **Step 3 : Créer le module avec les exceptions**

Créer `quoridor_engine/uart_client.py` :

```python
"""Client UART pour le protocole Plan 2 entre Raspberry Pi et ESP32.

Voir docs/superpowers/specs/2026-05-01-protocole-uart-plan-2-design.md
"""


class UartError(Exception):
    """Base pour toutes les erreurs UART."""


class UartTimeoutError(UartError):
    """Levee apres 3 essais CMD sans DONE."""


class UartProtocolError(UartError):
    """Levee si le pic de trames mal formees depasse un seuil anormal."""


class UartVersionError(UartError):
    """Levee si HELLO v=K recu ne correspond pas a la version Python attendue."""


class UartHardwareError(UartError):
    """Levee a la reception d'un ERR non-recuperable de l'ESP32."""

    def __init__(self, code: str, message: str = ""):
        self.code = code
        full_msg = f"{code}" if not message else f"{code}: {message}"
        super().__init__(full_msg)
```

- [ ] **Step 4 : Vérifier que les tests passent**

Run: `pytest tests/test_uart_client.py::TestExceptionHierarchy -v`
Expected: 3 tests PASS.

- [ ] **Step 5 : Commit**

```bash
git add quoridor_engine/uart_client.py tests/test_uart_client.py
git commit -m "feat(uart): squelette uart_client.py + hierarchie d'exceptions"
```

---

## Task 3 : Calcul CRC-16 CCITT-FALSE + tests vecteurs

**Files:**
- Modify: `quoridor_engine/uart_client.py`
- Modify: `tests/test_uart_client.py`

- [ ] **Step 1 : Écrire les tests pour le CRC sur les 3 vecteurs figés**

Ajouter dans `tests/test_uart_client.py` :

```python
from quoridor_engine.uart_client import compute_crc


class TestCrc:
    """CRC-16 CCITT-FALSE (poly 0x1021, init 0xFFFF) sur les vecteurs figes du spec §3.5."""

    @pytest.mark.parametrize("data,expected", [
        # Remplacer ces valeurs par les CRC reels figes a la Task 1 §3.5 du spec.
        # Format : (chaine_input, valeur_crc_attendue_en_int)
        ("MOVE_REQ 3 4|seq=42", 0xXXXX),  # à remplir
        ("CMD MOVE 2 5|seq=43", 0xXXXX),  # à remplir
        ("KEEPALIVE|seq=0", 0xXXXX),       # à remplir
    ])
    def test_crc_reference_vectors(self, data: str, expected: int):
        assert compute_crc(data.encode("ascii")) == expected

    def test_crc_returns_int_in_uint16_range(self):
        crc = compute_crc(b"hello")
        assert 0 <= crc <= 0xFFFF
        assert isinstance(crc, int)

    def test_crc_empty_returns_init_value(self):
        # CCITT-FALSE init=0xFFFF, sur input vide le CRC reste a init
        assert compute_crc(b"") == 0xFFFF
```

**Important :** remplacer les `0xXXXX` par les valeurs réelles calculées à la Task 1 (lire le spec mis à jour).

- [ ] **Step 2 : Lancer les tests (doivent échouer)**

Run: `pytest tests/test_uart_client.py::TestCrc -v`
Expected: FAIL avec `ImportError: cannot import name 'compute_crc'`.

- [ ] **Step 3 : Implémenter `compute_crc`**

Ajouter dans `quoridor_engine/uart_client.py` :

```python
import binascii


def compute_crc(data: bytes) -> int:
    """Calcule le CRC-16 CCITT-FALSE sur les octets fournis.

    Polynome 0x1021, valeur initiale 0xFFFF, sans reflexion, sans XOR final.
    Retourne un entier non signe sur 16 bits.
    """
    return binascii.crc_hqx(data, 0xFFFF)
```

- [ ] **Step 4 : Lancer les tests (doivent passer)**

Run: `pytest tests/test_uart_client.py::TestCrc -v`
Expected: 5 tests PASS.

- [ ] **Step 5 : Commit**

```bash
git add quoridor_engine/uart_client.py tests/test_uart_client.py
git commit -m "feat(uart): CRC-16 CCITT-FALSE avec vecteurs de reference"
```

---

## Task 4 : `Frame` dataclass + encode des requêtes

**Files:**
- Modify: `quoridor_engine/uart_client.py`
- Modify: `tests/test_uart_client.py`

- [ ] **Step 1 : Écrire les tests pour `Frame.encode` (requêtes sans ack)**

Ajouter dans `tests/test_uart_client.py` :

```python
from quoridor_engine.uart_client import Frame


class TestFrameEncodeRequests:
    """Encodage de trames sans ack (requetes ou messages spontanes)."""

    def test_encode_keepalive(self):
        f = Frame(type="KEEPALIVE", args="", seq=0)
        encoded = f.encode()
        # Calcul attendu : <KEEPALIVE|seq=0|crc=XXXX>\n
        assert encoded.startswith(b"<KEEPALIVE|seq=0|crc=")
        assert encoded.endswith(b">\n")

    def test_encode_move_req(self):
        f = Frame(type="MOVE_REQ", args="3 4", seq=42)
        encoded = f.encode()
        assert encoded.startswith(b"<MOVE_REQ 3 4|seq=42|crc=")
        assert encoded.endswith(b">\n")

    def test_encode_hello_with_version(self):
        f = Frame(type="HELLO", args="", seq=2, version=1)
        encoded = f.encode()
        # Ordre des champs : seq puis v puis crc
        assert encoded.startswith(b"<HELLO|seq=2|v=1|crc=")
        assert encoded.endswith(b">\n")

    def test_encode_err_without_ack(self):
        # ERR spontane (reemission periodique en ERROR)
        f = Frame(type="ERR", args="UART_LOST", seq=99)
        encoded = f.encode()
        assert encoded.startswith(b"<ERR UART_LOST|seq=99|crc=")
        assert b"|ack=" not in encoded

    def test_encode_crc_is_4_hex_uppercase(self):
        f = Frame(type="KEEPALIVE", args="", seq=0)
        encoded = f.encode()
        # Le CRC doit etre 4 chars hex MAJUSCULES
        crc_part = encoded.split(b"|crc=")[1].rstrip(b">\n")
        assert len(crc_part) == 4
        assert crc_part.decode("ascii") == crc_part.decode("ascii").upper()
        # Doit etre du hex valide
        int(crc_part, 16)

    def test_encode_seq_padded_zero_for_crc_only(self):
        # Le seq lui-meme n'est pas zero-padde (decimal naturel)
        f = Frame(type="KEEPALIVE", args="", seq=7)
        encoded = f.encode()
        assert b"|seq=7|" in encoded
        assert b"|seq=07|" not in encoded
```

- [ ] **Step 2 : Lancer les tests (doivent échouer)**

Run: `pytest tests/test_uart_client.py::TestFrameEncodeRequests -v`
Expected: FAIL avec `ImportError: cannot import name 'Frame'`.

- [ ] **Step 3 : Implémenter `Frame` et `Frame.encode`**

Ajouter dans `quoridor_engine/uart_client.py` :

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class Frame:
    """Une trame protocolaire decodee ou en cours d'encodage.

    type    : nom de la trame en MAJUSCULES (MOVE_REQ, ACK, CMD, ...)
    args    : arguments serializes en chaine (vide si pas d'arg)
    seq     : numero de sequence de l'emetteur (0-255)
    ack     : seq de la requete a laquelle on repond (None sinon)
    version : numero de version, present uniquement sur HELLO
    """
    type: str
    args: str
    seq: int
    ack: Optional[int] = None
    version: Optional[int] = None

    def encode(self) -> bytes:
        """Serialize la trame au format <TYPE [args]|seq=N[|ack=M][|v=K]|crc=XXXX>\\n."""
        # Construit la zone CRC (entre '<' et '|crc=')
        body = self.type
        if self.args:
            body += " " + self.args
        body += f"|seq={self.seq}"
        if self.ack is not None:
            body += f"|ack={self.ack}"
        if self.version is not None:
            body += f"|v={self.version}"

        crc = compute_crc(body.encode("ascii"))
        crc_str = f"{crc:04X}"  # 4 chars hex MAJUSCULES, padde a gauche

        return f"<{body}|crc={crc_str}>\n".encode("ascii")
```

- [ ] **Step 4 : Lancer les tests (doivent passer)**

Run: `pytest tests/test_uart_client.py::TestFrameEncodeRequests -v`
Expected: 6 tests PASS.

- [ ] **Step 5 : Commit**

```bash
git add quoridor_engine/uart_client.py tests/test_uart_client.py
git commit -m "feat(uart): Frame dataclass + encode des requetes"
```

---

## Task 5 : Encode des réponses (avec `ack=`)

**Files:**
- Modify: `tests/test_uart_client.py`

- [ ] **Step 1 : Écrire les tests pour les réponses avec `ack`**

Ajouter dans `tests/test_uart_client.py` :

```python
class TestFrameEncodeResponses:
    """Encodage de trames de reponse (avec ack=)."""

    def test_encode_ack(self):
        f = Frame(type="ACK", args="", seq=17, ack=42)
        encoded = f.encode()
        # Ordre : seq puis ack puis crc
        assert encoded.startswith(b"<ACK|seq=17|ack=42|crc=")
        assert encoded.endswith(b">\n")

    def test_encode_nack_with_reason(self):
        f = Frame(type="NACK", args="ILLEGAL", seq=18, ack=42)
        encoded = f.encode()
        assert encoded.startswith(b"<NACK ILLEGAL|seq=18|ack=42|crc=")

    def test_encode_done(self):
        f = Frame(type="DONE", args="", seq=44, ack=43)
        encoded = f.encode()
        assert encoded.startswith(b"<DONE|seq=44|ack=43|crc=")

    def test_encode_hello_ack(self):
        f = Frame(type="HELLO_ACK", args="", seq=0, ack=2)
        encoded = f.encode()
        assert encoded.startswith(b"<HELLO_ACK|seq=0|ack=2|crc=")

    def test_encode_err_with_ack_response_to_cmd(self):
        # ERR emis en reponse a une CMD echouee : porte un ack=
        f = Frame(type="ERR", args="MOTOR_TIMEOUT", seq=46, ack=43)
        encoded = f.encode()
        assert encoded.startswith(b"<ERR MOTOR_TIMEOUT|seq=46|ack=43|crc=")
```

- [ ] **Step 2 : Lancer les tests (doivent passer — l'encode actuel gère déjà `ack`)**

Run: `pytest tests/test_uart_client.py::TestFrameEncodeResponses -v`
Expected: 5 tests PASS sans modification du code (l'implémentation Task 4 est complète).

- [ ] **Step 3 : Commit**

```bash
git add tests/test_uart_client.py
git commit -m "test(uart): encode des trames de reponse (ack=)"
```

---

## Task 6 : `Frame.decode` — trames valides

**Files:**
- Modify: `quoridor_engine/uart_client.py`
- Modify: `tests/test_uart_client.py`

- [ ] **Step 1 : Écrire les tests pour `Frame.decode` sur trames valides**

Ajouter dans `tests/test_uart_client.py` :

```python
class TestFrameDecodeValid:
    """Decodage de trames valides bien formees."""

    def test_decode_keepalive(self):
        # Encoder puis decoder doit redonner la meme Frame
        original = Frame(type="KEEPALIVE", args="", seq=0)
        encoded = original.encode()
        decoded = Frame.decode(encoded.rstrip(b"\n"))
        assert decoded.type == "KEEPALIVE"
        assert decoded.args == ""
        assert decoded.seq == 0
        assert decoded.ack is None
        assert decoded.version is None

    def test_decode_move_req(self):
        original = Frame(type="MOVE_REQ", args="3 4", seq=42)
        decoded = Frame.decode(original.encode().rstrip(b"\n"))
        assert decoded.type == "MOVE_REQ"
        assert decoded.args == "3 4"
        assert decoded.seq == 42

    def test_decode_ack_with_ack_field(self):
        original = Frame(type="ACK", args="", seq=17, ack=42)
        decoded = Frame.decode(original.encode().rstrip(b"\n"))
        assert decoded.ack == 42
        assert decoded.seq == 17

    def test_decode_hello_with_version(self):
        original = Frame(type="HELLO", args="", seq=2, version=1)
        decoded = Frame.decode(original.encode().rstrip(b"\n"))
        assert decoded.version == 1

    def test_decode_err_with_ack(self):
        original = Frame(type="ERR", args="MOTOR_TIMEOUT", seq=46, ack=43)
        decoded = Frame.decode(original.encode().rstrip(b"\n"))
        assert decoded.type == "ERR"
        assert decoded.args == "MOTOR_TIMEOUT"
        assert decoded.ack == 43

    def test_decode_handles_bytes_with_trailing_newline(self):
        # Le decoder doit accepter une trame avec ou sans \n final
        original = Frame(type="KEEPALIVE", args="", seq=0)
        with_newline = original.encode()  # avec \n
        decoded = Frame.decode(with_newline)
        assert decoded.type == "KEEPALIVE"
```

- [ ] **Step 2 : Lancer les tests (doivent échouer)**

Run: `pytest tests/test_uart_client.py::TestFrameDecodeValid -v`
Expected: FAIL avec `AttributeError: type object 'Frame' has no attribute 'decode'`.

- [ ] **Step 3 : Implémenter `Frame.decode`**

Ajouter dans `quoridor_engine/uart_client.py`, dans la classe `Frame` :

```python
    @staticmethod
    def decode(raw: bytes) -> "Frame":
        """Decode une trame brute en Frame. Leve UartProtocolError si malformee.

        raw : octets de la trame, avec ou sans \\n final, avec les delimiteurs <>.
        """
        # Strip eventuel \n final et \r
        if raw.endswith(b"\n"):
            raw = raw[:-1]
        if raw.endswith(b"\r"):
            raw = raw[:-1]

        # Verifie longueur max
        if len(raw) > 80:
            raise UartProtocolError(f"trame trop longue ({len(raw)} > 80 octets)")

        # Verifie delimiteurs
        if not raw.startswith(b"<") or not raw.endswith(b">"):
            raise UartProtocolError("delimiteurs <> manquants ou mal places")

        # Retire <>
        inner = raw[1:-1].decode("ascii", errors="strict")

        # Split sur '|'
        parts = inner.split("|")
        if len(parts) < 2:
            raise UartProtocolError("trame sans champs metadata")

        # Premier champ : TYPE [args]
        head = parts[0]
        if " " in head:
            type_str, args_str = head.split(" ", 1)
        else:
            type_str = head
            args_str = ""

        # Verifie que TYPE est en majuscules valides
        if not type_str or not all(c.isupper() or c.isdigit() or c == "_" for c in type_str):
            raise UartProtocolError(f"TYPE invalide : {type_str!r}")

        # Le dernier champ doit etre crc=XXXX
        crc_field = parts[-1]
        if not crc_field.startswith("crc="):
            raise UartProtocolError("champ crc= manquant en fin")
        crc_value = crc_field[4:]
        if len(crc_value) != 4 or crc_value != crc_value.upper():
            raise UartProtocolError(f"format crc invalide : {crc_value!r}")
        try:
            crc_int = int(crc_value, 16)
        except ValueError:
            raise UartProtocolError(f"crc non hexadecimal : {crc_value!r}")

        # Champs intermediaires : seq= obligatoire, ack= et v= optionnels
        seq = None
        ack = None
        version = None
        for field in parts[1:-1]:
            if field.startswith("seq="):
                seq = int(field[4:])
                if not (0 <= seq <= 255):
                    raise UartProtocolError(f"seq hors plage : {seq}")
            elif field.startswith("ack="):
                ack = int(field[4:])
                if not (0 <= ack <= 255):
                    raise UartProtocolError(f"ack hors plage : {ack}")
            elif field.startswith("v="):
                version = int(field[2:])
            else:
                raise UartProtocolError(f"champ inconnu : {field!r}")

        if seq is None:
            raise UartProtocolError("champ seq= manquant")

        # Verifie le CRC sur la zone (TYPE [args]|seq=N[|ack=M][|v=K])
        crc_zone = inner.rsplit("|crc=", 1)[0]
        computed = compute_crc(crc_zone.encode("ascii"))
        if computed != crc_int:
            raise UartProtocolError(
                f"CRC invalide : recu 0x{crc_int:04X}, calcule 0x{computed:04X}"
            )

        return Frame(type=type_str, args=args_str, seq=seq, ack=ack, version=version)
```

- [ ] **Step 4 : Lancer les tests**

Run: `pytest tests/test_uart_client.py::TestFrameDecodeValid -v`
Expected: 6 tests PASS.

- [ ] **Step 5 : Commit**

```bash
git add quoridor_engine/uart_client.py tests/test_uart_client.py
git commit -m "feat(uart): Frame.decode pour trames valides"
```

---

## Task 7 : `Frame.decode` — rejets de trames mal formées

**Files:**
- Modify: `tests/test_uart_client.py`

- [ ] **Step 1 : Écrire les tests pour les cas de rejet**

Ajouter dans `tests/test_uart_client.py` :

```python
class TestFrameDecodeRejects:
    """Rejets de trames mal formees - couvre §3.6 du spec."""

    def test_reject_too_long(self):
        # Trame > 80 octets
        long_args = "A" * 80
        with pytest.raises(UartProtocolError, match="trop longue"):
            Frame.decode(f"<MOVE_REQ {long_args}|seq=0|crc=ABCD>".encode("ascii"))

    def test_reject_no_delimiters(self):
        with pytest.raises(UartProtocolError, match="delimiteurs"):
            Frame.decode(b"KEEPALIVE|seq=0|crc=ABCD")

    def test_reject_only_open_delimiter(self):
        with pytest.raises(UartProtocolError, match="delimiteurs"):
            Frame.decode(b"<KEEPALIVE|seq=0|crc=ABCD")

    def test_reject_lowercase_type(self):
        with pytest.raises(UartProtocolError, match="TYPE invalide"):
            Frame.decode(b"<keepalive|seq=0|crc=ABCD>")

    def test_reject_missing_seq(self):
        with pytest.raises(UartProtocolError, match="seq="):
            Frame.decode(b"<KEEPALIVE|crc=ABCD>")

    def test_reject_missing_crc(self):
        with pytest.raises(UartProtocolError, match="crc="):
            Frame.decode(b"<KEEPALIVE|seq=0>")

    def test_reject_lowercase_crc(self):
        with pytest.raises(UartProtocolError, match="format crc"):
            Frame.decode(b"<KEEPALIVE|seq=0|crc=abcd>")

    def test_reject_short_crc(self):
        with pytest.raises(UartProtocolError, match="format crc"):
            Frame.decode(b"<KEEPALIVE|seq=0|crc=AB>")

    def test_reject_crc_value_mismatch(self):
        # Trame valide en structure mais CRC incorrect
        with pytest.raises(UartProtocolError, match="CRC invalide"):
            Frame.decode(b"<KEEPALIVE|seq=0|crc=0000>")

    def test_reject_seq_out_of_range(self):
        with pytest.raises(UartProtocolError, match="seq hors plage"):
            # 256 hors plage [0,255]
            Frame.decode(b"<KEEPALIVE|seq=256|crc=ABCD>")

    def test_reject_unknown_metadata_field(self):
        with pytest.raises(UartProtocolError, match="champ inconnu"):
            Frame.decode(b"<KEEPALIVE|seq=0|foo=bar|crc=ABCD>")
```

- [ ] **Step 2 : Lancer les tests**

Run: `pytest tests/test_uart_client.py::TestFrameDecodeRejects -v`
Expected: 11 tests PASS (la logique de rejet est dans `Frame.decode` de la Task 6).

- [ ] **Step 3 : Commit**

```bash
git add tests/test_uart_client.py
git commit -m "test(uart): rejets de trames mal formees"
```

---

## Task 8 : Fixtures `MockSerial` et `MockClock`

**Files:**
- Create: `tests/conftest.py`
- Modify: `tests/test_uart_client.py`

- [ ] **Step 1 : Créer `tests/conftest.py` avec les fixtures**

Créer `tests/conftest.py` :

```python
"""Fixtures pytest partagees pour les tests du projet Quoridor."""

import threading
from collections import deque

import pytest


class MockSerial:
    """Mock de serial.Serial pour tests sans hardware.

    Buffer bidirectionnel en memoire :
    - tx : ce que le code testant ecrit (vu via inject_rx_from_external pour simuler la reponse de l'ESP32)
    - rx : ce que le code testant lit (rempli via inject_rx pour simuler des trames ESP32 entrantes)
    """

    def __init__(self):
        self._rx_buffer = bytearray()
        self._tx_buffer = bytearray()
        self._lock = threading.Lock()
        self.is_open = True
        self.timeout = 0.1

    def write(self, data: bytes) -> int:
        with self._lock:
            self._tx_buffer.extend(data)
        return len(data)

    def read(self, n: int = 1) -> bytes:
        with self._lock:
            if not self._rx_buffer:
                return b""
            chunk = bytes(self._rx_buffer[:n])
            del self._rx_buffer[:n]
            return chunk

    def readline(self) -> bytes:
        with self._lock:
            idx = self._rx_buffer.find(b"\n")
            if idx == -1:
                return b""
            line = bytes(self._rx_buffer[: idx + 1])
            del self._rx_buffer[: idx + 1]
            return line

    @property
    def in_waiting(self) -> int:
        return len(self._rx_buffer)

    def close(self):
        self.is_open = False

    # API helpers pour les tests
    def inject_rx(self, data: bytes) -> None:
        """Simule l'arrivee de bytes depuis l'ESP32."""
        with self._lock:
            self._rx_buffer.extend(data)

    def get_tx(self) -> bytes:
        """Recupere et vide le buffer TX (ce que le code a envoye a l'ESP32)."""
        with self._lock:
            data = bytes(self._tx_buffer)
            self._tx_buffer.clear()
            return data

    def peek_tx(self) -> bytes:
        """Lit le buffer TX sans le vider."""
        with self._lock:
            return bytes(self._tx_buffer)


class MockClock:
    """Horloge virtuelle pour tester les timeouts sans sleep reel."""

    def __init__(self, start: float = 0.0):
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


@pytest.fixture
def mock_serial():
    return MockSerial()


@pytest.fixture
def mock_clock():
    return MockClock()
```

- [ ] **Step 2 : Vérifier que les fixtures sont chargeables**

Run: `pytest tests/ --collect-only -q | head -20`
Expected: aucune erreur de collection. Les tests existants restent listés.

- [ ] **Step 3 : Test simple des fixtures**

Ajouter dans `tests/test_uart_client.py` :

```python
class TestMocks:
    """Sanity checks pour MockSerial et MockClock (fixtures conftest.py)."""

    def test_mock_serial_write_and_get_tx(self, mock_serial):
        mock_serial.write(b"hello")
        assert mock_serial.get_tx() == b"hello"
        assert mock_serial.get_tx() == b""  # vide apres lecture

    def test_mock_serial_inject_rx_and_readline(self, mock_serial):
        mock_serial.inject_rx(b"line1\nline2\n")
        assert mock_serial.readline() == b"line1\n"
        assert mock_serial.readline() == b"line2\n"
        assert mock_serial.readline() == b""

    def test_mock_clock_advance(self, mock_clock):
        assert mock_clock() == 0.0
        mock_clock.advance(15.0)
        assert mock_clock() == 15.0
```

- [ ] **Step 4 : Lancer les tests**

Run: `pytest tests/test_uart_client.py::TestMocks -v`
Expected: 3 tests PASS.

- [ ] **Step 5 : Commit**

```bash
git add tests/conftest.py tests/test_uart_client.py
git commit -m "test(uart): fixtures MockSerial et MockClock"
```

---

## Task 9 : `UartClient` — init + thread de lecture

**Files:**
- Modify: `quoridor_engine/uart_client.py`
- Modify: `tests/test_uart_client.py`

- [ ] **Step 1 : Écrire les tests pour `UartClient` minimal**

Ajouter dans `tests/test_uart_client.py` :

```python
from quoridor_engine.uart_client import UartClient


class TestUartClientInit:
    """Construction de UartClient + thread de lecture."""

    def test_init_does_not_open_port(self, mock_serial, mock_clock):
        # L'ouverture est differee a connect()
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        assert client.is_connected is False

    def test_close_stops_reader_thread(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client._start_reader_thread()  # API interne pour tests
        assert client._reader_thread is not None
        assert client._reader_thread.is_alive()
        client.close()
        # Le thread doit s'arreter rapidement
        client._reader_thread.join(timeout=2)
        assert not client._reader_thread.is_alive()

    def test_reader_thread_parses_incoming_frames(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client._start_reader_thread()

        # Inject une trame valide
        f = Frame(type="KEEPALIVE", args="", seq=5)
        mock_serial.inject_rx(f.encode())

        # Laisser le thread lire (court timeout)
        import time
        time.sleep(0.2)

        # La frame doit etre dans la queue interne
        received = client._rx_queue.get(timeout=1)
        assert received.type == "KEEPALIVE"
        assert received.seq == 5

        client.close()

    def test_reader_thread_classifies_debug_lines(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client._start_reader_thread()

        mock_serial.inject_rx(b"[FSM] BOOT -> WAITING_RPI\n")
        import time
        time.sleep(0.2)

        # La ligne de debug doit etre dans le buffer debug, pas dans la rx_queue
        assert client._debug_lines  # non vide
        assert "[FSM]" in client._debug_lines[0]

        client.close()
```

- [ ] **Step 2 : Lancer les tests (doivent échouer)**

Run: `pytest tests/test_uart_client.py::TestUartClientInit -v`
Expected: FAIL avec `ImportError: cannot import name 'UartClient'`.

- [ ] **Step 3 : Implémenter `UartClient` minimal avec thread de lecture**

Ajouter dans `quoridor_engine/uart_client.py` :

```python
import queue
import threading
import time
from typing import Callable, Optional


class UartClient:
    """Client UART Plan 2 cote Raspberry Pi (Python).

    Voir docs/superpowers/specs/2026-05-01-protocole-uart-plan-2-design.md
    """

    PROTOCOL_VERSION = 1
    MAX_DEBUG_LINES = 200  # buffer circulaire pour les logs ESP32

    def __init__(
        self,
        serial_port,
        clock: Optional[Callable[[], float]] = None,
        expected_version: int = PROTOCOL_VERSION,
    ):
        """
        serial_port : objet compatible serial.Serial (avec write/readline/in_waiting/close)
        clock : callable retournant un float monotone (default time.monotonic) ; injectable pour tests
        expected_version : version protocole attendue (default = PROTOCOL_VERSION)
        """
        self._serial = serial_port
        self._clock = clock or time.monotonic
        self._expected_version = expected_version

        self._tx_seq = 0
        self._tx_seq_lock = threading.Lock()
        self._last_request_seq: Optional[int] = None
        self._last_err_received: Optional[str] = None

        self._rx_queue: "queue.Queue[Frame]" = queue.Queue()
        self._debug_lines: list[str] = []  # logs ESP32 (lignes ne commencant pas par '<')
        self._read_buffer = bytearray()

        self._reader_thread: Optional[threading.Thread] = None
        self._stop_reader = threading.Event()

        self.is_connected = False

    def _next_tx_seq(self) -> int:
        """Retourne le seq courant et incremente (modulo 256)."""
        with self._tx_seq_lock:
            seq = self._tx_seq
            self._tx_seq = (self._tx_seq + 1) & 0xFF
            return seq

    def _start_reader_thread(self) -> None:
        """Demarre le thread de lecture du port serie. Idempotent."""
        if self._reader_thread is not None and self._reader_thread.is_alive():
            return
        self._stop_reader.clear()
        self._reader_thread = threading.Thread(
            target=self._reader_loop, daemon=True, name="UartReader"
        )
        self._reader_thread.start()

    def _reader_loop(self) -> None:
        """Boucle de lecture. Decoupe en lignes, classe trame protocole / debug."""
        while not self._stop_reader.is_set():
            try:
                chunk = self._serial.read(64)  # timeout cote serial
            except Exception:
                break
            if chunk:
                self._read_buffer.extend(chunk)
            # Decoupe en lignes
            while True:
                idx = self._read_buffer.find(b"\n")
                if idx == -1:
                    # Protection : si buffer > 80 octets sans \n, jeter
                    if len(self._read_buffer) > 80:
                        self._read_buffer.clear()
                    break
                raw_line = bytes(self._read_buffer[: idx + 1])
                del self._read_buffer[: idx + 1]
                self._dispatch_line(raw_line)

    def _dispatch_line(self, raw_line: bytes) -> None:
        """Classe une ligne recue : trame protocole ou log debug."""
        # Strip \r\n
        stripped = raw_line.rstrip(b"\r\n")
        if not stripped:
            return
        # Test sur le PREMIER caractere uniquement
        if stripped[0:1] == b"<":
            try:
                frame = Frame.decode(stripped)
                self._rx_queue.put(frame)
            except UartProtocolError:
                # Rejet silencieux (cf. §3.6 spec)
                pass
        else:
            # Ligne de debug ESP32
            try:
                line_str = stripped.decode("ascii", errors="replace")
            except Exception:
                return
            self._debug_lines.append(line_str)
            # Rotation simple
            if len(self._debug_lines) > self.MAX_DEBUG_LINES:
                self._debug_lines = self._debug_lines[-self.MAX_DEBUG_LINES :]

    def close(self) -> None:
        """Arrete le thread de lecture et ferme le port serie."""
        self._stop_reader.set()
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=2)
        try:
            self._serial.close()
        except Exception:
            pass
        self.is_connected = False
```

- [ ] **Step 4 : Lancer les tests**

Run: `pytest tests/test_uart_client.py::TestUartClientInit -v`
Expected: 4 tests PASS.

- [ ] **Step 5 : Commit**

```bash
git add quoridor_engine/uart_client.py tests/test_uart_client.py
git commit -m "feat(uart): UartClient init + thread de lecture"
```

---

## Task 10 : Handshake `HELLO` / `HELLO_ACK` + version

**Files:**
- Modify: `quoridor_engine/uart_client.py`
- Modify: `tests/test_uart_client.py`

- [ ] **Step 1 : Écrire les tests pour le handshake**

Ajouter dans `tests/test_uart_client.py` :

```python
class TestHandshake:
    """Handshake HELLO / HELLO_ACK + verification version (§6.6 spec)."""

    def test_connect_sends_hello_ack_on_hello_v1(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock, expected_version=1)
        client._start_reader_thread()

        # Simule reception HELLO v=1
        hello = Frame(type="HELLO", args="", seq=2, version=1)
        mock_serial.inject_rx(hello.encode())

        # connect doit aboutir
        client.connect(timeout=1.0)
        assert client.is_connected

        # Verifier qu'on a bien envoye HELLO_ACK avec ack=2
        sent = mock_serial.get_tx()
        assert b"<HELLO_ACK|" in sent
        assert b"|ack=2|" in sent

        client.close()

    def test_connect_raises_version_error_on_mismatch(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock, expected_version=1)
        client._start_reader_thread()

        # Simule reception HELLO v=2 (incompatible)
        hello = Frame(type="HELLO", args="", seq=2, version=2)
        mock_serial.inject_rx(hello.encode())

        with pytest.raises(UartVersionError, match="version"):
            client.connect(timeout=1.0)

        client.close()

    def test_connect_raises_timeout_if_no_hello(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock, expected_version=1)
        client._start_reader_thread()

        with pytest.raises(UartTimeoutError, match="HELLO"):
            client.connect(timeout=0.5)

        client.close()
```

- [ ] **Step 2 : Lancer les tests (doivent échouer)**

Run: `pytest tests/test_uart_client.py::TestHandshake -v`
Expected: FAIL avec `AttributeError: 'UartClient' object has no attribute 'connect'`.

- [ ] **Step 3 : Implémenter `connect()`**

Ajouter dans `quoridor_engine/uart_client.py`, dans `UartClient` :

```python
    def connect(self, timeout: float = 3.0) -> None:
        """Realise le handshake HELLO/HELLO_ACK et verifie la version.

        Bloque jusqu'a reception d'un HELLO valide ou timeout.
        Leve UartTimeoutError si pas de HELLO recu, UartVersionError si version incompatible.
        """
        self._start_reader_thread()

        deadline = self._clock() + timeout
        while self._clock() < deadline:
            try:
                frame = self._rx_queue.get(timeout=0.05)
            except queue.Empty:
                continue

            if frame.type == "HELLO":
                # Verifie version
                if frame.version != self._expected_version:
                    raise UartVersionError(
                        f"version protocole incompatible : "
                        f"recu v={frame.version}, attendu v={self._expected_version}"
                    )
                # Repond HELLO_ACK avec ack=seq du HELLO
                self._send_response(type="HELLO_ACK", args="", ack=frame.seq)
                self.is_connected = True
                return

        raise UartTimeoutError(f"aucun HELLO recu apres {timeout}s")

    def _send_frame(self, frame: Frame) -> None:
        """Envoie une frame deja construite sur le port serie."""
        self._serial.write(frame.encode())

    def _send_response(self, type: str, args: str, ack: int) -> None:
        """Construit et envoie une reponse (avec ack=)."""
        seq = self._next_tx_seq()
        frame = Frame(type=type, args=args, seq=seq, ack=ack)
        self._send_frame(frame)

    def _send_request(self, type: str, args: str, version: Optional[int] = None) -> int:
        """Construit et envoie une requete. Retourne le seq utilise."""
        seq = self._next_tx_seq()
        frame = Frame(type=type, args=args, seq=seq, version=version)
        self._send_frame(frame)
        return seq
```

- [ ] **Step 4 : Lancer les tests**

Run: `pytest tests/test_uart_client.py::TestHandshake -v`
Expected: 3 tests PASS.

- [ ] **Step 5 : Commit**

```bash
git add quoridor_engine/uart_client.py tests/test_uart_client.py
git commit -m "feat(uart): handshake HELLO/HELLO_ACK + verification version"
```

---

## Task 11 : Émission `KEEPALIVE` périodique

**Files:**
- Modify: `quoridor_engine/uart_client.py`
- Modify: `tests/test_uart_client.py`

- [ ] **Step 1 : Écrire les tests**

Ajouter dans `tests/test_uart_client.py` :

```python
class TestKeepalive:
    """Emission de KEEPALIVE - methode appelable par le main loop."""

    def test_send_keepalive_writes_frame(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True

        client.send_keepalive()

        sent = mock_serial.get_tx()
        assert sent.startswith(b"<KEEPALIVE|seq=")
        assert sent.endswith(b">\n")

    def test_send_keepalive_increments_seq(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True

        client.send_keepalive()
        client.send_keepalive()

        sent = mock_serial.get_tx()
        # On doit voir seq=0 puis seq=1 (compteur initialise a 0)
        assert b"|seq=0|" in sent
        assert b"|seq=1|" in sent

    def test_send_keepalive_no_op_if_not_connected(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        # is_connected reste False (pas d'appel a connect)

        client.send_keepalive()

        # Rien ne doit etre envoye si pas connecte
        assert mock_serial.get_tx() == b""
```

- [ ] **Step 2 : Lancer les tests (doivent échouer)**

Run: `pytest tests/test_uart_client.py::TestKeepalive -v`
Expected: FAIL avec `AttributeError: 'UartClient' object has no attribute 'send_keepalive'`.

- [ ] **Step 3 : Implémenter `send_keepalive`**

Ajouter dans `quoridor_engine/uart_client.py`, dans `UartClient` :

```python
    def send_keepalive(self) -> None:
        """Envoie une trame KEEPALIVE. A appeler periodiquement (1 s) depuis le main loop.

        No-op si pas connecte.
        """
        if not self.is_connected:
            return
        self._send_request(type="KEEPALIVE", args="")
```

- [ ] **Step 4 : Lancer les tests**

Run: `pytest tests/test_uart_client.py::TestKeepalive -v`
Expected: 3 tests PASS.

- [ ] **Step 5 : Commit**

```bash
git add quoridor_engine/uart_client.py tests/test_uart_client.py
git commit -m "feat(uart): emission KEEPALIVE + sequencement"
```

---

## Task 12 : Réception `MOVE_REQ`/`WALL_REQ` + `send_ack`/`send_nack`

**Files:**
- Modify: `quoridor_engine/uart_client.py`
- Modify: `tests/test_uart_client.py`

- [ ] **Step 1 : Écrire les tests**

Ajouter dans `tests/test_uart_client.py` :

```python
class TestReceiveIntents:
    """Reception MOVE_REQ / WALL_REQ et reponse ACK/NACK."""

    def test_receive_returns_move_req(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True
        client._start_reader_thread()

        f = Frame(type="MOVE_REQ", args="3 4", seq=42)
        mock_serial.inject_rx(f.encode())

        intent = client.receive(timeout=1.0)
        assert intent.type == "MOVE_REQ"
        assert intent.args == "3 4"
        assert intent.seq == 42

        client.close()

    def test_receive_returns_none_on_timeout(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True
        client._start_reader_thread()

        intent = client.receive(timeout=0.1)
        assert intent is None

        client.close()

    def test_send_ack_carries_request_seq(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True

        client.send_ack(request_seq=42)

        sent = mock_serial.get_tx()
        assert sent.startswith(b"<ACK|seq=")
        assert b"|ack=42|" in sent

    def test_send_nack_carries_reason_and_request_seq(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True

        client.send_nack(request_seq=42, reason="ILLEGAL")

        sent = mock_serial.get_tx()
        assert sent.startswith(b"<NACK ILLEGAL|seq=")
        assert b"|ack=42|" in sent
```

- [ ] **Step 2 : Lancer les tests**

Run: `pytest tests/test_uart_client.py::TestReceiveIntents -v`
Expected: FAIL (méthodes manquantes).

- [ ] **Step 3 : Implémenter `receive`, `send_ack`, `send_nack`**

Ajouter dans `quoridor_engine/uart_client.py`, dans `UartClient` :

```python
    def receive(self, timeout: Optional[float] = None) -> Optional[Frame]:
        """Recupere la prochaine intention recue (MOVE_REQ, WALL_REQ, ERR, ...) ou None si timeout.

        timeout : duree max d'attente en secondes. None = bloquant.
        """
        try:
            return self._rx_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def send_ack(self, request_seq: int) -> None:
        """Repond ACK a une requete dont le seq est request_seq."""
        if not self.is_connected:
            return
        self._send_response(type="ACK", args="", ack=request_seq)

    def send_nack(self, request_seq: int, reason: str) -> None:
        """Repond NACK avec une raison (mot-cle MAJUSCULES)."""
        if not self.is_connected:
            return
        self._send_response(type="NACK", args=reason, ack=request_seq)
```

- [ ] **Step 4 : Lancer les tests**

Run: `pytest tests/test_uart_client.py::TestReceiveIntents -v`
Expected: 4 tests PASS.

- [ ] **Step 5 : Commit**

```bash
git add quoridor_engine/uart_client.py tests/test_uart_client.py
git commit -m "feat(uart): reception MOVE_REQ/WALL_REQ + send_ack/send_nack"
```

---

## Task 13 : Émission `CMD` avec retry idempotent

**Files:**
- Modify: `quoridor_engine/uart_client.py`
- Modify: `tests/test_uart_client.py`

- [ ] **Step 1 : Écrire les tests pour `send_cmd` avec retry**

Ajouter dans `tests/test_uart_client.py` :

```python
class TestSendCmd:
    """Emission CMD avec retry idempotent (§5.5 spec)."""

    def test_send_cmd_returns_on_done_received(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True
        client._start_reader_thread()

        # Lance send_cmd dans un thread (car bloquant)
        result = []
        def runner():
            try:
                client.send_cmd("CMD", "MOVE 2 5")
                result.append("done")
            except Exception as e:
                result.append(("err", e))

        t = threading.Thread(target=runner, daemon=True)
        t.start()

        # Petite attente pour que la CMD parte
        import time as _t
        _t.sleep(0.1)

        # Recupere le seq utilise dans la trame TX
        sent = mock_serial.peek_tx()
        # Trouve seq=N dans la trame
        import re
        m = re.search(rb"\|seq=(\d+)\|", sent)
        assert m is not None
        seq_used = int(m.group(1))

        # Simule la reception de DONE avec le bon ack
        done = Frame(type="DONE", args="", seq=99, ack=seq_used)
        mock_serial.inject_rx(done.encode())

        t.join(timeout=2)
        assert result == ["done"]

        client.close()

    def test_send_cmd_retries_with_same_seq_on_timeout(self, mock_serial, mock_clock):
        """Apres 15 s sans DONE, retransmettre la meme trame avec le meme seq."""
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True
        client._start_reader_thread()

        # Configure timeout court pour test (override en injectant directement)
        client._cmd_timeout_seconds = 1.0

        result = []
        def runner():
            try:
                client.send_cmd("CMD", "MOVE 2 5")
                result.append("done")
            except UartTimeoutError as e:
                result.append(("timeout", e))

        t = threading.Thread(target=runner, daemon=True)
        t.start()

        import time as _t
        _t.sleep(0.1)
        first_tx = mock_serial.peek_tx()
        import re
        first_seq = int(re.search(rb"\|seq=(\d+)\|", first_tx).group(1))

        # Avance l'horloge mock pour declencher le 1er retry
        mock_clock.advance(1.5)
        _t.sleep(0.1)

        full_tx = mock_serial.peek_tx()
        # On doit voir 2 trames maintenant : envoi initial + retry, MEME seq
        all_seqs = re.findall(rb"\|seq=(\d+)\|", full_tx)
        assert len(all_seqs) >= 2
        assert all_seqs[0] == all_seqs[1]
        assert int(all_seqs[0]) == first_seq

        # Resoudre proprement
        done = Frame(type="DONE", args="", seq=99, ack=first_seq)
        mock_serial.inject_rx(done.encode())
        t.join(timeout=2)

        client.close()

    def test_send_cmd_raises_timeout_after_3_attempts(self, mock_serial, mock_clock):
        """3 essais sans DONE -> UartTimeoutError."""
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True
        client._start_reader_thread()
        client._cmd_timeout_seconds = 0.1

        result = []
        def runner():
            try:
                client.send_cmd("CMD", "MOVE 2 5")
                result.append("done")
            except UartTimeoutError as e:
                result.append("timeout")

        t = threading.Thread(target=runner, daemon=True)
        t.start()

        import time as _t
        # Avance assez pour 3 timeouts
        for _ in range(4):
            _t.sleep(0.15)
            mock_clock.advance(0.2)

        t.join(timeout=2)
        assert result == ["timeout"]

        client.close()
```

- [ ] **Step 2 : Lancer les tests**

Run: `pytest tests/test_uart_client.py::TestSendCmd -v`
Expected: FAIL (`send_cmd` n'existe pas).

- [ ] **Step 3 : Implémenter `send_cmd` avec retry idempotent**

Ajouter dans `quoridor_engine/uart_client.py`, dans `UartClient` :

```python
    # Constantes timing (overridables pour tests)
    CMD_TIMEOUT_SECONDS = 15.0
    CMD_MAX_ATTEMPTS = 3

    def __init__(self, *args, **kwargs):
        # ... appel init existant ...
        # Override possible en tests via _cmd_timeout_seconds attribute
        self._cmd_timeout_seconds = self.CMD_TIMEOUT_SECONDS

    def send_cmd(self, type: str, args: str) -> None:
        """Envoie une CMD au firmware ESP32 avec retry idempotent.

        Bloque jusqu'a reception du DONE correspondant ou epuisement des essais.
        En cas d'echec apres 3 essais : leve UartTimeoutError.
        En cas d'ERR recu pour cette CMD : leve UartHardwareError.
        """
        if not self.is_connected:
            raise UartError("client non connecte")

        seq = self._next_tx_seq()
        frame = Frame(type=type, args=args, seq=seq)
        self._last_request_seq = seq

        for attempt in range(1, self.CMD_MAX_ATTEMPTS + 1):
            self._send_frame(frame)  # meme seq sur tous les essais
            deadline = self._clock() + self._cmd_timeout_seconds

            while self._clock() < deadline:
                try:
                    received = self._rx_queue.get(timeout=0.05)
                except queue.Empty:
                    continue

                # Match DONE
                if received.type == "DONE" and received.ack == seq:
                    self._last_request_seq = None
                    return

                # Match ERR avec ack=seq -> erreur hardware sur cette CMD
                if received.type == "ERR" and received.ack == seq:
                    self._last_request_seq = None
                    raise UartHardwareError(received.args or "UNKNOWN")

                # Frame non liee a cette requete : remettre dans la queue pour autres consommateurs
                # (note : cela peut creer un loop, mais en pratique receive() lit en parallele)
                # Pour simplifier on remet en file uniquement les autres types de reponse
                if received.type in ("ACK", "NACK", "DONE", "ERR", "HELLO", "HELLO_ACK"):
                    pass  # ces reponses orphelines sont simplement ignorees
                else:
                    self._rx_queue.put(received)

            # Timeout sur cet essai, on retente (sauf si dernier essai)

        # 3 essais epuises sans DONE
        self._last_request_seq = None
        raise UartTimeoutError(
            f"CMD {type} {args} : aucun DONE apres {self.CMD_MAX_ATTEMPTS} essais"
        )
```

**Note importante :** la modification ci-dessus du `__init__` est en pseudo-code. Adapter pour intégrer dans le `__init__` existant (Task 9) en ajoutant `self._cmd_timeout_seconds = self.CMD_TIMEOUT_SECONDS` à la fin.

- [ ] **Step 4 : Adapter `__init__` proprement**

Editer la fin de `__init__` pour ajouter :

```python
        self._cmd_timeout_seconds = self.CMD_TIMEOUT_SECONDS
```

- [ ] **Step 5 : Lancer les tests**

Run: `pytest tests/test_uart_client.py::TestSendCmd -v`
Expected: 3 tests PASS.

- [ ] **Step 6 : Commit**

```bash
git add quoridor_engine/uart_client.py tests/test_uart_client.py
git commit -m "feat(uart): send_cmd avec retry idempotent (3 essais, timeout 15s)"
```

---

## Task 14 : Réception `ERR` + classement récupérable / non-récupérable

**Files:**
- Modify: `quoridor_engine/uart_client.py`
- Modify: `tests/test_uart_client.py`

- [ ] **Step 1 : Écrire les tests**

Ajouter dans `tests/test_uart_client.py` :

```python
class TestErrHandling:
    """Reception et classement des ERR (§4.3 spec)."""

    def test_err_recoverable_codes(self):
        from quoridor_engine.uart_client import is_recoverable_err
        assert is_recoverable_err("UART_LOST") is True
        assert is_recoverable_err("BUTTON_MATRIX") is True

    def test_err_unrecoverable_codes(self):
        from quoridor_engine.uart_client import is_recoverable_err
        for code in ["MOTOR_TIMEOUT", "LIMIT_UNEXPECTED", "HOMING_FAILED",
                     "I2C_NACK", "BOOT_I2C", "BOOT_LED", "BOOT_HOMING"]:
            assert is_recoverable_err(code) is False, f"{code} ne doit pas etre recuperable"

    def test_handle_err_recoverable_sends_cmd_reset(self, mock_serial, mock_clock):
        """Reception ERR UART_LOST -> envoi auto de CMD_RESET."""
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True
        client._start_reader_thread()

        err = Frame(type="ERR", args="UART_LOST", seq=99)
        mock_serial.inject_rx(err.encode())

        # Le main loop appelle handle_received_err pour traiter
        import time as _t
        _t.sleep(0.2)
        # Recupere le frame de la queue
        frame = client.receive(timeout=0.5)
        action = client.handle_err_received(frame)

        assert action == "RESET_SENT"
        sent = mock_serial.get_tx()
        assert b"<CMD_RESET|" in sent

        client.close()

    def test_handle_err_non_recoverable_raises_hardware_error(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True
        client._start_reader_thread()

        err = Frame(type="ERR", args="MOTOR_TIMEOUT", seq=99)
        mock_serial.inject_rx(err.encode())

        import time as _t
        _t.sleep(0.2)
        frame = client.receive(timeout=0.5)

        with pytest.raises(UartHardwareError, match="MOTOR_TIMEOUT"):
            client.handle_err_received(frame)

        client.close()
```

- [ ] **Step 2 : Lancer les tests**

Run: `pytest tests/test_uart_client.py::TestErrHandling -v`
Expected: FAIL (`is_recoverable_err`, `handle_err_received` manquants).

- [ ] **Step 3 : Implémenter le classement et le handler**

Ajouter dans `quoridor_engine/uart_client.py` :

```python
RECOVERABLE_ERR_CODES = frozenset([
    "UART_LOST",
    "BUTTON_MATRIX",
])

NON_RECOVERABLE_ERR_CODES = frozenset([
    "MOTOR_TIMEOUT",
    "LIMIT_UNEXPECTED",
    "HOMING_FAILED",
    "I2C_NACK",
    "BOOT_I2C",
    "BOOT_LED",
    "BOOT_HOMING",
])


def is_recoverable_err(code: str) -> bool:
    """Retourne True si le code d'erreur ESP32 est traitable par CMD_RESET auto."""
    return code in RECOVERABLE_ERR_CODES
```

Et ajouter dans `UartClient` :

```python
    def handle_err_received(self, frame: Frame) -> str:
        """Traite une trame ERR recue de l'ESP32.

        Si recuperable : envoie CMD_RESET, retourne "RESET_SENT".
        Si non recuperable : leve UartHardwareError.
        """
        if frame.type != "ERR":
            raise ValueError(f"handle_err_received attend une trame ERR, recu {frame.type}")

        code = frame.args or "UNKNOWN"

        # Dedup logs : ne pas spammer si meme code que le dernier recu
        if code != self._last_err_received:
            # log unique a chaque nouveau code
            self._last_err_received = code

        if is_recoverable_err(code):
            self.send_cmd_reset()
            return "RESET_SENT"
        else:
            raise UartHardwareError(code)

    def send_cmd_reset(self) -> None:
        """Envoie CMD_RESET pour reboot logiciel de l'ESP32."""
        if not self.is_connected:
            return
        self._send_request(type="CMD_RESET", args="")
```

- [ ] **Step 4 : Lancer les tests**

Run: `pytest tests/test_uart_client.py::TestErrHandling -v`
Expected: 4 tests PASS.

- [ ] **Step 5 : Commit**

```bash
git add quoridor_engine/uart_client.py tests/test_uart_client.py
git commit -m "feat(uart): reception ERR + auto CMD_RESET pour codes recuperables"
```

---

## Task 15 : Démarrage avec ESP32 en `ERROR` (cas RPi rebooté)

**Files:**
- Modify: `quoridor_engine/uart_client.py`
- Modify: `tests/test_uart_client.py`

- [ ] **Step 1 : Écrire le test du cas §6.6 du spec**

Ajouter dans `tests/test_uart_client.py` :

```python
class TestConnectWithEspInError:
    """§6.6 : RPi rebooté + ESP32 deja en ERROR."""

    def test_connect_sends_reset_if_only_err_received(self, mock_serial, mock_clock):
        """Si on recoit ERR au lieu de HELLO -> envoyer CMD_RESET et attendre HELLO."""
        client = UartClient(serial_port=mock_serial, clock=mock_clock, expected_version=1)
        client._start_reader_thread()

        # 1) ESP32 envoie ERR au lieu de HELLO
        err = Frame(type="ERR", args="UART_LOST", seq=99)
        mock_serial.inject_rx(err.encode())

        # 2) Connect doit envoyer CMD_RESET, puis attendre HELLO

        # Lance connect dans un thread
        result = []
        def runner():
            try:
                client.connect(timeout=2.0)
                result.append("connected")
            except Exception as e:
                result.append(("err", type(e).__name__))

        t = threading.Thread(target=runner, daemon=True)
        t.start()

        # Attendre que connect ait envoye CMD_RESET
        import time as _t
        _t.sleep(0.5)

        sent = mock_serial.get_tx()
        assert b"<CMD_RESET|" in sent

        # 3) Simuler le reboot ESP32 : BOOT_START puis HELLO
        boot = Frame(type="BOOT_START", args="", seq=0)
        hello = Frame(type="HELLO", args="", seq=2, version=1)
        mock_serial.inject_rx(boot.encode() + hello.encode())

        t.join(timeout=3)
        assert result == ["connected"]

        client.close()
```

- [ ] **Step 2 : Lancer (doit échouer car logique pas implémentée)**

Run: `pytest tests/test_uart_client.py::TestConnectWithEspInError -v`
Expected: FAIL — `connect` actuel ne gère pas ce cas.

- [ ] **Step 3 : Mettre à jour `connect()` pour gérer le cas ESP32 en ERROR**

Modifier la méthode `connect` dans `UartClient` :

```python
    def connect(self, timeout: float = 3.0) -> None:
        """Realise le handshake HELLO/HELLO_ACK et verifie la version.

        Gere aussi le cas RPi rebooté + ESP32 en ERROR (§6.6 spec) :
        - Si on recoit ERR avant HELLO, on envoie automatiquement CMD_RESET et on attend.

        Bloque jusqu'a reception d'un HELLO valide ou timeout.
        Leve UartTimeoutError si pas de HELLO recu, UartVersionError si version incompatible.
        """
        self._start_reader_thread()
        # Dans le cas ESP32 en ERROR, on envoie un seul CMD_RESET et on attend
        reset_already_sent = False

        deadline = self._clock() + timeout
        while self._clock() < deadline:
            try:
                frame = self._rx_queue.get(timeout=0.05)
            except queue.Empty:
                continue

            if frame.type == "HELLO":
                if frame.version != self._expected_version:
                    raise UartVersionError(
                        f"version protocole incompatible : "
                        f"recu v={frame.version}, attendu v={self._expected_version}"
                    )
                self._send_response(type="HELLO_ACK", args="", ack=frame.seq)
                self.is_connected = True
                return

            if frame.type == "ERR" and not reset_already_sent:
                # ESP32 est en ERROR : envoyer CMD_RESET pour le rebooter
                # On utilise un envoi direct sans verifier is_connected (qui est False)
                seq = self._next_tx_seq()
                reset_frame = Frame(type="CMD_RESET", args="", seq=seq)
                self._send_frame(reset_frame)
                reset_already_sent = True
                # Etendre le timeout pour attendre le reboot ESP32 (§6.6 : 10 s)
                deadline = max(deadline, self._clock() + 10.0)

            # BOOT_START et autres trames sont ignorees, on continue d'attendre HELLO

        raise UartTimeoutError(f"aucun HELLO recu apres {timeout}s")
```

- [ ] **Step 4 : Lancer le test**

Run: `pytest tests/test_uart_client.py::TestConnectWithEspInError -v`
Expected: PASS.

- [ ] **Step 5 : Vérifier non-régression sur Task 10**

Run: `pytest tests/test_uart_client.py::TestHandshake -v`
Expected: 3 tests PASS.

- [ ] **Step 6 : Commit**

```bash
git add quoridor_engine/uart_client.py tests/test_uart_client.py
git commit -m "feat(uart): cas RPi rebooté + ESP32 en ERROR (§6.6)"
```

---

## Task 16 : Reset de session sur `BOOT_START` ou nouveau `HELLO`

**Files:**
- Modify: `quoridor_engine/uart_client.py`
- Modify: `tests/test_uart_client.py`

- [ ] **Step 1 : Écrire les tests**

Ajouter dans `tests/test_uart_client.py` :

```python
class TestSessionReset:
    """Reset session sur BOOT_START ou nouveau HELLO en session active (§5.1 spec)."""

    def test_boot_start_resets_tx_seq(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True

        # Avance le compteur
        for _ in range(10):
            client.send_keepalive()
        # tx_seq devrait etre a 10
        assert client._tx_seq == 10

        # Simule reception BOOT_START
        client._reset_session()

        assert client._tx_seq == 0
        assert client._last_request_seq is None

    def test_reader_resets_session_on_boot_start(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client.is_connected = True
        client._start_reader_thread()

        # Avance le compteur
        for _ in range(5):
            client.send_keepalive()

        # Inject BOOT_START
        boot = Frame(type="BOOT_START", args="", seq=0)
        mock_serial.inject_rx(boot.encode())

        import time as _t
        _t.sleep(0.2)

        # tx_seq doit etre reset
        assert client._tx_seq == 0

        client.close()
```

- [ ] **Step 2 : Lancer les tests**

Run: `pytest tests/test_uart_client.py::TestSessionReset -v`
Expected: FAIL — `_reset_session` manquant.

- [ ] **Step 3 : Implémenter `_reset_session` et hooker dans `_dispatch_line`**

Ajouter dans `quoridor_engine/uart_client.py`, dans `UartClient` :

```python
    def _reset_session(self) -> None:
        """Reset complet de la session apres reboot ESP32 (§5.1 spec)."""
        with self._tx_seq_lock:
            self._tx_seq = 0
        self._last_request_seq = None
        self._last_err_received = None
```

Et modifier `_dispatch_line` pour détecter `BOOT_START` ou nouveau `HELLO` en session active :

```python
    def _dispatch_line(self, raw_line: bytes) -> None:
        """Classe une ligne recue : trame protocole ou log debug."""
        stripped = raw_line.rstrip(b"\r\n")
        if not stripped:
            return
        if stripped[0:1] == b"<":
            try:
                frame = Frame.decode(stripped)
                # Reset session si BOOT_START ou HELLO en session active
                if frame.type == "BOOT_START" or (
                    frame.type == "HELLO" and self.is_connected
                ):
                    self._reset_session()
                self._rx_queue.put(frame)
            except UartProtocolError:
                pass
        else:
            try:
                line_str = stripped.decode("ascii", errors="replace")
            except Exception:
                return
            self._debug_lines.append(line_str)
            if len(self._debug_lines) > self.MAX_DEBUG_LINES:
                self._debug_lines = self._debug_lines[-self.MAX_DEBUG_LINES :]
```

- [ ] **Step 4 : Lancer tous les tests**

Run: `pytest tests/test_uart_client.py -v`
Expected: tous les tests PASS (les nouveaux + non-régression sur les anciens).

- [ ] **Step 5 : Commit**

```bash
git add quoridor_engine/uart_client.py tests/test_uart_client.py
git commit -m "feat(uart): reset session sur BOOT_START ou nouveau HELLO"
```

---

## Task 17 : Co-existence debug — assurer que les logs ESP32 sont bien classés

**Files:**
- Modify: `tests/test_uart_client.py`

- [ ] **Step 1 : Écrire les tests pour les logs ESP32**

Ajouter dans `tests/test_uart_client.py` :

```python
class TestDebugCoexistence:
    """Lignes ne commencant pas par '<' = logs debug, ignorees par le protocole (§7.4 spec)."""

    def test_debug_line_does_not_pollute_rx_queue(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client._start_reader_thread()

        mock_serial.inject_rx(b"[FSM] BOOT -> WAITING_RPI\n")
        mock_serial.inject_rx(b"[BTN] tick=12345\n")

        import time as _t
        _t.sleep(0.2)

        # rx_queue doit etre vide (rien de protocolaire)
        assert client._rx_queue.empty()
        # debug_lines doit contenir les 2 lignes
        assert len(client._debug_lines) == 2
        assert "[FSM]" in client._debug_lines[0]
        assert "[BTN]" in client._debug_lines[1]

        client.close()

    def test_protocol_frame_after_debug_works(self, mock_serial, mock_clock):
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client._start_reader_thread()

        # Mix : log puis trame
        mock_serial.inject_rx(b"[FSM] starting\n")
        f = Frame(type="KEEPALIVE", args="", seq=0)
        mock_serial.inject_rx(f.encode())

        import time as _t
        _t.sleep(0.2)

        # La frame doit etre dans la queue
        received = client._rx_queue.get(timeout=1)
        assert received.type == "KEEPALIVE"
        # Le log dans debug
        assert any("[FSM]" in l for l in client._debug_lines)

        client.close()

    def test_line_with_lt_in_middle_is_debug(self, mock_serial, mock_clock):
        """[FSM] transition from <BOOT> n'est PAS une trame, c'est du debug."""
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client._start_reader_thread()

        mock_serial.inject_rx(b"[FSM] transition from <BOOT>\n")

        import time as _t
        _t.sleep(0.2)

        assert client._rx_queue.empty()
        assert len(client._debug_lines) == 1

        client.close()

    def test_corrupted_protocol_frame_is_silently_dropped(self, mock_serial, mock_clock):
        """Une trame avec mauvais CRC est ignoree silencieusement (§3.6)."""
        client = UartClient(serial_port=mock_serial, clock=mock_clock)
        client._start_reader_thread()

        mock_serial.inject_rx(b"<KEEPALIVE|seq=0|crc=0000>\n")  # CRC bidon

        import time as _t
        _t.sleep(0.2)

        # Rien dans la queue (rejet silencieux)
        assert client._rx_queue.empty()

        client.close()
```

- [ ] **Step 2 : Lancer les tests**

Run: `pytest tests/test_uart_client.py::TestDebugCoexistence -v`
Expected: 4 tests PASS (logique déjà en place dans Task 9).

- [ ] **Step 3 : Commit**

```bash
git add tests/test_uart_client.py
git commit -m "test(uart): co-existence debug/protocole sur meme UART"
```

---

## Task 18 : Vérification couverture ≥ 90 % + finalisation Python

**Files:**
- Modify: `requirements.txt` (si besoin)
- Modify: `quoridor_engine/__init__.py`

- [ ] **Step 1 : Ajouter `pyserial` à `requirements.txt`**

Editer `requirements.txt` pour ajouter :

```
pyserial>=3.5
```

(en gardant les autres dépendances déjà présentes)

- [ ] **Step 2 : Exporter `UartClient` et exceptions depuis le package**

Editer `quoridor_engine/__init__.py` :

```python
from .core import QuoridorGame, GameState, InvalidMoveError
from .ai import AI
from .uart_client import (
    UartClient,
    UartError,
    UartTimeoutError,
    UartProtocolError,
    UartVersionError,
    UartHardwareError,
    Frame,
    is_recoverable_err,
    compute_crc,
)
```

- [ ] **Step 3 : Lancer les tests avec couverture**

Run: `pytest tests/test_uart_client.py --cov=quoridor_engine.uart_client --cov-report=term-missing -v`
Expected: tous tests PASS, couverture ≥ 90 %. Si < 90 %, inspecter les lignes manquantes (`Missing` dans la sortie) et ajouter les tests manquants.

- [ ] **Step 4 : Lancer toute la suite de tests pour vérifier non-régression**

Run: `pytest`
Expected: 100 % tests PASS (les 90 anciens + nouveaux uart_client). Aucun fail.

- [ ] **Step 5 : Si couverture < 90 %, ajouter les tests manquants**

Pour chaque branche non couverte indiquée par `--cov-report=term-missing` :
- Identifier le scénario non testé
- Ajouter un test dans la classe appropriée de `tests/test_uart_client.py`
- Vérifier que la couverture remonte

Itérer jusqu'à atteindre ≥ 90 %.

- [ ] **Step 6 : Commit final Phase 1**

```bash
git add requirements.txt quoridor_engine/__init__.py tests/test_uart_client.py
git commit -m "feat(uart): finalisation P8.4 + P8.5 (couverture >= 90%)"
```

---

# Phase 2 — Documentation (P8.2)

## Task 19 : Réécrire `docs/06_protocole_uart.md`

**Files:**
- Modify: `docs/06_protocole_uart.md`

- [ ] **Step 1 : Réécrire la doc utilisateur du protocole**

Remplacer **intégralement** le contenu de `docs/06_protocole_uart.md` par :

````markdown
# Protocole UART — RPi ↔ ESP32 (Plan 2)

> **Statut** : ✅ *Plan 2 figé. Implémentation en cours dans P8.*
>
> **Spec de référence** : [`superpowers/specs/2026-05-01-protocole-uart-plan-2-design.md`](superpowers/specs/2026-05-01-protocole-uart-plan-2-design.md). Cette page est un résumé pratique pour l'équipe ; en cas de divergence apparente, le spec fait foi.

## En une phrase

Trames texte framées `<TYPE [args]|seq=N[|ack=M][|v=K]|crc=XXXX>\n`, intégrité CRC-16 CCITT-FALSE, séquencement modulo 256 avec `ack=M` sur les réponses, retry idempotent uniquement sur les `CMD ...` côté RPi (3 essais, 15 s).

## Liaison physique

- **UART0** entre RPi 3/4 et ESP32-WROOM
- **115200 bauds**, fin de ligne `LF`
- Câble direct (pas de bus intermédiaire)
- ⚠️ **Partagée avec le port USB de debug ESP32** : voir §"Co-existence debug" plus bas

## Format des trames

```
<TYPE [arg1 arg2 ...] | seq=N [|ack=M] [|v=K] | crc=XXXX>\n
```

| Champ | Description | Obligatoire ? |
|---|---|---|
| `<` ... `>\n` | Délimiteurs structurels | Oui |
| `TYPE` | Mot-clé MAJUSCULES (ex : `MOVE_REQ`, `CMD`) | Oui |
| Arguments | Mots-clés MAJUSCULES ou entiers décimaux, séparés par espaces | Selon TYPE |
| `seq=N` | Numéro de séquence émetteur (0–255) | Oui |
| `ack=M` | Seq de la requête à laquelle on répond | Sur réponses uniquement |
| `v=K` | Version protocole | Sur `HELLO` uniquement (v=1 actuel) |
| `crc=XXXX` | CRC-16 CCITT-FALSE en hexa MAJUSCULES sur 4 chars | Oui (toujours en dernier) |

**Calcul CRC** : sur les octets entre `<` (exclu) et `|crc=` (exclu).
**Polynôme** : 0x1021, **init** : 0xFFFF, **xorOut** : 0x0000, sans réflexion.
**Implémentation Python** : `binascii.crc_hqx(data, 0xFFFF)` — dans la stdlib.

**Longueur max** : 80 octets (toute trame plus longue est rejetée silencieusement).

## Catalogue des trames

### ESP32 → RPi (8 types)

| TYPE | Args | Quand |
|---|---|---|
| `BOOT_START` | aucun | Tout début de `setup()` |
| `SETUP_DONE` | aucun | Fin du `setup()` |
| `HELLO` | aucun (`v=1` séparé) | Toutes les 200 ms en `WAITING_RPI` |
| `MOVE_REQ` | `<row> <col>` | Détection clic 1 case |
| `WALL_REQ` | `<h\|v> <row> <col>` | Détection clic 2 cases adjacentes |
| `DONE` | aucun | Fin d'exécution d'une `CMD ...` reçue (porte `ack=`) |
| `ERR` | `<code>` | Entrée dans `ERROR` (réémis 1 s, peut porter `ack=`) |

### RPi → ESP32 (10 types)

| TYPE | Args | Quand |
|---|---|---|
| `HELLO_ACK` | aucun | Réponse à `HELLO` (active `CONNECTED`) |
| `KEEPALIVE` | aucun | Toutes les 1 s en session active |
| `ACK` | aucun | Validation d'un `MOVE_REQ`/`WALL_REQ` |
| `NACK` | `<raison>` | Refus d'un `MOVE_REQ`/`WALL_REQ` |
| `CMD MOVE` | `<row> <col>` | Coup IA déplacement |
| `CMD WALL` | `<h\|v> <row> <col>` | Coup IA mur |
| `CMD HIGHLIGHT` | `[<row> <col> ...]` (0 à 8) | Surbrillance ; vide = clear |
| `CMD SET_TURN` | `<j1\|j2>` | Indicateur visuel de tour |
| `CMD GAMEOVER` | `<j1\|j2>` | Fin de partie + servo |
| `CMD_RESET` | aucun | Reset depuis `ERROR` |

### Codes d'erreur (`ERR <code>`)

**Récupérables (auto `CMD_RESET`)** : `UART_LOST`, `BUTTON_MATRIX`
**Non récupérables (alerte humain)** : `MOTOR_TIMEOUT`, `LIMIT_UNEXPECTED`, `HOMING_FAILED`, `I2C_NACK`, `BOOT_I2C`, `BOOT_LED`, `BOOT_HOMING`

### Codes de raison (`NACK <code>`)

`ILLEGAL`, `OUT_OF_BOUNDS`, `WRONG_TURN`, `WALL_BLOCKED`, `NO_WALLS_LEFT`, `INVALID_FORMAT`

## Séquencement et idempotence

- Chaque émetteur (ESP32 et Python) maintient son propre compteur `tx_seq` ∈ [0, 255], incrémenté modulo 256 à chaque trame émise.
- **Sur retry de `CMD ...` côté RPi : on réutilise le même seq** (sinon l'idempotence ne marcherait pas).
- ESP32 stocke `last_cmd_seq_processed` + `last_cmd_result` pour dédup. Si un retry arrive pour la même seq déjà traitée → renvoie `DONE` sans re-exécuter.
- Si retry pendant exécution en cours → ignore en silence (le RPi attendra son timeout).

## Politique de retransmission

| Trame | Retry auto ? |
|---|---|
| `MOVE_REQ` / `WALL_REQ` | Non (l'humain reclique) |
| `CMD ...` | **Oui** : 2 retries (3 essais total), timeout 15 s, idempotent |
| `KEEPALIVE` | Émis périodiquement (1 s) |
| `HELLO` | Réémis périodiquement (200 ms) tant que pas d'`HELLO_ACK` |
| `ERR` | Réémis périodiquement (1 s) tant que ESP32 en `ERROR` |
| `ACK` / `NACK` / `DONE` | Non (réponses) |

## Co-existence debug ↔ protocole

L'UART0 est **physiquement la même** que le port USB de debug ESP32. Pour éviter la collision :

- **Trames protocolaires** : commencent par `<`, se terminent par `>\n`. Émises uniquement via `UartLink::sendFrame()`.
- **Logs de debug** : préfixés `[XXX]`, jamais commençant par `<`. Émis via `UartLink::log("XXX", ...)`.
- **Côté Python** : la condition "premier caractère = `<`" classe la ligne comme protocolaire. Sinon → log ESP32 (affiché dans le buffer debug).
- **Synchronisation FreeRTOS** : un mutex sur les accès à `Serial` empêche l'entrelacement entre Core 0 et Core 1 (sinon une trame en cours d'émission peut être corrompue par un log d'une autre tâche).

## Mode injection test

Pour les tests manuels au Serial Monitor (sans hardware), l'ESP32 accepte **en réception** un format simplifié :

```
BTN <row> <col>\n
```

Cette ligne (sans framing ni CRC) est interprétée comme un clic simulé. **Asymétrique** : seul l'ESP32 accepte ce format, le Python ne l'émet jamais.

## Pour aller plus loin

- **Spec complet** (toutes les décisions, justifications, diagrammes, vecteurs CRC, stratégie de tests) : [`superpowers/specs/2026-05-01-protocole-uart-plan-2-design.md`](superpowers/specs/2026-05-01-protocole-uart-plan-2-design.md)
- **Implémentation côté ESP32** : [`firmware/src/UartLink.{h,cpp}`](../firmware/src/)
- **Implémentation côté Python** : [`quoridor_engine/uart_client.py`](../quoridor_engine/uart_client.py)
- **Tests Python** : [`tests/test_uart_client.py`](../tests/test_uart_client.py)
- **Plan d'implémentation P8** : [`superpowers/plans/2026-05-01-protocole-uart-plan-2-implementation.md`](superpowers/plans/2026-05-01-protocole-uart-plan-2-implementation.md)
````

- [ ] **Step 2 : Vérifier le rendu Markdown**

Run: `cat docs/06_protocole_uart.md | head -50`
Expected: pas de `\\n` cassés, tableaux bien formés.

- [ ] **Step 3 : Commit**

```bash
git add docs/06_protocole_uart.md
git commit -m "docs(protocole): reecrire 06_protocole_uart.md pour Plan 2"
```

---

# Phase 3 — Firmware ESP32 (P8.3)

> ⚠️ **Note importante** : à partir de cette phase, on ne peut plus tester sur cible (DevKit indisponible avant lundi 2026-05-04). On valide uniquement par **compilation** (`pio run`). Les tests d'intégration sur DevKit sont reportés à P8.6.

## Task 20 : Nouvelle interface `UartLink.h`

**Files:**
- Modify: `firmware/src/UartLink.h`

- [ ] **Step 1 : Réécrire intégralement `UartLink.h`**

Remplacer le contenu de `firmware/src/UartLink.h` par :

```cpp
#ifndef UART_LINK_H
#define UART_LINK_H

#include <Arduino.h>

namespace UartLink {

  // Capacite max d'arguments dans une trame (ex : "h 2 3" pour WALL_REQ)
  constexpr size_t MAX_ARGS_LEN = 32;

  // Trame decodee disponible apres tryGetFrame
  struct Frame {
    char type[16];           // ex "MOVE_REQ", "ACK", "CMD"
    char args[MAX_ARGS_LEN]; // ex "3 4", "MOVE 2 5", vide si pas d'arg
    uint8_t seq;
    int16_t ack;             // -1 si pas d'ack
    int16_t version;         // -1 si pas de version
  };

  // Initialisation : cree le mutex, initialise les compteurs.
  // A appeler une seule fois dans setup() apres Serial.begin().
  void init();

  // Tick periodique (a appeler depuis loop()) :
  // - lit les octets entrants depuis Serial
  // - assemble en lignes
  // - decode les trames protocolaires valides
  // - dedup les CMD repetees (cf. §5.3 spec)
  // - place les trames decodees dans la file interne
  void poll();

  // Recupere la prochaine trame protocolaire decodee et validee.
  // Retourne true si une trame est disponible, remplit out.
  bool tryGetFrame(Frame& out);

  // Emet une trame protocolaire complete. Gere framing, seq, CRC, mutex.
  // type : "MOVE_REQ", "DONE", etc.
  // args : "3 4" ou "" si pas d'args
  // ack  : -1 si pas d'ack, sinon valeur (0..255)
  // version : -1 si pas de version, sinon valeur (utilise pour HELLO)
  void sendFrame(const char* type, const char* args, int ack = -1, int version = -1);

  // Emet un log de debug, prefixe [tag], sous mutex.
  // tag : ex "FSM", "BTN", "MOT" - majuscules courts
  // msg : message libre, sans \n
  void log(const char* tag, const char* msg);

  // Variante numerique pour eviter les conversions string a chaque appel
  void logf(const char* tag, const char* fmt, ...);

  // Statistiques debug
  uint32_t getRejectedCount();

  // Constantes protocole
  constexpr uint8_t PROTOCOL_VERSION = 1;
}

#endif
```

- [ ] **Step 2 : Vérifier la compilation (sans implémentation, doit échouer cleanly)**

Run: `cd firmware && pio run 2>&1 | tail -10`
Expected: erreurs de linker (les nouvelles fonctions n'ont pas d'implémentation). C'est attendu, on les ajoute aux tasks suivantes.

- [ ] **Step 3 : Commit (header seul)**

```bash
git add firmware/src/UartLink.h
git commit -m "refactor(firmware): nouvelle interface UartLink (header seul)"
```

---

## Task 21 : Implémentation `UartLink.cpp` — CRC-16 + sendFrame

**Files:**
- Modify: `firmware/src/UartLink.cpp`

- [ ] **Step 1 : Réécrire intégralement `UartLink.cpp`**

Remplacer le contenu de `firmware/src/UartLink.cpp` par :

```cpp
#include "UartLink.h"
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include <stdarg.h>

namespace {
  // Mutex pour serializer les acces a Serial entre Core 0 et Core 1
  SemaphoreHandle_t _serialMutex = nullptr;

  // Compteur de seq sortant
  volatile uint8_t _txSeq = 0;

  // Buffer de reception
  String _rxBuffer;

  // File de trames decodees (taille fixe pour eviter allocation dynamique)
  static constexpr size_t FRAME_QUEUE_SIZE = 4;
  UartLink::Frame _frameQueue[FRAME_QUEUE_SIZE];
  size_t _frameQueueHead = 0;
  size_t _frameQueueCount = 0;

  // Idempotence CMD (cf. §5.3 spec)
  int16_t _lastCmdSeqProcessed = -1;
  enum class CmdResult { NONE, DONE, ERR };
  CmdResult _lastCmdResult = CmdResult::NONE;
  char _lastCmdErrCode[16] = "";

  // Stats
  uint32_t _rejectedCount = 0;

  // CRC-16 CCITT-FALSE (poly 0x1021, init 0xFFFF, sans reflexion)
  uint16_t crc16(const uint8_t* data, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; i++) {
      crc ^= ((uint16_t)data[i]) << 8;
      for (int j = 0; j < 8; j++) {
        if (crc & 0x8000) crc = (crc << 1) ^ 0x1021;
        else crc <<= 1;
      }
    }
    return crc;
  }

  // Helper : prend le mutex, ecrit, relache
  void writeUnderMutex(const char* data, size_t len) {
    if (_serialMutex && xSemaphoreTake(_serialMutex, pdMS_TO_TICKS(100))) {
      Serial.write((const uint8_t*)data, len);
      xSemaphoreGive(_serialMutex);
    } else {
      // Fallback si mutex pas dispo
      Serial.write((const uint8_t*)data, len);
    }
  }

  uint8_t nextSeq() {
    uint8_t s = _txSeq;
    _txSeq = (uint8_t)((_txSeq + 1) & 0xFF);
    return s;
  }
}

void UartLink::init() {
  _serialMutex = xSemaphoreCreateMutex();
  _rxBuffer.reserve(96);
  _txSeq = 0;
  _lastCmdSeqProcessed = -1;
  _lastCmdResult = CmdResult::NONE;
  _frameQueueHead = 0;
  _frameQueueCount = 0;
  _rejectedCount = 0;
  log("UART", "init");
}

void UartLink::sendFrame(const char* type, const char* args, int ack, int version) {
  // Construire la zone CRC dans un buffer local
  char body[96];
  size_t pos = 0;

  // type
  size_t typeLen = strlen(type);
  if (typeLen + 1 >= sizeof(body)) return;
  memcpy(body + pos, type, typeLen);
  pos += typeLen;

  // args (precedes d'un espace si non vides)
  if (args && args[0] != '\0') {
    size_t argsLen = strlen(args);
    if (pos + 1 + argsLen >= sizeof(body)) return;
    body[pos++] = ' ';
    memcpy(body + pos, args, argsLen);
    pos += argsLen;
  }

  // |seq=N
  uint8_t seq = nextSeq();
  pos += snprintf(body + pos, sizeof(body) - pos, "|seq=%u", seq);

  // |ack=M (optionnel)
  if (ack >= 0) {
    pos += snprintf(body + pos, sizeof(body) - pos, "|ack=%d", ack);
  }

  // |v=K (optionnel)
  if (version >= 0) {
    pos += snprintf(body + pos, sizeof(body) - pos, "|v=%d", version);
  }

  // Calcul CRC
  uint16_t crc = crc16((const uint8_t*)body, pos);

  // Trame complete : <body|crc=XXXX>\n
  char full[120];
  int n = snprintf(full, sizeof(full), "<%s|crc=%04X>\n", body, crc);
  if (n > 0 && (size_t)n < sizeof(full)) {
    writeUnderMutex(full, (size_t)n);
  }
}
```

- [ ] **Step 2 : Compiler**

Run: `cd firmware && pio run 2>&1 | tail -15`
Expected: compilation **partielle** — les autres fonctions (`poll`, `tryGetFrame`, `log`, `logf`, `getRejectedCount`) sont déclarées mais pas définies → erreurs de linker. C'est attendu.

- [ ] **Step 3 : Commit (avancement intermédiaire)**

```bash
git add firmware/src/UartLink.cpp
git commit -m "feat(firmware): UartLink CRC16 + sendFrame avec mutex"
```

---

## Task 22 : `UartLink.cpp` — `log()`, `logf()`, `getRejectedCount()`

**Files:**
- Modify: `firmware/src/UartLink.cpp`

- [ ] **Step 1 : Ajouter les fonctions de log à `UartLink.cpp`**

Append à `firmware/src/UartLink.cpp` (après `sendFrame`) :

```cpp
void UartLink::log(const char* tag, const char* msg) {
  char buf[160];
  int n = snprintf(buf, sizeof(buf), "[%s] %s\n", tag, msg);
  if (n > 0 && (size_t)n < sizeof(buf)) {
    writeUnderMutex(buf, (size_t)n);
  }
}

void UartLink::logf(const char* tag, const char* fmt, ...) {
  char msg[140];
  va_list args;
  va_start(args, fmt);
  vsnprintf(msg, sizeof(msg), fmt, args);
  va_end(args);
  log(tag, msg);
}

uint32_t UartLink::getRejectedCount() {
  return _rejectedCount;
}
```

- [ ] **Step 2 : Compiler**

Run: `cd firmware && pio run 2>&1 | tail -15`
Expected: il manque encore `poll()` et `tryGetFrame()` → erreurs de linker (attendues).

- [ ] **Step 3 : Commit**

```bash
git add firmware/src/UartLink.cpp
git commit -m "feat(firmware): UartLink log() / logf() / getRejectedCount() avec mutex"
```

---

## Task 23 : `UartLink.cpp` — `poll()` + parser + dédup

**Files:**
- Modify: `firmware/src/UartLink.cpp`

- [ ] **Step 1 : Ajouter le parser et `poll()`**

Append à `firmware/src/UartLink.cpp` :

```cpp
namespace {
  // Parse une ligne brute (sans le \n final) en Frame.
  // Retourne true si trame valide, false sinon.
  bool parseFrame(const char* raw, size_t len, UartLink::Frame& out) {
    // Verifie longueur max
    if (len > 80) return false;
    // Verifie delimiteurs
    if (len < 3 || raw[0] != '<' || raw[len - 1] != '>') return false;

    // Travaille sur le contenu interne (sans <>)
    const char* inner = raw + 1;
    size_t innerLen = len - 2;

    // Trouve |crc= a la fin
    const char* crcMarker = "|crc=";
    if (innerLen < 9) return false;  // "|crc=XXXX" = 9 chars min
    const char* crcStart = nullptr;
    for (int i = (int)innerLen - 9; i >= 0; i--) {
      if (memcmp(inner + i, crcMarker, 5) == 0) {
        crcStart = inner + i;
        break;
      }
    }
    if (!crcStart) return false;
    // crcStart pointe sur '|', les 4 chars hex sont apres "|crc="
    const char* crcHex = crcStart + 5;
    if (inner + innerLen - crcHex != 4) return false;
    // Verifie que les 4 chars sont hex MAJUSCULES
    for (int i = 0; i < 4; i++) {
      char c = crcHex[i];
      bool valid = (c >= '0' && c <= '9') || (c >= 'A' && c <= 'F');
      if (!valid) return false;
    }
    // Parse la valeur CRC recue
    uint16_t recvCrc = 0;
    for (int i = 0; i < 4; i++) {
      char c = crcHex[i];
      uint8_t v = (c >= '0' && c <= '9') ? (c - '0') : (c - 'A' + 10);
      recvCrc = (recvCrc << 4) | v;
    }

    // Calcule le CRC sur la zone (inner sans |crc=XXXX)
    size_t crcZoneLen = (size_t)(crcStart - inner);
    uint16_t calcCrc = crc16((const uint8_t*)inner, crcZoneLen);
    if (calcCrc != recvCrc) return false;

    // Maintenant parser la zone CRC : TYPE [args]|seq=N[|ack=M][|v=K]
    char zone[96];
    if (crcZoneLen >= sizeof(zone)) return false;
    memcpy(zone, inner, crcZoneLen);
    zone[crcZoneLen] = '\0';

    // Trouve le premier '|' qui separe (TYPE [args]) du premier meta
    char* firstPipe = strchr(zone, '|');
    if (!firstPipe) return false;
    *firstPipe = '\0';
    char* head = zone;        // "TYPE" ou "TYPE args"
    char* metaStart = firstPipe + 1;

    // Split TYPE et args sur le 1er espace
    char* sp = strchr(head, ' ');
    if (sp) {
      *sp = '\0';
      strncpy(out.type, head, sizeof(out.type) - 1);
      out.type[sizeof(out.type) - 1] = '\0';
      strncpy(out.args, sp + 1, sizeof(out.args) - 1);
      out.args[sizeof(out.args) - 1] = '\0';
    } else {
      strncpy(out.type, head, sizeof(out.type) - 1);
      out.type[sizeof(out.type) - 1] = '\0';
      out.args[0] = '\0';
    }

    // Verifie que TYPE est en majuscules + chiffres + _
    for (size_t i = 0; out.type[i]; i++) {
      char c = out.type[i];
      bool ok = (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_';
      if (!ok) return false;
    }

    // Parse les meta : seq=N[|ack=M][|v=K]
    out.seq = 0;
    out.ack = -1;
    out.version = -1;
    bool hasSeq = false;

    char* tok = metaStart;
    while (tok && *tok) {
      char* nextPipe = strchr(tok, '|');
      if (nextPipe) *nextPipe = '\0';

      if (strncmp(tok, "seq=", 4) == 0) {
        int v = atoi(tok + 4);
        if (v < 0 || v > 255) return false;
        out.seq = (uint8_t)v;
        hasSeq = true;
      } else if (strncmp(tok, "ack=", 4) == 0) {
        int v = atoi(tok + 4);
        if (v < 0 || v > 255) return false;
        out.ack = (int16_t)v;
      } else if (strncmp(tok, "v=", 2) == 0) {
        out.version = (int16_t)atoi(tok + 2);
      }
      // Champ inconnu : on tolere silencieusement (forward compat mineure)

      tok = nextPipe ? nextPipe + 1 : nullptr;
    }

    if (!hasSeq) return false;
    return true;
  }

  bool isCmdFrame(const UartLink::Frame& f) {
    // CMD MOVE, CMD WALL, CMD HIGHLIGHT, CMD SET_TURN, CMD GAMEOVER, CMD_RESET
    return strcmp(f.type, "CMD") == 0 || strcmp(f.type, "CMD_RESET") == 0;
  }

  void enqueueFrame(const UartLink::Frame& f) {
    if (_frameQueueCount >= FRAME_QUEUE_SIZE) {
      // File pleine, on jette la plus ancienne (overwrite)
      _frameQueueHead = (_frameQueueHead + 1) % FRAME_QUEUE_SIZE;
      _frameQueueCount--;
    }
    size_t idx = (_frameQueueHead + _frameQueueCount) % FRAME_QUEUE_SIZE;
    _frameQueue[idx] = f;
    _frameQueueCount++;
  }

  // Mode injection test : "BTN <row> <col>" sans framing
  bool tryHandleInjection(const char* line) {
    if (strncmp(line, "BTN ", 4) != 0) return false;
    UartLink::Frame f;
    strcpy(f.type, "MOVE_REQ");
    // Recopier "row col" comme args
    strncpy(f.args, line + 4, sizeof(f.args) - 1);
    f.args[sizeof(f.args) - 1] = '\0';
    f.seq = 0;
    f.ack = -1;
    f.version = -1;
    enqueueFrame(f);
    return true;
  }
}

void UartLink::poll() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      // Ligne complete dans _rxBuffer
      Frame f;
      const char* line = _rxBuffer.c_str();
      size_t llen = _rxBuffer.length();

      if (llen > 0 && line[0] == '<') {
        // Tentative parsing trame protocolaire
        if (parseFrame(line, llen, f)) {
          // Dedup CMD (§5.3 spec)
          if (isCmdFrame(f)) {
            if ((int16_t)f.seq == _lastCmdSeqProcessed) {
              if (_lastCmdResult == CmdResult::DONE) {
                // Retransmission apres DONE perdu : renvoie DONE
                sendFrame("DONE", "", (int)f.seq);
              } else if (_lastCmdResult == CmdResult::ERR) {
                // Retransmission apres ERR : renvoie ERR
                sendFrame("ERR", _lastCmdErrCode, (int)f.seq);
              }
              // Si NONE (en cours d'execution), ignore silencieusement
            } else {
              // Nouvelle CMD : marque comme en cours et enqueue pour traitement
              _lastCmdSeqProcessed = (int16_t)f.seq;
              _lastCmdResult = CmdResult::NONE;
              enqueueFrame(f);
            }
          } else {
            enqueueFrame(f);
          }
        } else {
          _rejectedCount++;
        }
      } else if (llen > 0) {
        // Pas une trame protocolaire : tente injection BTN
        tryHandleInjection(line);
      }
      _rxBuffer = "";
    } else {
      _rxBuffer += c;
      if (_rxBuffer.length() > 80) {
        // Protection : on jette le buffer
        _rxBuffer = "";
      }
    }
  }
}

bool UartLink::tryGetFrame(Frame& out) {
  if (_frameQueueCount == 0) return false;
  out = _frameQueue[_frameQueueHead];
  _frameQueueHead = (_frameQueueHead + 1) % FRAME_QUEUE_SIZE;
  _frameQueueCount--;
  return true;
}
```

- [ ] **Step 2 : Compiler**

Run: `cd firmware && pio run 2>&1 | tail -15`
Expected: la compilation de `UartLink.cpp` passe. Reste les **callers** (GameController, main, etc.) qui appellent encore les anciennes API `sendLine`/`tryReadLine` — on les corrige aux Tasks 24-27.

- [ ] **Step 3 : Commit**

```bash
git add firmware/src/UartLink.cpp
git commit -m "feat(firmware): UartLink poll() + parser + dedup CMD"
```

---

## Task 24 : Helpers pour signaler résultat d'une CMD (DONE/ERR avec idempotence)

**Files:**
- Modify: `firmware/src/UartLink.h`
- Modify: `firmware/src/UartLink.cpp`

- [ ] **Step 1 : Ajouter à `UartLink.h` les helpers de réponse à CMD**

Editer `firmware/src/UartLink.h`, ajouter dans le namespace :

```cpp
  // Helpers pour signaler le resultat d'une CMD recue.
  // Stocke le resultat pour idempotence (renvoyer DONE/ERR sur retransmission).
  // ackSeq : seq de la CMD a laquelle on repond.
  void respondCmdDone(uint8_t ackSeq);
  void respondCmdErr(uint8_t ackSeq, const char* code);

  // Emet ERR spontane (entree en ERROR depuis BOOT ou autre etat sans CMD en cours).
  // Stocke le code pour la reemission periodique.
  void emitSpontaneousErr(const char* code);

  // A appeler periodiquement (1 s) tant qu'on est en ERROR pour reemettre.
  void tickErrReemission(unsigned long currentMs);

  // Reset l'etat ERR (a la sortie de l'etat ERROR, ex apres CMD_RESET).
  void clearErrState();
```

- [ ] **Step 2 : Ajouter les implémentations dans `UartLink.cpp`**

Append à `firmware/src/UartLink.cpp` :

```cpp
namespace {
  bool _errActive = false;
  char _errActiveCode[16] = "";
  unsigned long _lastErrEmitMs = 0;
  static constexpr unsigned long ERR_REEMIT_PERIOD_MS = 1000;
}

void UartLink::respondCmdDone(uint8_t ackSeq) {
  _lastCmdResult = CmdResult::DONE;
  _lastCmdErrCode[0] = '\0';
  sendFrame("DONE", "", (int)ackSeq);
}

void UartLink::respondCmdErr(uint8_t ackSeq, const char* code) {
  _lastCmdResult = CmdResult::ERR;
  strncpy(_lastCmdErrCode, code, sizeof(_lastCmdErrCode) - 1);
  _lastCmdErrCode[sizeof(_lastCmdErrCode) - 1] = '\0';
  // Cette ERR repond a une CMD : porte ack=
  sendFrame("ERR", code, (int)ackSeq);
  // Active la reemission periodique (cf. §6.5 spec)
  _errActive = true;
  strncpy(_errActiveCode, code, sizeof(_errActiveCode) - 1);
  _errActiveCode[sizeof(_errActiveCode) - 1] = '\0';
  _lastErrEmitMs = millis();
}

void UartLink::emitSpontaneousErr(const char* code) {
  // ERR sans ack : entree en ERROR depuis un etat sans CMD en cours
  sendFrame("ERR", code, -1);
  _errActive = true;
  strncpy(_errActiveCode, code, sizeof(_errActiveCode) - 1);
  _errActiveCode[sizeof(_errActiveCode) - 1] = '\0';
  _lastErrEmitMs = millis();
}

void UartLink::tickErrReemission(unsigned long currentMs) {
  if (!_errActive) return;
  if (currentMs - _lastErrEmitMs >= ERR_REEMIT_PERIOD_MS) {
    // Reemission periodique : sans ack=
    sendFrame("ERR", _errActiveCode, -1);
    _lastErrEmitMs = currentMs;
  }
}

void UartLink::clearErrState() {
  _errActive = false;
  _errActiveCode[0] = '\0';
}
```

- [ ] **Step 3 : Compiler**

Run: `cd firmware && pio run 2>&1 | tail -15`
Expected: `UartLink.cpp` compile. Les callers ne sont pas encore mis à jour → erreurs sur `GameController.cpp` et `main.cpp` qui appellent encore les anciennes API.

- [ ] **Step 4 : Commit**

```bash
git add firmware/src/UartLink.h firmware/src/UartLink.cpp
git commit -m "feat(firmware): UartLink helpers respondCmd + reemission ERR"
```

---

## Task 25 : Refactor `main.cpp`

**Files:**
- Modify: `firmware/src/main.cpp`

- [ ] **Step 1 : Remplacer les Serial.println directs par UartLink**

Editer `firmware/src/main.cpp`, remplacer :

```cpp
  Serial.println("BOOT_START");
```

par :

```cpp
  // BOOT_START doit etre une vraie trame protocolaire (cf. spec §4.1)
  // Mais UartLink::init() n'est pas encore appele a ce stade !
  // -> on l'appelle d'abord, puis on emet la trame
```

Réorganiser `setup()` ainsi :

```cpp
void setup() {
  Serial.begin(115200);
  delay(100);
  pinMode(PIN_LED_DEBUG, OUTPUT);

  // watchdog 5 s pour les deux coeurs
  esp_task_wdt_init(WDT_TIMEOUT_S, true);
  esp_task_wdt_add(NULL);

  // UartLink en premier pour pouvoir emettre BOOT_START en framed
  UartLink::init();
  UartLink::sendFrame("BOOT_START", "");

  LedDriver::init();
  LedAnimator::init();
  ButtonMatrix::init();
  MotionControl::init();
  GameController::init();

  UartLink::sendFrame("SETUP_DONE", "");
}
```

- [ ] **Step 2 : Mettre à jour `loop()` pour ticker la réémission ERR**

Modifier `loop()` :

```cpp
void loop() {
  esp_task_wdt_reset();
  UartLink::poll();
  UartLink::tickErrReemission(millis());  // reemission ERR si en ERROR
  ButtonMatrix::poll();
  GameController::tick();
  LedAnimator::tick();
}
```

- [ ] **Step 3 : Compiler**

Run: `cd firmware && pio run 2>&1 | tail -15`
Expected: la compilation de `main.cpp` passe. `GameController.cpp` reste avec des erreurs (appelle encore `sendLine` / `tryReadLine`).

- [ ] **Step 4 : Commit**

```bash
git add firmware/src/main.cpp
git commit -m "refactor(firmware): main.cpp utilise sendFrame pour BOOT_START/SETUP_DONE"
```

---

## Task 26 : Refactor `GameController.cpp`

**Files:**
- Modify: `firmware/src/GameController.cpp`

- [ ] **Step 1 : Remplacer tous les `Serial.print` par `UartLink::log` ou `UartLink::logf`**

Pour chaque occurrence dans `GameController.cpp` :

| Avant | Après |
|---|---|
| `Serial.print("[GameController] -> state "); Serial.println((int)s);` | `UartLink::logf("FSM", "-> state %d", (int)s);` |
| `Serial.print("[GameController] ENTER ERROR code="); Serial.println(code);` | `UartLink::logf("FSM", "ENTER ERROR code=%s", code);` |
| `Serial.println("[GameController] BOOT_FAILED LedDriver");` | `UartLink::log("FSM", "BOOT_FAILED LedDriver");` |
| `Serial.println("[GameController] BOOT_FAILED I2C/MotionControl");` | `UartLink::log("FSM", "BOOT_FAILED I2C/MotionControl");` |
| `Serial.println("[GameController] BOOT_FAILED homing");` | `UartLink::log("FSM", "BOOT_FAILED homing");` |
| `Serial.println("[GameController] BOOT_FAILED homing_timeout");` | `UartLink::log("FSM", "BOOT_FAILED homing_timeout");` |
| `Serial.println("[GameController] DEMO tick");` | `UartLink::log("FSM", "DEMO tick");` |
| `Serial.print("[GameController] CMD non-impl: "); Serial.println(line);` | `UartLink::logf("FSM", "CMD non-impl: %s", line.c_str());` |
| `Serial.print("[GameController] CONNECTED rx unhandled: "); Serial.println(line);` | `UartLink::logf("FSM", "CONNECTED rx unhandled: %s", line.c_str());` |
| `Serial.print("[GameController] INTENT_PENDING rx unhandled: "); Serial.println(line);` | `UartLink::logf("FSM", "INTENT_PENDING rx unhandled: %s", line.c_str());` |
| `Serial.print("[GameController] intent timeout (consecutive="); Serial.print(_consecutiveTimeouts); Serial.println(")");` | `UartLink::logf("FSM", "intent timeout consecutive=%d", _consecutiveTimeouts);` |
| `Serial.println("[GameController] RESET requested");` | `UartLink::log("FSM", "RESET requested");` |
| `Serial.println("[GameController] init");` | `UartLink::log("FSM", "init");` |

- [ ] **Step 2 : Remplacer `UartLink::sendLine` et `tryReadLine` par les nouvelles API**

Le module `GameController.cpp` lit les trames via `UartLink::tryReadLine(line)` puis matche `line == "HELLO_ACK"`, etc. Il faut migrer vers `UartLink::tryGetFrame(frame)` puis matcher `strcmp(frame.type, "HELLO_ACK") == 0`.

**Refactor de `tickWaitingRpi()` :**

```cpp
  void tickWaitingRpi() {
    if (millis() - _lastHelloMs >= HELLO_PERIOD_MS) {
      UartLink::sendFrame("HELLO", "", -1, UartLink::PROTOCOL_VERSION);
      _lastHelloMs = millis();
    }
    UartLink::Frame f;
    if (UartLink::tryGetFrame(f)) {
      if (strcmp(f.type, "HELLO_ACK") == 0) {
        resetUartActivity();
        enterState(GameController::State::CONNECTED);
        return;
      }
    }
    if (millis() - _stateEnteredMs >= HELLO_TIMEOUT_MS) {
      enterState(GameController::State::DEMO);
    }
  }
```

**Refactor de `tickDemo()` :**

```cpp
  void tickDemo() {
    UartLink::Frame drained;
    while (UartLink::tryGetFrame(drained)) {
      // ignore
    }
    static unsigned long _lastDemoMs = 0;
    if (millis() - _lastDemoMs >= 500) {
      UartLink::log("FSM", "DEMO tick");
      digitalWrite(2, !digitalRead(2));
      _lastDemoMs = millis();
    }
  }
```

**Refactor de `tickConnected()` :**

```cpp
  void tickConnected() {
    if (millis() - _lastUartActivityMs >= UART_TIMEOUT_MS) {
      enterError("UART_LOST");
      return;
    }
    UartLink::Frame f;
    if (UartLink::tryGetFrame(f)) {
      resetUartActivity();
      if (strcmp(f.type, "KEEPALIVE") == 0) {
        // KEEPALIVE : juste reset activite
      } else if (strcmp(f.type, "MOVE_REQ") == 0) {
        // Trame d'injection test convertie en MOVE_REQ par UartLink (cf. §4.6)
        // Args = "row col"
        int row = 0, col = 0;
        sscanf(f.args, "%d %d", &row, &col);
        ButtonMatrix::injectMoveIntent((uint8_t)row, (uint8_t)col);
      } else if (strcmp(f.type, "CMD") == 0 && strncmp(f.args, "MOVE ", 5) == 0) {
        int row = 0, col = 0;
        sscanf(f.args + 5, "%d %d", &row, &col);
        MotionControl::Command cmd = { MotionControl::CommandKind::MOVE_TO_WALL_SLOT,
                                       (uint8_t)row, (uint8_t)col, false };
        _currentCmdAckSeq = f.seq;
        enterExecutingWithCommand(cmd);
      } else if (strcmp(f.type, "CMD") == 0) {
        UartLink::logf("FSM", "CMD non-impl: %s", f.args);
      } else if (strcmp(f.type, "CMD_RESET") == 0) {
        // Reset hors etat ERROR : ignore (le RESET n'est traite qu'en ERROR)
      } else {
        UartLink::logf("FSM", "CONNECTED rx unhandled: %s", f.type);
      }
    }
    if (ButtonMatrix::hasIntent()) {
      emitIntent(ButtonMatrix::takeIntent());
    }
  }
```

**Ajouter une variable `_currentCmdAckSeq` au namespace anonyme :**

```cpp
namespace {
  // ... variables existantes ...
  uint8_t _currentCmdAckSeq = 0;
}
```

**Refactor de `tickIntentPending()` :**

```cpp
  void tickIntentPending() {
    if (millis() - _lastUartActivityMs >= UART_TIMEOUT_MS) {
      enterError("UART_LOST");
      return;
    }
    UartLink::Frame f;
    if (UartLink::tryGetFrame(f)) {
      resetUartActivity();
      if (strcmp(f.type, "ACK") == 0) {
        _consecutiveTimeouts = 0;
        MotionControl::Command cmd = { MotionControl::CommandKind::MOVE_TO_WALL_SLOT, 0, 0, false };
        _currentCmdAckSeq = f.ack >= 0 ? (uint8_t)f.ack : 0;
        enterExecutingWithCommand(cmd);
        return;
      }
      if (strcmp(f.type, "NACK") == 0) {
        _consecutiveTimeouts = 0;
        LedAnimator::play(LedAnimator::Pattern::NACK_FLASH);
        enterState(GameController::State::CONNECTED);
        return;
      }
      if (strcmp(f.type, "KEEPALIVE") == 0) {
        return;
      }
      UartLink::logf("FSM", "INTENT_PENDING rx unhandled: %s", f.type);
    }
    if (millis() - _stateEnteredMs >= INTENT_ACK_TIMEOUT_MS) {
      _consecutiveTimeouts++;
      UartLink::logf("FSM", "intent timeout consecutive=%d", _consecutiveTimeouts);
      LedAnimator::play(LedAnimator::Pattern::TIMEOUT_FLASH);
      if (_consecutiveTimeouts >= MAX_CONSECUTIVE_TIMEOUTS) {
        enterError("UART_LOST");
        return;
      }
      enterState(GameController::State::CONNECTED);
    }
  }
```

**Refactor de `tickExecuting()` :**

```cpp
  void tickExecuting() {
    if (millis() - _lastUartActivityMs >= UART_TIMEOUT_MS) {
      enterError("UART_LOST");
      return;
    }
    UartLink::Frame f;
    if (UartLink::tryGetFrame(f)) {
      resetUartActivity();
      // Toutes trames (sauf erreurs) sont ignorees pendant EXECUTING
    }
    MotionControl::Result res;
    if (_waitingMotion && MotionControl::tryGetResult(res)) {
      _waitingMotion = false;
      switch (res.kind) {
        case MotionControl::ResultKind::DONE:
          UartLink::respondCmdDone(_currentCmdAckSeq);
          enterState(GameController::State::CONNECTED);
          break;
        case MotionControl::ResultKind::ERR_MOTOR_TIMEOUT:
          enterError("MOTOR_TIMEOUT");
          break;
        case MotionControl::ResultKind::ERR_LIMIT_UNEXPECTED:
          enterError("LIMIT_UNEXPECTED");
          break;
        case MotionControl::ResultKind::ERR_HOMING_FAILED:
          enterError("HOMING_FAILED");
          break;
        case MotionControl::ResultKind::ERR_I2C_NACK:
          enterError("I2C_NACK");
          break;
      }
    }
  }
```

**Refactor de `tickError()` :**

```cpp
  void tickError() {
    UartLink::Frame f;
    if (UartLink::tryGetFrame(f)) {
      if (strcmp(f.type, "CMD_RESET") == 0) {
        UartLink::log("FSM", "RESET requested");
        UartLink::clearErrState();
        delay(100);
        ESP.restart();
      }
    }
  }
```

**Refactor de `enterError()` :**

```cpp
  void enterError(const char* code) {
    UartLink::logf("FSM", "ENTER ERROR code=%s", code);
    LedAnimator::play(LedAnimator::Pattern::ERROR_PATTERN);
    // Si on etait en train de traiter une CMD (state EXECUTING), respondCmdErr
    // sinon emitSpontaneousErr.
    if (_state == GameController::State::EXECUTING) {
      UartLink::respondCmdErr(_currentCmdAckSeq, code);
    } else {
      UartLink::emitSpontaneousErr(code);
    }
    enterState(GameController::State::ERROR_STATE);
  }
```

**Refactor de `emitIntent()` :**

```cpp
  void emitIntent(const ButtonMatrix::Intent& intent) {
    char args[16];
    const char* type = "MOVE_REQ";
    switch (intent.kind) {
      case ButtonMatrix::IntentKind::MOVE:
        type = "MOVE_REQ";
        snprintf(args, sizeof(args), "%d %d", intent.row, intent.col);
        break;
      case ButtonMatrix::IntentKind::WALL_H:
        type = "WALL_REQ";
        snprintf(args, sizeof(args), "h %d %d", intent.row, intent.col);
        break;
      case ButtonMatrix::IntentKind::WALL_V:
        type = "WALL_REQ";
        snprintf(args, sizeof(args), "v %d %d", intent.row, intent.col);
        break;
      default:
        return;
    }
    UartLink::sendFrame(type, args);
    LedAnimator::play(LedAnimator::Pattern::PENDING_FLASH);
    enterState(GameController::State::BUTTON_INTENT_PENDING);
  }
```

- [ ] **Step 3 : Compiler**

Run: `cd firmware && pio run 2>&1 | tail -20`
Expected: la compilation passe ou alors il reste juste les `Serial.println` dans `ButtonMatrix.cpp`, `LedDriver.cpp`, `LedAnimator.cpp`, `MotionControl.cpp` (Task suivante).

- [ ] **Step 4 : Commit**

```bash
git add firmware/src/GameController.cpp
git commit -m "refactor(firmware): GameController utilise UartLink::sendFrame/log/tryGetFrame"
```

---

## Task 27 : Refactor des autres modules (Serial.print direct → UartLink::log)

**Files:**
- Modify: `firmware/src/ButtonMatrix.cpp`
- Modify: `firmware/src/LedDriver.cpp`
- Modify: `firmware/src/LedAnimator.cpp`
- Modify: `firmware/src/MotionControl.cpp`

- [ ] **Step 1 : Ajouter `#include "UartLink.h"` à chacun**

Pour chacun des 4 fichiers, ajouter en haut :

```cpp
#include "UartLink.h"
```

(s'il n'est pas déjà présent)

- [ ] **Step 2 : Remplacer dans `ButtonMatrix.cpp`**

| Avant | Après |
|---|---|
| `Serial.println("[ButtonMatrix] init (stub)");` | `UartLink::log("BTN", "init (stub)");` |

- [ ] **Step 3 : Remplacer dans `LedDriver.cpp`**

| Avant | Après |
|---|---|
| `Serial.println("[LedDriver] init (stub)");` | `UartLink::log("LED", "init (stub)");` |
| `Serial.print("[LedDriver] setPixel "); Serial.print(index); Serial.print(" "); Serial.print(r); Serial.print(" "); Serial.print(g); Serial.print(" "); Serial.println(b);` | `UartLink::logf("LED", "setPixel %d %d %d %d", index, r, g, b);` |
| `Serial.println("[LedDriver] clear");` | `UartLink::log("LED", "clear");` |
| `Serial.println("[LedDriver] selfTest -> OK (stub)");` | `UartLink::log("LED", "selfTest -> OK (stub)");` |

- [ ] **Step 4 : Remplacer dans `LedAnimator.cpp`**

| Avant | Après |
|---|---|
| `Serial.println("[LedAnimator] init (stub)");` | `UartLink::log("ANIM", "init (stub)");` |
| `Serial.print("[LedAnimator] play pattern="); Serial.println((int)p);` | `UartLink::logf("ANIM", "play pattern=%d", (int)p);` |

- [ ] **Step 5 : Remplacer dans `MotionControl.cpp`**

| Avant | Après |
|---|---|
| `Serial.print("[MotionControl] exec command kind="); Serial.println((int)cmd.kind);` | `UartLink::logf("MOT", "exec command kind=%d", (int)cmd.kind);` |
| `Serial.println("[MotionControl] init (FreeRTOS task)");` | `UartLink::log("MOT", "init (FreeRTOS task)");` |
| `Serial.println("[MotionControl] selfTest -> OK (stub I2C)");` | `UartLink::log("MOT", "selfTest -> OK (stub I2C)");` |

- [ ] **Step 6 : Compiler**

Run: `cd firmware && pio run 2>&1 | tail -20`
Expected: compilation propre, **aucun warning** (en plus des erreurs corrigées). Si warnings, lire le message et corriger.

- [ ] **Step 7 : Vérifier qu'il ne reste aucun `Serial.print` direct**

Run: `grep -rn "Serial\.\(print\|println\|write\)" firmware/src/`
Expected: uniquement des occurrences dans `UartLink.cpp` (les seules autorisées).

- [ ] **Step 8 : Commit**

```bash
git add firmware/src/ButtonMatrix.cpp firmware/src/LedDriver.cpp firmware/src/LedAnimator.cpp firmware/src/MotionControl.cpp
git commit -m "refactor(firmware): tous les modules utilisent UartLink::log"
```

---

## Task 28 : Compilation finale et nettoyage

**Files:**
- Modify: `firmware/platformio.ini` (peut-être)

- [ ] **Step 1 : Compilation finale du firmware**

Run: `cd firmware && pio run 2>&1 | tee /tmp/pio_build.log | tail -40`
Expected:
- 0 erreur
- 0 warning (les warnings deviennent des erreurs implicitement par convention projet)
- Taille `.bin` raisonnable (< 1 Mo)

Si warnings, lister :

```bash
grep -E "warning:" /tmp/pio_build.log | head -20
```

Et corriger un par un.

- [ ] **Step 2 : Vérifier les flags de compilation strictes**

Confirmer que `firmware/platformio.ini` a bien :

```ini
build_flags =
  -Wall
  -Wno-unused-parameter
```

(C'est déjà le cas selon l'état actuel.)

- [ ] **Step 3 : Vérifier qu'il n'y a aucun `sendLine`/`tryReadLine` résiduel**

Run: `grep -rn "sendLine\|tryReadLine" firmware/src/`
Expected: 0 occurrence (l'ancienne API Plan 1 est entièrement supprimée).

- [ ] **Step 4 : Commit final firmware**

```bash
git add firmware/
git commit -m "build(firmware): UartLink Plan 2 compile clean (0 warning)"
```

(Commit vide possible si rien n'a changé depuis la Task 27 — passer si pas de modifications.)

---

# Phase 4 — Finalisation

## Task 29 : Mise à jour `CHANGELOG.md` + plan global + push

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `docs/00_plan_global.md`

- [ ] **Step 1 : Lire le CHANGELOG actuel**

Run: `head -30 CHANGELOG.md`

- [ ] **Step 2 : Ajouter une entrée pour P8**

Editer `CHANGELOG.md`, ajouter en haut (après l'éventuel header) :

```markdown
## P8 — Protocole UART Plan 2 (2026-05-01 → en cours)

### Ajouté
- Spec complet du protocole UART Plan 2 (`docs/superpowers/specs/2026-05-01-protocole-uart-plan-2-design.md`)
- Module Python `quoridor_engine/uart_client.py` : client UART avec encodage/décodage de trames, séquencement, retry idempotent, gestion d'erreurs typées
- Tests unitaires `tests/test_uart_client.py` (couverture ≥ 90 %)
- Documentation utilisateur réécrite : `docs/06_protocole_uart.md`

### Modifié
- Refactor complet de `firmware/src/UartLink.{h,cpp}` : nouvelle API `sendFrame` / `log` / `tryGetFrame`, framing CRC-16 CCITT-FALSE, mutex inter-cœurs, dédup CMD idempotent
- `firmware/src/main.cpp` : émet `BOOT_START` et `SETUP_DONE` en trames protocolaires
- `firmware/src/GameController.cpp` et tous les autres modules : `Serial.print` direct remplacé par `UartLink::log` / `logf`
- `requirements.txt` : ajout de `pyserial>=3.5`

### Reporté
- P8.6 (tests d'intégration sur DevKit) : à exécuter au retour du DevKit, lundi 2026-05-04. Checklist : `docs/superpowers/plans/2026-05-01-protocole-uart-plan-2-implementation.md` Task 30.
```

- [ ] **Step 3 : Cocher les sous-tâches dans le plan global**

Editer `docs/00_plan_global.md`, dans la section P8 :

```markdown
### P8 — Protocole UART Plan 2 🚧

> But : remplacer le protocole texte stub du Plan 1 par un protocole final (binaire ou texte enrichi avec framing + intégrité), implémenté côté ESP32 *et* côté Python.

- [x] **P8.1** Designer le protocole final — trancher : framing (COBS, SLIP, longueur fixe ?), intégrité (CRC-8/16, checksum XOR ?), versioning, ID de séquence (questions ouvertes dans [06_protocole_uart.md](06_protocole_uart.md))
- [x] **P8.2** Documenter le protocole arrêté dans [06_protocole_uart.md](06_protocole_uart.md)
- [x] **P8.3** Refactor [firmware/src/UartLink.{cpp,h}](../firmware/src/) pour implémenter le protocole final
- [x] **P8.4** Créer un module Python client UART (probablement `quoridor_engine/uart_client.py` ou `interface/uart.py`)
- [x] **P8.5** Tests unitaires côté Python (avec serial loopback ou ESP32 DevKit en mode echo)
- [ ] **P8.6** Tests d'intégration ESP32 DevKit ↔ Python : envoi/réception de toutes les trames *(reporté au 2026-05-04)*
```

P8 reste 🚧 tant que P8.6 n'est pas validé.

- [ ] **Step 4 : Vérifier l'ensemble des tests Python passent**

Run: `pytest`
Expected: 100 % PASS, aucune régression sur les 90 tests pré-existants.

- [ ] **Step 5 : Vérifier la compilation firmware une dernière fois**

Run: `cd firmware && pio run 2>&1 | tail -10`
Expected: compilation propre.

- [ ] **Step 6 : Commit final P8 (sauf P8.6)**

```bash
git add CHANGELOG.md docs/00_plan_global.md
git commit -m "docs(p8): cloture P8.1 a P8.5, P8.6 reportee au 2026-05-04"
```

- [ ] **Step 7 : Push (optionnel, à la discrétion de l'utilisateur)**

Run: `git push origin main`

---

## Task 30 : Checklist P8.6 pour lundi 2026-05-04

**Files:**
- Create: `firmware/INTEGRATION_TESTS_PENDING.md`

- [ ] **Step 1 : Créer le fichier de checklist**

Créer `firmware/INTEGRATION_TESTS_PENDING.md` :

```markdown
# Tests d'intégration P8.6 — pending DevKit

> **Cible :** lundi 2026-05-04, retour du DevKit ESP32. À exécuter avant de cocher P8.6 dans le plan global.

## Préparatifs

- [ ] Récupérer le DevKit ESP32 auprès du camarade
- [ ] Brancher le DevKit au Mac via USB
- [ ] Vérifier que le port apparaît : `pio device list` doit lister un `/dev/cu.SLAB_USBtoUART` ou `/dev/cu.usbserial-*`
- [ ] Compiler et flasher le firmware Plan 2 :
  ```
  cd firmware && pio run -t upload
  ```
- [ ] Ouvrir le Serial Monitor :
  ```
  pio device monitor
  ```
- [ ] Confirmer la séquence boot attendue :
  ```
  <BOOT_START|seq=0|crc=XXXX>
  [LED] init (stub)
  [LED] selfTest -> OK (stub)
  [MOT] init (FreeRTOS task)
  [MOT] selfTest -> OK (stub I2C)
  [BTN] init (stub)
  [ANIM] init (stub)
  [FSM] init
  [FSM] -> state 0
  ...
  <SETUP_DONE|seq=1|crc=XXXX>
  <HELLO|seq=2|v=1|crc=XXXX>
  ```

## Tests à exécuter (cf. spec §8.2)

### 1. Handshake nominal
- [ ] L'ESP32 émet `<BOOT_START>`, `<SETUP_DONE>`, `<HELLO|v=1>` au boot
- [ ] Envoi manuel via Serial Monitor : `<HELLO_ACK|seq=0|ack=2|crc=XXXX>` (CRC à calculer)
- [ ] Vérifier transition `[FSM] -> state 3` (CONNECTED)

### 2. Cycle nominal humain
- [ ] Au prompt Serial Monitor, taper : `BTN 3 4` puis Entrée
- [ ] Vérifier réception : `<MOVE_REQ 3 4|seq=N|crc=XXXX>`
- [ ] Répondre : `<ACK|seq=0|ack=N|crc=XXXX>`
- [ ] Vérifier `[FSM] -> state 5` (EXECUTING) et finalement `<DONE|seq=M|ack=N|crc=XXXX>`

### 3. Cycle nominal IA
- [ ] Envoyer : `<CMD MOVE 2 5|seq=10|crc=XXXX>`
- [ ] Vérifier `<DONE|seq=N|ack=10|crc=XXXX>` après quelques secondes

### 4. Idempotence CMD
- [ ] Envoyer `<CMD MOVE 2 5|seq=20|crc=XXXX>`
- [ ] Attendre `<DONE|seq=N|ack=20|crc=XXXX>`
- [ ] **Renvoyer la même trame** `<CMD MOVE 2 5|seq=20|crc=XXXX>` (avec le même seq)
- [ ] Vérifier qu'AUCUNE séquence `[MOT] exec command` n'apparaît une 2ᵉ fois
- [ ] Vérifier qu'un nouveau `<DONE|seq=M|ack=20|crc=XXXX>` est renvoyé immédiatement

### 5. Trame corrompue
- [ ] Envoyer une trame avec CRC bidon : `<KEEPALIVE|seq=0|crc=0000>`
- [ ] Vérifier qu'aucune réaction (pas de transition d'état, log éventuel `getRejectedCount()` incrémenté)

### 6. Trame > 80 octets
- [ ] Envoyer une ligne `<` suivie de 90 caractères puis `>`
- [ ] Vérifier rejet silencieux

### 7. Mode injection test (sans framing)
- [ ] Taper `BTN 5 5` (sans `<>`)
- [ ] Vérifier que l'ESP32 émet bien `<MOVE_REQ 5 5|seq=N|crc=XXXX>`

### 8. Émission ERR + réémission périodique
- [ ] Forcer une erreur : envoyer `<CMD MOVE 99 99|seq=30|crc=XXXX>` (coordonnées hors plateau, devrait causer `MOTOR_TIMEOUT` ou similaire selon stub)
- [ ] Vérifier `<ERR ...|seq=N|ack=30|crc=XXXX>` initial
- [ ] Vérifier que `<ERR ...|seq=N+k|crc=XXXX>` (sans ack=) est réémis toutes les 1 s
- [ ] Envoyer `<CMD_RESET|seq=0|crc=XXXX>`
- [ ] Vérifier reboot complet (nouveau `<BOOT_START>`)

### 9. Test Python ↔ ESP32 réel (script automatisé)

Créer `tests/integration/test_uart_devkit.py` (à écrire à ce moment-là, pas dans P8.5) qui ouvre le port série réel et joue les scénarios 1-8 ci-dessus en automatique.

## Validation finale

Quand tous les tests passent :
- [ ] Cocher P8.6 dans `docs/00_plan_global.md`
- [ ] Passer P8 de 🚧 à ✅
- [ ] Supprimer ce fichier (`firmware/INTEGRATION_TESTS_PENDING.md`)
- [ ] Commit `test(firmware): plan 2 valide en bout-en-bout sur DevKit`
- [ ] Démarrer P9 (intégration RPi ↔ ESP32 dans `main.py`)
```

- [ ] **Step 2 : Commit**

```bash
git add firmware/INTEGRATION_TESTS_PENDING.md
git commit -m "docs(firmware): checklist P8.6 a executer au retour du DevKit"
```

---

# Self-review du plan

**Spec coverage** (vérifier que chaque section du spec a un task) :

| Section spec | Task(s) qui l'implémente(nt) |
|---|---|
| §2.1 Format texte avec framing | Tasks 4-7 (encode/decode), Task 21 (sendFrame ESP32) |
| §2.2 CRC-16 CCITT-FALSE | Tasks 1, 3 (Python), Task 21 (ESP32) |
| §2.3 Versioning HELLO | Task 4 (encode v=), Task 10 (handshake), Task 26 (ESP32 sendFrame avec version) |
| §2.4 Séquencement | Task 9 (`_next_tx_seq`), Task 11 (test wrap), Task 21 (ESP32 nextSeq) |
| §2.5 Retry idempotent CMD | Task 13 (Python), Task 23 (ESP32 dédup) |
| §3 Format complet | Tasks 4-7 (Python), Tasks 21, 23 (ESP32) |
| §4 Catalogue trames | Couvert par tests d'encodage Tasks 4-5 |
| §5 Séquencement & idempotence | Tasks 13, 16, 23, 24 |
| §6 Politique erreurs | Tasks 13, 14, 15, 24 |
| §7 Co-existence debug | Task 17 (Python), Tasks 22, 27 (ESP32) |
| §8 Stratégie tests | Tasks 2-18 (P8.5), Task 30 (P8.6) |
| §9 Implémentation | Tasks 18, 20-28 |
| §10 Coupure Plan 1 | Tasks 20, 26, 28 (`grep` post-refactor) |

✅ **Couverture complète.**

**Placeholder scan :**
- ⚠️ Task 3 mentionne `0xXXXX` à remplir avec les vecteurs CRC réels — c'est volontaire, dépendant de Task 1 qui les calcule. Le worker doit faire Task 1 d'abord et substituer.
- ✅ Aucun autre TBD/TODO dans le plan.

**Type consistency :**
- `Frame` dataclass utilisée cohéremment (Tasks 4-17).
- `UartClient` méthodes : `connect`, `send_keepalive`, `send_ack`, `send_nack`, `send_cmd`, `send_cmd_reset`, `receive`, `handle_err_received`, `close` — toutes définies, pas de divergence de signature entre tasks.
- ESP32 `UartLink::Frame` struct : champs `type`, `args`, `seq`, `ack`, `version` — cohérent avec usage GameController (Task 26).
- ✅ Pas de divergence détectée.

**Vérification finale du plan :** complet, exhaustif, exécutable task-par-task. Chaque task contient les commandes exactes, les bouts de code complets, les expected outputs. ~30 tasks au total.

---

# Execution Handoff

Plan complet et sauvegardé. Deux options d'exécution :

**1. Subagent-Driven (recommandé pour ce plan)** — Je dispatche un subagent frais par task, je revue entre tasks, itération rapide. Adapté au volume (30 tasks, beaucoup de TDD strict).

**2. Inline Execution** — Exécution dans cette session avec checkpoints. Adapté si tu veux superviser de très près chaque étape.

**Quelle approche ?**
