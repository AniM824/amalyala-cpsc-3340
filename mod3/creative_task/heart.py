"""
Glass Heart -- mod3 creative task client.

Listens for UDP messages from the ESP32 inside the printed heart and draws a
red glass heart (2D, shaded to look 3D) that cracks, shatters, heals and scars.

UDP messages (port 3333), one per packet:
    light,<shaded 0-2>,<drop 0-1>     photoresistors: community heals cracks and shatters
    touch,<pad1>,<pad2>,<pad3>        capacitive pads (0/1): any touch grows a shining crack
    hit,<strength 0-1>                piezo spike: shatters if too strong

Keyboard simulation (works alongside the sensors):
    A / S      hold to shade photoresistor 1 / 2
    J / K / L  hold to touch pad 1 / 2 / 3
    SPACE      hold to wind up, release to hit (longer hold = harder hit)
    H          toggle HUD
    ESC        quit

    python3 heart.py               windowed
    python3 heart.py --fullscreen  for the Pi
"""
import math
import socket
import sys
import time
from collections import deque

import numpy as np
import pygame

# ---------- SETTINGS ----------
PORT = 3333
FPS = 60
SENSOR_TIMEOUT = 0.5      # seconds before UDP readings count as stale

CRACK_DELAY = 0.3        # seconds of touch before cracks start
CRACK_SPEED = 30          # crack growth in px/s (at a 900px heart image)
MAX_CRACK_SEGS = 160      # per crack
NOISE_FLOOR = 0.05        # piezo hits below this are ignored
SHATTER_THRESHOLD = 0.35  # piezo strength that breaks an uncracked heart
HEAL_SPEED = 0.5          # shard return speed with a full crowd
CRACK_HEAL_RATE = 8       # crack segments healed per second with a full crowd
MAX_SCAR_SEGS = 400       # oldest whole scars are removed past this many segments
BASE_HEAL = 0.0           # healing with nobody around (0 = it needs people)
FACETS = 12               # facets around each ring of the cut
FACET_RINGS = [0.42, 0.75, 1.5]   # how far out each ring of points sits (1 = the edge)
FACET_TILT = [0.45, 1.0, 2.5]      # how steeply the facets in each ring lean outward

# heart-space -> image mapping (the implicit heart spans x +-1.14, y -1..1.24)
SPAN = 3.3
Y_SHIFT = 0.1

# ---------- COLORS ----------
HUD_COLOR = (230, 200, 210)
CRACK_HALO = (255, 90, 130, 60)
CRACK_MID = (255, 170, 195, 160)
CRACK_CORE = (255, 250, 250)
CRACK_LIGHT = (200, 60, 95)
SCAR_SHADOW = (70, 22, 0, 150)       # dark amber outline, sets the gold into the glass
SCAR_CORE = (215, 155, 70, 215)      # warm gold, a little see-through
SCAR_RIDGE = (255, 238, 190, 170)    # pale highlight along the top edge


def norm(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def to_surface(rgb, alpha=None):
    """float arrays in 0..1, shape (h, w, 3) and (h, w) -> pygame surface"""
    h, w = rgb.shape[:2]
    if alpha is None:
        data = np.clip(rgb * 255, 0, 255).astype(np.uint8)
        return pygame.image.frombuffer(data.tobytes(), (w, h), "RGB").convert()
    rgba = np.empty((h, w, 4), np.uint8)
    rgba[..., :3] = np.clip(np.broadcast_to(rgb, (h, w, 3)) * 255, 0, 255)
    rgba[..., 3] = np.clip(alpha * 255, 0, 255)
    return pygame.image.frombuffer(rgba.tobytes(), (w, h), "RGBA").convert_alpha()


def flat(color, shape):
    return np.broadcast_to(np.asarray(color, float), shape + (3,))


def heart_field(x, y):
    """< 0 inside the classic implicit heart curve"""
    a = x * x + y * y - 1
    return a * a * a - x * x * y * y * y


def heart_grid(n):
    j, i = np.mgrid[0:n, 0:n]
    X = (i + 0.5) / n * SPAN - SPAN / 2
    Y = SPAN / 2 - (j + 0.5) / n * SPAN + Y_SHIFT
    return X, Y


def blur_surface(surf, levels=4):
    """soft blur: shrink the image by halves, then grow it back"""
    sizes = [surf.get_width() // 2 ** k for k in range(levels + 1)]
    for size in sizes[1:]:
        surf = pygame.transform.smoothscale(surf, (size, size))
    for size in reversed(sizes[:-1]):
        surf = pygame.transform.smoothscale(surf, (size, size))
    return surf


# ---------- PRE-RENDERED GLASS ----------
class HeartImages:
    """Shades the heart once at startup: a red glass heart cut into flat facets."""

    def __init__(self, S):
        self.S = S
        X, Y = heart_grid(S)
        f = heart_field(X, Y)
        gy, gx = np.gradient(f)
        inward = -f / (np.hypot(gx, gy) + 1e-9)   # roughly how many pixels in from the edge
        mask = np.clip(0.5 + inward, 0, 1)         # 1 inside, smooth edge
        # thickness: 0 at the edge, 1 in the middle (square root makes it rise fast near the edge)
        h = np.sqrt(np.clip(inward / (0.18 * S), 0, 1))   # the middle is about 0.18*S in from the edge
        self.h = h

        # cut the heart into triangle facets like a gem: rings of points from the middle out
        # past the edge, each ring turned half a step, neighbouring rings joined into triangles
        rng = np.random.default_rng(3)
        cx, cy = S / 2, (SPAN / 2 + Y_SHIFT - 0.2) / SPAN * S   # middle of the cut, in pixels
        rings = [[(cx, cy)] * FACETS]
        for ring, t in enumerate(FACET_RINGS, 1):
            pts = []
            for k in range(FACETS):
                a = (k + 0.5 * ring) / FACETS * 2 * math.pi
                dx, dy = math.cos(a), math.sin(a)
                edge = 0.0                        # step out until we leave the heart
                while heart_field(dx * edge, 0.2 + dy * edge) < 0:
                    edge += 0.01
                r = edge * t * rng.uniform(0.94, 1.06)
                pts.append((cx + dx * r / SPAN * S, cy - dy * r / SPAN * S))   # heart units -> pixels
            rings.append(pts)
        tris, tilts = [], []
        for ring, (inner, outer) in enumerate(zip(rings, rings[1:])):
            for k in range(FACETS):
                tris.append([inner[k], outer[k], inner[(k + 1) % FACETS]])
                tris.append([outer[k], inner[(k + 1) % FACETS], outer[(k + 1) % FACETS]])
                tilts += [FACET_TILT[ring]] * 2
        # draw each triangle in its own colour (its number), then read the numbers back
        ids = pygame.Surface((S, S))
        for k, tri in enumerate(tris):
            pygame.draw.polygon(ids, (k + 1, 0, 0), tri)
        labels = np.maximum(pygame.surfarray.array3d(ids)[..., 0].T.astype(int) - 1, 0)   # 0 outside the cut

        # each facet is flat and leans outward from the middle, more in the outer rings
        fn = []
        for tri, tilt in zip(tris, tilts):
            mx = sum(p[0] for p in tri) / 3 - cx
            my = sum(p[1] for p in tri) / 3 - cy
            d = math.hypot(mx, my) + 1e-9
            tilt *= rng.uniform(0.6, 1.4)        # no two facets lean exactly the same
            fn.append(norm([mx / d * tilt + rng.normal(0, 0.15), my / d * tilt + rng.normal(0, 0.15), 1]))
        fn = np.array(fn)

        # light each facet once
        L = norm([-0.45, -0.6, 0.66])
        L2 = norm([0.5, 0.45, 0.75])
        ndl = np.clip(fn @ L, 0, 1)
        flash = np.clip((fn @ norm(L + [0, 0, 1]) - 0.96) * 25, 0, 1)            # facets facing the light flash
        flash2 = np.clip((fn @ norm(L2 + [0, 0, 1]) - 0.97) * 25, 0, 1) * 0.5
        fres = (1 - fn[:, 2]) ** 2
        side = (fn[:, 0] * L[0] + fn[:, 1] * L[1]) / np.hypot(L[0], L[1])   # +1 facing the light, -1 away
        up = np.clip(-fn[:, 1], 0, 1)                    # facets tilted up reflect the pale room
        down = np.clip(fn[:, 1], 0, 1)                   # facets tilted down glow with light coming through
        tone = 0.3 + 0.9 * ndl ** 2 + 0.15 * rng.uniform(-1, 1, len(tris))   # small per-facet variety
        fcol = tone[:, None] * [0.38, 0.015, 0.05]
        fcol = fcol + (up ** 2)[:, None] * [0.35, 0.18, 0.22]
        fcol = fcol + (down ** 1.5)[:, None] * [0.75, 0.06, 0.1]
        fcol = fcol + fres[:, None] * [0.4, 0.06, 0.12]
        fcol = fcol + (fres * np.clip(-side, 0, 1))[:, None] * [0.8, 0.25, 0.3]   # light caught on the far side
        fcol = fcol + (flash + flash2)[:, None] * [0.85, 0.75, 0.78]
        falpha = 0.62 + 0.6 * fres + flash + flash2

        # paint the facets, then the light that passes through the whole piece
        col = fcol[labels] * (0.6 + 0.4 * h)[..., None]   # thicker glass in the middle is a bit brighter
        # light refracted through the glass pools on the far side, low and to the right
        caustic = np.exp(-((X - 0.25) ** 2 + (Y + 0.3) ** 2) / 0.3) * h
        col = col + caustic[..., None] * [0.65, 0.08, 0.11]
        # light passing through: dim at the top, glowing toward the bottom
        col = col * (0.75 + 0.5 * np.clip(0.5 - Y * 0.45, 0, 1))[..., None]
        alpha = falpha[labels] + 0.25 * h

        # thin bright lines where facets meet, and around the outer edge
        lit = np.clip(0.35 + (Y - X) / SPAN, 0.15, 1)    # brighter toward the top-left
        seam = ((labels != np.roll(labels, 1, 0)) | (labels != np.roll(labels, 1, 1))).astype(float)
        seam = (2 * seam + np.roll(seam, 1, 0) + np.roll(seam, -1, 1)) / 3   # soften the pixel steps
        line = np.clip(seam * 0.45 * lit + np.exp(-np.abs(inward - 2) / 1.5) * lit, 0, 1) * mask
        col = col + line[..., None] * [1, 0.6, 0.65]
        alpha = np.clip(alpha + line, 0, 1) * mask

        self.heart = to_surface(col, alpha)

        self.aura = blur_surface(to_surface(flat([1, 0.3, 0.45], (S, S)), mask))
        aura_alpha = pygame.surfarray.pixels_alpha(self.aura)
        aura_alpha[:] = np.minimum(aura_alpha.astype(int) * 2, 255)   # stronger near the edge
        del aura_alpha
        self.mask = mask

        # glow cast on the floor and a soft contact shadow
        fw, fh = int(S * 0.62), int(S * 0.16)
        fj, fi = np.mgrid[0:fh, 0:fw]
        e = ((fi - fw / 2) / (fw / 2)) ** 2 + ((fj - fh / 2) / (fh / 2)) ** 2
        self.floor_glow = to_surface(flat([0.9, 0.1, 0.2], (fh, fw)), np.exp(-e * 3) * 0.45)
        self.floor_shadow = to_surface(flat([0, 0, 0], (fh, fw)), np.exp(-e * 7) * 0.6)

    def depth(self, x, y):
        """glass thickness (0 at the edge, 1 in the middle) at pixel x, y"""
        return self.h[int(y), int(x)]

    def inside(self, p, depth=0.3):
        """is the point on the glass, at least a little way in from the edge"""
        x, y = p
        return 0 <= x < self.S and 0 <= y < self.S and self.depth(x, y) > depth


def build_background(W, H):
    yy, xx = np.mgrid[0:H, 0:W]
    t = (yy / H)[..., None]
    col = np.array([0.075, 0.03, 0.055]) * (1 - t) + np.array([0.02, 0.012, 0.022]) * t
    d = np.hypot((xx - W / 2) / W, (yy - H * 0.45) / H)
    col = col + np.exp(-d ** 2 / 0.05)[..., None] * [0.09, 0.02, 0.04]
    col = col * (1 - 0.6 * np.clip(d * 1.3 - 0.25, 0, 1))[..., None]
    return to_surface(col)


# ---------- CRACKS ----------
class Crack:
    """Branching random walk that stays inside the glass."""

    def __init__(self, origin, rng, images, scale):
        self.rng = rng
        self.images = images
        self.step = 7 * scale
        self.segs = []   # (start, end, width)
        self.tips = []   # [pos, angle, width]
        self.budget = 0.0
        base = rng.uniform(0, 2 * math.pi)
        n = int(rng.integers(2, 5))
        for k in range(n):
            angle = base + k * 2 * math.pi / n + rng.normal(0, 0.3)
            self.tips.append([origin.copy(), angle, 2.0])

    def grow(self, distance):
        rng = self.rng
        self.budget += distance
        while self.budget >= self.step:
            self.budget -= self.step
            if len(self.segs) >= MAX_CRACK_SEGS:
                self.budget = 0
                return
            if not self.tips:
                if not self.segs:
                    return
                # stress reopens the crack from a random point along it
                _, end, _ = self.segs[int(rng.integers(len(self.segs)))]
                self.tips.append([end.copy(), rng.uniform(0, 2 * math.pi), 1.0])
            k = int(rng.integers(len(self.tips)))
            tip = self.tips[k]
            tip[1] += rng.normal(0, 0.32)
            length = self.step * rng.uniform(0.7, 1.4)
            new = tip[0] + length * np.array([math.cos(tip[1]), math.sin(tip[1])])
            if not self.images.inside(new):
                self.tips.pop(k)
                continue
            self.segs.append((tip[0], new, tip[2]))
            tip[0] = new
            if rng.random() < 0.13 and len(self.tips) < 7:
                turn = rng.choice([-1, 1]) * rng.uniform(0.45, 1.0)
                self.tips.append([new.copy(), tip[1] + turn, max(1.0, tip[2] - 1)])
            elif rng.random() < 0.02:
                tip[2] = max(1.0, tip[2] - 1)


# ---------- SHARDS ----------
class Shard:
    def __init__(self, surf, home, rng):
        self.surf = surf
        self.home = home
        self.pos = home.copy()
        self.vel = np.zeros(2)
        self.angle = 0.0
        self.spin = 0.0
        self.locked = False
        self.eager = rng.uniform(0.6, 1.4)   # some shards come home sooner
        self.phase = rng.uniform(0, 2 * math.pi)


class GlassHeart:
    def __init__(self, fullscreen=False):
        pygame.init()
        if fullscreen:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            pygame.mouse.set_visible(False)
        else:
            self.screen = pygame.display.set_mode((1100, 850))
        pygame.display.set_caption("Glass Heart")
        self.W, self.H = self.screen.get_size()
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 24)
        self.rng = np.random.default_rng()

        self.S = int(min(self.W, self.H) * 0.92)
        self.scale = self.S / 900
        self.images = HeartImages(self.S)
        self.background = build_background(self.W, self.H)
        self.ox = self.W / 2 - self.S / 2
        self.oy = self.H * 0.47 - self.S * 0.494

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock.bind(("0.0.0.0", PORT))
            self.sock.setblocking(False)
        except OSError as e:
            print(f"UDP port {PORT} unavailable ({e}); keyboard only")
            self.sock = None

        # sensor readings
        self.udp_light = (0, 0.0)
        self.udp_light_t = -1.0
        self.udp_touch = [False] * 3
        self.udp_touch_t = -1.0
        self.udp_seen = -1.0
        self.shaded, self.drop = 0, 0.0
        self.touched = [False] * 3
        self.touch_since = None
        self.charge_start = None
        self.last_hit = None

        # heart state
        self.cracks = []
        self.growing = None        # the crack the current touch is growing
        self.cracks_dirty = True
        self.crack_light = None
        self.cracks_drawn = 0.0
        self.mend_budget = 0.0
        self.shards = None
        self.heal = 0.0
        self.glow = 0.0
        self.shake = 0.0
        self.shatter_cracks = []   # touch cracks carried by the shards, scarred on reassembly
        self.state = "INTACT"
        self.show_hud = True
        self.running = True

        self.scars = deque()       # one list of segments per scar, oldest first
        self.scar_segs = 0
        self.crack_surf = pygame.Surface((self.S, self.S), pygame.SRCALPHA)
        self.scar_surf = pygame.Surface((self.S, self.S), pygame.SRCALPHA)

    # ---------- SCARS ----------
    def draw_scar(self, a, b, w):
        # gold seam (like kintsugi) with a highlight catching the light
        pygame.draw.line(self.scar_surf, SCAR_SHADOW, a, b, 3 if w > 1 else 2)
        pygame.draw.line(self.scar_surf, SCAR_CORE, a, b, 2 if w > 1 else 1)
        pygame.draw.aaline(self.scar_surf, SCAR_RIDGE, a - 1, b - 1)

    def add_scar(self, scar, seg):
        """turn one crack segment into scar tissue, evicting the oldest scars past the cap"""
        if not any(s is scar for s in self.scars):
            self.scars.append(scar)
        scar.append(seg)
        self.scar_segs += 1
        self.draw_scar(*seg)
        if self.scar_segs > MAX_SCAR_SEGS and len(self.scars) > 1:
            while self.scar_segs > MAX_SCAR_SEGS and len(self.scars) > 1:
                old = self.scars.popleft()
                self.scar_segs -= len(old)
                old.clear()
            self.scar_surf.fill((0, 0, 0, 0))
            for old in self.scars:
                for old_seg in old:
                    self.draw_scar(*old_seg)

    # ---------- INPUT ----------
    def handle_events(self, now):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_h:
                    self.show_hud = not self.show_hud
                elif event.key == pygame.K_SPACE:
                    self.charge_start = now
            elif event.type == pygame.KEYUP and event.key == pygame.K_SPACE and self.charge_start:
                self.hit(min(1.0, (now - self.charge_start) / 1.2) ** 0.8, now)
                self.charge_start = None

    def poll_udp(self, now):
        while self.sock:
            try:
                data, _ = self.sock.recvfrom(1024)
            except (BlockingIOError, OSError):
                break
            self.udp_seen = now
            for line in data.decode(errors="ignore").split():
                self.parse(line, now)

    def parse(self, line, now):
        parts = line.strip().split(",")
        try:
            kind = parts[0].lower()
            if kind == "light" and len(parts) >= 3:
                self.udp_light = (int(float(parts[1])), float(parts[2]))
                self.udp_light_t = now
            elif kind == "touch" and len(parts) >= 2:
                vals = [float(p) != 0 for p in parts[1:4]]
                self.udp_touch = (vals + [False] * 3)[:3]
                self.udp_touch_t = now
            elif kind == "hit" and len(parts) >= 2:
                self.hit(float(parts[1]), now)
        except ValueError:
            pass

    def read_sensors(self, now):
        keys = pygame.key.get_pressed()
        sim_shaded = int(keys[pygame.K_a]) + int(keys[pygame.K_s])
        light_fresh = now - self.udp_light_t < SENSOR_TIMEOUT
        udp_shaded, udp_drop = self.udp_light if light_fresh else (0, 0.0)
        self.shaded = min(2, udp_shaded + sim_shaded)
        self.drop = max(udp_drop, 0.3 * sim_shaded)

        touch_fresh = now - self.udp_touch_t < SENSOR_TIMEOUT
        sim_touch = [keys[pygame.K_j], keys[pygame.K_k], keys[pygame.K_l]]
        self.touched = [bool(s) or (touch_fresh and u) for s, u in zip(sim_touch, self.udp_touch)]

    # ---------- EVENTS ----------
    def hit(self, strength, now):
        strength = max(0.0, min(1.0, strength))
        if strength < NOISE_FLOOR:
            return
        self.last_hit = (strength, now)
        self.shake = max(self.shake, strength)
        if self.shards:
            self.launch(strength)
            return
        # a cracked heart is a weaker heart
        load = min(1.0, sum(len(c.segs) for c in self.cracks) / 300)
        if strength >= SHATTER_THRESHOLD * (1 - 0.35 * load):
            self.shatter(strength)
        elif self.cracks:
            for c in self.cracks:
                c.grow(strength * 60 * self.scale)
            self.cracks_dirty = True

    def shatter(self, strength):
        S, rng, img = self.S, self.rng, self.images

        # touch cracks ride along on the shards and become scars once it heals
        self.shatter_cracks += [c.segs for c in self.cracks if c.segs]

        ys, xs = np.nonzero(img.mask > 0.02)
        pts = np.stack([xs, ys], 1).astype(np.float32)

        # random seed points over the glass; a harder hit breaks it into more pieces
        seeds = pts[rng.choice(len(pts), int(18 + 50 * strength))]

        # each pixel of glass belongs to its nearest seed (a Voronoi pattern)
        best = np.full(len(pts), np.inf)
        labels = np.zeros(len(pts), int)
        for k, seed in enumerate(seeds):
            d = ((pts - seed) ** 2).sum(1)
            closer = d < best
            best[closer] = d[closer]
            labels[closer] = k
        label_img = np.full((S, S), -1)
        label_img[ys, xs] = labels

        # bake the current look (scars, shining cracks) into the glass
        comp = img.heart.copy()
        comp.blit(self.scar_surf, (0, 0))
        if self.cracks:
            self.render_cracks()
            comp.blit(self.crack_surf, (0, 0))
        rgb = pygame.surfarray.array3d(comp).transpose(1, 0, 2).astype(np.float32)
        alpha = pygame.surfarray.array_alpha(comp).T.astype(np.float32)

        # light catches the freshly cut edges
        edge = np.zeros((S, S), bool)
        edge[:, :-1] |= label_img[:, :-1] != label_img[:, 1:]
        edge[:-1, :] |= label_img[:-1, :] != label_img[1:, :]
        edge &= img.mask > 0.5
        rgb[edge] = rgb[edge] * 0.4 + 255 * 0.6
        alpha[edge] = np.maximum(alpha[edge], 230)

        self.shards = []
        for k in range(len(seeds)):
            sy, sx = ys[labels == k], xs[labels == k]
            if len(sy) < 4:
                continue
            y0, x0 = sy.min(), sx.min()
            h, w = sy.max() - y0 + 1, sx.max() - x0 + 1
            rgba = np.zeros((h, w, 4), np.uint8)
            rgba[sy - y0, sx - x0, :3] = np.clip(rgb[sy, sx], 0, 255)
            rgba[sy - y0, sx - x0, 3] = np.clip(alpha[sy, sx], 0, 255)
            surf = pygame.image.frombuffer(rgba.tobytes(), (w, h), "RGBA").convert_alpha()
            self.shards.append(Shard(surf, np.array([x0 + w / 2, y0 + h / 2]), rng))

        self.cracks.clear()
        self.growing = None
        self.cracks_dirty = True
        self.launch(strength)

    def launch(self, strength):
        # every shard flies outward from the middle of the heart
        rng = self.rng
        middle = np.array([self.S / 2, self.S / 2])
        for sh in self.shards:
            d = sh.pos - middle
            speed = (150 + 600 * strength) * self.scale * rng.uniform(0.5, 1.2)
            sh.vel += d / (np.linalg.norm(d) + 1e-6) * speed + rng.normal(0, 60 * self.scale, 2)
            sh.spin += rng.normal(0, 90 + 400 * strength)
            sh.locked = False

    # ---------- UPDATE ----------
    def update(self, dt, now):
        community = 0.75 * self.shaded / 2 + 0.25 * self.drop
        self.heal = BASE_HEAL + community * (1 + community)   # a crowd heals faster than one

        if self.shards:
            self.update_shards(dt)
            self.state = "HEALING" if self.heal > 0 else "SHATTERED"
        else:
            self.update_touch(dt, now)
            self.mend_cracks(dt, now)

        self.shake *= math.exp(-dt * 6)

    def update_touch(self, dt, now):
        # any pad counts as a touch: one crack grows from a random spot while it's held
        cracking = False
        if not any(self.touched):
            self.touch_since = None
            self.growing = None
        else:
            if self.touch_since is None:
                self.touch_since = now
            if now - self.touch_since > CRACK_DELAY:
                cracking = True
                if self.growing not in self.cracks:
                    origin = self.rng.uniform(0, self.S, 2)
                    while not self.images.inside(origin):   # keep picking until it lands on the glass
                        origin = self.rng.uniform(0, self.S, 2)
                    self.growing = Crack(origin, self.rng, self.images, self.scale)
                    self.cracks.append(self.growing)
                self.growing.grow(dt * CRACK_SPEED * self.scale)
                self.cracks_dirty = True

        # glow eases toward 1 while touched, back to 0 when let go
        target = 1.0 if any(self.touched) else 0.0
        self.glow += (target - self.glow) * min(1.0, dt * 4)

        if cracking:
            self.state = "CRACKING"
        elif any(self.touched):
            self.state = "GLOWING"
        else:
            self.state = "INTACT"

    def mend_cracks(self, dt, now):
        # community closes the oldest crack without a trace, from where it started outward
        mending = [c for c in self.cracks if c.segs]
        if not mending or self.heal <= 0:
            self.mend_budget = 0.0
            return
        self.mend_budget += dt * CRACK_HEAL_RATE * self.heal
        while self.mend_budget >= 1 and mending:
            self.mend_budget -= 1
            c = mending[0]
            c.segs.pop(0)
            if not c.segs:
                mending.pop(0)
                if c is not self.growing:
                    self.cracks.remove(c)
            self.cracks_dirty = True

    def update_shards(self, dt):
        heal = self.heal
        lo = np.array([-self.ox, -self.oy])
        hi = np.array([self.W - self.ox, self.H - self.oy])
        for sh in self.shards:
            if sh.locked:
                continue
            sh.pos += sh.vel * dt
            sh.angle += sh.spin * dt
            sh.vel *= 1 - min(1.0, dt * (1.6 + 8 * heal))   # drag, stronger while healing
            sh.spin *= 1 - min(1.0, dt * (1.2 + 8 * heal))

            # bounce off the screen edges
            m = max(sh.surf.get_size()) / 2
            for ax in range(2):
                if sh.pos[ax] < lo[ax] + m:
                    sh.pos[ax] = lo[ax] + m
                    sh.vel[ax] = abs(sh.vel[ax]) * 0.5
                elif sh.pos[ax] > hi[ax] - m:
                    sh.pos[ax] = hi[ax] - m
                    sh.vel[ax] = -abs(sh.vel[ax]) * 0.5

            if heal > 0:
                # ease a fraction of the way home (and upright) every frame
                k = min(1.0, dt * HEAL_SPEED * heal * sh.eager)
                sh.pos += (sh.home - sh.pos) * k
                sh.angle = (sh.angle + 180) % 360 - 180
                sh.angle -= sh.angle * k
                if np.linalg.norm(sh.home - sh.pos) < 1.5 and abs(sh.angle) < 1:
                    sh.pos = sh.home.copy()
                    sh.angle = 0.0
                    sh.vel[:] = 0
                    sh.spin = 0.0
                    sh.locked = True

        if all(sh.locked for sh in self.shards):
            # the fractures close without a trace; the touch cracks become scars
            self.shards = None
            for segs in self.shatter_cracks:
                scar = []
                for seg in segs:
                    self.add_scar(scar, seg)
            self.shatter_cracks = []
            self.glow = 0.0
            self.state = "INTACT"

    # ---------- DRAW ----------
    def render_cracks(self):
        surf = self.crack_surf
        surf.fill((0, 0, 0, 0))
        segs = [s for c in self.cracks for s in c.segs]
        sc = self.scale
        for a, b, w in segs:
            pygame.draw.line(surf, CRACK_HALO, a, b, max(1, round((w + 5) * sc)))
        for a, b, w in segs:
            pygame.draw.line(surf, CRACK_MID, a, b, max(1, round((w + 1) * sc)))
        for a, b, _ in segs:
            pygame.draw.aaline(surf, CRACK_CORE, a, b)
        # light pouring out of the cracks: thick strokes, blurred, then brightened
        light = pygame.Surface((self.S, self.S))
        for a, b, w in segs:
            pygame.draw.line(light, CRACK_LIGHT, a, b, max(3, round((w + 6) * sc)))
        light = blur_surface(light)
        light.blit(light, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        light.blit(light, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        self.crack_light = light
        self.cracks_dirty = False

    def draw(self, now):
        img, scr = self.images, self.screen
        scr.blit(self.background, (0, 0))

        bob = math.sin(now * 0.9) * 0.006 * self.S
        jitter = self.rng.normal(0, self.shake * 10 * self.scale, 2) if self.shake > 0.02 else (0, 0)
        ox, oy = self.ox + jitter[0], self.oy + bob + jitter[1]
        beat = 0.5 + 0.5 * math.sin(now * 5)    # slow pulse

        # floor light and shadow
        fw, fh = img.floor_glow.get_size()
        fx, fy = self.W / 2 - fw / 2, self.oy + 0.86 * self.S - fh / 2
        whole = 0.35 if self.shards else 1.0
        img.floor_shadow.set_alpha(int(220 * whole))
        scr.blit(img.floor_shadow, (fx, fy))
        img.floor_glow.set_alpha(int((120 + 60 * beat) * whole))
        scr.blit(img.floor_glow, (fx, fy))

        img.aura.set_alpha(int((15 + 20 * beat) if self.shards else (30 + 25 * beat)))
        scr.blit(img.aura, (ox, oy))

        if self.shards:
            self.draw_shards(ox, oy, now)
        else:
            scr.blit(img.heart, (ox, oy))
            if self.scars:
                scr.blit(self.scar_surf, (ox, oy))
            if self.cracks:
                if self.crack_light is None or (self.cracks_dirty and now - self.cracks_drawn > 0.08):
                    self.render_cracks()
                    self.cracks_drawn = now
                # touch makes the cracks shine (pulsing); the rest of the glass stays dark
                v = int(255 * (0.3 + 0.7 * self.glow) * (0.8 + 0.2 * beat))
                light = self.crack_light.copy()
                light.fill((v, v, v), special_flags=pygame.BLEND_RGB_MULT)
                scr.blit(light, (ox, oy), special_flags=pygame.BLEND_RGB_ADD)
                self.crack_surf.set_alpha(int(255 * min(1.0, 0.6 + 0.4 * self.glow)))
                scr.blit(self.crack_surf, (ox, oy))
                if self.glow > 0.05:   # white-hot cores while touched
                    scr.blit(self.crack_surf, (ox, oy), special_flags=pygame.BLEND_RGB_ADD)

        if self.show_hud:
            self.draw_hud(now)

    def draw_shards(self, ox, oy, now):
        for sh in self.shards:
            x, y = sh.pos
            if not sh.locked:
                y += math.sin(now * 0.7 + sh.phase) * 3 * self.scale
            surf = sh.surf if abs(sh.angle) < 0.5 else pygame.transform.rotozoom(sh.surf, sh.angle, 1)
            rect = surf.get_rect(center=(ox + x, oy + y))
            self.screen.blit(surf, rect)

    def draw_hud(self, now):
        udp = "live" if now - self.udp_seen < SENSOR_TIMEOUT else "none"
        dots = " ".join("#" if t else "." for t in self.touched)
        held = now - self.touch_since if self.touch_since is not None else 0.0
        hit = "-"
        if self.last_hit:
            hit = f"{self.last_hit[0]:.2f} ({now - self.last_hit[1]:.0f}s ago)"
        lines = [
            f"{self.state}   heal x{self.heal:.2f}",
            f"light  shaded {self.shaded}/2  drop {self.drop:.2f}",
            f"touch  {dots}  held {held:.1f}s",
            f"hit    {hit}",
            f"scars  {len(self.scars)} ({self.scar_segs}/{MAX_SCAR_SEGS} segs)   udp {udp}",
        ]
        if self.charge_start:
            charge = min(1.0, (now - self.charge_start) / 1.2) ** 0.8
            lines.append("wind-up " + "|" * int(charge * 30))
        lines.append("A/S shade  J/K/L touch  SPACE hit  H hud")
        y = self.H - 14 - 22 * len(lines)
        for line in lines:
            self.screen.blit(self.font.render(line, True, HUD_COLOR), (14, y))
            y += 22

    def step(self, dt, now):
        self.handle_events(now)
        self.poll_udp(now)
        self.read_sensors(now)
        self.update(dt, now)
        self.draw(now)

    def run(self):
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000, 0.05)
            self.step(dt, time.monotonic())
            pygame.display.flip()
        pygame.quit()


if __name__ == "__main__":
    GlassHeart(fullscreen="--fullscreen" in sys.argv).run()
