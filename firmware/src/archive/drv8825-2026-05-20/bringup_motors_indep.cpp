// Sketch de controle bas niveau independant : 2 drivers DRV8825 + 2 moteurs NEMA17.
// Chaque commande agit sur UN SEUL composant. Aucune logique CoreXY, aucun homing,
// aucune coupure auto. L'utilisateur reste maitre de tout.
//
// Cible : ESP32-WROOM (Freenove DevKit). Drivers DRV8825 sur breadboard.
//
// === Cablage ===
//
//   Moteur 1 - DRV8825 #1
//     STEP -> GPIO 14    DIR -> GPIO 27    EN -> GPIO 26 (actif LOW)
//     VDD -> 3V3 ESP32   SLP+RST pontes -> 3V3
//     M0/M1/M2 selon microstepping (full step = tous a GND,
//                                   1/4 step = M0=GND, M1=3V3, M2=GND)
//     VMOT -> +12V       condo 100uF au plus pres
//     1A/1B + 2A/2B -> bobines NEMA17 #1
//
//   Moteur 2 - DRV8825 #2
//     STEP -> GPIO 16    DIR -> GPIO 17    EN -> GPIO 21 (actif LOW)
//     VDD -> 3V3 ESP32   SLP+RST pontes -> 3V3
//     M0/M1/M2 selon microstepping (idem driver 1)
//     VMOT -> +12V       condo 100uF dedie au plus pres
//     1A/1B + 2A/2B -> bobines NEMA17 #2
//
//   Alim 12V partagee, GND commun (ESP32 + 12V).
//
// === Etat au boot ===
//
//   Drivers 1 et 2 DESACTIVES (EN HIGH). STEP / DIR a LOW.
//   Aucun mouvement tant qu'on ne tape pas EN1 ON ou EN2 ON.
//
// === Commandes serie (115200 baud) ===
//
//   --- Activation des drivers (independante) ---
//   EN1 ON | EN1 OFF    active / coupe le driver 1
//   EN2 ON | EN2 OFF    active / coupe le driver 2
//   EN ON  | EN OFF     raccourci : agit sur LES DEUX drivers
//
//   --- Mouvement (chaque moteur independamment) ---
//   M1 F <n>            moteur 1, forward, n pas (1..10000)
//   M1 B <n>            moteur 1, backward, n pas
//   M2 F <n>            moteur 2, forward, n pas
//   M2 B <n>            moteur 2, backward, n pas
//
//   --- Reglages ---
//   SPEED <us>          demi-periode STEP en us (50..30000, defaut 1000)
//   STATUS              affiche l'etat des 2 drivers + SPEED
//   HELP                cette aide

#include <Arduino.h>
#include "esp_task_wdt.h"

// ============================================================================
// Pins
// ============================================================================

// Moteur 1
static constexpr uint8_t M1_STEP = 14;
static constexpr uint8_t M1_DIR  = 27;
static constexpr uint8_t M1_EN   = 26;

// Moteur 2
static constexpr uint8_t M2_STEP = 16;
static constexpr uint8_t M2_DIR  = 17;
static constexpr uint8_t M2_EN   = 21;

// ============================================================================
// Parametres
// ============================================================================

static constexpr uint32_t SPEED_DEFAUT_US = 1000;
static constexpr uint32_t SPEED_MIN_US    = 50;
static constexpr uint32_t SPEED_MAX_US    = 30000;
static constexpr uint32_t PAS_MAX         = 10000;

static uint32_t demi_periode_us = SPEED_DEFAUT_US;
static String   tampon_serie;

// ============================================================================
// Drivers : activer / desactiver
// ============================================================================

static void activer_driver_1(bool actif) {
  digitalWrite(M1_EN, actif ? LOW : HIGH);
}

static void activer_driver_2(bool actif) {
  digitalWrite(M2_EN, actif ? LOW : HIGH);
}

static bool driver_1_actif() { return digitalRead(M1_EN) == LOW; }
static bool driver_2_actif() { return digitalRead(M2_EN) == LOW; }

// ============================================================================
// Generation des pas sur un seul moteur
// ============================================================================

static void executer_pas(uint8_t pin_step, uint8_t pin_dir,
                         uint32_t nb_pas, bool sens_forward) {
  digitalWrite(pin_dir, sens_forward ? HIGH : LOW);
  delayMicroseconds(5);  // setup time DIR -> STEP

  for (uint32_t i = 0; i < nb_pas; ++i) {
    digitalWrite(pin_step, HIGH);
    delayMicroseconds(demi_periode_us);
    digitalWrite(pin_step, LOW);
    delayMicroseconds(demi_periode_us);

    if ((i & 0x3F) == 0) yield();
  }
}

// ============================================================================
// Affichage
// ============================================================================

static void afficher_aide() {
  Serial.println("Commandes :");
  Serial.println("  EN1 ON | EN1 OFF   active / coupe driver 1");
  Serial.println("  EN2 ON | EN2 OFF   active / coupe driver 2");
  Serial.println("  EN  ON | EN  OFF   raccourci pour les 2 drivers");
  Serial.println("  M1 F <n>           moteur 1 forward, n pas (1..10000)");
  Serial.println("  M1 B <n>           moteur 1 backward, n pas");
  Serial.println("  M2 F <n>           moteur 2 forward, n pas");
  Serial.println("  M2 B <n>           moteur 2 backward, n pas");
  Serial.println("  SPEED <us>         demi-periode STEP en us (50..30000)");
  Serial.println("  STATUS             etat actuel");
  Serial.println("  HELP               cette aide");
}

static void afficher_status() {
  Serial.print("  driver 1 : ");
  Serial.println(driver_1_actif() ? "ON  (EN=LOW)"  : "OFF (EN=HIGH)");
  Serial.print("  driver 2 : ");
  Serial.println(driver_2_actif() ? "ON  (EN=LOW)"  : "OFF (EN=HIGH)");
  Serial.print("  SPEED    : ");
  Serial.print(demi_periode_us);
  Serial.print(" us  (~");
  Serial.print(500000UL / demi_periode_us);
  Serial.println(" Hz STEP)");
}

// ============================================================================
// Parseur commandes
// ============================================================================

// Helper : execute n pas sur un moteur donne en verifiant que son driver est actif.
static void cmd_pas(const char* nom, uint8_t pin_step, uint8_t pin_dir,
                    bool (*driver_check)(), long n, bool sens_forward) {
  if (!driver_check()) {
    Serial.print("Driver de ");
    Serial.print(nom);
    Serial.println(" OFF. Active-le d'abord (EN1 ON / EN2 ON).");
    return;
  }
  Serial.print(nom);
  Serial.print(' ');
  Serial.print(sens_forward ? 'F' : 'B');
  Serial.print(' ');
  Serial.print(n);
  Serial.print(" pas a ");
  Serial.print(demi_periode_us);
  Serial.println(" us ...");
  executer_pas(pin_step, pin_dir, (uint32_t)n, sens_forward);
  Serial.println("done");
}

static void traiter(String s) {
  s.trim();
  s.toUpperCase();
  if (s.length() == 0) return;

  if (s == "HELP")    { afficher_aide();  return; }
  if (s == "STATUS")  { afficher_status(); return; }

  // EN groupes
  if (s == "EN1 ON")  { activer_driver_1(true);  Serial.println("driver 1 ON");  return; }
  if (s == "EN1 OFF") { activer_driver_1(false); Serial.println("driver 1 OFF"); return; }
  if (s == "EN2 ON")  { activer_driver_2(true);  Serial.println("driver 2 ON");  return; }
  if (s == "EN2 OFF") { activer_driver_2(false); Serial.println("driver 2 OFF"); return; }
  if (s == "EN ON")   { activer_driver_1(true);  activer_driver_2(true);
                        Serial.println("drivers 1 et 2 ON");  return; }
  if (s == "EN OFF")  { activer_driver_1(false); activer_driver_2(false);
                        Serial.println("drivers 1 et 2 OFF"); return; }

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

  // Mouvements moteurs : M1 / M2 + F / B + <n>
  if (s.startsWith("M1 F ") || s.startsWith("M1 B ")) {
    bool fwd = s.charAt(3) == 'F';
    long n = s.substring(5).toInt();
    if (n <= 0 || n > (long)PAS_MAX) {
      Serial.print("N hors limite [1..");
      Serial.print(PAS_MAX);
      Serial.println("]");
      return;
    }
    cmd_pas("M1", M1_STEP, M1_DIR, driver_1_actif, n, fwd);
    return;
  }
  if (s.startsWith("M2 F ") || s.startsWith("M2 B ")) {
    bool fwd = s.charAt(3) == 'F';
    long n = s.substring(5).toInt();
    if (n <= 0 || n > (long)PAS_MAX) {
      Serial.print("N hors limite [1..");
      Serial.print(PAS_MAX);
      Serial.println("]");
      return;
    }
    cmd_pas("M2", M2_STEP, M2_DIR, driver_2_actif, n, fwd);
    return;
  }

  Serial.print("Commande inconnue : '");
  Serial.print(s);
  Serial.println("' - tape HELP");
}

// ============================================================================
// Setup / Loop
// ============================================================================

void setup() {
  // Pins en sortie + etats surs (drivers OFF).
  pinMode(M1_STEP, OUTPUT); digitalWrite(M1_STEP, LOW);
  pinMode(M1_DIR,  OUTPUT); digitalWrite(M1_DIR,  LOW);
  pinMode(M1_EN,   OUTPUT); digitalWrite(M1_EN,   HIGH);  // driver 1 OFF
  pinMode(M2_STEP, OUTPUT); digitalWrite(M2_STEP, LOW);
  pinMode(M2_DIR,  OUTPUT); digitalWrite(M2_DIR,  LOW);
  pinMode(M2_EN,   OUTPUT); digitalWrite(M2_EN,   HIGH);  // driver 2 OFF

  esp_task_wdt_deinit();  // mouvements potentiellement longs en bloquant

  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("=== Controle independant 2 drivers DRV8825 + 2 moteurs ===");
  Serial.println("M1: STEP=14 DIR=27 EN=26");
  Serial.println("M2: STEP=16 DIR=17 EN=21");
  Serial.println("Drivers DESACTIVES au boot. Tape 'EN1 ON' ou 'EN2 ON' pour activer.");
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
