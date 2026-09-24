from gpiozero import LED, Button
from signal import pause

button = Button(14, bounce_time=0.05)
button.when_pressed = lambda: print("button pressed")
button.when_released = lambda: print("button released")

switch = Button(15, bounce_time=0.05)
switch.when_pressed = lambda: print("switch on")
switch.when_released = lambda: print("switch released")

joystick = Button(18, bounce_time=0.05)
joystick.when_pressed = lambda: print("joystick on")
joystick.when_released = lambda: print("joystick released")

pause()
