#ifndef UART_LINK_H
#define UART_LINK_H

#include <Arduino.h>

namespace UartLink {
  void init();
  void poll();                       // assemble les caracteres entrants en lignes
  bool tryReadLine(String& out);     // recupere une ligne complete si dispo
  void sendLine(const String& line); // envoie une ligne terminee par \n
}

#endif
