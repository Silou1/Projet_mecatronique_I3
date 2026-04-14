# Pin mapping verifie -- Quoridor PCB

> **Source de verite** : netlist `Sheet_1_2026-03-31.net` + pinout Freenove ESP32-WROOM + pinout Adafruit MCP23017
>
> **ATTENTION** : Le schema EasyEDA reference un ESP32-WROVER, mais le module reel est un
> **ESP32-WROOM**. Ce document utilise le module reel (WROOM). Principale consequence :
> GPIO16 et GPIO17 sont **disponibles** (pas de PSRAM).
>
> Ce document corrige les erreurs trouvees dans `REFERENCE_PCB.md` et constitue la reference
> a utiliser pour le developpement software.

---

## ESP32-WROOM Freenove (U1) -- module reel

### Pins utilises -- Vue par fonction

#### Matrice de boutons (12 pins)

**Colonnes (OUTPUT, connecteur H4)** -- Le scan met une colonne a LOW, les autres HIGH.

| GPIO | Pin ESP32 | Signal net | Connecteur | Strapping ? | Notes |
|------|-----------|-----------|------------|-------------|-------|
| IO15 | 36 | BOUTON1 | H4.3 | Oui (MTDO) | Active debug log si HIGH au boot |
| IO2 | 35 | BOUTON2 | H4.4 | Oui | LED interne, role au boot |
| IO0 | 34 | BOUTON3 | H4.5 | **Oui (CRITIQUE)** | LOW au boot = mode download |
| IO4 | 33 | BOUTON4 | H4.6 | Non | OK |
| IO5 | 30 | BOUTON5 | H4.7 | Non | OK |
| IO18 | 29 | BOUTON6 | H4.8 | Non | OK |

**Lignes (INPUT, connecteur H3)** -- Lecture du resultat du scan.

| GPIO | Pin ESP32 | Signal net | Connecteur | Strapping ? | Notes |
|------|-----------|-----------|------------|-------------|-------|
| IO13 | 15 | BOUTON7 | H3.3 | Non | OK, supporte INPUT_PULLUP |
| IO12 | 13 | BOUTON8 | H3.4 | **Oui (SERIEUX)** | HIGH = flash 1.8V, pull-down externe requise |
| IO14 | 12 | BOUTON9 | H3.5 | Non | OK, supporte INPUT_PULLUP |
| IO27 | 11 | BOUTON10 | H3.6 | Non | OK, supporte INPUT_PULLUP |
| IO26 | 10 | BOUTON11 | H3.7 | Non | OK, supporte INPUT_PULLUP |
| IO25 | 9 | BOUTON12 | H3.8 | Non | OK, supporte INPUT_PULLUP |

#### Correspondance matrice → plateau de jeu

```
             Col1(IO15) Col2(IO2) Col3(IO0) Col4(IO4) Col5(IO5) Col6(IO18)
Lig1(IO13)    [0,0]      [0,1]     [0,2]     [0,3]     [0,4]     [0,5]
Lig2(IO12)    [1,0]      [1,1]     [1,2]     [1,3]     [1,4]     [1,5]
Lig3(IO14)    [2,0]      [2,1]     [2,2]     [2,3]     [2,4]     [2,5]
Lig4(IO27)    [3,0]      [3,1]     [3,2]     [3,3]     [3,4]     [3,5]
Lig5(IO26)    [4,0]      [4,1]     [4,2]     [4,3]     [4,4]     [4,5]
Lig6(IO25)    [5,0]      [5,1]     [5,2]     [5,3]     [5,4]     [5,5]
```

> **Nota** : Les coordonnees `[ligne, colonne]` ci-dessus correspondent directement aux
> coordonnees `(row, col)` du moteur de jeu Python (0-indexed, (0,0) en haut a gauche).
> Lig1 = row 0, Lig6 = row 5. Col1 = col 0, Col6 = col 5.

#### Communication I2C (2 pins)

| GPIO | Pin ESP32 | Signal | Destination | Notes |
|------|-----------|--------|-------------|-------|
| IO22 | 23 | SCL | U6.16 (MCP23017) | Pull-up 10kΩ sur module Adafruit |
| IO21 | 26 | SDA | U6.17 (MCP23017) | Pull-up 10kΩ sur module Adafruit |

#### Communication UART

**UART0 (route sur le PCB vers RPi)** :

| GPIO | Pin ESP32 | Signal | Destination | Notes |
|------|-----------|--------|-------------|-------|
| GPIO1 | 24 | TX | RPi RX | Partage avec USB-UART bridge |
| GPIO3 | 25 | RX | RPi TX | Partage avec USB-UART bridge |

**UART2 (disponible grace au WROOM, non route sur PCB)** :

| GPIO | Pin ESP32 | Signal | Disponibilite | Notes |
|------|-----------|--------|---------------|-------|
| GPIO16 | -- | RX2 | **Libre (WROOM)** | Pin par defaut UART2 RX, pas sur le PCB |
| GPIO17 | -- | TX2 | **Libre (WROOM)** | Pin par defaut UART2 TX, pas sur le PCB |

> **Recommandation** : Utiliser UART0 (GPIO1/3) pour la communication RPi comme prevu sur le
> PCB. Debrancher le cable UART RPi pendant la programmation/debug USB. Ou bien remappe
> Serial2 sur GPIO1/3 pour la RPi et garder Serial pour le debug USB (meme conflit physique).

#### LEDs et Servo (APRES correction hardware)

| GPIO | Pin ESP32 | Signal original | Fonction | Correction |
|------|-----------|----------------|----------|------------|
| ~~IO34~~ | ~~5~~ | ~~LED~~ | ~~Data LEDs~~ | ~~INPUT-ONLY, ne fonctionne pas~~ |
| ~~IO35~~ | ~~6~~ | ~~SERVOMOT~~ | ~~PWM servo~~ | ~~INPUT-ONLY, ne fonctionne pas~~ |
| **IO32** | **7** | SUPP1 → **LED** | **Data LEDs (corrige)** | Fil volant IO32 → H1.4 |
| **IO33** | **8** | SUPP2 → **SERVO** | **PWM servo (corrige)** | Fil volant IO33 → U2.2 |

#### Pins spare restants (apres corrections)

| GPIO | Pin ESP32 | Signal | Connecteur | Disponible pour |
|------|-----------|--------|------------|-----------------|
| IO16 | -- | -- | Non route sur PCB | **UART2 RX** (defaut), GPIO general |
| IO17 | -- | -- | Non route sur PCB | **UART2 TX** (defaut), GPIO general |
| IO23 | 22 | SUPP3 | H1.8 | GPIO general |
| IO19 | 28 | SUPP4 | H1.7 | GPIO general |

> **Note** : GPIO16/17 ne sont pas routes sur le PCB (le schema importe un WROVER qui les
> reserve au PSRAM). Ils sont accessibles directement sur les pins de la carte ESP32 mais
> il n'y a pas de piste PCB pour eux. Pour les utiliser, il faut souder des fils volants
> depuis la carte ESP32 ou les connecter via des cables Dupont.

---

## MCP23017 (U6) -- Adafruit breakout, adresse I2C 0x20

### Configuration des pins d'adresse

| Pin module | Nom | Etat | Resultat |
|-----------|-----|------|----------|
| U6.3 | D0 (A0 du chip) | Non connecte → pull-down interne = LOW | Bit 0 = 0 |
| U6.4 | D1 (A1 du chip) | Non connecte → pull-down interne = LOW | Bit 1 = 0 |
| U6.5 | D2 (A2 du chip) | Non connecte → pull-down interne = LOW | Bit 2 = 0 |

**Adresse I2C** : `0b0100000` = **0x20**

### Port A (registre GPIOA = 0x12) → Moteur Y (U3/A4988 #2 → U8/Nema17 Y)

| Bit | Pin lib Adafruit | Pin module | Signal net | Destination A4988 | Fonction |
|-----|-----------------|-----------|------------|-------------------|----------|
| A0 | 0 | U6.19 | DIR_MOT2 | U3.8 (DIR) | Direction moteur Y |
| A1 | 1 | U6.20 | STEP_MOT2 | U3.7 (STEP) | Impulsion pas moteur Y |
| A2 | 2 | U6.21 | MS3_2 | U3.4 (MS3) | Microstep bit 3 |
| A3 | 3 | U6.22 | MS2_2 | U3.3 (MS2) | Microstep bit 2 |
| A4 | 4 | U6.23 | MS1_2 | U3.2 (MS1) | Microstep bit 1 |
| A5 | 5 | U6.24 | -- | -- | **Libre** |
| A6 | 6 | U6.25 | -- | -- | **Libre** |
| A7 | 7 | U6.26 | -- | -- | **Libre** |

### Port B (registre GPIOB = 0x13) → Moteur X (U4/A4988 #1 → U7/Nema17 X)

| Bit | Pin lib Adafruit | Pin module | Signal net | Destination A4988 | Fonction |
|-----|-----------------|-----------|------------|-------------------|----------|
| B0 | 8 | U6.13 | DIR_MOT1 | U4.8 (DIR) | Direction moteur X |
| B1 | 9 | U6.12 | STEP_MOT1 | U4.7 (STEP) | Impulsion pas moteur X |
| B2 | 10 | U6.11 | MS3_1 | U4.4 (MS3) | Microstep bit 3 |
| B3 | 11 | U6.10 | MS2_1 | U4.3 (MS2) | Microstep bit 2 |
| B4 | 12 | U6.9 | MS1_1 | U4.2 (MS1) | Microstep bit 1 |
| B5 | 13 | U6.8 | -- | -- | **Libre** (candidat ENA moteur X) |
| B6 | 14 | U6.7 | -- | -- | **Libre** |
| B7 | 15 | U6.6 | -- | -- | **Libre** |

### Registres byte pour ecriture rapide

Pour envoyer une commande complete en une seule ecriture I2C :

**Port A (moteur Y)** — byte = `0bXXX MS1 MS2 MS3 STEP DIR`

| Bit 7 | Bit 6 | Bit 5 | Bit 4 | Bit 3 | Bit 2 | Bit 1 | Bit 0 |
|-------|-------|-------|-------|-------|-------|-------|-------|
| A7 (libre) | A6 (libre) | A5 (libre) | MS1_2 | MS2_2 | MS3_2 | STEP_MOT2 | DIR_MOT2 |

**Port B (moteur X)** — byte = `0bXXX MS1 MS2 MS3 STEP DIR`

| Bit 7 | Bit 6 | Bit 5 | Bit 4 | Bit 3 | Bit 2 | Bit 1 | Bit 0 |
|-------|-------|-------|-------|-------|-------|-------|-------|
| B7 (libre) | B6 (libre) | B5 (libre) | MS1_1 | MS2_1 | MS3_1 | STEP_MOT1 | DIR_MOT1 |

**Exemple** : faire un pas en avant sur moteur X (direction = 1, step pulse) :
```cpp
// Direction = HIGH, microstepping 1/8 (MS1=1, MS2=1, MS3=0)
// Byte = 0b000 1 1 0 0 1 = 0x19
Wire.beginTransmission(0x20);
Wire.write(0x13);   // registre GPIOB
Wire.write(0x19);   // DIR=1, STEP=0, MS3=0, MS2=1, MS1=1
Wire.endTransmission();

// Pulse STEP HIGH
// Byte = 0b000 1 1 0 1 1 = 0x1B
Wire.beginTransmission(0x20);
Wire.write(0x13);
Wire.write(0x1B);   // STEP passe a HIGH
Wire.endTransmission();

delayMicroseconds(10);  // pulse minimum 1µs pour A4988

// Pulse STEP LOW
Wire.beginTransmission(0x20);
Wire.write(0x13);
Wire.write(0x19);   // STEP revient a LOW
Wire.endTransmission();
```

---

## A4988 Drivers (U3 et U4)

### Configuration commune

| Pin A4988 | Connexion | Notes |
|-----------|-----------|-------|
| RST (5) | Lie a SLP (6) | Mode toujours actif |
| SLP (6) | Lie a RST (5) | Pas de mode veille |
| ENA (1) | **Non connecte** | Pull-down interne = LOW = driver actif |
| VDD (10) | Net "5V" | Alimentation logique |
| VMOT (16) | Net "+12V" | Alimentation moteur |
| GND (9, 15) | GND | Masse logique et moteur |

### Tableau de microstepping A4988

| MS1 | MS2 | MS3 | Resolution | Pas/tour (Nema17) |
|-----|-----|-----|------------|-------------------|
| LOW | LOW | LOW | Full step | 200 |
| HIGH | LOW | LOW | 1/2 step | 400 |
| LOW | HIGH | LOW | 1/4 step | 800 |
| HIGH | HIGH | LOW | 1/8 step | 1600 |
| HIGH | HIGH | HIGH | 1/16 step | 3200 |

**Recommandation pour le plateau** : 1/8 step (MS1=HIGH, MS2=HIGH, MS3=LOW) offre un bon
compromis entre precision et vitesse via I2C.

---

## Alimentation

### Rails de tension

| Rail | Source | Net name | Composants alimentes |
|------|--------|----------|---------------------|
| USB 5V | Port micro-USB ESP32 | *(non route)* | ESP32 uniquement |
| +5V ext | H2 pin 4 | **"+5"** | **RIEN** (erreur de net, voir audit #3) |
| 5V composants | H1 pin 3 | **"5V"** | Servo, MCP23017, A4988 VDD, LEDs |
| +12V | H2 pin 3 | "+12" | A4988 VMOT (x2), condensateur 10µF |
| GND | H2 pins 6-8 | "GND" | Tous les composants |

> **ATTENTION** : Verifier au multimetre que "+5" (H2.4) et "5V" (composants) sont bien
> relies physiquement sur le PCB. Si non, souder un pont (voir SOLUTIONS_CORRECTIONS.md #3).

### Connecteur H2 (alimentation externe)

| Pin | Signal | Connexion |
|-----|--------|-----------|
| H2.1 | NC | -- |
| H2.2 | NC | -- |
| H2.3 | +12V | A4988 VMOT, condensateur |
| H2.4 | +5V | **A verifier** (voir ci-dessus) |
| H2.5 | NC | -- |
| H2.6 | GND | Masse commune |
| H2.7 | GND | Masse commune |
| H2.8 | GND | Masse commune |

---

## Connecteur H1 (LEDs + spare)

| Pin | Signal | GPIO | Fonction finale |
|-----|--------|------|----------------|
| H1.1 | NC | -- | -- |
| H1.2 | GND | -- | Masse LEDs |
| H1.3 | 5V | -- | Alimentation LEDs |
| H1.4 | LED | ~~IO34~~ → **IO32** | Data LEDs (apres correction) |
| H1.5 | SUPP1 | IO32 | ~~Spare~~ → utilise pour LEDs |
| H1.6 | SUPP2 | IO33 | ~~Spare~~ → utilise pour servo |
| H1.7 | SUPP4 | IO19 | Spare (UART2 TX possible) |
| H1.8 | SUPP3 | IO23 | Spare (UART2 RX possible) |

---

## Synthese des defines pour le code ESP32

```cpp
// ===== PIN DEFINITIONS (VERIFIEES CONTRE NETLIST) =====

// --- Matrice boutons ---
// Colonnes (OUTPUT, active LOW)
#define COL_1  15  // IO15 - H4.3 - strapping (debug log)
#define COL_2   2  // IO2  - H4.4 - strapping (boot)
#define COL_3   0  // IO0  - H4.5 - strapping (boot mode !)
#define COL_4   4  // IO4  - H4.6
#define COL_5   5  // IO5  - H4.7
#define COL_6  18  // IO18 - H4.8

// Lignes (INPUT, active LOW avec pull-up)
#define LIG_1  13  // IO13 - H3.3
#define LIG_2  12  // IO12 - H3.4 - strapping (flash voltage !)
#define LIG_3  14  // IO14 - H3.5
#define LIG_4  27  // IO27 - H3.6
#define LIG_5  26  // IO26 - H3.7
#define LIG_6  25  // IO25 - H3.8

// --- LEDs (apres correction hardware IO34 → IO32) ---
#define PIN_LED_DATA  32  // IO32 - H1.5 → cable vers H1.4
#define NUM_LEDS      36  // 6x6 plateau

// --- Servo (apres correction hardware IO35 → IO33) ---
#define PIN_SERVO     33  // IO33 - H1.6 → cable vers U2.2

// --- I2C (MCP23017) ---
#define PIN_SDA       21  // IO21
#define PIN_SCL       22  // IO22
#define MCP23017_ADDR 0x20

// --- MCP23017 : Moteur Y (Port A) ---
#define MOT_Y_DIR    0   // A0
#define MOT_Y_STEP   1   // A1
#define MOT_Y_MS3    2   // A2
#define MOT_Y_MS2    3   // A3
#define MOT_Y_MS1    4   // A4

// --- MCP23017 : Moteur X (Port B) ---
#define MOT_X_DIR    8   // B0
#define MOT_X_STEP   9   // B1
#define MOT_X_MS3   10   // B2
#define MOT_X_MS2   11   // B3
#define MOT_X_MS1   12   // B4

// --- UART (Raspberry Pi) ---
// UART0 (GPIO1/3) : route sur PCB vers RPi, partage avec USB debug
// UART2 (GPIO16/17) : disponible sur WROOM, non route sur PCB
#define UART_BAUD     115200
#define PIN_UART2_RX  16  // IO16 - disponible sur WROOM (pas sur WROVER)
#define PIN_UART2_TX  17  // IO17 - disponible sur WROOM (pas sur WROVER)
```
