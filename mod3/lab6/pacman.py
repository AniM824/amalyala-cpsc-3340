import pygame
import socket
import math

# ---------- SETTINGS ----------
PORT = 3333
MIN_LIGHT = 800
MAX_LIGHT = 2600

TILE = 32
FPS = 60
MOVE_DELAY = 0.12  # Seconds per tile

# # = wall, . = coin, P = starting position
MAZE = [
    "###################",
    "#P................#",
    "#.###.###.###.###.#",
    "#...#...#...#.....#",
    "###.#.#.#.#.#.###.#",
    "#...#.#...#.#.....#",
    "#.###.#####.###.#.#",
    "#.....#.....#...#.#",
    "#.###.#.###.#.###.#",
    "#...#...#...#.....#",
    "###.#####.#.###.#.#",
    "#.........#.......#",
    "###################",
]

ROWS = len(MAZE)
COLS = len(MAZE[0])

# ---------- COLORS ----------
BLACK = (8, 8, 20)
BLUE = (35, 65, 220)
YELLOW = (255, 220, 0)
WHITE = (240, 240, 240)
COIN = (255, 190, 80)

# ---------- SETUP ----------
pygame.init()

screen = pygame.display.set_mode(
    (COLS * TILE, ROWS * TILE + 70)
)
pygame.display.set_caption("Photoresistor Pac-Man")

clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 26)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", PORT))
sock.setblocking(False)

DIRECTIONS = {
    "UP": (0, -1),
    "RIGHT": (1, 0),
    "DOWN": (0, 1),
    "LEFT": (-1, 0),
}

ANGLES = {
    "RIGHT": 0,
    "DOWN": 90,
    "LEFT": 180,
    "UP": 270,
}


def direction_from_light(value):
    value = max(MIN_LIGHT, min(MAX_LIGHT, value))

    if value < 1250:
        return "UP"
    elif value < 1700:
        return "RIGHT"
    elif value < 2150:
        return "DOWN"
    else:
        return "LEFT"


def reset_game():
    global walls, coins, pacman, direction, desired_direction
    global score, move_timer

    walls = set()
    coins = set()

    for y, row in enumerate(MAZE):
        for x, cell in enumerate(row):
            if cell == "#":
                walls.add((x, y))
            elif cell == ".":
                coins.add((x, y))
            elif cell == "P":
                pacman = (x, y)

    direction = "RIGHT"
    desired_direction = "RIGHT"
    score = 0
    move_timer = 0


def can_move(position, direction_name):
    dx, dy = DIRECTIONS[direction_name]
    next_position = (position[0] + dx, position[1] + dy)
    return next_position not in walls


reset_game()

light = 1500
source = "Keyboard"
running = True
elapsed = 0

while running:
    dt = clock.tick(FPS) / 1000.0
    elapsed += dt
    move_timer += dt

    # ---------- EVENTS ----------
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False

            elif event.key == pygame.K_r:
                reset_game()

            elif event.key == pygame.K_UP:
                desired_direction = "UP"
                source = "Keyboard"

            elif event.key == pygame.K_RIGHT:
                desired_direction = "RIGHT"
                source = "Keyboard"

            elif event.key == pygame.K_DOWN:
                desired_direction = "DOWN"
                source = "Keyboard"

            elif event.key == pygame.K_LEFT:
                desired_direction = "LEFT"
                source = "Keyboard"

    # ---------- UDP ----------
    while True:
        try:
            data, addr = sock.recvfrom(1024)
        except BlockingIOError:
            break

        print(f"Packet from {addr}: {data!r}", flush=True)

        try:
            light = int(data.decode().strip())
            desired_direction = direction_from_light(light)
            source = "ESP32 / UDP"
            print(f"Light: {light} -> {desired_direction}", flush=True)
        except ValueError:
            pass

    # ---------- MOVEMENT ----------
    if move_timer >= MOVE_DELAY and coins:
        move_timer -= MOVE_DELAY

        # Turn if the requested direction is available
        if can_move(pacman, desired_direction):
            direction = desired_direction

        # Otherwise continue moving in current direction
        if can_move(pacman, direction):
            dx, dy = DIRECTIONS[direction]
            pacman = (pacman[0] + dx, pacman[1] + dy)

        # Collect coins
        if pacman in coins:
            coins.remove(pacman)
            score += 10

    # ---------- DRAW ----------
    screen.fill(BLACK)

    # Walls
    for x, y in walls:
        rect = pygame.Rect(
            x * TILE + 2,
            y * TILE + 2,
            TILE - 4,
            TILE - 4
        )
        pygame.draw.rect(screen, BLUE, rect, border_radius=6)

    # Coins
    for x, y in coins:
        pygame.draw.circle(
            screen,
            COIN,
            (x * TILE + TILE // 2, y * TILE + TILE // 2),
            4
        )

    # Pac-Man
    px = pacman[0] * TILE + TILE // 2
    py = pacman[1] * TILE + TILE // 2

    radius = TILE // 2 - 3

    mouth = 15 + abs(math.sin(elapsed * 12)) * 25
    facing = ANGLES[direction]

    # Draw Pac-Man as a circle with a triangular mouth cutout
    pygame.draw.circle(screen, YELLOW, (px, py), radius)

    angle1 = math.radians(facing - mouth)
    angle2 = math.radians(facing + mouth)

    mouth_points = [
        (px, py),
        (
            px + math.cos(angle1) * (radius + 2),
            py + math.sin(angle1) * (radius + 2),
        ),
        (
            px + math.cos(angle2) * (radius + 2),
            py + math.sin(angle2) * (radius + 2),
        ),
    ]

    pygame.draw.polygon(screen, BLACK, mouth_points)

    # ---------- HUD ----------
    hud_y = ROWS * TILE + 10

    status = (
        f"Score: {score}   "
        f"Light: {light}   "
        f"Direction: {desired_direction}   "
        f"Source: {source}"
    )

    screen.blit(
        font.render(status, True, WHITE),
        (10, hud_y)
    )

    instructions = "Arrow keys: test | R: restart | ESC: quit"

    if not coins:
        instructions = "YOU WIN! Press R to restart"

    screen.blit(
        font.render(instructions, True, WHITE),
        (10, hud_y + 30)
    )

    pygame.display.flip()

sock.close()
pygame.quit()
