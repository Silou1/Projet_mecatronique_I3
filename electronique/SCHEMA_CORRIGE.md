# Schema electrique corrige -- Quoridor Interactif

> Version corrigee du schema `Schematic_mecatronique_2026-03-31.pdf`.
> Les modifications par rapport a l'original sont marquees avec (**CORRIGE**).
>
> Ce schema sert de reference visuelle en attendant la mise a jour EasyEDA.

---

## Vue d'ensemble

```
                                 ALIMENTATION
                                 ============
                            +12V ──┐    +5V ──┐
                                   │          │
                              C 10uF     (CORRIGE: net
                                   │      unifie "5V")
                                   │          │
    ┌──────────────────────────────────────────────────────────────────┐
    │                                                                  │
    │   ┌─────────┐    I2C     ┌───────────┐     ┌─────────┐         │
    │   │  ESP32   │◄─────────►│ MCP23017  │────►│ A4988 X │──► Nema17 X (U7)
    │   │  WROOM   │  SDA/SCL  │   (U6)    │    │  (U4)   │
    │   │  (U1)    │           │ addr 0x20 │    └─────────┘         │
    │   │          │           │           │     ┌─────────┐         │
    │   │ *CORRIGE*│           │           │────►│ A4988 Y │──► Nema17 Y (U8)
    │   └────┬─────┘           └───────────┘     │  (U3)   │
    │        │                                    └─────────┘         │
    │   ┌────┴──────────────────────────┐                             │
    │   │           │          │        │                             │
    │   ▼           ▼          ▼        ▼                             │
    │ Boutons    LEDs      Servo    UART RPi                         │
    │ 6x6       IO32*     IO33*    TX/RX                             │
    │ matrice   *CORRIGE*  *CORRIGE*                                  │
    └──────────────────────────────────────────────────────────────────┘
```

---

## ESP32-WROOM (U1) -- Brochage corrige

```
                    ESP32-WROOM Freenove
                    (**CORRIGE** : etait WROVER)
              ┌──────────────────────────────┐
              │            USB               │
              │         ┌───────┐            │
              │         │       │            │
     3V3  [1] ├─        │       │        ─┤ [40] GND
      EN  [2] ├─        └───────┘        ─┤ [39] CLK
VP/IO36   [3] ├─ (non connecte)          ─┤ [38] SD0
VN/IO39   [4] ├─ (non connecte)          ─┤ [37] SD1
              │                             │
   IO34   [5] ├─ ~~LED~~  (ANCIEN, input-only, deconnecte)
              │   (**CORRIGE** : plus rien sur IO34)
              │                             │
   IO35   [6] ├─ ~~SERVO~~ (ANCIEN, input-only, deconnecte)
              │   (**CORRIGE** : plus rien sur IO35)
              │                          ─┤ [36] IO15 ── BOUTON1 (col 1) ──► H4.3
   IO32   [7] ├─ LED ──────────────► H1.4  │
              │   (**CORRIGE** : LED deplacee ici)
              │                          ─┤ [35] IO2  ── BOUTON2 (col 2) ──► H4.4
   IO33   [8] ├─ SERVOMOT ─────────► U2.2  │
              │   (**CORRIGE** : servo deplace ici)
              │                          ─┤ [34] IO0  ── BOUTON3 (col 3) ──► H4.5
   IO25   [9] ├─ BOUTON12 (lig 6) ► H3.8   │           ⚠ strapping boot
   IO26  [10] ├─ BOUTON11 (lig 5) ► H3.7 ─┤ [33] IO4  ── BOUTON4 (col 4) ──► H4.6
   IO27  [11] ├─ BOUTON10 (lig 4) ► H3.6   │
   IO14  [12] ├─ BOUTON9  (lig 3) ► H3.5   │
   IO12  [13] ├─ BOUTON8  (lig 2) ► H3.4 ─┤ [32] GND
              │   ⚠ strapping flash volt    │
     GND [14] ├─ GND                     ─┤ [31] GND
   IO13  [15] ├─ BOUTON7  (lig 1) ► H3.3   │
     SD2 [16] ├─ (flash, ne pas utiliser)  ─┤ [30] IO5  ── BOUTON5 (col 5) ──► H4.7
     SD3 [17] ├─ (flash, ne pas utiliser)  ─┤ [29] IO18 ── BOUTON6 (col 6) ──► H4.8
     CMD [18] ├─ (flash, ne pas utiliser)  ─┤ [28] IO19 ── SUPP4 ──► H1.7 (spare)
     VCC [19] ├─ 5V USB                   ─┤ [27] GND
     VCC [20] ├─ 5V USB                   ─┤ [26] IO21 ── SDA ──► MCP23017 U6.17
              │                          ─┤ [25] RX/IO3 ◄── RPi TX
     GND [21] ├─ GND                     ─┤ [24] TX/IO1 ──► RPi RX
   IO23  [22] ├─ SUPP3 ──► H1.8 (spare)  ─┤ [23] IO22 ── SCL ──► MCP23017 U6.16
              │                             │
              └──────────────────────────────┘

    GPIO16 ── UART2 RX (disponible sur WROOM, non route sur PCB)
    GPIO17 ── UART2 TX (disponible sur WROOM, non route sur PCB)
```

---

## MCP23017 (U6) -- Expandeur I2C → Drivers moteurs

```
                    MCP23017 Adafruit
                    Adresse I2C : 0x20
              ┌──────────────────────────────┐
              │                              │
      IA  [1] ├─ (non connecte)             │
      IB  [2] ├─ (non connecte)             │
      D0  [3] ├─ (pull-down = addr bit 0)   │
      D1  [4] ├─ (pull-down = addr bit 1)   │
      D2  [5] ├─ (pull-down = addr bit 2)   │
              │                              │
              │    PORT B → MOTEUR X (U4)    │
              │  (**CORRIGE** : etait appele  │
              │   "Port A" dans la doc)       │
      B7  [6] ├─ (libre)                    │
      B6  [7] ├─ (libre)                    │
      B5  [8] ├─ (libre, candidat ENA X)    │
      B4  [9] ├─ MS1_1 ──────────► U4.2     │
     B3  [10] ├─ MS2_1 ──────────► U4.3     │
     B2  [11] ├─ MS3_1 ──────────► U4.4     │
     B1  [12] ├─ STEP_MOT1 ──────► U4.7     │
     B0  [13] ├─ DIR_MOT1 ───────► U4.8     │
              │                              │
     VIN [14] ├─ 5V                          │
     GND [15] ├─ GND                         │
     SCL [16] ├─◄── IO22 (ESP32)            │
     SDA [17] ├─◄── IO21 (ESP32)            │
     RST [18] ├─ (pull-up interne, OK)      │
              │                              │
              │    PORT A → MOTEUR Y (U3)    │
              │  (**CORRIGE** : etait appele  │
              │   "Port B" dans la doc)       │
     A0  [19] ├─ DIR_MOT2 ───────► U3.8     │
     A1  [20] ├─ STEP_MOT2 ──────► U3.7     │
     A2  [21] ├─ MS3_2 ──────────► U3.4     │
     A3  [22] ├─ MS2_2 ──────────► U3.3     │
     A4  [23] ├─ MS1_2 ──────────► U3.2     │
     A5  [24] ├─ (libre, candidat ENA Y)    │
     A6  [25] ├─ (libre)                    │
     A7  [26] ├─ (libre)                    │
              │                              │
              └──────────────────────────────┘
```

---

## A4988 Drivers + Moteurs Nema 17

```
    A4988 #1 (U4) -- MOTEUR X                A4988 #2 (U3) -- MOTEUR Y
    Controle via MCP23017 Port B              Controle via MCP23017 Port A

    ┌────────────────────┐                    ┌────────────────────┐
    │                    │                    │                    │
    │ ENA  [1]  (NC/LOW) │                    │ ENA  [1]  (NC/LOW) │
    │ MS1  [2] ◄── B4   │                    │ MS1  [2] ◄── A4   │
    │ MS2  [3] ◄── B3   │                    │ MS2  [3] ◄── A3   │
    │ MS3  [4] ◄── B2   │                    │ MS3  [4] ◄── A2   │
    │ RST  [5] ─┐       │                    │ RST  [5] ─┐       │
    │ SLP  [6] ─┘       │                    │ SLP  [6] ─┘       │
    │ STEP [7] ◄── B1   │                    │ STEP [7] ◄── A1   │
    │ DIR  [8] ◄── B0   │                    │ DIR  [8] ◄── A0   │
    │ GND  [9]  GND     │                    │ GND  [9]  GND     │
    │ VDD [10]  5V      │                    │ VDD [10]  5V      │
    │ 1B  [11] ──► U7.1B│                    │ 1B  [11] ──► U8.1B│
    │ 1A  [12] ──► U7.1A│                    │ 1A  [12] ──► U8.1A│
    │ 2A  [13] ──► U7.2A│                    │ 2A  [13] ──► U8.2A│
    │ 2B  [14] ──► U7.2B│                    │ 2B  [14] ──► U8.2B│
    │ GND [15]  GND     │                    │ GND [15]  GND     │
    │ VMOT[16]  +12V    │                    │ VMOT[16]  +12V    │
    │                    │                    │                    │
    └────────────────────┘                    └────────────────────┘
           │                                         │
           ▼                                         ▼
    ┌──────────────┐                          ┌──────────────┐
    │   Nema 17    │                          │   Nema 17    │
    │   (U7)       │                          │   (U8)       │
    │   Axe X      │                          │   Axe Y      │
    │  1A 1B 2A 2B │                          │  1A 1B 2A 2B │
    └──────────────┘                          └──────────────┘
```

---

## Servo SG90 (U2)

```
    Servo SG90
    ┌─────────────┐
    │             │
    │ GND  [1] ──── GND
    │ GPIO [2] ◄─── IO33 (ESP32 pin 8)   (**CORRIGE** : etait IO35)
    │ 5V   [3] ──── 5V
    │             │
    └─────────────┘
```

---

## Connecteurs

### H1 -- LEDs + Spare (corrige)

```
    H1 (1x8 femelle)
    ┌───┐
    │ 1 │  NC
    │ 2 │  GND ──── Masse LEDs
    │ 3 │  5V  ──── Alimentation LEDs
    │ 4 │  LED ◄─── IO32 (ESP32 pin 7)   (**CORRIGE** : etait IO34)
    │ 5 │  IO32 ─── (meme signal que LED, car fil volant pin 7 → H1.4)
    │ 6 │  IO33 ─── (meme signal que SERVO, car fil volant pin 8 → U2.2)
    │ 7 │  IO19 ─── SUPP4 (spare)
    │ 8 │  IO23 ─── SUPP3 (spare)
    └───┘
```

### H2 -- Alimentation externe (corrige)

```
    H2 (1x8 femelle)
    ┌───┐
    │ 1 │  NC
    │ 2 │  NC
    │ 3 │  +12V ─── A4988 VMOT (x2), condensateur 10uF
    │ 4 │  5V   ─── Servo, MCP23017, A4988 VDD, LEDs
    │   │             (**CORRIGE** : etait "+5", renomme "5V")
    │ 5 │  NC
    │ 6 │  GND
    │ 7 │  GND
    │ 8 │  GND
    └───┘
```

### H3 -- Boutons lignes (inchange)

```
    H3 (1x8 femelle)
    ┌───┐
    │ 1 │  NC
    │ 2 │  NC
    │ 3 │  IO13 ── Ligne 1 (row 0)
    │ 4 │  IO12 ── Ligne 2 (row 1)  ⚠ strapping
    │ 5 │  IO14 ── Ligne 3 (row 2)
    │ 6 │  IO27 ── Ligne 4 (row 3)
    │ 7 │  IO26 ── Ligne 5 (row 4)
    │ 8 │  IO25 ── Ligne 6 (row 5)
    └───┘
```

### H4 -- Boutons colonnes (inchange)

```
    H4 (1x8 femelle)
    ┌───┐
    │ 1 │  NC
    │ 2 │  NC
    │ 3 │  IO15 ── Colonne 1 (col 0)  ⚠ strapping
    │ 4 │  IO2  ── Colonne 2 (col 1)  ⚠ strapping
    │ 5 │  IO0  ── Colonne 3 (col 2)  ⚠ strapping boot
    │ 6 │  IO4  ── Colonne 4 (col 3)
    │ 7 │  IO5  ── Colonne 5 (col 4)
    │ 8 │  IO18 ── Colonne 6 (col 5)
    └───┘
```

---

## Alimentation (corrige)

```
                        H2 (alimentation externe)
                        ┌──────────┐
                 +12V ──┤ H2.3     │
                        │    C     │
                 +5V  ──┤ H2.4     │  (**CORRIGE** : net "5V" unifie)
                        │          │
                  GND ──┤ H2.6-8   │
                        └──────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
         +12V │         +5V  │         GND  │
              │              │              │
              ▼              ▼              ▼
    ┌──────────────┐  ┌────────────┐  (tous les
    │ A4988 VMOT   │  │ MCP23017   │  composants)
    │ U3.16, U4.16 │  │ VIN U6.14  │
    │              │  │            │
    │ Condo 10uF   │  │ A4988 VDD  │
    │ C.2          │  │ U3.10,U4.10│
    └──────────────┘  │            │
                      │ Servo 5V   │
                      │ U2.3       │
                      │            │
                      │ LEDs 5V    │
                      │ H1.3       │
                      └────────────┘
```

---

## Matrice de boutons 6x6 (inchange)

```
    Scan : colonnes en OUTPUT (une a LOW, les autres HIGH)
           lignes en INPUT_PULLUP (LOW = bouton presse)

               Col1     Col2     Col3     Col4     Col5     Col6
               IO15     IO2      IO0      IO4      IO5      IO18
                │        │        │        │        │        │
    Lig1 IO13 ──┤────────┤────────┤────────┤────────┤────────┤
                │[0,0]   │[0,1]   │[0,2]   │[0,3]   │[0,4]   │[0,5]
    Lig2 IO12 ──┤────────┤────────┤────────┤────────┤────────┤
       ⚠       │[1,0]   │[1,1]   │[1,2]   │[1,3]   │[1,4]   │[1,5]
    Lig3 IO14 ──┤────────┤────────┤────────┤────────┤────────┤
                │[2,0]   │[2,1]   │[2,2]   │[2,3]   │[2,4]   │[2,5]
    Lig4 IO27 ──┤────────┤────────┤────────┤────────┤────────┤
                │[3,0]   │[3,1]   │[3,2]   │[3,3]   │[3,4]   │[3,5]
    Lig5 IO26 ──┤────────┤────────┤────────┤────────┤────────┤
                │[4,0]   │[4,1]   │[4,2]   │[4,3]   │[4,4]   │[4,5]
    Lig6 IO25 ──┤────────┤────────┤────────┤────────┤────────┤
                │[5,0]   │[5,1]   │[5,2]   │[5,3]   │[5,4]   │[5,5]
                │        │        │        │        │        │

    Coordonnees [row, col] = memes que le moteur de jeu Python
    (0,0) = haut-gauche, (5,5) = bas-droite
```

---

## Resume des corrections appliquees dans ce schema

| # | Modification | Avant | Apres |
|---|-------------|-------|-------|
| 1 | Module ESP32 | WROVER | **WROOM** |
| 2 | Signal LED | IO34 (pin 5) | **IO32 (pin 7)** |
| 3 | Signal Servo | IO35 (pin 6) | **IO33 (pin 8)** |
| 4 | Net alim H2.4 | "+5" (isole) | **"5V"** (unifie) |
| 5 | Port A MCP23017 | "Moteur X" (faux) | **Moteur Y** |
| 6 | Port B MCP23017 | "Moteur Y" (faux) | **Moteur X** |
| 7 | GPIO16/17 | Reserves PSRAM | **Disponibles** (UART2) |
