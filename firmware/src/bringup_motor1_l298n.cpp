// Sketch de test : moteur 1 (NEMA17) pilote via pont en H L298N.
// Cible : ESP32-WROOM (Freenove DevKit)
//
// Cablage L298N :
//   IN1 -> GPIO 14   phase A+
//   IN2 -> GPIO 27   phase A-
//   IN3 -> GPIO 26   phase B+
//   IN4 -> GPIO 25   phase B-
//   ENA -> GPIO 33   PWM canal A (limitation courant moyen)
//   ENB -> GPIO 32   PWM canal B
//   OUT1/OUT2 -> bobine A du moteur (noir/vert)
//   OUT3/OUT4 -> bobine B du moteur (rouge/bleu)
//   +12V / GND -> alim 12V breadboard
//   Jumpers ENA et ENB du L298N RETIRES (pour piloter ENA/ENB en PWM)
//   Jumper 5V_EN du L298N EN PLACE (regulateur 5V interne actif)
//
// ATTENTION : le L298N n'a pas de regulation de courant interne.
//             DUTY (PWM sur ENA/ENB) limite le courant moyen via PWM.
//             Toucher le L298N pendant le test : si trop chaud pour le doigt,
//             couper immediatement et baisser DUTY.
//
// Commandes serie (115200 baud) :
//   M1 F <n>    forward n pas full-step (1..10000)
//   M1 B <n>    backward n pas
//   EN ON       active driver (PWM ON, phase courante appliquee)
//   EN OFF      desactive driver - etat boot
//   SPEED <us>  delai entre transitions de phase (500..10000, defaut 2000)
//   DUTY <pct>  PWM en pourcent (10..60, defaut 40)
//   STATUS      etat actuel
//   HELP        cette aide

#include <Arduino.h>
#include "esp_task_wdt.h"

static constexpr uint8_t PIN_IN1 = 14;
static constexpr uint8_t PIN_IN2 = 27;
static constexpr uint8_t PIN_IN3 = 26;
static constexpr uint8_t PIN_IN4 = 25;
static constexpr uint8_t PIN_ENA = 33;
static constexpr uint8_t PIN_ENB = 32;

static constexpr uint32_t SPEED_DEFAUT_US = 2000;  // 2 ms entre transitions
static constexpr uint32_t SPEED_MIN_US    = 500;
static constexpr uint32_t SPEED_MAX_US    = 10000;
static constexpr uint32_t PAS_MAX         = 10000;

static constexpr uint8_t  DUTY_DEFAUT_PCT = 40;
static constexpr uint8_t  DUTY_MIN_PCT    = 10;
static constexpr uint8_t  DUTY_MAX_PCT    = 60;  // garde-fou anti-surchauffe

// Sequence full-step 4 phases : (IN1, IN2, IN3, IN4)
// Step 0 : A+ B+   Step 1 : A- B+   Step 2 : A- B-   Step 3 : A+ B-
static const uint8_t SEQUENCE[4][4] = {
  {1, 0, 1, 0},
  {0, 1, 1, 0},
  {0, 1, 0, 1},
  {1, 0, 0, 1}
};

static uint32_t demi_periode_us = SPEED_DEFAUT_US;
static uint8_t  duty_pct        = DUTY_DEFAUT_PCT;
static int      phase_courante  = 0;
static bool     driver_actif    = false;
static String   tampon_serie;

static uint8_t duty_to_pwm(uint8_t pct) {
  uint32_t v = (uint32_t)pct * 255 / 100;
  return (uint8_t)(v > 255 ? 255 : v);
}

static void couper_phases() {
  digitalWrite(PIN_IN1, LOW);
  digitalWrite(PIN_IN2, LOW);
  digitalWrite(PIN_IN3, LOW);
  digitalWrite(PIN_IN4, LOW);
}

static void appliquer_phase(int index) {
  digitalWrite(PIN_IN1, SEQUENCE[index][0] ? HIGH : LOW);
  digitalWrite(PIN_IN2, SEQUENCE[index][1] ? HIGH : LOW);
  digitalWrite(PIN_IN3, SEQUENCE[index][2] ? HIGH : LOW);
  digitalWrite(PIN_IN4, SEQUENCE[index][3] ? HIGH : LOW);
}

static void activer_driver(bool actif) {
  driver_actif = actif;
  if (actif) {
    uint8_t pwm = duty_to_pwm(duty_pct);
    analogWrite(PIN_ENA, pwm);
    analogWrite(PIN_ENB, pwm);
    appliquer_phase(phase_courante);  // couple de maintien
  } else {
    analogWrite(PIN_ENA, 0);
    analogWrite(PIN_ENB, 0);
    couper_phases();
  }
}

static void executer_pas(uint32_t nb_pas, bool sens_forward) {
  for (uint32_t i = 0; i < nb_pas; ++i) {
    // +1 mod 4 si forward, -1 mod 4 si backward (= +3 mod 4)
    phase_courante = (phase_courante + (sens_forward ? 1 : 3)) & 3;
    appliquer_phase(phase_courante);
    delayMicroseconds(demi_periode_us);

    if ((i & 0x3F) == 0) yield();
  }
}

static void afficher_aide() {
  Serial.println("Commandes :");
  Serial.println("  M1 F <n>    forward n pas (1..10000)");
  Serial.println("  M1 B <n>    backward n pas");
  Serial.println("  EN ON       active driver");
  Serial.println("  EN OFF      desactive driver (etat boot)");
  Serial.println("  SPEED <us>  delai entre pas en us (500..10000, defaut 2000)");
  Serial.println("  DUTY <pct>  PWM en % (10..60, defaut 40)");
  Serial.println("  STATUS      etat actuel");
  Serial.println("  HELP        cette aide");
}

static void afficher_status() {
  Serial.print("  EN     : ");
  Serial.println(driver_actif ? "ON  (driver actif)" : "OFF (driver coupe)");
  Serial.print("  SPEED  : ");
  Serial.print(demi_periode_us);
  Serial.print(" us  (~");
  Serial.print(1000000UL / demi_periode_us);
  Serial.println(" pas/s)");
  Serial.print("  DUTY   : ");
  Serial.print(duty_pct);
  Serial.println(" %");
  Serial.print("  PHASE  : ");
  Serial.println(phase_courante);
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

  if (s.startsWith("DUTY ")) {
    long v = s.substring(5).toInt();
    if (v < (long)DUTY_MIN_PCT || v > (long)DUTY_MAX_PCT) {
      Serial.print("DUTY hors limite [");
      Serial.print(DUTY_MIN_PCT);
      Serial.print("..");
      Serial.print(DUTY_MAX_PCT);
      Serial.println("] %");
      return;
    }
    duty_pct = (uint8_t)v;
    if (driver_actif) {
      uint8_t pwm = duty_to_pwm(duty_pct);
      analogWrite(PIN_ENA, pwm);
      analogWrite(PIN_ENB, pwm);
    }
    Serial.print("DUTY = ");
    Serial.print(duty_pct);
    Serial.println(" %");
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
    if (!driver_actif) {
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

  esp_task_wdt_deinit();  // mouvements potentiellement longs

  pinMode(PIN_IN1, OUTPUT);
  pinMode(PIN_IN2, OUTPUT);
  pinMode(PIN_IN3, OUTPUT);
  pinMode(PIN_IN4, OUTPUT);
  pinMode(PIN_ENA, OUTPUT);
  pinMode(PIN_ENB, OUTPUT);

  // SECURITE : tout coupe au boot
  couper_phases();
  analogWrite(PIN_ENA, 0);
  analogWrite(PIN_ENB, 0);

  Serial.println();
  Serial.println("=== Test moteur 1 (L298N + NEMA17) ===");
  Serial.println("IN1=14 IN2=27 IN3=26 IN4=25 ENA=33 ENB=32");
  Serial.println("Driver DESACTIVE au boot. Tape 'EN ON' pour activer.");
  Serial.print("Duty par defaut : ");
  Serial.print(duty_pct);
  Serial.println(" %");
  Serial.println("ATTENTION : touche le L298N regulierement.");
  Serial.println("Si trop chaud -> coupe et baisse DUTY.");
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
