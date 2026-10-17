# Mean Art
> By: Aniketh Malyala and Abheek Dhawan

Move the two cursors with the joysticks. When drawing is on, their midpoint traces the shape.

## Hardware

Connect the ESP32-S3 to the Raspberry Pi with a USB data cable. Power both joysticks from **3.3 V**, with a shared GND. Connect each button/switch between its GPIO and GND.

| Input | ESP32 pin | Action |
|---|---|---|
| P1 joystick X / Y | A4 / A3 | Move blue cursor |
| P2 joystick X / Y | A5 / GPIO18 | Move pink cursor |
| Button 1 | GPIO2 | Submit |
| Button 2 | GPIO16 | Clear drawing |
| Switch 1 | GPIO42 | Drawing on/off |
| Switch 2 | GPIO17 | OFF: easy, ON: hard |

The ESP32 sketch must send this CSV order at **115200 baud**, with buttons/switches reporting `1` when active:

```text
x1,y1,button1,switch1,x2,y2,button2,switch2
```

## Run

On Raspberry Pi OS, install dependencies:

```bash
sudo apt install python3-pygame python3-serial
```

From the folder containing the game, run in the Pi's desktop:

```bash
python game.py --port /dev/ttyUSB0
```

Change the port if needed (for example, `/dev/ttyACM0`). Leave both joysticks centered during startup calibration. Press **Esc** to quit. Add `--windowed` for a window.

## Configuration

Near the top of the Python file, adjust `DEADZONE`, `CURSOR_SPEED`, or `INVERT_X` / `INVERT_Y` (P1, P2). Both joysticks currently swap X/Y in `SerialInput.axes()`.

For keyboard testing, run with `--keyboard`: **WASD** for P1, **arrow keys** for P2, **Space** to draw, **H** for difficulty, **Enter** to submit, and **R** to reset.
