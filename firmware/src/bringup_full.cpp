// Sketch d'integration : CoreXY (2 moteurs L298N) + 2 fins de course + servo SG90.
// Cible : ESP32-WROOM (Freenove DevKit). Combine bringup_motors_and_limits + bringup_servo.
//
// But du sketch : permettre de tester le cycle complet de placement d'un mur :
//   1. HOME  : initialisation des moteurs (chariot a l'origine)
//   2. GOTO X Y : placement du chariot sous le levier d'un mur
//   3. LEVER : servo a 0 deg, le piston pousse le levier qui leve le mur
//   4. BAISSER : servo a 180 deg, le piston redescend, le chariot peut bouger
//
// === Cablage ===
//
//   Moteur 1 (L298N #1)
//     IN1 -> GPIO 14   IN2 -> GPIO 27   IN3 -> GPIO 26   IN4 -> GPIO 25
//     ENA -> GPIO 33   ENB -> GPIO 32
//
//   Moteur 2 (L298N #2)
//     IN1 -> GPIO 16   IN2 -> GPIO 17   IN3 -> GPIO 21   IN4 -> GPIO 22
//     ENA -> GPIO 19   ENB -> GPIO 23
//
//   Capteur 1 (fin de course axe X) : entre GPIO 13 et GND (INPUT_PULLUP)
//   Capteur 2 (fin de course axe Y) : entre GPIO 18 et GND (INPUT_PULLUP)
//
//   Servo SG90 (piston placement murs) :
//     Signal (orange) -> GPIO 4
//     V+     (rouge)  -> alim externe 5V (PAS le 5V de l'ESP32)
//     GND    (marron) -> GND alim externe ET GND ESP32 (masse commune OBLIGATOIRE)
//
//   Convention servo : 180 deg = REPOS (piston bas), 0 deg = MUR LEVE (piston haut).
//
//   Alim 12V partagee moteurs, masses communes (ESP32 + alim 12V + 2 L298N + alim 5V servo).
//   Jumpers ENA/ENB des 2 L298N RETIRES. Jumpers 5V_EN en place.
//
// === Conventions CoreXY (validees 2026-05-20 sur cette machine) ===
//
//   X pur : M1 et M2 sens OPPOSES   (Capteur 1 = fin de course X-)
//   Y pur : M1 et M2 MEME sens      (Capteur 2 = fin de course Y-)
//   X F (forward) = s'eloigne de l'origine X. X B = vers Capteur 1.
//   Y F (forward) = s'eloigne de l'origine Y. Y B = vers Capteur 2.
//   Origine (0, 0) etablie par HOME : 20 pas apres contact des deux capteurs.
//
// === Tracking de position ===
//
//   La position du chariot est connue UNIQUEMENT apres un HOME reussi.
//   Toute commande M1/M2 individuelle (debug, mouvement diagonal) INVALIDE
//   la position. Refaire HOME pour utiliser GOTO.
//
// === Commandes serie (115200 baud) ===
//
//   HOME              homing X puis Y, etablit l'origine (0, 0)
//   GOTO <x> <y>      deplace le chariot a (x, y) en pas depuis l'origine
//                     (necessite HOME prealable)
//   LEVER             servo a 0 deg (piston monte, leve le mur)
//   BAISSER           servo a 180 deg (piston redescend, position de repos)
//   SERVO <angle>     position arbitraire du servo (0..180) - debug
//
//   X F/B <n>         axe X pur (M1 et M2 sens opposes)  -- update position
//   Y F/B <n>         axe Y pur (M1 et M2 meme sens)     -- update position
//   M1 F/B <n>        moteur 1 SEUL - debug (diagonale)  -- INVALIDE position
//   M2 F/B <n>        moteur 2 SEUL - debug (diagonale)  -- INVALIDE position
//
//   LIMITS            lecture instantanee L1/L2
//   LIMITS WATCH      affichage continu des transitions (Enter pour sortir)
//   EN ON | EN OFF    active / coupe les 2 drivers moteur
//   SPEED <us>        delai inter-pas (500..10000, defaut 8000)
//   DUTY <pct>        PWM moteurs (10..60, defaut 60)
//   STATUS            etat courant (servo + moteurs + position + limits)
//   HELP              cette aide
//
// === Securite ===
//
//   - Servo ATTACHE au boot et force a 180 deg (position de repos).
//     Sinon le mecanisme de placement des murs casse.
//   - Drivers moteurs DESACTIVES au boot.
//   - GOTO refuse si position pas connue (HOME manquant).
//   - GOTO refuse si la cible sort des bornes [0..GOTO_X_MAX] x [0..GOTO_Y_MAX].

#include <Arduino.h>
#include <ESP32Servo.h>
#include "esp_task_wdt.h"

// ============================================================================
// Pins
// ============================================================================

static constexpr uint8_t PIN_LIMIT_1 = 13;
static constexpr uint8_t PIN_LIMIT_2 = 18;
static constexpr uint8_t PIN_SERVO   = 4;

struct Moteur {
  const char* nom;
  uint8_t in1, in2, in3, in4;
  uint8_t ena, enb;
  int phase_courante;
};

static Moteur M1 = { "M1", 14, 27, 26, 25, 33, 32, 0 };
static Moteur M2 = { "M2", 16, 17, 21, 22, 19, 23, 0 };

// ============================================================================
// Parametres moteurs
// ============================================================================

static constexpr uint32_t SPEED_DEFAUT_US = 8000;
static constexpr uint32_t SPEED_MIN_US    = 500;
static constexpr uint32_t SPEED_MAX_US    = 10000;
static constexpr uint32_t PAS_MAX         = 10000;

static constexpr uint8_t  DUTY_DEFAUT_PCT = 60;
static constexpr uint8_t  DUTY_MIN_PCT    = 10;
static constexpr uint8_t  DUTY_MAX_PCT    = 60;

static constexpr uint32_t HOME_PAS_MAX    = 4000;
static constexpr uint32_t HOME_RECUL_PAS  = 20;
static constexpr uint32_t HOME_LIBERATION = 50;

// Bornes GOTO. Mesures faites au homing : ~553 pas X, ~506 pas Y de l'origine
// jusqu'a la butee. Bornes confortables au-dessus de la course mesuree au cas
// ou la mesure varie ou l'origine bouge legerement. A ajuster si besoin.
static constexpr long GOTO_X_MAX = 700;
static constexpr long GOTO_Y_MAX = 700;

// Sequence full-step 4 phases : (IN1, IN2, IN3, IN4)
static const uint8_t SEQUENCE[4][4] = {
  {1, 0, 1, 0},
  {0, 1, 1, 0},
  {0, 1, 0, 1},
  {1, 0, 0, 1}
};

static uint32_t demi_periode_us = SPEED_DEFAUT_US;
static uint8_t  duty_pct        = DUTY_DEFAUT_PCT;
static bool     driver_actif    = false;
static String   tampon_serie;

// ============================================================================
// Parametres servo
// ============================================================================

static constexpr int ANGLE_MIN   = 0;
static constexpr int ANGLE_MAX   = 180;
static constexpr int ANGLE_REPOS = 180;   // position mecanique de repos
static constexpr int ANGLE_MUR   = 0;     // mur leve
static constexpr int PULSE_MIN_US = 500;
static constexpr int PULSE_MAX_US = 2400;

static Servo servo;
static int   angle_servo     = ANGLE_REPOS;
static bool  servo_attache   = false;

// ============================================================================
// Tracking de position
// ============================================================================

static long position_x_pas   = 0;
static long position_y_pas   = 0;
static bool position_connue  = false;  // passe a true apres HOME reussi

// ============================================================================
// Helpers moteur
// ============================================================================

static uint8_t duty_to_pwm(uint8_t pct) {
  uint32_t v = (uint32_t)pct * 255 / 100;
  return (uint8_t)(v > 255 ? 255 : v);
}

static void couper_phases(const Moteur& m) {
  digitalWrite(m.in1, LOW);
  digitalWrite(m.in2, LOW);
  digitalWrite(m.in3, LOW);
  digitalWrite(m.in4, LOW);
}

static void appliquer_phase(const Moteur& m, int idx) {
  digitalWrite(m.in1, SEQUENCE[idx][0] ? HIGH : LOW);
  digitalWrite(m.in2, SEQUENCE[idx][1] ? HIGH : LOW);
  digitalWrite(m.in3, SEQUENCE[idx][2] ? HIGH : LOW);
  digitalWrite(m.in4, SEQUENCE[idx][3] ? HIGH : LOW);
}

static void appliquer_pwm(const Moteur& m, uint8_t pwm) {
  analogWrite(m.ena, pwm);
  analogWrite(m.enb, pwm);
}

static void activer_drivers(bool actif) {
  driver_actif = actif;
  if (actif) {
    uint8_t pwm = duty_to_pwm(duty_pct);
    appliquer_pwm(M1, pwm);
    appliquer_pwm(M2, pwm);
    appliquer_phase(M1, M1.phase_courante);
    appliquer_phase(M2, M2.phase_courante);
  } else {
    appliquer_pwm(M1, 0);
    appliquer_pwm(M2, 0);
    couper_phases(M1);
    couper_phases(M2);
  }
}

static void faire_un_pas(Moteur& m, bool sens_forward) {
  m.phase_courante = (m.phase_courante + (sens_forward ? 1 : 3)) & 3;
  appliquer_phase(m, m.phase_courante);
  delayMicroseconds(demi_periode_us);
}

static void executer_pas(Moteur& m, uint32_t nb_pas, bool sens_forward) {
  for (uint32_t i = 0; i < nb_pas; ++i) {
    faire_un_pas(m, sens_forward);
    if ((i & 0x3F) == 0) yield();
  }
}

// ============================================================================
// Mouvements coordonnes CoreXY
// ============================================================================

static void faire_un_pas_coordonne(bool m1_forward, bool m2_forward) {
  M1.phase_courante = (M1.phase_courante + (m1_forward ? 1 : 3)) & 3;
  M2.phase_courante = (M2.phase_courante + (m2_forward ? 1 : 3)) & 3;
  appliquer_phase(M1, M1.phase_courante);
  appliquer_phase(M2, M2.phase_courante);
  delayMicroseconds(demi_periode_us);
}

static void executer_axe_X(uint32_t nb_pas, bool forward) {
  // X = M1 et M2 sens opposes
  for (uint32_t i = 0; i < nb_pas; ++i) {
    faire_un_pas_coordonne(forward, !forward);
    if ((i & 0x3F) == 0) yield();
  }
}

static void executer_axe_Y(uint32_t nb_pas, bool forward) {
  // Y = M1 et M2 meme sens
  for (uint32_t i = 0; i < nb_pas; ++i) {
    faire_un_pas_coordonne(forward, forward);
    if ((i & 0x3F) == 0) yield();
  }
}

// ============================================================================
// Homing
// ============================================================================

static bool homing_axe(const char* nom,
                       uint8_t pin_limit,
                       bool m1_fwd_vers_switch,
                       bool m2_fwd_vers_switch) {
  Serial.print("HOME ");
  Serial.print(nom);
  Serial.println(" ...");

  if (digitalRead(pin_limit) == LOW) {
    Serial.print("  switch deja LOW, recul de ");
    Serial.print(HOME_LIBERATION);
    Serial.println(" pas pour liberer");
    for (uint32_t i = 0; i < HOME_LIBERATION; ++i) {
      faire_un_pas_coordonne(!m1_fwd_vers_switch, !m2_fwd_vers_switch);
      if ((i & 0x3F) == 0) yield();
    }
    if (digitalRead(pin_limit) == LOW) {
      Serial.println("  ERREUR : switch toujours LOW apres liberation");
      return false;
    }
  }

  for (uint32_t i = 0; i < HOME_PAS_MAX; ++i) {
    if (digitalRead(pin_limit) == LOW) {
      Serial.print("  contact apres ");
      Serial.print(i);
      Serial.println(" pas");
      for (uint32_t j = 0; j < HOME_RECUL_PAS; ++j) {
        faire_un_pas_coordonne(!m1_fwd_vers_switch, !m2_fwd_vers_switch);
        if ((j & 0x3F) == 0) yield();
      }
      Serial.print("  axe ");
      Serial.print(nom);
      Serial.println(" origine etablie");
      return true;
    }
    faire_un_pas_coordonne(m1_fwd_vers_switch, m2_fwd_vers_switch);
    if ((i & 0x3F) == 0) yield();
  }

  Serial.print("  ERREUR : ");
  Serial.print(HOME_PAS_MAX);
  Serial.println(" pas sans toucher le switch -> abandon");
  return false;
}

static void executer_home() {
  if (!driver_actif) {
    Serial.println("Driver OFF. Tape 'EN ON' d'abord.");
    return;
  }

  bool ok_x = homing_axe("X", PIN_LIMIT_1, /*m1*/ false, /*m2*/ true);
  bool ok_y = homing_axe("Y", PIN_LIMIT_2, /*m1*/ false, /*m2*/ false);

  if (ok_x && ok_y) {
    position_x_pas  = 0;
    position_y_pas  = 0;
    position_connue = true;
    Serial.println("HOME OK : chariot a l'origine (X=0, Y=0)");
  } else {
    position_connue = false;
    Serial.println("HOME ECHEC (voir messages ci-dessus) - position INCONNUE");
  }
}

// ============================================================================
// GOTO
// ============================================================================

static void executer_goto(long x_cible, long y_cible) {
  if (!driver_actif) {
    Serial.println("Driver OFF. Tape 'EN ON' d'abord.");
    return;
  }
  if (!position_connue) {
    Serial.println("Position INCONNUE. Tape 'HOME' d'abord.");
    return;
  }
  if (x_cible < 0 || x_cible > GOTO_X_MAX) {
    Serial.print("X hors limite [0..");
    Serial.print(GOTO_X_MAX);
    Serial.println("] pas");
    return;
  }
  if (y_cible < 0 || y_cible > GOTO_Y_MAX) {
    Serial.print("Y hors limite [0..");
    Serial.print(GOTO_Y_MAX);
    Serial.println("] pas");
    return;
  }

  long dx = x_cible - position_x_pas;
  long dy = y_cible - position_y_pas;

  Serial.print("GOTO (");
  Serial.print(x_cible);
  Serial.print(", ");
  Serial.print(y_cible);
  Serial.print(") depuis (");
  Serial.print(position_x_pas);
  Serial.print(", ");
  Serial.print(position_y_pas);
  Serial.print(") -> dx=");
  Serial.print(dx);
  Serial.print(" dy=");
  Serial.println(dy);

  if (dx != 0) {
    bool forward = (dx > 0);
    uint32_t n = (uint32_t)(forward ? dx : -dx);
    Serial.print("  X ");
    Serial.print(forward ? "F " : "B ");
    Serial.print(n);
    Serial.println(" ...");
    executer_axe_X(n, forward);
    position_x_pas = x_cible;
  }
  if (dy != 0) {
    bool forward = (dy > 0);
    uint32_t n = (uint32_t)(forward ? dy : -dy);
    Serial.print("  Y ");
    Serial.print(forward ? "F " : "B ");
    Serial.print(n);
    Serial.println(" ...");
    executer_axe_Y(n, forward);
    position_y_pas = y_cible;
  }
  Serial.print("GOTO OK : position (");
  Serial.print(position_x_pas);
  Serial.print(", ");
  Serial.print(position_y_pas);
  Serial.println(")");
}

// ============================================================================
// Servo
// ============================================================================

static void attacher_servo() {
  if (servo_attache) return;
  servo.setPeriodHertz(50);
  servo.attach(PIN_SERVO, PULSE_MIN_US, PULSE_MAX_US);
  servo_attache = true;
}

static void detacher_servo() {
  if (!servo_attache) return;
  servo.detach();
  servo_attache = false;
}

static void servo_aller_a(int angle) {
  if (angle < ANGLE_MIN || angle > ANGLE_MAX) {
    Serial.print("Angle hors limite [");
    Serial.print(ANGLE_MIN);
    Serial.print("..");
    Serial.print(ANGLE_MAX);
    Serial.println("] deg");
    return;
  }
  attacher_servo();
  angle_servo = angle;
  servo.write(angle_servo);
  Serial.print("servo -> ");
  Serial.print(angle_servo);
  Serial.println(" deg");
}

// ============================================================================
// LIMITS
// ============================================================================

static void lire_limits_une_fois() {
  int l1 = digitalRead(PIN_LIMIT_1);
  int l2 = digitalRead(PIN_LIMIT_2);
  Serial.print("L1=");
  Serial.print(l1 == LOW ? "LOW " : "HIGH");
  Serial.print("  L2=");
  Serial.println(l2 == LOW ? "LOW " : "HIGH");
}

static void watch_limits() {
  Serial.println("LIMITS WATCH : appuie sur Enter pour sortir");
  int dernier_l1 = -1;
  int dernier_l2 = -1;
  while (true) {
    int l1 = digitalRead(PIN_LIMIT_1);
    int l2 = digitalRead(PIN_LIMIT_2);
    if (l1 != dernier_l1 || l2 != dernier_l2) {
      Serial.print("  L1=");
      Serial.print(l1 == LOW ? "LOW " : "HIGH");
      Serial.print("  L2=");
      Serial.println(l2 == LOW ? "LOW " : "HIGH");
      dernier_l1 = l1;
      dernier_l2 = l2;
    }
    if (Serial.available()) {
      char c = (char)Serial.read();
      if (c == '\n' || c == '\r') {
        Serial.println("WATCH stop");
        while (Serial.available()) Serial.read();
        return;
      }
    }
    delay(20);
  }
}

// ============================================================================
// Parser
// ============================================================================

static void afficher_aide() {
  Serial.println("Commandes :");
  Serial.println("  HOME                  homing X puis Y, etablit l'origine (0,0)");
  Serial.println("  GOTO <x> <y>          deplace chariot a (x,y) en pas (necessite HOME)");
  Serial.println("  LEVER                 servo a 0 deg (piston monte, leve un mur)");
  Serial.println("  BAISSER               servo a 180 deg (piston au repos)");
  Serial.println("  SERVO <angle>         angle arbitraire (0..180) - debug");
  Serial.println("  X F/B <n> | Y F/B <n> deplacement axe pur (update position)");
  Serial.println("  M1 F/B <n>            moteur 1 SEUL (diagonale) - INVALIDE position");
  Serial.println("  M2 F/B <n>            moteur 2 SEUL (diagonale) - INVALIDE position");
  Serial.println("  LIMITS | LIMITS WATCH lecture / surveillance des fins de course");
  Serial.println("  EN ON | EN OFF        active / coupe les 2 drivers moteur");
  Serial.println("  SPEED <us>            delai inter-pas (500..10000, defaut 8000)");
  Serial.println("  DUTY <pct>            PWM moteurs (10..60, defaut 60)");
  Serial.println("  STATUS                etat courant");
  Serial.println("  HELP                  cette aide");
}

static void afficher_status() {
  Serial.print("  EN     : ");
  Serial.println(driver_actif ? "ON" : "OFF");
  Serial.print("  SPEED  : ");
  Serial.print(demi_periode_us);
  Serial.print(" us  (~");
  Serial.print(1000000UL / demi_periode_us);
  Serial.println(" pas/s)");
  Serial.print("  DUTY   : ");
  Serial.print(duty_pct);
  Serial.println(" %");
  Serial.print("  POS    : ");
  if (position_connue) {
    Serial.print("(");
    Serial.print(position_x_pas);
    Serial.print(", ");
    Serial.print(position_y_pas);
    Serial.println(") pas");
  } else {
    Serial.println("INCONNUE (faire HOME)");
  }
  Serial.print("  SERVO  : ");
  Serial.print(angle_servo);
  Serial.print(" deg  (");
  Serial.print(servo_attache ? "attache" : "detache");
  Serial.println(")");
  lire_limits_une_fois();
}

static bool parser_moteur(const String& s) {
  if (s.length() < 5) return false;
  Moteur* m;
  if (s.startsWith("M1 ")) {
    m = &M1;
  } else if (s.startsWith("M2 ")) {
    m = &M2;
  } else {
    return false;
  }
  char sens = s.charAt(3);
  if ((sens != 'F' && sens != 'B') || s.charAt(4) != ' ') return false;
  long n = s.substring(5).toInt();
  if (n <= 0 || n > (long)PAS_MAX) {
    Serial.print("N hors limite [1..");
    Serial.print(PAS_MAX);
    Serial.println("]");
    return true;
  }
  if (!driver_actif) {
    Serial.println("Driver OFF. Tape 'EN ON' d'abord.");
    return true;
  }
  bool forward = (sens == 'F');
  Serial.print(m->nom);
  Serial.print(forward ? " F " : " B ");
  Serial.print(n);
  Serial.println(" pas (DIAGONAL - INVALIDE position) ...");
  executer_pas(*m, (uint32_t)n, forward);
  position_connue = false;
  Serial.println("done");
  return true;
}

static bool parser_axe(const String& s) {
  if (s.length() < 5) return false;
  char axe = s.charAt(0);
  if (axe != 'X' && axe != 'Y') return false;
  if (s.charAt(1) != ' ') return false;
  char sens = s.charAt(2);
  if ((sens != 'F' && sens != 'B') || s.charAt(3) != ' ') return false;
  long n = s.substring(4).toInt();
  if (n <= 0 || n > (long)PAS_MAX) {
    Serial.print("N hors limite [1..");
    Serial.print(PAS_MAX);
    Serial.println("]");
    return true;
  }
  if (!driver_actif) {
    Serial.println("Driver OFF. Tape 'EN ON' d'abord.");
    return true;
  }
  bool forward = (sens == 'F');
  Serial.print(axe);
  Serial.print(forward ? " F " : " B ");
  Serial.print(n);
  Serial.println(" pas ...");
  if (axe == 'X') {
    executer_axe_X((uint32_t)n, forward);
    if (position_connue) position_x_pas += (forward ? n : -n);
  } else {
    executer_axe_Y((uint32_t)n, forward);
    if (position_connue) position_y_pas += (forward ? n : -n);
  }
  Serial.println("done");
  return true;
}

// GOTO <x> <y>
static bool parser_goto(const String& s) {
  if (!s.startsWith("GOTO ")) return false;
  String args = s.substring(5);
  args.trim();
  int sep = args.indexOf(' ');
  if (sep < 0) {
    Serial.println("GOTO attend 2 arguments : 'GOTO <x> <y>'");
    return true;
  }
  String sx = args.substring(0, sep);
  String sy = args.substring(sep + 1);
  sx.trim();
  sy.trim();
  long x = sx.toInt();
  long y = sy.toInt();
  executer_goto(x, y);
  return true;
}

static void traiter(String s) {
  s.trim();
  s.toUpperCase();
  if (s.length() == 0) return;

  if (s == "HELP")    { afficher_aide();   return; }
  if (s == "STATUS")  { afficher_status(); return; }
  if (s == "HOME")    { executer_home();   return; }
  if (s == "LEVER")   { servo_aller_a(ANGLE_MUR);   return; }
  if (s == "BAISSER") { servo_aller_a(ANGLE_REPOS); return; }

  if (s == "EN ON")  { activer_drivers(true);  Serial.println("drivers ON");  return; }
  if (s == "EN OFF") { activer_drivers(false); Serial.println("drivers OFF"); return; }

  if (s == "LIMITS")       { lire_limits_une_fois(); return; }
  if (s == "LIMITS WATCH") { watch_limits();         return; }

  if (s.startsWith("SERVO ")) {
    long v = s.substring(6).toInt();
    servo_aller_a((int)v);
    return;
  }

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
      appliquer_pwm(M1, pwm);
      appliquer_pwm(M2, pwm);
    }
    Serial.print("DUTY = ");
    Serial.print(duty_pct);
    Serial.println(" %");
    return;
  }

  if (s.startsWith("GOTO ")) {
    if (parser_goto(s)) return;
  }

  if (s.startsWith("M1 ") || s.startsWith("M2 ")) {
    if (parser_moteur(s)) return;
  }

  if (s.startsWith("X ") || s.startsWith("Y ")) {
    if (parser_axe(s)) return;
  }

  Serial.print("Commande inconnue : '");
  Serial.print(s);
  Serial.println("' - tape HELP");
}

// ============================================================================
// Setup / loop
// ============================================================================

static void init_moteur(const Moteur& m) {
  pinMode(m.in1, OUTPUT);
  pinMode(m.in2, OUTPUT);
  pinMode(m.in3, OUTPUT);
  pinMode(m.in4, OUTPUT);
  pinMode(m.ena, OUTPUT);
  pinMode(m.enb, OUTPUT);
  couper_phases(m);
  analogWrite(m.ena, 0);
  analogWrite(m.enb, 0);
}

void setup() {
  // PRIORITE 1 : forcer le servo a 180 deg LE PLUS TOT POSSIBLE dans setup().
  // Le mecanisme casse si le servo demarre dans une autre position. On fait
  // l'init servo AVANT Serial.begin et avant l'init moteurs, pour minimiser
  // la fenetre sans signal PWM apres le power-on (~50 ms au lieu de ~500 ms).
  // L'allocation du timer LEDC doit aussi etre AVANT les analogWrite des
  // moteurs pour eviter un conflit (analogWrite utilise aussi LEDC).
  ESP32PWM::allocateTimer(0);
  servo.setPeriodHertz(50);
  servo.attach(PIN_SERVO, PULSE_MIN_US, PULSE_MAX_US);
  servo.writeMicroseconds(PULSE_MAX_US);  // 2400 us = 180 deg (= ANGLE_REPOS)
  servo_attache = true;
  angle_servo = ANGLE_REPOS;

  Serial.begin(115200);
  delay(500);

  esp_task_wdt_deinit();

  init_moteur(M1);
  init_moteur(M2);

  pinMode(PIN_LIMIT_1, INPUT_PULLUP);
  pinMode(PIN_LIMIT_2, INPUT_PULLUP);

  Serial.println();
  Serial.println("=== Bring-up integration : CoreXY + capteurs + servo ===");
  Serial.println("M1 L298N : IN1=14 IN2=27 IN3=26 IN4=25 ENA=33 ENB=32");
  Serial.println("M2 L298N : IN1=16 IN2=17 IN3=21 IN4=22 ENA=19 ENB=23");
  Serial.println("LIMIT 1 : GPIO 13      LIMIT 2 : GPIO 18");
  Serial.print("SERVO   : GPIO ");
  Serial.print(PIN_SERVO);
  Serial.print(" (force a ");
  Serial.print(ANGLE_REPOS);
  Serial.println(" deg = repos)");
  Serial.println("Drivers moteur DESACTIVES au boot. Tape 'EN ON' pour activer.");
  Serial.print("SPEED ");
  Serial.print(demi_periode_us);
  Serial.print(" us  DUTY ");
  Serial.print(duty_pct);
  Serial.println(" %");
  Serial.println("Position INCONNUE - faire HOME avant GOTO.");
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
