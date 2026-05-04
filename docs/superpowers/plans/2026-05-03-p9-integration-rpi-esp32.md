# Intégration logicielle RPi ↔ ESP32 (P9) — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implémenter intégralement la couche d'orchestration P9 selon le spec figé dans [`2026-05-03-p9-integration-rpi-esp32-design.md`](../specs/2026-05-03-p9-integration-rpi-esp32-design.md). À la fin du plan, [`main.py`](../../../main.py) accepte un mode plateau, le moteur Python dialogue avec l'ESP32 via UART (intentions joueur → ACK/NACK, coups IA → CMD/DONE), le firmware accepte `CMD WALL` et `CMD GAMEOVER` en stub, la robustesse aux déconnexions est en place et testée, et les ~90 tests existants restent verts. Les tests E2E sur DevKit (P9.5) sont reportés au 2026-05-04 (retour DevKit).

**Architecture:** TDD strict côté Python (chaque comportement = test rouge → minimal code → vert → commit). Build-driven côté firmware (modification → `pio run` → vérification compilation sans warning). Ordre privilégié : (1) refactor `InvalidMoveError` + `NackCode` car breaking pour tout le reste, (2) extensions `UartClient` (atomiques), (3) `GameSession` (cœur de P9), (4) `main.py` CLI, (5) firmware stubs (autonome), (6) documentation. Les fixtures `MockSerial` et `MockClock` ([`tests/conftest.py`](../../../tests/conftest.py)) couvrent tout le scope test sans hardware.

**Tech Stack:** Python 3.x + `pyserial` + `pytest` + `argparse` (stdlib) — aucune dépendance ajoutée. Arduino C++ + PlatformIO côté firmware (déjà au stack).

**Phases couvertes du plan global :**
- 🟢 P9.1 (CLI mode plateau) — Tasks 16–17
- 🟢 P9.2 (flux entrant ACK/NACK) — Tasks 11
- 🟢 P9.3 (flux sortant CMD) — Tasks 12–13
- 🟢 P9.4 (firmware stubs `CMD WALL`/`CMD GAMEOVER`) — Task 18
- 🟢 P9.6 (mise à jour docs) — Tasks 19–22
- 📅 P9.5 (E2E DevKit) — checklist à compléter au retour DevKit (2026-05-04), Task 23

---

## Vue d'ensemble — fichiers créés / modifiés

### Côté Python

| Fichier | Action |
|---|---|
| `quoridor_engine/core.py` | **Modifier** — ajouter `NackCode` Enum, signature `InvalidMoveError(message, code)`, propager le code aux 12 sites de levée |
| `quoridor_engine/ai.py` | **Modifier** — propager le code au 1 site de levée (interne, jamais émis sur le wire) |
| `quoridor_engine/uart_client.py` | **Modifier** — compteur rejected, détection thread mort, fix `_reset_session`, fix `handle_err_received`, thread keepalive |
| `quoridor_engine/__init__.py` | **Modifier** — exposer `NackCode` et `GameSession` |
| `quoridor_engine/game_session.py` | **Créer** — classe `GameSession` (boucle de jeu plateau, ~250 lignes attendues) |
| `main.py` | **Modifier** — argparse, dispatch console/plateau, `run_plateau()` |
| `tests/test_core.py` | **Modifier** — paramétrer ≥ 1 test par site `InvalidMoveError` pour vérifier `.code` |
| `tests/test_uart_client.py` | **Modifier** — 4 nouveaux tests (`_rejected_count`, thread mort, `_reset_session`, keepalive) |
| `tests/test_game_session.py` | **Créer** — 9 tests planifiés (cf. spec §4.5/§5.5/§6.7) |
| `tests/test_main_cli.py` | **Créer** — 3-4 tests argparse (cf. spec §3.4) |

### Côté firmware ESP32

| Fichier | Action |
|---|---|
| `firmware/src/GameController.cpp` | **Modifier** — 6 lignes nettes : 2 stubs `CMD WALL` et `CMD GAMEOVER` dans `tickConnected` |

### Documentation

| Fichier | Action |
|---|---|
| `docs/02_architecture.md` | **Modifier** — décrire la couche P9 (GameSession, dispatch console/plateau, CLI) |
| `docs/06_protocole_uart.md` | **Modifier** — note "P9 émet `MOVE`/`WALL`/`GAMEOVER` ; `HIGHLIGHT`/`SET_TURN` réservés à P11" |
| `docs/00_plan_global.md` | **Modifier** — cocher P9.1–P9.4 et P9.6, laisser P9.5 ouvert (DevKit) |
| `CHANGELOG.md` | **Modifier** — entrée P9 |
| `firmware/INTEGRATION_TESTS_PENDING.md` | **Modifier ou créer** — ajouter checklist P9.5 (4 scénarios) |

---

## Notes de contexte importantes

**Convention TDD :** chaque tâche Python suit le cycle rouge → vert → commit. Les tests sont écrits AVANT le code. Si un test n'échoue pas avant l'écriture du code, c'est qu'il ne teste rien d'utile — réécrire le test.

**MockSerial / MockClock :** les fixtures `mock_serial` et `mock_clock` sont déjà dans [`tests/conftest.py`](../../../tests/conftest.py). API rapide :
- `mock_serial.inject_rx(b"<HELLO|seq=0|v=1|crc=...>\n")` → simule un octet entrant.
- `mock_serial.get_tx() -> bytes` → ce que le code Python a écrit (vide le buffer).
- `mock_serial.peek_tx() -> bytes` → idem sans vider.
- `mock_clock()` → temps virtuel ; `mock_clock.advance(0.5)` pour avancer.

**Pattern test thread keepalive :** comme le thread tourne en arrière-plan, on injecte `mock_clock` dans `UartClient` et on instrumente le thread pour utiliser ce clock. Sinon le thread utilisera `time.sleep(1.0)` réel et le test sera lent. Le `UartClient` actuel accepte déjà `clock=` au constructeur — on le passera au thread via un paramètre.

**Format de trame attendu (rappel) :** `<TYPE [args]|seq=N[|ack=M][|v=K]|crc=XXXX>\n`. Le helper `Frame(type, args, seq, ack, version).encode()` construit la trame correctement avec CRC. Le helper `Frame.decode(raw)` parse et valide.

**Convention joueurs en mode plateau :** `j1` = humain (boutons physiques), `j2` = IA. Aucune autre configuration n'est exposée par P9.

**Si DevKit indisponible :** s'arrêter à `pio run` (compilation seule) pour la Task 18. Les tests d'injection manuelle reportés à la checklist `firmware/INTEGRATION_TESTS_PENDING.md` (Task 23).

**Aucun nouveau type de trame ni code d'erreur protocole** — P9 est purement une couche d'orchestration au-dessus du protocole UART Plan 2 figé.

---

## Phase A — Refactor `InvalidMoveError` + `NackCode`

> Cette phase introduit un changement breaking dans la signature de `InvalidMoveError`. Tous les tests existants `pytest.raises(InvalidMoveError)` continuent de fonctionner (pytest capture l'exception peu importe les arguments), mais le code qui CONSTRUIT `InvalidMoveError(...)` doit être mis à jour. C'est pourquoi cette phase est en premier : aucune autre tâche ne peut compiler tant que les 13 sites n'ont pas été migrés.

### Task 1: Ajouter `NackCode` Enum dans core.py

**Files:**
- Modify: `quoridor_engine/core.py:71-...` (proche de `InvalidMoveError`)
- Test: `tests/test_core.py` (ajout d'un nouveau test class)

- [ ] **Step 1: Écrire le test rouge pour `NackCode`**

Ajouter à la fin de [`tests/test_core.py`](../../../tests/test_core.py) :

```python
def test_nack_code_values_aligned_with_uart_protocol():
    """NackCode.X.value doit correspondre exactement aux codes du spec UART §4.4."""
    from quoridor_engine.core import NackCode

    assert NackCode.ILLEGAL.value == "ILLEGAL"
    assert NackCode.OUT_OF_BOUNDS.value == "OUT_OF_BOUNDS"
    assert NackCode.WRONG_TURN.value == "WRONG_TURN"
    assert NackCode.WALL_BLOCKED.value == "WALL_BLOCKED"
    assert NackCode.NO_WALLS_LEFT.value == "NO_WALLS_LEFT"
    assert NackCode.INVALID_FORMAT.value == "INVALID_FORMAT"


def test_nack_code_is_str_enum():
    """NackCode hérite de str pour permettre `nack.value` direct dans les trames."""
    from quoridor_engine.core import NackCode

    assert isinstance(NackCode.ILLEGAL, str)
    assert isinstance(NackCode.ILLEGAL.value, str)
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
cd /Users/silouanechaumais/Documents/01_ICAM/2025-2026_Année_3/Projet_mécatronique/programmation
pytest tests/test_core.py::test_nack_code_values_aligned_with_uart_protocol tests/test_core.py::test_nack_code_is_str_enum -v
```

Expected : FAIL avec `ImportError: cannot import name 'NackCode' from 'quoridor_engine.core'`.

- [ ] **Step 3: Implémenter `NackCode`**

Ajouter dans [`quoridor_engine/core.py`](../../../quoridor_engine/core.py) juste avant la classe `InvalidMoveError` (vers la ligne 70) :

```python
from enum import Enum


class NackCode(str, Enum):
    """Codes d'erreur typés pour les NACK du protocole UART Plan 2.

    Les valeurs MAJUSCULES sont alignées exactement sur le catalogue §4.4
    du spec protocole [docs/06_protocole_uart.md].
    """
    ILLEGAL         = "ILLEGAL"
    OUT_OF_BOUNDS   = "OUT_OF_BOUNDS"
    WRONG_TURN      = "WRONG_TURN"
    WALL_BLOCKED    = "WALL_BLOCKED"
    NO_WALLS_LEFT   = "NO_WALLS_LEFT"
    INVALID_FORMAT  = "INVALID_FORMAT"
```

Si `from enum import Enum` est déjà importé en haut du fichier, ne pas le doubler.

- [ ] **Step 4: Vérifier que les tests passent**

```bash
pytest tests/test_core.py::test_nack_code_values_aligned_with_uart_protocol tests/test_core.py::test_nack_code_is_str_enum -v
```

Expected : 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add quoridor_engine/core.py tests/test_core.py
git commit -m "feat(core): ajouter enum NackCode aligné sur le protocole UART"
```

---

### Task 2: Modifier la signature de `InvalidMoveError` (ajout `code` obligatoire)

**Files:**
- Modify: `quoridor_engine/core.py:71-78` (signature `InvalidMoveError`)
- Test: `tests/test_core.py`

- [ ] **Step 1: Écrire les tests rouges**

Ajouter à [`tests/test_core.py`](../../../tests/test_core.py) :

```python
def test_invalid_move_error_requires_code():
    """InvalidMoveError doit imposer un argument code obligatoire."""
    import pytest
    from quoridor_engine.core import InvalidMoveError

    with pytest.raises(TypeError):
        InvalidMoveError("message sans code")  # manque code → TypeError


def test_invalid_move_error_exposes_code_attribute():
    """L'attribut .code est accessible après levée."""
    from quoridor_engine.core import InvalidMoveError, NackCode

    err = InvalidMoveError("test", NackCode.ILLEGAL)
    assert err.code == NackCode.ILLEGAL
    assert err.code.value == "ILLEGAL"
    assert str(err) == "test"
```

- [ ] **Step 2: Vérifier que les tests échouent**

```bash
pytest tests/test_core.py::test_invalid_move_error_requires_code tests/test_core.py::test_invalid_move_error_exposes_code_attribute -v
```

Expected : FAIL — la classe actuelle accepte `InvalidMoveError("foo")` sans erreur.

- [ ] **Step 3: Modifier la signature**

Remplacer la classe `InvalidMoveError` actuelle dans [`quoridor_engine/core.py`](../../../quoridor_engine/core.py) (vers la ligne 71) par :

```python
class InvalidMoveError(Exception):
    """Exception levée pour un coup invalide selon les règles Quoridor.

    Args:
        message: description humaine (en français)
        code: NackCode obligatoire, utilisé pour construire la trame NACK
              côté UART. Aligné sur le catalogue §4.4 du protocole.
    """

    def __init__(self, message: str, code: "NackCode"):
        super().__init__(message)
        self.code = code
```

- [ ] **Step 4: Vérifier que les nouveaux tests passent — mais que les anciens échouent**

```bash
pytest tests/test_core.py::test_invalid_move_error_requires_code tests/test_core.py::test_invalid_move_error_exposes_code_attribute -v
```

Expected : 2 PASS.

```bash
pytest tests/test_core.py tests/test_walls.py tests/test_moves.py -v 2>&1 | tail -30
```

Expected : ERREURS sur les tests qui appellent du code qui CONSTRUIT `InvalidMoveError(...)` sans `code`. C'est attendu — Task 3 corrige tous les sites.

- [ ] **Step 5: NE PAS COMMITER avant Task 3**

La signature est cassée pour tout le code qui construit `InvalidMoveError`. On commitera Task 2 + Task 3 ensemble pour ne jamais avoir un état rouge en HEAD.

---

### Task 3: Propager `NackCode` aux 13 sites de levée

**Files:**
- Modify: `quoridor_engine/core.py` (12 sites — lignes 405, 409, 558, 564, 576, 582, 591, 627, 631, 650, 654, 716)
- Modify: `quoridor_engine/ai.py` (1 site — ligne ~1129)

- [ ] **Step 1: Mettre à jour `core.py:405` (déplacement, mauvais joueur) → `WRONG_TURN`**

Localiser dans [`quoridor_engine/core.py:405`](../../../quoridor_engine/core.py#L405) :

```python
raise InvalidMoveError(f"Ce n'est pas le tour du joueur {player}.")
```

Remplacer par :

```python
raise InvalidMoveError(f"Ce n'est pas le tour du joueur {player}.", NackCode.WRONG_TURN)
```

- [ ] **Step 2: Mettre à jour `core.py:409` (déplacement vers case invalide) → `ILLEGAL`**

```python
raise InvalidMoveError(f"Le déplacement vers {target_coord} est invalide.", NackCode.ILLEGAL)
```

- [ ] **Step 3: Mettre à jour `core.py:558` (mur hors plateau) → `OUT_OF_BOUNDS`**

```python
raise InvalidMoveError("Le mur est en dehors des limites de placement.", NackCode.OUT_OF_BOUNDS)
```

- [ ] **Step 4: Mettre à jour `core.py:564` (mur identique existant) → `WALL_BLOCKED`**

```python
raise InvalidMoveError("Un mur identique existe déjà.", NackCode.WALL_BLOCKED)
```

- [ ] **Step 5: Mettre à jour `core.py:576` (mur chevauche) → `WALL_BLOCKED`**

```python
raise InvalidMoveError("Le mur chevauche un mur existant.", NackCode.WALL_BLOCKED)
```

- [ ] **Step 6: Mettre à jour `core.py:582` (mur chevauche perpendiculaire) → `WALL_BLOCKED`**

```python
raise InvalidMoveError("Le mur chevauche un mur existant.", NackCode.WALL_BLOCKED)
```

> Si `core.py:576` et `core.py:582` ont le même message, les deux remplacements seront identiques — pas de problème.

- [ ] **Step 7: Mettre à jour `core.py:591` (mur croise mur existant) → `WALL_BLOCKED`**

```python
raise InvalidMoveError("Le mur croise un mur existant.", NackCode.WALL_BLOCKED)
```

- [ ] **Step 8: Mettre à jour `core.py:627` (placement mur, mauvais joueur) → `WRONG_TURN`**

```python
raise InvalidMoveError(f"Ce n'est pas le tour du joueur {player}.", NackCode.WRONG_TURN)
```

- [ ] **Step 9: Mettre à jour `core.py:631` (plus de murs) → `NO_WALLS_LEFT`**

```python
raise InvalidMoveError("Le joueur n'a plus de murs.", NackCode.NO_WALLS_LEFT)
```

- [ ] **Step 10: Mettre à jour `core.py:650` (mur bloque j1) → `WALL_BLOCKED`**

```python
raise InvalidMoveError("Le mur bloque le chemin du joueur 1.", NackCode.WALL_BLOCKED)
```

- [ ] **Step 11: Mettre à jour `core.py:654` (mur bloque j2) → `WALL_BLOCKED`**

```python
raise InvalidMoveError("Le mur bloque le chemin du joueur 2.", NackCode.WALL_BLOCKED)
```

- [ ] **Step 12: Mettre à jour `core.py:716` (clic non-adjacent) → `INVALID_FORMAT`**

Localiser dans [`quoridor_engine/core.py:716`](../../../quoridor_engine/core.py#L716) :

```python
raise InvalidMoveError("Les deux cases cliquées doivent être adjacentes.")
```

Remplacer par :

```python
raise InvalidMoveError("Les deux cases cliquées doivent être adjacentes.", NackCode.INVALID_FORMAT)
```

- [ ] **Step 13: Mettre à jour `ai.py:1129` (erreur interne IA) → `ILLEGAL`**

Localiser dans [`quoridor_engine/ai.py`](../../../quoridor_engine/ai.py) (vers ligne 1129, peut bouger légèrement) :

```bash
grep -n "raise InvalidMoveError" quoridor_engine/ai.py
```

Remplacer la levée trouvée par :

```python
raise InvalidMoveError("...message original...", NackCode.ILLEGAL)
```

Et ajouter en haut du fichier l'import :

```python
from quoridor_engine.core import InvalidMoveError, NackCode  # ou ajouter NackCode si InvalidMoveError est déjà importé
```

- [ ] **Step 14: Vérifier que toute la suite passe**

```bash
pytest -x 2>&1 | tail -20
```

Expected : tous les tests existants passent (les `pytest.raises(InvalidMoveError)` continuent de fonctionner sans modification — pytest capture l'exception sans regarder ses arguments).

- [ ] **Step 15: Commit (Tasks 2 + 3 ensemble)**

```bash
git add quoridor_engine/core.py quoridor_engine/ai.py tests/test_core.py
git commit -m "feat(core): InvalidMoveError porte un NackCode obligatoire (13 sites migrés)"
```

---

### Task 4: Tests paramétrés `.code` sur les sites principaux

**Files:**
- Modify: `tests/test_core.py`, `tests/test_moves.py`, `tests/test_walls.py`

- [ ] **Step 1: Écrire les tests rouges pour vérifier `.code`**

Ajouter à [`tests/test_core.py`](../../../tests/test_core.py) (créer une nouvelle classe `TestInvalidMoveErrorCodes` à la fin) :

```python
class TestInvalidMoveErrorCodes:
    """Vérifie que chaque site de InvalidMoveError porte le bon NackCode."""

    def test_wrong_turn_on_pawn_move(self):
        from quoridor_engine.core import QuoridorGame, InvalidMoveError, NackCode

        game = QuoridorGame()
        # j1 commence, on essaie de jouer pour j2
        with pytest.raises(InvalidMoveError) as exc:
            game.play_move_for_player(("deplacement", (1, 3)), "j2")
        # Note : si play_move_for_player n'existe pas, utiliser core.move_pawn() directement
        assert exc.value.code == NackCode.WRONG_TURN

    def test_illegal_pawn_move_target(self):
        from quoridor_engine.core import QuoridorGame, InvalidMoveError, NackCode

        game = QuoridorGame()
        with pytest.raises(InvalidMoveError) as exc:
            game.play_move(("deplacement", (3, 3)))  # case non-adjacente
        assert exc.value.code == NackCode.ILLEGAL

    def test_wall_out_of_bounds(self):
        from quoridor_engine.core import QuoridorGame, InvalidMoveError, NackCode

        game = QuoridorGame()
        with pytest.raises(InvalidMoveError) as exc:
            game.play_move(("mur", ("h", 10, 10, 2)))
        assert exc.value.code == NackCode.OUT_OF_BOUNDS

    def test_wall_already_exists(self):
        from quoridor_engine.core import QuoridorGame, InvalidMoveError, NackCode

        game = QuoridorGame()
        game.play_move(("mur", ("h", 2, 2, 2)))
        # j2 tente le même mur
        game.play_move(("deplacement", (1, 3)))   # j2 bouge pour rendre la main à j1 ? À adapter selon API
        with pytest.raises(InvalidMoveError) as exc:
            game.play_move(("mur", ("h", 2, 2, 2)))
        assert exc.value.code == NackCode.WALL_BLOCKED

    def test_no_walls_left(self):
        from quoridor_engine.core import QuoridorGame, InvalidMoveError, NackCode

        game = QuoridorGame()
        # Épuiser les 6 murs de j1 (à réécrire selon l'API exacte qui permet
        # d'épuiser les murs ; sinon manipuler directement game._current_state)
        for i in range(6):
            game.play_move(("mur", ("h", i, 0, 2)))    # j1
            game.play_move(("deplacement", ...))        # j2 — placeholder à remplir selon la mécanique réelle
        with pytest.raises(InvalidMoveError) as exc:
            game.play_move(("mur", ("h", 0, 4, 2)))
        assert exc.value.code == NackCode.NO_WALLS_LEFT

    def test_invalid_format_double_click_non_adjacent(self):
        from quoridor_engine.core import interpret_double_click, InvalidMoveError, NackCode

        with pytest.raises(InvalidMoveError) as exc:
            interpret_double_click((0, 0), (5, 5))
        assert exc.value.code == NackCode.INVALID_FORMAT
```

> **Note importante :** les détails exacts (API `play_move`, état initial, configuration de `j2`) dépendent de la mécanique de jeu réelle. Si une assertion ne peut pas être configurée parce que l'API n'expose pas le scénario directement, **simplifier le test au minimum nécessaire** — ce qui compte est de vérifier `.code`, pas de reproduire toute la mécanique. En dernier recours, instancier `InvalidMoveError` directement et vérifier `.code` (ne valide pas le site mais valide la propagation).

- [ ] **Step 2: Vérifier que les tests passent**

```bash
pytest tests/test_core.py::TestInvalidMoveErrorCodes -v
```

Expected : 6 PASS. Si certains tests rencontrent des difficultés à atteindre le site (mécanique de jeu trop contraignante), réduire le nombre de tests à ceux qui sont praticables (minimum : 1 test par code distinct, soit 5 codes = 5 tests).

- [ ] **Step 3: Vérifier que les ~90 tests existants passent toujours**

```bash
pytest 2>&1 | tail -5
```

Expected : aucun test cassé par rapport à HEAD~1.

- [ ] **Step 4: Commit**

```bash
git add tests/test_core.py
git commit -m "test(core): vérifier InvalidMoveError.code pour chaque NackCode distinct"
```

---

## Phase B — Extensions `UartClient`

> Cette phase fait évoluer `UartClient` pour P9 (compteur, robustesse). Toutes les modifications sont **atomiques** : on peut commit chaque tâche indépendamment et la suite reste verte.

### Task 5: Compteur `_rejected_count` + getter

**Files:**
- Modify: `quoridor_engine/uart_client.py:226-236` (init `__init__`) et `:294-296` (branche `except UartProtocolError`)
- Test: `tests/test_uart_client.py`

- [ ] **Step 1: Écrire le test rouge**

Ajouter à [`tests/test_uart_client.py`](../../../tests/test_uart_client.py) :

```python
class TestRejectedCount:
    """Vérifie le compteur de trames mal formées (cf. spec P9 §9.2)."""

    def test_rejected_count_starts_at_zero(self, mock_serial):
        from quoridor_engine import UartClient

        client = UartClient(mock_serial)
        assert client.get_rejected_count() == 0

    def test_rejected_count_increments_on_malformed_frame(self, mock_serial):
        import time
        from quoridor_engine import UartClient

        client = UartClient(mock_serial)
        client._start_reader_thread()
        try:
            # Trame avec CRC invalide (volontairement faux)
            mock_serial.inject_rx(b"<MOVE_REQ 3 4|seq=0|crc=0000>\n")
            time.sleep(0.1)  # laisser le reader thread la consommer
            assert client.get_rejected_count() >= 1
        finally:
            client.close()
```

- [ ] **Step 2: Vérifier qu'il échoue**

```bash
pytest tests/test_uart_client.py::TestRejectedCount -v
```

Expected : FAIL — `AttributeError: 'UartClient' object has no attribute 'get_rejected_count'`.

- [ ] **Step 3: Implémenter le compteur**

Dans [`quoridor_engine/uart_client.py`](../../../quoridor_engine/uart_client.py), `UartClient.__init__` (vers ligne 220) ajouter :

```python
self._rejected_count = 0
self._rejected_lock = threading.Lock()
```

Modifier la branche `except UartProtocolError: pass` dans `_dispatch_line` (vers ligne 294) :

```python
except UartProtocolError:
    # Rejet silencieux (cf. §3.6 spec protocole). Compteur incrémenté pour debug.
    with self._rejected_lock:
        self._rejected_count += 1
```

Ajouter une méthode publique :

```python
def get_rejected_count(self) -> int:
    """Retourne le nombre de trames mal formees recues depuis le boot."""
    with self._rejected_lock:
        return self._rejected_count
```

- [ ] **Step 4: Vérifier que les tests passent**

```bash
pytest tests/test_uart_client.py::TestRejectedCount -v
```

Expected : 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add quoridor_engine/uart_client.py tests/test_uart_client.py
git commit -m "feat(uart_client): compteur _rejected_count + get_rejected_count()"
```

---

### Task 6: Détection thread mort dans `_send_frame`

**Files:**
- Modify: `quoridor_engine/uart_client.py` (méthode `_is_reader_alive`, modif `_send_frame`)
- Test: `tests/test_uart_client.py`

- [ ] **Step 1: Écrire le test rouge**

Ajouter à `tests/test_uart_client.py` :

```python
class TestReaderThreadDeath:
    """Vérifie que la mort du thread de lecture est détectée à l'envoi."""

    def test_send_frame_raises_when_reader_thread_dead(self, mock_serial):
        from quoridor_engine import UartClient
        from quoridor_engine.uart_client import UartError, Frame

        client = UartClient(mock_serial)
        client._start_reader_thread()
        # Tuer le thread de lecture proprement
        client._stop_reader.set()
        client._reader_thread.join(timeout=2)
        assert not client._reader_thread.is_alive()

        # Toute tentative d'envoi doit lever UartError
        import pytest
        frame = Frame(type="KEEPALIVE", args="", seq=0)
        with pytest.raises(UartError, match="reader thread"):
            client._send_frame(frame)

    def test_is_reader_alive_returns_false_before_start(self, mock_serial):
        from quoridor_engine import UartClient

        client = UartClient(mock_serial)
        assert client._is_reader_alive() is False
```

- [ ] **Step 2: Vérifier qu'il échoue**

```bash
pytest tests/test_uart_client.py::TestReaderThreadDeath -v
```

Expected : FAIL — `AttributeError: '_is_reader_alive'` ou bien `_send_frame` n'a pas le check.

- [ ] **Step 3: Implémenter**

Dans [`quoridor_engine/uart_client.py`](../../../quoridor_engine/uart_client.py), ajouter dans la classe `UartClient` :

```python
def _is_reader_alive(self) -> bool:
    """True ssi le thread de lecture tourne. Cf. spec P9 §6.2."""
    return self._reader_thread is not None and self._reader_thread.is_alive()
```

Modifier `_send_frame` (vers ligne 363) :

```python
def _send_frame(self, frame: "Frame") -> None:
    """Envoie une frame deja construite sur le port serie.

    Leve UartError si le thread de lecture est mort (cf. spec P9 §6.2).
    """
    if not self._is_reader_alive():
        raise UartError("reader thread died — connexion cassée")
    self._serial.write(frame.encode())
```

- [ ] **Step 4: Vérifier que les tests passent**

```bash
pytest tests/test_uart_client.py::TestReaderThreadDeath -v
```

Expected : 2 PASS.

- [ ] **Step 5: Vérifier que le reste passe toujours**

```bash
pytest tests/test_uart_client.py 2>&1 | tail -5
```

Expected : aucune régression.

- [ ] **Step 6: Commit**

```bash
git add quoridor_engine/uart_client.py tests/test_uart_client.py
git commit -m "feat(uart_client): détection thread mort → UartError immédiat"
```

---

### Task 7: `_reset_session` clear `is_connected`

**Files:**
- Modify: `quoridor_engine/uart_client.py:487-492` (méthode `_reset_session`)
- Test: `tests/test_uart_client.py`

- [ ] **Step 1: Écrire le test rouge**

Ajouter à `tests/test_uart_client.py` :

```python
class TestResetSessionClearsConnection:
    """Régression bug : _reset_session doit clear is_connected (spec P9 §6.3)."""

    def test_reset_session_sets_is_connected_false(self, mock_serial):
        from quoridor_engine import UartClient

        client = UartClient(mock_serial)
        client.is_connected = True   # simule un état post-handshake
        client._reset_session()
        assert client.is_connected is False

    def test_boot_start_received_clears_is_connected(self, mock_serial):
        import time
        from quoridor_engine import UartClient
        from quoridor_engine.uart_client import Frame

        client = UartClient(mock_serial)
        client.is_connected = True
        client._start_reader_thread()
        try:
            # Simuler un BOOT_START reçu (ESP32 a rebooté de lui-même)
            boot_frame = Frame(type="BOOT_START", args="", seq=0).encode()
            mock_serial.inject_rx(boot_frame)
            time.sleep(0.15)  # laisser le reader consommer
            assert client.is_connected is False
        finally:
            client.close()
```

- [ ] **Step 2: Vérifier qu'il échoue**

```bash
pytest tests/test_uart_client.py::TestResetSessionClearsConnection -v
```

Expected : FAIL sur `assert client.is_connected is False` car la méthode actuelle ne le fait pas.

- [ ] **Step 3: Modifier `_reset_session`**

Dans [`quoridor_engine/uart_client.py`](../../../quoridor_engine/uart_client.py), méthode `_reset_session` (vers ligne 487) :

```python
def _reset_session(self) -> None:
    """Reset complet de la session apres reboot ESP32 (sec 5.1 spec).

    Ajout P9 (§6.3) : remettre is_connected à False pour forcer un re-handshake.
    """
    with self._tx_seq_lock:
        self._tx_seq = 0
    self._last_request_seq = None
    self._last_err_received = None
    self.is_connected = False  # AJOUT P9 §6.3
```

- [ ] **Step 4: Vérifier que les tests passent**

```bash
pytest tests/test_uart_client.py::TestResetSessionClearsConnection -v
```

Expected : 2 PASS.

- [ ] **Step 5: Vérifier non-régression**

```bash
pytest tests/test_uart_client.py 2>&1 | tail -5
```

Expected : aucune régression.

- [ ] **Step 6: Commit**

```bash
git add quoridor_engine/uart_client.py tests/test_uart_client.py
git commit -m "fix(uart_client): _reset_session clear is_connected (force re-handshake)"
```

---

### Task 8: `handle_err_received` re-handshake (clear is_connected)

**Files:**
- Modify: `quoridor_engine/uart_client.py:460-479` (méthode `handle_err_received`)
- Test: `tests/test_uart_client.py`

- [ ] **Step 1: Écrire les tests rouges**

Ajouter à `tests/test_uart_client.py` :

```python
class TestHandleErrRecovery:
    """Vérifie le re-handshake forcé après ERR récupérable (spec P9 §6.4)."""

    def test_recoverable_err_sends_reset_then_clears_is_connected(self, mock_serial):
        from quoridor_engine import UartClient
        from quoridor_engine.uart_client import Frame

        client = UartClient(mock_serial)
        client.is_connected = True   # session active
        client._start_reader_thread()
        try:
            err_frame = Frame(type="ERR", args="UART_LOST", seq=10)
            result = client.handle_err_received(err_frame)
            assert result == "RESET_SENT"
            # CMD_RESET doit être envoyé AVANT que is_connected passe à False
            tx = mock_serial.peek_tx()
            assert b"CMD_RESET" in tx
            # is_connected est maintenant False
            assert client.is_connected is False
        finally:
            client.close()

    def test_non_recoverable_err_raises_and_keeps_is_connected(self, mock_serial):
        import pytest
        from quoridor_engine import UartClient
        from quoridor_engine.uart_client import Frame, UartHardwareError

        client = UartClient(mock_serial)
        client.is_connected = True
        client._start_reader_thread()
        try:
            err_frame = Frame(type="ERR", args="HOMING_FAILED", seq=11)
            with pytest.raises(UartHardwareError):
                client.handle_err_received(err_frame)
            # Non récupérable : is_connected reste True (partie figée, partie remontée à l'app)
            assert client.is_connected is True
        finally:
            client.close()
```

- [ ] **Step 2: Vérifier qu'il échoue**

```bash
pytest tests/test_uart_client.py::TestHandleErrRecovery -v
```

Expected : FAIL — `is_connected` ne passe pas à False dans le code actuel.

- [ ] **Step 3: Modifier `handle_err_received`**

Dans [`quoridor_engine/uart_client.py`](../../../quoridor_engine/uart_client.py), méthode `handle_err_received` (vers ligne 460) :

```python
def handle_err_received(self, frame: "Frame") -> str:
    """Traite une trame ERR recue de l'ESP32.

    Si recuperable : envoie CMD_RESET, **clear is_connected** (force re-handshake
    cote orchestrateur), retourne "RESET_SENT".
    Si non recuperable : leve UartHardwareError. is_connected n'est pas touche.

    Ordre critique (cf. spec P9 §6.4) : send_cmd_reset() est appelé AVANT
    de passer is_connected à False, sinon send_cmd_reset no-op silencieusement.
    """
    if frame.type != "ERR":
        raise ValueError(f"handle_err_received attend une trame ERR, recu {frame.type}")

    code = frame.args or "UNKNOWN"

    if code != self._last_err_received:
        self._last_err_received = code

    if is_recoverable_err(code):
        self.send_cmd_reset()        # ← envoyer CMD_RESET d'abord
        self.is_connected = False    # ← AJOUT P9 §6.4 : force re-handshake (après l'envoi)
        return "RESET_SENT"
    raise UartHardwareError(code)
```

- [ ] **Step 4: Vérifier que les tests passent**

```bash
pytest tests/test_uart_client.py::TestHandleErrRecovery -v
```

Expected : 2 PASS.

- [ ] **Step 5: Vérifier non-régression**

```bash
pytest tests/test_uart_client.py 2>&1 | tail -5
```

Expected : aucune régression.

- [ ] **Step 6: Commit**

```bash
git add quoridor_engine/uart_client.py tests/test_uart_client.py
git commit -m "feat(uart_client): handle_err_received clear is_connected sur ERR récupérable"
```

---

### Task 9: Thread keepalive

**Files:**
- Modify: `quoridor_engine/uart_client.py` (init, démarrer dans `connect`, stopper dans `close`)
- Test: `tests/test_uart_client.py`

- [ ] **Step 1: Écrire les tests rouges**

Ajouter à `tests/test_uart_client.py` :

```python
class TestKeepaliveThread:
    """Vérifie le thread keepalive (spec P9 §2.4 / §B Phase B)."""

    def _make_connected_client(self, mock_serial):
        """Helper : injecte un HELLO et complète le handshake."""
        from quoridor_engine import UartClient
        from quoridor_engine.uart_client import Frame
        client = UartClient(mock_serial)
        # Pré-remplir un HELLO valide
        hello = Frame(type="HELLO", args="", seq=0, version=UartClient.PROTOCOL_VERSION)
        mock_serial.inject_rx(hello.encode())
        client.connect(timeout=2.0)
        return client

    def test_keepalive_thread_started_after_connect(self, mock_serial):
        client = self._make_connected_client(mock_serial)
        try:
            assert client._keepalive_thread is not None
            assert client._keepalive_thread.is_alive()
        finally:
            client.close()

    def test_keepalive_thread_stops_on_close(self, mock_serial):
        client = self._make_connected_client(mock_serial)
        ka_thread = client._keepalive_thread
        client.close()
        ka_thread.join(timeout=3)
        assert not ka_thread.is_alive()

    def test_keepalive_emits_keepalive_frames_periodically(self, mock_serial):
        import time
        client = self._make_connected_client(mock_serial)
        try:
            mock_serial.get_tx()  # vider tx (HELLO_ACK)
            time.sleep(2.5)       # 2 keepalives attendus (1 Hz)
            tx = mock_serial.get_tx()
            keepalive_count = tx.count(b"KEEPALIVE")
            assert keepalive_count >= 2, f"attendu >=2 KEEPALIVE, trouvé {keepalive_count}"
        finally:
            client.close()
```

- [ ] **Step 2: Vérifier qu'ils échouent**

```bash
pytest tests/test_uart_client.py::TestKeepaliveThread -v
```

Expected : FAIL — `AttributeError: '_keepalive_thread'`.

- [ ] **Step 3: Implémenter le thread**

Dans [`quoridor_engine/uart_client.py`](../../../quoridor_engine/uart_client.py), `UartClient` :

a) Dans `__init__` ajouter :

```python
self._keepalive_thread: Optional[threading.Thread] = None
self._stop_keepalive = threading.Event()
self._keepalive_period = 1.0  # secondes (spec §2.4)
```

b) Ajouter la boucle keepalive et le helper de démarrage :

```python
def _start_keepalive_thread(self) -> None:
    """Démarre le thread keepalive (idempotent). Appelé après handshake réussi."""
    if self._keepalive_thread is not None and self._keepalive_thread.is_alive():
        return
    self._stop_keepalive.clear()
    self._keepalive_thread = threading.Thread(
        target=self._keepalive_loop, daemon=True, name="UartKeepalive"
    )
    self._keepalive_thread.start()

def _keepalive_loop(self) -> None:
    """Émet 1 KEEPALIVE par seconde tant que la session est connectée."""
    while not self._stop_keepalive.is_set():
        # send_keepalive est déjà no-op si is_connected == False
        try:
            self.send_keepalive()
        except Exception:
            # Si _send_frame lève (thread reader mort), on arrête le keepalive
            break
        # sleep "interruptible" via Event.wait()
        if self._stop_keepalive.wait(timeout=self._keepalive_period):
            return
```

c) Démarrer dans `connect()` (à la fin, après `self.is_connected = True`) :

```python
self._start_keepalive_thread()
```

d) Stopper dans `close()` (ajouter avant `self._stop_reader.set()`) :

```python
self._stop_keepalive.set()
if self._keepalive_thread is not None:
    self._keepalive_thread.join(timeout=2)
```

- [ ] **Step 4: Vérifier que les tests passent**

```bash
pytest tests/test_uart_client.py::TestKeepaliveThread -v
```

Expected : 3 PASS. Le test périodique est lent (~2.5 s) — c'est attendu.

- [ ] **Step 5: Vérifier non-régression**

```bash
pytest tests/test_uart_client.py 2>&1 | tail -5
```

Expected : aucune régression.

- [ ] **Step 6: Commit**

```bash
git add quoridor_engine/uart_client.py tests/test_uart_client.py
git commit -m "feat(uart_client): thread keepalive (1 Hz) lancé après handshake"
```

---

## Phase C — Création `GameSession`

> Cette phase crée le module `game_session.py` qui orchestre la boucle de jeu plateau. Tout est testable sans hardware via `mock_serial`. Aucune modification de `main.py` ici — Phase D s'en occupe.

### Task 10: Créer `game_session.py` avec le squelette de classe

**Files:**
- Create: `quoridor_engine/game_session.py`
- Modify: `quoridor_engine/__init__.py` (exporter `GameSession`, `NackCode`)
- Create: `tests/test_game_session.py`

- [ ] **Step 1: Écrire le test rouge minimal**

Créer [`tests/test_game_session.py`](../../../tests/test_game_session.py) :

```python
"""Tests pour GameSession (spec P9 §4-§6)."""

import pytest
from quoridor_engine.uart_client import Frame, UartClient


class TestGameSessionConstruction:
    def test_can_construct_with_required_args(self, mock_serial):
        from quoridor_engine import QuoridorGame, AI, GameSession

        game = QuoridorGame()
        ai = AI(player="j2", difficulty="normal")
        uart = UartClient(mock_serial)
        session = GameSession(game, ai, uart, debug=False)

        assert session.game is game
        assert session.ai is ai
        assert session.uart is uart
        assert session.debug is False
        assert session._unexpected_frame_count == 0
```

- [ ] **Step 2: Vérifier qu'il échoue**

```bash
pytest tests/test_game_session.py -v
```

Expected : FAIL — `ImportError: cannot import name 'GameSession'`.

- [ ] **Step 3: Créer le module**

Créer [`quoridor_engine/game_session.py`](../../../quoridor_engine/game_session.py) :

```python
"""Session de jeu plateau (orchestration RPi <-> ESP32 via UART).

Spec : docs/superpowers/specs/2026-05-03-p9-integration-rpi-esp32-design.md
"""

from typing import Optional

from .ai import AI
from .core import QuoridorGame, InvalidMoveError, NackCode
from .uart_client import (
    UartClient,
    Frame,
    UartError,
    UartTimeoutError,
    UartHardwareError,
)


class GameSession:
    """Orchestre une partie en mode plateau physique.

    Architecture (cf. spec §2.7) : injecte game, ai, uart explicitement pour
    permettre les tests sans hardware. La boucle de jeu (`run`) gère le cycle
    de vie complet : handshake -> game loop -> gameover -> close.
    """

    HANDSHAKE_TIMEOUT_S = 15.0  # spec §6.5 : uniforme pour handshake et reconnect

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
        self._unexpected_frame_count = 0

    def run(self) -> None:
        """Lance la partie. Bloquant. Lève les exceptions UART non-récupérables."""
        try:
            self.uart.connect(timeout=self.HANDSHAKE_TIMEOUT_S)
            self._game_loop()
            self._send_gameover()
        finally:
            self.uart.close()

    def _game_loop(self) -> None:
        """Boucle principale (à compléter dans Tasks 11-15)."""
        raise NotImplementedError("implémenté dans Tasks 11-15")
```

- [ ] **Step 4: Exposer dans `__init__.py`**

Modifier [`quoridor_engine/__init__.py`](../../../quoridor_engine/__init__.py) :

```python
from .core import QuoridorGame, GameState, InvalidMoveError, NackCode
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
from .game_session import GameSession
```

- [ ] **Step 5: Vérifier que le test passe**

```bash
pytest tests/test_game_session.py::TestGameSessionConstruction -v
```

Expected : 1 PASS.

- [ ] **Step 6: Commit**

```bash
git add quoridor_engine/game_session.py quoridor_engine/__init__.py tests/test_game_session.py
git commit -m "feat(game_session): squelette GameSession + exports module"
```

---

### Task 11: Helpers `_parse_intent_to_move` et `_move_to_cmd_args`

**Files:**
- Modify: `quoridor_engine/game_session.py`
- Modify: `tests/test_game_session.py`

- [ ] **Step 1: Écrire les tests rouges**

Ajouter à [`tests/test_game_session.py`](../../../tests/test_game_session.py) :

```python
class TestParseIntentToMove:
    def _make_session(self, mock_serial):
        from quoridor_engine import QuoridorGame, AI, GameSession, UartClient
        return GameSession(QuoridorGame(), AI(player="j2"), UartClient(mock_serial))

    def test_move_req_valid(self, mock_serial):
        session = self._make_session(mock_serial)
        frame = Frame(type="MOVE_REQ", args="3 4", seq=42)
        coup = session._parse_intent_to_move(frame)
        assert coup == ("deplacement", (3, 4))

    def test_wall_req_horizontal(self, mock_serial):
        session = self._make_session(mock_serial)
        frame = Frame(type="WALL_REQ", args="h 2 3", seq=43)
        coup = session._parse_intent_to_move(frame)
        assert coup == ("mur", ("h", 2, 3, 2))

    def test_wall_req_vertical(self, mock_serial):
        session = self._make_session(mock_serial)
        frame = Frame(type="WALL_REQ", args="v 1 2", seq=44)
        coup = session._parse_intent_to_move(frame)
        assert coup == ("mur", ("v", 1, 2, 2))

    def test_move_req_malformed_returns_none(self, mock_serial):
        session = self._make_session(mock_serial)
        frame = Frame(type="MOVE_REQ", args="abc", seq=45)
        coup = session._parse_intent_to_move(frame)
        assert coup is None

    def test_wall_req_invalid_orientation_returns_none(self, mock_serial):
        session = self._make_session(mock_serial)
        frame = Frame(type="WALL_REQ", args="x 2 3", seq=46)
        coup = session._parse_intent_to_move(frame)
        assert coup is None


class TestMoveToCmdArgs:
    def _make_session(self, mock_serial):
        from quoridor_engine import QuoridorGame, AI, GameSession, UartClient
        return GameSession(QuoridorGame(), AI(player="j2"), UartClient(mock_serial))

    def test_pawn_move(self, mock_serial):
        session = self._make_session(mock_serial)
        coup = ("deplacement", (2, 5))
        assert session._move_to_cmd_args(coup) == "MOVE 2 5"

    def test_wall_horizontal(self, mock_serial):
        session = self._make_session(mock_serial)
        coup = ("mur", ("h", 1, 2, 2))
        assert session._move_to_cmd_args(coup) == "WALL h 1 2"

    def test_wall_vertical(self, mock_serial):
        session = self._make_session(mock_serial)
        coup = ("mur", ("v", 3, 4, 2))
        assert session._move_to_cmd_args(coup) == "WALL v 3 4"
```

- [ ] **Step 2: Vérifier qu'ils échouent**

```bash
pytest tests/test_game_session.py::TestParseIntentToMove tests/test_game_session.py::TestMoveToCmdArgs -v
```

Expected : FAIL — `AttributeError: '_parse_intent_to_move'`.

- [ ] **Step 3: Implémenter les helpers**

Dans [`quoridor_engine/game_session.py`](../../../quoridor_engine/game_session.py), classe `GameSession` :

```python
def _parse_intent_to_move(self, frame: Frame) -> Optional[tuple]:
    """Convertit une trame MOVE_REQ ou WALL_REQ en coup moteur.

    Retourne None si format invalide (NACK INVALID_FORMAT côté appelant).
    """
    parts = frame.args.split()
    try:
        if frame.type == "MOVE_REQ":
            if len(parts) != 2:
                return None
            row, col = int(parts[0]), int(parts[1])
            return ("deplacement", (row, col))
        if frame.type == "WALL_REQ":
            if len(parts) != 3:
                return None
            orient, row, col = parts[0], int(parts[1]), int(parts[2])
            if orient not in ("h", "v"):
                return None
            return ("mur", (orient, row, col, 2))
    except ValueError:
        return None
    return None

def _move_to_cmd_args(self, coup: tuple) -> str:
    """Sérialise un coup moteur en args CMD pour le firmware ESP32."""
    kind, payload = coup
    if kind == "deplacement":
        row, col = payload
        return f"MOVE {row} {col}"
    if kind == "mur":
        orient, row, col, _ = payload
        return f"WALL {orient} {row} {col}"
    raise ValueError(f"coup non reconnu: {coup!r}")
```

- [ ] **Step 4: Vérifier que les tests passent**

```bash
pytest tests/test_game_session.py::TestParseIntentToMove tests/test_game_session.py::TestMoveToCmdArgs -v
```

Expected : 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add quoridor_engine/game_session.py tests/test_game_session.py
git commit -m "feat(game_session): helpers _parse_intent_to_move et _move_to_cmd_args"
```

---

### Task 12: Flux entrant — `_process_player_intent`

**Files:**
- Modify: `quoridor_engine/game_session.py`
- Modify: `tests/test_game_session.py`

- [ ] **Step 1: Écrire les tests rouges**

Ajouter à `tests/test_game_session.py` :

```python
class TestProcessPlayerIntent:
    """Spec §4.4 : MOVE_REQ/WALL_REQ valide -> ACK ; invalide -> NACK <code>."""

    def _make_connected_session(self, mock_serial):
        from quoridor_engine import QuoridorGame, AI, GameSession, UartClient
        client = UartClient(mock_serial)
        client.is_connected = True   # short-circuit handshake pour ce test
        session = GameSession(QuoridorGame(), AI(player="j2"), client)
        return session, client

    def test_valid_move_req_sends_ack(self, mock_serial):
        session, client = self._make_connected_session(mock_serial)
        client._start_reader_thread()
        try:
            # j1 commence en (5, 3) ; coup vers (4, 3) = avancer
            frame = Frame(type="MOVE_REQ", args="4 3", seq=42)
            session._process_player_intent(frame)
            tx = mock_serial.get_tx()
            assert b"<ACK|" in tx
            assert b"ack=42" in tx
            # tour bascule à j2
            assert session.game.get_current_player() == "j2"
        finally:
            client.close()

    def test_invalid_move_req_sends_nack_with_code(self, mock_serial):
        session, client = self._make_connected_session(mock_serial)
        client._start_reader_thread()
        try:
            # case non-adjacente
            frame = Frame(type="MOVE_REQ", args="0 0", seq=43)
            session._process_player_intent(frame)
            tx = mock_serial.get_tx()
            assert b"<NACK ILLEGAL|" in tx
            assert b"ack=43" in tx
        finally:
            client.close()

    def test_malformed_move_req_sends_nack_invalid_format(self, mock_serial):
        session, client = self._make_connected_session(mock_serial)
        client._start_reader_thread()
        try:
            frame = Frame(type="MOVE_REQ", args="xyz", seq=44)
            session._process_player_intent(frame)
            tx = mock_serial.get_tx()
            assert b"<NACK INVALID_FORMAT|" in tx
            assert b"ack=44" in tx
        finally:
            client.close()
```

- [ ] **Step 2: Vérifier qu'ils échouent**

```bash
pytest tests/test_game_session.py::TestProcessPlayerIntent -v
```

Expected : FAIL — méthode absente.

- [ ] **Step 3: Implémenter**

Dans `GameSession` (`quoridor_engine/game_session.py`) :

```python
def _process_player_intent(self, frame: Frame) -> None:
    """Coeur du flux entrant : valide via QuoridorGame, répond ACK ou NACK <code>."""
    coup = self._parse_intent_to_move(frame)
    if coup is None:
        self.uart.send_nack(frame.seq, NackCode.INVALID_FORMAT.value)
        if self.debug:
            print(f"[debug] NACK INVALID_FORMAT seq={frame.seq} args={frame.args!r}")
        return
    try:
        self.game.play_move(coup)
    except InvalidMoveError as e:
        self.uart.send_nack(frame.seq, e.code.value)
        if self.debug:
            print(f"[debug] NACK {e.code.value} seq={frame.seq}: {e}")
        return
    self.uart.send_ack(frame.seq)
    if self.debug:
        print(f"[debug] ACK seq={frame.seq} coup={coup}")
```

- [ ] **Step 4: Vérifier que les tests passent**

```bash
pytest tests/test_game_session.py::TestProcessPlayerIntent -v
```

Expected : 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add quoridor_engine/game_session.py tests/test_game_session.py
git commit -m "feat(game_session): _process_player_intent (ACK/NACK avec code typé)"
```

---

### Task 13: Flux sortant — `_send_ai_move`

**Files:**
- Modify: `quoridor_engine/game_session.py`
- Modify: `tests/test_game_session.py`

- [ ] **Step 1: Écrire les tests rouges**

Ajouter à `tests/test_game_session.py` :

```python
class TestSendAiMove:
    """Spec §5.2 : tour IA -> CMD MOVE/WALL -> attente DONE -> commit."""

    def _make_connected_session_with_ai(self, mock_serial, fake_move):
        """Helper qui retourne (session, client). L'IA est un fake qui retourne `fake_move`."""
        from quoridor_engine import QuoridorGame, GameSession, UartClient

        class FakeAI:
            def __init__(self, move):
                self._move = move
                self.player = "j2"
            def find_best_move(self, state, verbose=False):
                return self._move

        client = UartClient(mock_serial)
        client.is_connected = True
        session = GameSession(QuoridorGame(), FakeAI(fake_move), client)
        return session, client

    def test_ai_pawn_move_sends_cmd_then_commits(self, mock_serial):
        # Faire jouer j1 d'abord pour passer le tour à j2
        session, client = self._make_connected_session_with_ai(
            mock_serial, ("deplacement", (1, 3))
        )
        client._start_reader_thread()
        try:
            session.game.play_move(("deplacement", (4, 3)))   # j1 avance

            # Pré-injecter le DONE qui sera reçu après envoi
            done = Frame(type="DONE", args="", seq=0, ack=0)
            mock_serial.inject_rx(done.encode())

            session._send_ai_move()
            tx = mock_serial.get_tx()
            assert b"<CMD MOVE 1 3|" in tx
            # j2 a joué -> tour bascule à j1
            assert session.game.get_current_player() == "j1"
        finally:
            client.close()

    def test_ai_wall_move_sends_cmd_wall(self, mock_serial):
        session, client = self._make_connected_session_with_ai(
            mock_serial, ("mur", ("h", 1, 1, 2))
        )
        client._start_reader_thread()
        try:
            session.game.play_move(("deplacement", (4, 3)))   # j1 avance

            done = Frame(type="DONE", args="", seq=0, ack=0)
            mock_serial.inject_rx(done.encode())

            session._send_ai_move()
            tx = mock_serial.get_tx()
            assert b"<CMD WALL h 1 1|" in tx
        finally:
            client.close()
```

- [ ] **Step 2: Vérifier qu'ils échouent**

```bash
pytest tests/test_game_session.py::TestSendAiMove -v
```

Expected : FAIL.

- [ ] **Step 3: Implémenter**

Dans `GameSession` :

```python
def _send_ai_move(self) -> None:
    """Coeur du flux sortant : IA -> CMD -> DONE -> commit (spec §5.2)."""
    state = self.game.get_current_state()
    coup = self.ai.find_best_move(state, verbose=False)
    cmd_args = self._move_to_cmd_args(coup)
    if self.debug:
        print(f"[debug] IA → CMD {cmd_args}")
    self.uart.send_cmd("CMD", cmd_args)   # bloquant, retry idempotent
    # CMD acknowledged : commit côté Python
    self.game.play_move(coup)
```

- [ ] **Step 4: Vérifier que les tests passent**

```bash
pytest tests/test_game_session.py::TestSendAiMove -v
```

Expected : 2 PASS. Note : si le `seq` envoyé par `send_cmd` n'est pas 0 (parce que le `_tx_seq` a été incrémenté ailleurs), ajuster le `ack` de la frame pré-injectée. **Solution alternative robuste** : faire `client._tx_seq = 0` avant l'appel, ou récupérer le seq utilisé via `client._last_request_seq` puis injecter le DONE avec le bon ack.

> Si le test reste rouge à cause d'un mismatch de seq, modifier le test ainsi : injecter le DONE de manière dynamique en utilisant un thread (avec `threading.Timer(0.05, lambda: mock_serial.inject_rx(...))`) qui lit `client._last_request_seq` après le `send_cmd` ait commencé.

- [ ] **Step 5: Commit**

```bash
git add quoridor_engine/game_session.py tests/test_game_session.py
git commit -m "feat(game_session): _send_ai_move (CMD + commit après DONE)"
```

---

### Task 14: Fin de partie — `_send_gameover`

**Files:**
- Modify: `quoridor_engine/game_session.py`
- Modify: `tests/test_game_session.py`

- [ ] **Step 1: Écrire les tests rouges**

Ajouter à `tests/test_game_session.py` :

```python
class TestSendGameover:
    def test_send_gameover_with_winner(self, mock_serial):
        from quoridor_engine import QuoridorGame, AI, GameSession, UartClient

        class StubGame:
            """Stub minimal qui se prétend terminé avec j1 gagnant."""
            def get_winner(self):
                return "j1"

        client = UartClient(mock_serial)
        client.is_connected = True
        session = GameSession(StubGame(), AI(player="j2"), client)
        client._start_reader_thread()
        try:
            done = Frame(type="DONE", args="", seq=0, ack=0)
            mock_serial.inject_rx(done.encode())
            session._send_gameover()
            tx = mock_serial.get_tx()
            assert b"<CMD GAMEOVER j1|" in tx
        finally:
            client.close()

    def test_send_gameover_no_winner_is_no_op(self, mock_serial):
        from quoridor_engine import AI, GameSession, UartClient

        class StubGame:
            def get_winner(self):
                return None

        client = UartClient(mock_serial)
        client.is_connected = True
        session = GameSession(StubGame(), AI(player="j2"), client)
        client._start_reader_thread()
        try:
            session._send_gameover()
            tx = mock_serial.get_tx()
            assert b"GAMEOVER" not in tx
        finally:
            client.close()
```

- [ ] **Step 2: Vérifier qu'ils échouent**

```bash
pytest tests/test_game_session.py::TestSendGameover -v
```

Expected : FAIL.

- [ ] **Step 3: Implémenter**

Dans `GameSession` :

```python
def _send_gameover(self) -> None:
    """Envoie CMD GAMEOVER <winner> en fin de partie (spec §5.4).

    Si la CMD échoue (timeout ou ERR), on log et on n'empêche pas la sortie
    du run() : la partie côté Python est terminée.
    """
    winner = self.game.get_winner()
    if winner is None:
        return
    if self.debug:
        print(f"[debug] FIN DE PARTIE → CMD GAMEOVER {winner}")
    try:
        self.uart.send_cmd("CMD", f"GAMEOVER {winner}")
    except (UartTimeoutError, UartHardwareError) as exc:
        if self.debug:
            print(f"[debug] CMD GAMEOVER échec : {exc}")
```

- [ ] **Step 4: Vérifier que les tests passent**

```bash
pytest tests/test_game_session.py::TestSendGameover -v
```

Expected : 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add quoridor_engine/game_session.py tests/test_game_session.py
git commit -m "feat(game_session): _send_gameover en fin de partie"
```

---

### Task 15: Gestion ERR — `_handle_err` + reconnect

**Files:**
- Modify: `quoridor_engine/game_session.py`
- Modify: `tests/test_game_session.py`

- [ ] **Step 1: Écrire les tests rouges**

Ajouter à `tests/test_game_session.py` :

```python
class TestHandleErr:
    """Spec §6.4 : ERR récupérable -> reconnect ; non-récupérable -> remonte."""

    def test_recoverable_err_triggers_reconnect(self, mock_serial):
        from quoridor_engine import QuoridorGame, AI, GameSession, UartClient

        client = UartClient(mock_serial)
        client.is_connected = True
        session = GameSession(QuoridorGame(), AI(player="j2"), client)
        client._start_reader_thread()
        try:
            # Pré-injecter le HELLO qui suivra le CMD_RESET pour permettre le reconnect
            hello = Frame(type="HELLO", args="", seq=0, version=UartClient.PROTOCOL_VERSION)
            mock_serial.inject_rx(hello.encode())

            err = Frame(type="ERR", args="UART_LOST", seq=99)
            session._handle_err(err)

            tx = mock_serial.get_tx()
            assert b"CMD_RESET" in tx
            assert b"HELLO_ACK" in tx   # reconnexion réussie
            assert client.is_connected is True
        finally:
            client.close()

    def test_non_recoverable_err_raises(self, mock_serial):
        import pytest
        from quoridor_engine import QuoridorGame, AI, GameSession, UartClient
        from quoridor_engine.uart_client import UartHardwareError

        client = UartClient(mock_serial)
        client.is_connected = True
        session = GameSession(QuoridorGame(), AI(player="j2"), client)
        client._start_reader_thread()
        try:
            err = Frame(type="ERR", args="HOMING_FAILED", seq=100)
            with pytest.raises(UartHardwareError):
                session._handle_err(err)
        finally:
            client.close()
```

- [ ] **Step 2: Vérifier qu'ils échouent**

```bash
pytest tests/test_game_session.py::TestHandleErr -v
```

Expected : FAIL.

- [ ] **Step 3: Implémenter**

Dans `GameSession` :

```python
def _handle_err(self, frame: Frame) -> None:
    """Spec §6.4 : ERR récupérable → reconnect ; non-récupérable → remonte."""
    result = self.uart.handle_err_received(frame)   # peut lever UartHardwareError
    if result == "RESET_SENT":
        if self.debug:
            print(f"[debug] ESP32 ERR récupérable {frame.args} → CMD_RESET, reconnexion…")
        self.uart.connect(timeout=self.HANDSHAKE_TIMEOUT_S)
        if self.debug:
            print("[debug] reconnexion réussie, reprise au tour courant")
```

- [ ] **Step 4: Vérifier que les tests passent**

```bash
pytest tests/test_game_session.py::TestHandleErr -v
```

Expected : 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add quoridor_engine/game_session.py tests/test_game_session.py
git commit -m "feat(game_session): _handle_err avec reconnect 15s sur ERR récupérable"
```

---

### Task 16: Boucle principale `_game_loop` + `_await_player_intent` + `_check_health`

**Files:**
- Modify: `quoridor_engine/game_session.py`
- Modify: `tests/test_game_session.py`

- [ ] **Step 1: Écrire les tests rouges**

Ajouter à `tests/test_game_session.py` :

```python
class TestGameLoop:
    """Spec §4.2 : alternance j1 (humain via plateau) / j2 (IA via CMD)."""

    def test_loop_exits_when_game_is_over(self, mock_serial):
        from quoridor_engine import AI, GameSession, UartClient

        class StubGame:
            def __init__(self):
                self._over = True
            def is_game_over(self):
                return (self._over, "j1")
            def get_current_player(self):
                return "j1"

        client = UartClient(mock_serial)
        client.is_connected = True
        session = GameSession(StubGame(), AI(player="j2"), client)
        client._start_reader_thread()
        try:
            session._game_loop()  # ne doit pas boucler infiniment
        finally:
            client.close()

    def test_check_health_raises_if_reader_dead(self, mock_serial):
        import pytest
        from quoridor_engine import QuoridorGame, AI, GameSession, UartClient
        from quoridor_engine.uart_client import UartError

        client = UartClient(mock_serial)
        client.is_connected = True
        session = GameSession(QuoridorGame(), AI(player="j2"), client)
        # NB : _start_reader_thread non appelé → reader est mort dès le départ
        with pytest.raises(UartError):
            session._check_health()
```

- [ ] **Step 2: Vérifier qu'ils échouent**

```bash
pytest tests/test_game_session.py::TestGameLoop -v
```

Expected : FAIL — `_game_loop` lève actuellement `NotImplementedError`.

- [ ] **Step 3: Implémenter**

Dans `GameSession`, remplacer le `_game_loop` placeholder et ajouter les helpers :

```python
def _game_loop(self) -> None:
    """Alterne tour j1 (humain via plateau) / tour j2 (IA via CMD)."""
    while True:
        is_over, _winner = self.game.is_game_over()
        if is_over:
            return
        if self.game.get_current_player() == "j1":
            self._await_player_intent()
        else:
            self._send_ai_move()

def _await_player_intent(self) -> None:
    """Attend une trame MOVE_REQ ou WALL_REQ. Gère ERR au passage."""
    while True:
        frame = self.uart.receive(timeout=0.5)
        if frame is None:
            self._check_health()
            continue
        if frame.type in ("MOVE_REQ", "WALL_REQ"):
            self._process_player_intent(frame)
            return
        if frame.type == "ERR":
            self._handle_err(frame)
            return
        # frame inattendue (KEEPALIVE pollué, etc.) -> ignorer
        self._unexpected_frame_count += 1
        if self.debug:
            print(f"[debug] frame inattendue ignorée: {frame}")

def _check_health(self) -> None:
    """Lève UartError immédiat si le thread de lecture est mort."""
    if not self.uart._is_reader_alive():
        raise UartError("reader thread died — partie interrompue")
```

- [ ] **Step 4: Vérifier que les tests passent**

```bash
pytest tests/test_game_session.py::TestGameLoop -v
```

Expected : 2 PASS.

- [ ] **Step 5: Vérifier toute la suite test_game_session**

```bash
pytest tests/test_game_session.py -v
```

Expected : tous PASS.

- [ ] **Step 6: Commit**

```bash
git add quoridor_engine/game_session.py tests/test_game_session.py
git commit -m "feat(game_session): _game_loop + _await_player_intent + _check_health"
```

---

## Phase D — Refactor `main.py` argparse

### Task 17: Ajouter argparse + mode plateau dispatch

**Files:**
- Modify: `main.py` (top-level)
- Create: `tests/test_main_cli.py`

- [ ] **Step 1: Écrire les tests rouges**

Créer [`tests/test_main_cli.py`](../../../tests/test_main_cli.py) :

```python
"""Tests pour le parsing CLI de main.py (spec P9 §3.4)."""

import pytest
import sys
import subprocess


def test_help_lists_all_flags():
    """python main.py --help affiche les 4 flags."""
    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    out = result.stdout
    assert "--mode" in out
    assert "--port" in out
    assert "--difficulty" in out
    assert "--debug" in out


def test_plateau_mode_without_port_exits_2():
    """--mode plateau sans --port → exit 2 avec message clair."""
    result = subprocess.run(
        [sys.executable, "main.py", "--mode", "plateau"],
        capture_output=True, text=True
    )
    assert result.returncode == 2
    assert "--port" in result.stderr.lower() or "--port" in result.stdout.lower()


def test_parse_args_console_default():
    """Sans argument, args.mode == 'console'."""
    sys.argv = ["main.py"]
    from main import parse_args
    args = parse_args()
    assert args.mode == "console"
    assert args.port is None
    assert args.debug is False


def test_parse_args_plateau_with_port():
    sys.argv = ["main.py", "--mode", "plateau", "--port", "/dev/null", "--debug"]
    from main import parse_args
    args = parse_args()
    assert args.mode == "plateau"
    assert args.port == "/dev/null"
    assert args.debug is True
```

- [ ] **Step 2: Vérifier qu'ils échouent**

```bash
pytest tests/test_main_cli.py -v
```

Expected : FAIL — `parse_args` n'existe pas dans `main.py`.

- [ ] **Step 3: Refactor `main.py`**

Lire d'abord [`main.py`](../../../main.py) en entier pour identifier la fonction qui contient la boucle console actuelle (probablement `main()` ou similaire). La renommer en `run_console(args)` (en lui passant l'objet `args` même si elle n'utilise pas tout).

Au sommet du fichier, ajouter (au-dessus de tout le code existant) :

```python
import argparse
import sys


def parse_args():
    p = argparse.ArgumentParser(description="Quoridor — moteur Python.")
    p.add_argument("--mode", choices=["console", "plateau"], default="console",
                   help="console = prompt clavier ; plateau = dialogue UART avec ESP32")
    p.add_argument("--port", help="Port série pour le mode plateau (ex /dev/ttyUSB0)")
    p.add_argument("--difficulty", choices=["facile", "normal", "difficile"],
                   help="Niveau de l'IA (default: normal en plateau, prompt en console)")
    p.add_argument("--debug", action="store_true",
                   help="Mode verbeux (logs trames + état). Hors démo.")
    args = p.parse_args()
    if args.mode == "plateau" and not args.port:
        p.error("--port requis en mode plateau")
    return args


def run_plateau(args):
    """Mode plateau physique : dispatch UART vers ESP32 (spec P9)."""
    import serial   # pyserial
    from quoridor_engine import QuoridorGame, AI, UartClient, GameSession

    ser = serial.Serial(args.port, baudrate=115200, timeout=0.05)
    uart = UartClient(ser)
    game = QuoridorGame()
    ai = AI(player="j2", difficulty=args.difficulty or "normal")
    session = GameSession(game, ai, uart, debug=args.debug)
    try:
        session.run()
    except Exception as exc:
        print(f"[ERREUR] {exc}", file=sys.stderr)
        sys.exit(1)


def main():
    args = parse_args()
    if args.mode == "console":
        run_console(args)
    else:
        run_plateau(args)


if __name__ == "__main__":
    main()
```

> **Note de refactor :** la fonction `main()` actuelle de `main.py` contient probablement la boucle console. La renommer en `run_console(args)` et la rendre indépendante de l'argument (elle peut ignorer `args` si elle n'utilise rien). S'assurer que le nouveau `main()` au-dessus du fichier prend le contrôle du `if __name__ == "__main__":` final — supprimer toute autre instance de `if __name__ == "__main__"` plus bas dans le fichier.

- [ ] **Step 4: Vérifier que les tests CLI passent**

```bash
pytest tests/test_main_cli.py -v
```

Expected : 4 PASS.

- [ ] **Step 5: Vérifier que le mode console fonctionne toujours**

```bash
echo "q" | python main.py 2>&1 | head -5
```

Expected : la boucle console démarre comme avant et se termine sur `q` (ou autre input de quit reconnu). Pas de crash.

- [ ] **Step 6: Vérifier toute la suite Python**

```bash
pytest 2>&1 | tail -5
```

Expected : aucun test ne casse.

- [ ] **Step 7: Commit**

```bash
git add main.py tests/test_main_cli.py
git commit -m "feat(main): argparse --mode plateau + dispatch GameSession"
```

---

## Phase E — Stubs firmware ESP32

### Task 18: Ajouter `CMD WALL` et `CMD GAMEOVER` dans `tickConnected`

**Files:**
- Modify: `firmware/src/GameController.cpp` (entre L170 et L171)

- [ ] **Step 1: Lire le fichier autour de L170**

```bash
sed -n '160,180p' firmware/src/GameController.cpp
```

Repérer le bloc :

```cpp
} else if (strcmp(f.type, "CMD") == 0 && strncmp(f.args, "MOVE ", 5) == 0) {
  ...
  enterExecutingWithCommand(cmd);     // L170
} else if (strcmp(f.type, "CMD") == 0) {     // L171 (catch-all non-impl)
  UartLink::logf("FSM", "CMD non-impl: %s", f.args);
} else if (strcmp(f.type, "CMD_RESET") == 0) {
  ...
```

- [ ] **Step 2: Insérer les 2 stubs entre L170 et L171**

Utiliser l'outil Edit :

Localiser l'ancrage :

```cpp
        enterExecutingWithCommand(cmd);
      } else if (strcmp(f.type, "CMD") == 0) {
        UartLink::logf("FSM", "CMD non-impl: %s", f.args);
```

Le remplacer par :

```cpp
        enterExecutingWithCommand(cmd);
      } else if (strcmp(f.type, "CMD") == 0 && strncmp(f.args, "WALL ", 5) == 0) {
        UartLink::logf("FSM", "CMD WALL stub: %s", f.args + 5);
        UartLink::respondCmdDone(f.seq);
      } else if (strcmp(f.type, "CMD") == 0 && strncmp(f.args, "GAMEOVER ", 9) == 0) {
        UartLink::logf("FSM", "CMD GAMEOVER stub: %s", f.args + 9);
        UartLink::respondCmdDone(f.seq);
      } else if (strcmp(f.type, "CMD") == 0) {
        UartLink::logf("FSM", "CMD non-impl: %s", f.args);
```

- [ ] **Step 3: Compiler le firmware**

```bash
cd firmware
~/.platformio/penv/bin/pio run 2>&1 | tail -30
```

Expected : `SUCCESS` à la fin, exit code 0, **aucun nouveau warning** par rapport à un `pio run` avant la modification.

- [ ] **Step 4: Vérifier la taille de l'exécutable**

```bash
~/.platformio/penv/bin/pio run 2>&1 | grep -E "RAM|Flash"
```

Noter mentalement : la taille flash a augmenté de quelques dizaines d'octets max (~50 octets pour 2 strings + 2 appels de fonction). Si l'augmentation est > 1 KB, c'est anormal (probable inclusion accidentelle d'un header lourd).

- [ ] **Step 5: Commit**

```bash
cd ..
git add firmware/src/GameController.cpp
git commit -m "feat(firmware): stubs CMD WALL et CMD GAMEOVER dans tickConnected"
```

---

## Phase F — Documentation

### Task 19: Mettre à jour `docs/02_architecture.md`

**Files:**
- Modify: `docs/02_architecture.md`

- [ ] **Step 1: Lire la structure actuelle**

```bash
sed -n '1,30p' docs/02_architecture.md
```

Identifier la section qui parle de `main.py` ou de l'orchestration globale (probablement §1 ou §3 « Couches logicielles »).

- [ ] **Step 2: Ajouter une sous-section P9**

Ajouter dans la section appropriée (à la suite du paragraphe sur le moteur de jeu côté Python) le bloc suivant :

```markdown
### Couche d'orchestration plateau (P9)

Depuis P9, [`main.py`](../main.py) accepte un argument `--mode plateau` qui
remplace le prompt console par un dialogue UART avec l'ESP32. La logique
d'orchestration vit dans [`quoridor_engine/game_session.py`](../quoridor_engine/game_session.py)
(classe `GameSession`).

Cycle de vie d'une partie en mode plateau :

1. `main.py --mode plateau --port /dev/ttyUSB0` ouvre `serial.Serial(...)`.
2. `GameSession.run()` appelle `uart.connect(timeout=15.0)` (handshake HELLO/HELLO_ACK).
3. La boucle de jeu alterne :
   - tour `j1` (humain) : `_await_player_intent` lit `MOVE_REQ`/`WALL_REQ` du firmware,
     valide via `QuoridorGame.play_move`, répond `ACK` ou `NACK <code>` (cf. `NackCode`).
   - tour `j2` (IA) : `_send_ai_move` calcule le coup, envoie `CMD MOVE`/`CMD WALL`,
     bloque jusqu'au `DONE`.
4. Fin de partie : `CMD GAMEOVER <winner>` envoyée puis `uart.close()`.

**Robustesse aux déconnexions** (spec §6) : le client UART détecte les pertes
de session (3 KEEPALIVE manqués → `ERR UART_LOST` reçu), envoie un `CMD_RESET`,
ré-établit le handshake. Limitation P9 acceptée : la position physique des pions
et l'état des LEDs sont perdus à chaque reboot ESP32 (re-synchronisation prévue
en P11 via `CMD SET_BOARD_STATE`).

Le mode console (`--mode console`, défaut) reste inchangé : prompt clavier,
plateau ASCII, logique console pure.
```

- [ ] **Step 3: Vérifier la cohérence avec le diagramme existant (si présent)**

Si [`docs/02_architecture.md`](../../../docs/02_architecture.md) contient un diagramme ASCII des couches, vérifier qu'il reste cohérent (ajouter `GameSession` entre `main.py` et `UartClient` si besoin).

- [ ] **Step 4: Commit**

```bash
git add docs/02_architecture.md
git commit -m "docs(architecture): décrire la couche P9 (GameSession + dispatch CLI)"
```

---

### Task 20: Mettre à jour `docs/06_protocole_uart.md`

**Files:**
- Modify: `docs/06_protocole_uart.md`

- [ ] **Step 1: Lire la fin du fichier**

```bash
tail -50 docs/06_protocole_uart.md
```

Identifier la dernière section (probablement « Statut » ou « Évolution »).

- [ ] **Step 2: Ajouter une note P9**

Ajouter à la fin du fichier (avant tout pied de page) :

```markdown
---

## Note P9 (2026-05-03) — sous-ensemble émis par la couche d'orchestration

La couche `GameSession` côté RPi (P9) émet uniquement les CMD qui modifient
l'état du jeu : `CMD MOVE`, `CMD WALL`, `CMD GAMEOVER`. Les CMD purement
visuelles (`CMD HIGHLIGHT`, `CMD SET_TURN`) sont **réservées à P11** quand
les drivers LEDs réels seront en place — le firmware les ignorera côté
catch-all `CMD non-impl` jusque-là.

Côté firmware, P9 ajoute des **stubs** pour `CMD WALL` et `CMD GAMEOVER` qui
acceptent la trame, loggent en debug, et répondent `DONE` immédiatement sans
action mécanique (cf. [`firmware/src/GameController.cpp:tickConnected`](../firmware/src/GameController.cpp)).
Ces stubs seront remplacés par la logique réelle (mouvement moteur pour
`WALL`, déclenchement servo pour `GAMEOVER`) en P11.

Aucune modification du format de trame, des codes d'erreur, ou du séquencement
n'est introduite par P9. Le protocole reste **strictement** défini par la
spec [`2026-05-01-protocole-uart-plan-2-design.md`](superpowers/specs/2026-05-01-protocole-uart-plan-2-design.md).
```

- [ ] **Step 3: Commit**

```bash
git add docs/06_protocole_uart.md
git commit -m "docs(uart): note P9 — sous-ensemble CMD émis par GameSession"
```

---

### Task 21: Mettre à jour `docs/00_plan_global.md`

**Files:**
- Modify: `docs/00_plan_global.md` (cocher P9.1–P9.4 et P9.6, marquer P9 🚧 → ✅)

- [ ] **Step 1: Lire la section P9 actuelle**

```bash
sed -n '85,100p' docs/00_plan_global.md
```

- [ ] **Step 2: Cocher les sous-tâches terminées**

Modifier les lignes correspondantes :

```markdown
- [x] **P9.1** Adapter [main.py](../main.py) pour offrir un mode « plateau physique » en plus du mode console
- [x] **P9.2** Implémenter le flux entrant : Python attend `MOVE_REQ` → valide via `QuoridorGame` → renvoie `ACK` ou `NACK`
- [x] **P9.3** Implémenter le flux sortant : Python envoie `CMD MOVE` pour les coups joués par l'IA
- [x] **P9.4** Côté ESP32 (DevKit), conserver les boutons en mode injection (commande `BTN x y` via Serial) et les LEDs/moteurs en stub (logs uniquement)
- [ ] **P9.5** Tests d'intégration end-to-end : partie complète PvIA via UART avec ESP32 DevKit *(reporté au 2026-05-04, retour DevKit)*
- [x] **P9.6** Mettre à jour [02_architecture.md](02_architecture.md) et [06_protocole_uart.md](06_protocole_uart.md)
```

> Le statut global de P9 reste 🚧 (en cours) tant que P9.5 n'est pas faite.

- [ ] **Step 3: Mettre à jour la "Note d'avancement" en tête de fichier**

Si la note d'avancement est encore au 2026-05-01 et parle de P8, la remplacer par une note 2026-05-03 mentionnant que P8 est terminée et P9 (sauf P9.5) implémentée.

```markdown
## ⏸️ Note d'avancement — 2026-05-03

P8 (Protocole UART Plan 2) terminée. P9 (Intégration logicielle RPi ↔ ESP32)
est implémentée à 5/6 sous-tâches : P9.1 à P9.4 et P9.6 sont complètes (voir
[`docs/superpowers/specs/2026-05-03-p9-integration-rpi-esp32-design.md`](superpowers/specs/2026-05-03-p9-integration-rpi-esp32-design.md)).
**P9.5** (tests E2E sur DevKit physique) est reportée au 2026-05-04 (retour
DevKit) — checklist dans [`firmware/INTEGRATION_TESTS_PENDING.md`](../firmware/INTEGRATION_TESTS_PENDING.md).
```

- [ ] **Step 4: Commit**

```bash
git add docs/00_plan_global.md
git commit -m "docs(plan): cocher P9.1–P9.4 + P9.6, P9.5 reportée au DevKit"
```

---

### Task 22: Mettre à jour `CHANGELOG.md`

**Files:**
- Modify: `CHANGELOG.md` (à la racine du repo)

- [ ] **Step 1: Lire l'entrée la plus récente**

```bash
head -30 CHANGELOG.md
```

- [ ] **Step 2: Ajouter une entrée P9**

Ajouter en haut du fichier (juste après l'éventuel titre `# Changelog` ou `# Historique`) :

```markdown
## P9 — Intégration logicielle RPi ↔ ESP32 (2026-05-03)

### Ajouté
- `quoridor_engine.NackCode` : Enum des codes d'erreur typés alignés sur le protocole UART (`ILLEGAL`, `OUT_OF_BOUNDS`, `WRONG_TURN`, `WALL_BLOCKED`, `NO_WALLS_LEFT`, `INVALID_FORMAT`).
- `quoridor_engine.GameSession` : classe d'orchestration de partie en mode plateau. Cycle complet handshake → game loop → gameover → close avec robustesse aux déconnexions (re-handshake automatique sur ERR récupérable, timeout 15 s).
- `main.py --mode plateau --port <chemin>` : nouveau mode CLI qui dispatche vers `GameSession.run()`.
- `main.py --debug` : mode verbeux (logs trames envoyées/reçues, état session).
- Thread keepalive 1 Hz dans `UartClient` (démarré dans `connect()`, stoppé dans `close()`).
- Compteur `UartClient.get_rejected_count()` (trames mal formées rejetées silencieusement).
- Détection thread mort dans `_send_frame` → `UartError` immédiat.
- Stubs firmware `CMD WALL` et `CMD GAMEOVER` dans `GameController::tickConnected` (réponse `DONE` sans action mécanique, action réelle reportée à P11).

### Modifié
- `InvalidMoveError(message, code)` : argument `code: NackCode` désormais **obligatoire**. 13 sites de levée migrés (12 dans `core.py`, 1 dans `ai.py`).
- `_reset_session()` clear `is_connected` (correctif bug où Python continuait d'envoyer après reboot ESP32 spontané).
- `handle_err_received()` clear `is_connected` après `CMD_RESET` envoyé (force le re-handshake côté orchestrateur).

### Tests
- 9 tests `test_game_session.py` (handshake, flux entrant, flux sortant, gameover, ERR recovery).
- 4 tests `test_uart_client.py` étendus (rejected count, thread death, _reset_session, keepalive).
- 4 tests `test_main_cli.py` (argparse).
- Tests `test_core.py` paramétrés pour vérifier `InvalidMoveError.code`.

### Reporté
- **P9.5** : tests d'intégration E2E sur DevKit ESP32 → 2026-05-04 (retour DevKit). Checklist dans [`firmware/INTEGRATION_TESTS_PENDING.md`](firmware/INTEGRATION_TESTS_PENDING.md).
```

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): entrée P9 (intégration RPi ↔ ESP32)"
```

---

### Task 23: Préparer la checklist `INTEGRATION_TESTS_PENDING.md` pour P9.5

**Files:**
- Modify ou Create: `firmware/INTEGRATION_TESTS_PENDING.md`

- [ ] **Step 1: Vérifier l'existant**

```bash
ls firmware/INTEGRATION_TESTS_PENDING.md 2>/dev/null && cat firmware/INTEGRATION_TESTS_PENDING.md || echo "fichier absent"
```

- [ ] **Step 2: Ajouter ou créer la section P9.5**

Si le fichier existe, **ajouter** à la fin une nouvelle section. S'il n'existe pas, créer un fichier neuf avec :

```markdown
# Tests d'intégration en attente de hardware

> Ce fichier liste les tests à exécuter au retour du DevKit ESP32. Une fois
> tous les scénarios validés, ce fichier sera supprimé et la phase concernée
> du [plan global](../docs/00_plan_global.md) sera cochée terminée.

---

## P9.5 — Tests E2E RPi ↔ ESP32 DevKit (date cible : 2026-05-04)

**Pré-requis matériel :** DevKit ESP32-WROOM connecté en USB, plateau
physique non requis (boutons en mode injection via `BTN x y` au Serial Monitor).

**Pré-requis logiciel :**
- Firmware Plan 2 + stubs P9 flashés : `cd firmware && pio run -t upload`.
- Python : `python main.py --mode plateau --port /dev/ttyUSB0 --debug`.

### Scénario 1 — Partie nominale PvIA via injection manuelle

1. Lancer Python en mode plateau avec `--debug`.
2. Vérifier au terminal Python : `[debug] handshake → HELLO_ACK envoyé (v=1)` puis `[debug] keepalive thread démarré (1 Hz)`.
3. Au Serial Monitor (autre terminal) : injecter `BTN 4 3` (déplacement j1).
4. Vérifier côté Python : `[debug] ACK seq=N coup=('deplacement', (4, 3))`.
5. Vérifier au Serial Monitor : `<MOVE_REQ 4 3|...>` puis `<ACK|...|ack=N|...>`.
6. Tour IA : Python doit imprimer `[debug] IA → CMD MOVE r c` puis `[debug] DONE reçu`. Au Serial Monitor : `FSM CMD MOVE stub: r c` (ou la motion réelle si P11 en place).
7. Continuer la partie (au moins 5 tours) jusqu'à fin de partie.
8. Vérifier : `[debug] FIN DE PARTIE → CMD GAMEOVER j1` (ou j2). Au Serial Monitor : `FSM CMD GAMEOVER stub: j1`.
9. Le port se ferme proprement, `python` exit 0.

### Scénario 2 — Coupure UART en milieu de partie

1. Lancer une partie en mode plateau.
2. Au milieu de la partie (après 2-3 coups), débrancher physiquement le câble USB pendant 5 secondes.
3. Re-brancher.
4. Vérifier côté Python : `[debug] ESP32 ERR récupérable UART_LOST → CMD_RESET, reconnexion…` puis `[debug] reconnexion réussie, reprise au tour courant`.
5. Continuer la partie : les nouveaux `BTN x y` injectés doivent fonctionner normalement.
6. **Limitation acceptée P9 (cf. spec §6.6) :** les LEDs et la position visuelle ne sont pas restaurées après reboot — c'est documenté.

### Scénario 3 — IA pose un mur

1. Lancer une partie en mode plateau avec `--difficulty difficile` pour augmenter la probabilité que l'IA pose un mur tôt.
2. Jouer normalement jusqu'à ce que l'IA décide de placer un mur.
3. Vérifier côté Python : `[debug] IA → CMD WALL h r c` (ou v).
4. Vérifier au Serial Monitor : `FSM CMD WALL stub: h r c` puis trame `<DONE|...>`.
5. Le tour bascule à j1.

### Scénario 4 — Idempotence d'une CMD perdue

1. Pour ce test, instrumenter temporairement le firmware pour **simuler la perte du premier `DONE`** (par exemple : ajouter un `if (_currentCmdAckSeq == 5) return;` avant le `respondCmdDone` dans `tickExecuting`, à supprimer après le test).
2. Re-flasher.
3. Lancer une partie. À la 5e CMD, observer le retry (Python renvoie 2 fois la même CMD avec le même seq, espacées de 15 s).
4. Vérifier au Serial Monitor : un seul log `FSM CMD MOVE stub` mais deux trames `<DONE|...|ack=5|...>` reçues côté Python (la 2e étant dédupliquée et ré-émise par `_lastCmdResult`).
5. Retirer l'instrumentation et reflasher avant de cocher la case.

---

✅ Tous les scénarios passés → supprimer cette section, cocher `P9.5` dans
[`docs/00_plan_global.md`](../docs/00_plan_global.md), basculer P9 de 🚧 à ✅.
```

- [ ] **Step 3: Commit**

```bash
git add firmware/INTEGRATION_TESTS_PENDING.md
git commit -m "docs(firmware): checklist P9.5 (tests E2E DevKit, à exécuter le 2026-05-04)"
```

---

## Validation finale du plan

### Task 24: Vérification globale

- [ ] **Step 1: Faire tourner toute la suite Python**

```bash
pytest --tb=short 2>&1 | tail -10
```

Expected : tous les tests passent (90 anciens + ~20 nouveaux ≈ 110 tests). Couverture stable ou améliorée.

- [ ] **Step 2: Compiler le firmware**

```bash
cd firmware && ~/.platformio/penv/bin/pio run 2>&1 | tail -10 && cd ..
```

Expected : `SUCCESS`, exit code 0, aucun nouveau warning.

- [ ] **Step 3: Smoke test mode console**

```bash
echo -e "1\nq\n" | python main.py 2>&1 | head -5
```

Expected : démarrage console nominal, sortie propre sur quit.

- [ ] **Step 4: Smoke test CLI parsing**

```bash
python main.py --help
python main.py --mode plateau 2>&1 | tail -3   # exit 2 attendu
```

Expected : help lisible ; mode plateau sans port → exit 2.

- [ ] **Step 5: Vérifier l'historique git**

```bash
git log --oneline | head -25
```

Expected : ~20 commits cohérents (un par task), tous avec un message conventional (`feat(...)`, `fix(...)`, `docs(...)`, `test(...)`).

- [ ] **Step 6: Si tout est vert, célébrer**

P9 est implémentée à 5/6. P9.5 attend le DevKit (2026-05-04).

---

## Récapitulatif des fichiers touchés

| Fichier | Tasks | Lignes nettes (approximatif) |
|---|---|---|
| `quoridor_engine/core.py` | 1, 2, 3 | +25 (NackCode + InvalidMoveError refactor) |
| `quoridor_engine/ai.py` | 3 | +1 (1 site refactoré) |
| `quoridor_engine/uart_client.py` | 5, 6, 7, 8, 9 | +50 |
| `quoridor_engine/__init__.py` | 10 | +2 (exports) |
| `quoridor_engine/game_session.py` | 10–16 | +250 (création) |
| `main.py` | 17 | +30 net (ajout argparse + run_plateau, le reste reste) |
| `tests/test_core.py` | 1, 2, 4 | +80 |
| `tests/test_uart_client.py` | 5, 6, 7, 8, 9 | +120 |
| `tests/test_game_session.py` | 10–16 | +400 (création) |
| `tests/test_main_cli.py` | 17 | +50 (création) |
| `firmware/src/GameController.cpp` | 18 | +6 |
| `docs/02_architecture.md` | 19 | +25 |
| `docs/06_protocole_uart.md` | 20 | +20 |
| `docs/00_plan_global.md` | 21 | ~6 lignes modifiées |
| `CHANGELOG.md` | 22 | +35 |
| `firmware/INTEGRATION_TESTS_PENDING.md` | 23 | +60 |

**Total côté Python :** ~1000 lignes nettes (50 % code, 50 % tests).
**Total côté firmware :** 6 lignes.
**Total documentation :** ~150 lignes.
