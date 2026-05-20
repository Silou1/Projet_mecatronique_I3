// Sketch de controle bas niveau independant L298N : 2 ponts en H + 2 moteurs
// + 2 fins de course (lecture) + servo SG90.
// Chaque commande agit sur UN SEUL composant. Aucune logique CoreXY, aucun homing,
// aucune coupure auto. L'utilisateur reste maitre de tout.
//
// Cible : ESP32-WROOM (Freenove DevKit).
//
// === Cablage ===
//
//   Moteur 1 - L298N #1
//     IN1=14, IN2=27, IN3=26, IN4=25, ENA=33, ENB=32
//
//   Moteur 2 - L298N #2
//     IN1=16, IN2=17, IN3=21, IN4=22, ENA=19, ENB=23
//
//   Capteurs : X = GPIO 13, Y = GPIO 18 (INPUT_PULLUP, switch vers GND)
//
//   Servo SG90 :
//     Signal -> GPIO 4
//     V+     -> alim 5V externe (PAS le 5V ESP32)
//     GND    -> GND commun
//     Convention : 180 deg = REPOS (piston bas), 0 deg = MUR LEVE.
//     Au boot le servo est force a 180 deg AVANT toute autre init.
//
//   Jumpers ENA/ENB des deux L298N RETIRES (pilotage PWM par GPIO).
//   Jumper 5V_EN en place. Alim +12V partagee, GND commun.
//
// === Etat au boot ===
//
//   Servo a 180 deg (init en toute premiere ligne pour securite mecanique).
//   Drivers 1 et 2 DESACTIVES (PWM = 0). Phases coupees.
//
// === Commandes serie (115200 baud) ===
//
//   --- Drivers (independants) ---
//   EN1 ON | EN1 OFF    active / coupe driver 1
//   EN2 ON | EN2 OFF    active / coupe driver 2
//   EN ON  | EN OFF     raccourci pour LES DEUX
//
//   --- Moteurs (independants, refuses si leur driver est OFF) ---
//   M1 F <n>            moteur 1 forward, n pas (1..10000)
//   M1 B <n>            moteur 1 backward, n pas
//   M2 F <n>            moteur 2 forward, n pas
//   M2 B <n>            moteur 2 backward, n pas
//
//   --- Capteurs ---
//   LIMITS              lecture instantanee X et Y
//   LIMITS WATCH        lecture continue (Enter pour sortir)
//
//   --- Servo ---
//   SERVO <angle>       angle 0..180
//   LEVER               raccourci servo a 0 deg (mur leve)
//   BAISSER             raccourci servo a 180 deg (repos)
//
//   --- Reglages ---
//   SPEED <us>          delai entre transitions de phase (500..10000, defaut 2000)
//   DUTY <pct>          PWM ENA/ENB en % (10..60, defaut 40)
//   STATUS              etat actuel
//   HELP                cette aide

#include <Arduino.h>
#include <ESP32Servo.h>
#include "esp_task_wdt.h"

// ============================================================================
// Pins
// ============================================================================

struct Moteur {
  const char* nom;
  uint8_t in1, in2, in3, in4, ena, enb;
  int phase;
  bool actif;
};

static Moteur M1 = { "M1", 14, 27, 26, 25, 33, 32, 0, false };
static Moteur M2 = { "M2", 16, 17, 21, 22, 19, 23, 0, false };

static constexpr uint8_t PIN_LIMIT_X = 13;
static constexpr uint8_t PIN_LIMIT_Y = 18;
static constexpr uint8_t PIN_SERVO   = 4;

// ============================================================================
// Parametres
// ============================================================================

static constexpr uint32_t SPEED_DEFAUT_US = 10000;
static constexpr uint32_t SPEED_MIN_US    = 500;
static constexpr uint32_t SPEED_MAX_US    = 10000;
static constexpr uint32_t PAS_MAX         = 10000;

static constexpr uint8_t DUTY_DEFAUT_PCT = 40;
static constexpr uint8_t DUTY_MIN_PCT    = 10;
static constexpr uint8_t DUTY_MAX_PCT    = 60;

static constexpr uint16_t SERVO_REPOS_DEG = 180;
static constexpr uint16_t SERVO_LEVER_DEG = 0;
static constexpr uint16_t PULSE_MIN_US    = 500;
static constexpr uint16_t PULSE_MAX_US    = 2500;

static const uint8_t SEQUENCE[4][4] = {
  {1, 0, 1, 0},
  {0, 1, 1, 0},
  {0, 1, 0, 1},
  {1, 0, 0, 1}
};

static uint32_t demi_periode_us = SPEED_DEFAUT_US;
static uint8_t  duty_pct        = DUTY_DEFAUT_PCT;
static String   tampon_serie;
static Servo    servo;

// ============================================================================
// Fonctions moteur
// ============================================================================

static uint8_t duty_to_pwm(uint8_t pct) {
  uint32_t v = (uint32_t)pct * 255 / 100;
  return (uint8_t)(v > 255 ? 255 : v);
}

static void couper_phases(Moteur& m) {
  digitalWrite(m.in1, LOW);
  digitalWrite(m.in2, LOW);
  digitalWrite(m.in3, LOW);
  digitalWrite(m.in4, LOW);
}

static void appliquer_phase(Moteur& m, int idx) {
  digitalWrite(m.in1, SEQUENCE[idx][0] ? HIGH : LOW);
  digitalWrite(m.in2, SEQUENCE[idx][1] ? HIGH : LOW);
  digitalWrite(m.in3, SEQUENCE[idx][2] ? HIGH : LOW);
  digitalWrite(m.in4, SEQUENCE[idx][3] ? HIGH : LOW);
}

static void activer_driver(Moteur& m, bool actif) {
  m.actif = actif;
  if (actif) {
    uint8_t pwm = duty_to_pwm(duty_pct);
    analogWrite(m.ena, pwm);
    analogWrite(m.enb, pwm);
    appliquer_phase(m, m.phase);
  } else {
    analogWrite(m.ena, 0);
    analogWrite(m.enb, 0);
    couper_phases(m);
  }
}

static void appliquer_duty(Moteur& m) {
  if (!m.actif) return;
  uint8_t pwm = duty_to_pwm(duty_pct);
  analogWrite(m.ena, pwm);
  analogWrite(m.enb, pwm);
}

static void executer_pas(Moteur& m, uint32_t nb_pas, bool sens_forward) {
  for (uint32_t i = 0; i < nb_pas; ++i) {
    m.phase = (m.phase + (sens_forward ? 1 : 3)) & 3;
    appliquer_phase(m, m.phase);
    delayMicroseconds(demi_periode_us);
    if ((i & 0x3F) == 0) yield();
  }
}

// CoreXY : avance les phases de M1 ET M2 simultanement.
// Convention machine : X pur = M1 et M2 sens opposes, Y pur = M1 et M2 meme sens.
static void executer_pas_corexy(uint32_t nb_pas, bool m1_fwd, bool m2_fwd) {
  for (uint32_t i = 0; i < nb_pas; ++i) {
    M1.phase = (M1.phase + (m1_fwd ? 1 : 3)) & 3;
    appliquer_phase(M1, M1.phase);
    M2.phase = (M2.phase + (m2_fwd ? 1 : 3)) & 3;
    appliquer_phase(M2, M2.phase);
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
  Serial.println("  M1 F <n> | M1 B <n>   moteur 1 seul (1..10000 pas)");
  Serial.println("  M2 F <n> | M2 B <n>   moteur 2 seul");
  Serial.println("  X F <n>  | X B <n>    axe X pur CoreXY (M1 + M2 coordonnes)");
  Serial.println("  Y F <n>  | Y B <n>    axe Y pur CoreXY");
  Serial.println("                        (X et Y necessitent les 2 drivers ON)");
  Serial.println("  LIMITS             lecture X et Y");
  Serial.println("  LIMITS WATCH       lecture continue (Enter pour sortir)");
  Serial.println("  SERVO <angle>      angle 0..180");
  Serial.println("  LEVER | BAISSER    servo 0 deg / 180 deg");
  Serial.println("  SPEED <us>         delai entre pas (500..10000)");
  Serial.println("  DUTY <pct>         PWM en % (10..60)");
  Serial.println("  STATUS             etat actuel");
  Serial.println("  HELP               cette aide");
}

static void afficher_status() {
  Serial.print("  driver 1 : "); Serial.println(M1.actif ? "ON"  : "OFF");
  Serial.print("  driver 2 : "); Serial.println(M2.actif ? "ON"  : "OFF");
  Serial.print("  SPEED    : "); Serial.print(demi_periode_us); Serial.println(" us");
  Serial.print("  DUTY     : "); Serial.print(duty_pct); Serial.println(" %");
  Serial.print("  PHASE M1 : "); Serial.println(M1.phase);
  Serial.print("  PHASE M2 : "); Serial.println(M2.phase);
  Serial.print("  LIMIT X  : "); Serial.println(digitalRead(PIN_LIMIT_X) == LOW ? "LOW" : "HIGH");
  Serial.print("  LIMIT Y  : "); Serial.println(digitalRead(PIN_LIMIT_Y) == LOW ? "LOW" : "HIGH");
}

static void limits_watch() {
  Serial.println("LIMITS WATCH (Enter pour sortir)");
  int px = -1, py = -1;
  while (true) {
    int x = digitalRead(PIN_LIMIT_X);
    int y = digitalRead(PIN_LIMIT_Y);
    if (x != px || y != py) {
      Serial.print("X="); Serial.print(x == LOW ? "LOW " : "HIGH");
      Serial.print("  Y="); Serial.println(y == LOW ? "LOW " : "HIGH");
      px = x; py = y;
    }
    if (Serial.available()) { while (Serial.available()) Serial.read(); break; }
    delay(15);
  }
  Serial.println("(sortie LIMITS WATCH)");
}

// ============================================================================
// Parseur commandes
// ============================================================================

// Commande axe CoreXY (X ou Y). Necessite les DEUX drivers actifs.
static void cmd_axe(const char* nom, bool m1_fwd, bool m2_fwd, long n) {
  if (n <= 0 || n > (long)PAS_MAX) {
    Serial.print("N hors limite [1.."); Serial.print(PAS_MAX); Serial.println("]");
    return;
  }
  if (!M1.actif || !M2.actif) {
    Serial.println("Les 2 drivers doivent etre ON (tape EN ON).");
    return;
  }
  Serial.print(nom); Serial.print(' '); Serial.print(n); Serial.println(" pas ...");
  executer_pas_corexy((uint32_t)n, m1_fwd, m2_fwd);
  Serial.println("done");
}

static void cmd_moteur(Moteur& m, bool fwd, long n) {
  if (n <= 0 || n > (long)PAS_MAX) {
    Serial.print("N hors limite [1.."); Serial.print(PAS_MAX); Serial.println("]");
    return;
  }
  if (!m.actif) {
    Serial.print("Driver de "); Serial.print(m.nom);
    Serial.println(" OFF. Active-le d'abord.");
    return;
  }
  Serial.print(m.nom); Serial.print(' '); Serial.print(fwd ? 'F' : 'B');
  Serial.print(' '); Serial.print(n); Serial.println(" pas ...");
  executer_pas(m, (uint32_t)n, fwd);
  Serial.println("done");
}

static void traiter(String s) {
  s.trim();
  s.toUpperCase();
  if (s.length() == 0) return;

  if (s == "HELP")    { afficher_aide();  return; }
  if (s == "STATUS")  { afficher_status(); return; }
  if (s == "LIMITS")  {
    Serial.print("X="); Serial.print(digitalRead(PIN_LIMIT_X) == LOW ? "LOW " : "HIGH");
    Serial.print("  Y="); Serial.println(digitalRead(PIN_LIMIT_Y) == LOW ? "LOW " : "HIGH");
    return;
  }
  if (s == "LIMITS WATCH") { limits_watch(); return; }

  if (s == "EN1 ON")  { activer_driver(M1, true);  Serial.println("driver 1 ON");  return; }
  if (s == "EN1 OFF") { activer_driver(M1, false); Serial.println("driver 1 OFF"); return; }
  if (s == "EN2 ON")  { activer_driver(M2, true);  Serial.println("driver 2 ON");  return; }
  if (s == "EN2 OFF") { activer_driver(M2, false); Serial.println("driver 2 OFF"); return; }
  if (s == "EN ON")   { activer_driver(M1, true);  activer_driver(M2, true);
                        Serial.println("drivers 1 et 2 ON");  return; }
  if (s == "EN OFF")  { activer_driver(M1, false); activer_driver(M2, false);
                        Serial.println("drivers 1 et 2 OFF"); return; }

  if (s == "LEVER")   { servo.write(SERVO_LEVER_DEG); Serial.println("servo 0 deg (LEVER)");   return; }
  if (s == "BAISSER") { servo.write(SERVO_REPOS_DEG); Serial.println("servo 180 deg (BAISSER)"); return; }

  if (s.startsWith("SERVO ")) {
    long v = s.substring(6).toInt();
    if (v < 0 || v > 180) { Serial.println("angle hors [0..180]"); return; }
    servo.write((int)v);
    Serial.print("servo "); Serial.print(v); Serial.println(" deg");
    return;
  }

  if (s.startsWith("SPEED ")) {
    long v = s.substring(6).toInt();
    if (v < (long)SPEED_MIN_US || v > (long)SPEED_MAX_US) {
      Serial.print("SPEED hors limite ["); Serial.print(SPEED_MIN_US);
      Serial.print(".."); Serial.print(SPEED_MAX_US); Serial.println("] us");
      return;
    }
    demi_periode_us = (uint32_t)v;
    Serial.print("SPEED = "); Serial.print(demi_periode_us); Serial.println(" us");
    return;
  }

  if (s.startsWith("DUTY ")) {
    long v = s.substring(5).toInt();
    if (v < (long)DUTY_MIN_PCT || v > (long)DUTY_MAX_PCT) {
      Serial.print("DUTY hors limite ["); Serial.print(DUTY_MIN_PCT);
      Serial.print(".."); Serial.print(DUTY_MAX_PCT); Serial.println("] %");
      return;
    }
    duty_pct = (uint8_t)v;
    appliquer_duty(M1);
    appliquer_duty(M2);
    Serial.print("DUTY = "); Serial.print(duty_pct); Serial.println(" %");
    return;
  }

  if (s.startsWith("M1 F ") || s.startsWith("M1 B ")) {
    cmd_moteur(M1, s.charAt(3) == 'F', s.substring(5).toInt());
    return;
  }
  if (s.startsWith("M2 F ") || s.startsWith("M2 B ")) {
    cmd_moteur(M2, s.charAt(3) == 'F', s.substring(5).toInt());
    return;
  }
  // CoreXY : X pur = M1 et M2 sens opposes, Y pur = M1 et M2 meme sens.
  if (s.startsWith("X F ")) { cmd_axe("X F", true,  false, s.substring(4).toInt()); return; }
  if (s.startsWith("X B ")) { cmd_axe("X B", false, true,  s.substring(4).toInt()); return; }
  if (s.startsWith("Y F ")) { cmd_axe("Y F", true,  true,  s.substring(4).toInt()); return; }
  if (s.startsWith("Y B ")) { cmd_axe("Y B", false, false, s.substring(4).toInt()); return; }

  Serial.print("Commande inconnue : '"); Serial.print(s); Serial.println("' - tape HELP");
}

// ============================================================================
// Setup / Loop
// ============================================================================

void setup() {
  // 1. Servo init a 180 deg en TOUT PREMIER (securite mecanique du piston).
  servo.attach(PIN_SERVO, PULSE_MIN_US, PULSE_MAX_US);
  servo.write(SERVO_REPOS_DEG);

  // 2. Init pins moteurs en sortie + drivers OFF.
  for (Moteur* m : { &M1, &M2 }) {
    pinMode(m->in1, OUTPUT); pinMode(m->in2, OUTPUT);
    pinMode(m->in3, OUTPUT); pinMode(m->in4, OUTPUT);
    pinMode(m->ena, OUTPUT); pinMode(m->enb, OUTPUT);
    couper_phases(*m);
    analogWrite(m->ena, 0);
    analogWrite(m->enb, 0);
  }

  pinMode(PIN_LIMIT_X, INPUT_PULLUP);
  pinMode(PIN_LIMIT_Y, INPUT_PULLUP);

  esp_task_wdt_deinit();

  Serial.begin(115200);
  delay(500);
  Serial.println();
  Serial.println("=== Controle independant 2 L298N + servo + capteurs ===");
  Serial.println("M1: IN=14/27/26/25  ENA=33 ENB=32");
  Serial.println("M2: IN=16/17/21/22  ENA=19 ENB=23");
  Serial.println("Capteurs: X=13 Y=18    Servo: 4");
  Serial.println("Drivers DESACTIVES au boot. EN1 ON / EN2 ON pour activer.");
  Serial.print("DUTY par defaut : "); Serial.print(duty_pct); Serial.println(" %");
  Serial.println("ATTENTION : touche les L298N regulierement. Si trop chaud -> EN OFF + baisser DUTY.");
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
