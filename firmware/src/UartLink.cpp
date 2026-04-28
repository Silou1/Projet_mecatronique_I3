#include "UartLink.h"

namespace {
  String _rxBuffer;
  String _pendingLine;
  bool _hasPending = false;
}

void UartLink::init() {
  // Serial deja initialise dans setup()
  Serial.println("[UartLink] init");
  _rxBuffer.reserve(64);
}

void UartLink::poll() {
  while (Serial.available() > 0 && !_hasPending) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      _pendingLine = _rxBuffer;
      _rxBuffer = "";
      _hasPending = true;
      break;
    }
    _rxBuffer += c;
    if (_rxBuffer.length() > 60) {
      // protection debordement : on jette
      _rxBuffer = "";
    }
  }
}

bool UartLink::tryReadLine(String& out) {
  if (!_hasPending) return false;
  out = _pendingLine;
  _hasPending = false;
  return true;
}

void UartLink::sendLine(const String& line) {
  Serial.print(line);
  Serial.print('\n');
}
