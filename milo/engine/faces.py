"""Flat cartoon face decals, 1024x578, black strokes 9-17 px, features in the middle 45%.
Writes out/faces/<name>.png, the stacked atlas out/faces/atlas.png and a contact sheet."""
import math, os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
LOOK = os.environ.get("MILO_LOOK")
REAL = LOOK == "real"             # top-channel style: thicker ink, big white eyes
BRICK = LOOK == "brick"           # toy prints: thin lines, small oval eyes, thin brows (printed flat on the head)
DIR = os.path.join(os.path.dirname(HERE), "work", "faces_real" if REAL else "faces_brick" if BRICK else "faces")
LW = 1.45 if REAL else 0.62 if BRICK else 1.0
W, H, S = 1024, 578, 4            # draw at 4x, downsample for clean edges
from facelist import FACES
BLACK, WHITE = ((22, 18, 16, 255) if BRICK else (0, 0, 0, 255)), (255, 255, 255, 255)
LX, RX, EY, MX, MY = 432, 592, 248, 512, 360   # eye x's, eye y, mouth centre


# the decal spans the whole head height, so features are drawn wide to read round; brick prints go flat on the
# front of a box head (planar, 1:1), so they keep their shape
KX, KY = (1.0, 0.92) if BRICK else (1.75, 0.93)


class Pen:
    def __init__(self):
        self.im = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)

    @staticmethod
    def _p(x, y):
        return (W / 2 + (x - W / 2) * KX) * S, (H / 2 + (y - H / 2) * KY) * S

    def _b(self, box):
        x0, y0 = self._p(box[0], box[1])
        x1, y1 = self._p(box[2], box[3])
        return [x0, y0, x1, y1]

    def oval(self, cx, cy, rx, ry, fill=BLACK, outline=None, width=0):
        self.d.ellipse(self._b((cx - rx, cy - ry, cx + rx, cy + ry)), fill=fill,
                       outline=outline, width=int(width * LW * S))

    def line(self, pts, width=13):
        pts = [self._p(x, y) for x, y in pts]
        self.d.line(pts, fill=BLACK, width=int(width * LW * S), joint="curve")
        for x, y in (pts[0], pts[-1]):
            r = width * LW * S / 2
            self.d.ellipse((x - r, y - r, x + r, y + r), fill=BLACK)

    def arc(self, cx, cy, rx, ry, a0, a1, width=13):
        n = 40
        pts = [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
        self.line(pts, width)

    def poly(self, pts, fill=BLACK):
        self.d.polygon([self._p(x, y) for x, y in pts], fill=fill)

    def chord(self, cx, cy, rx, ry, a0, a1, fill=BLACK):
        self.d.chord(self._b((cx - rx, cy - ry, cx + rx, cy + ry)), a0, a1, fill=fill)

    def done(self):
        return self.im.resize((W, H), Image.LANCZOS)


def eyes(p, rx=17, ry=31, dy=0, look=(0, 0)):
    if REAL:                         # big white eyes, thick rim, pupil + glint
        for x in (LX, RX):
            p.oval(x, EY + dy, rx * 1.75, ry * 1.25, fill=WHITE, outline=BLACK, width=10)
            p.oval(x + look[0], EY + dy + 4 + look[1], rx * 0.8, ry * 0.62)
            p.oval(x + look[0] - 5, EY + dy - 6 + look[1], 5, 6, fill=WHITE)
        return
    if BRICK:                        # small printed oval eyes with a pin-point glint
        for x in (LX, RX):
            p.oval(x + look[0], EY + dy + look[1], rx * 0.82, ry * 0.68)
            p.oval(x + look[0] - 4, EY + dy - 7 + look[1], 3.5, 4.5, fill=WHITE)
        return
    for x in (LX, RX):
        p.oval(x, EY + dy, rx, ry)
        p.oval(x - 5, EY + dy - 12, 5, 7, fill=WHITE)


def big_eyes(p, r=33, pupil=11):
    if REAL:
        r, pupil = int(r * 1.25), int(pupil * 1.15)
    for x in (LX, RX):
        p.oval(x, EY, r, r + 3, fill=WHITE, outline=BLACK, width=11)
        p.oval(x, EY + 4, pupil, pupil + 2)


def wavy(p, cx, cy, w, amp, n=4, width=11):
    pts = [(cx - w / 2 + w * i / (n * 8), cy + amp * math.sin(i / 8 * math.pi * 2 / 2 * 2))
           for i in range(n * 8 + 1)]
    p.line(pts, width)


def smile(p):
    eyes(p)
    p.arc(MX, MY - 34, 78, 48, 25, 155, 14)


def grin(p):
    eyes(p)
    p.chord(MX, MY - 30, 92, 70, 0, 180)
    p.d.rectangle(p._b((MX - 72, MY - 30, MX + 72, MY - 12)), fill=WHITE)


def angry(p):
    eyes(p, 16, 25, 6)
    p.line([(LX - 40, EY - 52), (LX + 32, EY - 26)], 16)
    p.line([(RX + 40, EY - 52), (RX - 32, EY - 26)], 16)
    p.arc(MX, MY + 40, 62, 34, 205, 335, 14)


def scared(p):
    big_eyes(p, 31, 10)
    p.line([(LX - 38, EY - 44), (LX + 30, EY - 66)], 12)
    p.line([(RX + 38, EY - 44), (RX - 30, EY - 66)], 12)
    wavy(p, MX, MY + 18, 120, 9, 3, 11)


def shock(p):
    big_eyes(p, 36, 9)
    p.arc(LX, EY - 62, 34, 16, 200, 340, 11)
    p.arc(RX, EY - 62, 34, 16, 200, 340, 11)
    p.oval(MX, MY + 22, 32, 44)


def determined(p):
    for x in (LX, RX):
        p.chord(x, EY + 4, 19, 30, 0, 180)        # lower half: half-lidded
    p.line([(LX - 38, EY - 22), (LX + 30, EY - 6)], 15)
    p.line([(RX + 38, EY - 22), (RX - 30, EY - 6)], 15)
    p.line([(MX - 58, MY + 14), (MX + 40, MY + 8), (MX + 62, MY - 2)], 14)


def smug(p):
    for x in (LX, RX):
        p.chord(x, EY + 2, 19, 28, 0, 180)
        p.line([(x - 26, EY + 2), (x + 26, EY + 2)], 11)
    p.arc(MX + 14, MY - 10, 66, 36, 15, 120, 14)


def ahh(p):
    for x in (LX, RX):
        p.arc(x, EY + 14, 30, 26, 200, 340, 13)   # squeezed upward ^ ^
    p.line([(LX - 34, EY - 54), (LX + 26, EY - 68)], 11)
    p.line([(RX + 34, EY - 54), (RX - 26, EY - 68)], 11)
    p.oval(MX - 13, MY - 44, 7, 6)
    p.oval(MX + 13, MY - 44, 7, 6)
    p.oval(MX, MY + 20, 40, 34)


def sneeze(p):
    p.line([(LX - 28, EY - 24), (LX + 22, EY), (LX - 28, EY + 24)], 14)
    p.line([(RX + 28, EY - 24), (RX - 22, EY), (RX + 28, EY + 24)], 14)
    p.chord(MX, MY - 10, 86, 72, 0, 180)
    for dx, dy in ((-110, 10), (112, 22), (-118, 50), (120, 58)):
        p.oval(MX + dx, MY + dy, 7, 7)


def twitch(p):
    p.oval(LX, EY, 17, 31)
    p.oval(LX - 5, EY - 12, 5, 7, fill=WHITE)
    p.line([(RX + 28, EY - 20), (RX - 20, EY), (RX + 28, EY + 20)], 13)
    for dx in (-14, 0, 14):
        p.line([(MX + dx, EY - 24), (MX + dx * 1.4, EY + 4)], 9)
    wavy(p, MX, MY + 10, 100, 8, 3, 11)


def wink(p):
    p.oval(LX, EY, 17, 31)
    p.oval(LX - 5, EY - 12, 5, 7, fill=WHITE)
    p.arc(RX, EY + 12, 30, 22, 200, 340, 14)
    p.chord(MX, MY - 30, 92, 70, 0, 180)
    p.d.rectangle(p._b((MX - 72, MY - 30, MX + 72, MY - 12)), fill=WHITE)


def cry(p):
    for x in (LX, RX):
        p.arc(x, EY + 16, 30, 22, 200, 340, 14)
        p.line([(x, EY + 10), (x - 4, EY + 60), (x + 2, EY + 92)], 10)
    p.line([(LX - 36, EY - 40), (LX + 28, EY - 60)], 12)
    p.line([(RX + 36, EY - 40), (RX - 28, EY - 60)], 12)
    p.chord(MX, MY + 40, 70, 46, 180, 360)


def sleepy(p):
    for x in (LX, RX):
        p.chord(x, EY + 12, 19, 22, 0, 180)
        p.line([(x - 28, EY + 12), (x + 28, EY + 12)], 12)
    p.oval(MX + 10, MY + 18, 20, 18, fill=None, outline=BLACK, width=11)


# ---- added for the top-channel style (our own designs)
def evil(p):
    for x, s_ in ((LX, 1), (RX, -1)):
        p.chord(x, EY + 6, 24, 26, 0, 180)                       # narrowed, scheming eyes
        p.line([(x - 34 * s_, EY - 34), (x + 30 * s_, EY - 6)], 15)
    p.chord(MX, MY - 36, 120, 84, 0, 180)                         # very wide grin
    p.d.rectangle(p._b((MX - 98, MY - 36, MX + 98, MY - 14)), fill=WHITE)
    for dx in (-60, -20, 20, 60):
        p.line([(MX + dx, MY - 36), (MX + dx, MY - 14)], 6)


def sideeye(p):
    eyes(p, 17, 27, 0, look=(16, 0))
    for x in (LX, RX):
        p.line([(x - 30, EY - 22), (x + 30, EY - 22)], 11)        # flat lids
    p.line([(MX - 40, MY + 6), (MX + 46, MY - 2)], 13)


def _heart(p, cx, cy, r, col):
    p.oval(cx - r * 0.5, cy - r * 0.2, r * 0.55, r * 0.55, fill=col)
    p.oval(cx + r * 0.5, cy - r * 0.2, r * 0.55, r * 0.55, fill=col)
    p.poly([(cx - r * 1.02, cy - r * 0.05), (cx + r * 1.02, cy - r * 0.05), (cx, cy + r * 1.05)], fill=col)


def hearts(p):
    for x in (LX, RX):
        _heart(p, x, EY, 40, BLACK)
        _heart(p, x, EY - 2, 32, (232, 30, 60, 255))
    p.chord(MX, MY - 30, 80, 60, 0, 180)


def _star(p, cx, cy, r, col):
    pts = []
    for i in range(10):
        a = math.radians(-90 + i * 36)
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    p.poly(pts, fill=col)


def stars(p):
    for x in (LX, RX):
        _star(p, x, EY, 46, BLACK)
        _star(p, x, EY, 34, (255, 214, 40, 255))
    p.chord(MX, MY - 30, 86, 66, 0, 180)


def teary(p):
    big_eyes(p, 34, 13)
    for x in (LX, RX):
        p.oval(x + 12, EY + 16, 7, 8, fill=WHITE)                 # wet shine
        p.line([(x - 40, EY - 48), (x + 30, EY - 64)] if x == LX else [(x + 40, EY - 48), (x - 30, EY - 64)], 11)
    wavy(p, MX, MY + 22, 90, 7, 3, 11)


def laughcry(p):
    for x in (LX, RX):
        p.arc(x, EY + 14, 30, 24, 200, 340, 14)
        p.line([(x + (26 if x == RX else -26), EY + 14), (x + (40 if x == RX else -40), EY + 70)], 10)
    p.chord(MX, MY - 34, 96, 80, 0, 180)
    p.d.rectangle(p._b((MX - 76, MY - 34, MX + 76, MY - 16)), fill=WHITE)


def deadpan(p):
    for x in (LX, RX):
        p.oval(x, EY + 4, 10, 10)
    p.line([(MX - 44, MY), (MX + 44, MY)], 12)


BROWS = {"smile", "grin", "wink", "smug", "hearts", "stars", "deadpan", "sleepy", "laughcry"}


def brows(p, lift=0):
    """Brick prints: thin, gently arched brows on the faces that have none of their own."""
    for x in (LX, RX):
        p.arc(x, EY - 50 - lift, 28, 9, 200, 340, 10)


def main():
    os.makedirs(DIR, exist_ok=True)
    tiles = []
    for name in FACES:
        p = Pen()
        globals()[name](p)
        if BRICK and name in BROWS:
            brows(p, 6 if name in ("hearts", "stars") else 0)
        im = p.done()
        im.save(os.path.join(DIR, f"{name}.png"))
        tiles.append(im)
    atlas = Image.new("RGBA", (W, H * len(tiles)), (0, 0, 0, 0))
    for i, im in enumerate(tiles):
        atlas.paste(im, (0, H * i))
    atlas.save(os.path.join(DIR, "atlas.png"))
    # contact sheet on skin tone, cropped to the feature area
    sheet = Image.new("RGB", (5 * 512, ((len(tiles) + 4) // 5) * 330), (245, 205, 160))
    for i, im in enumerate(tiles):
        crop = im.crop((256, 120, 768, 450))
        sheet.paste(crop, ((i % 5) * 512, (i // 5) * 330), crop)
    sheet.save(os.path.join(DIR, "sheet.png"))
    print("faces:", ", ".join(FACES))


if __name__ == "__main__":
    main()
