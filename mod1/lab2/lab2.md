2:05 – Received button, analog joystick, and switch
2:06 – started collecting wires to connect protoboard to rpi
2:08 – plugged hardwares into protoboard
2:10 – Used pinout to identify ground pins, power pins, and gpi
2:12 – Connected GND to blue rail, connected button to protoboard, and connected other lead of button to GPIO2
2:15 – simple test script using gpiozero to print when button is pressed or not
2:20 – repeat for switch, map when_pressed and when_released to print lambdas
2:25 – for joystick, we are just using the switch and the wiring setup is a little different
Connect +5v on joystick to +3.3v on Pi so output isn’t 5V to GPIO
Connect GND to blue rail & SW to GPIO
2:35 – Finish code for printing states based on button states (bitwise or of on/off for 8 states)
2:40 – look into physical debouncing, realize it’s not a possibility with the tools we have right now, use pull_up and bounce_time kwargs to debounce in code
2:45 – have a text input line, output that text line modified in a way specified by current state (e.g. to upper, to lower, etc.)
