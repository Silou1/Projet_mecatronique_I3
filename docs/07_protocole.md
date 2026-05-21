# 07 — Protocole d'application Mac ↔ ESP32

## Vue d'ensemble

Le protocole est **texte ligne par ligne**. Une commande = une ligne terminée par `\n`.
Une réponse = une ligne terminée par `\n`. Encodage : UTF-8.

| Paramètre        | Valeur                                      |
|------------------|---------------------------------------------|
| Liaison USB      | 115200 baud, 8N1                            |
| Liaison Wi-Fi    | TCP sur `192.168.4.1:3333` (AP `Quoridor-ESP32`) |
| Fin de ligne     | `\n` (LF)                                   |
| Encodage         | UTF-8                                       |
| Framing          | Aucun (texte brut)                          |
| Checksum         | Aucun                                       |
| Séquence / ack   | Aucun                                       |

Le canal (USB local ou Wi-Fi local en mode AP) est supposé **fiable et exclusif** :
pas de détection d'erreur applicative au niveau transport.

Le protocole est **identique mot pour mot** sur les deux canaux. Côté Python,
l'abstraction `Transport` (`SerialTransport`, `WiFiTransport`, `NullTransport`) expose
la même API `write_line` / `read_line`. Côté firmware, la fonction `traiter()` accepte
un `Stream*` (polymorphisme `HardwareSerial` / `WiFiClient`), donc une seule logique de
dispatch sert les deux canaux.

---

## Commandes envoyées par le Mac

### `PING`

Handshake initial. Envoyé au démarrage pour vérifier que l'ESP32 est présent et opérationnel.

```
PING
```

L'ESP32 répond `PONG`.

La webapp tente le handshake à l'ouverture du port série (timeout 5 s, polling toutes les 0,5 s).
Si aucun `PONG` n'est reçu, le bridge reste désactivé et la webapp passe en mode autonome.

---

### `WALL <H|V> <row> <col>`

Lève un mur Quoridor sur le plateau physique.

```
WALL <H|V> <row> <col>
```

| Champ       | Type   | Valeurs      | Description                              |
|-------------|--------|--------------|------------------------------------------|
| `H` ou `V`  | char   | `H` ou `V`   | Orientation du mur                       |
| `row`       | entier | `[0..4]`     | Indice ligne dans la grille Quoridor     |
| `col`       | entier | `[0..4]`     | Indice colonne dans la grille Quoridor   |

Exemples :

```
WALL H 2 3
WALL V 0 0
WALL H 4 4
```

> **Note — inversion d'orientation** : la couche Python (`webapp/service.py`,
> méthode `_forward_to_plateau_unlocked`) applique une inversion `H ↔ V` avant
> d'envoyer la commande, pour compenser la convention d'orientation inverse entre
> l'engine Quoridor et les matrices physiques du firmware. Le firmware reçoit donc
> l'orientation **déjà corrigée** ; les exemples ci-dessus sont ceux effectivement
> envoyés sur le fil.

---

### `HOME`

Déclenche un homing complet (retour aux fins de course, remise à zéro de la position).
Envoyé par la webapp en début de partie pour garantir un état machine cohérent.

```
HOME
```

Le firmware ne renvoie pas de ligne de réponse structurée pour `HOME` ;
seuls des logs verbeux sont émis (filtrés côté Python, voir §&nbsp;Logs verbeux).

---

## Réponses de l'ESP32

### `PONG`

Réponse à `PING`. Indique que l'ESP32 est prêt.

```
PONG
```

---

### `WALL OK <H|V> <row> <col> raised=<n>`

Levée réussie.

```
WALL OK H 2 3 raised=2
```

`n` = nombre de cases physiques effectivement manipulées par le servo (0, 1 ou 2).

| Valeur de `n` | Signification                                                                 |
|---------------|-------------------------------------------------------------------------------|
| `2`           | Les deux positions du mur sont mesurées et ont été levées.                    |
| `1`           | Une seule position est mesurée (l'autre est `_NA`).                           |
| `0`           | Aucune position mesurée ; la commande est valide mais rien n'a bougé.         |

---

### `WALL ERR <raison>`

Échec de la commande `WALL`. La raison est une chaîne lisible.

```
WALL ERR borne : row=99 col=0 hors [0..4]
```

| Raison                                    | Cause                                               |
|-------------------------------------------|-----------------------------------------------------|
| `orientation : H ou V attendu`            | Premier argument ni `H` ni `V`                      |
| `borne : row=X col=Y hors [0..4]`         | `row` ou `col` hors de `[0..4]`                     |
| `syntaxe : WALL <H\|V> <row> <col>`       | Commande mal formée (argument(s) manquant(s))       |

---

## Comportement firmware

Le firmware (`bringup_l298n_complet.cpp`) lit les lignes dans la boucle principale et
les dispatche dans la fonction `traiter()`. Pour la commande `WALL` (lignes 736–762) :

1. La chaîne reçue est convertie en majuscules et trimée.
2. Validation de l'orientation (`H` ou `V`) et des bornes `[0..4]`.
3. Appel de `wall_lever(orientation, row, col)` (lignes 618–632).

Dans `wall_lever` :

- **Mur horizontal (`H`)** : calcule `j = 4 - row`, puis tente de lever les positions
  physiques `(col, j)` et `(col+1, j)` via `position_mur_h()`.
- **Mur vertical (`V`)** : calcule `i = col`, puis tente de lever les positions
  physiques `(i, 5-row)` et `(i, 4-row)` via `position_mur_v()`.

Pour chaque position mesurée (non `_NA`) :

1. `GOTO` vers les coordonnées en pas.
2. Servo à 0° (`LEVER`) + délai 400 ms.
3. Servo à 180° (`BAISSER`) + délai 400 ms.

La fonction retourne `raised` (0, 1 ou 2), inclus dans la réponse `WALL OK`.

Les 18 positions validées au 2026-05-20 sont encodées dans les matrices `MURS_H` / `MURS_V`
du sketch. Les 42 autres positions sont marquées `_NA` et sautées sans erreur.

---

## Idempotence et garanties

- **Pas de déduplication** : si une commande `WALL` est envoyée deux fois pour la même
  position, le firmware lèvera deux fois (ou tentera de le faire).
- **Côté Mac** : envoyer la commande, attendre la ligne de réponse (timeout recommandé :
  10 secondes, pour couvrir les déplacements CoreXY les plus longs).
- **Phase démo** : ne pas faire de retry automatique en cas de timeout ; afficher une
  erreur côté UI et laisser le joueur décider. Le bridge se désactive (`available = False`)
  à la première erreur de transport ; les forwards suivants sont des no-ops silencieux.

---

## Exemple de session

```
> PING
< PONG
> HOME
  (logs verbeux filtrés)
> WALL H 2 3
< WALL OK H 2 3 raised=2
> WALL V 0 0
< WALL OK V 0 0 raised=1
> WALL H 1 1
< WALL OK H 1 1 raised=0
> WALL H 99 0
< WALL ERR borne : row=99 col=0 hors [0..4]
> WALL X 2 3
< WALL ERR orientation : H ou V attendu
> WALL H 2
< WALL ERR syntaxe : WALL <H|V> <row> <col>
```

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

```
> LED 3 0 0 0          ← éteindre l'ancienne position J1
< OK
> LED 8 0 0 255        ← allumer la nouvelle position J1 (bleu)
< OK
> LED 7 0 64 64        ← case atteignable (cyan dim, P1 bonus)
< OK
> LEDSHOW              ← push atomique
< OK
```

---

## Logs verbeux du firmware

En plus des réponses structurées, le firmware émet des messages de debug sur le même
canal série. Exemples :

```
=== Integration L298N : CoreXY + capteurs + servo ===
HOME OK. Origine (0, 0) etablie.
GOTO (102, 35)  dx=102 dy=35
done
servo 0 deg
servo 180 deg
```

La couche Python (`webapp/plateau.py`) lit les lignes ; les logs verbeux qui
n'appartiennent pas au protocole sont ignorés au niveau du heartbeat (qui attend
exactement `PONG`).

---

## Transport Wi-Fi (phase 5, implémenté)

Le protocole texte est strictement identique au transport USB. Seul le canal change :

- **Côté firmware** : `WiFi.softAP("Quoridor-ESP32", "quoridor2026")` au boot, puis
  `WiFiServer` sur port `3333`. Politique "dernier client gagne" + watchdog 30 s
  pour libérer les sockets fantômes.
- **Côté Mac** : `WiFiTransport` (TCP brut, buffer interne pour lignes coupées entre
  chunks). `PlateauBridge` ajoute heartbeat applicatif (`PING` toutes les 5 s,
  détection coupure après 2 PONG ratés), reconnexion auto (10 s), et lock TX pour
  sérialiser les commandes concurrentes.

Test bout-en-bout validé (cf. [`08_tests.md`](08_tests.md) — tests `devkit_wifi`) :
PING/PONG, politique dernier client, coexistence USB + Wi-Fi simultanée.
