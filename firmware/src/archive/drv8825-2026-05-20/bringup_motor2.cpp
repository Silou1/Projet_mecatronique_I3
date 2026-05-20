// Sketch de test : moteur 2 (NEMA17 + driver DRV8825 #2) - bring-up breadboard.
// Cible : ESP32-WROOM (Freenove DevKit). Jumeau de bringup_motor1.cpp pour M2.
//
// Cablage (mapping breadboard 2026-05-20, recupere les GPIO L298N de M2) :
//   - STEP -> GPIO 16
//   - DIR  -> GPIO 17
//   - EN   -> GPIO 21  (actif LOW : LOW = driver actif, HIGH = desactive)
//   - VDD  -> 3V3 ESP32 (alim logique du driver)
//   - SLP + RST pontes ensemble et tires au 3.3V
//   - M0/M1/M2 selon microstepping voulu (full step = tous a GND,
//     1/4 step = M0=GND, M1=3V3, M2=GND)
//   - VMOT = 12V (avec condo 100uF electrolytique entre VMOT et GND, au plus pres)
//   - GND logique + GND alim 12V + GND ESP32 tous sur le rail GND breadboard
//   - 1A/1B + 2A/2B -> bobines moteur NEMA17 (ne JAMAIS debrancher sous tension)
//
// SECURITE :
//   - Driver DESACTIVE au boot (EN = HIGH).
//   - Tape "EN ON" pour activer avant tout mouvement.
//   - Vref a regler AU MULTIMETRE avant tout : Vref = I_bobine x 5 x R_sense.
//     Avec R100 (0.1 ohm), demarrer a Vref = 0.25V (~0.5A/bobine) - safe pour bring-up.
//
// Commandes serie (115200 baud) :
//   M2 F <n>    moteur 2, forward, n pas/microsteps (ex. M2 F 200)
//   M2 B <n>    moteur 2, backward, n pas/microsteps
//   EN ON       active le driver (EN = LOW)
//   EN OFF      desactive le driver (EN = HIGH) - etat boot
//   SPEED <us>  demi-periode du STEP en microsecondes, defaut 1000 (= 500 Hz)
//   STATUS      affiche etat actuel
//   HELP        liste les commandes

#include <Arduino.h>
#include "esp_task_wdt.h"

static constexpr uint8_t PIN_STEP = 16;
static constexpr uint8_t PIN_DIR  = 17;
static constexpr uint8_t PIN_EN   = 21;

static constexpr uint32_t SPEED_DEFAUT_US = 1000;
static constexpr uint32_t SPEED_MIN_US    = 50;
static constexpr uint32_t SPEED_MAX_US    = 30000;
static constexpr uint32_t PAS_MAX         = 10000;

static uint32_t demi_periode_us = SPEED_DEFAUT_US;
static String   tampon_serie;

static void activer_driver(bool actif) {
  digitalWrite(PIN_EN, actif ? LOW : HIGH);
}

static void executer_pas(uint32_t nb_pas, bool sens_forward) {
  digitalWrite(PIN_DIR, sens_forward ? HIGH : LOW);
  delayMicroseconds(5);

  for (uint32_t i = 0; i < nb_pas; ++i) {
    digitalWrite(PIN_STEP, HIGH);
    delayMicroseconds(demi_periode_us);
    digitalWrite(PIN_STEP, LOW);
    delayMicroseconds(demi_periode_us);

    if ((i & 0x3F) == 0) yield();
  }
}

static void afficher_aide() {
  Serial.println("Commandes :");
  Serial.println("  M2 F <n>    moteur 2 forward, n pas (1..10000)");
  Serial.println("  M2 B <n>    moteur 2 backward, n pas");
  Serial.println("  EN ON       active le driver");
  Serial.println("  EN OFF      desactive le driver (etat boot)");
  Serial.println("  SPEED <us>  demi-periode STEP en us (50..30000, defaut 1000)");
  Serial.println("  STATUS      affiche etat actuel");
  Serial.println("  HELP        cette aide");
}

static void afficher_status() {
  Serial.print("  EN     : ");
  Serial.println(digitalRead(PIN_EN) == LOW ? "ON  (driver actif)" : "OFF (driver coupe)");
  Serial.print("  SPEED  : ");
  Serial.print(demi_periode_us);
  Serial.print(" us  (~");
  Serial.print(500000UL / demi_periode_us);
  Serial.println(" Hz STEP)");
}

static void traiter(String s) {
  s.trim();
  s.toUpperCase();
  if (s.length() == 0) return;

  if (s == "HELP")   { afficher_aide();  return; }
  if (s == "STATUS") { afficher_status(); return; }
  if (s == "EN ON")  { activer_driver(true);  Serial.println("driver ON");  return; }
  if (s == "EN OFF") { activer_driver(false); Serial.println("driver OFF"); return; }

  if (s.startsWith("SPEED ")) {
    long v = s.substring(6).toInt();
    if (v < (long)SPEED_MIN_US || v > (long)SPEED_MAX_US) {
      Serial.print("SPEED hors limite [");
      Serial.print(SPEED_MIN_US);
      Serial.print("..");
      Serial.print(SPEED_MAX_US);
      Serial.println("] us");
      return;
    }
    demi_periode_us = (uint32_t)v;
    Serial.print("SPEED = ");
    Serial.print(demi_periode_us);
    Serial.println(" us");
    return;
  }

  if (s.startsWith("M2 F ") || s.startsWith("M2 B ")) {
    bool sens_forward = s.charAt(3) == 'F';
    long n = s.substring(5).toInt();
    if (n <= 0 || n > (long)PAS_MAX) {
      Serial.print("N hors limite [1..");
      Serial.print(PAS_MAX);
      Serial.println("]");
      return;
    }
    if (digitalRead(PIN_EN) == HIGH) {
      Serial.println("Driver OFF. Tape 'EN ON' d'abord.");
      return;
    }
    Serial.print("M2 ");
    Serial.print(sens_forward ? "F " : "B ");
    Serial.print(n);
    Serial.print(" pas a ");
    Serial.print(demi_periode_us);
    Serial.println(" us ...");
    executer_pas((uint32_t)n, sens_forward);
    Serial.println("done");
    return;
  }

  Serial.print("Commande inconnue : '");
  Serial.print(s);
  Serial.println("' - tape HELP");
}

void setup() {
  Serial.begin(115200);
  delay(500);

  esp_task_wdt_deinit();

  pinMode(PIN_STEP, OUTPUT);
  pinMode(PIN_DIR,  OUTPUT);
  pinMode(PIN_EN,   OUTPUT);
  digitalWrite(PIN_STEP, LOW);
  digitalWrite(PIN_DIR,  LOW);
  digitalWrite(PIN_EN,   HIGH);  // SECURITE : driver desactive au boot

  Serial.println();
  Serial.println("=== Test moteur 2 (DRV8825 #2 + NEMA17) ===");
  Serial.println("STEP=GPIO 16, DIR=GPIO 17, EN=GPIO 21 (actif LOW)");
  Serial.println("Driver DESACTIVE au boot. Tape 'EN ON' pour activer.");
  Serial.println();
  afficher_aide();
  Serial.println();
}

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      traiter(tampon_serie);
      tampon_serie = "";
    } else {
      tampon_serie += c;
      if (tampon_serie.length() > 64) {
        tampon_serie = "";
        Serial.println("Ligne trop longue, ignoree.");
      }
    }
  }
}
