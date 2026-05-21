# Protocole de communication UART RPi ↔ ESP32

Ce document détaille le **protocole UART Plan 2** qui sert d'interface entre le Raspberry Pi (moteur de jeu Python) et l'ESP32 (firmware hardware). Format de trame texte avec CRC-16, séquencement, retry et codes d'erreur typés.

Sources : `quoridor_engine/uart_client.py` (côté RPi), spec dans `docs/06_protocole_uart.md`.

---

## Format de trame

Toutes les trames suivent le même schéma textuel, terminé par un saut de ligne :

```
<TYPE [args]|seq=N[|ack=M][|v=K]|crc=XXXX>\n
```

- **TYPE** : verbe de la trame (HELLO, ACK, NACK, CMD, DONE, MOVE_REQ, WALL_REQ, ERR, KEEPALIVE...)
- **args** : arguments dépendant du type (positions, codes d'erreur, etc.)
- **seq=N** : numéro de séquence de l'émetteur (mod 256)
- **ack=M** : numéro de séquence de la trame à laquelle on répond (optionnel)
- **v=K** : version du protocole (uniquement dans HELLO/HELLO_ACK)
- **crc=XXXX** : CRC-16 CCITT-FALSE (polynôme 0x1021, init 0xFFFF) sur tout le contenu **avant** `|crc=`

```mermaid
flowchart LR
    subgraph TRAME["Exemple : <CMD PAWN 3 4|seq=12|crc=A7F3>\\n"]
        T1["TYPE : CMD"]
        T2["args : PAWN 3 4"]
        T3["seq : 12"]
        T4["crc : A7F3"]
    end

    T1 --> CHK["Validé par<br/>parseur côté ESP32"]
    T2 --> CHK
    T3 --> CHK
    T4 --> CHK

    style TRAME fill:#FFF3E0
    style CHK fill:#4CAF50,color:#fff
```

---

## Handshake d'établissement de session

Au démarrage de l'ESP32, un handshake confirme que les deux côtés parlent le même protocole. Tant que le handshake n'a pas réussi, aucune partie ne peut commencer.

```mermaid
sequenceDiagram
    participant ESP as ESP32 (firmware)
    participant RPI as RPi (uart_client.py)

    Note over ESP: Reset / power-on
    ESP->>RPI: <BOOT_START|seq=0|crc=...>
    Note over ESP: setup() en cours...
    ESP->>RPI: <SETUP_DONE|seq=1|crc=...>

    loop Toutes les 200 ms
        ESP->>RPI: <HELLO|v=1|seq=N|crc=...>
    end

    Note over RPI: connect(timeout=15s)
    RPI->>ESP: <HELLO_ACK|seq=M|ack=N|crc=...>

    Note over ESP,RPI: Session établie<br/>is_connected = True

    loop Toutes les 1 s en session
        RPI->>ESP: <KEEPALIVE|seq=K|crc=...>
    end
```

> Le HELLO_ACK doit arriver avant **15 secondes**, sinon `uart_client.connect()` lève `UartTimeoutError` et la partie ne démarre pas.

---

## Cycle d'un coup IA (RPi → ESP32)

Quand c'est le tour de l'IA, le RPi calcule le coup en Python puis envoie une commande à l'ESP32, qui exécute physiquement (déplacement chariot + servo si mur). L'ESP32 confirme par DONE.

```mermaid
sequenceDiagram
    participant AI as IA Python<br/>(ai.py)
    participant RPI as uart_client.py
    participant ESP as Firmware ESP32

    AI->>RPI: find_best_move() retourne<br/>('deplacement', (3, 4))
    RPI->>ESP: <CMD PAWN 3 4|seq=12|crc=A7F3>

    alt Succès direct
        Note over ESP: GOTO x y selon mapping<br/>(case → position en pas)
        ESP->>RPI: <DONE|seq=20|ack=12|crc=...>
        Note over RPI: send_cmd() retourne OK
    else Erreur récupérable (UART_LOST)
        ESP->>RPI: <ERR UART_LOST|seq=21|crc=...>
        RPI->>ESP: <CMD_RESET|seq=13|crc=...>
        Note over RPI: Re-handshake puis retry
    else Timeout (15 s sans DONE)
        Note over RPI: Retry avec MÊME seq<br/>(idempotence)
        RPI->>ESP: <CMD PAWN 3 4|seq=12|crc=A7F3>
        Note over ESP: Déduplication via<br/>last_cmd_seq_processed
        ESP->>RPI: <DONE|seq=22|ack=12|crc=...>
    else 3 essais échoués
        Note over RPI: Lève UartTimeoutError<br/>partie interrompue
    end
```

> **Idempotence** : sur retry, le RPi conserve le même `seq`. L'ESP32 garde en mémoire le dernier `seq` traité, donc si la trame revient en double, il ne ré-exécute pas le coup et renvoie juste le DONE caché.

---

## Cycle d'un coup humain via plateau physique

Le joueur appuie sur des boutons du plateau pour signaler son intention. L'ESP32 envoie une **requête** (MOVE_REQ ou WALL_REQ), et le RPi répond ACK (coup valide, va l'exécuter) ou NACK avec un code d'erreur typé.

```mermaid
sequenceDiagram
    participant USER as Joueur
    participant ESP as Firmware ESP32
    participant RPI as game_session.py
    participant ENGINE as quoridor_engine

    USER->>ESP: Appui bouton case (r, c)
    ESP->>RPI: <MOVE_REQ 3 4|seq=30|crc=...>

    RPI->>ENGINE: play_move(('deplacement', (3, 4)))

    alt Coup valide
        ENGINE->>RPI: Nouvel état OK
        RPI->>ESP: <ACK|seq=40|ack=30|crc=...>
        Note over ESP: Exécute mouvements<br/>(GOTO + éventuellement servo)
        ESP->>RPI: <DONE|seq=31|ack=40|crc=...>
        Note over RPI: Passe au tour suivant
    else Coup invalide
        ENGINE->>RPI: InvalidMoveError(code=ILLEGAL)
        RPI->>ESP: <NACK ILLEGAL|seq=41|ack=30|crc=...>
        Note over ESP: Refus signalé au joueur<br/>(LED rouge, beep)
        USER->>ESP: Nouvelle tentative
    end
```

---

## Catalogue des codes NACK

Le moteur Python lève une exception `InvalidMoveError(message, code: NackCode)` qui est convertie en NACK textuel sur l'UART. Les codes sont alignés exactement entre Python et C++.

```mermaid
flowchart LR
    NACK(["NACK"]) --> CODES

    CODES{"Code"}

    CODES --> C1["ILLEGAL<br/>Mouvement non autorisé<br/>(cible inaccessible, mur entre, etc.)"]
    CODES --> C2["OUT_OF_BOUNDS<br/>Coordonnée hors plateau<br/>(case ou mur)"]
    CODES --> C3["WRONG_TURN<br/>Ce n'est pas le tour<br/>de ce joueur"]
    CODES --> C4["WALL_BLOCKED<br/>Mur identique, chevauchement,<br/>croisement, ou blocage<br/>du chemin adverse"]
    CODES --> C5["NO_WALLS_LEFT<br/>Le joueur a déjà utilisé<br/>ses 6 murs"]
    CODES --> C6["INVALID_FORMAT<br/>Trame mal formée<br/>(args invalides)"]

    style NACK fill:#f44336,color:#fff
    style C1 fill:#FF7043,color:#fff
    style C2 fill:#FF7043,color:#fff
    style C3 fill:#FF7043,color:#fff
    style C4 fill:#FF7043,color:#fff
    style C5 fill:#FF7043,color:#fff
    style C6 fill:#FF7043,color:#fff
```

---

## Gestion des erreurs et déconnexions

Le protocole distingue deux familles d'erreurs : récupérables (un reset suffit) et non-récupérables (partie interrompue).

```mermaid
flowchart TD
    ERR(["L'ESP32 émet <ERR CODE>"]) --> KIND{"Type d'erreur"}

    KIND -->|"Récupérable"| RECOV["UART_LOST<br/>BUTTON_MATRIX<br/>..."]
    KIND -->|"Non récupérable"| FATAL["MOTOR_TIMEOUT<br/>HOMING_FAILED<br/>BOOT_I2C<br/>..."]

    RECOV --> RESET["RPi envoie<br/><CMD_RESET|seq=N>"]
    RESET --> REHANDSHAKE["Re-handshake<br/>HELLO/HELLO_ACK"]
    REHANDSHAKE --> RESUME["Reprise de la partie<br/>(état GameState préservé)"]

    FATAL --> ABORT["Lève UartHardwareError<br/>côté Python"]
    ABORT --> STOP["Partie interrompue<br/>+ message d'erreur"]

    style ERR fill:#f44336,color:#fff
    style RESUME fill:#4CAF50,color:#fff
    style STOP fill:#9E9E9E,color:#fff
```

> **Limitation connue (Plan P11 à venir)** : après un reset ESP32, la position physique des pions sur le plateau est perdue tant que la machine n'a pas refait son HOME. La re-synchronisation complète sera ajoutée dans une phase ultérieure.

---

## Vue d'ensemble du dialogue typique d'une partie

```mermaid
sequenceDiagram
    participant ESP as ESP32
    participant RPI as RPi (game_session.py)

    Note over ESP,RPI: 1. Boot + handshake
    ESP->>RPI: HELLO (boucle)
    RPI->>ESP: HELLO_ACK

    Note over ESP,RPI: 2. Tour 1 — humain
    ESP->>RPI: MOVE_REQ (r, c)
    RPI->>ESP: ACK
    ESP->>RPI: DONE

    Note over ESP,RPI: 3. Tour 2 — IA
    RPI->>ESP: CMD PAWN (r, c)
    ESP->>RPI: DONE

    Note over ESP,RPI: 4. Tour 3 — humain (mur)
    ESP->>RPI: WALL_REQ (h, r, c)
    RPI->>ESP: ACK
    ESP->>RPI: DONE

    Note over ESP,RPI: ...alternance jusqu'à victoire

    Note over ESP,RPI: N. Fin de partie
    RPI->>ESP: CMD GAMEOVER j1
    ESP->>RPI: DONE
```

---

> **Principe clé** : tous les échanges sont **typés** (verbe explicite), **vérifiés** (CRC-16), **séquencés** (anti-doublon) et **acquittés** (corrélation requête/réponse). Cette discipline garantit que le moteur de jeu Python reste la **seule source de vérité** sur les règles, et que l'ESP32 ne fait qu'exécuter ce qui lui est explicitement demandé.
