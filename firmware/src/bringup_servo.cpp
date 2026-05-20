// Sketch de test : servo SG90 pour mecanisme placement des murs.
// Cible : ESP32-WROOM (Freenove DevKit)
//
// Cablage SG90 :
//   Signal (orange) -> GPIO 4
//   V+ (rouge)      -> alim EXTERNE 5V dediee (PAS le 5V de l'ESP32)
//   GND (marron)    -> GND alim externe ET GND ESP32 (masse commune OBLIGATOIRE)
//
// IMPORTANT : la masse de l'alim 5V externe DOIT etre reliee a la masse de
//             l'ESP32. Sans masse commune le signal PWM n'a pas de reference
//             et le servo vibre, ne tourne pas, ou ne suit pas la consigne.
//
// SG90 accepte un signal 3.3V de l'ESP32 sans level-shifter
// (datasheet : VIH min ~2V).
//
// Convention mecanique de CE mecanisme de placement des murs :
//   - 180 deg = position de REPOS (mecanisme retracte, plateau en securite)
//   - 0   deg = mur LEVE (mecanisme deploye)
//
// Au boot le servo est ATTACHE et force a 180 deg (position de repos),
// sinon le mecanisme casse si le servo demarre dans une autre position.
//
// Commandes serie (115200 baud) :
//   SERVO <angle>  deplace le servo a l'angle donne (0..180 deg)
//   HOME           retour a 180 deg (position de repos)
//   ATTACH         attache le servo (signal PWM ON)
//   DETACH         relache le servo (coupe le signal, plus de couple)
//                  ATTENTION : sans couple le servo peut deriver, ne pas
//                  utiliser pendant le jeu, seulement pour debug.
//   STATUS         etat actuel
//   HELP           cette aide

#include <Arduino.h>
#include <ESP32Servo.h>

static constexpr uint8_t PIN_SERVO   = 4;
static constexpr int     ANGLE_MIN   = 0;
static constexpr int     ANGLE_MAX   = 180;
static constexpr int     ANGLE_REPOS = 180;  // position mecanique de base (boot + HOME)
static constexpr int     ANGLE_MUR   = 0;    // position "mur leve" (juste pour info)

// Largeur d'impulsion calibree SG90. Les bornes standards 1000-2000 us peuvent
// limiter la course; 500-2400 us donne la course complete sur la plupart des
// SG90. A ajuster si le servo force en butee mecanique.
static constexpr int PULSE_MIN_US = 500;
static constexpr int PULSE_MAX_US = 2400;

static Servo  servo;
static int    angle_courant  = ANGLE_REPOS;
static bool   servo_attache  = false;
static String tampon_serie;

static void attacher() {
  if (servo_attache) return;
  servo.setPeriodHertz(50);                              // 50 Hz = periode 20 ms
  servo.attach(PIN_SERVO, PULSE_MIN_US, PULSE_MAX_US);
  servo_attache = true;
}

static void detacher() {
  if (!servo_attache) return;
  servo.detach();
  servo_attache = false;
}

static void afficher_aide() {
  Serial.println("Commandes :");
  Serial.println("  SERVO <angle>  deplace le servo (0..180 deg)");
  Serial.println("  HOME           retour position de repos (180 deg)");
  Serial.println("  ATTACH         attache le servo (signal PWM ON)");
  Serial.println("  DETACH         relache le servo (signal PWM OFF, plus de couple)");
  Serial.println("                 ATTENTION : sans couple le servo peut deriver,");
  Serial.println("                 a n'utiliser que pour debug.");
  Serial.println("  STATUS         etat actuel");
  Serial.println("  HELP           cette aide");
}

static void afficher_status() {
  Serial.print("  ATTACH : ");
  Serial.println(servo_attache ? "ON (signal PWM actif)" : "OFF (servo libre)");
  Serial.print("  ANGLE  : ");
  Serial.print(angle_courant);
  Serial.println(" deg");
  Serial.print("  PIN    : GPIO ");
  Serial.println(PIN_SERVO);
}

static void traiter(String s) {
  s.trim();
  s.toUpperCase();
  if (s.length() == 0) return;

  if (s == "HELP")   { afficher_aide();  return; }
  if (s == "STATUS") { afficher_status(); return; }
  if (s == "ATTACH") { attacher();  Serial.println("servo ATTACH"); return; }
  if (s == "DETACH") { detacher();  Serial.println("servo DETACH"); return; }

  if (s == "HOME") {
    attacher();
    angle_courant = ANGLE_REPOS;
    servo.write(angle_courant);
    Serial.print("servo HOME -> ");
    Serial.print(angle_courant);
    Serial.println(" deg (repos)");
    return;
  }

  if (s.startsWith("SERVO ")) {
    long v = s.substring(6).toInt();
    if (v < (long)ANGLE_MIN || v > (long)ANGLE_MAX) {
      Serial.print("Angle hors limite [");
      Serial.print(ANGLE_MIN);
      Serial.print("..");
      Serial.print(ANGLE_MAX);
      Serial.println("] deg");
      return;
    }
    attacher();
    angle_courant = (int)v;
    servo.write(angle_courant);
    Serial.print("servo -> ");
    Serial.print(angle_courant);
    Serial.println(" deg");
    return;
  }

  Serial.print("Commande inconnue : '");
  Serial.print(s);
  Serial.println("' - tape HELP");
}

void setup() {
  Serial.begin(115200);
  delay(500);

  // Allouer un timer LEDC pour ESP32Servo (l'ESP32 en a 4 disponibles)
  ESP32PWM::allocateTimer(0);

  // SECURITE MECANIQUE : force le servo a 180 deg (position de repos) au boot.
  // Le mecanisme casse si le servo demarre dans une autre position.
  attacher();
  angle_courant = ANGLE_REPOS;
  servo.write(angle_courant);

  Serial.println();
  Serial.println("=== Test servo SG90 ===");
  Serial.print("Signal sur GPIO ");
  Serial.println(PIN_SERVO);
  Serial.println("V+ sur alim externe 5V (masse commune ESP32 OBLIGATOIRE)");
  Serial.print("Servo ATTACHE au boot, force a ");
  Serial.print(ANGLE_REPOS);
  Serial.println(" deg (position de repos).");
  Serial.print("Convention : ");
  Serial.print(ANGLE_REPOS);
  Serial.print(" deg = repos, ");
  Serial.print(ANGLE_MUR);
  Serial.println(" deg = mur leve.");
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
