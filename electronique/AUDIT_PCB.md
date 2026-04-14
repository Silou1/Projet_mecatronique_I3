# Audit complet du PCB -- Quoridor Interactif

> **Date de l'audit** : 2026-04-14 (mis a jour 2026-04-14)
> **PCB audite** : `Schematic_mecatronique_2026-03-31` (EasyEDA, par jeanrdc)
> **Sources** : netlist `Sheet_1_2026-03-31.net`, schema PDF, layout PCB PDF, BOM, pinout Freenove
>
> **IMPORTANT** : Le module reel est un **ESP32-WROOM** (pas WROVER comme indique sur le
> schema). Le schema EasyEDA a importe le mauvais composant. Consequence : GPIO16 et GPIO17
> sont **disponibles** (pas de PSRAM). Voir issue #15.

---

## Synthese des anomalies

| # | Severite | Composant | Probleme | Impact |
|---|----------|-----------|----------|--------|
| 1 | **CRITIQUE** | GPIO34 (LEDs) | Pin input-only, ne peut pas emettre de signal | LEDs inutilisables |
| 2 | **CRITIQUE** | GPIO35 (Servo) | Pin input-only, ne peut pas generer de PWM | Servo inutilisable |
| 3 | **CRITIQUE** | Net "+5" vs "5V" | Deux noms de net differents = non connectes | Alimentation 5V potentiellement coupee |
| 4 | **SERIEUX** | GPIO0 (Col 3) | Strapping pin : LOW au boot = mode download | ESP32 ne boot pas si bouton appuye |
| 5 | **SERIEUX** | GPIO2 (Col 2) | Strapping pin : comportement special au boot | Risque de boot instable |
| 6 | **SERIEUX** | GPIO12 (Lig 2) | Strapping pin : HIGH au boot = flash 1.8V | WROOM a besoin de 3.3V, crash possible |
| 7 | **MODERE** | GPIO15 (Col 1) | Strapping pin : affecte les logs au boot | Messages parasites sur UART au demarrage |
| 8 | **MODERE** | Matrice boutons | Aucune resistance pull-up/pull-down | Lectures flottantes, faux positifs |
| 9 | **MODERE** | Moteurs (I2C) | Signaux STEP via MCP23017 (bus I2C) | Latence, vitesse moteur limitee |
| 10 | **MODERE** | Servo SG90 | Partage le rail 5V avec logique | Pics de courant = bruit sur MCP23017/A4988 |
| 11 | **MODERE** | A4988 ENA | Pin ENABLE non connecte (flottant) | Moteurs toujours alimentes = chaleur |
| 12 | **RESOLU** | ~~UART TX/RX~~ | ~~Partage avec USB debug (UART0)~~ | Resolu : UART2 sur GPIO16/17 (WROOM) |
| 13 | **MINEUR** | REFERENCE_PCB.md | Port A/B du MCP23017 inverses | Erreur de doc = bugs software potentiels |
| 14 | **MINEUR** | Condensateurs | Un seul 10uF sur +12V, rien sur 5V | Decouplage insuffisant |
| 15 | **MINEUR** | Schema EasyEDA | Mauvais module (WROVER au lieu de WROOM) | Doc incorrecte, GPIO16/17 non documentes |

---

## CRITIQUE (P0) -- Le PCB ne fonctionne pas

### 1. GPIO34 pour les LEDs -- INPUT ONLY

**Constat** : Sur le schema, le signal `LED` est connecte a U1 pin 5 = `IO34`.

**Probleme** : Sur l'ESP32, GPIO34 fait partie du bloc ADC1 "input-only" (GPIOs 34, 35, 36, 39). Ces pins :
- N'ont **pas** de driver de sortie (pas de transistor push-pull/open-drain)
- Ne peuvent **pas** etre configures en `OUTPUT`
- Ne peuvent **pas** generer de signal digital (NeoPixel WS2812B, APA102, etc.)
- Ne supportent **pas** le PWM via LEDC

**Consequence** : Impossible de piloter des LEDs depuis IO34. Le `digitalWrite()`, `analogWrite()`, ou toute librairie NeoPixel echouera silencieusement ou produira un signal nul.

**Verification dans la netlist** :
```
(LED
H1-4
U1-5)        ← U1 pin 5 = IO34 = input-only
```

---

### 2. GPIO35 pour le Servo SG90 -- INPUT ONLY

**Constat** : Le signal `SERVOMOT` est connecte a U1 pin 6 = `IO35`.

**Probleme** : Meme cause que le #1. GPIO35 est input-only :
- Ne peut **pas** generer de signal PWM (50Hz, largeur 1-2ms pour servo)
- La librairie `ESP32Servo` ou `ledcWrite()` ne fonctionnera **pas**
- Aucun signal ne sortira sur la piste PCB vers le servo

**Verification dans la netlist** :
```
(SERVOMOT
U1-6
U2-2)        ← U1 pin 6 = IO35 = input-only
```

---

### 3. Nets "+5" et "5V" non connectees -- Alimentation coupee ?

**Constat** : L'alimentation externe 5V arrive sur le connecteur H2, pin 4. Le schema utilise le label `+5` pour ce pin. Mais les composants (servo, MCP23017, A4988 VDD, LEDs) utilisent le label `5V`.

**Probleme** : Dans EasyEDA, **deux labels de net differents = deux nets electriquement separees**. La netlist confirme :

```
(+5
H2-4)              ← net "+5" : SEUL, ne va nulle part

(5V
H1-3               ← net "5V" : alimente les composants...
U2-3                   servo SG90
U3-10                  A4988 #2 VDD
U4-10                  A4988 #1 VDD
U6-14)                 MCP23017 VIN
                    ← ...mais n'a PAS de source d'alimentation !
```

**Consequence** : Si le PCB physique reproduit fidellement le schema, alors :
- L'alimentation +5V externe (H2.4) ne rejoint **aucun** composant
- Le rail "5V" des composants n'a **aucune source**
- Le MCP23017, les A4988, le servo et les LEDs n'auront **pas de courant**

**Nuance importante** : Il est possible que le concepteur ait corrige cette erreur directement sur le PCB en routant une piste physique entre H2.4 et le rail 5V, malgre l'erreur de nommage dans le schema. **Il faut verifier physiquement avec un multimetre** (continuite entre H2 pin 4 et VIN du MCP23017).

**Verification** : L'ESP32 pins 19-20 (VCC/5V USB) ne sont dans **aucun** net de la netlist, donc le 5V USB de l'ESP32 n'alimente pas non plus les composants externes.

---

## SERIEUX (P1) -- Problemes au boot ou fiabilite

### 4. GPIO0 (BOUTON3 / Colonne 3) -- Strapping pin de boot

**Constat** : GPIO0 est utilise comme colonne 3 de la matrice de boutons.

**Probleme** : GPIO0 est un "strapping pin" de l'ESP32 :
- **HIGH au boot** (defaut, pull-up interne) → mode execution normale (SPI boot)
- **LOW au boot** → mode download (programmation serie)

Si un bouton de la colonne 3 est enfonce pendant un reset/power-on, GPIO0 sera tire LOW par le scan de la matrice (ou par le bouton lui-meme si les lignes n'ont pas de pull-up), et l'ESP32 entrera en **mode programmation** au lieu de demarrer normalement.

**Verification dans la netlist** :
```
(BOUTON3
U1-34
H4-5)        ← U1 pin 34 = IO0 = strapping pin
```

---

### 5. GPIO2 (BOUTON2 / Colonne 2) -- Strapping pin de boot

**Constat** : GPIO2 est utilise comme colonne 2 de la matrice de boutons.

**Probleme** : GPIO2 est aussi un strapping pin :
- Controle le boot conjointement avec GPIO0
- Doit etre **LOW ou flottant** pour entrer en mode download
- Connecte a la **LED interne** de la carte Freenove (peut tirer le signal)
- Si un signal parasite tire GPIO2 HIGH au mauvais moment, le boot peut echouer

**Risque en pratique** : Moins bloquant que GPIO0, mais peut causer des comportements imprevisibles au demarrage, surtout si la LED interne consomme du courant sur cette ligne.

---

### 6. GPIO12 (BOUTON8 / Ligne 2) -- Strapping pin flash voltage

**Constat** : GPIO12 est utilise comme ligne 2 de la matrice de boutons. En mode scan, les lignes seront configurees en `INPUT_PULLUP`.

**Probleme** : GPIO12 (MTDI) est un strapping pin qui controle la tension VDD_SDIO :
- **LOW au boot** → VDD_SDIO = 3.3V (correct pour WROOM avec flash 3.3V)
- **HIGH au boot** → VDD_SDIO = 1.8V (incompatible avec le flash du WROOM)

Si GPIO12 a un pull-up actif au moment du boot (ce qui sera le cas avec `INPUT_PULLUP` configure dans `setup()`), l'ESP32 tentera de lire le flash en 1.8V au lieu de 3.3V → **le boot echouera** ou le comportement sera instable.

**Nuance** : Le code Arduino appelle `INPUT_PULLUP` dans `setup()`, qui s'execute **apres** le boot. Donc le strapping est lu avant que le pull-up software soit configure. Si aucun circuit externe ne tire GPIO12 HIGH au moment du power-on, ca devrait fonctionner. Mais sans pull-down externe, le pin est **flottant** au boot, ce qui est risque.

---

### 7. GPIO15 (BOUTON1 / Colonne 1) -- Strapping pin debug

**Constat** : GPIO15 est utilise comme colonne 1 de la matrice de boutons.

**Probleme** : GPIO15 (MTDO) controle l'emission de logs debug au boot :
- **HIGH au boot** → active les messages de debug U0TXD au demarrage
- **LOW au boot** → supprime les messages de boot

**Impact** : Si GPIO15 est HIGH au boot, des caracteres parasites seront envoyes sur TX (GPIO1) = sur la liaison UART vers le Raspberry Pi. Le RPi pourrait interpreter ces caracteres comme des donnees valides du protocole de communication.

---

## MODERE (P2) -- Performance et conception

### 8. Matrice de boutons sans pull-up/pull-down

**Constat** : Le schema ne montre **aucune resistance** sur les lignes ou colonnes de la matrice de boutons. La netlist confirme : chaque signal BOUTON connecte directement un pin ESP32 a un connecteur H3/H4, sans composant intermediaire.

**Probleme** :
- Les lignes (INPUT) sont **flottantes** quand aucun bouton n'est presse
- Lectures aleatoires, faux positifs, rebonds non filtres
- Le debounce purement software ne suffit pas pour des pins flottants

**Solution software** : Utiliser `INPUT_PULLUP` sur les lignes (H3). L'ESP32 a des pull-ups internes de ~45kΩ sur la plupart des GPIOs. Mais attention au conflit avec GPIO12 (voir issue #6).

---

### 9. Signaux STEP des moteurs via I2C (MCP23017)

**Constat** : Les signaux STEP et DIR des A4988 passent par le MCP23017, accessible uniquement en I2C.

**Probleme** : Pour chaque pas moteur, il faut :
1. Ecrire un byte via I2C pour mettre STEP HIGH
2. Attendre la duree du pulse (min 1 µs pour A4988)
3. Ecrire un byte via I2C pour mettre STEP LOW

Chaque transaction I2C a 100 kHz prend ~100 µs (adresse + registre + data). A 400 kHz (fast mode) : ~25 µs.

**Frequence max theorique** : ~5 kHz en fast mode (2 transactions par pas).
Avec un Nema 17 en full-step (200 pas/tour) : ~25 tours/sec max ≈ 1500 RPM.
En microstep 1/8 (1600 pas/tour) : ~3 tours/sec ≈ 188 RPM.

**Impact** : Pour un systeme de deplacement XY sur un plateau de jeu (mouvements lents et precis), c'est probablement suffisant. Mais les mouvements simultanees X+Y seront sequentiels, pas vraiment paralleles.

---

### 10. Servo SG90 sur le meme rail 5V que la logique

**Constat** : Le servo SG90 (U2) est alimente par le meme net "5V" que le MCP23017 (VIN) et les A4988 (VDD).

**Probleme** : Le SG90 peut tirer jusqu'a **750 mA** en pic (demarrage/blocage). Ces pics de courant provoquent des chutes de tension sur le rail 5V qui peuvent :
- Faire reseter le MCP23017 (brown-out)
- Causer des erreurs I2C
- Perturber la logique des A4988

---

### 11. A4988 ENABLE non connecte

**Constat** : Les pins ENA (U3-1, U4-1) ne sont dans aucun net de la netlist = flottants.

**Probleme** : Le pin ENABLE de l'A4988 est actif LOW avec pull-down interne. Quand il est flottant ou LOW, le driver est **toujours actif**. Les bobines du moteur sont alimentees en permanence → **chaleur** dans le moteur et le driver, meme quand le moteur est immobile.

**Impact** : Usure thermique, consommation inutile, risque de surchauffe si le systeme tourne longtemps.

---

### 12. UART0 partage entre USB et Raspberry Pi -- RESOLU

**Constat** : Les pins TX (GPIO1) et RX (GPIO3) sont connectes au Raspberry Pi. Ce sont aussi les pins de l'UART0, utilise par le bridge USB-serie de la carte Freenove.

**Probleme initial** : Si le cable USB **et** le cable UART du RPi sont branches en meme temps, les signaux TX entrent en conflit.

**RESOLU grace au WROOM** : Le module reel est un WROOM (pas WROVER), donc GPIO16 et GPIO17 sont **disponibles**. Ce sont les pins par defaut de UART2. On peut :
- Utiliser **UART2 (Serial2)** sur GPIO16 (RX) / GPIO17 (TX) pour la communication RPi
- Garder **UART0 (Serial)** sur GPIO1/GPIO3 pour le debug USB
- Les deux fonctionnent en meme temps sans conflit

**Note** : Le PCB route TX/RX (GPIO1/GPIO3) vers le RPi. Il faudra soit recabler le connecteur UART vers GPIO16/17, soit remappe Serial2 sur GPIO1/GPIO3 et accepter de ne pas pouvoir debug par USB en meme temps. Voir SOLUTIONS_CORRECTIONS.md #7.

---

## MINEUR (P3) -- Documentation et details

### 13. REFERENCE_PCB.md : Port A et Port B du MCP23017 inverses

**Constat** : Le document `REFERENCE_PCB.md` indique :
- "Port A" → pins U6.9 a U6.13 → Moteur X
- "Port B" → pins U6.19 a U6.23 → Moteur Y

**Realite (verifiee dans la netlist et le pinout Adafruit)** :
- Pins U6.9-U6.13 = **B4-B0 (Port B)** → Moteur X
- Pins U6.19-U6.23 = **A0-A4 (Port A)** → Moteur Y

Les labels sont **inverses**. Si le code software se base sur cette doc pour ecrire dans les registres I2C du MCP23017 (`GPIOA = 0x12`, `GPIOB = 0x13`), les moteurs seront permutes.

**De plus** : La doc dit "6 GPIO libres sur port B pins B2-B7". En realite :
- Port A : A5, A6, A7 (3 pins libres)
- Port B : B5, B6, B7 (3 pins libres)
- Total : 6 pins libres (chiffre correct, assignation de port incorrecte)

---

### 14. Decouplage insuffisant

**Constat** : Un seul condensateur de 10 µF sur le rail +12V. Aucun condensateur visible sur le rail 5V, ni pres des VDD des A4988 ou du MCP23017.

**Impact** : Les commutations rapides des A4988 (back-EMF des moteurs) peuvent generer du bruit sur le rail 12V. Sans decouplage 100 nF pres de chaque VDD, risque de comportement erratique de la logique.

---

### 15. Mauvais module ESP32 dans le schema EasyEDA

**Constat** : Le schema et la BOM referent a un **ESP32-WROVER-Dev Freenove v1.6**. Le module reellement utilise est un **ESP32-WROOM** (confirme par le pinout Freenove fourni par l'equipe).

**Differences cles** :

| | WROVER (dans le schema) | WROOM (reel) |
|--|------------------------|--------------|
| PSRAM | 4 MB (SPI, utilise GPIO16/17) | Aucun |
| GPIO16 | Occupe par PSRAM | **Disponible** (RX2 par defaut) |
| GPIO17 | Occupe par PSRAM | **Disponible** (TX2 par defaut) |
| Flash | 4-16 MB | 4 MB |
| Footprint PCB | Compatible | **Compatible** (meme brochage 38/40 pins) |

**Impact positif** : GPIO16 et GPIO17 sont utilisables, ce qui :

- Resout le conflit UART (issue #12) : UART2 sur GPIO16/17 pour RPi, UART0 pour USB
- Ajoute 2 pins spare supplementaires au total

**Impact negatif** : La configuration PlatformIO (`board = upesy_wrover`) est incorrecte et pourrait activer des options PSRAM inutiles.

---

## Elements verifies et corrects

| Element | Statut | Detail |
|---------|--------|--------|
| I2C SDA/SCL | OK | IO21 (SDA) → U6.17, IO22 (SCL) → U6.16, pull-ups sur module Adafruit |
| MCP23017 adresse | OK | Pins D0-D2 non connectes = pull-down = adresse **0x20** |
| MCP23017 RST | OK | Non connecte, pull-up interne sur module Adafruit = actif |
| A4988 RST/SLP | OK | Lies ensemble (U3-5↔U3-6, U4-5↔U4-6) = mode toujours actif |
| Moteurs coils | OK | Connexions A4988 ↔ Nema17 (1A/1B/2A/2B) correctes |
| Condensateur 12V | OK | 10 µF entre +12V et GND |
| Connecteur H2 | OK | +12V (pin 3), +5 (pin 4), GND (pins 6-8) |
| Flash SPI | OK | Pins SD0-SD3, CLK, CMD non utilises (reserves au flash interne) |
| GPIO16/GPIO17 | **DISPONIBLES** | Module reel = WROOM (pas de PSRAM) → utilisables pour UART2 |

---

## Resume : que faut-il corriger ?

### Corrections hardware obligatoires (sans refaire le PCB)

1. **Recabler les LEDs** : couper la piste IO34 → H1.4, souder un fil volant depuis un pin spare (IO32, IO33, IO23 ou IO19) vers H1.4
2. **Recabler le servo** : couper la piste IO35 → U2.2, souder un fil volant depuis un pin spare vers U2.2
3. **Verifier la continuite +5/5V** : tester au multimetre si H2.4 est bien relie au VIN du MCP23017

### Corrections software obligatoires

4. **Pull-ups internes** sur les lignes de la matrice (INPUT_PULLUP) -- sauf GPIO12
5. **Gestion des strapping pins** (GPIO0, GPIO2, GPIO12, GPIO15) dans le code de scan
6. **Utiliser les bons registres MCP23017** : Port A = moteur Y, Port B = moteur X (pas l'inverse)
7. **Debounce software** pour la matrice de boutons

### Corrections recommandees

8. Ajouter une pull-down externe sur GPIO12 (10kΩ vers GND)
9. Ajouter une pull-up externe sur GPIO0 (10kΩ vers 3.3V)
10. Ajouter des condensateurs 100 nF de decouplage pres des A4988 VDD
