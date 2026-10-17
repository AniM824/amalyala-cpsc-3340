#!/usr/bin/env python3
import argparse
import glob
import math
import random
import sys
import threading
import time

import pygame

try:
    import serial
except ImportError:
    serial = None


WIDTH, HEIGHT = 1280, 720
FPS = 60

SHAPE_BOX = 500
SHAPE_CENTER = (WIDTH / 2, HEIGHT / 2 + 20)
TOLERANCE_PX = 12
RESULT_SECONDS = 4.0

CURSOR_SPEED = 450
DEADZONE = 0.12
ADC_MAX = 4095
CALIBRATION_SAMPLES = 25
INPUT_TIMEOUT = 0.5
DEBOUNCE_SECONDS = 0.04

INVERT_X = (False, True)
INVERT_Y = (False, True)

BG = (18, 18, 26)
TARGET_COLOR = (62, 62, 84)
TARGET_REVEAL_COLOR = (120, 120, 160)
INK_COLOR = (255, 196, 64)
CURSOR_COLORS = ((64, 210, 255), (255, 92, 200))
TEXT_COLOR = (220, 220, 230)
DIM_TEXT = (130, 130, 150)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


def _closed(points):
    return points + [points[0]]


def _parametric(fn, t0=0.0, t1=2 * math.pi, n=240):
    return [fn(t0 + (t1 - t0) * i / n) for i in range(n + 1)]


def _star_points(tips, outer, inner):
    pts = []
    for i in range(tips * 2):
        r = outer if i % 2 == 0 else inner
        a = math.pi / 2 + math.pi * i / tips
        pts.append((r * math.cos(a), r * math.sin(a)))
    return _closed(pts)


def shape_circle():
    return [_parametric(lambda t: (math.cos(t), math.sin(t)))]


def shape_square():
    return [_closed([(-1, -1), (1, -1), (1, 1), (-1, 1)])]


def shape_triangle():
    return [_closed([(math.cos(a), math.sin(a))
                     for a in (math.pi / 2, math.pi * 7 / 6, math.pi * 11 / 6)])]


def shape_heart():
    def fn(t):
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        return (x, y)
    return [_parametric(fn)]


def shape_diamond():
    return [_closed([(0, 1.3), (0.8, 0), (0, -1.3), (-0.8, 0)])]


def shape_star():
    return [_star_points(5, 1.0, 0.42)]


def shape_moon():


    big_r, d, small_r = 1.0, 0.55, 0.85
    ix = (d * d + big_r * big_r - small_r * small_r) / (2 * d)
    iy = math.sqrt(big_r * big_r - ix * ix)
    a = math.atan2(iy, ix)
    b = math.atan2(iy, ix - d)
    outer = _parametric(lambda t: (big_r * math.cos(t), big_r * math.sin(t)), a, 2 * math.pi - a)
    inner = _parametric(lambda t: (d + small_r * math.cos(t), small_r * math.sin(t)),
                        2 * math.pi - b, b)
    return [outer + inner]


def shape_pumpkin():
    def dimple(t, centre, depth):
        offset = (t - centre + math.pi) % (2 * math.pi) - math.pi
        return depth * math.exp(-(offset / 0.4) ** 2)

    def body(t):
        k = 1 - dimple(t, math.pi / 2, 0.14) - dimple(t, -math.pi / 2, 0.08)
        return (1.3 * math.cos(t) * k, 0.95 * math.sin(t) * k)

    def rib(side):
        return _parametric(lambda s: (side * 0.6 * math.cos(s), 0.84 * math.sin(s)),
                           -math.pi / 2, math.pi / 2, 80)

    stem = [(-0.1, 0.8), (-0.14, 1.2), (0.06, 1.25), (0.1, 0.8)]
    return [_parametric(body), rib(-1), rib(1), stem]


def shape_house():
    walls = [(-1, 0.4), (-1, -1), (1, -1), (1, 0.4)]
    roof = _closed([(-1.2, 0.4), (0, 1.3), (1.2, 0.4)])
    door = [(-0.25, -1), (-0.25, -0.3), (0.25, -0.3), (0.25, -1)]
    return [walls, roof, door]


def shape_lightning():
    return [_closed([(-0.1, 1.3), (0.6, 1.3), (0.15, 0.3), (0.6, 0.3),
                     (-0.4, -1.3), (-0.05, -0.15), (-0.5, -0.15)])]


def shape_spiral():
    turns = 3
    end = 2 * math.pi * turns
    return [_parametric(lambda t: (t / end * math.cos(t), t / end * math.sin(t)), 0, end, 480)]


EASY_SHAPES = {
    "Circle": shape_circle,
    "Square": shape_square,
    "Triangle": shape_triangle,
    "Heart": shape_heart,
    "Diamond": shape_diamond,
}
HARD_SHAPES = {
    "Pumpkin": shape_pumpkin,
    "Star": shape_star,
    "Moon": shape_moon,
    "House": shape_house,
    "Lightning Bolt": shape_lightning,
    "Spiral": shape_spiral,
}


def fit_to_canvas(polylines):
    xs = [x for line in polylines for x, _ in line]
    ys = [y for line in polylines for _, y in line]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    scale = SHAPE_BOX / max(max_x - min_x, max_y - min_y)
    mid_x, mid_y = (min_x + max_x) / 2, (min_y + max_y) / 2
    cx, cy = SHAPE_CENTER
    return [[(cx + (x - mid_x) * scale, cy - (y - mid_y) * scale) for x, y in line]
            for line in polylines]


def _rasterize(polylines, radius):
    surf = pygame.Surface((WIDTH, HEIGHT))
    surf.fill(BLACK)
    surf.set_colorkey(BLACK)
    for line in polylines:
        pts = [(round(x), round(y)) for x, y in line]
        if radius == 0:
            if len(pts) > 1:
                pygame.draw.lines(surf, WHITE, False, pts, 1)
            else:
                surf.set_at(pts[0], WHITE)
        else:
            if len(pts) > 1:
                pygame.draw.lines(surf, WHITE, False, pts, 2 * radius + 1)

            for p in pts:
                pygame.draw.circle(surf, WHITE, p, radius)
    return pygame.mask.from_surface(surf)


def score_drawing(target, strokes, tolerance=TOLERANCE_PX):
    strokes = [s for s in strokes if s]
    if not strokes:
        return 0.0, 0.0, 0.0

    drawn = _rasterize(strokes, 0)
    target_thin = _rasterize(target, 0)
    precision = drawn.overlap_area(_rasterize(target, tolerance), (0, 0)) / drawn.count()
    recall = target_thin.overlap_area(_rasterize(strokes, tolerance), (0, 0)) / target_thin.count()
    if precision + recall == 0:
        return 0.0, precision, recall
    return 2 * precision * recall / (precision + recall), precision, recall


def normalize_axis(raw, center):
    if raw >= center:
        v = (raw - center) / max(1, ADC_MAX - center)
    else:
        v = (raw - center) / max(1, center)
    if abs(v) < DEADZONE:
        return 0.0
    magnitude = min(1.0, (abs(v) - DEADZONE) / (1 - DEADZONE))
    return math.copysign(magnitude ** 2, v)


def parse_csv_packet(line):
    if not line.endswith(b"\n"):
        return None
    try:
        values = tuple(map(int, line.decode("ascii").strip().split(",")))
    except (ValueError, UnicodeDecodeError):
        return None
    if len(values) != 8:
        return None
    x1, y1, button1, switch1, x2, y2, button2, switch2 = values
    if any(not 0 <= v <= ADC_MAX for v in (x1, y1, x2, y2)):
        return None
    if any(v not in (0, 1) for v in (button1, switch1, button2, switch2)):
        return None
    return values


class DebouncedInput:

    def __init__(self):
        self.value = False
        self.candidate = None
        self.changed_at = 0.0

    def update(self, value, now):
        value = bool(value)
        if self.candidate is None:

            self.value = self.candidate = value
            self.changed_at = now
            return False
        if value != self.candidate:
            self.candidate = value
            self.changed_at = now
        if self.value != self.candidate and now - self.changed_at >= DEBOUNCE_SECONDS:
            self.value = self.candidate
            return self.value
        return False


class SerialInput:

    help_lines = ()

    def __init__(self, port, baud):
        self.port = port
        self.serial = serial.Serial(port, baud, timeout=0.1)
        self.lock = threading.Lock()
        self.raw = None
        self.centers = None
        self._calibration = []
        self.draw = False
        self.hard = False
        self._submits = 0
        self._resets = 0
        self.error = None
        self.last_packet = None
        self._digital = [DebouncedInput() for _ in range(4)]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def _read_loop(self):
        pending = bytearray()
        while not self._stop.is_set():
            try:
                chunk = self.serial.read_until(b"\n", size=256)
            except (serial.SerialException, OSError) as exc:
                self.error = f"Serial error: {exc}"
                return
            if not chunk:
                continue
            pending.extend(chunk)
            if not pending.endswith(b"\n"):
                if len(pending) > 1024:
                    self.error = "Controller sent an oversized line; restart the game."
                    return
                continue
            packet = parse_csv_packet(bytes(pending))
            pending.clear()
            if packet is None:
                continue
            self._accept_packet(packet, time.monotonic())

    def _accept_packet(self, packet, now):
        x1, y1, button1, switch1, x2, y2, button2, switch2 = packet
        raw = (x1, y1, x2, y2)
        with self.lock:
            if self.last_packet is not None and now - self.last_packet > INPUT_TIMEOUT:
                self._digital = [DebouncedInput() for _ in range(4)]
                self._submits = self._resets = 0
                if self.centers is None:
                    self._calibration.clear()
            self.raw = raw
            self.last_packet = now
            edges = [control.update(value, now) for control, value in
                     zip(self._digital, (button1, switch1, button2, switch2))]
            self.draw = self._digital[1].value
            self.hard = self._digital[3].value
            if self.centers is None:
                self._calibration.append(raw)
                if len(self._calibration) >= CALIBRATION_SAMPLES:
                    self.centers = tuple(sum(c) / len(c) for c in zip(*self._calibration))
            else:
                self._submits += int(edges[0])
                self._resets += int(edges[2])

    @property
    def ready(self):
        with self.lock:
            return (not self.error and self.centers is not None
                    and self.last_packet is not None
                    and time.monotonic() - self.last_packet <= INPUT_TIMEOUT)

    def status(self):
        if self.error:
            return self.error
        if self.raw is None:
            return f"Waiting for controller on {self.port}..."
        if time.monotonic() - self.last_packet > INPUT_TIMEOUT:
            return "Controller data stopped - check the USB connection."
        return "Calibrating - don't touch the joysticks..."

    def close(self):
        self._stop.set()
        self._thread.join(timeout=1)
        self.serial.close()

    def handle_event(self, event):
        pass

    def axes(self):
        with self.lock:
            raw, centers = self.raw, self.centers
        if raw is None or centers is None:
            return ((0.0, 0.0), (0.0, 0.0))
        result = []
        for player in range(2):
            x = normalize_axis(raw[player * 2], centers[player * 2])
            y = normalize_axis(raw[player * 2 + 1], centers[player * 2 + 1])
            x, y = y, x
            if INVERT_X[player]:
                x = -x
            if INVERT_Y[player]:
                y = -y
            result.append((x, y))
        return tuple(result)

    def pop_events(self):
        with self.lock:
            submits, resets = self._submits, self._resets
            self._submits = self._resets = 0
        return submits, resets


class KeyboardInput:

    ready = True
    help_lines = (
        "P1 cursor: W A S D",
        "P2 cursor: Arrow keys",
        "SPACE: toggle draw",
        "H: toggle easy/hard",
        "ENTER: submit",
        "R: reset",
        "ESC: quit",
    )

    def __init__(self):
        self.draw = False
        self.hard = False
        self._submits = 0
        self._resets = 0

    def status(self):
        return ""

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_SPACE:
            self.draw = not self.draw
        elif event.key == pygame.K_h:
            self.hard = not self.hard
        elif event.key == pygame.K_RETURN:
            self._submits += 1
        elif event.key == pygame.K_r:
            self._resets += 1

    def axes(self):
        keys = pygame.key.get_pressed()

        def axis(neg, pos):
            return float(keys[pos]) - float(keys[neg])

        return ((axis(pygame.K_a, pygame.K_d), axis(pygame.K_w, pygame.K_s)),
                (axis(pygame.K_LEFT, pygame.K_RIGHT), axis(pygame.K_UP, pygame.K_DOWN)))

    def pop_events(self):
        submits, resets = self._submits, self._resets
        self._submits = self._resets = 0
        return submits, resets


def find_serial_port():
    patterns = ["/dev/ttyACM*", "/dev/ttyUSB*",
                "/dev/cu.usbmodem*", "/dev/cu.usbserial*", "/dev/cu.wchusbserial*"]
    for pattern in patterns:
        ports = sorted(glob.glob(pattern))
        if ports:
            return ports[0]
    return None


class Game:
    def __init__(self, controls):
        self.controls = controls
        self.cursors = [[WIDTH / 3, HEIGHT / 2], [WIDTH * 2 / 3, HEIGHT / 2]]
        self.ink = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.strokes = []
        self.current_stroke = None
        self.hard = controls.hard
        self.shape_name = None
        self.target = []
        self.result = None
        self.result_until = 0.0
        self.font = pygame.font.Font(None, 34)
        self.big_font = pygame.font.Font(None, 120)
        self.small_font = pygame.font.Font(None, 26)
        self.new_shape()


    def new_shape(self):
        shapes = HARD_SHAPES if self.hard else EASY_SHAPES
        choices = [name for name in shapes if name != self.shape_name] or list(shapes)
        self.shape_name = random.choice(choices)
        self.target = fit_to_canvas(shapes[self.shape_name]())
        self.clear_drawing()

    def clear_drawing(self):
        self.strokes = []
        self.current_stroke = None
        self.ink.fill((0, 0, 0, 0))

    def submit(self):
        self.result = score_drawing(self.target, self.strokes)
        self.result_until = time.monotonic() + RESULT_SECONDS
        self.current_stroke = None


    def midpoint(self):
        (x1, y1), (x2, y2) = self.cursors
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    def update(self, dt):
        submits, resets = self.controls.pop_events()

        if self.result is not None:
            if time.monotonic() >= self.result_until:
                self.result = None
                self.new_shape()
            return

        if self.controls.hard != self.hard:
            self.hard = self.controls.hard
            self.new_shape()
        if resets:
            self.clear_drawing()
        if submits:
            self.submit()
            return

        for cursor, (ax, ay) in zip(self.cursors, self.controls.axes()):
            cursor[0] = min(max(cursor[0] + ax * CURSOR_SPEED * dt, 0), WIDTH - 1)
            cursor[1] = min(max(cursor[1] + ay * CURSOR_SPEED * dt, 0), HEIGHT - 1)

        if not self.controls.draw:
            self.current_stroke = None
            return

        mid = self.midpoint()
        if self.current_stroke is None:
            self.current_stroke = [mid]
            self.strokes.append(self.current_stroke)
            pygame.draw.circle(self.ink, INK_COLOR, mid, 2)
        elif math.dist(mid, self.current_stroke[-1]) >= 1.0:
            last = self.current_stroke[-1]
            self.current_stroke.append(mid)
            pygame.draw.line(self.ink, INK_COLOR, last, mid, 4)
            pygame.draw.circle(self.ink, INK_COLOR, mid, 2)


    def draw(self, screen):
        screen.fill(BG)
        color = TARGET_REVEAL_COLOR if self.result else TARGET_COLOR
        for line in self.target:
            pygame.draw.lines(screen, color, False, line, 8)
            for p in line:
                pygame.draw.circle(screen, color, p, 3)
        screen.blit(self.ink, (0, 0))

        for (x, y), cursor_color in zip(self.cursors, CURSOR_COLORS):
            pygame.draw.circle(screen, cursor_color, (x, y), 11, 3)
            pygame.draw.circle(screen, cursor_color, (x, y), 2)


        self._draw_hud(screen)
        if self.result is not None:
            self._draw_result(screen)
        if not self.controls.ready:
            self._draw_banner(screen, self.controls.status())

    def _text(self, screen, text, pos, color=TEXT_COLOR, font=None, anchor="topleft"):
        surf = (font or self.font).render(text, True, color)
        rect = surf.get_rect(**{anchor: pos})
        screen.blit(surf, rect)

    def _draw_hud(self, screen):
        mode = "HARD" if self.hard else "EASY"
        self._text(screen, f"Trace: {self.shape_name}", (24, 20))
        self._text(screen, f"Mode: {mode}", (24, 54), DIM_TEXT)
        pen = "DRAW: ON" if self.controls.draw else "DRAW: OFF"
        self._text(screen, pen, (WIDTH - 24, 20),
                   INK_COLOR if self.controls.draw else DIM_TEXT, anchor="topright")
        self._text(screen, "Submit to score  -  Reset to clear", (WIDTH / 2, HEIGHT - 24),
                   DIM_TEXT, anchor="midbottom")


        line_height = 24
        top = HEIGHT - 24 - line_height * len(self.controls.help_lines)
        for i, line in enumerate(self.controls.help_lines):
            self._text(screen, line, (24, top + i * line_height), DIM_TEXT, self.small_font)

    def _draw_result(self, screen):
        score, precision, recall = self.result
        panel = pygame.Surface((520, 230), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 190))
        rect = panel.get_rect(center=(WIDTH / 2, HEIGHT / 2))
        screen.blit(panel, rect)
        self._text(screen, f"{score * 100:.0f}%", (rect.centerx, rect.top + 30),
                   INK_COLOR, self.big_font, "midtop")
        self._text(screen, f"On the lines: {precision * 100:.0f}%    Covered: {recall * 100:.0f}%",
                   (rect.centerx, rect.top + 140), TEXT_COLOR, anchor="midtop")
        self._text(screen, "Next shape coming up...", (rect.centerx, rect.top + 180),
                   DIM_TEXT, anchor="midtop")

    def _draw_banner(self, screen, message):
        panel = pygame.Surface((WIDTH, 70), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 200))
        screen.blit(panel, (0, HEIGHT / 2 - 35))
        self._text(screen, message, (WIDTH / 2, HEIGHT / 2), TEXT_COLOR, anchor="center")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", help="serial port (default: auto-detect)")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--keyboard", action="store_true", help="use keyboard instead of ESP32")
    parser.add_argument("--windowed", action="store_true", help="don't go fullscreen")
    args = parser.parse_args()

    pygame.init()
    flags = pygame.SCALED if args.windowed else pygame.SCALED | pygame.FULLSCREEN
    screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
    pygame.display.set_caption("Tracing Game")
    pygame.mouse.set_visible(False)

    if args.keyboard:
        controls = KeyboardInput()
    else:
        if serial is None:
            sys.exit("pyserial is not installed: pip install pyserial (or use --keyboard)")
        port = args.port or find_serial_port()
        if port is None:
            sys.exit("No serial port found. Plug in the ESP32 or pass --port.")
        controls = SerialInput(port, args.baud)

    try:
        game = Game(controls)
        clock = pygame.time.Clock()
        while True:
            dt = min(clock.tick(FPS) / 1000, 0.05)
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (
                        event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    return
                controls.handle_event(event)
            if controls.ready:
                game.update(dt)
            else:
                controls.pop_events()
                game.current_stroke = None
            game.draw(screen)
            pygame.display.flip()
    finally:
        if isinstance(controls, SerialInput):
            controls.close()
        pygame.quit()


if __name__ == "__main__":
    main()
