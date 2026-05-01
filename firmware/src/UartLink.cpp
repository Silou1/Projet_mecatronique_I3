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
