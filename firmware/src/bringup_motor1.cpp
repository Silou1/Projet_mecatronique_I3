// Sketch de test : moteur 1 (NEMA17 + driver DRV8825) - bring-up breadboard.
// Cible : ESP32-WROOM (Freenove DevKit)
//
// Cablage :
//   - STEP -> GPIO 14
//   - DIR  -> GPIO 27
//   - EN   -> GPIO 33  (actif LOW : LOW = driver actif, HIGH = desactive)
//   - SLP + RST pontes ensemble et tires au 3.3V
//   - M0/M1/M2 non connectes (full step, 200 pas/tour)
//   - VMOT = 12V (avec condo 100uF entre VMOT et GND)
//   - GND logique + GND alim 12V tous deux sur le rail GND breadboard
//
// SECURITE :
//   - Driver DESACTIVE au boot (EN = HIGH).
//   - Tape "EN ON" pour activer avant tout mouvement.
//   - Vref doit etre regle a ~0.25V (pour 0.5A par bobine) AVANT brancher le moteur.
//
// Commandes serie (115200 baud) :
//   M1 F <n>    moteur 1, forward, n pas (ex. M1 F 200)
//   M1 B <n>    moteur 1, backward, n pas
//   EN ON       active le driver (EN = LOW)
//   EN OFF      desactive le driver (EN = HIGH) - etat boot
//   SPEED <us>  demi-periode du STEP en microsecondes, defaut 1000 (= 500 Hz)
//   STATUS      affiche etat actuel
//   HELP        liste les commandes

#include <Arduino.h>
#include "esp_task_wdt.h"

static constexpr uint8_t PIN_STEP = 14;
static constexpr uint8_t PIN_DIR  = 27;
static constexpr uint8_t PIN_EN   = 33;

static constexpr uint32_t SPEED_DEFAUT_US = 1000;  // demi-periode = 1 ms -> 500 Hz
static constexpr uint32_t SPEED_MIN_US    = 50;    // borne inferieure de securite
static constexpr uint32_t SPEED_MAX_US    = 10000; // borne superieure
static constexpr uint32_t PAS_MAX         = 10000; // limite par commande, evite blocage long

static uint32_t demi_periode_us = SPEED_DEFAUT_US;
static String   tampon_serie;

static void activer_driver(bool actif) {
  // Le DRV8825 a EN actif LOW : LOW = driver alimente, HIGH = driver coupe.
  digitalWrite(PIN_EN, actif ? LOW : HIGH);
}

static void executer_pas(uint32_t nb_pas, bool sens_forward) {
  digitalWrite(PIN_DIR, sens_forward ? HIGH : LOW);
  delayMicroseconds(5);  // setup time DIR -> STEP (DRV8825 demande 650 ns, 5 us large)

  for (uint32_t i = 0; i < nb_pas; ++i) {
    digitalWrite(PIN_STEP, HIGH);
    delayMicroseconds(demi_periode_us);
    digitalWrite(PIN_STEP, LOW);
    delayMicroseconds(demi_periode_us);

    // Cede le CPU regulierement pour eviter les soucis watchdog/Wi-Fi/BT.
    if ((i & 0x3F) == 0) yield();
  }
}

static void afficher_aide() {
  Serial.println("Commandes :");
  Serial.println("  M1 F <n>    moteur 1 forward, n pas (1..10000)");
  Serial.println("  M1 B <n>    moteur 1 backward, n pas");
  Serial.println("  EN ON       active le driver");
  Serial.println("  EN OFF      desactive le driver (etat boot)");
  Serial.println("  SPEED <us>  demi-periode STEP en us (50..10000, defaut 1000)");
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

  if (s == "HELP") { afficher_aide(); return; }
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

  if (s.startsWith("M1 F ") || s.startsWith("M1 B ")) {
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
    Serial.print("M1 ");
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

  // Watchdog desactive pour ce sketch (mouvements potentiellement longs en bloquant).
  esp_task_wdt_deinit();

  // Pins en sortie, etats surs avant que rien ne bouge.
  pinMode(PIN_STEP, OUTPUT);
  pinMode(PIN_DIR,  OUTPUT);
  pinMode(PIN_EN,   OUTPUT);
  digitalWrite(PIN_STEP, LOW);
  digitalWrite(PIN_DIR,  LOW);
  digitalWrite(PIN_EN,   HIGH);  // SECURITE : driver desactive au boot

  Serial.println();
  Serial.println("=== Test moteur 1 (DRV8825 + NEMA17) ===");
  Serial.println("STEP=GPIO 14, DIR=GPIO 27, EN=GPIO 33 (actif LOW)");
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
      // Garde-fou contre les lignes geantes
      if (tampon_serie.length() > 64) {
        tampon_serie = "";
        Serial.println("Ligne trop longue, ignoree.");
      }
    }
  }
}
