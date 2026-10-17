#include <Arduino.h>
#include <WiFi.h>
#include <NetworkUdp.h>

const char *networkName = "yale wireless";
const char *networkPswd = "";
const char *udpAddress = "10.67.65.142";
const int udpPort = 3333;
const int photoPin = 4;

volatile boolean connected = false;
NetworkUDP udp;

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

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  WiFi.disconnect(true);
  WiFi.onEvent(WiFiEvent);
  WiFi.begin(networkName, networkPswd);
  WiFi.setSleep(false);
  Serial.println("Connecting to WiFi...");
}

void loop() {
  int lightValue = analogRead(photoPin);
  Serial.println(lightValue);
  if (connected) {
    udp.beginPacket(udpAddress, udpPort);
    udp.print(lightValue);
    udp.endPacket();
  } else {
    Serial.println("not connected");
  }
  delay(50);
}
