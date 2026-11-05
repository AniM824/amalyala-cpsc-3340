#include <Stepper.h>
#include <ESP32Servo.h>

const int stepsPerRevolution = 2048;  // change this to fit the number of steps per revolution
// for your motor

// initialize the stepper library on pins 8 through 11:
Stepper thugstep(stepsPerRevolution, 19, 5, 18, 17);  // IN1, IN3, IN2, IN4 order
Servo servodisdih;
int dihval = 0;

void setup() {
  // set the speed at 60 rpm:
  thugstep.setSpeed(20);
  servodisdih.attach(13);
  // initialize the serial port:
  Serial.begin(9600);
}

void loop() {
  // step one revolution  in one direction:
  Serial.println("clockwise");
  thugstep.step(stepsPerRevolution);
  dihval += 10;
  dihval %= 190;
  servodisdih.write(dihval);
  delay(100);

  // step one revolution in the other direction:
  // Serial.println("counterclockwise");
  // thugstep.step(-stepsPerRevolution);
  // delay(500);
}
