# Reference PCB -- Mapping complet des connexions

Genere a partir de la netlist `Sheet_1_2026-03-31.net` et du schema `Schematic_mecatronique_2026-03-31.pdf`.
PCB concu sur EasyEDA par jeanrdc (2026-02-16).

---

## Architecture materielle

```
[Raspberry Pi 3/4]  <--UART TX/RX-->  [ESP32-WROVER-Dev]  <--I2C-->  [MCP23017]
        |                                   |                            |
    IA + moteur jeu                    Controleur HW              Expandeur GPIO
                                            |                     |          |
                                    +-------+-------+        [A4988 X]  [A4988 Y]
                                    |       |       |            |          |
                                  LEDs  Boutons  Servo        Nema17     Nema17
                                 (H1)  (H3+H4)  SG90          (U7)       (U8)
```

---

## Composants (BOM)

| Ref | Composant | Footprint | Qty | Role |
|-----|-----------|-----------|-----|------|
| U1 | ESP32-WROVER-Dev Freenove v1.6 | 40 pins | 1 | Controleur principal |
| U6 | MCP23017 (Adafruit) | 26 pins | 1 | Expandeur I2C 16 GPIO |
| U3 | A4988 Driver | 16 pins | 1 | Driver stepper moteur 2 (axe Y) |
| U4 | A4988 Driver | 16 pins | 1 | Driver stepper moteur 1 (axe X) |
| U7 | Nema 17 Stepper Motor | 4 pins | 1 | Moteur axe X |
| U8 | Nema 17 Stepper Motor | 4 pins | 1 | Moteur axe Y |
| U2 | Servo SG90 | 3 pins | 1 | Piston (levee des murs) |
| C | Condensateur 10uF | 2 pins | 1 | Decouplage alim 12V |
| H1 | Connecteur femelle 1x8 | 8 pins | 1 | LEDs + Supp |
| H2 | Connecteur femelle 1x8 | 8 pins | 1 | Alimentation (+12V, +5V, GND) |
| H3 | Connecteur femelle 1x8 | 8 pins | 1 | Boutons lignes (matrice) |
| H4 | Connecteur femelle 1x8 | 8 pins | 1 | Boutons colonnes (matrice) |

---

## Mapping ESP32 pins -> Fonctions

Source : netlist (U1 = ESP32, pin numbering Freenove WROVER-Dev v1.6)

### Cote gauche (pins 1-20)

| Pin | GPIO ESP32 | Signal net | Fonction |
|-----|-----------|------------|----------|
| 1 | 3V3 | - | Alimentation 3.3V |
| 2 | EN | - | Enable (reset) |
| 3 | VP (GPIO36) | - | Non connecte |
| 4 | VN (GPIO39) | - | Non connecte |
| 5 | IO34 | LED | Signal data LEDs (H1.4) |
| 6 | IO35 | SERVOMOT | Signal PWM servo SG90 (U2.2) |
| 7 | IO32 | SUPP1 | Spare (H1.5) |
| 8 | IO33 | SUPP2 | Spare (H1.6) |
| 9 | IO25 | BOUTON12 | Matrice boutons - ligne 6 (H3.8) |
| 10 | IO26 | BOUTON11 | Matrice boutons - ligne 5 (H3.7) |
| 11 | IO27 | BOUTON10 | Matrice boutons - ligne 4 (H3.6) |
| 12 | IO14 | BOUTON9 | Matrice boutons - ligne 3 (H3.5) |
| 13 | IO12 | BOUTON8 | Matrice boutons - ligne 2 (H3.4) |
| 14 | GND | GND | Masse |
| 15 | IO13 | BOUTON7 | Matrice boutons - ligne 1 (H3.3) |
| 16 | SD2 | - | Flash SPI (ne pas utiliser) |
| 17 | SD3 | - | Flash SPI (ne pas utiliser) |
| 18 | CMD | - | Flash SPI (ne pas utiliser) |
| 19 | VCC | - | Alimentation 5V (USB) |
| 20 | VCC | - | Alimentation 5V (USB) |

### Cote droit (pins 21-40)

| Pin | GPIO ESP32 | Signal net | Fonction |
|-----|-----------|------------|----------|
| 21 | GND | GND | Masse |
| 22 | IO23 | SUPP3 | Spare (H1.8) |
| 23 | IO22 | SCL | I2C Clock -> MCP23017 (U6.16) |
| 24 | TX (GPIO1) | TX | UART TX -> Raspberry Pi RX |
| 25 | RX (GPIO3) | RX | UART RX -> Raspberry Pi TX |
| 26 | IO21 | SDA | I2C Data -> MCP23017 (U6.17) |
| 27 | GND | GND | Masse |
| 28 | IO19 | SUPP4 | Spare (H1.7) |
| 29 | IO18 | BOUTON6 | Matrice boutons - colonne 6 (H4.8) |
| 30 | IO5 | BOUTON5 | Matrice boutons - colonne 5 (H4.7) |
| 31 | GND | GND | Masse |
| 32 | GND | GND | Masse |
| 33 | IO4 | BOUTON4 | Matrice boutons - colonne 4 (H4.6) |
| 34 | IO0 | BOUTON3 | Matrice boutons - colonne 3 (H4.5) |
| 35 | IO2 | BOUTON2 | Matrice boutons - colonne 2 (H4.4) |
| 36 | IO15 | BOUTON1 | Matrice boutons - colonne 1 (H4.3) |
| 37 | SD1 | - | Flash SPI (ne pas utiliser) |
| 38 | SD0 | - | Flash SPI (ne pas utiliser) |
| 39 | CLK | - | Flash SPI (ne pas utiliser) |
| 40 | GND | GND | Masse |

### Resume GPIO ESP32

| Fonction | GPIOs | Nombre |
|----------|-------|--------|
| Matrice colonnes (H4) | IO15, IO2, IO0, IO4, IO5, IO18 | 6 |
| Matrice lignes (H3) | IO13, IO12, IO14, IO27, IO26, IO25 | 6 |
| I2C (MCP23017) | IO22 (SCL), IO21 (SDA) | 2 |
| UART (Raspberry Pi) | TX (GPIO1), RX (GPIO3) | 2 |
| LEDs | IO34 | 1 |
| Servo SG90 | IO35 | 1 |
| Spare | IO32, IO33, IO23, IO19 | 4 |
| **Total utilises** | | **18** |

---

## Mapping MCP23017 (U6) -> Drivers moteurs

Le MCP23017 communique en I2C avec l'ESP32 et controle les 2 drivers A4988.

### Port A (pins GPA0-GPA7 = pins 21-28 du chip, mais ici pins 1-8 du module Adafruit)

| Pin module | Signal net | Destination | Fonction |
|-----------|------------|-------------|----------|
| U6.9 | MS1_1 | U4.2 (A4988 #1) | Microstep bit 1 moteur X |
| U6.10 | MS2_1 | U4.3 (A4988 #1) | Microstep bit 2 moteur X |
| U6.11 | MS3_1 | U4.4 (A4988 #1) | Microstep bit 3 moteur X |
| U6.12 | STEP_MOT1 | U4.7 (A4988 #1) | Impulsion pas moteur X |
| U6.13 | DIR_MOT1 | U4.8 (A4988 #1) | Direction moteur X |

### Port B

| Pin module | Signal net | Destination | Fonction |
|-----------|------------|-------------|----------|
| U6.19 | DIR_MOT2 | U3.8 (A4988 #2) | Direction moteur Y |
| U6.20 | STEP_MOT2 | U3.7 (A4988 #2) | Impulsion pas moteur Y |
| U6.21 | MS3_2 | U3.4 (A4988 #2) | Microstep bit 3 moteur Y |
| U6.22 | MS2_2 | U3.3 (A4988 #2) | Microstep bit 2 moteur Y |
| U6.23 | MS1_2 | U3.2 (A4988 #2) | Microstep bit 1 moteur Y |

### Pins MCP23017 non connectes (selon netlist)

Pins du port B : B2-B7 (U6 pins 14-18 selon mapping) -> 6 GPIO libres.

---

## Drivers A4988 -> Moteurs Nema 17

### U4 (A4988 #1) -> U7 (Nema 17 axe X)

| Pin A4988 | Signal | Connexion |
|-----------|--------|-----------|
| U4.2 | MS1 | MS1_1 (via MCP23017) |
| U4.3 | MS2 | MS2_1 (via MCP23017) |
| U4.4 | MS3 | MS3_1 (via MCP23017) |
| U4.5-6 | RST-SLP | Lies ensemble (mode actif) |
| U4.7 | STEP | STEP_MOT1 (via MCP23017) |
| U4.8 | DIR | DIR_MOT1 (via MCP23017) |
| U4.9 | GND | GND |
| U4.10 | VDD | 5V |
| U4.11 | 1B | U7.1B |
| U4.12 | 1A | U7.1A |
| U4.13 | 2A | U7.2A |
| U4.14 | 2B | U7.2B |
| U4.15 | GND | GND (moteur) |
| U4.16 | VMOT | +12V |

### U3 (A4988 #2) -> U8 (Nema 17 axe Y)

Meme schema que U4, avec signaux _MOT2 et moteur U8.

---

## Alimentation

| Rail | Source | Composants alimentes |
|------|--------|---------------------|
| USB 5V | Port USB ESP32 | ESP32 uniquement |
| +5V (H2.4) | Alimentation externe | Servo SG90, MCP23017, A4988 VDD, LEDs (H1.3) |
| +12V (H2.3) | Alimentation externe | A4988 VMOT (U3.16, U4.16), condensateur 10uF |
| GND | Commun | Tous les composants |

---

## Connecteurs

### H1 - LEDs + Spare (1x8 femelle)

| Pin | Signal | Connexion |
|-----|--------|-----------|
| H1.1 | - | Non connecte |
| H1.2 | GND | Masse |
| H1.3 | 5V | Alimentation LEDs |
| H1.4 | LED | ESP32 IO34 (data LEDs) |
| H1.5 | SUPP1 | ESP32 IO32 (spare) |
| H1.6 | SUPP2 | ESP32 IO33 (spare) |
| H1.7 | SUPP4 | ESP32 IO19 (spare) |
| H1.8 | SUPP3 | ESP32 IO23 (spare) |

### H2 - Alimentation externe (1x8 femelle)

| Pin | Signal |
|-----|--------|
| H2.1-2 | Non connecte |
| H2.3 | +12V |
| H2.4 | +5V |
| H2.5 | Non connecte |
| H2.6-8 | GND |

### H3 - Boutons lignes (1x8 femelle)

| Pin | Signal | ESP32 GPIO |
|-----|--------|-----------|
| H3.1-2 | Non connecte | - |
| H3.3 | BOUTON7 (ligne 1) | IO13 |
| H3.4 | BOUTON8 (ligne 2) | IO12 |
| H3.5 | BOUTON9 (ligne 3) | IO14 |
| H3.6 | BOUTON10 (ligne 4) | IO27 |
| H3.7 | BOUTON11 (ligne 5) | IO26 |
| H3.8 | BOUTON12 (ligne 6) | IO25 |

### H4 - Boutons colonnes (1x8 femelle)

| Pin | Signal | ESP32 GPIO |
|-----|--------|-----------|
| H4.1-2 | Non connecte | - |
| H4.3 | BOUTON1 (col 1) | IO15 |
| H4.4 | BOUTON2 (col 2) | IO2 |
| H4.5 | BOUTON3 (col 3) | IO0 |
| H4.6 | BOUTON4 (col 4) | IO4 |
| H4.7 | BOUTON5 (col 5) | IO5 |
| H4.8 | BOUTON6 (col 6) | IO18 |

---

## Matrice boutons 6x6

Colonnes (OUTPUT, H4) scannees par l'ESP32, lignes (INPUT, H3) lues.

```
          Col1    Col2    Col3    Col4    Col5    Col6
          IO15    IO2     IO0     IO4     IO5     IO18
           |       |       |       |       |       |
Lig1 IO13--[1,1]--[1,2]--[1,3]--[1,4]--[1,5]--[1,6]
Lig2 IO12--[2,1]--[2,2]--[2,3]--[2,4]--[2,5]--[2,6]
Lig3 IO14--[3,1]--[3,2]--[3,3]--[3,4]--[3,5]--[3,6]
Lig4 IO27--[4,1]--[4,2]--[4,3]--[4,4]--[4,5]--[4,6]
Lig5 IO26--[5,1]--[5,2]--[5,3]--[5,4]--[5,5]--[5,6]
Lig6 IO25--[6,1]--[6,2]--[6,3]--[6,4]--[6,5]--[6,6]
```

---

## Problemes potentiels identifies

1. **STEP via I2C (MCP23017)** : Les signaux STEP des moteurs passent par le bus I2C (100-400 kHz). Generer des impulsions rapides et regulieres pour les steppers via I2C ajoute de la latence. Peut limiter la vitesse max des moteurs.

2. **IO0 utilise pour BOUTON3** : GPIO0 est un pin de boot sur ESP32. S'il est LOW au demarrage, l'ESP32 entre en mode programmation. Il faut une pull-up externe ou s'assurer que le bouton n'est pas presse au boot.

3. **IO34 pour LEDs** : GPIO34 est un pin **input-only** sur ESP32. Il ne peut PAS generer de signal de sortie. Si les LEDs sont des NeoPixels (WS2812), ce pin ne fonctionnera pas.

4. **IO35 pour Servo** : GPIO35 est aussi **input-only** sur ESP32. Il ne peut PAS generer de signal PWM. Le servo SG90 ne fonctionnera pas sur ce pin.

5. **IO2 pour BOUTON2** : GPIO2 est le pin de la LED interne et a un comportement special au boot. Peut causer des problemes si tire LOW au demarrage.

6. **Pas de resistances pull-up/pull-down** visibles pour la matrice de boutons sur le schema. Necessaires pour eviter les lectures flottantes.

7. **Alimentation servo 5V sur meme rail que logique** : Le SG90 peut tirer des pics de courant qui perturbent l'alimentation du MCP23017 et des A4988.
