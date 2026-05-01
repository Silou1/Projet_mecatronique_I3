#include "UartLink.h"
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include <stdarg.h>
#include <string.h>

namespace {
  // Mutex pour serializer les acces a Serial entre Core 0 et Core 1
  SemaphoreHandle_t _serialMutex = nullptr;

  // Compteur de seq sortant
  volatile uint8_t _txSeq = 0;

  // Buffer de reception
  String _rxBuffer;

  // File de trames decodees (taille fixe pour eviter allocation dynamique)
  static constexpr size_t FRAME_QUEUE_SIZE = 4;
  UartLink::Frame _frameQueue[FRAME_QUEUE_SIZE];
  size_t _frameQueueHead = 0;
  size_t _frameQueueCount = 0;

  // Idempotence CMD (cf. sec 5.3 spec)
  int16_t _lastCmdSeqProcessed = -1;
  enum class CmdResult { NONE, DONE, ERR };
  CmdResult _lastCmdResult = CmdResult::NONE;
  char _lastCmdErrCode[16] = "";

  // Etat ERR (reemission periodique)
  bool _errActive = false;
  char _errActiveCode[16] = "";
  unsigned long _lastErrEmitMs = 0;
  static constexpr unsigned long ERR_REEMIT_PERIOD_MS = 1000;

  // Stats
  uint32_t _rejectedCount = 0;

  // Legacy Plan 1 (a supprimer apres refactor callers)
  String _legacyPendingLine;
  bool _legacyHasPending = false;

  // CRC-16 CCITT-FALSE (poly 0x1021, init 0xFFFF, sans reflexion)
  uint16_t crc16(const uint8_t* data, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; i++) {
      crc ^= ((uint16_t)data[i]) << 8;
      for (int j = 0; j < 8; j++) {
        if (crc & 0x8000) crc = (crc << 1) ^ 0x1021;
        else crc <<= 1;
      }
    }
    return crc;
  }

  // Helper : prend le mutex, ecrit, relache
  void writeUnderMutex(const char* data, size_t len) {
    if (_serialMutex && xSemaphoreTake(_serialMutex, pdMS_TO_TICKS(100))) {
      Serial.write((const uint8_t*)data, len);
      xSemaphoreGive(_serialMutex);
    } else {
      Serial.write((const uint8_t*)data, len);
    }
  }

  uint8_t nextSeq() {
    uint8_t s = _txSeq;
    _txSeq = (uint8_t)((_txSeq + 1) & 0xFF);
    return s;
  }
}

void UartLink::init() {
  _serialMutex = xSemaphoreCreateMutex();
  _rxBuffer.reserve(96);
  _txSeq = 0;
  _lastCmdSeqProcessed = -1;
  _lastCmdResult = CmdResult::NONE;
  _frameQueueHead = 0;
  _frameQueueCount = 0;
  _rejectedCount = 0;
  _errActive = false;
  _legacyHasPending = false;
  log("UART", "init");
}

void UartLink::sendFrame(const char* type, const char* args, int ack, int version) {
  // Construire la zone CRC dans un buffer local
  char body[96];
  size_t pos = 0;

  // type
  size_t typeLen = strlen(type);
  if (typeLen + 1 >= sizeof(body)) return;
  memcpy(body + pos, type, typeLen);
  pos += typeLen;

  // args (precedes d'un espace si non vides)
  if (args && args[0] != '\0') {
    size_t argsLen = strlen(args);
    if (pos + 1 + argsLen >= sizeof(body)) return;
    body[pos++] = ' ';
    memcpy(body + pos, args, argsLen);
    pos += argsLen;
  }

  // |seq=N
  uint8_t seq = nextSeq();
  pos += snprintf(body + pos, sizeof(body) - pos, "|seq=%u", seq);

  // |ack=M (optionnel)
  if (ack >= 0) {
    pos += snprintf(body + pos, sizeof(body) - pos, "|ack=%d", ack);
  }

  // |v=K (optionnel)
  if (version >= 0) {
    pos += snprintf(body + pos, sizeof(body) - pos, "|v=%d", version);
  }

  // Calcul CRC
  uint16_t crc = crc16((const uint8_t*)body, pos);

  // Trame complete : <body|crc=XXXX>\n
  char full[120];
  int n = snprintf(full, sizeof(full), "<%s|crc=%04X>\n", body, crc);
  if (n > 0 && (size_t)n < sizeof(full)) {
    writeUnderMutex(full, (size_t)n);
  }
}

void UartLink::log(const char* tag, const char* msg) {
  char buf[160];
  int n = snprintf(buf, sizeof(buf), "[%s] %s\n", tag, msg);
  if (n > 0 && (size_t)n < sizeof(buf)) {
    writeUnderMutex(buf, (size_t)n);
  }
}

void UartLink::logf(const char* tag, const char* fmt, ...) {
  char msg[140];
  va_list args;
  va_start(args, fmt);
  vsnprintf(msg, sizeof(msg), fmt, args);
  va_end(args);
  log(tag, msg);
}

uint32_t UartLink::getRejectedCount() {
  return _rejectedCount;
}

namespace {
  // Parse une ligne brute (sans le \n final) en Frame.
  // Retourne true si trame valide, false sinon.
  bool parseFrame(const char* raw, size_t len, UartLink::Frame& out) {
    // Verifie longueur max
    if (len > 80) return false;
    // Verifie delimiteurs
    if (len < 3 || raw[0] != '<' || raw[len - 1] != '>') return false;

    // Travaille sur le contenu interne (sans <>)
    const char* inner = raw + 1;
    size_t innerLen = len - 2;

    // Trouve |crc= a la fin
    if (innerLen < 9) return false;
    const char* crcStart = nullptr;
    for (int i = (int)innerLen - 9; i >= 0; i--) {
      if (memcmp(inner + i, "|crc=", 5) == 0) {
        crcStart = inner + i;
        break;
      }
    }
    if (!crcStart) return false;
    const char* crcHex = crcStart + 5;
    if (inner + innerLen - crcHex != 4) return false;
    for (int i = 0; i < 4; i++) {
      char c = crcHex[i];
      bool valid = (c >= '0' && c <= '9') || (c >= 'A' && c <= 'F');
      if (!valid) return false;
    }
    uint16_t recvCrc = 0;
    for (int i = 0; i < 4; i++) {
      char c = crcHex[i];
      uint8_t v = (c >= '0' && c <= '9') ? (c - '0') : (c - 'A' + 10);
      recvCrc = (recvCrc << 4) | v;
    }

    // Calcule le CRC sur la zone (inner sans |crc=XXXX)
    size_t crcZoneLen = (size_t)(crcStart - inner);
    uint16_t calcCrc = crc16((const uint8_t*)inner, crcZoneLen);
    if (calcCrc != recvCrc) return false;

    // Parser la zone : TYPE [args]|seq=N[|ack=M][|v=K]
    char zone[96];
    if (crcZoneLen >= sizeof(zone)) return false;
    memcpy(zone, inner, crcZoneLen);
    zone[crcZoneLen] = '\0';

    char* firstPipe = strchr(zone, '|');
    if (!firstPipe) return false;
    *firstPipe = '\0';
    char* head = zone;
    char* metaStart = firstPipe + 1;

    char* sp = strchr(head, ' ');
    if (sp) {
      *sp = '\0';
      strncpy(out.type, head, sizeof(out.type) - 1);
      out.type[sizeof(out.type) - 1] = '\0';
      strncpy(out.args, sp + 1, sizeof(out.args) - 1);
      out.args[sizeof(out.args) - 1] = '\0';
    } else {
      strncpy(out.type, head, sizeof(out.type) - 1);
      out.type[sizeof(out.type) - 1] = '\0';
      out.args[0] = '\0';
    }

    // Verifie que TYPE est en majuscules + chiffres + _
    for (size_t i = 0; out.type[i]; i++) {
      char c = out.type[i];
      bool ok = (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') || c == '_';
      if (!ok) return false;
    }

    out.seq = 0;
    out.ack = -1;
    out.version = -1;
    bool hasSeq = false;

    char* tok = metaStart;
    while (tok && *tok) {
      char* nextPipe = strchr(tok, '|');
      if (nextPipe) *nextPipe = '\0';

      if (strncmp(tok, "seq=", 4) == 0) {
        int v = atoi(tok + 4);
        if (v < 0 || v > 255) return false;
        out.seq = (uint8_t)v;
        hasSeq = true;
      } else if (strncmp(tok, "ack=", 4) == 0) {
        int v = atoi(tok + 4);
        if (v < 0 || v > 255) return false;
        out.ack = (int16_t)v;
      } else if (strncmp(tok, "v=", 2) == 0) {
        out.version = (int16_t)atoi(tok + 2);
      }

      tok = nextPipe ? nextPipe + 1 : nullptr;
    }

    if (!hasSeq) return false;
    return true;
  }

  bool isCmdFrame(const UartLink::Frame& f) {
    return strcmp(f.type, "CMD") == 0 || strcmp(f.type, "CMD_RESET") == 0;
  }

  void enqueueFrame(const UartLink::Frame& f) {
    if (_frameQueueCount >= FRAME_QUEUE_SIZE) {
      _frameQueueHead = (_frameQueueHead + 1) % FRAME_QUEUE_SIZE;
      _frameQueueCount--;
    }
    size_t idx = (_frameQueueHead + _frameQueueCount) % FRAME_QUEUE_SIZE;
    _frameQueue[idx] = f;
    _frameQueueCount++;
  }

  // Mode injection test : "BTN <row> <col>" sans framing
  bool tryHandleInjection(const char* line) {
    if (strncmp(line, "BTN ", 4) != 0) return false;
    UartLink::Frame f;
    strcpy(f.type, "MOVE_REQ");
    strncpy(f.args, line + 4, sizeof(f.args) - 1);
    f.args[sizeof(f.args) - 1] = '\0';
    f.seq = 0;
    f.ack = -1;
    f.version = -1;
    enqueueFrame(f);
    return true;
  }
}

void UartLink::poll() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      Frame f;
      const char* line = _rxBuffer.c_str();
      size_t llen = _rxBuffer.length();

      if (llen > 0 && line[0] == '<') {
        if (parseFrame(line, llen, f)) {
          // Dedup CMD (sec 5.3 spec)
          if (isCmdFrame(f)) {
            if ((int16_t)f.seq == _lastCmdSeqProcessed) {
              if (_lastCmdResult == CmdResult::DONE) {
                sendFrame("DONE", "", (int)f.seq);
              } else if (_lastCmdResult == CmdResult::ERR) {
                sendFrame("ERR", _lastCmdErrCode, (int)f.seq);
              }
              // Si NONE (en cours d'execution), ignore silencieusement
            } else {
              _lastCmdSeqProcessed = (int16_t)f.seq;
              _lastCmdResult = CmdResult::NONE;
              enqueueFrame(f);
            }
          } else {
            enqueueFrame(f);
          }
        } else {
          _rejectedCount++;
        }
      } else if (llen > 0) {
        // Pas une trame protocolaire : tente injection BTN
        // Conserve aussi en stub legacy pour compat ascendante (a supprimer apres refactor)
        if (!tryHandleInjection(line)) {
          // Legacy : conserve pour les callers Plan 1 qui appellent encore tryReadLine
          _legacyPendingLine = _rxBuffer;
          _legacyHasPending = true;
        }
      }
      _rxBuffer = "";
    } else {
      _rxBuffer += c;
      if (_rxBuffer.length() > 80) {
        _rxBuffer = "";
      }
    }
  }
}

bool UartLink::tryGetFrame(Frame& out) {
  if (_frameQueueCount == 0) return false;
  out = _frameQueue[_frameQueueHead];
  _frameQueueHead = (_frameQueueHead + 1) % FRAME_QUEUE_SIZE;
  _frameQueueCount--;
  return true;
}

// ==================================================================
// API legacy Plan 1 - stubs minimaux pour ne pas casser les callers existants.
// A supprimer dans le refactor des callers (Tasks 25-27).
// ==================================================================

void UartLink::sendLine(const String& line) {
  // Stub : envoie la ligne brute (sans framing). Les callers seront migres.
  String out = line + "\n";
  writeUnderMutex(out.c_str(), out.length());
}

bool UartLink::tryReadLine(String& out) {
  if (!_legacyHasPending) return false;
  out = _legacyPendingLine;
  _legacyHasPending = false;
  return true;
}

void UartLink::respondCmdDone(uint8_t ackSeq) {
  _lastCmdResult = CmdResult::DONE;
  _lastCmdErrCode[0] = '\0';
  sendFrame("DONE", "", (int)ackSeq);
}

void UartLink::respondCmdErr(uint8_t ackSeq, const char* code) {
  _lastCmdResult = CmdResult::ERR;
  strncpy(_lastCmdErrCode, code, sizeof(_lastCmdErrCode) - 1);
  _lastCmdErrCode[sizeof(_lastCmdErrCode) - 1] = '\0';
  // Cette ERR repond a une CMD : porte ack=
  sendFrame("ERR", code, (int)ackSeq);
  // Active la reemission periodique (cf. sec 6.5 spec)
  _errActive = true;
  strncpy(_errActiveCode, code, sizeof(_errActiveCode) - 1);
  _errActiveCode[sizeof(_errActiveCode) - 1] = '\0';
  _lastErrEmitMs = millis();
}

void UartLink::emitSpontaneousErr(const char* code) {
  // ERR sans ack : entree en ERROR depuis un etat sans CMD en cours
  sendFrame("ERR", code, -1);
  _errActive = true;
  strncpy(_errActiveCode, code, sizeof(_errActiveCode) - 1);
  _errActiveCode[sizeof(_errActiveCode) - 1] = '\0';
  _lastErrEmitMs = millis();
}

void UartLink::tickErrReemission(unsigned long currentMs) {
  if (!_errActive) return;
  if (currentMs - _lastErrEmitMs >= ERR_REEMIT_PERIOD_MS) {
    sendFrame("ERR", _errActiveCode, -1);
    _lastErrEmitMs = currentMs;
  }
}

void UartLink::clearErrState() {
  _errActive = false;
  _errActiveCode[0] = '\0';
}
