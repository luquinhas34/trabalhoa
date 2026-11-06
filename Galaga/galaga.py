"""
Galaga - clone feito com Pygame.

Controles:
  Setas ESQ/DIR ou A/D ... mover a nave
  ESPACO .................. atirar (maximo 2 tiros na tela)
  ENTER ................... iniciar / reiniciar
  P ....................... pausar
  ESC ..................... sair

Todos os sprites sao desenhados em codigo (pixel art), sem arquivos externos.
Se quiser usar sprites do spriters-resource.com, veja a funcao `build_sprites`.
"""
import math
import random
import sys
from array import array

import pygame

# ----------------------------------------------------------------------------
# Configuracoes
# ----------------------------------------------------------------------------
W, H = 224, 288            # resolucao logica (igual ao arcade original)
SCALE = 2                  # tamanho da janela = logica * SCALE
FPS = 60
HIGHSCORE_FILE = "highscore.txt"

COLORS = {
    "W": (240, 240, 240), "R": (230, 50, 50), "B": (50, 90, 240),
    "Y": (250, 220, 40), "G": (60, 220, 90), "P": (200, 70, 220),
    "C": (60, 220, 230), "O": (250, 140, 30), "K": (20, 20, 40),
}


# ----------------------------------------------------------------------------
# Sprites (pixel art espelhada: cada linha tem metade + coluna central)
# ----------------------------------------------------------------------------
def make_sprite(half_rows, palette_swap=None):
    h = len(half_rows)
    surf = pygame.Surface((15, h), pygame.SRCALPHA)
    for y, row in enumerate(half_rows):
        row = row.ljust(8)[:8]
        for x, ch in enumerate(row):
            if ch == " ":
                continue
            if palette_swap and ch in palette_swap:
                ch = palette_swap[ch]
            col = COLORS[ch]
            surf.set_at((x, y), col)
            surf.set_at((14 - x, y), col)
    return surf


PLAYER = [
    "       W", "       W", "      WW", "      WW", "  R   WB", "  R  WWB",
    " RR  WWB", " RRW WWW", " RRWWWWW", " RRWWWRW", " RRRWWRW", " R RWW  ",
]
BEE_A = [
    "   R    ", "  RR  YY", " RR  YYB", " R  YYBY", "  YYYYYY", "   YYYBY",
    "    YYYY", "   B YY ", "  B  YY ",
]
BEE_B = [
    "        ", "   R  YY", "  RR YYB", "  RRYYBY", " R YYYYY", " R YYYBY",
    "    YYYY", "   B YY ", "  B  YY ",
]
BUT_A = [
    "R      C", "RR   R W", "RRR RRWW", "RRRRRBWW", " RRRRRBR", "  RRRRRR",
    "   RRRBW", "    RRR ", "   R  R ",
]
BUT_B = [
    "        ", "R     RC", "RR  RRRW", "RRRRRRBW", "RRRRRRBR", " RRRRRRR",
    "  RRRRBW", "   RRRR ", "    R R ",
]
BOSS_A = [
    "  G   G ", " GG  GGG", "GGGPGGGG", "GGGPPGWW", " GGGGGGG", "  GGGGPG",
    "  GGGPPG", "   GGGGG", "   G  G ",
]
BOSS_B = [
    "        ", " G   G G", "GGG GGGG", "GGGPGGWW", "GGGGGGGG", " GGGGGPG",
    "  GGGPPG", "   GGGGG", "    G G ",
]


def build_sprites():
    """Cria todos os sprites. Para usar imagens externas, troque aqui por
    pygame.image.load('arquivo.png').convert_alpha()."""
    s = {
        "player": make_sprite(PLAYER),
        "bee": [make_sprite(BEE_A), make_sprite(BEE_B)],
        "butterfly": [make_sprite(BUT_A), make_sprite(BUT_B)],
        "boss": [make_sprite(BOSS_A), make_sprite(BOSS_B)],
        "boss_hit": [make_sprite(BOSS_A, {"G": "P", "P": "C"}),
                     make_sprite(BOSS_B, {"G": "P", "P": "C"})],
    }
    return s


# ----------------------------------------------------------------------------
# Sons (sintetizados em codigo)
# ----------------------------------------------------------------------------
def synth(f0, f1, dur, vol=0.25, noise=False):
    rate = 22050
    n = int(rate * dur)
    buf = array("h")
    phase = 0.0
    for i in range(n):
        t = i / n
        f = f0 + (f1 - f0) * t
        phase += f / rate
        if noise:
            v = random.uniform(-1, 1)
        else:
            v = 1.0 if (phase % 1.0) < 0.5 else -1.0
        env = (1 - t) ** 1.5
        buf.append(int(v * env * vol * 32767))
    return pygame.mixer.Sound(buffer=buf.tobytes())


class Sfx:
    def __init__(self):
        self.ok = True
        try:
            self.shoot = synth(900, 300, 0.12)
            self.boom = synth(200, 40, 0.3, 0.35, noise=True)
            self.hit = synth(500, 250, 0.1, 0.2)
            self.dive = synth(300, 700, 0.35, 0.15)
            self.start = synth(300, 900, 0.6, 0.2)
            self.die = synth(400, 30, 0.8, 0.35, noise=True)
            self.life = synth(600, 1200, 0.5, 0.2)
        except Exception:
            self.ok = False

    def play(self, name):
        if self.ok:
            getattr(self, name).play()


# ----------------------------------------------------------------------------
# Entidades
# ----------------------------------------------------------------------------
class Star:
    def __init__(self):
        self.x = random.uniform(0, W)
        self.y = random.uniform(0, H)
        self.layer = random.choice([0, 1, 2])
        self.speed = 0.3 + self.layer * 0.5
        self.color = random.choice([(255, 255, 255), (120, 160, 255), (255, 120, 120), (120, 255, 200)])
        self.phase = random.uniform(0, 6.28)

    def update(self):
        self.y += self.speed
        if self.y > H:
            self.y = 0
            self.x = random.uniform(0, W)

    def draw(self, surf, t):
        if math.sin(t * 4 + self.phase) > -0.4:
            surf.set_at((int(self.x), int(self.y)), self.color)


class Bullet:
    def __init__(self, x, y, vx, vy, player):
        self.x, self.y, self.vx, self.vy, self.player = x, y, vx, vy, player

    def update(self):
        self.x += self.vx
        self.y += self.vy

    def alive(self):
        return -8 < self.y < H + 8 and -8 < self.x < W + 8

    def rect(self):
        return pygame.Rect(int(self.x) - 1, int(self.y) - 3, 3, 7)

    def draw(self, surf):
        r = self.rect()
        if self.player:
            pygame.draw.rect(surf, COLORS["W"], (r.x + 1, r.y, 1, 7))
            pygame.draw.rect(surf, COLORS["R"], (r.x + 1, r.y, 1, 3))
        else:
            pygame.draw.rect(surf, COLORS["O"], (r.x, r.y, 3, 6))
            pygame.draw.rect(surf, COLORS["W"], (r.x + 1, r.y + 1, 1, 4))


class Particle:
    def __init__(self, x, y, color):
        a = random.uniform(0, 6.283)
        s = random.uniform(0.5, 2.5)
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(a) * s, math.sin(a) * s
        self.life = random.randint(15, 35)
        self.color = color

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.96
        self.vy *= 0.96
        self.life -= 1

    def draw(self, surf):
        if self.life > 0:
            surf.fill(self.color, (int(self.x), int(self.y), 2, 2))


BOSS_HALF = [
    "      PP", "  P  PPC", " PP PPPC", "PPPPPGGC", "PPGPGWWG", "PPPPGWRG",
    "PPPPPGGG", " PPPPPPP", " R PP PP", "R   PPPP", "R    P  ",
]


class Boss:
    """Chefe final (aparece a cada 5 fases). Tem 2 fases de ataque."""

    def __init__(self, stage):
        base = make_sprite(BOSS_HALF)
        flash = make_sprite([r.replace("P", "W").replace("G", "W").replace("C", "W").replace("R", "W") for r in BOSS_HALF])
        size = (base.get_width() * 4, base.get_height() * 4)
        self.img = pygame.transform.scale(base, size)
        self.img_flash = pygame.transform.scale(flash, size)
        self.stage = stage
        self.max_hp = 40 + stage * 4
        self.hp = self.max_hp
        self.x, self.y = W / 2, -50.0
        self.target_y = 62
        self.age = 0
        self.cd = 90
        self.n = 0
        self.spiral = 0.0
        self.flash = 0

    @property
    def phase(self):
        return 1 if self.hp > self.max_hp / 2 else 2

    def rect(self):
        return pygame.Rect(int(self.x) - 26, int(self.y) - 20, 52, 40)

    def update(self, ebullets, player, active):
        if self.flash > 0:
            self.flash -= 1
        if self.y < self.target_y:
            self.y += 1
            return
        self.age += 1
        mult = 1.0 if self.phase == 1 else 1.7
        self.x = W / 2 + math.sin(self.age * 0.02 * mult) * (W / 2 - 45)
        if not active:
            return
        sp = 1.6 + min(self.stage, 20) * 0.03
        if self.phase == 2:
            self.spiral += 0.45
            if self.age % 9 == 0:
                ebullets.append(Bullet(self.x, self.y + 14, math.cos(self.spiral) * 1.2, 1.4 + abs(math.sin(self.spiral)), False))
        self.cd -= 1
        if self.cd > 0:
            return
        self.cd = 75 if self.phase == 1 else 55
        self.n += 1
        if self.n % 2 == 0:
            count = 5 if self.phase == 1 else 7
            for i in range(count):
                a = math.pi / 2 + (i - count // 2) * 0.28
                ebullets.append(Bullet(self.x, self.y + 16, math.cos(a) * sp, math.sin(a) * sp, False))
        else:
            base = math.atan2(player.y - self.y, player.x - self.x)
            for off in (-0.18, 0, 0.18):
                ebullets.append(Bullet(self.x, self.y + 16, math.cos(base + off) * (sp + 0.5), math.sin(base + off) * (sp + 0.5), False))

    def draw(self, surf):
        img = self.img_flash if self.flash > 0 else self.img
        surf.blit(img, img.get_rect(center=(int(self.x), int(self.y))))
        # barra de vida
        bw = 160
        x0 = (W - bw) // 2
        pygame.draw.rect(surf, (60, 20, 20), (x0, 26, bw, 5))
        col = COLORS["G"] if self.phase == 1 else COLORS["R"]
        pygame.draw.rect(surf, col, (x0, 26, int(bw * max(0, self.hp) / self.max_hp), 5))
        pygame.draw.rect(surf, COLORS["W"], (x0 - 1, 25, bw + 2, 7), 1)


POWERUPS = {
    # letra: (nome, cor)
    "T": ("TIRO TRIPLO", "C"),
    "S": ("ESCUDO", "G"),
    "N": ("NOVA", "R"),
}


class PowerUp:
    """Item que cai de inimigos destruidos (diferencial do clone)."""

    def __init__(self, x, y, kind):
        self.x, self.y, self.kind = x, y, kind
        self.age = 0

    def update(self):
        self.y += 1.0
        self.age += 1

    def rect(self):
        return pygame.Rect(int(self.x) - 7, int(self.y) - 7, 14, 14)

    def draw(self, surf, font):
        col = COLORS[POWERUPS[self.kind][1]]
        pulse = 7 + int(math.sin(self.age * 0.2) * 1.5)
        pygame.draw.circle(surf, (20, 20, 40), (int(self.x), int(self.y)), pulse)
        pygame.draw.circle(surf, col, (int(self.x), int(self.y)), pulse, 2)
        img = font.render(self.kind, False, COLORS["W"])
        surf.blit(img, img.get_rect(center=(int(self.x), int(self.y))))


class Player:
    SPEED = 2.2

    def __init__(self, sprites):
        self.img = sprites["player"]
        self.x = W / 2
        self.y = H - 28
        self.alive = True
        self.shield = False
        self.triple = 0      # frames restantes de tiro triplo
        self.invuln = 0      # frames de invulnerabilidade apos escudo quebrar

    def rect(self):
        return pygame.Rect(int(self.x) - 6, int(self.y) - 6, 12, 12)

    def update(self, keys):
        if self.triple > 0:
            self.triple -= 1
        if self.invuln > 0:
            self.invuln -= 1
        dx = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            dx -= 1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            dx += 1
        self.x = max(10, min(W - 10, self.x + dx * self.SPEED))

    def draw(self, surf):
        surf.blit(self.img, (int(self.x) - 7, int(self.y) - 6))


KINDS = {
    # tipo: (pontos na formacao, pontos mergulhando, vidas)
    "bee": (50, 100, 1),
    "butterfly": (80, 160, 1),
    "boss": (150, 400, 2),
}
FORM_Y = 40


def build_path(side):
    """Cria o caminho de entrada (desce, faz um laco e vai a formacao)."""
    sgn = 1 if side == 0 else -1
    x0 = 40 if side == 0 else W - 40
    r = 28
    pts = [(x0, -16), (x0, 60), (x0, 130)]
    cx, cy = x0 + sgn * r, 130
    start = math.pi if sgn == 1 else 0.0
    # laco de ~300 graus
    for i in range(1, 22):
        a = start - sgn * (i / 20) * math.radians(300)
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts


class Enemy:
    def __init__(self, kind, col, row, path, delay, sprites):
        self.kind, self.col, self.row = kind, col, row
        self.sprites = sprites
        self.hp = KINDS[kind][2]
        self.path = path
        self.pi = 0
        self.x, self.y = path[0]
        self.delay = delay
        self.state = "wait"
        self.shots_left = 0
        self.dive_t = 0.0
        self.dive_x0 = 0.0

    def slot(self, form):
        shift, breath = form
        sx = W / 2 + (self.col - 4.5) * 16 * breath + shift
        sy = FORM_Y + self.row * 16 * (0.7 + 0.3 * breath)
        return sx, sy

    def rect(self):
        return pygame.Rect(int(self.x) - 6, int(self.y) - 6, 12, 12)

    def move_to(self, tx, ty, speed):
        dx, dy = tx - self.x, ty - self.y
        d = math.hypot(dx, dy)
        if d <= speed:
            self.x, self.y = tx, ty
            return True
        self.x += dx / d * speed
        self.y += dy / d * speed
        return False

    def start_dive(self, player_x, stage):
        self.state = "dive"
        self.dive_x0 = self.x
        self.dive_y0 = self.y
        self.dive_dir = 1 if self.x < player_x else -1
        self.target_x = player_x
        self.shots_left = 1 + (1 if stage > 2 else 0)
        self.shot_y = [self.y + 60, self.y + 120][: self.shots_left]

    def update(self, form, player_x, bullets, stage, sfx):
        if self.state == "wait":
            self.delay -= 1
            if self.delay <= 0:
                self.state = "enter"
            return
        if self.state == "enter":
            speed = 3.0 + min(stage, 6) * 0.1
            if self.pi < len(self.path):
                if self.move_to(*self.path[self.pi], speed):
                    self.pi += 1
            else:
                if self.move_to(*self.slot(form), speed):
                    self.state = "form"
        elif self.state == "form":
            self.x, self.y = self.slot(form)
        elif self.state == "dive":
            speed = 2.0 + min(stage, 8) * 0.12
            self.y += speed
            wob = math.sin((self.y - self.dive_y0) / 22.0) * 22 * self.dive_dir
            steer = (self.target_x - self.dive_x0) * min(1.0, (self.y - self.dive_y0) / 220)
            self.x = self.dive_x0 + steer + wob
            for sy in list(self.shot_y):
                if self.y > sy and self.y < H - 60:
                    self.shot_y.remove(sy)
                    ang = math.atan2(H - 28 - self.y, player_x - self.x)
                    sp = 1.8 + min(stage, 8) * 0.1
                    bullets.append(Bullet(self.x, self.y + 6, math.cos(ang) * sp, math.sin(ang) * sp, False))
            if self.y > H + 12:
                self.y = -12
                self.state = "return"
        elif self.state == "return":
            if self.move_to(*self.slot(form), 2.8):
                self.state = "form"

    def draw(self, surf, t):
        frame = int(t * 3) % 2
        if self.kind == "boss":
            imgs = self.sprites["boss_hit"] if self.hp < 2 else self.sprites["boss"]
        else:
            imgs = self.sprites[self.kind]
        img = imgs[frame]
        if self.state == "dive":
            ang = -self.dive_dir * math.sin((self.y - self.dive_y0) / 22.0) * 25 + 180
            img = pygame.transform.rotate(img, ang)
        r = img.get_rect(center=(int(self.x), int(self.y)))
        surf.blit(img, r)


# ----------------------------------------------------------------------------
# Jogo
# ----------------------------------------------------------------------------
class Game:
    def __init__(self):
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        self.window = pygame.display.set_mode((W * SCALE, H * SCALE))
        pygame.display.set_caption("Galaga - Clone em Pygame")
        self.screen = pygame.Surface((W, H))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 11, bold=True)
        self.big = pygame.font.SysFont("consolas", 18, bold=True)
        self.sprites = build_sprites()
        self.sfx = Sfx()
        self.stars = [Star() for _ in range(90)]
        self.high = self.load_high()
        self.t = 0.0
        self.state = "menu"
        self.reset()

    # -- util --
    def load_high(self):
        try:
            with open(HIGHSCORE_FILE) as f:
                return int(f.read().strip())
        except Exception:
            return 20000

    def save_high(self):
        try:
            with open(HIGHSCORE_FILE, "w") as f:
                f.write(str(self.high))
        except Exception:
            pass

    def text(self, s, x, y, color=(240, 240, 240), font=None, center=False):
        font = font or self.font
        img = font.render(s, False, color)
        if center:
            x = x - img.get_width() // 2
        self.screen.blit(img, (x, y))

    def reset(self):
        self.score = 0
        self.lives = 3
        self.stage = 0
        self.next_bonus = 20000
        self.shots = 0
        self.hits = 0
        self.player = Player(self.sprites)
        self.pbullets, self.ebullets, self.enemies, self.parts = [], [], [], []
        self.powerups = []
        self.nova = 0
        self.msg, self.msg_t = "", 0
        self.respawn = 0
        self.banner = 0
        self.clear_timer = 0
        self.dive_timer = 0
        self.boss = None
        self.paused = False

    def add_score(self, n):
        self.score += n
        if self.score > self.high:
            self.high = self.score
        if self.score >= self.next_bonus:
            self.lives += 1
            self.sfx.play("life")
            self.next_bonus = 70000 if self.next_bonus == 20000 else self.next_bonus + 70000

    # -- fases --
    def start_stage(self):
        self.stage += 1
        self.banner = 150
        self.clear_timer = 0
        self.dive_timer = 240
        self.enemies = []
        self.boss = None
        if self.stage % 5 == 0:
            self.boss = Boss(self.stage)
            self.sfx.play("start")
            return
        layout = []
        for c in range(3, 7):
            layout.append(("boss", c, 0))
        for r in (1, 2):
            for c in range(1, 9):
                layout.append(("butterfly", c, r))
        for r in (3, 4):
            for c in range(0, 10):
                layout.append(("bee", c, r))
        # 5 grupos de 8, alternando lados
        groups = [
            [e for e in layout if e[2] == 0] + [e for e in layout if e[2] == 1 and e[1] < 5],
            [e for e in layout if e[2] == 1 and e[1] >= 5] + [e for e in layout if e[2] == 2 and e[1] >= 5],
            [e for e in layout if e[2] == 2 and e[1] < 5],
            [e for e in layout if e[2] == 3],
            [e for e in layout if e[2] == 4],
        ]
        base = 160
        for gi, g in enumerate(groups):
            side = gi % 2
            for ei, (k, c, r) in enumerate(g):
                path = build_path(side if k != "boss" else 1 - side)
                delay = base + gi * 130 + ei * 9
                self.enemies.append(Enemy(k, c, r, path, delay, self.sprites))
        self.sfx.play("start")

    def formation(self):
        shift = math.sin(self.t * 0.6) * 12
        breath = 1.0 + 0.08 * (math.sin(self.t * 1.3) + 1)
        return shift, breath

    # -- eventos --
    def handle_events(self):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.quit()
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.quit()
                if self.state in ("menu", "gameover") and e.key == pygame.K_RETURN:
                    self.reset()
                    self.state = "play"
                    self.start_stage()
                elif self.state == "play":
                    if e.key == pygame.K_p:
                        self.paused = not self.paused
                    elif e.key == pygame.K_SPACE and not self.paused:
                        self.shoot()

    def shoot(self):
        p = self.player
        limit = 6 if p.triple > 0 else 2
        if p.alive and self.respawn == 0 and len(self.pbullets) < limit and self.banner < 130:
            self.pbullets.append(Bullet(p.x, p.y - 8, 0, -6, True))
            if p.triple > 0:
                self.pbullets.append(Bullet(p.x - 4, p.y - 6, -1.2, -5.8, True))
                self.pbullets.append(Bullet(p.x + 4, p.y - 6, 1.2, -5.8, True))
            self.shots += 1
            self.sfx.play("shoot")

    def quit(self):
        self.save_high()
        pygame.quit()
        sys.exit()

    # -- atualizacao --
    def explode(self, x, y, colors, n=22):
        for _ in range(n):
            self.parts.append(Particle(x, y, random.choice(colors)))

    def popup(self, text):
        self.msg, self.msg_t = text, 90

    def damage_enemy(self, en, dmg=1):
        """Tira vida do inimigo; se morrer, pontua e pode soltar power-up."""
        en.hp -= dmg
        if en.hp > 0:
            self.sfx.play("hit")
            return
        pts = KINDS[en.kind][1 if en.state == "dive" else 0]
        self.add_score(pts)
        if en in self.enemies:
            self.enemies.remove(en)
        self.explode(en.x, en.y, [COLORS["W"], COLORS["Y"], COLORS["O"], COLORS["R"]])
        self.sfx.play("boom")
        chance = 0.30 if en.kind == "boss" else (0.12 if en.state == "dive" else 0.07)
        if random.random() < chance:
            self.powerups.append(PowerUp(en.x, en.y, random.choice("TTSN")))

    def collect(self, pu):
        p = self.player
        self.add_score(500)
        self.popup(POWERUPS[pu.kind][0])
        self.sfx.play("life")
        if pu.kind == "T":
            p.triple = 60 * 12
        elif pu.kind == "S":
            p.shield = True
        elif pu.kind == "N":
            # onda de choque: dano em todos os inimigos e limpa os tiros
            self.ebullets.clear()
            self.nova = 25
            for en in list(self.enemies):
                if en.state != "wait":
                    self.damage_enemy(en)
            if self.boss:
                self.damage_boss(8)

    def damage_boss(self, dmg=1):
        b = self.boss
        b.hp -= dmg
        b.flash = 4
        self.add_score(10)
        self.sfx.play("hit")
        if b.hp <= 0:
            self.add_score(5000 * (self.stage // 5))
            for _ in range(6):
                self.explode(b.x + random.uniform(-26, 26), b.y + random.uniform(-20, 20),
                             [COLORS["W"], COLORS["Y"], COLORS["O"], COLORS["R"], COLORS["P"]], 40)
            self.sfx.play("die")
            self.ebullets.clear()
            for i, k in enumerate("TSN"):
                self.powerups.append(PowerUp(b.x + (i - 1) * 24, b.y, k))
            self.popup("CHEFE DERROTADO!")
            self.boss = None

    def update_play(self):
        keys = pygame.key.get_pressed()
        if self.banner > 0:
            self.banner -= 1
        if self.player.alive:
            self.player.update(keys)
        elif self.respawn > 0:
            self.respawn -= 1
            if self.respawn == 0:
                if self.lives > 0:
                    self.player.alive = True
                    self.player.x = W / 2
                    self.ebullets.clear()
                else:
                    self.state = "gameover"
                    self.save_high()
                    return

        form = self.formation()
        for en in self.enemies:
            en.update(form, self.player.x, self.ebullets, self.stage, self.sfx)
        if self.boss:
            self.boss.update(self.ebullets, self.player, self.banner == 0 and self.player.alive)

        # mergulhos
        ready = [e for e in self.enemies if e.state == "form"]
        all_in = all(e.state in ("form", "dive", "return") for e in self.enemies)
        if all_in and ready and self.player.alive:
            self.dive_timer -= 1
            if self.dive_timer <= 0:
                n = min(1 + self.stage // 2, 4)
                if len(self.enemies) < 10:
                    n += 1
                for e in random.sample(ready, min(n, len(ready))):
                    e.start_dive(self.player.x, self.stage)
                self.sfx.play("dive")
                self.dive_timer = max(50, 160 - self.stage * 12) + random.randint(0, 60)

        for b in self.pbullets:
            b.update()
        for b in self.ebullets:
            b.update()
        self.pbullets = [b for b in self.pbullets if b.alive()]
        self.ebullets = [b for b in self.ebullets if b.alive()]

        # tiros do jogador x inimigos
        for b in list(self.pbullets):
            br = b.rect()
            for en in self.enemies:
                if en.state != "wait" and br.colliderect(en.rect()):
                    self.pbullets.remove(b)
                    self.hits += 1
                    self.damage_enemy(en)
                    break
            else:
                if self.boss and br.colliderect(self.boss.rect()) and self.boss.y >= self.boss.target_y:
                    self.pbullets.remove(b)
                    self.hits += 1
                    self.damage_boss()

        # jogador atingido
        if self.player.alive:
            pr = self.player.rect()
            hit = any(pr.colliderect(b.rect()) for b in self.ebullets)
            self.ebullets = [b for b in self.ebullets if not pr.colliderect(b.rect())]
            for en in list(self.enemies):
                if en.state != "wait" and pr.colliderect(en.rect()):
                    hit = True
                    self.enemies.remove(en)
                    self.explode(en.x, en.y, [COLORS["W"], COLORS["O"]])
            if hit and self.player.invuln > 0:
                pass
            elif hit and self.player.shield:
                self.player.shield = False
                self.player.invuln = 60
                self.explode(self.player.x, self.player.y, [COLORS["G"], COLORS["W"]], 25)
                self.popup("ESCUDO QUEBRADO")
                self.sfx.play("hit")
            elif hit:
                self.player.alive = False
                self.player.triple = 0
                self.lives -= 1
                self.respawn = 120
                self.explode(self.player.x, self.player.y, [COLORS["W"], COLORS["C"], COLORS["R"], COLORS["B"]], 40)
                self.sfx.play("die")

            for pu in list(self.powerups):
                if pr.colliderect(pu.rect()):
                    self.powerups.remove(pu)
                    self.collect(pu)

        for pu in self.powerups:
            pu.update()
        self.powerups = [pu for pu in self.powerups if pu.y < H + 10]
        if self.msg_t > 0:
            self.msg_t -= 1
        if self.nova > 0:
            self.nova -= 1

        for p in self.parts:
            p.update()
        self.parts = [p for p in self.parts if p.life > 0]

        # fase concluida
        if not self.enemies and not self.boss and self.banner == 0 and self.player.alive:
            if self.clear_timer == 0:
                self.clear_timer = 150
            self.clear_timer -= 1
            if self.clear_timer == 0:
                self.start_stage()

    # -- desenho --
    def draw_hud(self):
        self.text("1UP", 12, 2, COLORS["R"])
        self.text(f"{self.score:>7}", 8, 12)
        self.text("HIGH SCORE", W // 2, 2, COLORS["R"], center=True)
        self.text(f"{self.high}", W // 2, 12, center=True)
        mini = pygame.transform.scale(self.sprites["player"], (11, 9))
        for i in range(max(0, self.lives - (1 if self.player.alive or self.respawn else 0))):
            self.screen.blit(mini, (4 + i * 13, H - 12))
        s = f"STAGE {self.stage}"
        self.text(s, W - 8 - self.font.size(s)[0], H - 13, COLORS["C"])

        # power-ups: itens caindo, escudo, barra de tiro triplo, mensagem
        for pu in self.powerups:
            pu.draw(self.screen, self.font)
        p = self.player
        if p.alive and p.shield:
            pygame.draw.circle(self.screen, COLORS["G"], (int(p.x), int(p.y)), 11 + int(math.sin(self.t * 8)), 1)
        if p.triple > 0:
            pygame.draw.rect(self.screen, COLORS["C"], (60, H - 8, int(p.triple / 720 * 100), 3))
            self.text("T", 50, H - 12, COLORS["C"])
        if self.msg_t > 0:
            self.text(self.msg, W // 2, 200, COLORS["Y"], center=True)
        if self.nova > 0:
            ring = pygame.Surface((W, H), pygame.SRCALPHA)
            pygame.draw.circle(ring, (255, 120, 80, int(self.nova * 8)), (int(p.x), int(p.y)), (25 - self.nova) * 12, 3)
            self.screen.blit(ring, (0, 0))

    def draw(self):
        self.screen.fill((0, 0, 12))
        for s in self.stars:
            s.update() if not self.paused else None
            s.draw(self.screen, self.t)

        if self.state == "menu":
            self.text("GALAGA", W // 2, 70, COLORS["C"], self.big, True)
            self.text("CLONE EM PYGAME", W // 2, 94, COLORS["Y"], center=True)
            for i, k in enumerate(("boss", "butterfly", "bee")):
                img = self.sprites[k][int(self.t * 3) % 2]
                self.screen.blit(img, (70, 125 + i * 22))
                self.text(f"= {KINDS[k][0]} / {KINDS[k][1]} pts", 94, 128 + i * 22)
            self.text("SETAS: MOVER   ESPACO: ATIRAR", W // 2, 205, center=True)
            self.text("P: PAUSAR   ESC: SAIR", W // 2, 218, center=True)
            if int(self.t * 2) % 2 == 0:
                self.text("PRESSIONE ENTER", W // 2, 245, COLORS["R"], center=True)
            self.text(f"HIGH SCORE {self.high}", W // 2, 268, center=True)
        else:
            for en in self.enemies:
                if en.state != "wait":
                    en.draw(self.screen, self.t)
            if self.boss:
                self.boss.draw(self.screen)
            for b in self.pbullets + self.ebullets:
                b.draw(self.screen)
            if self.player.alive:
                self.player.draw(self.screen)
            for p in self.parts:
                p.draw(self.screen)
            self.draw_hud()

            if self.banner > 0 and self.state == "play":
                self.text(f"STAGE {self.stage}", W // 2, 140, COLORS["C"], self.big, True)
                if self.boss:
                    self.text("CUIDADO: CHEFE!", W // 2, 165, COLORS["R"], center=True)
            if self.state == "play" and not self.player.alive and self.respawn > 0 and self.lives > 0:
                self.text("READY", W // 2, 150, COLORS["C"], center=True)
            if self.paused:
                self.text("PAUSADO", W // 2, 140, COLORS["Y"], self.big, True)
            if self.state == "gameover":
                self.text("GAME OVER", W // 2, 110, COLORS["R"], self.big, True)
                acc = (self.hits / self.shots * 100) if self.shots else 0
                self.text(f"TIROS: {self.shots}", W // 2, 145, center=True)
                self.text(f"ACERTOS: {self.hits}", W // 2, 158, center=True)
                self.text(f"PRECISAO: {acc:.1f}%", W // 2, 171, COLORS["Y"], center=True)
                if int(self.t * 2) % 2 == 0:
                    self.text("ENTER PARA JOGAR NOVAMENTE", W // 2, 210, center=True)

        pygame.transform.scale(self.screen, self.window.get_size(), self.window)
        pygame.display.flip()

    def run(self):
        while True:
            self.handle_events()
            if not self.paused:
                self.t += 1 / FPS
                if self.state == "play":
                    self.update_play()
                elif self.state == "gameover":
                    for p in self.parts:
                        p.update()
            self.draw()
            self.clock.tick(FPS)


if __name__ == "__main__":
    Game().run()
