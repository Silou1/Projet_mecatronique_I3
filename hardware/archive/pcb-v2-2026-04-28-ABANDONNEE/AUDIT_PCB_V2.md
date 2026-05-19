# Audit PCB v2 -- Quoridor Interactif

> **Date de l'audit** : 2026-04-14
> **PCB audite** : `PCB_PCB_mecatronique_2026-04-14 (2).json` (EasyEDA, corrige par jeanrdc)
> **Sources** : fichier JSON PCB EasyEDA, ancien audit v1, pinout Freenove ESP32-WROOM
>
> **Composant ESP32** : Le composant EasyEDA est bien libelle "Freenove ESP32 WROOM" (U10).

---

## Synthese des anomalies

| # | Severite | Composant | Probleme | Impact |
|---|----------|-----------|----------|--------|
| 1 | **A VERIFIER** | Pin 27 (LED) | GPIO reel a confirmer (IO35 input-only ou IO25 output) | LEDs potentiellement inutilisables |
| 2 | **CORRIGE** | Pin 28 (Servo) | Maintenant sur IO32 (PWM capable) | Servo fonctionne |
| 3 | **CORRIGE** | Net 5V | H2 pin 4 est sur le net "5V" (unifie) | Alimentation OK |
| 4 | **DEPLACE** | GPIO0 (BOUTON1) | Strapping pin toujours dans la matrice | Boot mode si bouton appuye |
| 5 | **CORRIGE** | GPIO12 | Pin 34 non connectee (retire de la matrice) | Plus de risque flash 1.8V |
| 6 | **SERIEUX** | IO16/IO17 (BOUTON3/4) | UART2 consomme par la matrice | Plus de UART2 pour RPi |
| 7 | PERSISTE | A4988 ENABLE | Non connecte | Moteurs toujours alimentes |
| 8 | PERSISTE | Matrice boutons | Pas de pull-up externe | Depends de INPUT_PULLUP |
| 9 | **NOUVEAU** | Condensateur C | Polarite possiblement inversee dans le schema | Risque de defaillance |

---

## Changements par rapport a l'ancien PCB

### Corrections confirmees

1. **Net 5V unifie** : H2 pin 4 est maintenant sur le net `5V` (pas `+5`). Les tracks montrent
   une connexion continue entre H2.4, H1.3, U6 VIN (MCP23017), U3/U4 VDD (A4988), U2.3 (servo)
   et l'ESP32. **Probleme #3 de l'ancien audit resolu.**

2. **Servo (SERVOMOT) deplace sur pin 28** : Correspond a **IO32** sur le mapping Freenove standard.
   IO32 supporte output et PWM (canal LEDC). **Probleme #2 de l'ancien audit resolu.**

3. **GPIO12 retire de la matrice** : Pin 34 du U10 (IO12, strapping pin) est non connectee.
   **Probleme #6 de l'ancien audit resolu.**

4. **GPIO2 et GPIO15 probablement retires** : Pins 15 et 16 semblent non connectees.
   **Problemes #5 et #7 partiellement resolus** (a confirmer).

### Problemes non resolus ou deplaces

5. **LED toujours potentiellement sur input-only** : Le signal LED est sur U10 pin 27.
   Selon le mapping Freenove DevKitC 40-pin standard, pin 27 = IO35 (input-only).
   MAIS selon un mapping alternatif, pin 27 = IO25 (output capable).
   **A VERIFIER PHYSIQUEMENT - voir procedure ci-dessous.**

6. **GPIO0 toujours dans la matrice** : Deplace de BOUTON3 a BOUTON1 (pin 14). Le risque
   de boot mode accidentel persiste avec un bouton different.

---

## Detail des anomalies

### A VERIFIER : LED (pin 27) -- GPIO reel ?

Le signal `LED` est route de U10 pin 27 vers H1 pin 4 via des tracks sur la couche top :
```
U10.27 → track LED → H1.4
```

**Deux scenarios possibles :**

| Scenario | GPIO pin 27 | LED fonctionne ? | Action |
|----------|-------------|-------------------|--------|
| A (standard DevKitC) | IO35 | **NON** (input-only) | Fil volant depuis IO23 ou IO19 |
| B (alternatif) | IO25 | **OUI** (output capable) | Aucune correction necessaire |

**Procedure de verification :**
```cpp
void setup() {
  Serial.begin(115200);
  // Test GPIO25 : si un signal apparait sur le pad pin 27 de U10, c'est IO25
  pinMode(25, OUTPUT);
  digitalWrite(25, HIGH);
  delay(1000);
  digitalWrite(25, LOW);
  delay(1000);
  // Test GPIO35 : ne devrait PAS produire de signal (input-only)
  // mais si la pin 27 reagit avec le test ci-dessus, on sait que c'est IO25
}
```

### SERIEUX : IO16/IO17 dans la matrice boutons

BOUTON3 est sur pin 12 (probable IO16) et BOUTON4 sur pin 11 (probable IO17).

**Consequence** : GPIO16 et GPIO17 sont les pins par defaut de UART2 (Serial2).
L'avantage principal du WROOM sur le WROVER (disponibilite de UART2 pour le RPi)
est **perdu** si ces GPIO sont utilises pour les boutons.

**Options :**
1. Rester sur UART0 (GPIO1/3) pour le RPi -- debrancher USB pendant fonctionnement
2. Remapper UART2 sur d'autres GPIO via `Serial2.begin(baud, config, rxPin, txPin)` --
   mais les GPIO disponibles sont limites
3. Dans une future revision du PCB, deplacer BOUTON3/4 sur d'autres GPIO

### NOUVEAU : Condensateur C -- Polarite

Le JSON indique pour le condensateur 10uF :
- Pin 1 (marque `+`) = net `GND`
- Pin 2 = net `+12`

Si c'est un electrolytique, le `+` devrait etre sur `+12V` et le `-` sur GND.
**Verifier l'orientation physique du condensateur sur le PCB.**

---

## Mapping des composants -- Nouveau PCB

### ESP32-WROOM (U10) -- Mapping probable

**Cote droit (pins 1-20) :**

| Pin | GPIO probable | Net | Fonction | Notes |
|-----|--------------|-----|----------|-------|
| 1 | GND | GND | Masse | OK |
| 2 | IO23 | SUPP3 | Spare → H1.8 | Output capable |
| 3 | IO22 | SCL | I2C Clock → MCP23017 | OK |
| 4 | IO1 (TXD0) | -- | Non connecte | USB debug TX |
| 5 | IO3 (RXD0) | -- | Non connecte | USB debug RX |
| 6 | IO21 | SDA | I2C Data → MCP23017 | OK |
| 7 | GND | -- | Non connecte | |
| 8 | IO19 | SUPP4 | Spare → H1.7 | Output capable |
| 9 | IO18 | BOUTON6 | Col 6 → H4.8 | OK |
| 10 | IO5 | BOUTON5 | Col 5 → H4.7 | OK |
| 11 | **IO17** | BOUTON4 | Col 4 → H4.6 | **UART2 TX perdu** |
| 12 | **IO16** | BOUTON3 | Col 3 → H4.5 | **UART2 RX perdu** |
| 13 | IO4 | BOUTON2 | Col 2 → H4.4 | OK |
| 14 | **IO0** | BOUTON1 | Col 1 → H4.3 | **Strapping!** Pull-up requise |
| 15 | IO2 | -- | Non connecte | Strapping retire, bon |
| 16 | IO15 | -- | Non connecte | Strapping retire, bon |
| 17-20 | Flash SPI | -- | Non connecte | Reserve |

**Cote gauche (pins 21-40) :**

| Pin | GPIO probable | Net | Fonction | Notes |
|-----|--------------|-----|----------|-------|
| 21-24 | VIN/3V3/EN/VP | -- | Non connecte | Alim/reset |
| 25 | IO39 ou IO32 | SUPP1 | Spare → H1.5 | **A verifier** |
| 26 | IO34 ou IO33 | SUPP2 | Spare → H1.6 | **A verifier** |
| 27 | **IO35 ou IO25** | **LED** | Data LEDs → H1.4 | **CRITIQUE a verifier** |
| 28 | IO32 | SERVOMOT | PWM Servo → U2.2 | OK |
| 29 | IO33 | BOUTON12 | Lig 6 → H3.8 | OK |
| 30 | IO25 | BOUTON11 | Lig 5 → H3.7 | OK |
| 31 | IO26 | BOUTON10 | Lig 4 → H3.6 | OK |
| 32 | IO27 | BOUTON9 | Lig 3 → H3.5 | OK |
| 33 | IO14 | BOUTON8 | Lig 2 → H3.4 | OK |
| 34 | IO12 | -- | Non connecte | Strapping retire |
| 35 | IO13 | BOUTON7 | Lig 1 → H3.3 | OK |
| 36-40 | Divers | -- | Non connecte | OK |

### Connecteurs

**H1 (LEDs + spare) :**
| Pin | Net | Fonction |
|-----|-----|----------|
| 1 | H1_1 | Non connecte |
| 2 | GND | Masse |
| 3 | 5V | Alimentation |
| 4 | LED | Data WS2812B |
| 5 | SUPP1 | Spare (IO39 ou IO32) |
| 6 | SUPP2 | Spare (IO34 ou IO33) |
| 7 | SUPP4 | Spare (IO19) |
| 8 | SUPP3 | Spare (IO23) |

**H2 (alimentation externe) :**
| Pin | Net | Fonction |
|-----|-----|----------|
| 1 | H2_1 | Non connecte |
| 2 | H2_2 | Non connecte |
| 3 | +12 | Alimentation moteurs |
| 4 | **5V** | Alimentation 5V (meme net que composants) |
| 5 | H2_5 | Non connecte |
| 6 | GND | Masse |
| 7 | GND | Masse |
| 8 | GND | Masse |

**H3 (lignes boutons) :** Pins 3-8 = BOUTON7 a BOUTON12
**H4 (colonnes boutons) :** Pins 3-8 = BOUTON1 a BOUTON6
**H5/H6/H7 :** Connecteurs moteurs pas-a-pas (paires de fils)

### MCP23017 (U6) -- Identique a l'ancien PCB

Port A (moteur Y) : DIR_MOT2, STEP_MOT2, MS3_2, MS2_2, MS1_2
Port B (moteur X) : DIR_MOT1, STEP_MOT1, MS3_1, MS2_1, MS1_1

### A4988 (U3, U4) -- Identique

RST lie a SLP, ENA non connecte, VDD=5V, VMOT=+12V.

---

## Plan d'action prioritaire

### Priorite 0 : Verifier le GPIO de la pin 27 (LED)

**AVANT TOUTE FABRICATION**, tester sur la carte physique quel GPIO correspond
a la pin 27 de U10. Si IO35, prevoir un fil volant.

### Priorite 1 : Pull-up sur GPIO0 (BOUTON1)

Ajouter 10kΩ entre le signal BOUTON1 et 3.3V pour eviter le mode download
accidentel au boot.

### Priorite 2 : Verifier orientation condensateur C

S'assurer que le `+` est sur +12V et le `-` sur GND.

### Priorite 3 : Adapter le code ESP32

Mettre a jour les `#define` pour correspondre au nouveau mapping.
Voir section "Defines pour le code" ci-dessous.

---

## Defines pour le code ESP32

```cpp
// ===== NOUVEAU PCB v2 -- PIN DEFINITIONS (A CONFIRMER PIN 27) =====

// --- Matrice boutons ---
// Colonnes (OUTPUT, active LOW)
#define COL_1   0  // IO0  - pin14 - STRAPPING! pull-up 10k requise
#define COL_2   4  // IO4  - pin13
#define COL_3  16  // IO16 - pin12 - ATTENTION: UART2 RX par defaut
#define COL_4  17  // IO17 - pin11 - ATTENTION: UART2 TX par defaut
#define COL_5   5  // IO5  - pin10
#define COL_6  18  // IO18 - pin9

// Lignes (INPUT_PULLUP)
#define LIG_1  13  // IO13 - pin35
#define LIG_2  14  // IO14 - pin33
#define LIG_3  27  // IO27 - pin32
#define LIG_4  26  // IO26 - pin31
#define LIG_5  25  // IO25 - pin30
#define LIG_6  33  // IO33 - pin29

// --- LEDs WS2812B ---
// OPTION A (si pin 27 = IO25) : #define PIN_LED_DATA 25
// OPTION B (si pin 27 = IO35, fil volant vers IO23) : #define PIN_LED_DATA 23
#define PIN_LED_DATA  25  // A CONFIRMER -- tester physiquement
#define NUM_LEDS      36  // 6x6 plateau

// --- Servo SG90 ---
#define PIN_SERVO     32  // IO32 - pin28 - PWM capable, CONFIRME

// --- I2C (MCP23017) ---
#define PIN_SDA       21  // IO21 - pin6
#define PIN_SCL       22  // IO22 - pin3
#define MCP23017_ADDR 0x20

// --- MCP23017 : Moteur Y (Port A) --- inchange
#define MOT_Y_DIR    0   // A0
#define MOT_Y_STEP   1   // A1
#define MOT_Y_MS3    2   // A2
#define MOT_Y_MS2    3   // A3
#define MOT_Y_MS1    4   // A4

// --- MCP23017 : Moteur X (Port B) --- inchange
#define MOT_X_DIR    8   // B0
#define MOT_X_STEP   9   // B1
#define MOT_X_MS3   10   // B2
#define MOT_X_MS2   11   // B3
#define MOT_X_MS1   12   // B4

// --- UART (Raspberry Pi) ---
// UART2 NON DISPONIBLE (IO16/IO17 dans la matrice boutons)
// Utiliser UART0 (GPIO1/3) -- partage avec USB debug
#define UART_BAUD     115200
```

### Correspondance matrice → plateau de jeu (nouveau PCB)

```
             Col1(IO0)  Col2(IO4)  Col3(IO16) Col4(IO17) Col5(IO5)  Col6(IO18)
Lig1(IO13)    [0,0]      [0,1]      [0,2]      [0,3]      [0,4]      [0,5]
Lig2(IO14)    [1,0]      [1,1]      [1,2]      [1,3]      [1,4]      [1,5]
Lig3(IO27)    [2,0]      [2,1]      [2,2]      [2,3]      [2,4]      [2,5]
Lig4(IO26)    [3,0]      [3,1]      [3,2]      [3,3]      [3,4]      [3,5]
Lig5(IO25)    [4,0]      [4,1]      [4,2]      [4,3]      [4,4]      [4,5]
Lig6(IO33)    [5,0]      [5,1]      [5,2]      [5,3]      [5,4]      [5,5]
```

---

## Comparaison ancien vs nouveau PCB

| Aspect | Ancien PCB | Nouveau PCB | Statut |
|--------|-----------|-------------|--------|
| LED GPIO | IO34 (input-only) | IO35 ou IO25 (a verifier) | A verifier |
| Servo GPIO | IO35 (input-only) | IO32 (PWM OK) | **Corrige** |
| Net 5V | "+5" vs "5V" (deconnecte) | "5V" unifie | **Corrige** |
| GPIO12 (strapping) | Dans matrice (BOUTON8) | Non connecte | **Corrige** |
| GPIO0 (strapping) | BOUTON3 | BOUTON1 | Deplace |
| GPIO2 (strapping) | BOUTON2 | Non connecte | **Corrige** |
| GPIO15 (strapping) | BOUTON1 | Non connecte | **Corrige** |
| UART2 (IO16/17) | Libres | Dans matrice | **Regression** |
| A4988 ENABLE | Non connecte | Non connecte | Inchange |
| Condensateur | 10uF sur +12V | Meme, polarite a verifier | A verifier |
