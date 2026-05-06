# Portage pytest des scénarios P8.6 (sc 1-8) — design

**Date :** 2026-05-06
**Auteur :** Silouane (brainstorming assisté)
**Statut :** validé, prêt pour planification d'implémentation
**Portée :** spécification du portage des 8 scénarios d'intégration UART P8.6 (actuellement dans `firmware/tests_devkit/run_p86_manual.py`) vers une suite pytest automatisable dans `tests/integration/test_uart_devkit.py`. Couvre la mutualisation des helpers, les fixtures pytest pour le DevKit, la configuration du marqueur, la stratégie d'exécution et de validation. **Hors scope :** sc 9 P9.5 (idempotence d'une CMD perdue, nécessite instrumentation firmware), tests breadboard hardware (LED/boutons/MCP/A4988/servo, séparés), refonte du protocole UART.
**Source amont :** [`firmware/INTEGRATION_TESTS_PENDING.md`](../../../firmware/INTEGRATION_TESTS_PENDING.md) section « Tests à exécuter (cf. spec §8.2) — Test 9 », [`firmware/tests_devkit/run_p86_manual.py`](../../../firmware/tests_devkit/run_p86_manual.py) (implémentation manuelle de référence).
**Phase couverte :** P8.6 sc 9 du [plan global](../../00_plan_global.md). Une fois cochée, P8 passe de 🚧 à ✅.

---

## Table des matières

1. [Contexte](#1-contexte)
2. [Décisions clés](#2-décisions-clés)
3. [Structure des fichiers](#3-structure-des-fichiers)
4. [Module partagé `_uart_helpers.py`](#4-module-partagé-_uart_helperspy)
5. [Fixtures pytest](#5-fixtures-pytest)
6. [Forme des 8 tests](#6-forme-des-8-tests)
7. [Configuration `pyproject.toml`](#7-configuration-pyprojecttoml)
8. [Stratégie de validation](#8-stratégie-de-validation)
9. [Limitations connues](#9-limitations-connues)
10. [Hors scope](#10-hors-scope)

---

## 1. Contexte

À l'issue de la session du 2026-05-06 (commit `033a64d`), les 8 scénarios P8.6 ont été validés en semi-automatique via le harness `firmware/tests_devkit/run_p86_manual.py` : reset DevKit, handshake, exécution séquentielle, table de synthèse PASS/FAIL, stop on first FAIL. Le scénario 9 (« Test pytest ») reste différé.

Le harness manuel a deux limites pour un usage répété :

- Il ne peut pas être lancé via `pytest`, donc il échappe à la suite verte (226 tests) et nécessite un appel séparé.
- Un échec sur un scénario stoppe la suite ; pour relancer un scénario isolé il faut `python firmware/tests_devkit/run_p86_manual.py 5`, syntaxe maison.

Le portage en pytest vise à offrir :

- Une intégration dans `pytest` (avec marqueur `@pytest.mark.devkit` pour skipper sans hardware).
- Une isolation par test (`pytest -k sc_5`, `pytest tests/integration/ -v -s`).
- Un runtime acceptable (~50-60 s pour les 8 scénarios sur DevKit branché) pour relance après chaque modification firmware.

L'objectif n'est **pas** d'améliorer la couverture, ni de réécrire la logique : c'est un portage 1:1 des scénarios existants, avec adaptation aux conventions pytest.

---

## 2. Décisions clés

| # | Décision | Pourquoi |
|---|---|---|
| 1 | Helpers extraits dans `firmware/tests_devkit/_uart_helpers.py`, importés par `run_p86_manual.py` ET le pytest. | DRY : une seule source de vérité pour `crc16`, `make_frame`, `reset_esp`, `wait_for`, etc. Le harness manuel reste utilisable pour debug. |
| 2 | Fixture `serial_port` **session-scoped** : ouvre le port une fois pour toute la session pytest. | Éviter le coût d'open/close (~50 ms) à chaque test ; le DevKit reste sur un seul port pendant une session. |
| 3 | Fixtures `raw_devkit` et `connected_devkit` **function-scoped** : reset hardware avant chaque test. | Isolation totale entre tests, ordre indifférent. Coût ~3 s × 8 = 24 s overhead, acceptable. |
| 4 | Détection du port via `glob("/dev/cu.usbserial-*")` (premier match), pas hardcodé `-110`. | Le suffixe peut changer après débranchement (cf. memory `project_brainstorm_progress.md` point 9). |
| 5 | Skip via `pytest.skip()` dans la fixture `serial_port` si aucun port détecté ; marqueur `@pytest.mark.devkit` enregistré dans `pyproject.toml` pour permettre `pytest -m "not devkit"`. | Comportement par défaut : skip silencieux sans hardware, suite verte préservée. Marqueur explicite pour filtrer. |
| 6 | `pyproject.toml` créé avec `[tool.pytest.ini_options]` minimal (markers, testpaths) ; `pyserial` déclaré dans `[project.optional-dependencies] devkit`. | Le fichier était vide. On documente la dépendance hardware-spécifique. |
| 7 | Sc 1 utilise `raw_devkit` (reset seul), sc 2-8 utilisent `connected_devkit` (reset + handshake). | Sc 1 **teste** le handshake : il ne peut pas l'avoir en pré-condition de fixture. Sc 2-8 supposent CONNECTED. |
| 8 | `assert ..., "msg"` à la place de `return False, "msg"`. | Convention pytest. Les messages d'erreur restent identiques au harness manuel. |
| 9 | `run_p86_manual.py` est conservé après refactor (n'importe que les helpers). | Outil interactif utile pour debug ; CLI `python … 5` reste pratique. |

---

## 3. Structure des fichiers

### Avant

```
firmware/tests_devkit/
  run_p86_manual.py    # ~314 lignes : helpers + 8 scénarios + main interactif
  run_p95_e2e.py       # harness P9.5 (intact, hors scope)
tests/
  conftest.py          # MockSerial, MockClock (intact)
  test_*.py            # 226 tests existants (intact)
pyproject.toml         # absent
pytest.ini             # absent
```

### Après

```
firmware/tests_devkit/
  _uart_helpers.py     # NEW : helpers protocole + serial (extraits)
  run_p86_manual.py    # REFACTOR : `from _uart_helpers import …`,
                       # ne contient plus que les 8 scénarios + main
  run_p95_e2e.py       # intact
tests/
  conftest.py          # intact
  test_*.py            # intact (226 tests verts)
  integration/
    __init__.py        # NEW : vide
    conftest.py        # NEW : serial_port, raw_devkit, connected_devkit
    test_uart_devkit.py # NEW : 8 fonctions test_sc_*_*
pyproject.toml         # NEW : config pytest + dep optionnelle pyserial
```

Le sous-dossier `tests/integration/` est nouveau ; il accueille tous les tests qui requièrent du hardware. Le `conftest.py` racine reste limité aux tests unitaires (mocks). La séparation est conventionnelle pytest et permet `pytest tests/` (tout) vs `pytest tests/integration/` (hardware seulement) vs `pytest --ignore=tests/integration/` (exclusion explicite ; redondant avec `-m "not devkit"` mais plus rapide en collecte).

---

## 4. Module partagé `_uart_helpers.py`

Contenu extrait depuis `run_p86_manual.py` (lignes 11-102), aucune modification logique :

- Constantes : `PORT_GLOB = "/dev/cu.usbserial-*"`, `BAUD = 115200`.
- Helpers protocole : `crc16(data) -> str`, `make_frame(type_, args, seq, ack, version) -> bytes`, `parse_frames(text) -> list[dict]`, `FRAME_RE` (regex compilée).
- Helpers serial : `reset_esp(s)`, `keepalive(s)`, `read_for(s, duration)`, `wait_for(s, pattern, timeout)`.
- Nouveau : `find_devkit_port() -> str | None` qui fait `sorted(glob.glob(PORT_GLOB))` et retourne le premier match (ordre lexico, déterministe entre runs) ou `None`.

Le préfixe `_` indique un module **privé** au dossier `firmware/tests_devkit/` ; il n'est pas exporté ni installé.

`run_p86_manual.py` est mis à jour pour faire :

```python
from _uart_helpers import (
    crc16, make_frame, parse_frames,
    reset_esp, keepalive, read_for, wait_for,
    BAUD, find_devkit_port,
)
```

Le `PORT = "/dev/cu.usbserial-110"` hardcodé en haut du fichier devient `PORT = find_devkit_port() or "/dev/cu.usbserial-110"` (fallback vers la valeur historique pour ne rien casser si le glob ne matche pas).

---

## 5. Fixtures pytest

Toutes dans `tests/integration/conftest.py` :

```python
import re
import sys
from pathlib import Path

import pytest
import serial

# Permet l'import de _uart_helpers depuis firmware/tests_devkit/
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "firmware" / "tests_devkit"))
from _uart_helpers import (  # noqa: E402
    BAUD, find_devkit_port, make_frame, reset_esp, wait_for,
)


@pytest.fixture(scope="session")
def serial_port():
    """Ouvre le port DevKit pour toute la session. Skip si non détecté."""
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
    """Reset hardware uniquement. Pour sc 1 qui teste le handshake."""
    reset_esp(serial_port)
    return serial_port


@pytest.fixture
def connected_devkit(serial_port):
    """Reset + handshake complet. Pour sc 2-8 qui partent de CONNECTED."""
    reset_esp(serial_port)
    out = wait_for(serial_port, r"<HELLO\|seq=(\d+)\|v=1\|crc=", timeout=4.0)
    m = re.search(r"<HELLO\|seq=(\d+)\|v=1\|crc=", out)
    assert m, "fixture connected_devkit : pas de HELLO reçu après reset"
    serial_port.write(make_frame("HELLO_ACK", seq=0, ack=int(m.group(1))))
    out2 = wait_for(serial_port, r"\[FSM\] -> state 3", timeout=2.0)
    assert "state 3" in out2, "fixture connected_devkit : pas de transition CONNECTED"
    return serial_port
```

**Remarque sur `sys.path`** : on injecte `firmware/tests_devkit/` dans le path car ce dossier n'est pas un package Python (pas de `__init__.py`, c'est volontaire — le harness `run_p86_manual.py` est exécuté en script). Solution la plus simple, sans toucher à la structure existante.

**Pourquoi pas de teardown explicite après sc 8** : sc 8 envoie `CMD_RESET` et le DevKit reboote. Si un test suivant tourne, sa fixture `connected_devkit` fait reset+handshake → état propre. Si sc 8 est le dernier, fin de session, on ferme juste le port ; le DevKit reste en `BOOT_START` (état stable, prêt pour la session suivante).

---

## 6. Forme des 8 tests

Fichier `tests/integration/test_uart_devkit.py`. Chaque test = un scénario, marqué `@pytest.mark.devkit`, avec `assert` à la place de `return False, msg`.

Squelette du sc 1 :

```python
import re

import pytest

from _uart_helpers import crc16, make_frame, read_for, wait_for


@pytest.mark.devkit
def test_sc_1_handshake(raw_devkit):
    """Handshake nominal : BOOT_START → HELLO → HELLO_ACK → state 3."""
    out = wait_for(raw_devkit, r"<HELLO\|seq=(\d+)\|v=1\|crc=", timeout=4.0)
    m = re.search(r"<HELLO\|seq=(\d+)\|v=1\|crc=", out)
    assert m, "aucun HELLO reçu"
    raw_devkit.write(make_frame("HELLO_ACK", seq=0, ack=int(m.group(1))))
    out2 = wait_for(raw_devkit, r"\[FSM\] -> state 3", timeout=2.0)
    assert "state 3" in out2, "pas de transition vers state 3 (CONNECTED)"
```

Sc 2-8 suivent le même patron, en utilisant `connected_devkit` :

```python
@pytest.mark.devkit
def test_sc_2_btn_humain(connected_devkit):
    connected_devkit.reset_input_buffer()
    connected_devkit.write(b"BTN 3 4\n")
    out = wait_for(connected_devkit, r"<MOVE_REQ 3 4\|seq=(\d+)\|crc=", timeout=2.0)
    m = re.search(r"<MOVE_REQ 3 4\|seq=(\d+)\|crc=([0-9A-F]+)>", out)
    assert m, "pas de MOVE_REQ 3 4 émis"
    move_seq = int(m.group(1))
    crc_recv = m.group(2)
    crc_calc = crc16(f"MOVE_REQ 3 4|seq={move_seq}")
    assert crc_recv == crc_calc, f"CRC invalide (recu {crc_recv}, calculé {crc_calc})"
    connected_devkit.write(make_frame("ACK", seq=0, ack=move_seq))
    out2 = wait_for(connected_devkit, r"\[FSM\] -> state 5", timeout=2.0)
    assert "state 5" in out2, "pas de transition state 5 (EXECUTING)"
    out3 = wait_for(connected_devkit, rf"<DONE\|seq=\d+\|ack={move_seq}\|crc=", timeout=4.0)
    assert "DONE" in out3, "pas de DONE reçu"
```

Mapping complet :

| Test | Fixture | Source `run_p86_manual.py` |
|---|---|---|
| `test_sc_1_handshake` | `raw_devkit` | `scenario_1_handshake` (l. 108-123) |
| `test_sc_2_btn_humain` | `connected_devkit` | `scenario_2_btn_humain` (l. 126-152) |
| `test_sc_3_cmd_ia` | `connected_devkit` | `scenario_3_cmd_ia` (l. 155-165) |
| `test_sc_4_idempotence` | `connected_devkit` | `scenario_4_idempotence` (l. 168-191) |
| `test_sc_5_crc_corrompu` | `connected_devkit` | `scenario_5_crc_corrompu` (l. 194-206) |
| `test_sc_6_trame_longue` | `connected_devkit` | `scenario_6_trame_longue` (l. 209-221) |
| `test_sc_7_btn_sans_framing` | `connected_devkit` | `scenario_7_btn_sans_framing` (l. 224-238) |
| `test_sc_8_err_reset` | `connected_devkit` | `scenario_8_err_reset` (l. 241-268) |

Conservation **stricte** des assertions et des messages d'erreur de la version manuelle (sauf adaptation `print` → message d'assert). Aucune amélioration de coverage : c'est un portage 1:1.

---

## 7. Configuration `pyproject.toml`

Le fichier est créé (vide actuellement) avec le minimum :

```toml
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

`devkit` en optional-dependency car les 226 tests unitaires existants n'ont pas besoin de `pyserial` (ils utilisent `MockSerial`). Installation : `uv pip install -e ".[devkit]"`.

Pas de modification des tests existants ni du `tests/conftest.py` racine.

---

## 8. Stratégie de validation

À l'issue de l'implémentation, vérifier sur le DevKit branché (`/dev/cu.usbserial-110` actuellement) :

1. **Découverte pytest** : `pytest --collect-only tests/integration/` doit lister 8 tests `test_sc_*`.
2. **Exécution complète** : `pytest tests/integration/test_uart_devkit.py -v -s` → 8 PASS, runtime ~50-60 s.
3. **Sélection isolée** : `pytest tests/integration/test_uart_devkit.py::test_sc_5_crc_corrompu -v` → PASS isolé (vérifie isolation par fixture).
4. **Filtre marker** : `pytest -m "not devkit"` → 226 tests verts (aucun `devkit` exécuté).
5. **Skip sans hardware** : débrancher DevKit, relancer `pytest tests/integration/` → 8 SKIPPED avec raison « DevKit ESP32 non détecté ».
6. **Non-régression harness manuel** : `python firmware/tests_devkit/run_p86_manual.py 3` doit toujours produire le même résultat qu'avant le refactor.

Si tous ces points passent :

- Cocher sc 9 dans [`firmware/INTEGRATION_TESTS_PENDING.md`](../../../firmware/INTEGRATION_TESTS_PENDING.md).
- Cocher P8.6 dans [`docs/00_plan_global.md`](../../00_plan_global.md), passer P8 de 🚧 à ✅.
- Commit suggéré : `test(p86): porter sc 1-8 en pytest avec marqueur devkit`.

---

## 9. Limitations connues

1. **Sc 8 dépend du watchdog UART**, pas du driver moteur réel. Comme noté dans `firmware/INTEGRATION_TESTS_PENDING.md`, le stub `MotionControl` accepte les coords (99,99). L'`ERR` observé vient du watchdog UART (3 s), pas de la validation métier. La validation par erreur métier sera refaite en P11 avec le vrai driver. **Le portage pytest hérite de cette limitation.**
2. **Détection du port** : `find_devkit_port` retourne le premier match du glob. Si plusieurs DevKits sont branchés, comportement non déterministe. Cas limite improbable en pratique (un seul DevKit pour le projet).
3. **Pas d'export JUnit/XML** : la sortie reste textuelle pytest. Pas de besoin actuel.
4. **Runtime ~50-60 s** : si des optimisations deviennent nécessaires (CI fréquente), envisager une fixture `connected_devkit_session` (scope session) pour les sc qui n'ont pas besoin de reset (sc 2-7 modulo état). Pas pour cette session : on privilégie simplicité et isolation.

---

## 10. Hors scope

- **Sc 4 P9.5** (idempotence d'une CMD perdue) : nécessite instrumentation firmware temporaire, traité dans une session séparée.
- **Tests breadboard** (LED WS2812B, boutons, MCP23017, A4988, servo) : objectif 2 de la session, planifié séparément après réception des composants.
- **Refonte du protocole UART** : Plan 2 reste figé (P8 done).
- **Intégration CI GitHub Actions** : pas pour cette phase. La suite tourne en local.
- **Couverture pytest-cov sur les tests devkit** : pas pertinent (les tests sont end-to-end via serial, pas de couverture Python à mesurer).
