# Solutions et corrections -- PCB Quoridor

> Corrections classees par priorite. Chaque section detaille le probleme, la correction
> hardware (si necessaire), la correction software, et comment verifier que ca fonctionne.

---

## Table des matieres

1. [Recablage LEDs (GPIO34 → pin spare)](#1-recablage-leds-gpio34--pin-spare)
2. [Recablage Servo (GPIO35 → pin spare)](#2-recablage-servo-gpio35--pin-spare)
3. [Verification alimentation +5V / 5V](#3-verification-alimentation-5v--5v)
4. [Gestion des strapping pins (GPIO0, 2, 12, 15)](#4-gestion-des-strapping-pins)
5. [Pull-ups matrice de boutons](#5-pull-ups-matrice-de-boutons)
6. [Correction registres MCP23017 (Port A/B)](#6-correction-registres-mcp23017)
7. [UART -- Communication RPi](#7-uart----communication-rpi-resolu-grace-au-wroom)
8. [Moteurs : chaleur et bruit](#8-moteurs-chaleur-et-bruit)

---

## 1. Recablage LEDs (GPIO34 → pin spare)

### Le probleme
GPIO34 est input-only. Il ne peut pas piloter des LEDs.

### Pins spare disponibles

| Pin | GPIO | Signal | Connecteur | Remarques |
|-----|-------|--------|------------|-----------|
| 7 | IO32 | SUPP1 | H1.5 | **Recommande pour LEDs** -- supporte PWM, RMT (NeoPixel) |
| 8 | IO33 | SUPP2 | H1.6 | Bon choix aussi, supporte PWM/RMT |
| 22 | IO23 | SUPP3 | H1.8 | Bon choix, supporte PWM (pas RMT sur tous les canaux) |
| 28 | IO19 | SUPP4 | H1.7 | Bon choix, supporte PWM |

### Correction hardware recommandee

**Option A -- Fil volant (plus simple)** :
1. Couper la piste entre IO34 (U1 pin 5) et H1.4 (avec un cutter ou un fer)
2. Souder un fil volant entre IO32 (U1 pin 7 / H1.5) et H1.4
3. Les LEDs seront cablees sur H1.4 comme prevu, mais pilotees par IO32

**Option B -- Cablage cote connecteur (sans toucher au PCB)** :
1. Sur le connecteur H1, ne pas brancher le fil de data LED sur H1.4
2. Brancher le fil de data LED directement sur H1.5 (IO32/SUPP1)
3. Avantage : pas besoin de couper de piste

### Correction software
```cpp
// Dans le code ESP32 :
#define PIN_LED_DATA  32   // au lieu de 34

// Exemple avec FastLED :
#define NUM_LEDS 36
CRGB leds[NUM_LEDS];
FastLED.addLeds<WS2812B, PIN_LED_DATA, GRB>(leds, NUM_LEDS);

// Exemple avec Adafruit NeoPixel :
Adafruit_NeoPixel strip(NUM_LEDS, PIN_LED_DATA, NEO_GRB + NEO_KHZ800);
```

### Verification
- Charger un sketch de test qui fait clignoter la premiere LED
- Verifier avec un oscilloscope que IO32 genere un signal a 800 kHz (protocole WS2812B)

---

## 2. Recablage Servo (GPIO35 → pin spare)

### Le probleme
GPIO35 est input-only. Il ne peut pas generer de PWM pour le servo SG90.

### Correction hardware recommandee

**Pin recommande** : **IO33 (SUPP2)** si IO32 est utilise pour les LEDs.

**Option A -- Fil volant** :
1. Couper la piste entre IO35 (U1 pin 6) et U2.2 (GPIO du servo)
2. Souder un fil volant entre IO33 (U1 pin 8) et U2.2

**Option B -- Cablage externe** :
1. Ne pas utiliser la piste PCB pour le signal servo
2. Brancher le fil signal du servo directement sur le pin IO33 de la carte ESP32
3. Garder GND et 5V sur le connecteur d'origine

### Correction software
```cpp
#define PIN_SERVO 33   // au lieu de 35

// Avec la librairie ESP32Servo :
#include <ESP32Servo.h>
Servo servo_mur;
servo_mur.attach(PIN_SERVO);
servo_mur.write(90);  // position neutre

// Ou avec LEDC directement :
ledcAttach(PIN_SERVO, 50, 16);  // 50 Hz, 16-bit resolution
ledcWrite(PIN_SERVO, 4915);     // ~1.5ms = position neutre
```

### Verification
- Le servo doit tourner physiquement quand on envoie differents angles
- Verifier le signal PWM : 50 Hz, pulse entre 1 ms (0°) et 2 ms (180°)

---

## 3. Verification alimentation +5V / 5V

### Le probleme
La netlist montre deux nets separees : "+5" (H2.4 seul) et "5V" (composants). Si non connectees, les composants n'ont pas de courant.

### Verification obligatoire (avant tout test)

**Etape 1 -- Test de continuite** :
1. PCB non alimentee, rien de branche
2. Multimetre en mode continuite (beep)
3. Toucher une sonde sur H2 pin 4 (+5V externe)
4. Toucher l'autre sonde sur U6 pin 14 (VIN du MCP23017) ou U4 pin 10 (VDD A4988)

**Resultat A : beep** → Les nets sont connectees sur le PCB malgre l'erreur de nommage. Pas de correction necessaire.

**Resultat B : pas de beep** → Les nets sont reellement separees. Correction obligatoire :

### Correction hardware (si nets deconnectees)
1. Souder un fil volant entre H2 pin 4 et n'importe quel point du net "5V" :
   - H1 pin 3 (le plus accessible)
   - Ou directement sur le pad VIN du MCP23017
2. Alternative : pont de soudure entre les deux pistes si elles passent pres l'une de l'autre sur le PCB

### Verification post-correction
1. Brancher l'alimentation externe 5V sur H2
2. Mesurer la tension sur VIN du MCP23017 → doit lire ~5V
3. Mesurer sur VDD de l'A4988 → doit lire ~5V
4. Mesurer sur le pin 5V du servo → doit lire ~5V

---

## 4. Gestion des strapping pins

### Tableau recapitulatif

| GPIO | Fonction matrice | Strapping | Etat pour boot normal | Risque |
|------|-----------------|-----------|----------------------|--------|
| GPIO0 | Colonne 3 (OUTPUT) | Boot mode | HIGH | Bouton enfonce = mode download |
| GPIO2 | Colonne 2 (OUTPUT) | Boot mode | LOW/flottant | LED interne peut tirer le signal |
| GPIO12 | Ligne 2 (INPUT) | Flash voltage | LOW (3.3V) | INPUT_PULLUP = HIGH = flash 1.8V |
| GPIO15 | Colonne 1 (OUTPUT) | Debug log | Indifferent | Logs parasites sur UART au boot |

### Corrections pour GPIO0 (BOUTON3)

**Hardware** : Ajouter une resistance **pull-up de 10 kΩ** entre GPIO0 et 3.3V. Cela garantit que GPIO0 est HIGH au boot meme si le bouton est dans un etat ambigu.

**Software** : Au debut du scan de la matrice, **ne pas mettre GPIO0 en OUTPUT LOW** avant que le boot soit termine. Sequence recommandee :
```cpp
void setup() {
    delay(100);  // laisser le boot se terminer

    // Configurer les colonnes en OUTPUT HIGH (inactif)
    for (int col : colonnes) {
        pinMode(col, OUTPUT);
        digitalWrite(col, HIGH);
    }
    // Configurer les lignes en INPUT_PULLUP
    for (int lig : lignes) {
        if (lig != 12) {  // GPIO12 : voir ci-dessous
            pinMode(lig, INPUT_PULLUP);
        }
    }
}
```

### Corrections pour GPIO12 (BOUTON8)

**Hardware (recommande)** : Ajouter une resistance **pull-down de 10 kΩ** entre GPIO12 et GND. Cela force GPIO12 LOW au boot (= flash 3.3V). L'`INPUT_PULLUP` software (~45kΩ) sera plus faible que la pull-down externe (10kΩ), mais on peut aussi :

**Alternative software** : Ne **pas** utiliser `INPUT_PULLUP` sur GPIO12. A la place :
```cpp
// Pour GPIO12 : utiliser INPUT simple (pas de pull-up)
pinMode(12, INPUT);
// La pull-down externe (si ajoutee) maintiendra le niveau LOW quand pas de bouton
// Le bouton devra amener GPIO12 a HIGH (inverser la logique pour cette ligne)
```

**Alternative definitive** : Graver le eFuse pour forcer VDD_SDIO a 3.3V, ce qui ignore le strapping de GPIO12 :
```bash
# ATTENTION : operation irreversible !
espefuse.py --port /dev/ttyUSB0 set_flash_voltage 3.3V
```

### Corrections pour GPIO15 (BOUTON1)

**Software uniquement** : Au demarrage, GPIO15 peut etre dans n'importe quel etat. Les messages de boot parasites sur UART seront envoyes avant que `setup()` ne s'execute. 

**Mitigation cote Raspberry Pi** : Ignorer les donnees recues sur UART pendant les 2 premieres secondes apres un reset de l'ESP32, ou attendre un message "READY" specifique avant de commencer la communication.

---

## 5. Pull-ups matrice de boutons

### Le probleme
Les lignes de la matrice (INPUT) n'ont pas de pull-up/pull-down. Sans pull-up, les pins flottent et donnent des lectures aleatoires.

### Correction software (suffisante dans la plupart des cas)

```cpp
// Pins de la matrice
const int colonnes[] = {15, 2, 0, 4, 5, 18};  // H4 : OUTPUT
const int lignes[]   = {13, 12, 14, 27, 26, 25};  // H3 : INPUT

void setup_matrice() {
    // Colonnes en OUTPUT HIGH (inactif = pas de scan)
    for (int col : colonnes) {
        pinMode(col, OUTPUT);
        digitalWrite(col, HIGH);
    }

    // Lignes en INPUT_PULLUP (pull-up interne ~45kΩ)
    for (int lig : lignes) {
        if (lig == 12) {
            // GPIO12 : pas de pull-up (strapping pin)
            // Ajouter une pull-down externe de 10kΩ
            pinMode(lig, INPUT);
        } else {
            pinMode(lig, INPUT_PULLUP);
        }
    }
}
```

### Scan de la matrice avec debounce

```cpp
// Logique de scan :
// 1. Mettre une colonne a LOW, les autres a HIGH
// 2. Lire chaque ligne :
//    - LOW = bouton enfonce (pour lignes avec INPUT_PULLUP)
//    - HIGH = bouton enfonce (pour GPIO12 avec pull-down externe)
// 3. Passer a la colonne suivante
// 4. Debounce : un bouton est valide seulement si lu 2 fois de suite (20ms d'ecart)

int lire_bouton() {
    static unsigned long derniere_lecture[6][6] = {0};
    static bool etat_precedent[6][6] = {false};

    for (int c = 0; c < 6; c++) {
        // Activer la colonne (LOW)
        digitalWrite(colonnes[c], LOW);
        delayMicroseconds(10);  // temps d'etablissement

        for (int l = 0; l < 6; l++) {
            bool presse;
            if (lignes[l] == 12) {
                presse = digitalRead(lignes[l]) == HIGH;  // logique inversee
            } else {
                presse = digitalRead(lignes[l]) == LOW;   // pull-up : LOW = presse
            }

            if (presse && !etat_precedent[l][c]) {
                if (millis() - derniere_lecture[l][c] > 50) {  // debounce 50ms
                    derniere_lecture[l][c] = millis();
                    etat_precedent[l][c] = true;
                    digitalWrite(colonnes[c], HIGH);
                    return (l + 1) * 10 + (c + 1);  // ex: 23 = ligne 2, col 3
                }
            }
            if (!presse) {
                etat_precedent[l][c] = false;
            }
        }

        // Desactiver la colonne
        digitalWrite(colonnes[c], HIGH);
    }
    return -1;  // aucun bouton presse
}
```

### Correction hardware complementaire (recommandee)
Ajouter des resistances pull-down de 10 kΩ sur **toutes** les lignes (H3.3 a H3.8 vers GND). Cela :
- Uniformise la logique de lecture (pas de cas special pour GPIO12)
- Offre un etat defini au boot (tous les pins INPUT = LOW)
- Evite les problemes de strapping

---

## 6. Correction registres MCP23017

### Le probleme
REFERENCE_PCB.md dit "Port A → Moteur X" et "Port B → Moteur Y". C'est **l'inverse**.

### Mapping reel (verifie contre la netlist)

**Port B** (registre GPIOB = `0x13`, OLATB = `0x15`) → **Moteur X (U4)** :

| Bit | Pin MCP23017 | Signal | Fonction |
|-----|-------------|--------|----------|
| B0 | Module pin 13 | DIR_MOT1 | Direction moteur X |
| B1 | Module pin 12 | STEP_MOT1 | Pas moteur X |
| B2 | Module pin 11 | MS3_1 | Microstep bit 3 |
| B3 | Module pin 10 | MS2_1 | Microstep bit 2 |
| B4 | Module pin 9 | MS1_1 | Microstep bit 1 |
| B5-B7 | Pins 8-6 | -- | Libres |

**Port A** (registre GPIOA = `0x12`, OLATA = `0x14`) → **Moteur Y (U3)** :

| Bit | Pin MCP23017 | Signal | Fonction |
|-----|-------------|--------|----------|
| A0 | Module pin 19 | DIR_MOT2 | Direction moteur Y |
| A1 | Module pin 20 | STEP_MOT2 | Pas moteur Y |
| A2 | Module pin 21 | MS3_2 | Microstep bit 3 |
| A3 | Module pin 22 | MS2_2 | Microstep bit 2 |
| A4 | Module pin 23 | MS1_2 | Microstep bit 1 |
| A5-A7 | Pins 24-26 | -- | Libres |

### Code correct pour le MCP23017

```cpp
#include <Wire.h>
#include <Adafruit_MCP23X17.h>

Adafruit_MCP23X17 mcp;

// Definitions des pins MCP23017
// Port B → Moteur X (U4)
#define MOT_X_DIR   8   // B0 (MCP pin 8 dans la lib Adafruit = GPA0... non)
// ATTENTION : dans la librairie Adafruit_MCP23X17 :
//   Pins 0-7  = GPA0-GPA7 (Port A)
//   Pins 8-15 = GPB0-GPB7 (Port B)

// Port A → Moteur Y
#define MOT_Y_DIR   0   // A0
#define MOT_Y_STEP  1   // A1
#define MOT_Y_MS3   2   // A2
#define MOT_Y_MS2   3   // A3
#define MOT_Y_MS1   4   // A4

// Port B → Moteur X
#define MOT_X_DIR   8   // B0
#define MOT_X_STEP  9   // B1
#define MOT_X_MS3   10  // B2
#define MOT_X_MS2   11  // B3
#define MOT_X_MS1   12  // B4

void setup_moteurs() {
    mcp.begin_I2C(0x20);  // adresse par defaut

    // Configurer tous les pins moteurs en OUTPUT
    for (int pin : {0,1,2,3,4, 8,9,10,11,12}) {
        mcp.pinMode(pin, OUTPUT);
        mcp.digitalWrite(pin, LOW);
    }

    // Microstepping 1/8 : MS1=HIGH, MS2=HIGH, MS3=LOW
    mcp.digitalWrite(MOT_X_MS1, HIGH);
    mcp.digitalWrite(MOT_X_MS2, HIGH);
    mcp.digitalWrite(MOT_X_MS3, LOW);
    mcp.digitalWrite(MOT_Y_MS1, HIGH);
    mcp.digitalWrite(MOT_Y_MS2, HIGH);
    mcp.digitalWrite(MOT_Y_MS3, LOW);
}

void step_moteur_x(bool direction, int pas) {
    mcp.digitalWrite(MOT_X_DIR, direction ? HIGH : LOW);
    for (int i = 0; i < pas; i++) {
        mcp.digitalWrite(MOT_X_STEP, HIGH);
        delayMicroseconds(100);
        mcp.digitalWrite(MOT_X_STEP, LOW);
        delayMicroseconds(500);  // ~1600 pas/sec max en I2C fast mode
    }
}
```

---

## 7. UART -- Communication RPi (RESOLU grace au WROOM)

### Le probleme initial
TX/RX (GPIO1/3) sont routes sur le PCB vers le RPi, mais sont aussi utilises par le bridge
USB-serie pour le debug. Conflit si les deux sont branches.

### Solution grace au WROOM

Le module reel est un **ESP32-WROOM** (pas WROVER). GPIO16 et GPIO17 sont donc **disponibles** et sont les pins par defaut de **UART2**. Cela donne deux options propres :

**Option A -- Utiliser UART0 pour RPi (comme route sur PCB)** :
```cpp
void setup() {
    // UART0 (GPIO1/3) → RPi, comme cable sur le PCB
    Serial.begin(115200);

    // Pendant le dev : debrancher le cable RPi pour le debug USB
    // En production : pas de cable USB, Serial = RPi
}
```
Simple, pas de modification hardware. Debrancher le cable RPi pendant la programmation.

**Option B -- Utiliser UART2 sur GPIO16/17 pour RPi (recommande)** :
```cpp
void setup() {
    Serial.begin(115200);    // UART0 (GPIO1/3) = debug USB
    Serial2.begin(115200, SERIAL_8N1, 16, 17);  // UART2 = RPi
    // RX2 = GPIO16, TX2 = GPIO17
}
```
Necessite de cabler GPIO16/17 (fils volants depuis la carte ESP32 vers le RPi) au lieu
d'utiliser le connecteur TX/RX du PCB. Mais permet le debug USB et la communication RPi
**en meme temps**. Les pins spare H1 (IO19, IO23) restent libres pour d'autres usages.

---

## 8. Moteurs : chaleur et bruit

### A4988 ENABLE (chaleur)

**Solution software** : Desactiver les moteurs quand ils ne bougent pas.

Comme ENABLE n'est pas route sur le PCB, on peut utiliser les pins libres du MCP23017 :
- B5 (MCP pin 13 dans la lib = pin `13`) → cable volant vers U4 pin 1 (ENA moteur X)
- A5 (MCP pin 5 dans la lib = pin `5`) → cable volant vers U3 pin 1 (ENA moteur Y)

```cpp
#define MOT_X_ENA  13  // B5
#define MOT_Y_ENA  5   // A5

void moteurs_enable(bool enable) {
    // ENA est actif LOW : LOW = enabled, HIGH = disabled
    mcp.digitalWrite(MOT_X_ENA, enable ? LOW : HIGH);
    mcp.digitalWrite(MOT_Y_ENA, enable ? LOW : HIGH);
}
```

### Servo bruit d'alimentation

**Solution hardware** : Ajouter un condensateur electrolytique de **470 µF** entre le 5V et GND du servo, le plus pres possible du connecteur du servo. Cela absorbe les pics de courant.

---

## Ordre de priorite des corrections

| Priorite | Action | Type | Temps estime |
|----------|--------|------|-------------|
| 1 | Verifier continuite +5V/5V au multimetre | Test | 5 min |
| 2 | Recabler LEDs (IO34 → IO32) | Hardware | 15 min |
| 3 | Recabler Servo (IO35 → IO33) | Hardware | 15 min |
| 4 | Corriger pont +5V/5V si necessaire | Hardware | 10 min |
| 5 | Pull-down 10kΩ sur GPIO12 | Hardware | 5 min |
| 6 | Pull-up 10kΩ sur GPIO0 | Hardware | 5 min |
| 7 | Condensateur 470µF sur servo 5V | Hardware | 5 min |
| 8 | Code ESP32 avec bons pins et registres | Software | -- |
