"""Shirt print decals for the "real" look (our own simple graphics), stacked into work/prints/atlas.png.
Print 0 is blank. Prints are white with a dark rim so they read on any shirt colour."""
import math, os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(os.path.dirname(HERE), "work", "prints")
N = 512
PRINTS = ["blank", "bolt", "star", "stripes", "ring", "heart", "seven", "wave"]
INK, PAPER = (20, 20, 24, 255), (250, 250, 250, 255)


def bolt(d):
    pts = [(290, 40), (150, 270), (250, 270), (200, 470), (370, 210), (265, 210), (330, 40)]
    d.polygon(pts, fill=PAPER, outline=INK, width=14)


def star(d):
    pts = []
    for i in range(10):
        a = math.radians(-90 + 36 * i)
        r = 220 if i % 2 == 0 else 95
        pts.append((256 + r * math.cos(a), 270 + r * math.sin(a)))
    d.polygon(pts, fill=(255, 210, 50, 255), outline=INK, width=14)


def stripes(d):
    for k, y in enumerate((120, 230, 340)):
        d.rectangle((0, y, N, y + 60), fill=PAPER if k != 1 else (230, 40, 50, 255))


def ring(d):
    d.ellipse((76, 90, 436, 450), fill=PAPER, outline=INK, width=16)
    d.ellipse((176, 190, 336, 350), fill=(40, 120, 230, 255), outline=INK, width=12)


def heart(d):
    d.ellipse((96, 120, 266, 290), fill=(232, 40, 70, 255))
    d.ellipse((246, 120, 416, 290), fill=(232, 40, 70, 255))
    d.polygon([(106, 235), (406, 235), (256, 440)], fill=(232, 40, 70, 255))


def seven(d):
    d.rectangle((120, 90, 400, 160), fill=PAPER, outline=INK, width=10)
    d.polygon([(330, 160), (400, 160), (240, 440), (170, 440)], fill=PAPER, outline=INK, width=10)


def wave(d):
    for k in range(3):
        pts = [(x, 200 + k * 70 + 40 * math.sin(x / 512 * 4 * math.pi)) for x in range(0, N + 1, 8)]
        d.line(pts, fill=PAPER if k != 1 else (80, 200, 255, 255), width=34)


def main():
    os.makedirs(DIR, exist_ok=True)
    atlas = Image.new("RGBA", (N, N * len(PRINTS)), (0, 0, 0, 0))
    for i, name in enumerate(PRINTS):
        im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
        if name != "blank":
            globals()[name](ImageDraw.Draw(im))
        atlas.paste(im, (0, N * i))
    atlas.save(os.path.join(DIR, "atlas.png"))
    print("prints:", ", ".join(PRINTS))


if __name__ == "__main__":
    main()
