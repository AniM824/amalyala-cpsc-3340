from gpiozero import Button

button = Button(2, pull_up=True, bounce_time=0.03)
joystick = Button(3, pull_up=True, bounce_time=0.03)
switch = Button(4, pull_up=True, bounce_time=0.03)

transforms = [
    lambda s: s,             # 0 = 000
    lambda s: s.upper(),     # 1 = 001
    lambda s: s.lower(),     # 2 = 010
    lambda s: s[::-1],       # 3 = 011
    lambda s: f"*{s}*",      # 4 = 100
    lambda s: f"[{s}]",      # 5 = 101
    lambda s: s + "!",       # 6 = 110
    lambda s: s + "!!!",     # 7 = 111
]

while True:
    text = input("> ")

    state = (
        (button.is_pressed << 2)
        | (joystick.is_pressed << 1)
        | switch.is_pressed
    )

    print(transforms[state](text))
