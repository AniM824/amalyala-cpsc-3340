/*
 *  Glass Heart firmware: reads the sensors inside the printed heart and
 *  streams them to the client (heart.py) over UDP, one message per packet:
 *    hit,<strength 0-1>         once per tap, right after its peak
 *    light,<covered 0/1>,<drop 0-1>   20/s
 *    touch,<0/1>                20/s
 *
 *  Pins:  GPIO4  = piezo
 *         GPIO5  = photoresistor (LDR) divider
 *         GPIO11 = capacitive touch (copper tape)
 */
#include <Arduino.h>
#include <WiFi.h>
#include <NetworkUdp.h>

// ---------- WiFi / UDP ----------
const char *networkName = "yale wireless";
const char *networkPswd = "";
const char *udpAddress  = "10.66.184.190";   // IP of the computer running heart.py
const int   udpPort     = 3333;

// ---------- Pins ----------
const int PIEZO_PIN = 4;
const int LDR_PIN   = 5;
const int TOUCH_PIN = 11;

// ---------- Tuning ----------
const int   PIEZO_MIN_THRESHOLD_MV   = 80;   // never trigger below this
const int   PIEZO_MARGIN_MV          = 60;   // added on top of idle noise
const int   PIEZO_MAX_MV             = 3100; // a reading this high counts as the hardest hit
const unsigned long PIEZO_PEAK_MS    = 15;   // how long to watch a tap for its peak
const unsigned long PIEZO_DEADTIME_MS = 150; // ignore ringing after a tap
const float TOUCH_ON_RATIO    = 1.05;  // touched when reading > baseline * this
const float TOUCH_OFF_RATIO   = 1.03;  // released when reading < baseline * this
const float LDR_COVERED_RATIO = 0.6;   // "covered" when light < baseline * this
const unsigned long SEND_INTERVAL_MS = 50;  // 20 packets per second
const bool  SERIAL_DEBUG = true;       // also print every message to Serial

// ---------- State ----------
NetworkUDP udp;
volatile bool connected = false;

int   piezoThreshold = PIEZO_MIN_THRESHOLD_MV;
float touchBaseline  = 0;
float lightBaseline  = 0;

int  tapPeak = 0;            // highest reading of the tap being measured (0 = no tap)
unsigned long tapStartMs = 0, lastTapMs = 0;

bool touched = false;

int  lightMv = 0;
bool covered = false;

unsigned long lastTouchReadMs = 0, lastLightReadMs = 0, lastSendMs = 0;

// WARNING: WiFiEvent is called from a separate FreeRTOS task (thread)!
void WiFiEvent(WiFiEvent_t event) {
  switch (event) {
    case ARDUINO_EVENT_WIFI_STA_GOT_IP:
      Serial.print("WiFi connected! IP address: ");
      Serial.println(WiFi.localIP());
      udp.begin(WiFi.localIP(), udpPort);
      connected = true;
      break;
    case ARDUINO_EVENT_WIFI_STA_DISCONNECTED:
      Serial.println("WiFi lost connection");
      connected = false;
      break;
    default: break;
  }
}

void connectToWiFi(const char *ssid, const char *pwd) {
  Serial.println("Connecting to WiFi network: " + String(ssid));
  WiFi.disconnect(true);
  WiFi.onEvent(WiFiEvent);
  WiFi.begin(ssid, pwd);
}

void send(const char *msg) {
  if (connected) {
    udp.beginPacket(udpAddress, udpPort);
    udp.print(msg);
    udp.endPacket();
  }
  if (SERIAL_DEBUG) Serial.println(msg);
}

void calibrate() {
  Serial.println("Calibrating - keep hands off the heart for 2 seconds...");

  // The first touch readings after boot are junk; throw them away
  for (int i = 0; i < 5; i++) { touchRead(TOUCH_PIN); delay(20); }

  const int N = 100;
  uint64_t touchSum = 0, lightSum = 0;
  int piezoIdleMax = 0;

  for (int i = 0; i < N; i++) {
    touchSum += touchRead(TOUCH_PIN);
    lightSum += analogReadMilliVolts(LDR_PIN);
    for (int j = 0; j < 20; j++) {               // sample piezo noise
      int p = analogReadMilliVolts(PIEZO_PIN);
      if (p > piezoIdleMax) piezoIdleMax = p;
    }
    delay(15);
  }

  touchBaseline  = touchSum / (float)N;
  lightBaseline  = lightSum / (float)N;
  lightMv        = (int)lightBaseline;
  piezoThreshold = max(PIEZO_MIN_THRESHOLD_MV, piezoIdleMax + PIEZO_MARGIN_MV);

  Serial.printf("Touch baseline: %.0f\n", touchBaseline);
  Serial.printf("Light baseline: %.0f mV\n", lightBaseline);
  Serial.printf("Piezo idle max: %d mV -> threshold %d mV\n", piezoIdleMax, piezoThreshold);
}

void setup() {
  Serial.begin(115200);
  delay(500);

  analogReadResolution(12);
  analogSetPinAttenuation(PIEZO_PIN, ADC_11db);
  analogSetPinAttenuation(LDR_PIN, ADC_11db);

  calibrate();
  connectToWiFi(networkName, networkPswd);
}

void loop() {
  unsigned long now = millis();
  char msg[40];

  // --- Piezo: read every pass so short spikes aren't missed ---
  // a tap starts when the reading crosses the threshold; watch it for a few ms
  // to catch its peak, then send how hard it was
  int p = analogReadMilliVolts(PIEZO_PIN);
  if (tapPeak == 0 && p > piezoThreshold && now - lastTapMs > PIEZO_DEADTIME_MS) {
    tapStartMs = now;
    tapPeak = p;
  }
  if (tapPeak > 0) {
    if (p > tapPeak) tapPeak = p;
    if (now - tapStartMs >= PIEZO_PEAK_MS) {
      float strength = constrain((tapPeak - piezoThreshold) / (float)(PIEZO_MAX_MV - piezoThreshold), 0.0, 1.0);
      snprintf(msg, sizeof msg, "hit,%.2f", strength);
      send(msg);
      if (SERIAL_DEBUG) Serial.printf("TAP peak %d mV\n", tapPeak);
      tapPeak = 0;
      lastTapMs = now;
    }
  }

  // --- Touch: every 20 ms, with hysteresis ---
  if (now - lastTouchReadMs >= 20) {
    lastTouchReadMs = now;
    uint32_t touchValue = touchRead(TOUCH_PIN);
    touched = touched ? (touchValue > touchBaseline * TOUCH_OFF_RATIO)
                      : (touchValue > touchBaseline * TOUCH_ON_RATIO);
    // Let the baseline slowly follow temperature/humidity drift while untouched
    if (!touched) touchBaseline = touchBaseline * 0.999f + touchValue * 0.001f;
  }

  // --- Light: every 50 ms, smoothed ---
  if (now - lastLightReadMs >= 50) {
    lastLightReadMs = now;
    int raw = analogReadMilliVolts(LDR_PIN);
    lightMv = (lightMv * 3 + raw) / 4;
    covered = lightMv < lightBaseline * LDR_COVERED_RATIO;
  }

  // --- Send light and touch ---
  if (now - lastSendMs >= SEND_INTERVAL_MS) {
    lastSendMs = now;
    float drop = constrain((lightBaseline - lightMv) / max(lightBaseline, 1.0f), 0.0, 1.0);
    snprintf(msg, sizeof msg, "light,%d,%.2f", covered ? 1 : 0, drop);
    send(msg);
    snprintf(msg, sizeof msg, "touch,%d", touched ? 1 : 0);
    send(msg);
  }
}
