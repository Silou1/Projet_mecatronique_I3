# Décisions et pivots du projet

Registre chronologique inversé (du plus récent au plus ancien) des décisions
structurantes prises au cours du projet : abandons, pivots d'architecture,
choix techniques majeurs. Chaque entrée explique le **contexte**, la
**décision**, les **raisons** et l'**impact**.

L'objectif de ce document est double :

- **Pédagogique** : montrer la démarche d'ingénierie, les essais et les
  pivots argumentés. Documenter un abandon bien justifié est un atout du
  rapport, pas un aveu de faiblesse.
- **Pratique** : éviter qu'un membre de l'équipe ou un futur lecteur ne
  ressuscite une approche déjà étudiée et écartée.

---

## 2026-05-22 — Retrait du toggle « Mode plateau » de la webapp

### Contexte

Depuis la mise en place du transport ESP32 (Wi-Fi + USB), la page d'accueil
de la webapp exposait un toggle « Plateau physique » que le joueur devait
activer manuellement pour que les murs posés dans la webapp soient miroités
sur le plateau (commande `WALL` au firmware). Le toggle était grisé tant que
le transport n'était pas détecté ; sinon, le joueur devait penser à l'activer.

### Décision

**Suppression du toggle et de la notion `plateau_mode` dans l'API.** Le
forward physique des coups au plateau est désormais **automatique** :
chaque pose de mur déclenche un `WALL` ssi `_plateau.available == True` au
moment du forward.

### Raisons

1. **UX simplifiée.** En pratique, le seul cas où on veut explicitement
   désactiver le plateau alors qu'il est joignable est marginal (debug
   webapp pur). Pour ce cas, la variable d'env `QUORIDOR_TRANSPORT=none`
   couvre déjà.
2. **Robustesse aux blips de canal.** L'ancienne logique figeait
   `plateau_mode` à la valeur du toggle au moment du `new_game`. Si le
   canal était momentanément perdu à cet instant (PING raté + reconnect
   en cours), la partie restait en mode app pure même après retour du
   canal. La nouvelle logique évalue la disponibilité **à chaque coup**,
   donc un blip momentané n'affecte qu'éventuellement un mur, pas toute
   la partie.
3. **Code plus simple.** Suppression d'un champ d'état (`_plateau_mode`),
   d'un paramètre de `new_game`, d'un champ du `NewGamePayload` Pydantic,
   et de tout le câblage UI (toggle HTML + CSS + listener JS).

### Impact

- **Schéma API** : `NewGamePayload` perd le champ `plateau_mode`. Pydantic v2
  ignore les champs extra par défaut, donc les anciens clients qui envoient
  encore `plateau_mode` ne sont pas cassés (champ silencieusement ignoré).
- **Frontend** : `index.html` perd le bloc `.toggle-row` ; `app.js` perd
  l'event listener `#plateau-toggle` et la fonction `renderPlateauToggle()` ;
  `style.css` perd les règles `.toggle*` et `.hint`.
- **Backend** : `QuoridorService._plateau_mode` retiré, toutes les
  occurrences remplacées par `self._plateau.available` (évaluation
  dynamique). `to_dict()` retourne désormais `mode_active == available`.
- **Tests** : 253 tests unitaires passent toujours après simplification
  (paramètre `plateau_mode` retiré des appels de test).
- **Démo validée** : partie IA vs IA difficulté facile, 37 tours, 10 murs
  forwardés bout-en-bout, sans crash ni perte de transport.

### Liens

- Commit (à venir, cette session).
- Code modifié : [`webapp/service.py`](../webapp/service.py),
  [`webapp/server.py`](../webapp/server.py),
  [`webapp/schemas.py`](../webapp/schemas.py),
  [`webapp/static/index.html`](../webapp/static/index.html),
  [`webapp/static/app.js`](../webapp/static/app.js),
  [`webapp/static/style.css`](../webapp/static/style.css).

---

## 2026-05-21 — Abandon du système de boutons physiques (matrice 6×6)

### Contexte

Le projet prévoyait initialement un plateau **autonome** où le joueur
interagit directement avec une matrice 6×6 de boutons (un par case) intégrée
au plateau physique. Un bouton dédié devait basculer entre « mode pion »
et « mode mur ». Les LEDs WS2812B servaient de retour visuel (case
sélectionnée, coups légaux, etc.). Voir l'ancienne `note_de_projet.md` et
les flowcharts archivés pour le détail de cette vision initiale.

Un brainstorming complet (FSM B séquentielle, anti-ghosting matrice sans
diodes, fenêtre temporelle 500 ms, debounce 3 scans, anti-cascade
`RELEASING`) avait été conduit le 2026-05-19 et figeait l'UX et le firmware
à venir (cf. `firmware/archive_plan1_pcb_v2/` pour le code prototypé).

### Décision

**Abandon définitif du système de boutons physiques.** Le plateau n'est
plus une interface d'entrée : c'est un **miroir physique** des coups joués
sur la webapp. Toute l'interaction joueur passe désormais par la webapp
(navigateur sur smartphone ou ordinateur).

Le plateau garde deux rôles : (1) affichage des coups légaux, position
des pions et déplacements via la strip LED WS2812B (36 LEDs), (2) levée
mécanique des murs via le chariot CoreXY + servo.

### Raisons

1. **Matériel défaillant** : la matrice de boutons assemblée sur breadboard
   n'a jamais donné de scans fiables (rebonds chaotiques, ghosting
   reproductible même avec 2 appuis). Le passage à des switches mécaniques
   propres demandait un PCB dédié, exclu après l'abandon de la PCB v2
   (cf. décision 2026-05-19).
2. **Temps disponible** : démo finale le 2026-05-22. Pas la marge pour
   débugguer une matrice instable en parallèle du bring-up CoreXY + servo
   + Wi-Fi.
3. **Cohérence avec le pivot Mac + Wi-Fi** (cf. décision 2026-05-20) :
   l'interface webapp est déjà l'interface principale du projet depuis le
   pivot. Les boutons faisaient doublon avec elle, sans réelle valeur
   ajoutée tant que la webapp est disponible.

### Impact

- **Libère plusieurs GPIO ESP32** qui auraient servi à la matrice (12 fils
  pour scan 6 lignes × 6 colonnes) et à l'I²C de l'expander envisagé.
  Ces GPIO sont à nouveau disponibles pour évolutions futures (cf.
  [`hardware/pinout.md`](hardware/pinout.md)).
- **Simplifie le firmware** : pas de FSM de scan boutons, pas de gestion
  d'anti-ghosting, pas de fenêtre temporelle. Le sketch
  [`firmware/src/bringup_l298n_complet.cpp`](../firmware/src/bringup_l298n_complet.cpp)
  reste un dispatch de commandes texte (Serial + Wi-Fi).
- **Simplifie la documentation** : les anciens flowcharts décrivant le
  flux « bouton appui → MOVE_REQ → ACK » sont archivés sous
  [`flowcharts/archive/pre-2026-05-20/`](flowcharts/archive/pre-2026-05-20/).
- **Sous-système LEDs préservé** : la strip WS2812B 36 LEDs et son
  protocole (cf. spec
  [`superpowers/specs/2026-05-21-leds-design.md`](superpowers/specs/2026-05-21-leds-design.md))
  restent en place. Les LEDs gardent leur rôle d'affichage côté plateau.

### Liens

- [Brainstorming UX boutons (2026-05-19)](../firmware/archive_plan1_pcb_v2/) — code prototypé en référence
- [Spec LEDs](superpowers/specs/2026-05-21-leds-design.md) — sous-système conservé

---

## 2026-05-20 — Pivot architecture : Raspberry Pi → Mac, UART CRC-16 → texte simple

### Contexte

L'architecture initiale faisait tourner le moteur de jeu et l'IA sur une
**Raspberry Pi 3/4**, reliée à l'ESP32 via **UART** à 115200 bauds, avec
un protocole texte propriétaire **Plan 2** (trames `<TYPE args|seq=N|crc=XXXX>\n`,
CRC-16 CCITT-FALSE, séquencement anti-doublon, handshake HELLO/HELLO_ACK,
codes NACK typés). Le frontend webapp tournait sur la RPi via FastAPI.

L'objectif initial était de produire un système autonome embarqué dans le
plateau (RPi + ESP32 internes, alimentation locale, écran ou bornier),
indépendant d'un ordinateur externe.

### Décision

**Le moteur Python et la webapp tournent désormais sur le Mac de
l'utilisateur.** L'ESP32 garde son rôle d'actionneur (CoreXY + servo +
LEDs). La communication entre Mac et ESP32 utilise deux transports
interchangeables :

- **USB-série** (mode développement) : câble USB-C entre Mac et ESP32
- **Wi-Fi mode AP** (mode démo) : l'ESP32 héberge un réseau
  `Quoridor-ESP32` (WPA2, IP `192.168.4.1`, TCP port 3333) auquel le Mac
  se connecte ; aucun accès Internet requis pour la démo

Le **protocole texte simple** (`PING`/`PONG`, `WALL <H|V> <r> <c>`, `OK`/`ERR`)
remplace l'ancien Plan 2 avec CRC-16. Il est **identique** sur USB et Wi-Fi.

### Raisons

1. **Souplesse de développement** : Python natif sur Mac, debug Claude
   Code, pytest, hot-reload. Pas de mise au point d'un système embarqué
   intermédiaire (image RPi, alimentation, headless).
2. **Performance largement suffisante** pour l'IA Minimax sur un plateau
   6×6 (le Mac surpasse une RPi 3/4 d'un ordre de grandeur).
3. **Ajustements de dernière minute** facilités à J-2 d'une démo.
4. **Le protocole CRC-16 Plan 2 était sur-dimensionné** pour le besoin :
   l'USB-série local et le Wi-Fi local n'ont pas les contraintes EMI d'un
   bus longue distance. Un protocole texte simple est plus debuggable
   (lisible directement au moniteur série), plus évolutif (ajout de
   commandes sans recompilation) et identique sur les deux transports.

### Impact

- **Suppression des fichiers RPi-side** : `quoridor_engine/uart_client.py`,
  `quoridor_engine/game_session.py`. Remplacés par
  [`webapp/transport.py`](../webapp/transport.py) (3 implémentations
  `SerialTransport`, `WiFiTransport`, `NullTransport` + factory pilotée
  par env var `QUORIDOR_TRANSPORT`) et
  [`webapp/plateau.py`](../webapp/plateau.py) (`PlateauBridge` :
  heartbeat, lock TX, reconnexion auto, bascule à chaud).
- **Pinout ESP32 inchangé** côté moteurs, capteurs et servo. Pin GPIO 15
  réutilisé pour la strip LED WS2812B.
- **Sketch ESP32 refactoré** : `traiter(cmd, Stream*)` sert maintenant
  les deux canaux (Serial et WiFiClient) avec une seule fonction de
  dispatch.
- **Outils ajoutés** : [`tools/wifi_switch.py`](../tools/wifi_switch.py)
  automatise la bascule réseau côté Mac via `networksetup` (macOS).
- **Documentation des anciens flux UART** archivée dans
  [`flowcharts/archive/pre-2026-05-20/`](flowcharts/archive/pre-2026-05-20/).

### Liens

- [02_architecture.md](02_architecture.md) — architecture actuelle
- [07_protocole.md](07_protocole.md) — protocole actuel
- Postmortem PCB v2 (décision 2026-05-19) — élément déclencheur connexe

---

## 2026-05-19 — Abandon de la PCB v2 → retour breadboard

### Contexte

Une **PCB v2** (Printed Circuit Board) avait été conçue (EasyEDA) et
commandée le 2026-04-28 pour porter l'électronique du plateau :
2× L298N, ESP32, matrice boutons, alimentation 12 V, distribution LEDs.
Objectif : passer d'un prototype breadboard à un assemblage propre,
fiable, intégrable dans le plateau final.

### Décision

**Abandon de la PCB v2.** Retour au prototype breadboard pour la suite
du projet (et donc pour la démo).

### Raisons

Détaillées dans le postmortem
[`hardware/archive/pcb-v2-2026-04-28-ABANDONNEE/POSTMORTEM.md`](../hardware/archive/pcb-v2-2026-04-28-ABANDONNEE/POSTMORTEM.md) :
erreurs de routage, pistes incorrectes pour le courant moteurs,
incohérences entre symboles et empreintes, problèmes d'alimentation
12 V → 5 V, temps de refonte + relivraison incompatible avec le
calendrier ICAM.

### Impact

- **Cascade** : le retour breadboard fragilise l'idée d'un plateau
  autonome embarqué → contribue au pivot 2026-05-20 (Mac comme cerveau).
- **Et au pivot 2026-05-21** (abandon boutons) : sans PCB dédiée, la
  matrice de boutons restait sur breadboard instable.
- **Toutes les specs hardware antérieures** (pinout PCB, schématique,
  bill of materials) sont déclassées. Source de vérité unique pour le
  pinout courant : [`hardware/pinout.md`](hardware/pinout.md) +
  commentaires en tête de
  [`firmware/src/bringup_l298n_complet.cpp`](../firmware/src/bringup_l298n_complet.cpp).
- Code firmware prototypé pour la PCB v2 archivé dans
  [`firmware/archive_plan1_pcb_v2/`](../firmware/archive_plan1_pcb_v2/).

### Liens

- [Postmortem PCB v2](../hardware/archive/pcb-v2-2026-04-28-ABANDONNEE/POSTMORTEM.md)
- [Audit PCB v2](../hardware/archive/pcb-v2-2026-04-28-ABANDONNEE/AUDIT_PCB_V2.md)
