"""Set library (runs inside Blender). Each set is built around its own origin along X and returns
a Set with named spots (x, y, z, heading), a default wide camera, crowd spots and a crowd slide.
Characters face -Y (toward the default camera) at heading 0.
Dressing (trims, windows, doors, posters, clutter, plants, trees, street furniture) comes from setkit."""
from math import radians, sin, cos, atan2, sqrt, degrees
from core import part, text, empty, MESH, COLL, lin, keys, NF, FPS
import core, os
import setkit as K
from setkit import Wall, bbox
REAL = os.environ.get("MILO_LOOK") == "real"
BRICK = os.environ.get("MILO_LOOK") == "brick"
if BRICK:
    import brickkit as BK

SET_X = {"home": 0, "street": 120, "classroom": 240, "hallway": 360, "cafeteria": 480, "gym": 600,
         "museum": 720, "farm": 840, "sky": 960, "theater": 1080}


class Set:
    def __init__(self, name):
        self.name, self.x = name, SET_X[name]
        self.spots, self.crowd = {}, []
        self.wide = None          # (pos, target, fov)
        self.slide = None         # (pos, target, fov, slide vector)

    def spot(self, name, x, y, z=0.0, hd=0.0):
        self.spots[name] = (self.x + x, y, z, hd)

    def at(self, name):
        return self.spots[name]

    def P(self, x, y, z):
        return (self.x + x, y, z)


def box(s, name, x, y, z, sx, sy, sz, col, rot=(0, 0, 0), bev=0.0, tex=None):
    return bbox(f"{s.name}_{name}", s.P(x, y, z), (sx, sy, sz), col, rot=rot, bev=bev, tex=tex)


def walls(s, w, d):
    """Wall frames of a room(): back, left, right (inner faces)."""
    return (Wall(s, 0, d / 2 - 0.5, 0), Wall(s, -(w / 2 - 0.5), 0, 90), Wall(s, w / 2 - 0.5, 0, -90))


def room(s, w, d, floor, wall, h=10, window=True, wains=None, wains_h=3.2, wains_tex=None):
    """Floor, back wall and two side walls, open roof and open front so the sun gets in.
    Bevelled baseboards + crown on every wall, optional two-tone wainscot, a framed window."""
    if BRICK:
        return _brick_room(s, w, d, floor, wall, h, window, wains, wains_h)
    box(s, "floor", 0, 0, 0, w, d, 0.1, floor)
    box(s, "back", 0, d / 2, h / 2, w, 1, h, wall)
    for sx in (-1, 1):
        box(s, f"side{sx}", sx * w / 2, 0, h / 2, 1, d, h, wall)
    if REAL:      # enclosed room like the references: a ceiling the camera sees, the sun still gets in
        c = box(s, "ceil", 0, 0, h, w, d, 0.2, "#EEEEEC", tex="plaster")
        c.visible_shadow = False
    B, Lw, R = walls(s, w, d)
    iw, idp = w / 2 - 0.5, d / 2 - 0.5
    # the back baseboard keeps the old "band" name
    bbox(f"{s.name}_band", B.P(0, 0.08, 0.3), (2 * iw, 0.16, 0.6), "#FFFFFF", bev=0.05)
    B.box("bkcrown", 0, 0.12, h - 0.2, 2 * iw, 0.24, 0.4, "#FFFFFF", bev=0.06)
    B.box("bkcrown2", 0, 0.05, h - 0.55, 2 * iw, 0.1, 0.12, "#FFFFFF", bev=0.03)
    K.trims(Lw, "lt", -d / 2, idp, h)
    K.trims(R, "rt", -idp, d / 2, h)
    if wains:
        K.wainscot(B, "bk", -iw, iw, wains_h, wains, tex=wains_tex)
        K.wainscot(Lw, "lt", -d / 2, idp, wains_h, wains, tex=wains_tex)
        K.wainscot(R, "rt", -idp, d / 2, wains_h, wains, tex=wains_tex)
    if window:
        K.window(B, "win_", -w / 4, h * 0.55, w / 4 * 0.75, h * 0.34, cols=3, rows=2,
                 glass_name="win", frame_name="winf")
    return B, Lw, R


# ---------------------------------------------------------------- brick look (MILO_LOOK=brick)
# floor per room: ("studs",) = studded plate, or ("tiles", tx, ty, second colour, stagger) = smooth tiles
BRICK_FLOOR = {"home": ("studs",), "classroom": ("tiles", 2, 2, None, False), "hallway": ("tiles", 4, 2, None, False),
               "cafeteria": ("tiles", 2, 2, "#8E969E", False), "gym": ("tiles", 6, 1, None, True),
               "museum": ("tiles", 4, 4, None, False)}
# baseplate around each set (set coords x0, x1, y0, y1), colour; indoor plates frame the room footprint
BRICK_BASE = {"home": (-28, 28, -30, 15, "#E4CD9E"), "classroom": (-28, 28, -32, 17, "#A0A5A9"),
              "hallway": (-36, 36, -28, 13, "#A0A5A9"), "cafeteria": (-36, 36, -40, 20, "#A0A5A9"),
              "gym": (-40, 40, -36, 22, "#E4CD9E"), "museum": (-38, 38, -40, 22, "#A0A5A9"),
              "farm": (-44, 44, -38, 40, "#4B9F4A")}
GREEN, LGREY, DGREY = "#4B9F4A", "#A0A5A9", "#55595E"


def _brick_floor(s, x0, x1, y0, y1, col):
    spec = BRICK_FLOOR.get(s.name, ("studs",))
    z0 = BK.BASE_TOP_IN
    if spec[0] == "studs":
        return BK.plate_obj(f"{s.name}_floor", s.P(0, 0, 0), x0, x1, y0, y1, z0, 0.0, col)
    _, tx, ty, col2, stagger = spec
    cols = [col, col2 or core.shade(col, 0.9)]
    return BK.tiles_obj(f"{s.name}_floor", s.P(0, 0, 0), x0, x1, y0, y1, z0, 0.0, tx, ty, cols, stagger=stagger)


def _brick_room(s, w, d, floor, wall, h, window, wains, wains_h):
    """Brick room: floor plate/tiles on a baseplate, three running-bond walls (built after the set's windows
    have cut their holes), white tile trims, an optional second colour for the lower courses."""
    s.room = (w, d)
    _brick_floor(s, -w / 2 + 0.5, w / 2 - 0.5, -d / 2, d / 2 - 0.5, floor)
    B, Lw, R = walls(s, w, d)
    z0 = BK.BASE_TOP_IN
    BK.defer_wall(s, B, f"{s.name}_back", -w / 2 - 0.5, w / 2 + 0.5, z0, h - z0, wall, front=d)
    BK.defer_wall(s, Lw, f"{s.name}_side-1", -d / 2, d / 2 - 0.5, z0, h - z0, wall)
    BK.defer_wall(s, R, f"{s.name}_side1", -(d / 2 - 0.5), d / 2, z0, h - z0, wall)
    iw, idp = w / 2 - 0.5, d / 2 - 0.5
    bbox(f"{s.name}_band", B.P(0, 0.08, 0.3), (2 * iw, 0.16, 0.6), "#FFFFFF", bev=0.05)
    K.trims(Lw, "lt", -d / 2, idp, h, crown=False)
    K.trims(R, "rt", -idp, d / 2, h, crown=False)
    if wains:
        K.wainscot(B, "bk", -iw, iw, wains_h, wains)
        K.wainscot(Lw, "lt", -d / 2, idp, wains_h, wains)
        K.wainscot(R, "rt", -idp, d / 2, wains_h, wains)
    if window:
        K.window(B, "win_", -w / 4, h * 0.55, w / 4 * 0.75, h * 0.34, cols=3, rows=2,
                 glass_name="win", frame_name="winf")
    return B, Lw, R


def _brick_box(s, nm, x, y, w, d, h, col, z0=0.0):
    """Four running-bond walls around a footprint (a house / barn body). The front one (named nm, the old body
    name) is returned as a Wall frame whose windows cut holes in it."""
    W = Wall(s, x, y - d / 2, 0)
    BK.defer_wall(s, W, f"{s.name}_{nm}", -w / 2, w / 2, z0, h - z0, col, room=False)
    BK.defer_wall(s, Wall(s, x, y + d / 2, 180), f"{s.name}_{nm}wb", -w / 2, w / 2, z0, h - z0, col, room=False)
    BK.defer_wall(s, Wall(s, x - w / 2, y, -90), f"{s.name}_{nm}wl", -(d / 2 - 1), d / 2 - 1, z0, h - z0, col,
                  room=False)
    BK.defer_wall(s, Wall(s, x + w / 2, y, 90), f"{s.name}_{nm}wr", -(d / 2 - 1), d / 2 - 1, z0, h - z0, col,
                  room=False)
    return W


def _brick_ground(s):
    """Baseplate under / around the set (farm: green, top at z 0; rooms: a frame of grey or tan baseplate
    around the room footprint, top at -0.2 under the floor plate). The street builds its own."""
    if s.name not in BRICK_BASE:
        return
    x0, x1, y0, y1, col = BRICK_BASE[s.name]
    if s.name == "farm":
        BK.baseplate(f"{s.name}_base", s.P(0, 0, 0), x0, x1, y0, y1, BK.TABLE_Z, 0.0, col)
        return
    if hasattr(s, "room"):
        w, d = s.room
        hx0, hx1, hy0, hy1 = -w / 2 - 0.5, w / 2 + 0.5, -d / 2, d / 2 + 0.5
    else:                                          # hallway: floor + back wall
        hx0, hx1, hy0, hy1 = -30, 30, -10, 11
    zt = BK.BASE_TOP_IN
    rects = [("_base", x0, x1, y0, hy0), ("_base1", x0, x1, hy1, y1), ("_base2", x0, hx0, hy0, hy1),
             ("_base3", hx1, x1, hy0, hy1)]
    for nm, a, b, c, e in rects:
        if b - a >= 1 and e - c >= 1:
            BK.baseplate(f"{s.name}{nm}", s.P(0, 0, 0), a, b, c, e, BK.TABLE_Z, zt, col)


def tree(s, x, y, k=1.0, seed=0):
    K.tree(s, x, y, k, seed=seed)


def house(s, nm, x, y, w, d, h, wall, roof, door="#C0392B", seed=0):
    """Plaster house: overhanging roof with fascia + shingle courses, brick chimney, corner boards,
    foundation, framed windows with sills and shutters, door with casing, knob and a little awning."""
    if BRICK:
        return _brick_house(s, nm, x, y, w, d, h, wall, roof, door)
    box(s, nm, x, y, h / 2, w, d, h, wall)
    oh_w, oh_d, H = w + 2.2, d + 2.8, h * 0.55
    part(f"{s.name}_{nm}_roof", "prism", s.P(x, y, h), (oh_w, oh_d, H), roof)
    D = oh_d / 2
    ang = degrees(atan2(H, D))
    L = sqrt(D * D + H * H)
    rd = K._shade(roof, 0.78)
    for k, f in enumerate((0.2, 0.4, 0.6, 0.8)):
        for sd in (-1, 1):
            yc, zc = y + sd * D * (1 - f), h + H * f
            nx, nz = sd * H / L, D / L
            bbox(f"{s.name}_{nm}sh{k}{sd}", s.P(x, yc + nx * 0.05, zc + nz * 0.05), (oh_w + 0.02, 0.22, 0.07), rd,
                 rot=(-sd * ang, 0, 0), bev=0)
    bbox(f"{s.name}_{nm}ridge", s.P(x, y, h + H), (oh_w + 0.1, 0.5, 0.3), rd, bev=0.06)
    for sd in (-1, 1):
        bbox(f"{s.name}_{nm}fascia{sd}", s.P(x, y + sd * (D - 0.05), h - 0.12), (oh_w + 0.1, 0.22, 0.42),
             "#FFFFFF", bev=0.05)
    # chimney on the back slope
    cx, cy = x + w * 0.28, y + D * 0.35
    ztop = h + H * 1.08
    bbox(f"{s.name}_{nm}chim", s.P(cx, cy, (h + ztop) / 2), (1.5, 1.5, ztop - h), "#A0523D", bev=0.04, tex="brick")
    bbox(f"{s.name}_{nm}chimcap", s.P(cx, cy, ztop + 0.12), (1.85, 1.85, 0.25), "#6B6B6B", bev=0.05)
    # foundation + corner boards
    bbox(f"{s.name}_{nm}found", s.P(x, y, 0.3), (w + 0.3, d + 0.3, 0.6), "#9E9A92", bev=0.05)
    for sx in (-1, 1):
        bbox(f"{s.name}_{nm}cb{sx}", s.P(x + sx * w / 2, y - d / 2, h / 2), (0.45, 0.45, h), "#FFFFFF", bev=0.06)
    W = Wall(s, x, y - d / 2, 0)
    # door (old slab kept by name) + casing, panels, knob; doormat; awning
    fy = y - d / 2 - 0.08
    box(s, nm + "door", x, fy, 2.2, 2.2, 0.2, 4.4, door, bev=0.04)
    K.door(W, nm + "d", 0, 2.2, 4.4, door, slab=False, n0=-0.02)
    bbox(f"{s.name}_{nm}mat", s.P(x, y - d / 2 - 0.9, 0.03), (2.4, 1.2, 0.06), "#7A5A3A", bev=0)
    for sd in (-1, 1):
        bbox(f"{s.name}_{nm}awb{sd}", W.P(sd * 1.6, 0.6, 5.3), (0.2, 1.2, 0.2), "#FFFFFF", bev=0.03)
    bbox(f"{s.name}_{nm}awn", W.P(0, 0.75, 5.6), (3.8, 1.7, 0.2), rd, rot=(14, 0, 0), bev=0.05)
    # windows: glass + frame keep the old names
    for dx in (-w * 0.3, w * 0.3):
        K.window(W, nm + f"wn{dx:.0f}", dx, h * 0.58, 2.4, 2.3, cols=2, rows=2, outside=True,
                 glass_col="#9FC9E6", glass_name=nm + f"w{dx}", frame_name=nm + f"wf{dx}")
        for sd in (-1, 1):
            su = dx + sd * (1.2 + 0.28 + 0.55)
            W.box(nm + f"shut{dx:.0f}{sd}", su, 0.1, h * 0.58, 0.95, 0.12, 2.9, roof, bev=0.03)
            for j in range(3):
                W.box(nm + f"sl{dx:.0f}{sd}{j}", su, 0.17, h * 0.58 - 0.9 + 0.9 * j, 0.7, 0.04, 0.08, rd, bev=0)


def _brick_house(s, nm, x, y, w, d, h, wall, roof, door):
    """Brick house: four running-bond walls (windows cut real holes), a roof of stacked slope bricks with a
    studded ridge, a grey plinth, a door panel with casing, windows with clear panes, shutters, an awning."""
    W = _brick_box(s, nm, x, y, w, d, h, wall)
    oh_w, oh_d = w + 2.2, d + 2.8
    _, zt = BK.roof(f"{s.name}_{nm}_roof", s.P(x, y, h), oh_w, oh_d / 2, h * 0.55, roof)
    rd = K._shade(roof, 0.78)
    cx, cy = x + w * 0.28, y + oh_d / 2 * 0.35
    ztop = h + zt + 0.6
    bbox(f"{s.name}_{nm}chim", s.P(cx, cy, (h + ztop) / 2), (1.5, 1.5, ztop - h), "#A0523D", bev=0.04)
    bbox(f"{s.name}_{nm}chimcap", s.P(cx, cy, ztop + 0.2), (2.0, 2.0, 0.4), "#6B6B6B", bev=0.05)
    bbox(f"{s.name}_{nm}found", s.P(x, y, 0.4), (w + 0.4, d + 0.4, 0.8), "#9E9A92", bev=0.05)
    fy = y - d / 2 - 0.08
    box(s, nm + "door", x, fy, 2.2, 2.2, 0.2, 4.4, door, bev=0.04)
    K.door(W, nm + "d", 0, 2.2, 4.4, door, slab=False, n0=-0.02)
    bbox(f"{s.name}_{nm}mat", s.P(x, y - d / 2 - 0.9, 0.1), (2.4, 1.2, 0.2), "#7A5A3A", bev=0.04)
    for sd in (-1, 1):
        bbox(f"{s.name}_{nm}awb{sd}", W.P(sd * 1.6, 0.6, 5.3), (0.2, 1.2, 0.2), "#FFFFFF", bev=0.03)
    bbox(f"{s.name}_{nm}awn", W.P(0, 0.75, 5.6), (3.8, 1.7, 0.2), rd, rot=(14, 0, 0), bev=0.05)
    for dx in (-w * 0.3, w * 0.3):
        K.window(W, nm + f"wn{dx:.0f}", dx, h * 0.58, 2.4, 2.3, cols=2, rows=2, outside=True,
                 glass_col="#9FC9E6", glass_name=nm + f"w{dx}", frame_name=nm + f"wf{dx}")
        for sd in (-1, 1):
            su = dx + sd * (1.2 + 0.28 + 0.55)
            W.box(nm + f"shut{dx:.0f}{sd}", su, 0.1, h * 0.58, 0.95, 0.12, 2.9, roof, bev=0.03)
            for j in range(3):
                W.box(nm + f"sl{dx:.0f}{sd}{j}", su, 0.17, h * 0.58 - 0.9 + 0.9 * j, 0.7, 0.04, 0.08, rd, bev=0)


def desk(s, nm, x, y, col="#C98B4A", seed=0):
    box(s, nm + "top", x, y, 2.4, 3.2, 2.0, 0.25, col, bev=0.06, tex="wood")
    for dx in (-1.3, 1.3):
        box(s, nm + f"leg{dx}", x + dx, y, 1.2, 0.25, 1.6, 2.4, "#6B6B6B", bev=0.04)
    box(s, nm + "shelf", x, y + 0.1, 1.75, 2.4, 1.5, 0.12, "#6B6B6B", bev=0.02)
    box(s, nm + "seat", x, y + 2.0, 1.4, 2.0, 1.6, 0.25, "#2D5BFF", bev=0.06)
    box(s, nm + "back", x, y + 2.8, 2.6, 2.0, 0.2, 2.2, "#2D5BFF", bev=0.06)
    for dx in (-0.8, 0.8):
        for dy in (-0.6, 0.6):
            part(f"{s.name}_{nm}cl{dx}{dy}", "cyl", s.P(x + dx, y + 2.0 + dy, 0.65), (0.14, 0.14, 1.3), "#6B6B6B")
    # clutter on the desk top (z 2.525)
    z = 2.525
    K.stack(s, nm + "bk", x - 0.75, y - 0.2, z, n=1 + seed % 3, seed=seed + 5)
    part(f"{s.name}_{nm}pen", "cyl", s.P(x + 0.7, y - 0.35, z + 0.05), (0.09, 0.09, 1.0), "#F2C230", rot=(0, 90, 20))
    if seed % 3 == 0:
        K.apple(s, nm + "ap", x + 0.9, y + 0.4, z)
    elif seed % 3 == 1:
        bbox(f"{s.name}_{nm}nb", s.P(x + 0.5, y + 0.2, z + 0.03), (1.0, 0.8, 0.06), "#F4F4F4", rot=(0, 0, -8), bev=0)
    else:
        K.pencil_cup(s, nm + "pc", x + 1.0, y + 0.45, z)
    box(s, nm + "bag", x - 0.6, y + 0.2, 2.0, 1.0, 0.9, 0.4, ("#E5262B", "#16A085", "#8E44AD")[seed % 3], bev=0.06)


def crowd_grid(s, x0, x1, ys, z=0.0, hd=0.0, step=3.0):
    for k, y in enumerate(ys):
        x = x0 + (k % 2) * step / 2
        while x <= x1:
            s.crowd.append((s.x + x, y, z if not callable(z) else z(k), hd))
            x += step


def chair(s, nm, x, y, col="#A0663A", face=0):
    """Wooden chair facing -Y (face=0) or +Y (face=180)."""
    sy = -1 if face == 0 else 1
    box(s, nm + "seat", x, y, 1.7, 1.8, 1.8, 0.24, col, bev=0.05, tex="wood")
    for dx in (-0.75, 0.75):
        for dy in (-0.75, 0.75):
            box(s, nm + f"cl{dx}{dy}", x + dx, y + dy, 0.8, 0.2, 0.2, 1.6, K._shade(col, 0.8), bev=0.03)
    box(s, nm + "cback", x, y - sy * 0.82, 3.0, 1.8, 0.2, 2.4, col, bev=0.05, tex="wood")


# ---------------------------------------------------------------- the sets
def home():
    s = Set("home")
    B, Lw, R = room(s, 40, 26, "#C98B4A", "#F6E3C2", window=False)
    # window behind the couch with curtains
    K.window(B, "win_", -12, 6.0, 6.0, 4.2, cols=3, rows=2, glass_name="win", frame_name="winf")
    B.box("rod", -12, 0.5, 8.75, 9.6, 0.12, 0.12, "#5A3A1A", bev=0)
    for sd in (-1, 1):
        B.box(f"curt{sd}", -12 + sd * 4.0, 0.45, 5.9, 1.4, 0.3, 5.8, "#D9534F", bev=0.08, tex="carpet")
    if BRICK:        # a rug of red tiles laid over the studs
        BK.tiles_obj("home_rug", s.P(0, 0, 0), -11, 3, -6.5, 2.5, 0.0, 0.2, 2, 2, ["#E86A5A", "#D85A4C"])
    else:
        box(s, "rug", -4, -2, 0.07, 14, 9, 0.04, "#E86A5A")
    box(s, "couch", -4, 5, 1.2, 10, 3, 2.4, "#3F6FD8", bev=0.12)
    box(s, "couchb", -4, 6.4, 3.0, 10, 1.0, 3.0, "#3F6FD8", bev=0.14)
    for dx in (-5, 5):
        box(s, f"arm{dx}", -4 + dx, 5, 2.0, 1.0, 3, 2.0, "#3456B8", bev=0.12)
    for k, (px, col) in enumerate(((-8.0, "#F2C230"), (0.0, "#F4F4F4"))):
        box(s, f"pillow{k}", px, 5.6, 3.0, 1.5, 0.5, 1.4, col, rot=(-12, 0, 8 - 16 * k), bev=0.2)
    box(s, "tv", -19.3, 0, 3.6, 0.4, 7, 4, "#141414", bev=0.05)
    bbox("home_tvscreen", s.P(-19.08, 0, 3.6), (0.04, 6.5, 3.5), "#1B2A40", bev=0, mat=K.glow(0.35))
    box(s, "tvstand", -19, 0, 1.0, 1.5, 8, 2, "#6B4A2A", bev=0.06)
    K.plant(s, "tvplant", -18.6, 5.4, 0.9)
    box(s, "table", 10, 2, 2.5, 8, 5, 0.3, "#A0663A", bev=0.08)
    for dx in (-3, 3):
        for dy in (-1.8, 1.8):
            box(s, f"tl{dx}{dy}", 10 + dx, 2 + dy, 1.2, 0.3, 0.3, 2.4, "#6B4A2A", bev=0.04)
    # table setting: fruit bowl, plates, mug
    z = 2.65
    part("home_bowl", "frustum", s.P(10, 3.0, z + 0.3), (1.6, 1.6, 0.6), "#F4F4F4", rot=(180, 0, 0))
    for k, (dx, dy, col) in enumerate(((-0.3, 0, "#D62A2A"), (0.3, 0.1, "#F2C230"), (0, -0.25, "#3FA34D"))):
        K.apple(s, f"fruit{k}", 10 + dx, 3.0 + dy, z + 0.45, col)
    for k, px in enumerate((7.8, 12.2)):
        part(f"home_plate{k}", "cyl", s.P(px, 1.0, z + 0.04), (1.3, 1.3, 0.08), "#FFFFFF")
    K.mug(s, "mug", 12.9, 2.4, z, "#E5262B")
    for k, cx in enumerate((7.0, 10.0)):
        chair(s, f"ch{k}", cx, 5.6, face=0)
    box(s, "door", 16, 12.4, 3.2, 3.2, 0.3, 6.4, "#8B5A2B", bev=0.04)
    K.door(B, "doorf", 16, 3.2, 6.4, "#8B5A2B", slab=False, n0=0.05)
    box(s, "fridge", 17, 8, 3.5, 3, 2.5, 7, "#E8EEF2", bev=0.15)
    box(s, "fridgeh", 15.9, 6.72, 4.8, 0.2, 0.2, 1.6, "#9AA3AD", bev=0.04)
    box(s, "fridgeh2", 15.9, 6.72, 2.0, 0.2, 0.2, 1.2, "#9AA3AD", bev=0.04)
    box(s, "fridgeln", 17, 6.74, 3.6, 2.9, 0.04, 0.06, "#B8C0C8")
    # kitchen run on the right wall: base cabinets, marble counter, tile splash, upper cabinets
    R.box("kbase", 1, 0.95, 1.45, 10, 1.9, 2.9, "#F4F1EA", bev=0.05)
    R.box("kslab", 1, 1.05, 3.02, 10.3, 2.1, 0.25, "#EDEDED", bev=0.05, tex="marble")
    R.box("ksplash", 1, 0.04, 4.5, 10, 0.08, 2.7, "#FFFFFF", bev=0, tex="tiles")
    R.box("kupper", 1, 0.6, 7.2, 10, 1.2, 2.4, "#F4F1EA", bev=0.05)
    for k in range(4):
        u = -3.75 + k * 2.5
        R.box(f"kseam{k}", u + 1.25, 1.91, 1.45, 0.06, 0.04, 2.6, "#C9C2B4", bev=0)
        R.box(f"kknob{k}", u + 0.9, 1.95, 2.3, 0.12, 0.1, 0.5, "#9AA3AD", bev=0.02)
        R.box(f"kuseam{k}", u + 1.25, 1.21, 7.2, 0.06, 0.04, 2.2, "#C9C2B4", bev=0)
    K.mug(s, "kmug", 18.6, -2.5, 3.15, "#2D5BFF")
    K.plant(s, "kplant", 18.6, 2.5, 0.55, pot="#2D5BFF", z=3.15)
    # wall decor + shelf + plants + lamp
    K.picture(B, "pic1", -4.5, 6.9, 3.6, 2.6, art="landscape", frame="#5A3A1A")
    K.picture(B, "pic2", -0.4, 7.0, 1.8, 2.3, art="abstract", frame="#2B2B2B")
    K.picture(B, "pic3", 1.5, 6.7, 1.2, 1.6, art="portrait", frame="#C9A24A")
    K.clock(B, "clock", 3.3, 7.4, 0.85)
    K.bookshelf(B, "shelf", 8.5, 5.0, 7.0, 1.4, shelves=4, seed=3)
    K.globe(s, "shglobe", 7.4, 11.8, 7.2)
    K.tall_plant(s, "fplant", 4.2, 11.0, 0.9)
    part("home_lamppole", "cyl", s.P(-11.4, 6.2, 3.0), (0.16, 0.16, 6.0), "#3A3F47")
    part("home_lampfoot", "cyl", s.P(-11.4, 6.2, 0.1), (1.2, 1.2, 0.2), "#3A3F47")
    part("home_lampshade", "frustum", s.P(-11.4, 6.2, 6.3), (1.8, 1.8, 1.2), "#FFF1D6", mat=K.glow(1.0))
    K.ceiling_panels(s, (-4, 10), (1,), 10, w=2.4, round_=True)
    s.spot("couch", -5, 4.2, 1.0, 0)
    s.spot("couch2", -2, 4.2, 1.0, 0)
    s.spot("center", -4, 0, 0, 0)
    s.spot("table1", 8, -1.2, 0, 0)
    s.spot("table2", 12, -1.2, 0, 0)
    s.spot("door", 14, 9, 0, 180)
    s.wide = (s.P(2, -22, 8), s.P(2, 3, 3.5), 62)
    return s


def street():
    s = Set("street")
    for i, (x, col, roof) in enumerate(((-22, "#8FD0FF", "#6B4F3A"), (-6, "#FFE066", "#3A6FD8"),
                                        (10, "#FF9EC7", "#7A4A9E"), (26, "#B7E37A", "#C0392B"))):
        house(s, f"h{i}", x, 14, 13, 8, 8, col, roof, seed=i)
        # path to the door, bushes under the windows, a mailbox
        if BRICK:
            BK.tiles_obj(f"street_h{i}path", s.P(x, 0, 0), -1.5, 1.5, 4.0, 10.0, 0.0, 0.2, 1, 2,
                         ["#CFC8BB", "#BDB5A6"], stagger=True)
        else:
            box(s, f"h{i}path", x, 7.0, 0.04, 2.4, 6.0, 0.08, "#CFC8BB")
        for sd in (-1, 1):
            K.bush(s, f"h{i}bush{sd}", x + sd * 4.0, 8.9, 0.8, seed=i * 2 + sd)
        if i in (0, 2):
            K.mailbox(s, f"h{i}mail", x + 2.6, 4.6, ("#2D5BFF", "#E5262B", "#2B2B2B", "#2ECC40")[i])
    if BRICK:        # green baseplates, light-grey studded sidewalks, a smooth dark-grey tiled road
        BK.baseplate("street_base", s.P(0, 0, 0), -44, 44, 4, 40, BK.TABLE_Z, 0.0, GREEN)
        BK.baseplate("street_base2", s.P(0, 0, 0), -44, 44, -36, -13, BK.TABLE_Z, 0.0, GREEN)
        BK.plate_obj("street_walk", s.P(0, 0, 0), -44, 44, 0, 4, BK.TABLE_Z, 0.0, LGREY, kind="base")
        BK.plate_obj("street_walk2", s.P(0, 0, 0), -44, 44, -13, -10, BK.TABLE_Z, 0.0, LGREY, kind="base")
        BK.tiles_obj("street_road", s.P(0, 0, 0), -44, 44, -10, 0, BK.TABLE_Z, 0.0, 8, 5, [DGREY, "#4F5358"])
        box(s, "curb", 0, -0.5, 0.2, 88, 1.0, 0.4, LGREY, bev=0.05)
        box(s, "curb2", 0, -9.5, 0.2, 88, 1.0, 0.4, LGREY, bev=0.05)
        for x in range(-33, 34, 6):
            box(s, f"line{x}", x, -5, 0.05, 3.0, 0.5, 0.1, "#F4F4F4", bev=0.02)
    else:
        box(s, "walk", 0, 2, 0.05, 70, 4, 0.1, "#C8C8C8")
        box(s, "curb", 0, -0.25, 0.15, 70, 0.5, 0.3, "#BDBAB2", bev=0.06)
        box(s, "curb2", 0, -9.75, 0.15, 70, 0.5, 0.3, "#BDBAB2", bev=0.06)
        box(s, "walk2", 0, -11.5, 0.05, 70, 3, 0.1, "#C8C8C8", tex="cobble")
        box(s, "road", 0, -5, 0.03, 70, 9, 0.06, "#4D4D4D")
        for x in range(-33, 34, 6):
            box(s, f"line{x}", x, -5, 0.07, 2.5, 0.25, 0.02, "#FFFFFF")
    K.fence(s, "fence", -34, 34, 5.4, gaps=((-22, 1.6), (-6, 1.6), (10, 1.6), (26, 1.6)))
    for x in (-14, 2, 18):
        tree(s, x, 8, 1.0, seed=x)
    for k, (x, y, kk) in enumerate(((-34, 26, 1.4), (-24, 30, 1.6), (-12, 25, 1.3), (-2, 31, 1.7), (8, 26, 1.4),
                                    (19, 30, 1.6), (30, 25, 1.4), (38, 31, 1.5))):
        tree(s, x, y, kk, seed=k + 7)
    for k, x in enumerate((-15, 15)):
        K.street_lamp(s, f"lamp{k}", x, 4.4)
    K.hydrant(s, "hydrant", -31, 0.7)
    box(s, "stop_pole", 22, 0.5, 3, 0.3, 0.3, 6, "#9A9A9A")
    box(s, "stop_sign", 22, 0.5, 6.2, 2.2, 0.15, 1.2, "#2D5BFF", bev=0.05)
    text(f"{s.name}_stoptxt", "BUS", s.P(22, 0.38, 6.2), 0.8, "#FFFFFF")
    box(s, "bench", 25, 1, 1.0, 4, 1.2, 0.3, "#8B5A2B", bev=0.05)
    box(s, "benchbk", 25, 1.55, 1.9, 4, 0.15, 1.0, "#8B5A2B", bev=0.04, tex="planks")
    for dx in (-1.6, 1.6):
        box(s, f"benchft{dx}", 25 + dx, 1.1, 0.45, 0.2, 1.0, 0.9, "#3A3F47", bev=0.03)
    for i, x in enumerate((-20, -10, 0, 10, 20)):
        s.spot(f"walk{i}", x, 2, 0, 0)
    s.spot("busstop", 24, 1.5, 0, 0)
    s.spot("door1", -6, 9.2, 0, 0)
    s.spot("door2", 10, 9.2, 0, 0)
    s.spot("roof1", -6, 14, 10.5, 0)
    crowd_grid(s, -30, 30, (0.5, 3.5), 0, 0, 3.0)
    s.wide = (s.P(0, -24, 7), s.P(0, 6, 5), 64)
    s.slide = (s.P(-14, -10, 6), s.P(-14, 3, 3.6), 54, (10, 0, 0))
    return s


def classroom():
    s = Set("classroom")
    B, Lw, R = room(s, 40, 30, "#D9B98A", "#F2EBDD", window=False, wains="#A9CDB9")
    # windows down the right wall (u = -y)
    for k, y in enumerate((8, -1, -10)):
        K.window(R, f"rwin{k}", -y, 6.0, 5.0, 4.2, cols=2, rows=2, glass_name="win" if k == 0 else None,
                 frame_name="winf" if k == 0 else None)
    K.plant(s, "sillplant", 19.1, -1, 0.42, z=3.62)
    box(s, "board", 0, 14.4, 6, 16, 0.2, 5, "#2F5D3A")
    box(s, "boardf", 0, 14.45, 6, 16.6, 0.15, 5.6, "#8B5A2B", bev=0.06)
    text(f"{s.name}_boardtxt", "QUIZ TODAY", s.P(0, 14.25, 6.6), 1.2, "#FFFFFF")
    text(f"{s.name}_boardtxt2", "2 + 2 = ?", s.P(-4, 14.27, 4.8), 0.7, "#F4F0D8")
    text(f"{s.name}_boardtxt3", "A B C", s.P(4.6, 14.27, 4.8), 0.7, "#F7E36B")
    box(s, "tray", 0, 14.1, 3.3, 16, 0.6, 0.14, "#8B5A2B", bev=0.04)
    for k, (cx, col) in enumerate(((-5, "#FFFFFF"), (-4.4, "#F7E36B"), (3.5, "#FF9EC7"))):
        part(f"{s.name}_chalk{k}", "cyl", s.P(cx, 14.0, 3.43), (0.1, 0.1, 0.6), col, rot=(0, 90, 0))
    box(s, "eraser", 5.5, 14.0, 3.5, 1.0, 0.4, 0.25, "#3A4A6B", bev=0.04)
    # back wall: bulletin board, posters, clock, bookcases
    B.box("cork", -12.6, 0.08, 5.9, 4.4, 0.16, 3.4, "#C9A06B", bev=0.03)
    B.box("corkf", -12.6, 0.05, 5.9, 4.8, 0.1, 3.8, "#8B5A2B", bev=0.04)
    for k, (du, dz, col, rz) in enumerate(((-1.3, 0.7, "#FFF6A6", 4), (0.2, 0.8, "#FFFFFF", -3), (1.4, 0.5, "#B7E3FF", 6),
                                           (-1.0, -0.8, "#FFB7D5", -5), (0.7, -0.7, "#C8F2B0", 3))):
        bbox(f"classroom_note{k}", B.P(-12.6 + du, 0.2, 5.9 + dz), (1.1, 0.03, 1.3), col, rot=(0, rz, 0), bev=0)
        part(f"classroom_pin{k}", "sphere", B.P(-12.6 + du, 0.26, 5.9 + dz + 0.5), (0.16, 0.16, 0.16), "#E5262B")
    K.picture(B, "pREAD", -17.2, 6.2, 2.2, 3.0, art="poster", body="READ\nMORE", frame="#2D5BFF", ink="#E5262B")
    K.picture(B, "pKIND", 14.2, 6.3, 2.6, 3.2, art="poster", body="BE\nKIND", frame="#F2C230", ink="#2D5BFF")
    K.clock(B, "clock", 10.6, 7.6, 0.85)
    K.bookshelf(B, "lowshelf", -12.6, 4.6, 2.9, 1.3, shelves=2, seed=11)
    K.bookshelf(B, "tallshelf", 17.0, 3.6, 6.6, 1.4, shelves=4, seed=12)
    # teacher's desk with clutter, chair, bin
    box(s, "tdesk", 8, 10, 2.2, 6, 3, 0.3, "#A0663A", bev=0.06, tex="wood")
    box(s, "tdeskb", 8, 10, 1.1, 5.6, 2.6, 2.2, "#8B5A2B", bev=0.05)
    for k in range(2):
        box(s, f"tdrw{k}", 10.0, 8.68, 1.55 - k * 0.9, 1.6, 0.06, 0.7, "#7A4A22", bev=0.02)
        box(s, f"tdrwk{k}", 10.0, 8.62, 1.55 - k * 0.9, 0.5, 0.08, 0.12, "#C9A24A", bev=0.02)
    z = 2.35
    K.apple(s, "tapple", 5.9, 9.3, z)
    K.stack(s, "tbooks", 10.2, 10.4, z, n=3, seed=4, w=1.3, d=0.95)
    K.pencil_cup(s, "tcup", 10.6, 9.2, z)
    K.laptop(s, "tlap", 7.9, 9.9, z)
    K.globe(s, "tglobe", 5.8, 10.9, z)
    K.mug(s, "tmug", 9.2, 9.0, z, "#2ECC40")
    box(s, "tchairs", 8, 12.6, 1.6, 2.0, 2.0, 0.3, "#2B2B2B", bev=0.08)
    box(s, "tchairb", 8, 13.5, 3.0, 2.0, 0.3, 2.4, "#2B2B2B", bev=0.1)
    part("classroom_tchairp", "cyl", s.P(8, 12.6, 0.8), (0.25, 0.25, 1.5), "#9AA3AD")
    part("classroom_tchairf", "cyl", s.P(8, 12.6, 0.08), (1.8, 1.8, 0.16), "#2B2B2B")
    part("classroom_bin", "frustum", s.P(12.6, 9.4, 0.8), (1.3, 1.3, 1.6), "#4C7BD9", rot=(180, 0, 0))
    K.tall_plant(s, "cplant", -17.6, 12.4, 0.9)
    for r, y in enumerate((-6, 1)):
        for c, x in enumerate((-10, -2, 6)):
            desk(s, f"d{r}{c}", x, y, seed=r * 3 + c)
            s.spot(f"desk{r * 3 + c + 1}", x, y + 1.8, 0.0, 0)
    # classroom door on the left wall (u = y), next to the "door" spot
    K.door(Lw, "cdoor", 8, 3.4, 7.0, "#A0663A", glass=True, side=-1)
    K.picture(Lw, "pMAP", -3, 6.2, 5.0, 3.2, art="landscape", frame="#2B2B2B")
    K.ceiling_grid(s, 40, 30, 10)
    K.ceiling_panels(s, (-10, 0, 10), (-6, 4), 10, w=3.6, d=1.8)
    s.spot("front", 2, 9, 0, 0)
    s.spot("teacher", 8, 7.4, 0, 0)
    s.spot("door", -17, 8, 0, 90)
    crowd_grid(s, -14, 14, (-10, -3, 4), 0, 0, 3.4)
    s.wide = (s.P(0, -24, 9), s.P(0, 2, 3), 62)
    s.slide = (s.P(-10, -16, 6), s.P(-10, 0, 3.5), 52, (12, 0, 0))
    return s


def hallway():
    s = Set("hallway")
    W = Wall(s, 0, 10, 0)
    if BRICK:
        _brick_floor(s, -30, 30, -10, 10, "#BFC6CF")
    else:
        box(s, "floor", 0, 0, 0, 60, 20, 0.1, "#BFC6CF")
    gaps = {-6: "trophy", -5: "trophy", -4: "trophy", 9: "office", 10: "office", 11: "office"}
    for i in range(-14, 15):
        if i in gaps:
            continue
        col = ("#D9322B", "#2F5FD0")[(i // 4) % 2]
        dk = K._shade(col, 0.72)
        x = i * 2
        box(s, f"lk{i}", x, 9.5, 3.5, 1.9, 1.0, 7, col, bev=0.05)
        for j, z in enumerate((5.6, 5.85, 6.1)):
            box(s, f"lkv{i}" + ("" if j == 0 else "abc"[j]), x, 8.97, z + 0.2, 1.1, 0.06, 0.09, "#1A1A1A")
        for j, z in enumerate((1.0, 1.25)):
            box(s, f"lkvb{i}{j}", x, 8.97, z, 1.1, 0.06, 0.09, "#1A1A1A")
        box(s, f"lkh{i}", x + 0.6, 8.9, 3.7, 0.14, 0.14, 0.8, "#C8CDD3", bev=0.03)
        box(s, f"lkn{i}", x, 8.96, 6.75, 0.45, 0.04, 0.22, "#E8E8E8", bev=0)
        box(s, f"lkk{i}", x, 9.5, 0.22, 2.0, 1.04, 0.44, "#2B2B2B", bev=0.03)
        box(s, f"lkc{i}", x, 9.45, 7.1, 2.0, 1.14, 0.22, dk, bev=0.04)
    if BRICK:
        BK.defer_wall(s, W, "hallway_wall", -30, 30, BK.BASE_TOP_IN, 12 - BK.BASE_TOP_IN, "#F2EBDD", front=20)
    else:
        box(s, "wall", 0, 10.5, 6, 60, 1, 12, "#F2EBDD")
    box(s, "stripe", 0, 9.96, 7.7, 60, 0.08, 0.5, "#2F5FD0")
    W.box("hbase", 0, 0.08, 0.3, 60, 0.16, 0.6, "#FFFFFF", bev=0.05)
    W.box("hcrown", 0, 0.12, 11.8, 60, 0.24, 0.4, "#FFFFFF", bev=0.06)
    if REAL:
        box(s, "ceil", 0, 0, 12, 60, 22, 0.2, "#EEEEEC", tex="plaster").visible_shadow = False
    # trophy case in the gap at x -12..-8
    W.box("tcase", -10, 0.7, 1.5, 5.8, 1.4, 3.0, "#7A4A22", bev=0.05, tex="wood")
    W.box("tcaseback", -10, 0.1, 5.0, 5.8, 0.2, 4.0, "#1E2A5A", bev=0)
    W.box("tcasetop", -10, 0.7, 7.1, 6.0, 1.4, 0.25, "#7A4A22", bev=0.05, tex="wood")
    for sd in (-1, 1):
        W.box(f"tcaseside{sd}", -10 + sd * 2.9, 0.7, 5.0, 0.2, 1.4, 4.2, "#7A4A22", bev=0.04, tex="wood")
    W.box("tcaseshelf", -10, 0.7, 5.0, 5.6, 1.2, 0.1, "#E8E8E8", bev=0)
    for k, (du, z, sz) in enumerate(((-1.8, 3.05, 1.0), (0, 3.05, 1.4), (1.8, 3.05, 0.9), (-1.0, 5.05, 0.9),
                                     (1.0, 5.05, 1.1))):
        part(f"hallway_tr{k}b", "cyl", W.P(du, 0.7, z + 0.15), (0.6, 0.6, 0.3), "#3A2A1A")
        part(f"hallway_tr{k}s", "cyl", W.P(du, 0.7, z + 0.3 + 0.35 * sz), (0.14, 0.14, 0.7 * sz), "#E8B931",
             mat=K.metal())
        part(f"hallway_tr{k}c", "frustum", W.P(du, 0.7, z + 0.3 + 0.7 * sz + 0.3 * sz), (0.75 * sz, 0.75 * sz, 0.6 * sz),
             "#E8B931", rot=(180, 0, 0), mat=K.metal())
    # principal's office door, set flush on the wall now that the lockers make room for it
    box(s, "office", 20, 9.8, 3.4, 4, 0.4, 6.8, "#8B5A2B", bev=0.04)
    K.door(W, "offd", 20, 4.0, 6.8, "#8B5A2B", slab=False, glass=True, n0=0.2)
    W.box("offplaque", 20, 0.08, 7.95, 5.0, 0.12, 1.1, "#1E2A5A", bev=0.04)
    text(f"{s.name}_offtxt", "PRINCIPAL", s.P(20, 9.84, 7.95), 0.7, "#FFFFFF")
    # wall above the lockers: banner, posters, clock, exit sign
    W.box("banner", 0, 0.1, 9.6, 12, 0.08, 1.9, "#F2C230", bev=0.02)
    W.box("bannerb", 0, 0.06, 9.6, 12.4, 0.06, 2.3, "#2F5FD0", bev=0.02)
    W.label("bannertxt", "GO TIGERS!", 0, 0.16, 9.6, 1.1, "#2F5FD0")
    K.picture(W, "pRUN", -14, 9.6, 2.6, 2.6, art="poster", body="NO\nRUNNING", frame="#E5262B", ink="#1E2A5A")
    K.picture(W, "pREAD", 13.6, 9.6, 2.6, 2.6, art="poster", body="READ!", frame="#2ECC40", ink="#8E44AD")
    K.clock(W, "clock", 8.4, 9.7, 0.75)
    W.box("exitbox", -22, 0.2, 10.6, 2.2, 0.3, 0.9, "#F4F4F4", bev=0.04)
    ex = W.label("exittxt", "EXIT", -22, 0.37, 10.6, 0.6, "#FF2A2A")
    if REAL:
        ex.material_slots[0].link = "OBJECT"
        ex.material_slots[0].material = K.glow(3.0)
    K.tall_plant(s, "hplant", 27.5, 8.3, 0.9)
    K.ceiling_grid(s, 60, 22, 12)
    K.ceiling_panels(s, (-24, -12, 0, 12, 24), (1.5,), 12, w=3.6, d=1.8)
    for i, x in enumerate((-20, -10, 0, 10, 20)):
        s.spot(f"spot{i}", x, 3, 0, 0)
    s.spot("office", 20, 6, 0, 0)
    crowd_grid(s, -26, 26, (1, 5), 0, 0, 3.2)
    s.wide = (s.P(0, -20, 7), s.P(0, 5, 4), 62)
    s.slide = (s.P(-14, -9, 6), s.P(-14, 5, 3.8), 52, (12, 0, 0))
    return s


def cafeteria():
    s = Set("cafeteria")
    B, Lw, R = room(s, 56, 36, "#E3D9C6", "#F7E7A8", window=False, wains="#FFFFFF", wains_h=3.0, wains_tex="tiles")
    for k, u in enumerate((-20.5, 20.5)):
        K.window(B, f"bwin{k}", u, 6.0, 5.0, 4.6, cols=2, rows=2, glass_name="win" if k == 0 else None,
                 frame_name="winf" if k == 0 else None)
    box(s, "counter", 0, 15, 2.2, 30, 3, 4.4, "#B0B8C0", bev=0.06)
    box(s, "cslab", 0, 14.9, 4.5, 30.6, 3.4, 0.25, "#E6E6E6", bev=0.05, tex="marble")
    box(s, "cstripe", 0, 13.47, 3.2, 30, 0.06, 0.5, "#E5262B")
    box(s, "ckick", 0, 13.6, 0.3, 30, 0.3, 0.6, "#5A6068", bev=0.03)
    for k, x in enumerate(range(-12, 13, 3)):
        food = ("#F2C230", "#D9534F", "#5DAA4A", "#8B5A2B", "#F4E3B0")[k % 5]
        box(s, f"pan{k}", x, 15.0, 4.75, 2.4, 1.8, 0.3, "#C8CDD3", bev=0.04)
        box(s, f"food{k}", x, 15.0, 4.9, 2.1, 1.5, 0.12, food, bev=0.05)
    B.box("splash", 0, 0.04, 6.0, 32, 0.08, 1.6, "#FFFFFF", bev=0, tex="tiles")
    B.box("menu", 0, 0.12, 8.0, 14, 0.24, 2.9, "#1F2A2A", bev=0.05)
    B.box("menuf", 0, 0.06, 8.0, 14.5, 0.12, 3.3, "#8B5A2B", bev=0.04)
    B.label("menut", "TODAY:  PIZZA  -  TACOS  -  SALAD", 0, 0.3, 8.0, 0.62, "#F7E36B")
    K.clock(B, "clock", -10.5, 8.1, 0.8)
    K.picture(B, "pEAT", 10.6, 7.9, 2.6, 2.6, art="poster", body="EAT\nGREEN", frame="#2ECC40", ink="#2ECC40")
    # bins under the right window, vending machine on the left wall
    for k, (x, col) in enumerate(((19.4, "#2F5FD0"), (21.6, "#2ECC40"))):
        box(s, f"bin{k}", x, 16.1, 1.3, 1.9, 1.9, 2.6, col, bev=0.1)
        box(s, f"binlid{k}", x, 16.1, 2.7, 2.0, 2.0, 0.22, "#2B2B2B", bev=0.06)
    Lw.box("vend", 12, 1.1, 3.4, 3.4, 2.2, 6.8, "#C0392B", bev=0.1)
    Lw.box("vendglass", 11.6, 2.22, 4.1, 2.2, 0.06, 4.6, "#CFE7F5", bev=0, mat=K.glass_in())
    for r in range(4):
        for c in range(3):
            Lw.box(f"snack{r}{c}", 11.0 + c * 0.6, 2.28, 2.5 + r * 1.1, 0.42, 0.05, 0.55,
                   ("#F2C230", "#2D5BFF", "#2ECC40", "#FF7A1A")[(r + c) % 4], bev=0)
    Lw.box("vendpad", 13.3, 2.22, 4.6, 0.5, 0.06, 1.2, "#2B2B2B", bev=0.02)
    Lw.box("vendslot", 11.6, 2.22, 1.1, 2.0, 0.08, 0.5, "#1A1A1A", bev=0.02)
    K.picture(Lw, "pMENU", 0, 6.4, 3.0, 3.6, art="abstract", frame="#2D5BFF")
    K.tall_plant(s, "cplant", 25.6, 15.4, 0.9)
    for c, x in enumerate((-18, -6, 6, 18)):
        for r, y in enumerate((-8, 2)):
            box(s, f"t{c}{r}", x, y, 2.4, 9, 3.4, 0.3, "#3FA9F5", bev=0.08)
            for dx in (-3.2, 3.2):
                part(f"cafeteria_tp{c}{r}{dx}", "cyl", s.P(x + dx, y, 1.15), (0.3, 0.3, 2.3), "#9AA3AD")
            for dy in (-2.5, 2.5):
                box(s, f"b{c}{r}{dy}", x, y + dy, 1.2, 9, 1.0, 0.25, "#2D5BFF", bev=0.05)
                for dx in (-3.6, 3.6):
                    part(f"cafeteria_bp{c}{r}{dy}{dx}", "cyl", s.P(x + dx, y + dy, 0.55), (0.24, 0.24, 1.1), "#9AA3AD")
            for t, dx in enumerate((-2.6, 0.4, 3.0)):
                tc = ("#FF7A1A", "#2ECC40", "#E5262B")[(c + r + t) % 3]
                ty = y + (0.7 if t % 2 else -0.7)
                box(s, f"tray{c}{r}{t}", x + dx, ty, 2.6, 1.7, 1.2, 0.1, tc, bev=0.04)
                box(s, f"meal{c}{r}{t}", x + dx - 0.3, ty, 2.72, 0.7, 0.6, 0.14, "#F2C230", bev=0.06)
                part(f"cafeteria_milk{c}{r}{t}", "cube", s.P(x + dx + 0.5, ty, 2.95), (0.4, 0.4, 0.6), "#F4F4F4")
    K.ceiling_grid(s, 56, 36, 10)
    K.ceiling_panels(s, (-18, -6, 6, 18), (-10, 0, 10), 10, w=3.6, d=1.8)
    for r, y in enumerate((-12, -4.5, 5.5)):
        for c, x in enumerate((-22, -14, -6, 2, 10, 18, 24)):
            s.crowd.append((s.x + x, y, 0, 0))
    for i, (x, y) in enumerate(((-6, -11), (6, -11), (-18, -11), (18, -11), (0, 9))):
        s.spot(f"spot{i}", x, y, 0, 0)
    s.spot("counter", 0, 12, 0, 0)
    s.wide = (s.P(0, -32, 10), s.P(0, 2, 3), 64)
    s.slide = (s.P(-18, -24, 8), s.P(-18, 0, 3), 52, (14, 0, 0))
    return s


def gym():
    s = Set("gym")
    B, Lw, R = room(s, 64, 40, "#D9A35E", "#F0E6D2", h=14, window=False, wains="#3A62C9", wains_h=4.0)
    for k in range(4):
        y0 = 7.5 + 2 * k
        box(s, f"bl{k}", 0, (y0 + 19.5) / 2, 0.4 * (k + 1), 40, 19.5 - y0, 0.8 * (k + 1),
            "#8A8F98" if k % 2 else "#9EA3AC")
        box(s, f"seat{k}", 0, y0 + 0.25, 0.8 * (k + 1) + 0.1, 40, 0.5, 0.2, "#C98B4A", bev=0.05, tex="planks")
    for sd in (-1, 1):
        for k in range(4):
            part(f"gym_railp{sd}{k}", "cyl", s.P(sd * 20.3, 8.0 + 2 * k, 0.8 * (k + 1) + 1.2), (0.16, 0.16, 2.4),
                 "#C8CDD3", mat=K.metal())
        bbox(f"gym_rail{sd}", s.P(sd * 20.3, 11.0, 4.4), (0.16, 6.6, 0.16), "#C8CDD3", rot=(21.8, 0, 0),
             bev=0, mat=K.metal())
    # court markings
    for k, (x, y, sx, sy) in enumerate(((0, -18, 56, 0.25), (0, 6, 56, 0.25), (-28, -6, 0.25, 24), (28, -6, 0.25, 24),
                                        (0, -6, 0.25, 24))):
        box(s, f"court{k}", x, y, 0.06, sx, sy, 0.02, "#FFFFFF")
    part("gym_circle", "cyl", s.P(0, -6, 0.06), (6.8, 6.8, 0.02), "#FFFFFF")
    part("gym_circlein", "cyl", s.P(0, -6, 0.07), (6.3, 6.3, 0.02), "#2F5FD0")
    for sd in (-1, 1):
        box(s, f"key{sd}", sd * 24, -6, 0.06, 8, 8, 0.02, "#2F5FD0")
        box(s, f"keyl{sd}", sd * 20, -6, 0.075, 0.25, 8, 0.02, "#FFFFFF")
    # hoops on both side walls (u = y on the left, u = -y on the right)
    for nm, Wl, u in (("hoopL", Lw, -6), ("hoopR", R, 6)):
        Wl.box(nm + "arm", u, 1.5, 10.6, 0.3, 3.0, 0.3, "#3A3F47", bev=0.03)
        Wl.box(nm + "brace", u, 1.2, 9.6, 0.25, 2.4, 0.25, "#3A3F47", bev=0.03)
        Wl.box(nm + "board", u, 3.1, 10.3, 6.0, 0.2, 3.6, "#FFFFFF", bev=0.06)
        Wl.box(nm + "sq", u, 3.22, 9.9, 2.2, 0.04, 1.6, "#E5262B", bev=0)
        Wl.box(nm + "sqi", u, 3.25, 9.9, 1.8, 0.04, 1.2, "#FFFFFF", bev=0)
        part(f"gym_{nm}rim", "ring", Wl.P(u, 3.95, 8.8), (1.7, 1.7, 1.7), "#FF6A00", rot=(90, 0, 0))
        part(f"gym_{nm}net", "frustum", Wl.P(u, 3.95, 8.1), (1.5, 1.5, 1.3), "#F4F4F4", rot=(180, 0, 0))
    # scoreboard, champion banners, high windows
    B.box("score", 0, 0.25, 10.4, 10, 0.5, 4.0, "#1A1A1A", bev=0.08)
    B.label("scoreh", "HOME   GUEST", 0, 0.55, 11.5, 0.75, "#FFFFFF")
    sc = B.label("scored", "12     10", 0, 0.55, 9.8, 1.5, "#FF3B2F")
    if REAL:
        sc.material_slots[0].link = "OBJECT"
        sc.material_slots[0].material = K.glow(3.0)
    for k, (u, col, body) in enumerate(((-21, "#E5262B", "2025\nCHAMPS"), (-15.5, "#2F5FD0", "GO\nTIGERS"),
                                        (15.5, "#F2C230", "STATE\nFINALS"), (21, "#2ECC40", "2024\nCHAMPS"))):
        B.box(f"ban{k}", u, 0.08, 10.2, 3.6, 0.1, 4.4, col, bev=0.02)
        part(f"gym_bant{k}", "prism", B.P(u, 0.08, 8.0), (0.1, 3.6, 1.5), col, rot=(180, 0, 90))
        B.label(f"bantx{k}", body, u, 0.16, 10.4, 0.8, "#FFFFFF")
    for k, u in enumerate((-27, -9, 9, 27)):
        K.window(B, f"hwin{k}", u, 12.0, 4.0, 1.8, cols=2, rows=1, sill=False)
    # double door on the right wall at y = -2 (u = 2) with an exit sign
    K.door(R, "gdoorA", 1.0, 2.0, 7.4, "#7E8A96", glass=True, side=-1)
    K.door(R, "gdoorB", 3.0, 2.0, 7.4, "#7E8A96", glass=True, side=1)
    R.box("gexit", 2, 0.2, 8.6, 2.2, 0.3, 0.9, "#F4F4F4", bev=0.04)
    ex = R.label("gexittxt", "EXIT", 2, 0.37, 8.6, 0.6, "#FF2A2A")
    if REAL:
        ex.material_slots[0].link = "OBJECT"
        ex.material_slots[0].material = K.glow(3.0)
    # ball cart
    box(s, "cart", -26, 2.5, 1.0, 3.0, 2.0, 0.2, "#3A3F47", bev=0.03)
    for k, (dx, dy, dz) in enumerate(((-0.8, -0.4, 0), (0.0, -0.4, 0), (0.8, -0.4, 0), (-0.4, 0.4, 0), (0.4, 0.4, 0),
                                      (0.0, 0.0, 0.85))):
        part(f"gym_ball{k}", "sphere", s.P(-26 + dx, 2.5 + dy, 1.55 + dz), (0.95, 0.95, 0.95), "#E8701A")
    for dx in (-1.3, 1.3):
        for dy in (-0.8, 0.8):
            part(f"gym_cartl{dx}{dy}", "cyl", s.P(-26 + dx, 2.5 + dy, 0.5), (0.12, 0.12, 1.0), "#3A3F47")
    if REAL:
        for k, y in enumerate((-14, -6, 6, 14)):
            box(s, f"truss{k}", 0, y, 13.4, 64, 0.5, 0.8, "#5A6068", bev=0.04)
    K.ceiling_panels(s, (-20, -7, 7, 20), (-10, 2), 14, w=2.0, round_=True)
    for k in range(4):
        x = -18
        while x <= 18:
            s.crowd.append((s.x + x, 8.5 + 2 * k, 0.8 * (k + 1), 0))
            x += 3.2
    for i, x in enumerate((-12, -6, 0, 6, 12)):
        s.spot(f"floor{i}", x, -3, 0, 0)
    s.spot("door", 30, -2, 0, -90)
    s.wide = (s.P(0, -24, 8), s.P(0, 6, 4.5), 64)
    s.slide = (s.P(-12, -2, 9), s.P(-12, 12, 5.5), 50, (10, 0, 0))
    return s


def museum():
    s = Set("museum")
    B, Lw, R = room(s, 60, 40, "#E8E2D6", "#C9B79C", h=14, window=False, wains="#EFE6D2", wains_h=3.6)
    B.box("plaque", 0, 0.06, 11.0, 25, 0.12, 2.6, "#F3E7CF", bev=0.04)
    B.box("plaquef", 0, 0.03, 11.0, 25.6, 0.06, 3.2, "#C9A24A", bev=0.03)
    text(f"{s.name}_title", "HALL OF FAILED JOKES", s.P(0, 19.3, 11), 1.6, "#5A3A1A")
    # pilasters
    for k, u in enumerate((-14.5, 14.5, -28.2, 28.2)):
        B.box(f"pilb{k}", u, 0.4, 0.5, 2.2, 0.8, 1.0, "#F4EFE6", bev=0.06)
        B.box(f"pils{k}", u, 0.3, 6.8, 1.5, 0.6, 11.6, "#F4EFE6", bev=0.08)
        B.box(f"pilc{k}", u, 0.45, 12.9, 2.3, 0.9, 0.7, "#F4EFE6", bev=0.08)
        for f in (-0.45, 0, 0.45):
            B.box(f"pilf{k}{f}", u + f, 0.62, 6.8, 0.14, 0.06, 10.6, "#E2DACB", bev=0)
    # paintings with little track lights
    for k, (u, w, h, art, fr) in enumerate(((-8.6, 4.6, 3.4, "landscape", "#C9A24A"), (0, 3.0, 3.6, "portrait", "#C9A24A"),
                                            (8.6, 4.6, 3.4, "abstract", "#2B2B2B"), (-21.5, 4.4, 3.4, "portrait", "#C9A24A"),
                                            (21.5, 4.4, 3.4, "landscape", "#C9A24A"))):
        K.picture(B, f"art{k}", u, 7.3, w, h, art=art, frame=fr)
        part(f"museum_spot{k}", "frustum", B.P(u, 1.2, 9.6), (0.45, 0.45, 0.7), "#2B2B2B", rot=(40, 0, 0))
    for Wl, nm in ((Lw, "L"), (R, "R")):
        K.picture(Wl, f"sart{nm}", 0, 7.0, 5.0, 3.6, art="landscape" if nm == "L" else "abstract", frame="#C9A24A")
    for r, y in enumerate((-6, 0, 6, 12)):
        x = -21 + (r % 2) * 1.75
        while x <= 21:
            box(s, f"ped{r}{x:.1f}", x, y, 0.5, 2.6, 2.6, 1.0, "#F4F4F4", bev=0.05)
            box(s, f"pedc{r}{x:.1f}", x, y, 0.93, 2.9, 2.9, 0.14, "#E9E4DA", bev=0.04)
            box(s, f"pedp{r}{x:.1f}", x, y - 1.32, 0.5, 1.0, 0.05, 0.36, "#C9A24A", bev=0)
            s.crowd.append((s.x + x, y, 1.0, 0))
            x += 3.5
    for sd in (-1, 1):
        K.tall_plant(s, f"mplant{sd}", sd * 26.5, 16.5, 1.0, pot="#3A3F47")
    K.ceiling_panels(s, (-18, -6, 6, 18), (-10, 4), 14, w=6.0, d=3.0)
    for i, x in enumerate((-4.5, 0, 4.5)):
        s.spot(f"floor{i}", x, -12, 0, 0)
    s.wide = (s.P(0, -32, 10), s.P(0, 4, 4), 64)
    s.slide = (s.P(-14, -16, 7), s.P(-14, 2, 3.5), 52, (12, 0, 0))
    return s


def farm():
    s = Set("farm")
    if BRICK:
        _brick_box(s, "barn", 0, 20, 18, 10, 14, "#C0392B")
        BK.roof(f"{s.name}_barnroof", s.P(0, 20, 14), 20.4, 6.2, 6, "#6B4F3A")
    else:
        box(s, "barn", 0, 20, 7, 18, 10, 14, "#C0392B")
        part(f"{s.name}_barnroof", "prism", s.P(0, 20, 14), (20.4, 12.4, 6), "#6B4F3A")
    for sd in (-1, 1):
        box(s, f"barnfascia{sd}", 0, 20 + sd * 6.15, 13.9, 20.5, 0.22, 0.4, "#F4F4F4", bev=0.05)
        box(s, f"barncb{sd}", sd * 9, 15, 7, 0.5, 0.5, 14, "#F4F4F4", bev=0.06)
    box(s, "barndoor", 0, 14.9, 4, 7, 0.3, 8, "#F4F4F4", bev=0.05)
    for sd in (-1, 1):
        box(s, f"barnx{sd}", 0, 14.72, 4, 0.4, 0.08, 10.4, "#B03028", rot=(0, sd * 41, 0))
    box(s, "barndf", 0, 14.8, 8.1, 7.6, 0.3, 0.4, "#B03028", bev=0.04)
    box(s, "barndm", 0, 14.72, 4, 0.2, 0.08, 7.8, "#B03028")
    box(s, "loft", 0, 14.9, 11.2, 3.2, 0.3, 3.0, "#F4F4F4", bev=0.05)
    for sd in (-1, 1):
        box(s, f"loftx{sd}", 0, 14.72, 11.2, 0.3, 0.08, 3.8, "#B03028", rot=(0, sd * 45, 0))
    if BRICK:
        BK.silo(f"{s.name}_silo", s.P(14, 23, 0), 3.0, 16, "#B8BEC4", "#8E969E")
    else:
        part(f"{s.name}_silo", "cyl", s.P(14, 23, 8), (6, 6, 16), "#B8BEC4", mat=K.metal())
        part(f"{s.name}_silotop", "sphere", s.P(14, 23, 16), (6.2, 6.2, 4.4), "#8E969E", mat=K.metal())
    for k, z in enumerate((3, 7, 11, 15)):
        part(f"{s.name}_siloband{k}", "cyl", s.P(14, 23, z), (6.15, 6.15, 0.25), "#7A828A")
    for x in range(-30, 31, 3):
        box(s, f"fp{x}", x, 13, 1.4, 0.3, 0.3, 2.8, "#F4F4F4", bev=0.04)
    box(s, "fr", 0, 13, 2.2, 61, 0.2, 0.3, "#F4F4F4", bev=0.04)
    box(s, "fr2", 0, 13, 1.1, 61, 0.2, 0.3, "#F4F4F4", bev=0.04)
    for i, x in enumerate((-20, 20)):
        part(f"{s.name}_hay{i}", "cyl", s.P(x, 8, 1.6), (3.2, 3.2, 3.2), "#E8C25A", rot=(90, 0, 0))
        part(f"{s.name}_haycore{i}", "cyl", s.P(x, 6.38, 1.6), (2.2, 2.2, 0.06), "#C9A040", rot=(90, 0, 0))
    for k, (x, y, kk) in enumerate(((-26, 22, 1.4), (-16, 27, 1.6), (27, 21, 1.3), (32, 28, 1.6), (-34, 28, 1.5),
                                    (4, 32, 1.7))):
        tree(s, x, y, kk, seed=k + 3)
    for k, x in enumerate((-12, 9)):
        K.bush(s, f"fbush{k}", x, 15.6, 1.0, seed=k)
    crowd_grid(s, -24, 24, (-2, 2, 6, 10), 0, 0, 3.0)
    for i, x in enumerate((-8, 0, 8)):
        s.spot(f"field{i}", x, -8, 0, 0)
    s.wide = (s.P(0, -30, 9), s.P(0, 5, 4), 64)
    s.slide = (s.P(-14, -14, 6), s.P(-14, 3, 3.5), 52, (12, 0, 0))
    return s


def sky():
    s = Set("sky")
    for i, (x, y, z, k) in enumerate(((-14, 6, 10, 1.2), (0, 10, 12, 1.6), (14, 6, 10, 1.3), (-6, -2, 6, 1.0),
                                      (8, -4, 7, 1.1), (22, 12, 13, 1.4), (-24, 12, 13, 1.3))):
        for j, (dx, dz, r) in enumerate(((0, 0, 4), (3, 0.6, 3), (-3, 0.4, 3), (1, 1.6, 2.6))):
            part(f"{s.name}_cl{i}{j}", "sphere", s.P(x + dx * k, y, z + dz * k), (r * k * 1.6, r * k, r * k), "#FFFFFF")
    box(s, "roof", 0, 4, 5.0, 40, 16, 0.4, "#9A9A9A")
    for r, y in enumerate((0, 6)):
        x = -16
        while x <= 16:
            s.crowd.append((s.x + x, y, 5.2 + 1.5 * ((x + r) % 3), 0))
            x += 3.4
    for i, x in enumerate((-8, 0, 8)):
        s.spot(f"roof{i}", x, -2, 5.2, 0)
    s.wide = (s.P(0, -28, 12), s.P(0, 4, 8), 64)
    s.slide = (s.P(-12, -14, 10), s.P(-12, 2, 8), 52, (12, 0, 0))
    return s


BUILDERS = {"home": home, "street": street, "classroom": classroom, "hallway": hallway,
            "cafeteria": cafeteria, "gym": gym, "museum": museum, "farm": farm, "sky": sky}


def build(names):
    if BRICK:            # sets on baseplates on a wooden tabletop; printed sky cards behind outdoor sets
        BK.table()
        out = {}
        for n in names:
            s = BUILDERS[n]()
            _brick_ground(s)
            BK.finish_set(s)
            if n in ("street", "farm", "sky"):
                BK.card(f"{n}_backdrop", s.P(0, 44 if n != "sky" else 34, BK.TABLE_Z), 150, 48, seed=len(n))
            out[n] = s
        print(f"[brick] sets {list(out)}: {BK.STATS['studs']} studs on {BK.STATS['objects']} stud grids")
        return out
    gm = core.grass_material()
    ground = core.bpy.data.objects.new("ground", MESH["cube"].copy())
    ground.data.materials[0] = gm
    COLL.objects.link(ground)
    ground.location, ground.scale = (540, 0, -0.5), (1400, 300, 1)
    return {n: BUILDERS[n]() for n in names}
