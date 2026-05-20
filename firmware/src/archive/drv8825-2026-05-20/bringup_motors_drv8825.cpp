// Sketch d'integration CoreXY DRV8825 : M1 + M2 + 2 fins de course.
// Cible : ESP32-WROOM (Freenove DevKit). Drivers DRV8825 en microstepping 1/4.
//
// === Difference vs bringup_motors_and_limits.cpp (L298N) ===
//
//   - Pilotage STEP/DIR/EN au lieu de la sequence 4 phases + PWM L298N.
//   - Microstepping 1/4 active en hard (M0=GND, M1=3V3, M2=GND sur les 2 drivers).
//     800 microsteps/tour au lieu de 200 pas/tour en full-step.
//   - Coupure automatique des drivers (EN HIGH) apres 2 s d'inactivite
//     pour limiter la chauffe (point critique du DRV8825).
//   - HOME execute automatiquement au boot, plus besoin de lancer la commande.
//
// === Cablage (valide 2026-05-20) ===
//
//   Moteur 1 - DRV8825 #1
//     STEP -> GPIO 14    DIR -> GPIO 27    EN -> GPIO 26 (actif LOW)
//     VDD -> 3V3 ESP32   SLP+RST pontes -> 3V3   M0=GND, M1=3V3, M2=GND (1/4 step)
//     VMOT -> +12V       condo 100uF entre VMOT et GND au plus pres
//     1A/1B + 2A/2B -> bobines NEMA17 #1
//
//   Moteur 2 - DRV8825 #2
//     STEP -> GPIO 16    DIR -> GPIO 17    EN -> GPIO 21 (actif LOW)
//     VDD -> 3V3 ESP32   SLP+RST pontes -> 3V3   M0=GND, M1=3V3, M2=GND (1/4 step)
//     VMOT -> +12V       condo 100uF dedie au plus pres
//     1A/1B + 2A/2B -> bobines NEMA17 #2
//
//   Capteur 1 (fin de course axe X) : GPIO 13, INPUT_PULLUP (switch vers GND)
//   Capteur 2 (fin de course axe Y) : GPIO 18, INPUT_PULLUP
//
//   Alim 12V partagee, GND commun (ESP32 + 12V + capteurs).
//   Vref des deux drivers regle au multimetre avant tout test (cible 0.20-0.25 V).
//
// === Conventions CoreXY (validees machine 2026-05-20) ===
//
//   X pur : M1 et M2 sens OPPOSES   (Capteur 1 = fin de course X-)
//   Y pur : M1 et M2 MEME sens      (Capteur 2 = fin de course Y-)
//   X F = s'eloigne du capteur 1 ; X B = vers capteur 1
//   Y F = s'eloigne du capteur 2 ; Y B = vers capteur 2
//
// === Calibration en 1/4 step ===
//
//   Full-step L298N : 100 pas = 2 cm. En 1/4 step : 400 microsteps = 2 cm.
//   Donc 1 mm = 20 microsteps, 1 cm = 200 microsteps.
//   Bornes GOTO : ~110 mm en X = 2200 microsteps, ~100 mm en Y = 2000.
//
// === Sequence boot automatique ===
//
//   1. Init pins (drivers OFF par securite)
//   2. Init Serial
//   3. Activation drivers (EN LOW)
//   4. HOME X (recul 80 microsteps apres contact)
//   5. HOME Y (recul 80 microsteps apres contact)
//   6. Position etablie (0, 0). Drivers coupes apres 2 s d'inactivite.
//   7. Boucle de commandes serie pour test/debug
//
// === Commandes serie (115200 baud) ===
//
//   HOME              relance le homing
//   GOTO <x> <y>      deplacement absolu en microsteps depuis origine
//   X F/B <n>         axe X pur, n microsteps
//   Y F/B <n>         axe Y pur, n microsteps
//   M1 F/B <n>        moteur 1 seul (debug, INVALIDE la position)
//   M2 F/B <n>        moteur 2 seul (debug, INVALIDE la position)
//   LIMITS            lecture instantanee des fins de course
//   LIMITS WATCH      lecture continue (Enter pour sortir)
//   EN ON | EN OFF    active/coupe les 2 drivers (coupure auto apres 2 s anyway)
//   SPEED <us>        demi-periode STEP en us (100..30000, defaut 2000)
//   STATUS            etat courant
//   HELP              cette aide

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

// Capteurs
static constexpr uint8_t PIN_LIMIT_X = 13;
static constexpr uint8_t PIN_LIMIT_Y = 18;

// ============================================================================
// Parametres
// ============================================================================

static constexpr uint32_t SPEED_DEFAUT_US = 2000;   // demi-periode STEP (250 Hz STEP)
static constexpr uint32_t SPEED_MIN_US    = 100;    // borne sup vitesse (5 kHz STEP)
static constexpr uint32_t SPEED_MAX_US    = 30000;  // borne inf vitesse (~17 Hz STEP)
static constexpr uint32_t PAS_MAX_CMD     = 10000;  // limite par commande (microsteps)

// Coupure auto des drivers pour limiter la chauffe.
static constexpr uint32_t EN_AUTO_OFF_MS  = 2000;

// HOME (en microsteps 1/4 step)
static constexpr uint32_t HOME_PAS_MAX     = 4000;   // garde-fou (~20 cm de course max)
static constexpr uint32_t HOME_RECUL_PAS   = 80;     // 4 mm de recul apres contact
static constexpr uint32_t HOME_LIBERATION  = 200;    // si capteur deja LOW au boot
static constexpr uint32_t HOME_SPEED_US    = 3000;   // homing plus lent (~166 Hz)

// Bornes logicielles GOTO (en microsteps depuis HOME)
static constexpr int32_t GOTO_X_MAX = 2800;  // ~14 cm de marge sur la course mesuree
static constexpr int32_t GOTO_Y_MAX = 2800;

// ============================================================================
// Etat global
// ============================================================================

static uint32_t demi_periode_us  = SPEED_DEFAUT_US;
static bool     drivers_actifs   = false;
static uint32_t derniere_action_ms = 0;
static bool     position_connue  = false;
static int32_t  pos_x = 0;  // microsteps depuis HOME
static int32_t  pos_y = 0;
static String   tampon_serie;

// ============================================================================
// Driver enable / disable
// ============================================================================

static void activer_drivers(bool actif) {
  digitalWrite(M1_EN, actif ? LOW : HIGH);
  digitalWrite(M2_EN, actif ? LOW : HIGH);
  drivers_actifs = actif;
  if (actif) derniere_action_ms = millis();
}

static void coupure_auto_si_inactif() {
  if (!drivers_actifs) return;
  if (millis() - derniere_action_ms < EN_AUTO_OFF_MS) return;
  digitalWrite(M1_EN, HIGH);
  digitalWrite(M2_EN, HIGH);
  drivers_actifs = false;
  Serial.println("(drivers coupes apres inactivite -- limite la chauffe)");
}

// Reactive automatiquement les drivers si un mouvement est demande.
static void garantir_drivers_actifs() {
  if (!drivers_actifs) activer_drivers(true);
  derniere_action_ms = millis();
}

// ============================================================================
// Generation des pas (un moteur seul ou les deux en parallele)
// ============================================================================

// Pulse les deux moteurs en meme temps (pour les mouvements coordonnes CoreXY).
// Si l'un des deux moteurs n'a pas a bouger, passer son STEP pin a 255 (= ignore).
static void pulse_2_moteurs(uint32_t nb_pas,
                            bool m1_actif, bool m1_forward,
                            bool m2_actif, bool m2_forward,
                            uint32_t periode_us) {
  if (m1_actif) {
    digitalWrite(M1_DIR, m1_forward ? HIGH : LOW);
  }
  if (m2_actif) {
    digitalWrite(M2_DIR, m2_forward ? HIGH : LOW);
  }
  delayMicroseconds(5);  // setup time DIR -> STEP

  for (uint32_t i = 0; i < nb_pas; ++i) {
    if (m1_actif) digitalWrite(M1_STEP, HIGH);
    if (m2_actif) digitalWrite(M2_STEP, HIGH);
    delayMicroseconds(periode_us);
    if (m1_actif) digitalWrite(M1_STEP, LOW);
    if (m2_actif) digitalWrite(M2_STEP, LOW);
    delayMicroseconds(periode_us);

    if ((i & 0x3F) == 0) yield();  // protege Wi-Fi / watchdog
  }
}

// ============================================================================
// Mouvements CoreXY
// ============================================================================

// Convention machine : X = M1 et M2 sens opposes, Y = M1 et M2 meme sens.
// Pour X forward : M1 forward, M2 backward.
// Pour Y forward : M1 forward, M2 forward.
static void deplacer_x(uint32_t pas, bool forward) {
  garantir_drivers_actifs();
  pulse_2_moteurs(pas, true, forward, true, !forward, demi_periode_us);
  pos_x += forward ? (int32_t)pas : -(int32_t)pas;
  derniere_action_ms = millis();
}

static void deplacer_y(uint32_t pas, bool forward) {
  garantir_drivers_actifs();
  pulse_2_moteurs(pas, true, forward, true, forward, demi_periode_us);
  pos_y += forward ? (int32_t)pas : -(int32_t)pas;
  derniere_action_ms = millis();
}

// Pour debug : pulse un seul moteur. INVALIDE la position cartesienne.
static void deplacer_m1_seul(uint32_t pas, bool forward) {
  garantir_drivers_actifs();
  pulse_2_moteurs(pas, true, forward, false, false, demi_periode_us);
  position_connue = false;
  derniere_action_ms = millis();
}

static void deplacer_m2_seul(uint32_t pas, bool forward) {
  garantir_drivers_actifs();
  pulse_2_moteurs(pas, false, false, true, forward, demi_periode_us);
  position_connue = false;
  derniere_action_ms = millis();
}

// ============================================================================
// HOME
// ============================================================================

// Homing d'un axe : approche du capteur, recul de HOME_RECUL_PAS.
// Si capteur deja LOW au boot, libere de HOME_LIBERATION pas avant d'approcher.
// Retourne false si garde-fou HOME_PAS_MAX atteint.
static bool homing_axe(const char* nom,
                       uint8_t pin_capteur,
                       bool m1_backward,  // sens "B" (vers capteur) pour M1
                       bool m2_backward) {
  Serial.print("HOME ");
  Serial.print(nom);
  Serial.println(" ...");

  uint32_t sauv_speed = demi_periode_us;
  demi_periode_us = HOME_SPEED_US;
  garantir_drivers_actifs();

  // Si capteur deja appuye au depart : libere pour pouvoir le retoucher proprement.
  if (digitalRead(pin_capteur) == LOW) {
    Serial.print("  capteur deja LOW -> liberation ");
    Serial.print(HOME_LIBERATION);
    Serial.println(" microsteps");
    pulse_2_moteurs(HOME_LIBERATION, true, !m1_backward, true, !m2_backward, demi_periode_us);
  }

  // Approche du capteur, pas par pas, jusqu'a contact ou garde-fou.
  bool ok = false;
  for (uint32_t i = 0; i < HOME_PAS_MAX; ++i) {
    if (digitalRead(pin_capteur) == LOW) { ok = true; break; }
    pulse_2_moteurs(1, true, m1_backward, true, m2_backward, demi_periode_us);
    if ((i & 0x3F) == 0) yield();
  }

  if (!ok) {
    Serial.print("  ECHEC : capteur ");
    Serial.print(nom);
    Serial.print(" jamais atteint en ");
    Serial.print(HOME_PAS_MAX);
    Serial.println(" microsteps");
    demi_periode_us = sauv_speed;
    return false;
  }

  Serial.print("  capteur ");
  Serial.print(nom);
  Serial.println(" touche -> recul");
  pulse_2_moteurs(HOME_RECUL_PAS, true, !m1_backward, true, !m2_backward, demi_periode_us);

  demi_periode_us = sauv_speed;
  return true;
}

// Homing complet : X puis Y. Etablit l'origine (0, 0).
static bool homing_complet() {
  Serial.println();
  Serial.println("=== HOME ===");

  bool ok_x = homing_axe("X", PIN_LIMIT_X, /*m1_back*/ false, /*m2_back*/ true);
  if (!ok_x) return false;
  delay(150);
  bool ok_y = homing_axe("Y", PIN_LIMIT_Y, /*m1_back*/ false, /*m2_back*/ false);
  if (!ok_y) return false;

  pos_x = 0;
  pos_y = 0;
  position_connue = true;
  derniere_action_ms = millis();

  Serial.println("HOME OK. Origine (0, 0) etablie.");
  return true;
}

// ============================================================================
// GOTO (deplacement absolu, sequentiel X puis Y)
// ============================================================================

static void goto_xy(int32_t x_cible, int32_t y_cible) {
  if (!position_connue) {
    Serial.println("GOTO refuse : position inconnue (HOME requis).");
    return;
  }
  if (x_cible < 0 || x_cible > GOTO_X_MAX || y_cible < 0 || y_cible > GOTO_Y_MAX) {
    Serial.print("GOTO refuse : cible hors bornes [0..");
    Serial.print(GOTO_X_MAX);
    Serial.print("] x [0..");
    Serial.print(GOTO_Y_MAX);
    Serial.println("]");
    return;
  }

  int32_t dx = x_cible - pos_x;
  int32_t dy = y_cible - pos_y;
  Serial.print("GOTO (");
  Serial.print(x_cible);
  Serial.print(", ");
  Serial.print(y_cible);
  Serial.print(")  dx=");
  Serial.print(dx);
  Serial.print(" dy=");
  Serial.println(dy);

  if (dx != 0) deplacer_x((uint32_t)abs(dx), dx > 0);
  if (dy != 0) deplacer_y((uint32_t)abs(dy), dy > 0);
  Serial.println("done");
}

// ============================================================================
// Affichage
// ============================================================================

static void afficher_aide() {
  Serial.println("Commandes :");
  Serial.println("  HOME              relance le homing");
  Serial.println("  GOTO <x> <y>      deplacement absolu (microsteps)");
  Serial.println("  X F/B <n>         axe X pur, n microsteps");
  Serial.println("  Y F/B <n>         axe Y pur, n microsteps");
  Serial.println("  M1 F/B <n>        moteur 1 seul (debug, INVALIDE position)");
  Serial.println("  M2 F/B <n>        moteur 2 seul (debug, INVALIDE position)");
  Serial.println("  LIMITS            lecture instantanee des fins de course");
  Serial.println("  LIMITS WATCH      lecture continue (Enter pour sortir)");
  Serial.println("  EN ON | EN OFF    active/coupe les 2 drivers");
  Serial.println("  SPEED <us>        demi-periode STEP en us (100..30000)");
  Serial.println("  STATUS            etat courant");
  Serial.println("  HELP              cette aide");
}

static void afficher_status() {
  Serial.print("  drivers : ");
  Serial.println(drivers_actifs ? "ON" : "OFF");
  Serial.print("  position : ");
  if (position_connue) {
    Serial.print("(");
    Serial.print(pos_x);
    Serial.print(", ");
    Serial.print(pos_y);
    Serial.println(") microsteps");
  } else {
    Serial.println("INCONNUE (HOME requis)");
  }
  Serial.print("  SPEED   : ");
  Serial.print(demi_periode_us);
  Serial.print(" us  (~");
  Serial.print(500000UL / demi_periode_us);
  Serial.println(" Hz STEP)");
  Serial.print("  LIMIT X : ");
  Serial.println(digitalRead(PIN_LIMIT_X) == LOW ? "LOW (presse)" : "HIGH (relache)");
  Serial.print("  LIMIT Y : ");
  Serial.println(digitalRead(PIN_LIMIT_Y) == LOW ? "LOW (presse)" : "HIGH (relache)");
}

static void limits_watch() {
  Serial.println("LIMITS WATCH (Enter pour sortir)");
  int prev_x = -1, prev_y = -1;
  while (true) {
    int x = digitalRead(PIN_LIMIT_X);
    int y = digitalRead(PIN_LIMIT_Y);
    if (x != prev_x || y != prev_y) {
      Serial.print("X=");
      Serial.print(x == LOW ? "LOW " : "HIGH");
      Serial.print("  Y=");
      Serial.println(y == LOW ? "LOW " : "HIGH");
      prev_x = x;
      prev_y = y;
    }
    if (Serial.available()) {
      while (Serial.available()) Serial.read();
      break;
    }
    delay(15);
  }
  Serial.println("(sortie LIMITS WATCH)");
}

// ============================================================================
// Parseur commandes serie
// ============================================================================

static bool parse_2_args(const String& s, size_t offset, long& a, long& b) {
  String reste = s.substring(offset);
  reste.trim();
  int sp = reste.indexOf(' ');
  if (sp < 0) return false;
  a = reste.substring(0, sp).toInt();
  b = reste.substring(sp + 1).toInt();
  return true;
}

static void traiter(String s) {
  s.trim();
  s.toUpperCase();
  if (s.length() == 0) return;

  if (s == "HELP")    { afficher_aide();  return; }
  if (s == "STATUS")  { afficher_status(); return; }
  if (s == "EN ON")   { activer_drivers(true);  Serial.println("drivers ON");  return; }
  if (s == "EN OFF")  { activer_drivers(false); Serial.println("drivers OFF"); return; }
  if (s == "LIMITS")  {
    Serial.print("X=");
    Serial.print(digitalRead(PIN_LIMIT_X) == LOW ? "LOW " : "HIGH");
    Serial.print("  Y=");
    Serial.println(digitalRead(PIN_LIMIT_Y) == LOW ? "LOW " : "HIGH");
    return;
  }
  if (s == "LIMITS WATCH") { limits_watch(); return; }
  if (s == "HOME") { homing_complet(); return; }

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

  if (s.startsWith("GOTO ")) {
    long x, y;
    if (!parse_2_args(s, 5, x, y)) {
      Serial.println("Syntaxe : GOTO <x> <y>");
      return;
    }
    goto_xy((int32_t)x, (int32_t)y);
    return;
  }

  // Mouvements pas relatifs : X / Y / M1 / M2 + F / B + <n>
  auto parse_n = [&](size_t off) -> long {
    long n = s.substring(off).toInt();
    if (n <= 0 || n > (long)PAS_MAX_CMD) {
      Serial.print("N hors limite [1..");
      Serial.print(PAS_MAX_CMD);
      Serial.println("]");
      return -1;
    }
    return n;
  };

  if (s.startsWith("X F ") || s.startsWith("X B ")) {
    long n = parse_n(4);
    if (n < 0) return;
    deplacer_x((uint32_t)n, s.charAt(2) == 'F');
    Serial.println("done");
    return;
  }
  if (s.startsWith("Y F ") || s.startsWith("Y B ")) {
    long n = parse_n(4);
    if (n < 0) return;
    deplacer_y((uint32_t)n, s.charAt(2) == 'F');
    Serial.println("done");
    return;
  }
  if (s.startsWith("M1 F ") || s.startsWith("M1 B ")) {
    long n = parse_n(5);
    if (n < 0) return;
    deplacer_m1_seul((uint32_t)n, s.charAt(3) == 'F');
    Serial.println("done (position INVALIDEE)");
    return;
  }
  if (s.startsWith("M2 F ") || s.startsWith("M2 B ")) {
    long n = parse_n(5);
    if (n < 0) return;
    deplacer_m2_seul((uint32_t)n, s.charAt(3) == 'F');
    Serial.println("done (position INVALIDEE)");
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
  // 1. Init pins en sortie + etats surs (drivers OFF en premier).
  pinMode(M1_STEP, OUTPUT);
  pinMode(M1_DIR,  OUTPUT);
  pinMode(M1_EN,   OUTPUT);
  pinMode(M2_STEP, OUTPUT);
  pinMode(M2_DIR,  OUTPUT);
  pinMode(M2_EN,   OUTPUT);
  digitalWrite(M1_STEP, LOW);
  digitalWrite(M1_DIR,  LOW);
  digitalWrite(M1_EN,   HIGH);  // driver OFF par securite
  digitalWrite(M2_STEP, LOW);
  digitalWrite(M2_DIR,  LOW);
  digitalWrite(M2_EN,   HIGH);

  pinMode(PIN_LIMIT_X, INPUT_PULLUP);
  pinMode(PIN_LIMIT_Y, INPUT_PULLUP);

  // 2. Watchdog desactive (mouvements longs en bloquant).
  esp_task_wdt_deinit();

  // 3. Serial.
  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("=== Bring-up CoreXY DRV8825 (M1 + M2 + 2 capteurs) ===");
  Serial.println("M1: STEP=14 DIR=27 EN=26");
  Serial.println("M2: STEP=16 DIR=17 EN=21");
  Serial.println("Capteurs: X=13, Y=18 (INPUT_PULLUP)");
  Serial.println("Microstepping 1/4 (M0=GND, M1=3V3, M2=GND sur les 2 drivers)");
  Serial.println();

  // 4. HOME automatique.
  delay(200);
  if (!homing_complet()) {
    Serial.println();
    Serial.println("!! HOME echoue. Drivers coupes par securite.");
    Serial.println("!! Verifier capteurs + cablage moteurs + Vref, puis taper HOME.");
    activer_drivers(false);
  }

  Serial.println();
  afficher_aide();
  Serial.println();
}

void loop() {
  // Lecture des commandes serie ligne par ligne.
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

  // Coupure auto des drivers apres EN_AUTO_OFF_MS d'inactivite (thermique).
  coupure_auto_si_inactif();
}
