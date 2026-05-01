#ifndef UART_LINK_H
#define UART_LINK_H

#include <Arduino.h>

namespace UartLink {

  // Capacite max d'arguments dans une trame (ex : "h 2 3" pour WALL_REQ)
  constexpr size_t MAX_ARGS_LEN = 32;

  // Trame decodee disponible apres tryGetFrame
  struct Frame {
    char type[16];           // ex "MOVE_REQ", "ACK", "CMD"
    char args[MAX_ARGS_LEN]; // ex "3 4", "MOVE 2 5", vide si pas d'arg
    uint8_t seq;
    int16_t ack;             // -1 si pas d'ack
    int16_t version;         // -1 si pas de version
  };

  // Initialisation : cree le mutex, initialise les compteurs.
  // A appeler une seule fois dans setup() apres Serial.begin().
  void init();

  // Tick periodique (a appeler depuis loop()) :
  // - lit les octets entrants depuis Serial
  // - assemble en lignes
  // - decode les trames protocolaires valides
  // - dedup les CMD repetees (cf. sec 5.3 spec)
  // - place les trames decodees dans la file interne
  void poll();

  // Recupere la prochaine trame protocolaire decodee et validee.
  // Retourne true si une trame est disponible, remplit out.
  bool tryGetFrame(Frame& out);

  // Emet une trame protocolaire complete. Gere framing, seq, CRC, mutex.
  // type : "MOVE_REQ", "DONE", etc.
  // args : "3 4" ou "" si pas d'args
  // ack  : -1 si pas d'ack, sinon valeur (0..255)
  // version : -1 si pas de version, sinon valeur (utilise pour HELLO)
  void sendFrame(const char* type, const char* args, int ack = -1, int version = -1);

  // Emet un log de debug, prefixe [tag], sous mutex.
  // tag : ex "FSM", "BTN", "MOT" - majuscules courts
  // msg : message libre, sans \n
  void log(const char* tag, const char* msg);

  // Variante numerique pour eviter les conversions string a chaque appel
  void logf(const char* tag, const char* fmt, ...);

  // Statistiques debug
  uint32_t getRejectedCount();

  // Helpers pour signaler le resultat d'une CMD recue.
  // Stocke le resultat pour idempotence (renvoyer DONE/ERR sur retransmission).
  void respondCmdDone(uint8_t ackSeq);
  void respondCmdErr(uint8_t ackSeq, const char* code);

  // Emet ERR spontane (entree en ERROR depuis BOOT ou autre etat sans CMD en cours).
  void emitSpontaneousErr(const char* code);

  // A appeler periodiquement (depuis loop()) tant qu'on est en ERROR pour reemettre.
  void tickErrReemission(unsigned long currentMs);

  // Reset l'etat ERR (a la sortie de l'etat ERROR, ex apres CMD_RESET).
  void clearErrState();

  // Constantes protocole
  constexpr uint8_t PROTOCOL_VERSION = 1;
}

#endif
