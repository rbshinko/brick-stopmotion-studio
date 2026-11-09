"""Hand props for the cast (runs inside Blender), plus the phone-screen picture (run with plain Python:
`python engine/props.py` writes assets/props/phone_chat.png with PIL).

A held prop is built in its hand's GRIP space: up = -Y, front (the side the viewer reads) = -Z, x = across.
The rig turns each grip so a held prop stays upright and faces forward whatever the arm does, so these
builders never think about poses. Staging: `form hold_phone`, `hold_phone+cash_l` (_l = the other hand),
`hold_backpack:#E5262B` (a colour), `wear_backpack` (same thing). See STAGING.md for the list."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
MILO = os.path.dirname(HERE)
SCREEN_PNG = os.path.join(MILO, "assets", "props", "phone_chat.png")

# hand props (built on a grip) and body props (built on the body); names are what staging writes
HAND_PROPS = ["phone", "plate", "sandwich", "test", "cash", "cookie", "slice", "book", "trophy", "clock", "mic",
              "lunchbox", "tissue"]
BODY_PROPS = ["backpack", "beanbag", "hamster"]


# ---------------------------------------------------------------- picture (plain Python + PIL)
def make_screen_png(path=SCREEN_PNG):
    """A chat on a phone: header with a contact, grey and blue bubbles with text lines, a typing dot row."""
    from PIL import Image, ImageDraw
    W, H, S = 360, 640, 3
    im = Image.new("RGB", (W * S, H * S), (16, 18, 28))
    d = ImageDraw.Draw(im)

    def R(x0, y0, x1, y1, r, fill):
        d.rounded_rectangle((x0 * S, y0 * S, x1 * S, y1 * S), radius=r * S, fill=fill)

    for y in range(H):                                    # soft vertical gradient
        c = (int(18 + 10 * y / H), int(20 + 8 * y / H), int(34 + 18 * y / H))
        d.rectangle((0, y * S, W * S, (y + 1) * S), fill=c)
    R(0, 0, W, 92, 0, (34, 38, 58))                       # header
    d.ellipse((20 * S, 22 * S, 68 * S, 70 * S), fill=(255, 122, 26))
    R(84, 32, 200, 46, 7, (235, 238, 245))
    R(84, 54, 150, 64, 5, (120, 200, 140))
    R(300, 36, 336, 58, 10, (80, 140, 255))
    y = 120
    for side, w, lines in (("L", 230, 2), ("R", 200, 1), ("L", 170, 1), ("R", 250, 3), ("L", 210, 2)):
        h = 26 + 22 * lines
        if side == "L":
            x0, col, ink = 18, (58, 62, 80), (205, 210, 225)
        else:
            x0, col, ink = W - 18 - w, (46, 120, 255), (225, 236, 255)
        R(x0, y, x0 + w, y + h, 20, col)
        for k in range(lines):
            lw = w - 36 if k < lines - 1 else (w - 36) * 0.62
            R(x0 + 18, y + 15 + 22 * k, x0 + 18 + lw, y + 27 + 22 * k, 6, ink)
        y += h + 16
    R(18, y, 98, y + 40, 20, (58, 62, 80))                # typing...
    for k in range(3):
        d.ellipse(((34 + 22 * k) * S, (y + 14) * S, (46 + 22 * k) * S, (y + 26) * S), fill=(205, 210, 225))
    R(14, H - 64, W - 74, H - 18, 23, (40, 44, 62))       # input bar + send
    d.ellipse(((W - 64) * S, (H - 66) * S, (W - 14) * S, (H - 16) * S), fill=(46, 120, 255))
    im = im.resize((W, H), Image.LANCZOS)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path)
    return path


# ---------------------------------------------------------------- Blender side
_MESH = {}
_MAT = {}


def _screen_material():
    import bpy
    if "screen" in _MAT:
        return _MAT["screen"]
    m = bpy.data.materials.new("PhoneScreen")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.02, 0.02, 0.03, 1)
    b.inputs["Roughness"].default_value = 0.15
    b.inputs["Emission Strength"].default_value = 1.6
    if os.path.exists(SCREEN_PNG):
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(SCREEN_PNG, check_existing=True)
        uv = nt.nodes.new("ShaderNodeTexCoord")
        nt.links.new(uv.outputs["UV"], tex.inputs["Vector"])
        nt.links.new(tex.outputs["Color"], b.inputs["Emission Color"])
    else:
        b.inputs["Emission Color"].default_value = (0.25, 0.45, 1.0, 1)
    _MAT["screen"] = m
    return m


def _screen_mesh():
    """A unit plane facing -Z (the grip's front), UVs upright for a viewer in front (up = -Y)."""
    import bpy, bmesh
    if "screen" in _MESH:
        return _MESH["screen"]
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    vs = [bm.verts.new(p) for p in ((-0.5, 0.5, 0), (0.5, 0.5, 0), (0.5, -0.5, 0), (-0.5, -0.5, 0))]
    f = bm.faces.new(vs)
    bm.normal_update()
    if f.normal.z > 0:
        f.normal_flip()
    for lp in f.loops:
        x, y, _ = lp.vert.co
        lp[uvl].uv = (x + 0.5, 0.5 - y)
    me = bpy.data.meshes.new("screen")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(_screen_material())
    _MESH["screen"] = me
    return me


def _wedge_mesh():
    """Pizza-slice wedge: crust edge at y 0 (x -0.5..0.5), tip at y -1, 1 thick in z (centred)."""
    import bpy, bmesh
    import core
    if "wedge" in _MESH:
        return _MESH["wedge"]
    bm = bmesh.new()
    ring = []
    for z in (-0.5, 0.5):
        ring.append([bm.verts.new(p) for p in ((-0.5, 0, z), (0.5, 0, z), (0, -1, z))])
    bm.faces.new(ring[0][::-1]); bm.faces.new(ring[1])
    for i in range(3):
        j = (i + 1) % 3
        bm.faces.new((ring[0][i], ring[0][j], ring[1][j], ring[1][i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.04, segments=2, affect="EDGES", clamp_overlap=True)
    me = core.finish(bm, "wedge", smooth_=True)
    _MESH["wedge"] = me
    return me


def _text(name, body, loc, size, color, parent):
    import core
    ob = core.text(name, body, loc, size, color, rot=(180, 0, 0))
    ob.data.extrude = 0.015
    ob.parent = parent
    ob.location = loc
    return ob


def _fist(nm, ch, hand, g, style, zc=-0.1, t=0.1, bottom=0.12):
    """The closed mitten that holds a prop, built on the grip (so it stays upright with the prop). While a hand
    holds something the rig hides its open mitten and shows this instead (core.Char.write_outfits); the parts
    carry ob["fist"] so they take the hand's colour (skin, stone grey, ghost alpha).
    One smooth toy mitten closed round the prop (the held part disappears into it) + one rounded thumb:
    rod   : a handle runs up through the fist at x = z = 0; the thumb wraps over the front at the top.
    pinch : a flat prop stands in the plane z = zc (thickness t) with its bottom edge at y = bottom: the mitten
            swallows that edge (mostly behind it, a thin lip in front), the thumb pressed on the front face.
    palm  : a fist under the prop (plates): the prop rests on its top."""
    import core
    part = core.part
    inner = -1 if hand == 0 else 1            # thumb side, same as the open mitten's thumb
    sk = ch.skin
    F = []

    def add(k, loc, size, rot=(0, 0, 0), soft=0.4):
        ob = part(f"{nm}_fist{k}", core.soft_box(*size, k=soft), loc, size, sk, g, rot=rot)
        ob["fist"] = hand
        F.append(ob)

    if style in ("rod", "palm"):
        add("p", (-0.04 * inner, 0.0, 0.06), (0.84, 0.74, 0.8), soft=0.42)                     # the closed mitten
        add("t", (0.08 * inner, -0.25, -0.36), (0.52, 0.24, 0.26), rot=(0, 0, -14 * inner), soft=0.49)  # thumb
    else:                                                                                     # pinch
        zb = zc + t / 2                       # back face of the prop
        zf = zc - t / 2                       # front face
        z0, z1 = zf - 0.07, zb + 0.5          # a thin lip in front, the bulk of the hand behind
        add("p", (-0.04 * inner, bottom - 0.02, (z0 + z1) / 2), (0.84, 0.56, z1 - z0), soft=0.42)
        add("t", (0.2 * inner, bottom - 0.3, zf - 0.11), (0.26, 0.46, 0.2), rot=(0, 0, 16 * inner), soft=0.49)
    return F


def _seat(P, dy, dz):
    """Slide a prop built in the old grip layout so its held edge sits in the fist."""
    for ob in P:
        ob.location = (ob.location[0], ob.location[1] + dy, ob.location[2] + dz)
    return P


# how each prop is held: style, (dy, dz) to seat the old layout in the fist, (zc, t, bottom) for a pinch
HOLD = {"phone": ("pinch", (0.09, 0.32)), "test": ("pinch", (0.17, 0.32)), "cash": ("pinch", (0.46, 0.28)),
        "cookie": ("pinch", (0.18, 0.32)), "slice": ("pinch", (0.24, 0.3)), "book": ("pinch", (0.13, 0.3)),
        "clock": ("pinch", (0.32, 0.26)), "tissue": ("pinch", (0.22, 0.3)), "plate": ("palm", (0.0, 0.0)),
        "sandwich": ("palm", (0.0, 0.0)), "trophy": ("rod", (0.0, 0.0)), "mic": ("rod", (0.0, 0.0)),
        "lunchbox": ("rod", (0.0, 0.0))}
THICK = {"phone": 0.11, "test": 0.03, "cash": 0.24, "cookie": 0.14, "slice": 0.17, "book": 0.28, "clock": 0.36,
         "tissue": 0.04}


def hand_prop(kind, ch, hand=0, col=None):
    """Objects for one held prop on ch.grip[hand] (the prop first, then the fist holding it); None if `kind` is
    not a hand prop."""
    import core
    part = core.part
    g = ch.grip[hand]
    nm = f"{ch.name}_{kind}" + ("_l" if hand else "")
    P = []
    if kind == "phone":
        P.append(part(nm, "bcube", (0, -0.5, -0.42), (0.62, 1.06, 0.11), col or "#24252E", g))
        P.append(part(nm + "scr", _screen_mesh(), (0, -0.5, -0.48), (0.52, 0.9, 1), "#FFFFFF", g, shadow=False))
        P.append(part(nm + "cam", "cyl", (0.17, -0.9, -0.36), (0.12, 0.12, 0.04), "#111111", g, rot=(0, 0, 0)))
    elif kind in ("plate", "sandwich"):           # resting on the fist's top (y -0.36)
        P.append(part(nm, "cyl", (0, -0.4, 0), (1.6, 1.6, 0.07), "#F6F6F4", g, rot=(90, 0, 0)))
        P.append(part(nm + "rim", "frustum", (0, -0.46, 0), (1.5, 1.5, 0.06), "#E3E8EE", g, rot=(-90, 0, 0)))
        for k, (dy, sz, c) in enumerate(((-0.56, (0.98, 0.17, 0.82), "#E9B66A"), (-0.66, (1.06, 0.06, 0.9), "#5FBF3A"),
                                          (-0.71, (1.0, 0.06, 0.86), "#F7C948"), (-0.77, (0.98, 0.07, 0.84), "#F08A9A"),
                                          (-0.88, (0.98, 0.18, 0.82), "#E9B66A"))):
            P.append(part(nm + f"s{k}", "bcube", (0, dy, 0), sz, c, g, rot=(0, 8 if k == 2 else 0, 0)))
    elif kind == "test":                                   # graded test paper, big red A+ circled
        P.append(part(nm, "bcube", (0, -0.78, -0.42), (1.12, 1.46, 0.03), "#FBFBF6", g))
        P.append(part(nm + "nm", "bcube", (-0.22, -1.38, -0.44), (0.5, 0.06, 0.01), "#3A3A44", g))
        for k in range(5):
            P.append(part(nm + f"ln{k}", "bcube", (-0.06, -1.12 + 0.17 * k, -0.44), (0.82, 0.035, 0.01), "#9CC3F0", g))
            P.append(part(nm + f"ck{k}", "bcube", (0.42, -1.1 + 0.17 * k, -0.445), (0.12, 0.035, 0.01), "#E0262B", g,
                          rot=(0, 0, -40)))
        P.append(_text(nm + "aplus", "A+", (0.2, -1.22, -0.46), 0.5, "#E0262B", g))
        P.append(part(nm + "ring", "ring", (0.2, -1.22, -0.45), (0.78, 1, 0.62), "#E0262B", g, rot=(90, 0, 0)))
    elif kind == "cash":
        P.append(part(nm, "bcube", (0, -0.6, -0.38), (1.04, 0.52, 0.24), col or "#69C26E", g))
        P.append(part(nm + "f", "bcube", (0, -0.6, -0.51), (0.94, 0.42, 0.01), "#9BE09F", g))
        P.append(part(nm + "band", "bcube", (0, -0.6, -0.38), (0.24, 0.56, 0.28), "#F3E5BE", g))
        for s in (-1, 1):
            P.append(part(nm + f"fan{s}", "bcube", (0.12 * s, -0.68, -0.25), (1.04, 0.52, 0.02), "#5BB461", g,
                          rot=(0, 0, 14 * s)))
        P.append(_text(nm + "usd", "$", (-0.3, -0.6, -0.53), 0.3, "#2E7D32", g))
    elif kind == "cookie":
        P.append(part(nm, "cyl", (0, -0.45, -0.42), (0.78, 0.78, 0.14), "#D9A055", g))
        for k, (x, y) in enumerate(((-0.2, -0.36), (0.18, -0.42), (0.02, -0.62), (-0.22, -0.7), (0.22, -0.72))):
            P.append(part(nm + f"c{k}", "sphere", (x, y, -0.5), (0.13, 0.13, 0.07), "#4A2A14", g))
    elif kind == "slice":
        P.append(part(nm, _wedge_mesh(), (0, -0.22, -0.4), (1.0, 1.25, 0.09), "#F7C948", g))
        P.append(part(nm + "crust", "bcube", (0, -0.22, -0.4), (1.1, 0.2, 0.17), "#D08A35", g))
        for k, (x, y) in enumerate(((-0.17, -0.55), (0.16, -0.62), (0.0, -0.95))):
            P.append(part(nm + f"p{k}", "cyl", (x, y, -0.45), (0.24, 0.24, 0.03), "#C0392B", g))
    elif kind == "book":
        c = col or "#C0392B"
        P.append(part(nm, "bcube", (0, -0.62, -0.4), (0.92, 1.22, 0.28), c, g))
        P.append(part(nm + "pg", "bcube", (0.05, -0.62, -0.4), (0.86, 1.14, 0.22), "#FFF8E8", g))
        P.append(part(nm + "t", "bcube", (0, -0.86, -0.545), (0.6, 0.14, 0.01), "#F7D23E", g))
        P.append(part(nm + "t2", "bcube", (0, -0.66, -0.545), (0.42, 0.06, 0.01), "#F7D23E", g))
    elif kind == "trophy":                         # held by the stem: cup above the fist, base below it
        gold = col or "#F2C230"
        P.append(part(nm, "cyl", (0, 0, 0), (0.24, 0.24, 1.08), gold, g, rot=(90, 0, 0)))
        P.append(part(nm + "base", "bcube", (0, 0.56, 0), (0.78, 0.26, 0.66), "#5A3A22", g))
        P.append(part(nm + "cup", "frustum", (0, -0.86, 0), (1.0, 1.0, 0.68), gold, g, rot=(-90, 0, 0)))
        for s in (-1, 1):
            P.append(part(nm + f"h{s}", "ring", (0.52 * s, -0.92, 0), (0.42, 0.9, 0.42), gold, g, rot=(90, 0, 0)))
        P.append(part(nm + "star", "star", (0, -0.84, -0.44), (0.34, 0.6, 0.34), "#FFFFFF", g, rot=(90, 0, 0)))
    elif kind == "clock":
        c = col or "#E5262B"
        P.append(part(nm, "cyl", (0, -0.72, -0.36), (0.92, 0.92, 0.36), c, g))
        P.append(part(nm + "face", "cyl", (0, -0.72, -0.55), (0.74, 0.74, 0.03), "#FAFAF5", g))
        P.append(part(nm + "hh", "bcube", (0.08, -0.78, -0.575), (0.2, 0.05, 0.01), "#111111", g, rot=(0, 0, 30)))
        P.append(part(nm + "mh", "bcube", (0, -0.86, -0.575), (0.04, 0.3, 0.01), "#111111", g))
        for s in (-1, 1):
            P.append(part(nm + f"bell{s}", "sphere", (0.3 * s, -1.16, -0.36), (0.36, 0.3, 0.36), "#F2C230", g))
            P.append(part(nm + f"ft{s}", "bcube", (0.28 * s, -0.28, -0.36), (0.12, 0.16, 0.12), "#333333", g))
        P.append(part(nm + "ham", "bcube", (0, -1.22, -0.36), (0.1, 0.22, 0.1), "#333333", g))
    elif kind == "mic":
        # a handheld stage mic: black tapered handle through the fist, silver collar, dark mesh grille ball
        hcol, gcol, lcol = (col, col, "#A8A8A8") if col else ("#1C1C21", "#33363D", "#A9AEB8")
        P.append(part(nm, "frustum", (0, -0.05, 0), (0.36, 0.36, 1.16), hcol, g, rot=(-90, 0, 0)))
        P.append(part(nm + "band", "cyl", (0, -0.66, 0), (0.42, 0.42, 0.12), lcol, g, rot=(90, 0, 0)))
        P.append(part(nm + "head", "sphere", (0, -0.94, 0), (0.62, 0.62, 0.62), gcol, g))
        for k, (dy, r) in enumerate(((0.0, 0.64), (-0.15, 0.56), (0.15, 0.56))):      # grille seams
            P.append(part(nm + f"gr{k}", "cyl", (0, -0.94 + dy, 0), (r, r, 0.025), lcol, g, rot=(90, 0, 0)))
        P.append(part(nm + "grv", "ring", (0, -0.94, 0), (0.64, 0.5, 0.64), lcol, g, rot=(0, 0, 90)))
    elif kind == "lunchbox":                       # carried by the top handle, the box hanging below the fist
        P.append(part(nm, "bcube", (0, 0.74, 0), (1.1, 0.8, 0.5), col or "#3FA9F5", g))
        P.append(part(nm + "h", "bcube", (0, 0, 0), (0.5, 0.12, 0.12), "#2B2B2B", g))
        P.append(part(nm + "lid", "bcube", (0, 0.36, 0), (1.14, 0.06, 0.54), "#F7D23E", g))
    elif kind == "tissue":
        P.append(part(nm, "bcube", (0, -0.8, -0.4), (0.62, 1.4, 0.04), "#FFFFFF", g, rot=(0, 0, 6)))
    else:
        return None
    style, (dy, dz) = HOLD[kind]
    _seat(P, dy, dz)
    if style == "pinch":
        return P + _fist(nm, ch, hand, g, "pinch", zc=-0.1, t=THICK[kind], bottom=0.12)
    return P + _fist(nm, ch, hand, g, style)


def body_prop(kind, ch, col=None):
    """Objects for a prop worn/stuck on the body; None if `kind` is not a body prop."""
    import core
    part = core.part
    nm = f"{ch.name}_{kind}"
    b = ch.body
    if kind == "backpack":
        c = col or "#2D5BFF"
        P = [part(nm, "bcube", (0, 0.86, 1.05), (1.64, 0.72, 1.76), c, b),
             part(nm + "pk", "bcube", (0, 1.27, 0.7), (1.2, 0.26, 0.74), c, b),
             part(nm + "zip", "bcube", (0, 1.41, 0.92), (0.9, 0.02, 0.05), "#F2F2F2", b),
             part(nm + "hdl", "bcube", (0, 0.86, 2.0), (0.5, 0.14, 0.14), "#1E1E24", b)]
        for s in (-1, 1):
            P.append(part(nm + f"st{s}", "bcube", (0.56 * s, -0.53, 1.15), (0.24, 0.06, 1.75), "#1E1E24", b))
            P.append(part(nm + f"top{s}", "bcube", (0.56 * s, 0.17, 1.99), (0.24, 1.36, 0.06), "#1E1E24", b))
        return P
    if kind == "beanbag":
        return [part(nm, "sphere", (0.2, 1.2, 0.6), (3.0, 2.4, 2.2), col or "#8E44AD", b)]
    if kind == "hamster":
        return [part(nm, "bcube", (-0.9, -0.6, 2.4), (0.7, 0.6, 0.5), "#D9A35E", b),
                part(nm + "e", "sphere", (-0.9, -0.92, 2.5), (0.12, 0.08, 0.12), "#111111", b)]
    return None


def build(kind, ch, col=None):
    """kind as staging writes it ('phone', 'cash_l'); returns objects, or None if it is not a prop."""
    hand = 0
    if kind.endswith("_l"):
        kind, hand = kind[:-2], 1
    else:                     # the 2nd hand prop of a combo (hold_cookie+slice) goes in the other hand
        for o in getattr(ch, "outfits", {}).values():
            held = [a.partition(":")[0] for a in o.get("acc", [])]
            held = [a for a in held if a in HAND_PROPS]
            if kind in held and held.index(kind) > 0:
                hand = 1
    if kind in BODY_PROPS:
        return body_prop(kind, ch, col)
    return hand_prop(kind, ch, hand, col)


if __name__ == "__main__":
    print(make_screen_png())
