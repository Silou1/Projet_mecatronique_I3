// Sketch d'integration complete L298N : CoreXY (M1+M2) + 2 fins de course + servo.
// HOME execute automatiquement au boot, puis commandes serie dispos.
//
// Cible : ESP32-WROOM (Freenove DevKit).
//
// === Cablage (identique a bringup_l298n_indep) ===
//
//   Moteur 1 - L298N #1 : IN1=14, IN2=27, IN3=26, IN4=25, ENA=33, ENB=32
//   Moteur 2 - L298N #2 : IN1=16, IN2=17, IN3=21, IN4=22, ENA=19, ENB=23
//   Capteurs : X=13, Y=18 (INPUT_PULLUP)
//   Servo SG90 : Signal=4, V+ alim 5V externe, GND commun
//
//   Convention servo : 180 deg = REPOS (piston bas), 0 deg = MUR LEVE
//   Convention CoreXY (validee machine) :
//     X pur : M1 et M2 sens OPPOSES   (Capteur 1 = fin de course X-)
//     Y pur : M1 et M2 MEME sens      (Capteur 2 = fin de course Y-)
//
//   Calibration validee : 100 pas full-step = 2 cm. 1 cm = 50 pas, 1 mm = 5 pas.
//
// === Sequence boot automatique ===
//
//   1. Servo a 180 deg (toute premiere ligne, securite mecanique)
//   2. Init pins moteurs (drivers OFF)
//   3. Serial.begin
//   4. Activation des 2 drivers (PWM)
//   5. HOME X (M1 et M2 sens opposes vers Capteur X) + recul 20 pas
//   6. HOME Y (M1 et M2 meme sens vers Capteur Y) + recul 20 pas
//   7. Origine (0, 0) etablie
//   8. Boucle commandes serie
//
// === Commandes serie (115200 baud) ===
//
//   HOME              relance le homing
//   GOTO <x> <y>      deplacement absolu en pas depuis origine (bornes 0..700)
//   X F/B <n>         axe X pur, n pas
//   Y F/B <n>         axe Y pur, n pas
//   M1 F/B <n>        moteur 1 seul (debug, INVALIDE position)
//   M2 F/B <n>        moteur 2 seul (debug, INVALIDE position)
//   LEVER             servo a 0 deg
//   BAISSER           servo a 180 deg
//   SERVO <angle>     angle arbitraire 0..180
//   LIMITS            lecture instantanee X et Y
//   LIMITS WATCH      lecture continue (Enter pour sortir)
//   EN ON | EN OFF    active/coupe les 2 drivers
//   SPEED <us>        delai entre pas (500..10000, defaut 2000)
//   DUTY <pct>        PWM en % (10..60, defaut 40)
//   STATUS            etat actuel
//   HELP              cette aide

#include <Arduino.h>
#include <ESP32Servo.h>
#include <WiFi.h>
#include "esp_task_wdt.h"

// === Wi-Fi AP (phase 5) ===
const char* AP_SSID = "Quoridor-ESP32";
const char* AP_PASS = "quoridor2026";
const uint16_t TCP_PORT = 3333;
const unsigned long CLIENT_WATCHDOG_MS = 30000;

WiFiServer wifi_server(TCP_PORT);
WiFiClient wifi_client;
String tampon_wifi = "";
unsigned long last_rx_from_client = 0;

// ============================================================================
// Pins / parametres
// ============================================================================

struct Moteur {
  const char* nom;
  uint8_t in1, in2, in3, in4, ena, enb;
  int phase;
};

static Moteur M1 = { "M1", 14, 27, 26, 25, 33, 32, 0 };
static Moteur M2 = { "M2", 16, 17, 21, 22, 19, 23, 0 };

static constexpr uint8_t PIN_LIMIT_X = 13;
static constexpr uint8_t PIN_LIMIT_Y = 18;
static constexpr uint8_t PIN_SERVO   = 4;

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

static constexpr uint32_t HOME_PAS_MAX    = 4000;
static constexpr uint32_t HOME_RECUL      = 20;
static constexpr uint32_t HOME_LIBERATION = 50;
static constexpr int32_t  GOTO_MAX        = 900;

// ============================================================================
// MATRICES DES POSITIONS DE MURS (a remplir a la main)
// ============================================================================
//
// IL Y A 60 MURS AU TOTAL : 30 horizontaux + 30 verticaux. Chaque mur a une
// position physique (x, y) en pas, mesuree depuis l'origine HOME du chariot.
//
// COMMENT REMPLIR :
//   1. Upload le sketch, le HOME se fait automatiquement au boot.
//   2. Avec X F/B <n> et Y F/B <n>, navigue le piston pile sous un mur non mesure.
//   3. Tape STATUS, note la position (x, y) affichee.
//   4. Edite ce fichier : remplace _NA par {x, y} dans la cellule correspondante.
//   5. Recompile et reuploade. Tape LIST pour voir le statut de remplissage.
//   6. Tape TOUR pour parcourir TOUS les murs deja mesures et verifier leur position.
//
// _NA signifie "pas encore mesure". Le sketch refuse d'aller a un mur _NA via
// MUR H/V, et les saute lors de TOUR.

struct PointMesure {
  int32_t x;
  int32_t y;
};

static constexpr int32_t NA = -1;
#define _NA { NA, NA }

static inline bool est_mesure(const PointMesure& p) {
  return p.x != NA && p.y != NA;
}

// ----------------------------------------------------------------------------
// MURS HORIZONTAUX (rectangles couches, entre 2 cases verticalement adjacentes)
// ----------------------------------------------------------------------------
//
// 6 colonnes (i = 0 a 5) x 5 lignes (j = 0 a 4) = 30 murs.
//
// Vue de DESSUS du plateau (HOME en bas-gauche, donc j = 0 en bas) :
//
//   j=4 (haut)  [ ] [ ] [ ] [ ] [ ] [ ]
//   j=3         [ ] [ ] [ ] [ ] [ ] [ ]
//   j=2         [ ] [ ] [ ] [ ] [ ] [ ]
//   j=1         [ ] [ ] [ ] [ ] [ ] [ ]
//   j=0 (bas)   [ ] [ ] [ ] [ ] [ ] [ ]
//               i=0  i=1  i=2  i=3  i=4  i=5
//
// ATTENTION : dans le code, MURS_H[0] = j=0 (bas du plateau) en PREMIER.
// Acces : MURS_H[j][i].
//
static constexpr int MUR_H_NB_I = 6;
static constexpr int MUR_H_NB_J = 5;
static PointMesure MURS_H[MUR_H_NB_J][MUR_H_NB_I] = {
  //              i=0           i=1   i=2   i=3            i=4   i=5
  /* j=0 (bas)  */ { {102,  35}, _NA, _NA, {406,  35},    _NA, {709,  35} },
  /* j=1        */ { _NA,        _NA, _NA, _NA,            _NA, _NA        },
  /* j=2        */ { {105, 486}, _NA, _NA, {482, 406},    _NA, {709, 485} },
  /* j=3        */ { _NA,        _NA, _NA, _NA,            _NA, _NA        },
  /* j=4 (haut) */ { {109, 777}, _NA, _NA, {409, 777},    _NA, {709, 777} },
};

// ----------------------------------------------------------------------------
// MURS VERTICAUX (rectangles debout, entre 2 cases horizontalement adjacentes)
// ----------------------------------------------------------------------------
//
// 5 colonnes (i = 0 a 4) x 6 lignes (j = 0 a 5) = 30 murs.
//
// Vue de DESSUS du plateau (HOME en bas-gauche, donc j = 0 en bas) :
//
//   j=5 (haut)  [ ] [ ] [ ] [ ] [ ]
//   j=4         [ ] [ ] [ ] [ ] [ ]
//   j=3         [ ] [ ] [ ] [ ] [ ]
//   j=2         [ ] [ ] [ ] [ ] [ ]
//   j=1         [ ] [ ] [ ] [ ] [ ]
//   j=0 (bas)   [ ] [ ] [ ] [ ] [ ]
//               i=0  i=1  i=2  i=3  i=4
//
// Acces : MURS_V[j][i].
//
static constexpr int MUR_V_NB_I = 5;
static constexpr int MUR_V_NB_J = 6;
static PointMesure MURS_V[MUR_V_NB_J][MUR_V_NB_I] = {
  //              i=0          i=1  i=2          i=3  i=4
  /* j=0 (bas)  */ { { 32, 110}, _NA, {330, 107}, _NA, {779, 105} },
  /* j=1        */ { _NA,        _NA, _NA,         _NA, _NA        },
  /* j=2        */ { _NA,        _NA, _NA,         _NA, _NA        },
  /* j=3        */ { { 33, 408}, _NA, {407, 479}, _NA, {782, 400} },
  /* j=4        */ { _NA,        _NA, _NA,         _NA, _NA        },
  /* j=5 (haut) */ { { 34, 707}, _NA, {339, 711}, _NA, {784, 705} },
};

static constexpr int MUR_NB_H = MUR_H_NB_I * MUR_H_NB_J;  // 30
static constexpr int MUR_NB_V = MUR_V_NB_I * MUR_V_NB_J;  // 30
static constexpr int MUR_NB_TOTAL = MUR_NB_H + MUR_NB_V;  // 60

static const uint8_t SEQUENCE[4][4] = {
  {1, 0, 1, 0}, {0, 1, 1, 0}, {0, 1, 0, 1}, {1, 0, 0, 1}
};

// ============================================================================
// Etat global
// ============================================================================

static uint32_t demi_periode_us = SPEED_DEFAUT_US;
static uint8_t  duty_pct        = DUTY_DEFAUT_PCT;
static bool     drivers_actifs  = false;
static bool     position_connue = false;
static int32_t  pos_x = 0, pos_y = 0;
static String   tampon_serie;
static Servo    servo;

// Tournee automatique : -1 = inactif, 0..N-1 = index lineaire (H d'abord, puis V).
static int tour_index = -1;

// ============================================================================
// Moteurs : phases, drivers, pulses
// ============================================================================

static uint8_t duty_to_pwm(uint8_t pct) {
  uint32_t v = (uint32_t)pct * 255 / 100;
  return (uint8_t)(v > 255 ? 255 : v);
}

static void couper_phases(Moteur& m) {
  digitalWrite(m.in1, LOW); digitalWrite(m.in2, LOW);
  digitalWrite(m.in3, LOW); digitalWrite(m.in4, LOW);
}

static void appliquer_phase(Moteur& m, int idx) {
  digitalWrite(m.in1, SEQUENCE[idx][0] ? HIGH : LOW);
  digitalWrite(m.in2, SEQUENCE[idx][1] ? HIGH : LOW);
  digitalWrite(m.in3, SEQUENCE[idx][2] ? HIGH : LOW);
  digitalWrite(m.in4, SEQUENCE[idx][3] ? HIGH : LOW);
}

static void activer_drivers(bool actif) {
  drivers_actifs = actif;
  uint8_t pwm = actif ? duty_to_pwm(duty_pct) : 0;
  analogWrite(M1.ena, pwm); analogWrite(M1.enb, pwm);
  analogWrite(M2.ena, pwm); analogWrite(M2.enb, pwm);
  if (actif) {
    appliquer_phase(M1, M1.phase);
    appliquer_phase(M2, M2.phase);
  } else {
    couper_phases(M1); couper_phases(M2);
  }
}

static void appliquer_duty_courant() {
  if (!drivers_actifs) return;
  uint8_t pwm = duty_to_pwm(duty_pct);
  analogWrite(M1.ena, pwm); analogWrite(M1.enb, pwm);
  analogWrite(M2.ena, pwm); analogWrite(M2.enb, pwm);
}

// Avance les phases de M1 et/ou M2 simultanement pour nb_pas, avec sens donnes.
static void pulse_2_moteurs(uint32_t nb_pas,
                            bool m1_actif, bool m1_fwd,
                            bool m2_actif, bool m2_fwd) {
  for (uint32_t i = 0; i < nb_pas; ++i) {
    if (m1_actif) {
      M1.phase = (M1.phase + (m1_fwd ? 1 : 3)) & 3;
      appliquer_phase(M1, M1.phase);
    }
    if (m2_actif) {
      M2.phase = (M2.phase + (m2_fwd ? 1 : 3)) & 3;
      appliquer_phase(M2, M2.phase);
    }
    delayMicroseconds(demi_periode_us);
    if ((i & 0x3F) == 0) yield();
  }
}

// ============================================================================
// Mouvements CoreXY
// ============================================================================

// X pur : M1 et M2 sens opposes.
static void deplacer_x(uint32_t pas, bool fwd) {
  pulse_2_moteurs(pas, true, fwd, true, !fwd);
  pos_x += fwd ? (int32_t)pas : -(int32_t)pas;
}

// Y pur : M1 et M2 meme sens.
static void deplacer_y(uint32_t pas, bool fwd) {
  pulse_2_moteurs(pas, true, fwd, true, fwd);
  pos_y += fwd ? (int32_t)pas : -(int32_t)pas;
}

// M1 seul (debug, INVALIDE position cartesienne).
static void deplacer_m1(uint32_t pas, bool fwd) {
  pulse_2_moteurs(pas, true, fwd, false, false);
  position_connue = false;
}

static void deplacer_m2(uint32_t pas, bool fwd) {
  pulse_2_moteurs(pas, false, false, true, fwd);
  position_connue = false;
}

// ============================================================================
// HOME
// ============================================================================

static bool homing_axe(const char* nom, uint8_t pin_capteur,
                       bool m1_back, bool m2_back) {
  Serial.print("HOME "); Serial.print(nom); Serial.println(" ...");

  // Liberer si deja au contact.
  if (digitalRead(pin_capteur) == LOW) {
    Serial.print("  capteur deja LOW -> liberation "); Serial.print(HOME_LIBERATION);
    Serial.println(" pas");
    pulse_2_moteurs(HOME_LIBERATION, true, !m1_back, true, !m2_back);
  }

  // Approche, 1 pas a la fois.
  bool ok = false;
  for (uint32_t i = 0; i < HOME_PAS_MAX; ++i) {
    if (digitalRead(pin_capteur) == LOW) { ok = true; break; }
    pulse_2_moteurs(1, true, m1_back, true, m2_back);
    if ((i & 0x3F) == 0) yield();
  }

  if (!ok) {
    Serial.print("  ECHEC : capteur "); Serial.print(nom);
    Serial.print(" jamais atteint en "); Serial.print(HOME_PAS_MAX);
    Serial.println(" pas");
    return false;
  }

  Serial.print("  capteur "); Serial.print(nom); Serial.println(" touche -> recul");
  pulse_2_moteurs(HOME_RECUL, true, !m1_back, true, !m2_back);
  return true;
}

static bool homing_complet() {
  Serial.println();
  Serial.println("=== HOME ===");
  if (!drivers_actifs) activer_drivers(true);

  bool ok_x = homing_axe("X", PIN_LIMIT_Y, /*m1_back*/ false, /*m2_back*/ true);
  if (!ok_x) return false;
  delay(150);
  bool ok_y = homing_axe("Y", PIN_LIMIT_X, /*m1_back*/ false, /*m2_back*/ false);
  if (!ok_y) return false;

  pos_x = 0; pos_y = 0;
  position_connue = true;
  Serial.println("HOME OK. Origine (0, 0) etablie.");
  return true;
}

// ============================================================================
// GOTO
// ============================================================================

// Forward declaration (utilisee par aller_au_mur).
static void goto_xy(int32_t x_cible, int32_t y_cible);

// ============================================================================
// Murs : calcul de position par interpolation bilineaire des 4 coins mesures
// ============================================================================

// Lookup direct dans la matrice MURS_H/V. Retourne false si hors bornes ou pas mesure.
static bool position_mur_h(int i, int j, int32_t& x, int32_t& y) {
  if (i < 0 || i >= MUR_H_NB_I || j < 0 || j >= MUR_H_NB_J) return false;
  const PointMesure& p = MURS_H[j][i];
  if (!est_mesure(p)) return false;
  x = p.x; y = p.y;
  return true;
}

static bool position_mur_v(int i, int j, int32_t& x, int32_t& y) {
  if (i < 0 || i >= MUR_V_NB_I || j < 0 || j >= MUR_V_NB_J) return false;
  const PointMesure& p = MURS_V[j][i];
  if (!est_mesure(p)) return false;
  x = p.x; y = p.y;
  return true;
}

static void aller_au_mur_h(int i, int j) {
  if (i < 0 || i >= MUR_H_NB_I || j < 0 || j >= MUR_H_NB_J) {
    Serial.print("MUR H refuse : (i, j) hors [0..");
    Serial.print(MUR_H_NB_I - 1); Serial.print("] x [0..");
    Serial.print(MUR_H_NB_J - 1); Serial.println("]");
    return;
  }
  int32_t x, y;
  if (!position_mur_h(i, j, x, y)) {
    Serial.print("MUR H ("); Serial.print(i); Serial.print(", "); Serial.print(j);
    Serial.println(") PAS ENCORE MESURE. Remplis la matrice MURS_H dans le code.");
    return;
  }
  Serial.print("MUR H ("); Serial.print(i); Serial.print(", "); Serial.print(j);
  Serial.print(") -> ("); Serial.print(x); Serial.print(", "); Serial.print(y);
  Serial.println(")");
  goto_xy(x, y);
}

static void aller_au_mur_v(int i, int j) {
  if (i < 0 || i >= MUR_V_NB_I || j < 0 || j >= MUR_V_NB_J) {
    Serial.print("MUR V refuse : (i, j) hors [0..");
    Serial.print(MUR_V_NB_I - 1); Serial.print("] x [0..");
    Serial.print(MUR_V_NB_J - 1); Serial.println("]");
    return;
  }
  int32_t x, y;
  if (!position_mur_v(i, j, x, y)) {
    Serial.print("MUR V ("); Serial.print(i); Serial.print(", "); Serial.print(j);
    Serial.println(") PAS ENCORE MESURE. Remplis la matrice MURS_V dans le code.");
    return;
  }
  Serial.print("MUR V ("); Serial.print(i); Serial.print(", "); Serial.print(j);
  Serial.print(") -> ("); Serial.print(x); Serial.print(", "); Serial.print(y);
  Serial.println(")");
  goto_xy(x, y);
}

// Convertit un index lineaire 0..59 en (i, j) dans MURS_H ou MURS_V.
// Retourne true si le point a cet index est mesure, false sinon.
// type_h_out : true = H, false = V.
static bool decode_index_tour(int idx, bool& type_h_out,
                              int& i_out, int& j_out,
                              int32_t& x_out, int32_t& y_out) {
  if (idx < MUR_NB_H) {
    int i = idx % MUR_H_NB_I;
    int j = idx / MUR_H_NB_I;
    const PointMesure& p = MURS_H[j][i];
    type_h_out = true; i_out = i; j_out = j;
    if (!est_mesure(p)) return false;
    x_out = p.x; y_out = p.y;
    return true;
  } else {
    int k = idx - MUR_NB_H;
    int i = k % MUR_V_NB_I;
    int j = k / MUR_V_NB_I;
    const PointMesure& p = MURS_V[j][i];
    type_h_out = false; i_out = i; j_out = j;
    if (!est_mesure(p)) return false;
    x_out = p.x; y_out = p.y;
    return true;
  }
}

// Cherche le prochain index >= depart dont le mur est mesure. Renvoie -1 si aucun.
static int prochain_mur_mesure(int depart) {
  for (int idx = depart; idx < MUR_NB_TOTAL; ++idx) {
    bool th; int i, j; int32_t x, y;
    if (decode_index_tour(idx, th, i, j, x, y)) return idx;
  }
  return -1;
}

static void aller_au_point_tour(int idx) {
  bool th; int i, j; int32_t x, y;
  if (!decode_index_tour(idx, th, i, j, x, y)) return;
  Serial.print(">> "); Serial.print(th ? "MUR H (" : "MUR V (");
  Serial.print(i); Serial.print(", "); Serial.print(j);
  Serial.print(")  -> ("); Serial.print(x); Serial.print(", ");
  Serial.print(y); Serial.println(")");
  goto_xy(x, y);
}

// Demarre la tournee : parcourt tous les murs MESURES dans MURS_H puis MURS_V.
static void tour_demarrer() {
  if (!position_connue) {
    Serial.println("TOUR refuse : HOME requis.");
    return;
  }
  int prochain = prochain_mur_mesure(0);
  if (prochain < 0) {
    Serial.println("TOUR refuse : aucun mur mesure dans MURS_H ou MURS_V.");
    return;
  }
  tour_index = prochain;
  Serial.println("=== TOUR : parcours des murs mesures. NEXT pour avancer, STOP pour arreter ===");
  aller_au_point_tour(tour_index);
  Serial.println(">> Verifie le centrage. Tape NEXT pour le suivant.");
}

static void tour_suivant() {
  if (tour_index < 0) {
    Serial.println("NEXT ignore : aucune tournee active. Tape TOUR pour demarrer.");
    return;
  }
  int prochain = prochain_mur_mesure(tour_index + 1);
  if (prochain < 0) {
    Serial.println("=== TOUR termine : tous les murs mesures ont ete visites ===");
    tour_index = -1;
    return;
  }
  tour_index = prochain;
  aller_au_point_tour(tour_index);
  Serial.println(">> Verifie le centrage. Tape NEXT pour le suivant.");
}

static void tour_stop() {
  if (tour_index < 0) {
    Serial.println("STOP ignore : aucune tournee active.");
    return;
  }
  Serial.println("TOUR interrompu.");
  tour_index = -1;
}

// LIST : affiche le statut de remplissage des matrices MURS_H et MURS_V.
static void afficher_liste() {
  int nb_h = 0, nb_v = 0;
  Serial.println("=== Statut matrices ===");
  Serial.println("MURS_H (30 cellules) :");
  for (int j = MUR_H_NB_J - 1; j >= 0; --j) {  // affiche j=4 en haut, j=0 en bas
    Serial.print("  j="); Serial.print(j); Serial.print(" : ");
    for (int i = 0; i < MUR_H_NB_I; ++i) {
      if (est_mesure(MURS_H[j][i])) { Serial.print("[X] "); nb_h++; }
      else                          { Serial.print("[.] "); }
    }
    Serial.println();
  }
  Serial.println("MURS_V (30 cellules) :");
  for (int j = MUR_V_NB_J - 1; j >= 0; --j) {
    Serial.print("  j="); Serial.print(j); Serial.print(" : ");
    for (int i = 0; i < MUR_V_NB_I; ++i) {
      if (est_mesure(MURS_V[j][i])) { Serial.print("[X] "); nb_v++; }
      else                          { Serial.print("[.] "); }
    }
    Serial.println();
  }
  Serial.print("Total : "); Serial.print(nb_h + nb_v); Serial.print("/");
  Serial.print(MUR_NB_TOTAL); Serial.print("  (H : "); Serial.print(nb_h);
  Serial.print("/30, V : "); Serial.print(nb_v); Serial.println("/30)");
}

static void goto_xy(int32_t x_cible, int32_t y_cible) {
  if (!position_connue) {
    Serial.println("GOTO refuse : HOME requis.");
    return;
  }
  if (x_cible < 0 || x_cible > GOTO_MAX || y_cible < 0 || y_cible > GOTO_MAX) {
    Serial.print("GOTO refuse : hors bornes [0.."); Serial.print(GOTO_MAX); Serial.println("]");
    return;
  }
  int32_t dx = x_cible - pos_x;
  int32_t dy = y_cible - pos_y;
  Serial.print("GOTO ("); Serial.print(x_cible); Serial.print(", "); Serial.print(y_cible);
  Serial.print(")  dx="); Serial.print(dx); Serial.print(" dy="); Serial.println(dy);

  if (dx != 0) deplacer_x((uint32_t)abs(dx), dx > 0);
  if (dy != 0) deplacer_y((uint32_t)abs(dy), dy > 0);
  Serial.println("done");
}

// ============================================================================
// DEMO : N murs aleatoires parmi les mesures, levee + redescente a chaque arret
// ============================================================================

static constexpr uint32_t DEMO_DELAI_LEVE_MS    = 400;
static constexpr uint32_t DEMO_DELAI_BAISSE_MS  = 400;

static void demo_lever_murs(int n) {
  if (!position_connue) {
    Serial.println("DEMO refuse : HOME requis.");
    return;
  }

  int liste[MUR_NB_TOTAL];
  int nb = 0;
  for (int idx = 0; idx < MUR_NB_TOTAL; ++idx) {
    bool th; int i, j; int32_t x, y;
    if (decode_index_tour(idx, th, i, j, x, y)) liste[nb++] = idx;
  }
  if (nb == 0) {
    Serial.println("DEMO refuse : aucun mur mesure.");
    return;
  }

  // Fisher-Yates avec esp_random (RNG hardware ESP32).
  for (int i = nb - 1; i > 0; --i) {
    int k = (int)(esp_random() % (uint32_t)(i + 1));
    int tmp = liste[i]; liste[i] = liste[k]; liste[k] = tmp;
  }

  int total = (n < nb) ? n : nb;
  Serial.print("=== DEMO : "); Serial.print(total);
  Serial.print(" murs aleatoires parmi "); Serial.print(nb); Serial.println(" mesures ===");

  for (int k = 0; k < total; ++k) {
    bool th; int i, j; int32_t x, y;
    decode_index_tour(liste[k], th, i, j, x, y);

    Serial.print("DEMO "); Serial.print(k + 1); Serial.print("/"); Serial.print(total);
    Serial.print(" : "); Serial.print(th ? "MUR H (" : "MUR V (");
    Serial.print(i); Serial.print(", "); Serial.print(j);
    Serial.print(")  -> ("); Serial.print(x); Serial.print(", "); Serial.print(y);
    Serial.println(")");

    goto_xy(x, y);
    servo.write(SERVO_LEVER_DEG);
    delay(DEMO_DELAI_LEVE_MS);
    servo.write(SERVO_REPOS_DEG);
    delay(DEMO_DELAI_BAISSE_MS);
  }
  Serial.println("=== DEMO terminee ===");
}

// ============================================================================
// Levee de mur Quoridor (helper appele par la commande WALL)
// ============================================================================
//
// Convention Quoridor :
//   Mur H (h, row, col) : separe rangs row et row+1, occupe cols col et col+1
//   Mur V (v, row, col) : separe cols col et col+1, occupe rangs row et row+1
//   Domaine : row, col dans [0..4]
//
// Mapping vers la matrice firmware :
//   Mur H -> MURS_H[4-row][col] et MURS_H[4-row][col+1]
//   Mur V -> MURS_V[5-row][col] et MURS_V[4-row][col]
//
// Pour chaque case mesuree : GOTO + LEVER + BAISSER. Les cases _NA sont sautees.

static constexpr uint32_t WALL_DELAI_LEVE_MS   = 400;
static constexpr uint32_t WALL_DELAI_BAISSE_MS = 400;

static void wall_lever_case(int32_t x, int32_t y) {
  goto_xy(x, y);
  servo.write(SERVO_LEVER_DEG);
  delay(WALL_DELAI_LEVE_MS);
  servo.write(SERVO_REPOS_DEG);
  delay(WALL_DELAI_BAISSE_MS);
}

static int wall_lever(char orientation, int row, int col) {
  int raised = 0;
  int32_t x, y;

  if (orientation == 'H') {
    int j = 4 - row;
    if (position_mur_h(col, j, x, y))     { wall_lever_case(x, y); raised++; }
    if (position_mur_h(col + 1, j, x, y)) { wall_lever_case(x, y); raised++; }
  } else {  // 'V'
    int i = col;
    if (position_mur_v(i, 5 - row, x, y)) { wall_lever_case(x, y); raised++; }
    if (position_mur_v(i, 4 - row, x, y)) { wall_lever_case(x, y); raised++; }
  }
  return raised;
}

// ============================================================================
// Affichage
// ============================================================================

static void afficher_aide() {
  Serial.println("Commandes :");
  Serial.println("  HOME              relance homing");
  Serial.println("  GOTO <x> <y>      deplacement absolu (0..700 sur chaque axe)");
  Serial.println("  X F/B <n>         axe X pur");
  Serial.println("  Y F/B <n>         axe Y pur");
  Serial.println("  M1 F/B <n>        moteur 1 seul (debug, INVALIDE position)");
  Serial.println("  M2 F/B <n>        moteur 2 seul (debug, INVALIDE position)");
  Serial.println("  LEVER | BAISSER   servo 0 deg / 180 deg");
  Serial.println("  SERVO <angle>     angle 0..180");
  Serial.println("  DEMO [N]          N murs aleatoires parmi mesures, leve+baisse (defaut 10)");
  Serial.println("  LIMITS            lecture X et Y");
  Serial.println("  LIMITS WATCH      lecture continue (Enter pour sortir)");
  Serial.println("  EN ON | EN OFF    active/coupe les 2 drivers");
  Serial.println("  SPEED <us>        delai entre pas (500..10000)");
  Serial.println("  DUTY <pct>        PWM en % (10..60)");
  Serial.println("  STATUS            etat actuel");
  Serial.println("  PING              repond PONG (handshake webapp)");
  Serial.println("  WALL <H|V> <r> <c>  lever mur Quoridor (r,c dans [0..4])");
  Serial.println("  HELP              cette aide");
}

static void afficher_status() {
  Serial.print("  drivers  : "); Serial.println(drivers_actifs ? "ON" : "OFF");
  Serial.print("  position : ");
  if (position_connue) {
    Serial.print("("); Serial.print(pos_x); Serial.print(", "); Serial.print(pos_y);
    Serial.println(") pas");
  } else {
    Serial.println("INCONNUE (HOME requis)");
  }
  Serial.print("  SPEED    : "); Serial.print(demi_periode_us); Serial.println(" us");
  Serial.print("  DUTY     : "); Serial.print(duty_pct); Serial.println(" %");
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
// Parseur
// ============================================================================

static long parse_n_apres(const String& s, size_t off) {
  long n = s.substring(off).toInt();
  if (n <= 0 || n > (long)PAS_MAX) {
    Serial.print("N hors limite [1.."); Serial.print(PAS_MAX); Serial.println("]");
    return -1;
  }
  return n;
}

static void traiter(String s, Stream* reply) {
  s.trim();
  s.toUpperCase();
  if (s.length() == 0) return;

  if (s == "HELP")        { afficher_aide();  return; }
  if (s == "PING")        { reply->println("PONG"); return; }
  if (s == "STATUS")      { afficher_status(); reply->println("OK"); return; }
  if (s == "LIMITS")      {
    reply->print("X="); reply->print(digitalRead(PIN_LIMIT_X) == LOW ? "LOW " : "HIGH");
    reply->print("  Y="); reply->println(digitalRead(PIN_LIMIT_Y) == LOW ? "LOW " : "HIGH");
    return;
  }
  if (s == "LIMITS WATCH") { limits_watch(); return; }
  if (s == "EN ON")  { activer_drivers(true);  reply->println("drivers ON");  return; }
  if (s == "EN OFF") { activer_drivers(false); reply->println("drivers OFF"); return; }
  if (s == "HOME")   {
    bool ok = homing_complet();
    reply->println(ok ? "HOME OK" : "HOME ERR");
    return;
  }
  if (s == "LEVER")  { servo.write(SERVO_LEVER_DEG); reply->println("servo 0 deg"); return; }
  if (s == "BAISSER"){ servo.write(SERVO_REPOS_DEG); reply->println("servo 180 deg"); return; }
  if (s == "TOUR")   { tour_demarrer(); reply->println("OK"); return; }
  if (s == "NEXT" || s == "N") { tour_suivant(); reply->println("OK"); return; }
  if (s == "STOP")   { tour_stop(); reply->println("OK"); return; }
  if (s == "LIST")   { afficher_liste(); reply->println("OK"); return; }
  if (s == "DEMO")   { demo_lever_murs(10); reply->println("OK"); return; }
  if (s.startsWith("DEMO ")) {
    long v = s.substring(5).toInt();
    if (v <= 0) { reply->println("ERR DEMO N : N doit etre > 0"); return; }
    demo_lever_murs((int)v);
    reply->println("OK");
    return;
  }

  if (s.startsWith("WALL ")) {
    String r = s.substring(5); r.trim();
    if (r.length() < 5 || (r.charAt(0) != 'H' && r.charAt(0) != 'V')) {
      reply->println("WALL ERR orientation : H ou V attendu");
      return;
    }
    char orient = r.charAt(0);
    String reste = r.substring(2); reste.trim();
    int sp = reste.indexOf(' ');
    if (sp < 0) {
      reply->println("WALL ERR syntaxe : WALL <H|V> <row> <col>");
      return;
    }
    int row = reste.substring(0, sp).toInt();
    int col = reste.substring(sp + 1).toInt();
    if (row < 0 || row > 4 || col < 0 || col > 4) {
      reply->print("WALL ERR borne : row="); reply->print(row);
      reply->print(" col="); reply->print(col);
      reply->println(" hors [0..4]");
      return;
    }
    int raised = wall_lever(orient, row, col);
    reply->print("WALL OK "); reply->print(orient);
    reply->print(" "); reply->print(row); reply->print(" "); reply->print(col);
    reply->print(" raised="); reply->println(raised);
    return;
  }

  if (s.startsWith("MUR ")) {
    String r = s.substring(4); r.trim();
    if (r.length() < 3 || (r.charAt(0) != 'H' && r.charAt(0) != 'V')) {
      reply->println("ERR Syntaxe : MUR H <i> <j>  ou  MUR V <i> <j>");
      return;
    }
    char type = r.charAt(0);
    String reste = r.substring(2); reste.trim();
    int sp = reste.indexOf(' ');
    if (sp < 0) {
      reply->println("ERR Syntaxe : MUR H <i> <j>  ou  MUR V <i> <j>");
      return;
    }
    int i = reste.substring(0, sp).toInt();
    int j = reste.substring(sp + 1).toInt();
    if (type == 'H') aller_au_mur_h(i, j);
    else             aller_au_mur_v(i, j);
    reply->println("OK");
    return;
  }

  if (s.startsWith("SERVO ")) {
    long v = s.substring(6).toInt();
    if (v < 0 || v > 180) { reply->println("ERR angle hors [0..180]"); return; }
    servo.write((int)v);
    reply->print("servo "); reply->print(v); reply->println(" deg");
    return;
  }
  if (s.startsWith("SPEED ")) {
    long v = s.substring(6).toInt();
    if (v < (long)SPEED_MIN_US || v > (long)SPEED_MAX_US) {
      reply->println("ERR SPEED hors limite"); return;
    }
    demi_periode_us = (uint32_t)v;
    reply->print("SPEED = "); reply->print(demi_periode_us); reply->println(" us");
    return;
  }
  if (s.startsWith("DUTY ")) {
    long v = s.substring(5).toInt();
    if (v < (long)DUTY_MIN_PCT || v > (long)DUTY_MAX_PCT) {
      reply->println("ERR DUTY hors limite"); return;
    }
    duty_pct = (uint8_t)v;
    appliquer_duty_courant();
    reply->print("DUTY = "); reply->print(duty_pct); reply->println(" %");
    return;
  }
  if (s.startsWith("GOTO ")) {
    String r = s.substring(5); r.trim();
    int sp = r.indexOf(' ');
    if (sp < 0) { reply->println("ERR Syntaxe : GOTO <x> <y>"); return; }
    goto_xy(r.substring(0, sp).toInt(), r.substring(sp + 1).toInt());
    reply->println("OK");
    return;
  }
  if (!drivers_actifs && (s.startsWith("X ") || s.startsWith("Y ") ||
                          s.startsWith("M1 ") || s.startsWith("M2 "))) {
    reply->println("ERR Drivers OFF. Tape 'EN ON' d'abord.");
    return;
  }
  if (s.startsWith("X F ") || s.startsWith("X B ")) {
    long n = parse_n_apres(s, 4); if (n < 0) return;
    deplacer_x((uint32_t)n, s.charAt(2) == 'F');
    reply->println("done"); return;
  }
  if (s.startsWith("Y F ") || s.startsWith("Y B ")) {
    long n = parse_n_apres(s, 4); if (n < 0) return;
    deplacer_y((uint32_t)n, s.charAt(2) == 'F');
    reply->println("done"); return;
  }
  if (s.startsWith("M1 F ") || s.startsWith("M1 B ")) {
    long n = parse_n_apres(s, 5); if (n < 0) return;
    deplacer_m1((uint32_t)n, s.charAt(3) == 'F');
    reply->println("done (position INVALIDEE)"); return;
  }
  if (s.startsWith("M2 F ") || s.startsWith("M2 B ")) {
    long n = parse_n_apres(s, 5); if (n < 0) return;
    deplacer_m2((uint32_t)n, s.charAt(3) == 'F');
    reply->println("done (position INVALIDEE)"); return;
  }

  reply->print("ERR Commande inconnue : '"); reply->print(s); reply->println("' - tape HELP");
}

// ============================================================================
// Setup / Loop
// ============================================================================

void setup() {
  // 1. Servo a 180 deg en TOUT PREMIER (securite mecanique).
  servo.attach(PIN_SERVO, PULSE_MIN_US, PULSE_MAX_US);
  servo.write(SERVO_REPOS_DEG);

  // 2. Init pins moteurs + drivers OFF.
  for (Moteur* m : { &M1, &M2 }) {
    pinMode(m->in1, OUTPUT); pinMode(m->in2, OUTPUT);
    pinMode(m->in3, OUTPUT); pinMode(m->in4, OUTPUT);
    pinMode(m->ena, OUTPUT); pinMode(m->enb, OUTPUT);
    couper_phases(*m);
    analogWrite(m->ena, 0); analogWrite(m->enb, 0);
  }
  pinMode(PIN_LIMIT_X, INPUT_PULLUP);
  pinMode(PIN_LIMIT_Y, INPUT_PULLUP);

  esp_task_wdt_deinit();

  Serial.begin(115200);
  delay(500);
  Serial.println();
  Serial.println("=== Integration L298N : CoreXY + capteurs + servo ===");
  Serial.println("M1: IN=14/27/26/25  ENA=33 ENB=32");
  Serial.println("M2: IN=16/17/21/22  ENA=19 ENB=23");
  Serial.println("Capteurs: X=13 Y=18    Servo: 4");
  Serial.print("DUTY="); Serial.print(duty_pct); Serial.print("%  SPEED=");
  Serial.print(demi_periode_us); Serial.println("us");
  Serial.println();

  // 3. HOME automatique.
  if (!homing_complet()) {
    Serial.println();
    Serial.println("!! HOME echoue. Drivers coupes par securite.");
    Serial.println("!! Verifier capteurs + cablage + DUTY, puis taper HOME.");
    activer_drivers(false);
  }

  Serial.println();
  afficher_aide();
  Serial.println();

  // 4. Demarrage Wi-Fi AP (phase 5)
  WiFi.mode(WIFI_AP);
  bool ap_ok = WiFi.softAP(AP_SSID, AP_PASS);
  if (ap_ok) {
    Serial.print("[WiFi] AP demarre : ");
    Serial.print(AP_SSID);
    Serial.print(" / IP : ");
    Serial.println(WiFi.softAPIP());
  } else {
    Serial.println("[WiFi] AP softAP() echoue");
  }
  wifi_server.begin();
  Serial.print("[WiFi] Serveur TCP demarre sur port ");
  Serial.println(TCP_PORT);
  Serial.println();
}

void loop() {
  // 1. Accepter une nouvelle connexion TCP (politique "dernier client gagne")
  if (wifi_server.hasClient()) {
    if (wifi_client && wifi_client.connected()) {
      wifi_client.stop();
    }
    wifi_client = wifi_server.available();
    tampon_wifi = "";
    last_rx_from_client = millis();
    Serial.print("[WiFi] Nouveau client : ");
    Serial.println(wifi_client.remoteIP());
  }

  // 2. Lecture USB-serie (canal existant, inchange)
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      traiter(tampon_serie, &Serial);
      tampon_serie = "";
    } else {
      tampon_serie += c;
      if (tampon_serie.length() > 64) {
        tampon_serie = "";
        Serial.println("Ligne trop longue, ignoree.");
      }
    }
  }

  // 3. Lecture client TCP (nouveau)
  if (wifi_client && wifi_client.connected()) {
    while (wifi_client.available()) {
      char c = (char)wifi_client.read();
      if (c == '\r') continue;
      if (c == '\n') {
        traiter(tampon_wifi, &wifi_client);
        tampon_wifi = "";
        last_rx_from_client = millis();
      } else {
        tampon_wifi += c;
        if (tampon_wifi.length() > 64) {
          tampon_wifi = "";
          wifi_client.println("Ligne trop longue, ignoree.");
        }
      }
    }
  }

  // 4. Watchdog : drop client TCP si 30s sans trafic
  if (wifi_client && wifi_client.connected()
      && (millis() - last_rx_from_client > CLIENT_WATCHDOG_MS)) {
    Serial.println("[WiFi] Watchdog : client silencieux, drop");
    wifi_client.stop();
  }
}
