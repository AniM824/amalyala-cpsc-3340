import random
import sys

import pygame
from gpiozero import Button, DigitalInputDevice

W, H = 800, 480
GROUND = H - 80
FPS = 30
MODES = ["SUNNY", "SNOWY", "RAINY", "WINDY", "CLOUDY"]

press_count = 0


def on_press():
    global press_count
    press_count += 1


class Sunny:
    def __init__(self):
        self.weeds = []

    def trigger(self):
        self.weeds.append(-30)

    def update(self, intense):
        if intense:
            speed = 12
        else:
            speed = 6
        self.weeds = [x + speed for x in self.weeds if x < W + 30]

    def draw(self, s, intense):
        if intense:
            s.fill((255, 150, 60))
            sun_radius = 80
        else:
            s.fill((110, 180, 240))
            sun_radius = 50
        pygame.draw.circle(s, (255, 220, 60), (W - 130, 100), sun_radius)
        pygame.draw.rect(s, (235, 195, 125), (0, GROUND, W, H - GROUND))
        for x in self.weeds:
            pygame.draw.circle(s, (140, 100, 50), (x, GROUND - 20), 20, 4)


def hill_y(x):
    return 180 + (H - 240) * x / W


class Snowy:
    def __init__(self):
        self.flakes = []
        self.balls = []

    def trigger(self):
        self.balls.append(0)

    def update(self, intense):
        if intense:
            new_flakes = 4
            speed = 5
        else:
            new_flakes = 1
            speed = 2
        for _ in range(new_flakes):
            self.flakes.append([random.randint(0, W), 0])
        for f in self.flakes:
            f[1] += speed
        self.flakes = [f for f in self.flakes if f[1] < H]
        self.balls = [x + 5 for x in self.balls if x < W + 30]

    def draw(self, s, intense):
        if intense:
            s.fill((150, 155, 170))
        else:
            s.fill((60, 80, 130))
        pygame.draw.polygon(s, (245, 245, 255), [(0, hill_y(0)), (W, hill_y(W)), (W, H), (0, H)])
        for x in self.balls:
            center = (x, int(hill_y(x)) - 20)
            pygame.draw.circle(s, (255, 255, 255), center, 20)
            pygame.draw.circle(s, (160, 170, 190), center, 20, 2)
        for x, y in self.flakes:
            pygame.draw.circle(s, (255, 255, 255), (x, y), 2)


class Rainy:
    def __init__(self):
        self.drops = []
        self.bolt_frames = 0
        self.bolt_x = 0

    def trigger(self):
        self.bolt_frames = 10
        self.bolt_x = random.randint(100, W - 100)

    def update(self, intense):
        if intense:
            new_drops = 8
            speed = 14
        else:
            new_drops = 2
            speed = 9
        for _ in range(new_drops):
            self.drops.append([random.randint(0, W), 0])
        for d in self.drops:
            d[1] += speed
        self.drops = [d for d in self.drops if d[1] < GROUND]
        if self.bolt_frames > 0:
            self.bolt_frames -= 1

    def draw(self, s, intense):
        if intense:
            s.fill((50, 55, 65))
        else:
            s.fill((120, 130, 145))
        pygame.draw.rect(s, (60, 75, 60), (0, GROUND, W, H - GROUND))
        for x, y in self.drops:
            pygame.draw.line(s, (170, 190, 230), (x, y), (x, y + 12), 1)
        if self.bolt_frames > 0:
            x = self.bolt_x
            bolt = [(x, 0), (x - 30, 120), (x + 20, 120), (x - 20, 260), (x + 10, 260), (x - 10, GROUND)]
            pygame.draw.lines(s, (255, 230, 80), False, bolt, 6)


class Windy:
    def __init__(self):
        self.streaks = []
        self.tornado = None

    def trigger(self):
        if self.tornado is None:
            self.tornado = -60

    def update(self, intense):
        if intense:
            spawn_chance = 0.8
            speed = 25
        else:
            spawn_chance = 0.25
            speed = 10
        if random.random() < spawn_chance:
            self.streaks.append([-100, random.randint(20, GROUND - 20)])
        for st in self.streaks:
            st[0] += speed
        self.streaks = [st for st in self.streaks if st[0] < W]
        if self.tornado is not None:
            self.tornado += 4
            if self.tornado > W + 60:
                self.tornado = None

    def draw(self, s, intense):
        if intense:
            s.fill((130, 150, 170))
        else:
            s.fill((160, 210, 245))
        pygame.draw.rect(s, (90, 160, 70), (0, GROUND, W, H - GROUND))
        for x, y in self.streaks:
            pygame.draw.line(s, (255, 255, 255), (x, y), (x + 80, y), 2)
        if self.tornado is not None:
            x = self.tornado
            pygame.draw.polygon(s, (100, 100, 110), [(x - 60, GROUND - 250), (x + 60, GROUND - 250), (x, GROUND)])


class Cloudy:
    def __init__(self):
        self.clouds = [[random.randint(0, W), random.randint(40, 250)] for _ in range(8)]
        self.sun_frames = 0

    def trigger(self):
        self.sun_frames = 90

    def update(self, intense):
        if intense:
            speed = 2
        else:
            speed = 1
        for c in self.clouds:
            c[0] += speed
            if c[0] > W + 80:
                c[0] = -80
        if self.sun_frames > 0:
            self.sun_frames -= 1

    def draw(self, s, intense):
        if self.sun_frames > 0:
            s.fill((130, 190, 250))
            pygame.draw.circle(s, (255, 220, 60), (W // 2, 100), 60)
        elif intense:
            s.fill((90, 95, 105))
        else:
            s.fill((170, 180, 195))
        if intense:
            color = (120, 120, 130)
            cloud_count = 8
        else:
            color = (240, 240, 245)
            cloud_count = 4
        for x, y in self.clouds[:cloud_count]:
            for dx, r in [(0, 30), (35, 40), (70, 30)]:
                pygame.draw.circle(s, color, (x + dx, y), r)
        pygame.draw.rect(s, (100, 125, 100), (0, GROUND, W, H - GROUND))


SCENES = [Sunny, Snowy, Rainy, Windy, Cloudy]


def draw_text(s, font, text, y):
    img = font.render(text, True, (255, 255, 255))
    s.blit(img, img.get_rect(center=(W // 2, y)))


def main():
    global press_count

    button = Button(14, bounce_time=0.05)
    switch = Button(15, bounce_time=0.05)
    vry = DigitalInputDevice(21, pull_up=None, active_state=False)
    button.when_pressed = on_press

    pygame.init()
    if "--fullscreen" in sys.argv:
        screen = pygame.display.set_mode((W, H), pygame.FULLSCREEN)
    else:
        screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Weather Machine")
    clock = pygame.time.Clock()
    big = pygame.font.SysFont(None, 110)
    small = pygame.font.SysFont(None, 36)

    mode = 0
    scene = SCENES[mode]()
    held_frames = 0

    while True:
        pygame.event.pump()

        presses = press_count
        press_count = 0
        selecting = switch.is_pressed

        if vry.is_active:
            held_frames += 1
        else:
            held_frames = 0
        intense = held_frames >= 3 and not selecting

        if selecting:
            if presses > 0:
                mode = (mode + presses) % len(MODES)
                scene = SCENES[mode]()
        else:
            for _ in range(presses):
                scene.trigger()
        scene.update(intense)

        if selecting:
            screen.fill((0, 0, 0))
            draw_text(screen, small, f"MODE SELECT  {mode + 1}/{len(MODES)}", H // 2 - 80)
            draw_text(screen, big, MODES[mode], H // 2)
            draw_text(screen, small, "press button to change, flip switch to play", H // 2 + 80)
        else:
            scene.draw(screen, intense)
            if intense:
                status = "INTENSE"
            else:
                status = "CALM"
            label = small.render(f"{MODES[mode]}  -  {status}", True, (255, 255, 255))
            screen.blit(label, (20, 16))

        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()
