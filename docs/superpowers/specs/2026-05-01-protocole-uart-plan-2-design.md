# Protocole UART Plan 2 — design

**Date :** 2026-05-01
**Auteur :** Silouane (brainstorming assisté)
**Statut :** validé, prêt pour planification d'implémentation
**Portée :** spécification complète du protocole UART entre la Raspberry Pi (Python) et l'ESP32-WROOM (Arduino C++) pour le projet Quoridor 6×6. Couvre format des trames, séquencement, idempotence, politique d'erreurs, co-existence avec le debug, stratégie de tests. Implémentation détaillée par module (ESP32 et Python), intégration `main.py` et tests E2E sont explicitement hors scope (specs ultérieurs).
**Source amont :** [`2026-04-28-firmware-esp32-architecture-globale-design.md`](2026-04-28-firmware-esp32-architecture-globale-design.md). Ce spec en hérite directement (UART0 / 115200 bauds, FSM ESP32, primitives sémantiques, codes d'erreur, paramètres temporels). Toute divergence apparente entre les deux est une erreur à signaler.
**Phase couverte :** P8 du [plan global](../../00_plan_global.md) (sous-tâches P8.1 à P8.6).

---

## Table des matières

1. [Contexte](#1-contexte)
2. [Décisions architecturales (synthèse)](#2-décisions-architecturales-synthèse)
3. [Format de trame](#3-format-de-trame)
4. [Catalogue des trames](#4-catalogue-des-trames)
5. [Séquencement et idempotence](#5-séquencement-et-idempotence)
6. [Politique d'erreurs et retransmission](#6-politique-derreurs-et-retransmission)
7. [Co-existence debug ↔ protocole](#7-co-existence-debug--protocole)
8. [Stratégie de tests](#8-stratégie-de-tests)
9. [Implémentation — structure proposée](#9-implémentation--structure-proposée)
10. [Coupure nette avec Plan 1](#10-coupure-nette-avec-plan-1)
11. [Hors scope (specs ultérieurs)](#11-hors-scope-specs-ultérieurs)

---

## 1. Contexte

Le projet Quoridor Interactif repose sur deux processeurs qui communiquent par UART :

- **Raspberry Pi 3/4** : moteur de jeu Python (`quoridor_engine/`), IA Minimax, orchestration des tours.
- **ESP32-WROOM** : firmware Arduino C++, exécutant moyen niveau (cf. spec d'architecture §2.1) — boutons, LEDs WS2812B, moteurs A4988 via MCP23017, servo SG90.
- **Liaison physique** : UART0 (GPIO1/3 côté ESP32), 115200 bauds, câble direct, fin de ligne `LF`. **L'UART0 est physiquement partagée avec le port USB de debug** de l'ESP32.

Le firmware Plan 1 (terminé en P5) utilise un **protocole texte stub** ligne par ligne (`HELLO`, `BTN x y`, `ACK`, `NACK`, `CMD MOVE x y`, etc.) sans framing strict, sans intégrité, sans séquencement. Ce protocole stub a permis de valider la FSM, le watchdog et l'orchestration générale, mais il a **5 limites bloquantes** pour la mise en production :

1. Pas de checksum / CRC : un bit corrompu = trame acceptée comme valide.
2. Pas de framing structurel : un `Serial.println("debug")` quelque part dans le code parasite le protocole.
3. Pas de versioning : impossible de détecter une incompatibilité firmware ↔ Python au boot.
4. Pas de séquencement : un ACK retardé peut être attribué à la mauvaise requête.
5. Pas de retransmission idempotente : si un `DONE` se perd, un retry pourrait faire bouger le pion deux fois.

Le **Plan 2** définit le protocole final qui remplace intégralement le Plan 1. La transition est nette (pas de mode rétrocompatible — cf. §10).

---

## 2. Décisions architecturales (synthèse)

Cinq décisions de fond, prises dans l'ordre lors du brainstorming. Chacune est justifiée et défendable en soutenance.

### 2.1 Format des trames : texte avec framing explicite

**Décision :** trames texte, encadrées par `<` et `>\n`, lisibles au Serial Monitor.

**Justification :**

- Le throughput est négligeable (quelques trames/s côté boutons, 1 KEEPALIVE/s) : l'argument compacité du binaire ne pèse rien à 115200 bauds.
- L'UART partagée avec le debug USB est une vraie contrainte opérationnelle : avec du texte préfixé, debug et protocole se distinguent visuellement *et* structurellement (cf. §7).
- L'**injection manuelle de tests** au Serial Monitor (`BTN 3 4`) est utilisée par le firmware Plan 1 et le restera en P9.4. Incompatible avec un format binaire.
- Le délimiteur `<` au début (vs LF seul) garantit une **séparation structurelle** debug/protocole : si une ligne ne commence pas par `<`, elle est ignorée par le parser. Pas de discipline de préfixe à maintenir côté humain.

**Alternative écartée — binaire avec COBS/SLIP :** sur-ingénieré pour le throughput attendu, illisible au monitor (coût UX/debug), incompatible avec l'injection manuelle.
**Alternative écartée — texte simple ligne par ligne (LF seul) :** resync fragile en cas de bruit, distinction debug/protocole repose sur une convention humaine plutôt que sur la grammaire.

### 2.2 Intégrité : CRC-16 CCITT-FALSE

**Décision :** CRC-16 CCITT-FALSE (polynôme 0x1021, init 0xFFFF, refIn=false, refOut=false, xorOut=0x0000), encodé sur 4 chiffres hexadécimaux majuscules en fin de trame.

**Justification :**

- CRC-16 détecte tout burst d'erreur ≤ 16 bits, taux de fausse acceptation ~0.0015 %. CRC-8 plafonne à ~0.4 % (260× pire), XOR ~50 % (rate toute erreur paire).
- Variant **CCITT-FALSE** spécifiquement parce que `binascii.crc_hqx(data, 0xFFFF)` est dans la stdlib Python : **zéro dépendance à ajouter**. Côté ESP32, ~15 lignes de C++ ou la lib `FastCRC` (déjà courante en Arduino).
- Overhead négligeable : 4 octets de plus sur des trames de 25-50 octets, soit ~10 % au pire. À 115200 bauds, 4 octets = 350 µs invisibles.
- Standard de fait pour les protocoles série courts (XMODEM, CCITT-FALSE est utilisé par AUTOSAR et Bluetooth Classic). Réponse défendable en soutenance sans justification supplémentaire.

**Alternative écartée — CRC-8 :** taux de détection trop faible pour un protocole qui pilote des moteurs.
**Alternative écartée — XOR :** mauvais signal en revue (rate les erreurs paires, c'est un anti-pattern dans les cours de communications numériques).
**Alternative écartée — pas de CRC :** un seul bit flip dans `MOVE_REQ 3 4` qui transforme `3` en `2` → mauvais coup envoyé à l'IA, qui le valide possiblement. Inacceptable.

### 2.3 Versioning : champ `v=K` uniquement dans `HELLO`

**Décision :** chaque trame `HELLO` (ESP32 → RPi) porte un champ `v=K` indiquant la version du protocole supportée par le firmware. Le RPi compare avec sa version compilée. Si mismatch → exception claire, programme s'arrête. Version courante : **v=1**.

**Justification :**

- Le projet a un **seul couple de déploiement** (firmware + Python mis à jour ensemble). Pas de flotte avec gestion de rétrocompatibilité fine.
- Mettre `v=` sur chaque trame = cargo-cult : utile dans des contextes d'évolution lente sur N appareils, pas ici. Coût ~4 octets/trame pour zéro bénéfice.
- En revanche, mettre `v=` dans `HELLO` permet une **détection au boot** d'un mismatch (ex : on met à jour Python sur le Mac mais on oublie de reflasher l'ESP32 connecté à la RPi). Sans cette détection, des trames seraient silencieusement mal interprétées.

**Bumping :** la version est incrémentée uniquement en cas de **changement incompatible** du format de trame (renommage de TYPE, modification de champs obligatoires, changement d'encodage du CRC, etc.). L'ajout d'une nouvelle commande optionnelle ne bumpe pas la version.

### 2.4 Séquencement : `seq=N` sur toutes les trames, `ack=M` sur les réponses

**Décision :** chaque émetteur (ESP32 et Python) maintient un compteur `tx_seq` ∈ [0, 255], incrémenté modulo 256 à chaque trame émise. Toute trame porte `seq=N`. Les **réponses** (ACK, NACK, DONE, HELLO_ACK, et ERR quand répond à une CMD) portent en plus `ack=M` où M est le seq de la requête à laquelle elles répondent.

**Justification :**

- Sans `seq`, un scénario simple suffit à créer un bug : ESP32 envoie `MOVE_REQ`, timeout 500 ms, retour `CONNECTED`, joueur reclique, nouvelle `MOVE_REQ` → l'ACK retardé du premier arrive et est interprété comme l'ACK du deuxième. Bug subtil et reproductible.
- `seq` permet aussi la **dédup côté ESP32** (cf. §5.3) pour le retry idempotent des commandes RPi.
- Coût : ~6-9 octets/trame (`|seq=NNN`). Négligeable.
- 256 valeurs largement suffisantes : avec **au plus 1 trame en vol** (architecture sans pipelining), aucun risque de collision sur le wraparound.

**Alternative écartée — pas de seq :** la pipe de bugs subtils (ACK retardé) n'est pas couverte. Inacceptable pour un projet à présenter.

### 2.5 Politique de retransmission : retry idempotent uniquement sur `CMD ...`

**Décision :** retry automatique **uniquement** sur les trames `CMD ...` (RPi → ESP32), avec idempotence garantie par seq (max 3 essais total : 1 envoi initial + 2 retries, timeout 15 s entre chaque). Pour toutes les autres trames, **l'humain est la boucle de retransmission** (le joueur reclique, le KEEPALIVE est ré-émis périodiquement, etc.).

**Justification :**

- Identification de qui retentera spontanément :
  - `MOVE_REQ` / `WALL_REQ` perdu → le joueur voit le flash orange, reclique. **Pas de retry auto nécessaire.**
  - `CMD MOVE` (coup IA) perdu → personne ne retentera spontanément, le pion ne bouge plus, la partie semble figée. **Le seul cas où le retry auto est indispensable.**
  - `KEEPALIVE` perdu → couvert par "3 manqués = `ERR_UART_LOST`", pas de retry à ajouter.
  - `HELLO` perdu → ré-émis périodiquement par l'ESP32 toutes les 200 ms tant que pas d'ACK.
  - `ACK` / `NACK` / `DONE` perdu → c'est une réponse, l'émetteur de la requête originale gère son timeout.
- L'idempotence est gratuite (on a déjà les seq) : si l'ESP32 reçoit deux fois la même CMD avec le même seq, il dédoublonne et renvoie le résultat sans re-exécuter.

**Garantie pratique :** le pion ne bouge **jamais** deux fois pour une même CMD, même si le `DONE` est perdu N fois.

---

## 3. Format de trame

### 3.1 Grammaire (BNF simplifié)

```
trame      ::= '<' TYPE [ ' ' arg { ' ' arg } ] '|' meta_seq [ '|' meta_ack ] [ '|' meta_v ] '|' meta_crc '>' '\n'

TYPE       ::= mot en MAJUSCULES (lettres, chiffres, underscores, jamais d'espace)
arg        ::= mot ASCII sans <, >, |, =, espace ; ou entier décimal
meta_seq   ::= 'seq=' entier_decimal_0_255
meta_ack   ::= 'ack=' entier_decimal_0_255           (présent sur réponses uniquement)
meta_v     ::= 'v=' entier_decimal_positif           (présent sur HELLO uniquement)
meta_crc   ::= 'crc=' 4_chiffres_hexa_majuscules     (toujours en dernier)
```

**Ordre des champs strictement figé** : `TYPE [args] | seq | (ack OU v selon contexte) | crc`. Une trame qui dévie de cet ordre est rejetée comme malformée. Cette rigidité simplifie l'écriture du parser (un seul `split('|')` suffit) et élimine les ambiguïtés.

### 3.2 Encodage des champs

| Champ | Encodage | Exemple |
|---|---|---|
| `TYPE` | MAJUSCULES, underscores autorisés (`MOVE_REQ`, `CMD_RESET`) | `MOVE_REQ` |
| Arguments | MAJUSCULES pour les mots-clés (`ILLEGAL`, `MOVE`, `WALL`), décimal pour les entiers | `MOVE 3 4` |
| `seq=N` | Décimal, 1 à 3 chiffres (0 à 255), sans zéro de tête | `seq=42` |
| `ack=M` | Idem | `ack=42` |
| `v=K` | Décimal, ≥ 1 | `v=1` |
| `crc=XXXX` | Hexadécimal **majuscules**, **exactement 4 chiffres** (zéros de tête si valeur < 0x1000) | `crc=A1B2`, `crc=0089` |

Le décimal pour `seq`/`ack` (vs hexa) évite toute confusion avec le CRC.

### 3.3 Caractères réservés et casse

**Réservés (interdits dans les arguments)** : `<`, `>`, `|`, `=`, espace (sauf comme séparateur entre args), `\n`, `\r`, et tout caractère de contrôle. Les caractères ASCII non imprimables (sauf `\n`/`\r`) ne sont jamais émis ni acceptés.

**Pas d'UTF-8.** Le protocole est strictement ASCII imprimable.

**Sensibilité à la casse stricte :**
- TYPE et mots-clés argument : **MAJUSCULES** uniquement.
- Méta-champs (`seq`, `ack`, `v`, `crc`) : **minuscules** uniquement.
- Valeur du CRC : **hexa MAJUSCULES** uniquement.

Une casse divergente → rejet. Cette rigidité élimine l'ambiguïté et facilite la rédaction du parser.

### 3.4 Calcul du CRC

**Zone couverte :** tous les octets entre `<` (exclu) et `|crc=` (exclu).

**Exemple détaillé :**

```
Trame complète : <MOVE_REQ 3 4|seq=42|crc=A1B2>\n
Zone CRC       : MOVE_REQ 3 4|seq=42
                 (19 octets, pas de \n, pas de < ni de >, pas de |crc=)
```

Le CRC est calculé sur ces 19 octets, encodé en 4 hexa majuscules, et inséré dans `crc=A1B2`.

**Paramètres CRC-16 CCITT-FALSE :**

| Paramètre | Valeur |
|---|---|
| Polynôme | 0x1021 |
| Valeur initiale | 0xFFFF |
| Réflexion entrée | non |
| Réflexion sortie | non |
| XOR final | 0x0000 |

**Implémentation Python :** `binascii.crc_hqx(data_bytes, 0xFFFF)` retourne directement la valeur CRC sur 16 bits. Aucune dépendance externe.

**Implémentation ESP32 :** soit la lib `FastCRC` (`FastCRC16().ccitt(data, len)`), soit ~15 lignes maison. Voir §9.1 pour le squelette de code recommandé.

### 3.5 Vecteurs de référence CRC

**À figer en P8.4** lors de l'écriture des tests Python : calculer ces 3 vecteurs avec un outil tiers de référence ([crccalc.com](https://crccalc.com) en sélectionnant "CRC-16/CCITT-FALSE", ou la stdlib Python en console) et inscrire les valeurs dans cette table. Les tests unitaires ET les tests d'intégration vérifient ces valeurs comme références figées.

| Input (zone CRC) | CRC attendu (à figer en P8.4) |
|---|---|
| `MOVE_REQ 3 4\|seq=42` | `0xAED2` |
| `CMD MOVE 2 5\|seq=43` | `0x8489` |
| `KEEPALIVE\|seq=0` | `0x74D8` |

**Procédure de figement :**

```python
# À exécuter une fois en P8.4, copier les valeurs dans la table ci-dessus
import binascii
for s in ["MOVE_REQ 3 4|seq=42", "CMD MOVE 2 5|seq=43", "KEEPALIVE|seq=0"]:
    crc = binascii.crc_hqx(s.encode("ascii"), 0xFFFF)
    print(f"{s!r} → 0x{crc:04X}")
```

Si l'ESP32 et Python ne tombent pas sur les mêmes valeurs, l'implémentation est buggée — divergence à corriger immédiatement.

### 3.6 Trame mal formée — traitement

Une trame est **mal formée** si elle viole une contrainte parmi :
- Longueur > 80 octets (incluant délimiteurs et `\n`).
- N'est pas encadrée par `<` et `>` correctement.
- Ordre des champs incorrect.
- Casse incorrecte sur un TYPE, argument ou méta-champ.
- Caractères interdits dans un argument.
- Champ obligatoire manquant (`seq` ou `crc`).
- Valeur de `seq`/`ack`/`v` non décimale ou hors plage.
- Valeur de `crc` non hexa, longueur ≠ 4, ou minuscules.
- CRC calculé ≠ CRC reçu.

**Action des deux côtés (ESP32 et Python) : rejet silencieux.**
- Pas de NACK envoyé (un NACK pourrait lui-même être corrompu, boucle sans fin potentielle).
- Pas de log d'alerte.
- **Compteur statistique optionnel** côté implémentation pour debug ("X trames rejetées depuis le boot") — utile uniquement pour le diagnostic, pas exposé par le protocole.
- Le timeout naturel côté émetteur fait son travail : si la trame était une CMD, le RPi retentera ; si c'était une intention bouton, le joueur recliquera.

**Conséquence :** une trame perdue et une trame corrompue sont **indistinguables** pour l'émetteur. C'est voulu — les deux situations méritent le même traitement.

---

## 4. Catalogue des trames

18 types au total : 8 émis par ESP32, 10 émis par RPi.

### 4.1 ESP32 → RPi (8 types)

| TYPE | Args | Format complet (exemple) | Quand |
|---|---|---|---|
| `BOOT_START` | aucun | `<BOOT_START\|seq=0\|crc=...>\n` | Tout début de `setup()` |
| `SETUP_DONE` | aucun | `<SETUP_DONE\|seq=1\|crc=...>\n` | Fin du `setup()` |
| `HELLO` | aucun | `<HELLO\|seq=2\|v=1\|crc=...>\n` | Toutes les 200 ms en état `WAITING_RPI` |
| `MOVE_REQ` | `<row> <col>` | `<MOVE_REQ 3 4\|seq=42\|crc=...>\n` | Détection d'un clic 1 case |
| `WALL_REQ` | `<h\|v> <row> <col>` | `<WALL_REQ h 2 3\|seq=43\|crc=...>\n` | Détection de 2 clics simultanés (intention mur) |
| `DONE` | aucun | `<DONE\|seq=44\|ack=43\|crc=...>\n` | Fin d'exécution d'une `CMD ...` reçue |
| `ERR` | `<code>` | `<ERR UART_LOST\|seq=45\|crc=...>\n` ou avec `ack=` | Entrée dans état `ERROR` (réémis périodiquement, voir §6.5) |

### 4.2 RPi → ESP32 (10 types)

| TYPE | Args | Format complet (exemple) | Quand |
|---|---|---|---|
| `HELLO_ACK` | aucun | `<HELLO_ACK\|seq=0\|ack=2\|crc=...>\n` | Réponse à `HELLO` (active `CONNECTED`) |
| `KEEPALIVE` | aucun | `<KEEPALIVE\|seq=1\|crc=...>\n` | Toutes les 1 s en session active |
| `ACK` | aucun | `<ACK\|seq=2\|ack=42\|crc=...>\n` | Validation d'un `MOVE_REQ` ou `WALL_REQ` |
| `NACK` | `<raison>` | `<NACK ILLEGAL\|seq=3\|ack=42\|crc=...>\n` | Refus d'un `MOVE_REQ` ou `WALL_REQ` |
| `CMD MOVE` | `<row> <col>` | `<CMD MOVE 2 5\|seq=4\|crc=...>\n` | Coup de l'IA — déplacement de pion |
| `CMD WALL` | `<h\|v> <row> <col>` | `<CMD WALL v 1 2\|seq=5\|crc=...>\n` | Coup de l'IA — placement de mur |
| `CMD HIGHLIGHT` | `[<row> <col> ...]` (0 à 8 cellules) | `<CMD HIGHLIGHT 2 3 2 4 3 3\|seq=6\|crc=...>\n` | Surbrillance des coups possibles ; sans args = clear |
| `CMD SET_TURN` | `<j1\|j2>` | `<CMD SET_TURN j1\|seq=7\|crc=...>\n` | Indicateur visuel du tour courant |
| `CMD GAMEOVER` | `<j1\|j2>` | `<CMD GAMEOVER j1\|seq=8\|crc=...>\n` | Fin de partie — déclenche animation victoire + servo de réinit murs |
| `CMD_RESET` | aucun | `<CMD_RESET\|seq=9\|crc=...>\n` | Reset depuis état `ERROR` |

### 4.3 Codes d'erreur (`ERR <code>`)

Alignés sur le spec d'architecture §3 :

| Code | Signification | Récupérable par `CMD_RESET` ? |
|---|---|---|
| `UART_LOST` | 3 KEEPALIVE consécutifs manqués | ✅ oui (souvent transient) |
| `BUTTON_MATRIX` | ≥ 3 boutons collés simultanés | ✅ oui (peut être un faux positif) |
| `MOTOR_TIMEOUT` | Mouvement moteur dépassé sa durée théorique × 2 | ❌ non (probable blocage mécanique) |
| `LIMIT_UNEXPECTED` | Fin de course atteint pendant trajectoire | ❌ non |
| `HOMING_FAILED` | Homing au boot impossible | ❌ non |
| `I2C_NACK` | MCP23017 muet | ❌ non (probable câble I2C) |
| `BOOT_I2C` | Test I2C échoué au boot | ❌ non |
| `BOOT_LED` | Test LED échoué au boot | ❌ non |
| `BOOT_HOMING` | Homing échoué au boot | ❌ non |

**Distinction récupérable / non-récupérable :** côté Python, à la réception d'un `ERR` :
- **Récupérable** (`UART_LOST`, `BUTTON_MATRIX`) → envoi automatique de `CMD_RESET`, attente du nouveau `BOOT_START`/`HELLO`, reprise de la partie au tour courant si possible.
- **Non-récupérable** → log d'erreur, alerte joueur ("erreur hardware, reset manuel requis"), partie suspendue, pas de tentative auto.

### 4.4 Codes de raison (`NACK <raison>`)

| Code | Signification |
|---|---|
| `ILLEGAL` | Coup invalide selon les règles Quoridor (générique) |
| `OUT_OF_BOUNDS` | Coordonnée hors plateau |
| `WRONG_TURN` | Pas le tour de ce joueur |
| `WALL_BLOCKED` | Mur déjà placé à cet endroit ou bloque le pathfinding adverse |
| `NO_WALLS_LEFT` | Joueur n'a plus de murs disponibles |
| `INVALID_FORMAT` | Trame syntaxiquement OK mais sémantiquement aberrante (ex : `WALL_REQ` avec coordonnées non adjacentes) |

L'argument unique est en MAJUSCULES, sans espace. Pour un message multi-mots, utiliser des underscores : `NACK ILLEGAL_MOVE_OUT_OF_BOARD`.

### 4.5 Convention coordonnées

**Cellules** (pour `MOVE_REQ`, `CMD MOVE`, `CMD HIGHLIGHT`) : `(row, col)` avec `(0,0)` = coin haut-gauche, `(5,5)` = coin bas-droit (cohérent avec le moteur Python, cf. CLAUDE.md).

**Murs** (pour `WALL_REQ`, `CMD WALL`) : la position transmise est la **position canonique d'ancrage** = la plus petite des 2 cellules qu'il sépare (coin haut-gauche du segment). Cohérent avec le moteur Python qui stocke `('mur', ('h'|'v', row, col, 2))` (la longueur 2 est implicite).

- Mur **horizontal** entre lignes `r` et `r+1`, colonne `c` → `WALL_REQ h r c`
- Mur **vertical** entre colonnes `c` et `c+1`, ligne `r` → `WALL_REQ v r c`

**Filtrage sémantique côté ESP32 : aucun.** L'ESP32 envoie au RPi toute intention détectée, même apparemment aberrante. Le RPi est maître absolu et répond `NACK INVALID_FORMAT` ou `NACK ILLEGAL` selon la nature du problème. Cohérent avec le spec d'architecture §2.1.

**Cas du double clic accidentel sur 2 cellules non adjacentes :** l'ESP32 considère 2 cellules adjacentes comme `WALL_REQ`, sinon traite chaque cellule comme un `MOVE_REQ` séparé en file (premier servi). Si > 2 cellules sont cliquées dans la fenêtre 50 ms → on prend les 2 premières + ignore le reste.

### 4.6 Trame d'injection test (asymétrique, ESP32 réception uniquement)

Pour les tests manuels au Serial Monitor (en P9.4 sans hardware, ou pour le debug en cours de partie), l'ESP32 accepte **en réception** un format simplifié sans framing ni CRC, **uniquement pour `BTN <row> <col>`** :

```
BTN 3 4\n                 ← équivalent à un clic en (3,4), interprété comme MOVE_REQ
BTN 2 3 2 4\n             ← équivalent à 2 clics simultanés, interprété comme WALL_REQ h 2 3
```

**Asymétrie volontaire :**
- Seul l'**ESP32 accepte ce format en entrée** (au Serial Monitor par un humain).
- Le **Python n'émet jamais** ce format.
- L'ESP32 n'émet jamais ce format.

**Disponibilité :** uniquement quand l'ESP32 est en `CONNECTED` ou `BUTTON_INTENT_PENDING` (pas en `BOOT`, `WAITING_RPI`, `EXECUTING`, `ERROR`, `DEMO`).

**Effet :** la trame `BTN ...` est traitée **comme si la matrice physique avait détecté ce clic**. L'ESP32 émet alors une vraie trame protocolaire `MOVE_REQ` ou `WALL_REQ` au RPi, avec son propre seq, framée et CRC valide. C'est uniquement la *source* de l'intention qui change (Serial Monitor humain vs matrice physique), pas la suite du flow.

---

## 5. Séquencement et idempotence

### 5.1 Compteurs `tx_seq` (par émetteur)

Chaque côté maintient son propre compteur de seq sortant :

```
ESP32  : tx_seq_esp ∈ [0, 255]
Python : tx_seq_py  ∈ [0, 255]
```

**Règle d'incrément :**
- À chaque trame émise, le compteur est **utilisé** pour le champ `seq=`, puis **incrémenté modulo 256** : `tx_seq = (tx_seq + 1) & 0xFF`.
- **Une seule exception :** quand on **retransmet** une CMD (retry idempotent côté RPi, cf. §5.3), on **réutilise le même seq** que l'envoi initial. Sinon l'idempotence ne fonctionnerait pas.

**Initialisation :**
- ESP32 : `tx_seq_esp = 0` au boot (init avant `BOOT_START`). Première trame émise (`BOOT_START`) part avec `seq=0`.
- Python : `tx_seq_py = 0` au démarrage du programme.

**Reset de session côté Python :** à la réception d'un `BOOT_START` **OU** d'un `HELLO` alors qu'une session était déjà active, Python considère que l'ESP32 a redémarré et **reset complètement sa session** :
- `tx_seq_py = 0`
- `last_request_seq = None`
- Abandon de tous les retries CMD en cours
- `last_err_received = None` (cf. §6.5)

(Côté ESP32, pas de reset symétrique : c'est l'ESP32 qui génère le `BOOT_START`/`HELLO`, donc son compteur est cohérent par construction.)

### 5.2 Ack matching côté émetteur d'une requête

Chaque côté maintient une seule variable pour les requêtes en vol :

```
last_request_seq : int | None    # seq de la dernière requête émise pour laquelle on attend une réponse
```

À l'émission d'une requête : `last_request_seq = seq_de_la_trame`.

À la réception d'une réponse (ACK / NACK / DONE / HELLO_ACK / ERR avec ack=) :

| Condition | Action |
|---|---|
| `ack=M` reçu et `M == last_request_seq` | Match. Traiter normalement. `last_request_seq = None`. |
| `ack=M` reçu et `M != last_request_seq` | Réponse orpheline (en retard ou bug). **Ignorer silencieusement.** |
| `ack=M` reçu et `last_request_seq is None` | Aucune requête en vol. Réponse orpheline. **Ignorer.** |

**Cas concret côté ESP32 :**
- Joueur clique → ESP32 émet `MOVE_REQ seq=42` → `last_request_seq = 42`, état `BUTTON_INTENT_PENDING`.
- `ACK ack=42` arrive avant 500 ms → match, transition vers `EXECUTING`.
- `ACK ack=42` arrive après 500 ms → l'ESP32 a déjà timeouté et reset `last_request_seq = None` → ignoré.
- `ACK ack=39` arrive → orphelin → ignoré, l'état reste `BUTTON_INTENT_PENDING`.

**Cas concret côté Python :**
- Python émet `CMD MOVE seq=43` → `last_request_seq = 43`, attente `DONE` 15 s.
- `DONE ack=43` arrive → match, requête acquittée.
- `DONE ack=12` arrive → orphelin → ignoré (et le timeout 15 s continue de courir).

### 5.3 Idempotence côté ESP32 (dédup des CMD)

L'ESP32 maintient deux variables pour gérer les retries de CMD :

```
last_cmd_seq_processed : int  (initialisé à -1, sentinelle "aucune CMD jamais traitée")
last_cmd_result        : enum {NONE, DONE, ERR}  (initialisé à NONE)
last_cmd_err_code      : str | None  (code de l'erreur si last_cmd_result == ERR)
```

**À la réception d'une trame `CMD ...` avec `seq=N` :**

| Cas | Condition | Action |
|---|---|---|
| **Nouvelle commande** | `N != last_cmd_seq_processed` | `last_cmd_seq_processed = N` ; `last_cmd_result = NONE` ; **lance l'exécution**. À la fin, met à jour `last_cmd_result` (DONE ou ERR + code) et émet la réponse correspondante avec `ack=N`. |
| **Retry pendant exécution** | `N == last_cmd_seq_processed` ET `last_cmd_result == NONE` | **Ignore silencieusement.** Pas de réponse. Le RPi attendra son timeout. |
| **Retry après exécution finie** | `N == last_cmd_seq_processed` ET `last_cmd_result != NONE` | **Renvoie immédiatement** la réponse stockée (`DONE` ou `ERR`) avec `ack=N`. **Ne pas re-exécuter.** |

**Point critique — moment de la mise à jour :** `last_cmd_seq_processed = N` est mis à jour **dès le début du traitement**, **avant** l'exécution effective (et non à la fin). C'est ce qui garantit qu'un retry arrivant pendant l'exécution est correctement détecté.

**Pourquoi un seul slot de mémoire suffit :** côté Python, il y a au plus **1 CMD en vol à la fois** (séquentialité garantie par l'architecture : Python attend `DONE` avant la CMD suivante). Donc seule la dernière commande peut être retransmise — pas besoin d'historique.

**Wraparound du seq :**
- Si CMD seq=255 puis CMD seq=0 : `0 != 255` → traité comme nouvelle commande ✓
- Risque de collision sur 256 commandes consécutives sans intervention : impossible en pratique (max 1 CMD en vol, throughput humain ~10 CMD/min).

### 5.4 Pas d'idempotence côté Python

Le RPi ne reçoit pas de retries actifs de l'ESP32 :
- Les `MOVE_REQ` / `WALL_REQ` perdus ne sont pas retransmis (le joueur reclique → nouvelle trame avec **nouveau** seq).
- Les `DONE` / `ACK` / `NACK` perdus ne sont pas retransmis (le retry CMD côté RPi déclenchera le renvoi par l'ESP32).
- Seul `ERR` est réémis périodiquement (1 s) — mais c'est un événement, pas une réponse à re-acquitter.

**Cas particulier `ERR` :** côté Python, on **dédoublonne les `ERR` consécutifs identiques** (même code) dans les logs pour ne pas spammer la console. Ce n'est pas une obligation protocolaire, juste un confort UX. La variable `last_err_received` mémorise le dernier code reçu pour cette dédup ; reset quand on sort de la situation (réception d'un `BOOT_START` ou `HELLO`).

### 5.5 Diagramme — cycle complet d'un CMD avec retry

```
RPi                                          ESP32
 |                                             |
 | tx_seq_py = 43                              |  last_cmd_seq_processed = 42
 |                                             |  last_cmd_result = DONE (de la précédente)
 |                                             |
 | <CMD MOVE 2 5|seq=43|crc=...>               |
 | ────────────────────────────────────────>   |  Reçoit, valide format/CRC
 | last_request_seq = 43                       |  43 != 42 → nouvelle commande
 | tx_seq_py = 44                              |  last_cmd_seq_processed = 43
 | (start timeout 15 s)                        |  last_cmd_result = NONE
 |                                             |  → exécute mouvement (durée 4 s)
 |                                             |
 |                                             |  fin exécution
 |                                             |  last_cmd_result = DONE
 |                                             |
 | <DONE|seq=44|ack=43|crc=...>                |
 | <─────── X (DONE perdu en route)            |
 |                                             |
 | (timeout 15 s côté RPi)                     |
 |                                             |
 | <CMD MOVE 2 5|seq=43|crc=...>  (RETRY 1)    |
 | ────────────────────────────────────────>   |  Reçoit, valide
 | (même seq=43, on ne tx_seq_py pas)          |  43 == last_cmd_seq_processed
 |                                             |  last_cmd_result = DONE (≠ NONE)
 |                                             |  → renvoie DONE sans re-exécuter
 |                                             |
 | <DONE|seq=45|ack=43|crc=...>                |
 | <─────────────────────────────────────────  |
 | ack=43 == last_request_seq → match          |
 | last_request_seq = None                     |
 | (requête acquittée, partie continue)        |
```

**Garantie : le pion bouge exactement une fois**, peu importe le nombre de retries. C'est ce qui rend le protocole "safe to retry".

---

## 6. Politique d'erreurs et retransmission

### 6.1 Trame mal formée ou CRC invalide

Cf. §3.6 pour la définition. **Action des deux côtés : rejet silencieux**, pas de NACK envoyé, pas de log d'alerte (compteur stats optionnel pour debug). Le timeout naturel de l'émetteur fait son travail.

### 6.2 Timeouts — récapitulatif

| Timeout | Côté | Valeur | Déclenchement |
|---|---|---|---|
| Émission `HELLO` (période) | ESP32 | 200 ms | tant qu'en `WAITING_RPI` |
| Bascule vers `DEMO` (pas d'`HELLO_ACK`) | ESP32 | 3 s | au boot uniquement (pas de bascule à chaud) |
| Émission `KEEPALIVE` (période) | RPi | 1 s | tant qu'en session active |
| Détection perte UART | ESP32 | 3 s (= 3 KEEPALIVE manqués) | en `CONNECTED`, `BUTTON_INTENT_PENDING`, `EXECUTING` |
| ACK pour `MOVE_REQ`/`WALL_REQ` | ESP32 | 500 ms | en `BUTTON_INTENT_PENDING` |
| Escalade vers `ERROR` (timeouts ACK) | ESP32 | 3 timeouts consécutifs | en `BUTTON_INTENT_PENDING` |
| `DONE` pour CMD | RPi | **15 s** | après envoi d'une `CMD ...` |
| Retry CMD côté RPi | RPi | 2 retries max (3 essais total) | si pas de `DONE` après 15 s |
| Réémission `ERR` (période) | ESP32 | 1 s | tant qu'en `ERROR` |
| Watchdog ESP32 | ESP32 | 5 s | par tâche FreeRTOS (Core 0 et Core 1) |
| Tentatives `CMD_RESET` côté RPi | RPi | 5 s max | sur réception répétée du même `ERR` récupérable |

**Note sur le timeout 15 s :** dimensionné pour couvrir le pire cas légitime d'exécution moteur (mur qui monte avec déplacement XY + push), estimé à 5-10 s. Marge × 1.5. À ré-affiner empiriquement en P11.4 quand on aura mesuré les vraies durées avec la mécanique réelle.

**Indépendance vis-à-vis du watchdog :** le watchdog 5 s surveille les freezes de tâche (durée maximale entre deux yields), pas la durée totale d'une opération. Une tâche `MotionControl` peut prendre 10 s pour un mouvement, tant qu'elle ravitaille le watchdog régulièrement (entre chaque pulse moteur). Le timeout CMD côté RPi (15 s) est donc indépendant du watchdog.

### 6.3 Politique de retransmission par type de trame

| Trame | Retry auto ? | Détails |
|---|---|---|
| `BOOT_START` | non | Best effort, une seule émission |
| `SETUP_DONE` | non | Best effort, une seule émission |
| `HELLO` | implicite | Réémis périodiquement à 200 ms tant que pas d'`HELLO_ACK` |
| `MOVE_REQ` / `WALL_REQ` | non | L'humain reclique (flash orange après 500 ms). Compteur 3 timeouts → `ERROR` |
| `DONE` | non | C'est une réponse. Si perdue, le retry RPi de la CMD déclenchera le renvoi (idempotence) |
| `ERR` | **oui (1 s)** | Réémis périodiquement tant que l'ESP32 est en `ERROR` (best effort, voir §6.5) |
| `HELLO_ACK` | non | Si perdu, l'ESP32 réémettra `HELLO` |
| `KEEPALIVE` | implicite | Émis périodiquement à 1 s |
| `ACK` / `NACK` | non | Si perdu, l'ESP32 timeout sa requête et le joueur recliquera |
| `CMD MOVE` / `CMD WALL` / `CMD HIGHLIGHT` / `CMD SET_TURN` / `CMD GAMEOVER` | **oui** | Retry idempotent (même seq), 2 retries max, timeout 15 s entre essais |
| `CMD_RESET` | conditionnel | Réémis tant que le RPi reçoit `ERR` correspondant (max 5 s) |

### 6.4 Comportement en cas d'échec définitif côté RPi

**Après 3 essais CMD échoués (1 envoi + 2 retries sans `DONE`) :**

1. Log d'erreur structuré : timestamp, type CMD, seq, args, raison ("aucun DONE après 45 s").
2. Levée d'une exception **`UartTimeoutError`** (cf. §9.2 pour la hiérarchie d'exceptions).
3. Affichage console : `"⚠️ ESP32 ne répond plus. Vérifier le câble UART et l'alimentation."`
4. Bascule en mode "partie suspendue" : plus de validation des `MOVE_REQ` (NACK auto), arrêt des KEEPALIVE.
5. Attente d'une intervention humaine (Ctrl+C ou redémarrage manuel).

**Pas de tentative de récupération automatique.** C'est intentionnel : un échec après 3 retries indique un problème qui mérite l'œil humain (câble débranché, ESP32 bricked, alimentation insuffisante, etc.).

### 6.5 Récupération depuis `ERROR`

**Côté ESP32 — entrée en `ERROR` :**

1. **Stop immédiat** de toute activité moteur (désactivation A4988 via pin ENABLE → relâche le couple).
2. Servo en position neutre (signal PWM neutre).
3. LED rouge fixe + clignotement codé selon le code d'erreur (cf. animation dédiée dans `LedAnimator`).
4. Émission d'un `ERR <code>` au RPi, avec `ack=N` si l'erreur survient pendant l'exécution d'une CMD seq=N (sinon sans `ack`).
5. **Réémission de `ERR <code>`** toutes les 1 s tant que l'ESP32 reste en `ERROR` (best effort). Chaque réémission a un seq propre incrémenté ; `ack=` est **présent uniquement sur la première émission** (celle qui répond à la CMD). Les réémissions périodiques sont sans `ack=`.
6. Plus aucun traitement de trame entrante **sauf** `CMD_RESET`. Les `KEEPALIVE` reçus sont silencieusement ignorés.
7. Sortie : sur réception de `CMD_RESET` → `ESP.restart()` (reboot logiciel) → retour à `BOOT`.

**Côté RPi — réception d'un `ERR <code>` :**

1. **Arrêt immédiat des retries CMD en cours** (si une CMD était en vol). Reset `last_request_seq = None`.
2. Log de l'erreur reçue (avec dédup si même code que le précédent — cf. §5.4).
3. Selon le classement (cf. §4.3) :
   - **Erreur récupérable** (`UART_LOST`, `BUTTON_MATRIX`) : envoi automatique d'un `CMD_RESET`. Si le même `ERR` continue d'arriver pendant 5 s malgré les `CMD_RESET` répétés → escalade vers "non récupérable" (l'ESP32 ne sort pas de `ERROR`, problème plus profond).
   - **Erreur non récupérable** (toutes les autres) : levée d'une **`UartHardwareError`** avec le code, log, alerte joueur, partie suspendue.

**Cycle complet de récupération réussie :**

```
ESP32                                        RPi
  |                                            |
  | (en ERROR — moteur foiré pendant CMD #43)  |
  |                                            |
  | <ERR MOTOR_TIMEOUT|seq=99|ack=43|crc=...> |
  | ─────────────────────────────────────>    |
  |                                            | classé "non récupérable"
  |                                            | UartHardwareError("MOTOR_TIMEOUT")
  |                                            | partie suspendue, alerte joueur
```

**Cycle de récupération automatique (erreur récupérable) :**

```
ESP32                                        RPi
  |                                            |
  | (en ERROR — UART_LOST détecté)             |
  |                                            |
  | <ERR UART_LOST|seq=99|crc=...>             |
  | ─────────────────────────────────────>    |
  |                                            | classé "récupérable"
  |                                            | → envoie CMD_RESET
  |                                            |
  |                       <CMD_RESET|seq=N|crc=...>
  |   <───────────────────────────────────────|
  | ESP.restart()                              |
  | ─────────  reboot complet  ─────────       |
  |                                            |
  | <BOOT_START|seq=0|crc=...>                 |
  | ─────────────────────────────────────>    | reset de session côté Python
  | <SETUP_DONE|seq=1|crc=...>                 |
  | ─────────────────────────────────────>    |
  | <HELLO|seq=2|v=1|crc=...>                  |
  | ─────────────────────────────────────>    |
  |                       <HELLO_ACK|seq=0|ack=2|crc=...>
  |   <───────────────────────────────────────|
  | (CONNECTED, partie reprend au tour courant)|
```

### 6.6 Cas particulier : RPi rebooté + ESP32 en `ERROR`

**Scénario problématique :** le RPi crash (exception Python non rattrapée), l'ESP32 détecte `UART_LOST` après 3 s et bascule en `ERROR`, émet `ERR UART_LOST` toutes les secondes. Le RPi est rebooté quelques secondes plus tard. Au démarrage, **le RPi attend un `HELLO`. Mais l'ESP32 en `ERROR` n'émet plus de `HELLO` — il émet `ERR`.** Sans logique spécifique, deadlock.

**Décision :** au démarrage du programme Python, après ouverture du port série :

1. Attente de **n'importe quelle trame ESP32** pendant 3 s.
2. Si **`HELLO` reçu** → handshake normal (envoyer `HELLO_ACK`, vérifier version, passer en session active).
3. Si **`ERR` reçu** mais pas de `HELLO` → l'ESP32 est en `ERROR`. Envoyer automatiquement `CMD_RESET`, attendre le `BOOT_START` qui suivra, puis `HELLO`. Si après 10 s aucun `HELLO` ne vient → erreur "ESP32 muet ou bloqué", alerte joueur.
4. Si **aucune trame du tout** après 3 s → câble probablement débranché, ESP32 muet, alerte humain ("vérifier câble UART et alimentation ESP32").

### 6.7 Garanties offertes

Concrètement, ce que tu peux affirmer en soutenance :

- ✅ **Aucun double mouvement moteur** : garanti par l'idempotence par seq (§5.3).
- ✅ **Pas de partie cassée par une perte de trame ponctuelle** : retry CMD côté RPi pour le sens RPi→ESP32 ; humain reclique pour le sens ESP32→RPi.
- ✅ **Détection de panne ferme** : 3 KEEPALIVE manqués (3 s) ou 3 essais CMD échoués (45 s) → erreur claire et typée.
- ✅ **Pas de comportement silencieusement mauvais** : toute trame anormale est rejetée explicitement, jamais "interprétée à la louche".
- ✅ **Récupération possible sans reboot matériel** dans les cas mineurs : `CMD_RESET` software fait le travail.
- ✅ **Pas de deadlock RPi rebooté + ESP32 en ERROR** : récupération automatique au démarrage Python (§6.6).
- ✅ **Mismatch firmware/Python détecté au boot** : version `v=1` dans `HELLO`, refus immédiat avec message clair en cas de divergence.

**Limites assumées (non couvertes par le protocole, hors scope) :**
- Servo bloqué mécaniquement (pas de feedback de position SG90).
- Mur qui ne monte pas correctement (pas de capteur sur le mur).
- LED grillée (pas de feedback I/O sur WS2812B).
- Ces cas sont gérés par intervention humaine pendant la démo, comme indiqué dans le spec d'architecture §3.

---

## 7. Co-existence debug ↔ protocole

### 7.1 Le problème

L'UART0 ESP32 ↔ RPi est physiquement **la même** que l'UART de debug visible au Serial Monitor (USB du DevKit). Tout `Serial.print()` du firmware part sur ce canal, donc le RPi reçoit aussi les logs de debug. Sans discipline structurelle, deux risques :

- Un `Serial.print("debug")` parasite le parsing protocolaire côté RPi.
- Une trame protocolaire émise par `UartLink` au mauvais moment se mélange avec un log en cours d'écriture par une autre tâche FreeRTOS.

### 7.2 Convention firmware (point unique d'émission)

**Règle 1 — Toute émission série passe par `UartLink`.**

Deux fonctions (et **uniquement** ces deux) sont autorisées à écrire sur Serial dans tout le firmware :

```cpp
namespace UartLink {
  // Émet une trame protocolaire complète, framée et avec CRC, sous mutex.
  void sendFrame(const char* type, const char* args, /* ... seq, ack, v géré en interne ... */);

  // Émet une ligne de log de debug, préfixée [TAG], sous mutex.
  void log(const char* tag, const char* msg);
}
```

Toutes les autres parties du code (`GameController`, `MotionControl`, `LedAnimator`, etc.) appellent **uniquement** `UartLink::log("FSM", "BOOT -> WAITING_RPI")` pour leurs logs — jamais `Serial.print()` directement.

**Règle 2 — Convention de préfixe pour les logs.**

Tag entre crochets en MAJUSCULES, suivi d'un espace, suivi du message :

```
[FSM] BOOT -> WAITING_RPI
[BTN] tick=12345 cols=0x3F
[I2C] write reg=0x00 val=0xFF
[MOT] step X done in 234 ms
```

Aucun log ne commence par `<` (qui est réservé aux trames protocolaires). Aucun log ne contient de retour à la ligne au milieu (un seul `\n` final, ajouté par `UartLink::log`).

**Règle 3 — Revue de code en P8.3.**

Le refactor du firmware en P8.3 inclut une revue exhaustive : `grep -rn 'Serial\.\(print\|write\)'` doit retourner uniquement les appels internes à `UartLink`. Toute autre occurrence est un bug à corriger.

### 7.3 Synchronisation des accès `Serial` sur ESP32

**Le problème détaillé :** Core 1 (`UartLink::sendFrame`) et Core 0 (`MotionControl` qui veut logger) peuvent vouloir écrire sur Serial simultanément. Sans synchronisation, l'OS interrompt Core 1 au milieu d'une trame, Core 0 émet son log, Core 1 reprend. Résultat sur le fil : `<MOVE_REQ 3 4[MOT] pulse step=12|seq=42|crc=A1B2>\n` → trame corrompue (CRC invalide), rejetée par le RPi → bug intermittent reproductible 1 fois sur 50.

**Solution :** un mutex FreeRTOS (`SemaphoreHandle_t`) créé dans `UartLink::init()`, pris pendant toute la durée d'écriture d'une trame ou d'un log, relâché à la fin.

```cpp
// Pseudocode (squelette)
static SemaphoreHandle_t uart_mutex;

void UartLink::init() {
  uart_mutex = xSemaphoreCreateMutex();
}

void UartLink::sendFrame(...) {
  xSemaphoreTake(uart_mutex, portMAX_DELAY);
  // ... écriture atomique de la trame ...
  Serial.print('<');
  Serial.print(type);
  // ... etc ...
  Serial.print('\n');
  xSemaphoreGive(uart_mutex);
}

void UartLink::log(const char* tag, const char* msg) {
  xSemaphoreTake(uart_mutex, portMAX_DELAY);
  Serial.print('[');
  Serial.print(tag);
  Serial.print("] ");
  Serial.println(msg);
  xSemaphoreGive(uart_mutex);
}
```

**Garantie :** une trame protocole ou un log est émis atomiquement, sans entrelacement avec une autre émission.

### 7.4 Convention Python (parsing miroir)

Le module `quoridor_engine/uart_client.py` (à créer en P8.4) lit le port série **ligne par ligne** (séparateur `\n`). Pour chaque ligne reçue :

| Première condition | Action |
|---|---|
| Ligne vide | Ignorée |
| Ligne commence par `<` (en `line[0]`) | Tentative de parsing comme trame protocolaire. Si valide (CRC OK, format OK, version OK) → traitement. Sinon → rejet silencieux (compteur stats). |
| Ligne commence par autre chose | Considérée comme log de debug ESP32. **Optionnellement** affichée en console avec préfixe `[ESP32]` pour visibilité humaine, **jamais** traitée comme protocole. |

**La condition "commence par `<`" est testée sur le premier caractère de la ligne après split sur `\n`.** Si une ligne contient `<` ailleurs (ex : `[FSM] transition from <BOOT>`), c'est sans effet — la ligne entière commence par `[`, donc classée comme debug.

**Garantie structurelle :** peu importe ce qu'un nouveau membre de l'équipe fait dans le firmware, tant qu'il ne préfixe pas son log par `<`, il ne pourra pas casser le protocole. C'est ce qui distingue cette approche d'une convention "humaine" (du genre "n'oublie pas de préfixer tes logs").

### 7.5 Lecture côté Python — détails d'implémentation

**Configuration de pyserial :**
- `serial.Serial(..., timeout=0.1)` — timeout de 100 ms sur `read()` / `readline()` pour ne pas bloquer le thread principal indéfiniment sur une ligne tronquée.
- Lecture dans un **thread dédié** (background) qui poste les lignes dans une `queue.Queue` consommée par le code métier. Évite de coupler le timing du protocole avec le timing du jeu.

**Buffer interne :** si `readline()` retourne une ligne sans `\n` final (timeout atteint avant la fin de la ligne), elle est mise de côté dans un buffer interne et concaténée avec le prochain `read()`. Si le buffer dépasse 80 octets sans `\n` → on jette le buffer (trame anormalement longue, probablement corruption ou bruit).

**Log de debug Python :** activable par variable d'environnement (`UART_DEBUG=1`) pour afficher dans la console toutes les trames reçues et émises avec timestamp. Désactivé par défaut pour ne pas spammer.

### 7.6 Bootloader ESP32 au démarrage

Avant que le firmware démarre, le bootloader ROM ESP32 émet du texte sur l'UART (`rst:0x1`, message ESP-ROM, baud 74880 par défaut, etc.). Ces lignes apparaissent au Serial Monitor au moment du flash ou du reset.

**Aucune ne commence par `<`**, donc côté Python elles sont automatiquement ignorées par la règle structurelle de §7.4. Le seul effet visible : à 115200 bauds, le Serial Monitor peut afficher du charabia pendant les premiers ms (le bootloader émet à 74880). C'est cosmétique, pas un bug.

À mentionner pour qu'on n'aille pas chercher midi à quatorze heures si on voit des lignes étranges en `[ESP32]` au démarrage Python.

---

## 8. Stratégie de tests

### 8.1 Tests unitaires Python (P8.5, faisables sans hardware)

**Cible :** module `quoridor_engine/uart_client.py` (créé en P8.4).

**Méthodologie :**
- **Mocking complet** de `pyserial` via une classe `MockSerial` qui imite l'interface (`read()`, `write()`, `readline()`, `in_waiting`) et stocke en mémoire un buffer bidirectionnel. Aucune dépendance hardware.
- **Horloge injectable** (`MockClock`) pour tester les timeouts en quelques ms au lieu de 15 s. Le module accepte une horloge en paramètre du constructeur ; en production c'est `time.monotonic`, en tests c'est `MockClock` qui avance virtuellement (`clock.advance(15)` → 0 ms réel).
- **Cible de couverture :** ≥ 90 % sur `uart_client.py`. C'est un module sans branches métier complexes, atteignable.
- Outil : `pytest` (déjà utilisé dans le projet, cf. `tests/`). Pas besoin de framework supplémentaire.

**Catégories de tests à écrire :**

| Catégorie | Exemples de tests |
|---|---|
| **Encodage de trame** | `MOVE_REQ` ↔ string ; `CMD MOVE` ↔ string ; CRC calculé sur les vecteurs de référence (§3.5) ; CRC en hexa majuscules sur 4 chars exactement |
| **Décodage de trame** | Trame valide → objet typé ; CRC invalide → rejet ; format invalide → rejet ; ordre incorrect → rejet ; casse incorrecte → rejet |
| **Robustesse parsing** | Trame tronquée → buffered, complétée plus tard → décodée ; ligne sans `<` → classée debug ; ligne `<...>` sans `\n` → buffered jusqu'au `\n` ; bytes ASCII random fuzzed → tous rejetés sans crash |
| **Limite 80 octets** | Trame de 81 octets → rejet ; trame de 80 octets exactement → acceptée si bien formée |
| **Séquencement** | `tx_seq_py` incrémente normalement ; wrap à 256 → 0 ; reset à 0 sur réception `BOOT_START` ; reset sur nouveau `HELLO` en session active |
| **Ack matching** | `ACK ack=42` quand `last_request_seq=42` → match ; `ACK ack=99` → rejet orphelin ; `last_request_seq=None` → rejet |
| **Retry CMD** | Pas de DONE après 15 s (clock mocké) → retry avec **même seq** ; 3 essais sans DONE → `UartTimeoutError` ; DONE entre temps → pas de retry |
| **Réception ERR** | `ERR ack=42` quand CMD seq=42 en vol → annule retry, lève `UartHardwareError` selon classement ; spam d'`ERR` identiques → dédup logs (la 1ère seulement loggée, les suivantes silencieuses) |
| **Récupération récupérable** | Réception `ERR UART_LOST` → envoi `CMD_RESET` auto ; si `ERR` continue 5 s → escalade vers `UartHardwareError` |
| **Versioning** | `HELLO v=1` reçu, attendu v=1 → OK ; `HELLO v=2` reçu, attendu v=1 → `UartVersionError` "incompatibilité firmware" |
| **Co-existence debug** | Lignes `[FSM] xxx` reçues → ignorées sans erreur, accessibles dans le log `[ESP32]` |
| **Cas RPi rebooté + ESP32 ERROR** | Au démarrage, réception d'`ERR` sans `HELLO` → envoi auto `CMD_RESET` puis attente `BOOT_START` → handshake normal |
| **Threading** | Le thread de lecture ne bloque pas le main thread ; `queue.Queue` consommée correctement ; arrêt propre du thread sur `close()` |

### 8.2 Tests d'intégration ESP32 ↔ Python (P8.6, nécessite DevKit)

**Méthodologie :** ESP32 DevKit branché au Mac, firmware Plan 2 flashé, script Python (`tests/integration/test_uart_devkit.py`) qui ouvre le port série et joue des séquences de test contre le vrai firmware.

**Catégories :**

| Catégorie | Exemples |
|---|---|
| **Handshake nominal** | Boot ESP32 → réception de `BOOT_START`, `SETUP_DONE`, `HELLO v=1` ; envoi de `HELLO_ACK` → ESP32 transitionne en `CONNECTED` (vérifier via log `[FSM]`) |
| **Cycle de coup humain** | Injection `BTN 3 4\n` au Serial Monitor → Python reçoit `MOVE_REQ 3 4 seq=N` ; envoi `ACK ack=N` → ESP32 transitionne en `EXECUTING` |
| **Cycle de coup IA** | Envoi de `CMD MOVE 2 5 seq=43` → réception de `DONE ack=43` après ~T ms (T à mesurer) |
| **Idempotence CMD** | Envoi `CMD MOVE 2 5 seq=43`, attente `DONE`. Renvoi de la **même trame** (même seq=43) → vérifier qu'aucun double mouvement ne se déclenche (logs `[MOT]` doivent montrer 1 seule séquence de pulses), réception immédiate d'un `DONE ack=43` |
| **Perte de DONE simulée** | Envoi `CMD MOVE` avec seq=43, intercepter et "manger" le `DONE` côté Python pour simuler une perte. Attendre 15 s. Vérifier que Python retransmet la CMD avec seq=43, et que l'ESP32 répond immédiatement `DONE` sans re-bouger |
| **Perte de KEEPALIVE** | Couper l'envoi de KEEPALIVE côté Python pendant 4 s → vérifier que l'ESP32 entre en `ERROR` avec `ERR UART_LOST`. Reprendre les KEEPALIVE et envoyer `CMD_RESET` → vérifier reboot et nouvelle session |
| **Trame corrompue émise par Python** | Envoyer une trame avec CRC volontairement faux → vérifier qu'ESP32 ignore (compteur stats incrémenté côté ESP32 si exposé via log debug, mais aucune transition d'état) |
| **Trame > 80 octets** | Envoyer une trame de 81 octets côté Python → vérifier rejet silencieux ESP32 (pas de crash) |
| **Mismatch version** | Modifier le code Python pour rejeter `v=1` (simuler attente v=2) → vérifier `UartVersionError` levée, programme s'arrête avec message clair |
| **Stress UART** | Émettre des trames `KEEPALIVE` à 10 Hz pendant 10 s (100 trames) → vérifier 0 trame perdue, 0 trame corrompue détectée des deux côtés |
| **Récupération RPi rebooté** | Tester le scénario §6.6 : forcer ESP32 en `ERROR`, redémarrer le programme Python, vérifier qu'il envoie `CMD_RESET` automatiquement et reprend handshake |

### 8.3 Tests reportés à plus tard (hors P8)

Pour mémoire, ces tests sont prévus mais hors scope strict de P8 :

- **Tests de stress longue durée** : 1 h d'usage continu sans reboot watchdog → couvert par P13.1.
- **Tests de panne hardware réelle** : moteur bloqué physiquement, fin de course déclenché manuellement, MCP23017 débranché → couvert par P13.3 / P13.4.
- **Tests E2E partie complète** : 5+ parties bout-en-bout via UART → couvert par P9.5 et P13.1.
- **Tests sur PCB v2** (vs DevKit) : à faire en P10 quand la PCB sera reçue.

### 8.4 Critères de fin pour P8

**P8 est considéré comme terminé quand toutes ces conditions sont vraies :**

- ✅ Tous les tests unitaires Python (§8.1) passent à 100 %, couverture ≥ 90 % sur `uart_client.py`.
- ✅ Tous les tests d'intégration (§8.2) passent sur le DevKit (lundi+, P8.6).
- ✅ Le firmware Plan 2 compile sans warning sur `pio run` (cible `esp32dev`).
- ✅ Les vecteurs de référence CRC (§3.5) sont calculés, figés dans le spec, et vérifiés des deux côtés.
- ✅ Le module Python `uart_client.py` s'utilise depuis `main.py` (mode "plateau physique" ébauché pour P9).
- ✅ Documentation mise à jour : [`06_protocole_uart.md`](../../06_protocole_uart.md) réécrit avec le protocole final ; ce design doc archivé dans `docs/superpowers/specs/`.
- ✅ Aucun `Serial.print()` direct ailleurs dans le firmware (revue P8.3).
- ✅ Mutex Serial actif sur ESP32 (vérifié par test de stress §8.2).

---

## 9. Implémentation — structure proposée

Cette section donne une vue d'ensemble de la structure de code attendue, **sans entrer dans le détail des fonctions** (ce sera le rôle de specs ultérieurs ou directement de la phase d'implémentation).

### 9.1 Côté ESP32 — refactor de `UartLink` (cible P8.3)

**Fichiers modifiés :**
- `firmware/src/UartLink.h` — nouvelle interface
- `firmware/src/UartLink.cpp` — implémentation framing + CRC + mutex + dédup
- `firmware/src/GameController.cpp` — adaptation des appels `UartLink::sendLine` → `sendFrame` ou `log`
- Tous les autres modules — remplacement des `Serial.print` directs par `UartLink::log("TAG", ...)`

**Squelette de `UartLink.h` (proposé, à raffiner en P8.3) :**

```cpp
#ifndef UART_LINK_H
#define UART_LINK_H

#include <Arduino.h>

namespace UartLink {

  // Initialisation : crée le mutex, initialise les compteurs.
  void init();

  // Tick périodique (appelé depuis loop()) : assemble les caractères entrants en lignes,
  // gère la dédup CMD, dispatche les trames décodées vers GameController.
  void poll();

  // Émet une trame protocolaire complète. Gère framing, seq, CRC, mutex.
  // type : "MOVE_REQ", "DONE", etc.
  // args : "3 4" ou "" si pas d'args
  // ack  : -1 si pas d'ack, sinon valeur
  void sendFrame(const char* type, const char* args, int ack = -1);

  // Émet un log de debug, préfixé [tag], sous mutex.
  void log(const char* tag, const char* msg);

  // Tente de récupérer la prochaine trame protocolaire décodée et validée.
  // Retourne true si une trame est disponible, remplit les paramètres de sortie.
  bool tryGetFrame(char* type, char* args, int* seq, int* ack);

  // Statistiques debug (optionnel)
  uint32_t getRejectedCount();
}

#endif
```

**Calcul CRC-16 CCITT-FALSE — squelette ~15 lignes :**

```cpp
uint16_t crc16_ccitt(const uint8_t* data, size_t len) {
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
```

(Alternative : utiliser la lib `FastCRC` si elle est ajoutée à `platformio.ini`.)

### 9.2 Côté Python — nouveau module `uart_client` (cible P8.4)

**Fichier créé :** `quoridor_engine/uart_client.py` (placement cohérent avec `core.py` et `ai.py`).

**Hiérarchie d'exceptions :**

```python
class UartError(Exception):
    """Base pour toutes les erreurs UART."""

class UartTimeoutError(UartError):
    """Levée après 3 essais CMD sans DONE."""

class UartProtocolError(UartError):
    """Levée si le pic de trames mal formées dépasse un seuil (anormal)."""

class UartVersionError(UartError):
    """Levée si HELLO v=K reçu ne correspond pas à la version Python attendue."""

class UartHardwareError(UartError):
    """Levée à la réception d'un ERR non-récupérable."""
    code: str  # MOTOR_TIMEOUT, HOMING_FAILED, etc.
```

**Squelette de l'API publique (à raffiner en P8.4) :**

```python
class UartClient:
    def __init__(self, port: str, clock=None, expected_version: int = 1):
        """
        port: ex "/dev/cu.SLAB_USBtoUART"
        clock: callable retournant un float monotone (default: time.monotonic) ; injectable pour tests
        expected_version: version protocole attendue (default 1)
        """

    def connect(self) -> None:
        """Ouvre le port, fait le handshake (gère le cas RPi rebooté + ESP32 ERROR)."""

    def close(self) -> None:
        """Arrête le thread de lecture, ferme le port proprement."""

    def send_keepalive(self) -> None:
        """Émet un KEEPALIVE. À appeler périodiquement (1 s) depuis le main loop."""

    def send_cmd(self, cmd_type: str, args: str) -> None:
        """Émet une CMD avec retry idempotent (15 s × 2 retries). Bloque jusqu'à DONE ou exception."""

    def send_ack(self, request_seq: int) -> None:
        """Émet un ACK pour une requête reçue."""

    def send_nack(self, request_seq: int, reason: str) -> None:
        """Émet un NACK avec raison."""

    def receive(self, timeout: float = None) -> Frame | None:
        """Récupère la prochaine intention reçue (MOVE_REQ, WALL_REQ, ERR…) ou None si timeout."""
```

**Threading :** un thread daemon dédié à la lecture du port série, qui pose les frames décodées dans une `queue.Queue` consommée par `receive()`. L'écriture (envoi) est synchronisée par un mutex côté Python (les `send_*` peuvent être appelés depuis n'importe quel thread).

---

## 10. Coupure nette avec Plan 1

Le firmware Plan 2 ne supporte plus le protocole stub du Plan 1. **Pas de mode rétrocompat.**

**Trames Plan 1 supprimées :**
- `HELLO`, `HELLO_ACK`, `KEEPALIVE`, `BTN x y`, `MOVE_REQ x y`, `ACK`, `NACK`, `CMD MOVE x y`, `RESET` au format texte simple — toutes remplacées par leur équivalent framé `<...>\n`.
- `UartLink::sendLine()` et `UartLink::tryReadLine()` (interface Plan 1) — remplacées par `sendFrame()` / `log()` / `tryGetFrame()`.

**Exception conservée :** le format simplifié `BTN <row> <col>\n` (sans framing) reste accepté **en réception ESP32 uniquement**, comme documenté en §4.6 (mode injection test au Serial Monitor). C'est la seule trame "non framée" qui survit.

**Vérification du refactor (P8.3) :**
- `grep -rn 'sendLine\|tryReadLine' firmware/src/` → doit retourner 0 occurrence.
- `grep -rn 'Serial\.\(print\|write\)' firmware/src/` → doit retourner uniquement les appels internes à `UartLink.cpp`.

---

## 11. Hors scope (specs ultérieurs)

Ce document fige le protocole. Les sujets suivants seront traités séparément :

- **Implémentation détaillée par module ESP32** : le squelette donné au §9.1 est volontairement minimal. La conception fine de `UartLink::poll()` (state machine de parsing, gestion du buffer, dispatch vers `GameController`) sera affinée en P8.3.
- **Implémentation détaillée du module Python `uart_client`** : la conception fine du threading, de la queue, des timeouts par méthode, sera affinée en P8.4.
- **Adaptation de `main.py`** : le mode "plateau physique" qui utilisera `uart_client` est l'objet de P9.1–P9.3, spec à part.
- **Tests E2E partie complète** : couverts par P9.5 et P13.1, pas par P8.
- **Calibration des vrais timings moteur** : le timeout 15 s sur `CMD` est une estimation. Sa valeur définitive sera figée en P11.4 quand la mécanique réelle sera mesurée.
- **Gestion fine des animations LED pendant les transitions UART** (`PENDING_FLASH`, `EXECUTING_SPINNER`, etc.) : couvert par le spec dédié à `LedAnimator` quand on l'écrira.
- **Comportement du protocole sur la PCB v2** vs DevKit : à valider en P10 (réception PCB prévue 2026-05-10).

---

**Fin du spec.**
