const int joystick1YPin = A3;
const int joystick1XPin = A4;
// const int joystick1PressPin = 1;
const int button1Pin = 2;
const int switch1Pin = 42;
const int joystick2XPin = A5;
const int joystick2YPin = 18;
// const int joystick2PressPin = 10;
const int button2Pin = 16;
const int switch2Pin = 17;
void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  // pinMode(joystick1PressPin, INPUT_PULLUP);
  pinMode(button1Pin, INPUT_PULLUP);
  pinMode(switch1Pin, INPUT_PULLUP);
  // pinMode(joystick2PressPin, INPUT_PULLUP);
  pinMode(button2Pin, INPUT_PULLUP);
  pinMode(switch2Pin, INPUT_PULLUP);
}
void loop() {
  int x1 = analogRead(joystick1XPin);
  int y1 = analogRead(joystick1YPin);
  // int joystick1 = digitalRead(joystick1PressPin) == LOW;
  int button1 = digitalRead(button1Pin) == LOW;
  int switch1 = digitalRead(switch1Pin) == LOW;
  int x2 = analogRead(joystick2XPin);
  int y2 = analogRead(joystick2YPin);
  // int joystick2 = digitalRead(joystick2PressPin) == LOW;
  int button2 = digitalRead(button2Pin) == LOW;
  int switch2 = digitalRead(switch2Pin) == LOW;
  Serial.printf("%d,%d,%d,%d,%d,%d,%d,%d\n",
                x1, y1, button1, switch1,
                x2, y2, button2, switch2);
  delay(20);
}
