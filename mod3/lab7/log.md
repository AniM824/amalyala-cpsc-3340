## 10/29

### 1:50pm

- Ani caught up from missed lecture and figured out difference between servo & stepper motors, the reason we need a ULN2003 board for the stepper motor
- Looked into Stepper and Servo APIs, copied boilerplate code, and quickly wrote up programming logic for rotating stepper 10 degrees every servo revolution, and doing % 180 to move it back to 0

### 2:10pm

- Received hardware components and started wiring up stepper motor
- Connected ESP32 to laptop, connected ESP32 and ULN2003 to ground and 5v lanes, connected ESP32 to ULN2003 board, and connected ULN2003 board to stepper motor
- Started testing stepper motor in isolation, wasn't working
- Debugged and realized we were using the wrong pins

### 2:25pm

- Fixed pins and added debugging lines to code, tried again
- Servo motor was working, but stepper motor was not working (though we could feel whirring inside)
- Hypothesized that the stepper motor was just not working so we got a new one and tried again
- Realized RPM was too high, set it from 60 → 10 rpm, and then everything worked yay! (max RPM is 17-18 according to internet)

## 11/4 -- description of wiring
- ESP32 Micro-USB <---> Laptop USB
- ESP32 5V <---> breadboard +
- ESP32 GND <---> breadboard -

- ESP32 GPIO13 <---> Servo signal
- 5V rail <---> Servo Power
- GND rail <---> Servo GND

- ESP32 GPIO19 <---> ULN2003 IN1
- ESP32 GPIO18 <---> ULN2003 IN2
- ESP32 GPIO05 <---> ULN2003 IN3
- ESP32 GPIO17 <---> ULN2003 IN4
5V rail <---> ULN2003 +
GND rail <---> ULN2003 -
Stepper motor <---> ULN2003 "5-pin JST" (according to google, idk what its called)

