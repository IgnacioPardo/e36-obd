// KWP71 sobre ESP32-S3 + L9637D  —  BMW E36 M43B16, Motronic 1.7.2
//
// Puerto de e36obd/kline.py y e36obd/kwp71.py, que ya funcionan contra este
// auto. Lo que cambia respecto de macOS:
//
//   · El init de 5 baudios deja de ser un truco. En macOS habia que hacer
//     bit-bang con TIOCSBRK porque el driver FTDI no deja tocar la linea;
//     aca se escribe el GPIO directo.
//   · Desaparecen los 231 ms por lectura del driver FTDI. El techo real lo
//     pone el handshake de KWP71 y el retardo entre bytes del DME.
//
// El L9637D NO invierte: en la figura 5 de la hoja de datos, TX baja y K baja
// detras. Asi que la logica del GPIO es la del UART, sin inversion.
//
// La linea K es UN hilo, asi que todo lo que transmitimos vuelve por RX. Cada
// escritura se sigue de una lectura que descarta ese eco. Es distinto del
// reconocimiento invertido, que es lo que manda la ECU.
//
// Herramientas > Puerto: el de modo normal (usbmodem largo), no el de descarga.
// Herramientas > USB CDC On Boot: Enabled, para que Serial sea la consola USB.

#include <Arduino.h>

// ------------------------------------------------------------------ pines
static const int PIN_K_TX = 17;   // -> L9637D pin 4 (TX)
static const int PIN_K_RX = 18;   // <- L9637D pin 1 (RX)

// --------------------------------------------------------------- protocolo
static const uint32_t KLINE_BAUD   = 9600;
static const uint8_t  ECU_ADDRESS  = 0x10;   // DME. La caja es 0x6C a 4800.
static const int      KEYWORD_COUNT = 3;     // el DME responde 55 00 81

// BMW espera 2600 ms de bus en reposo antes de cada init. Con 260 ms el
// barrido de direcciones daba falsos negativos: es un error que ya cometimos.
static const uint32_t BUS_IDLE_MS    = 2600;
static const uint32_t BIT_MS         = 200;  // 5 baudios = 200 ms por bit
static const uint32_t INTER_BYTE_MS  = 5;
static const uint32_t BYTE_TIMEOUT_MS = 1200;

// Titulos de bloque KWP71
enum : uint8_t {
  BLK_READ_RAM        = 0x01,
  BLK_DISCONNECT      = 0x06,
  BLK_READ_FAULTS     = 0x07,
  BLK_READ_ADC        = 0x08,
  BLK_EMPTY           = 0x09,
  BLK_NACK            = 0x0A,
  BLK_NOT_SUPPORTED   = 0x0B,
  BLK_END             = 0x03,
};

static uint8_t g_seq = 0;

// =========================================================== transporte
static void klineIdle() {
  // Fuera de sesion la linea descansa alta (recesiva).
  pinMode(PIN_K_TX, OUTPUT);
  digitalWrite(PIN_K_TX, HIGH);
}

static bool readByteRaw(uint8_t *out, uint32_t timeoutMs) {
  uint32_t t0 = millis();
  while (millis() - t0 < timeoutMs) {
    if (Serial1.available()) { *out = (uint8_t)Serial1.read(); return true; }
    delay(1);
  }
  return false;
}

// Escribe un byte y se come su propio eco. La linea K es un hilo: lo que
// transmitimos siempre vuelve.
static bool writeByteSwallowEcho(uint8_t b) {
  while (Serial1.available()) Serial1.read();      // limpiar antes
  Serial1.write(b);
  Serial1.flush();
  uint8_t echo;
  if (!readByteRaw(&echo, 300)) return false;      // sin eco: algo anda mal
  return echo == b;
}

// ====================================================== init de 5 baudios
static bool slowInit(uint8_t address, uint8_t *keywords, int nKeywords) {
  Serial.printf("bus en reposo %lu ms...\n", (unsigned long)BUS_IDLE_MS);
  klineIdle();
  delay(BUS_IDLE_MS);

  Serial.printf("init de 5 baudios, direccion 0x%02X\n", address);

  // bit de arranque
  digitalWrite(PIN_K_TX, LOW);
  delay(BIT_MS);
  // ocho bits de datos, LSB primero
  for (int i = 0; i < 8; i++) {
    digitalWrite(PIN_K_TX, (address >> i) & 1 ? HIGH : LOW);
    delay(BIT_MS);
  }
  // El bit de parada NO se duerme: es la linea descansando alta. Si esperamos
  // los 200 ms completos antes de escuchar, tiramos a la basura el 0x55 de la
  // ECU, que puede llegar a los ~60 ms. Este bug ya nos costo una sesion.
  digitalWrite(PIN_K_TX, HIGH);

  // pasar el pin al UART y escuchar
  Serial1.begin(KLINE_BAUD, SERIAL_8N1, PIN_K_RX, PIN_K_TX);
  while (Serial1.available()) Serial1.read();

  uint8_t b;
  if (!readByteRaw(&b, 500)) {
    Serial.println("  sin respuesta al init");
    return false;
  }
  if (b != 0x55) {
    Serial.printf("  se esperaba 0x55 y llego 0x%02X\n", b);
    // 0x66 significa que la ECU habla a la MITAD de nuestra velocidad:
    // un 0x55 a 4800 muestreado a 9600 se lee 0x66. Asi encontramos la caja.
    if (b == 0x66) Serial.println("  0x66 = esta a 4800, no a 9600");
    return false;
  }
  Serial.println("  0x55 sincronismo OK");

  for (int i = 0; i < nKeywords; i++) {
    if (!readByteRaw(&keywords[i], 500)) {
      Serial.printf("  falto la keyword %d\n", i);
      return false;
    }
  }
  Serial.print("  keywords:");
  for (int i = 0; i < nKeywords; i++) Serial.printf(" %02X", keywords[i]);
  Serial.println();

  // La ultima keyword se reconoce invertida y ahi arranca la sesion.
  delay(INTER_BYTE_MS * 5);
  Serial1.write((uint8_t)(~keywords[nKeywords - 1]));
  Serial1.flush();
  uint8_t echo;
  readByteRaw(&echo, 300);
  return true;
}

// ============================================================== bloques
static bool sendBlock(uint8_t title, const uint8_t *payload, uint8_t n) {
  g_seq = (uint8_t)(g_seq + 1);
  uint8_t len = (uint8_t)(1 + 1 + n + 1);      // seq + title + payload + fin
  uint8_t buf[64];
  uint8_t k = 0;
  buf[k++] = len;
  buf[k++] = g_seq;
  buf[k++] = title;
  for (uint8_t i = 0; i < n; i++) buf[k++] = payload[i];
  buf[k++] = BLK_END;

  for (uint8_t i = 0; i < k; i++) {
    if (!writeByteSwallowEcho(buf[i])) {
      Serial.printf("  se perdio el eco en el byte %u\n", i);
      return false;
    }
    // Todos menos el ultimo los reconoce la ECU, invertidos.
    if (i < len) {
      uint8_t ack;
      if (!readByteRaw(&ack, BYTE_TIMEOUT_MS)) {
        Serial.printf("  sin reconocimiento del byte %u\n", i);
        return false;
      }
      if (ack != (uint8_t)(~buf[i])) {
        Serial.printf("  reconocimiento malo en %u: esperaba %02X, llego %02X\n",
                      i, (uint8_t)(~buf[i]), ack);
        return false;
      }
    }
    delay(INTER_BYTE_MS);
  }
  return true;
}

static bool recvBlock(uint8_t *title, uint8_t *payload, uint8_t *nOut) {
  uint8_t len;
  if (!readByteRaw(&len, BYTE_TIMEOUT_MS)) return false;
  if (len < 3) { Serial.printf("  bloque corto: len=%u\n", len); return false; }

  delay(INTER_BYTE_MS);
  writeByteSwallowEcho((uint8_t)(~len));

  uint8_t raw[64];
  raw[0] = len;
  for (uint8_t i = 1; i <= len; i++) {
    if (!readByteRaw(&raw[i], BYTE_TIMEOUT_MS)) return false;
    if (i < len) {
      delay(INTER_BYTE_MS);
      writeByteSwallowEcho((uint8_t)(~raw[i]));
    }
  }
  g_seq   = raw[1];
  *title  = raw[2];
  *nOut   = (uint8_t)(len - 3);
  for (uint8_t i = 0; i < *nOut; i++) payload[i] = raw[3 + i];
  return true;
}

// ============================================================== fallas
// Cada falla son 5 bytes: [codigo][condicion][rpm][byte3][frecuencia].
// Las escalas del freeze frame no estan cerradas; el codigo si.
static void printFaults(const uint8_t *p, uint8_t n) {
  if (n == 0) { Serial.println("  sin fallas almacenadas"); return; }
  for (uint8_t i = 0; i + 4 < n; i += 5) {
    Serial.printf("  codigo %3u  cond 0x%02X  ocurrencias %u  crudo %02X %02X\n",
                  p[i], p[i + 1], p[i + 4], p[i + 2], p[i + 3]);
    if (p[i] == 100) Serial.println("      -> Amplifier/output stage 1 in DME");
    if (p[i] == 36)  Serial.println("      -> EVAP / valvula del canister");
  }
}

// ================================================================ arranque
void setup() {
  Serial.begin(115200);
  uint32_t t0 = millis();
  while (!Serial && millis() - t0 < 4000) delay(50);
  delay(500);

  Serial.println();
  Serial.println("=== KWP71 / E36 M43B16 ===");
  Serial.printf("TX=GPIO%d  RX=GPIO%d  %lu baudios  direccion 0x%02X\n",
                PIN_K_TX, PIN_K_RX, (unsigned long)KLINE_BAUD, ECU_ADDRESS);
  Serial.println("Contacto en posicion 2. El motor puede estar apagado.");
  Serial.println();

  uint8_t kw[KEYWORD_COUNT] = {0};
  if (!slowInit(ECU_ADDRESS, kw, KEYWORD_COUNT)) {
    Serial.println("\nINIT FALLIDO. Revisar, en orden:");
    Serial.println("  1. llave en posicion 2, no en 1");
    Serial.println("  2. OBD2 pin 7 Y pin 15 juntos al pin 6 del L9637D");
    Serial.println("  3. pin 3 del L9637D en 3,3 V");
    Serial.println("  4. pin 6 en reposo cerca de 12 V");
    return;
  }
  Serial.println("\nSESION ABIERTA\n");

  // La ECU manda sus cadenas de identificacion sin que se las pidan.
  uint8_t title, payload[64], n;
  for (int i = 0; i < 8; i++) {
    if (!recvBlock(&title, payload, &n)) break;
    if (title == BLK_EMPTY) break;
    Serial.printf("bloque 0x%02X (%u bytes): ", title, n);
    for (uint8_t j = 0; j < n; j++)
      Serial.print((payload[j] >= 32 && payload[j] < 127) ? (char)payload[j] : '.');
    Serial.println();
    delay(INTER_BYTE_MS);
    sendBlock(BLK_EMPTY, nullptr, 0);
  }

  Serial.println("\n--- memoria de fallas ---");
  if (sendBlock(BLK_READ_FAULTS, nullptr, 0)) {
    while (recvBlock(&title, payload, &n)) {
      if (title == BLK_EMPTY) break;
      printFaults(payload, n);
      delay(INTER_BYTE_MS);
      sendBlock(BLK_EMPTY, nullptr, 0);
    }
  }

  Serial.println("\nSe esperan los codigos 100 y 36, los dos con contador en 50.");
  Serial.println("Si aparecen, todo el stack funciona.");
  sendBlock(BLK_DISCONNECT, nullptr, 0);
}

void loop() {
  delay(1000);
}
