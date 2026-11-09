"""Our original toy brick figure (MILO_LOOK=brick), built for core.Char with the same parts, joints and names.

NOT a minifigure: a rounded-box head (no cylinder, no stud) on a short neck peg, a straight rounded-rectangle
torso (no taper), a visible peg-joint waist over a hip block, one rounded block per leg with a moulded shoe,
bendable two-part arms with a ball shoulder and elbow, and mitten hands with a thumb (no clip hands). Hair is a
separate moulded piece; clothes details are flat prints on the torso (jacket, tee, pendant, tie ...).

Proportions (body space; the body empty sits at world z 2, so feet are at body z -2): hip block -0.5..0,
waist peg, torso 0.14..1.82, neck 1.82, head 1.45 tall (~27% of the 5.4-unit figure, hair adds ~0.7).
Edges get small crisp bevels (~0.3 mm at a 4 cm toy), not soft clay rounding.

Everything here runs inside Blender and is only called by core.py when core.BRICK is true."""
import os
import bpy, bmesh
from math import radians, sin, cos, pi

import core                                     # partially initialised when core imports us: use at call time

# ---------------------------------------------------------------- proportions (shared with core)
HW, HDP, HH = 1.6, 1.38, 1.5                  # head width / depth / height
HC = (0, 0, 0.85)                               # head centre in neck space (neck peg 0..0.14 shows below)
NECK_Z = 1.82                                   # neck (torso top) in body space
ARM = (0.5, 0.7, 0.48)                          # ELBOW, FOREARM, HAND
SHX, SHZ = 1.2, 1.48                           # shoulder pivots
GRIP_SCALE = 0.7                                # props/fists were sized for the bigger R6 mitten
TORSO = (1.78, 1.0, 1.68)
TZ0 = 0.14                                      # torso bottom (body z); top = NECK_Z
FRONT = -TORSO[1] / 2                           # torso front face (y)
PR = 0.006                                      # print offset off a surface (flush decal, no z-fight)
# face decal: planar from the front, UPX object units per atlas pixel, tile centred at ZC (head space)
UPX = 0.0031
FACE_ZC = -0.10

_MESH = {}


# ---------------------------------------------------------------- meshes
def _ring(bm, sx, sy, r, seg, z):
    out = []
    for k, (cx, cy) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
        ox, oy = cx * (sx / 2 - r), cy * (sy / 2 - r)
        for i in range(seg + 1):
            a = pi / 2 * (k + i / seg)
            out.append(bm.verts.new((ox + r * cos(a), oy + r * sin(a), z)))
    return out


def rbox(sx, sy, sz, rv=0.12, re=0.045, segv=4, sege=2, taper=1.0, unit=True, mat=None, rims="both"):
    """A toy-plastic rounded rectangle block: corners rounded by rv in plan, the top and bottom rims bevelled by re
    (crisp small bevel; rims="top" keeps a sharp bottom edge for shells over a limb). taper scales the top outline
    (skirts). unit=True: shrunk to unit size like core.bevel_box, so part(..., size=(sx, sy, sz)) restores it."""
    key = (round(sx, 3), round(sy, 3), round(sz, 3), round(rv, 3), round(re, 3), segv, sege, round(taper, 3), unit,
           rims)
    if key in _MESH and mat is None:
        return _MESH[key]
    rv = max(0.004, min(rv, 0.49 * min(sx, sy)))
    bm = bmesh.new()
    lo = _ring(bm, sx, sy, rv, segv, -sz / 2)
    hi = _ring(bm, sx * taper, sy * taper, rv * taper, segv, sz / 2)
    n = len(lo)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    bm.faces.new(hi)
    bm.faces.new(lo[::-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if re > 0:
        caps = [f for f in bm.faces if len(f.verts) > 4 and (rims == "both" or f.calc_center_median().z > 0)]
        rims = [e for f in caps for e in f.edges]
        bmesh.ops.bevel(bm, geom=rims, offset=min(re, 0.45 * sz, 0.9 * rv + 0.02), segments=sege, profile=0.5,
                        affect="EDGES", clamp_overlap=True)
    if unit:
        bmesh.ops.scale(bm, vec=(1 / sx, 1 / sy, 1 / sz), verts=bm.verts)
    me = bpy.data.meshes.new("rbox")
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    if hasattr(me, "set_sharp_from_angle"):
        me.set_sharp_from_angle(angle=radians(50))
    me.materials.append(mat or core.MAT_PLAIN)
    if mat is None:
        _MESH[key] = me
    return me


def head_mesh(mat):
    return rbox(HW, HDP, HH, rv=0.36, re=0.2, segv=6, sege=4, unit=False, mat=mat)


def blade():
    """A sculpted hair spike: a 6-sided cone with a blunt tip, smooth but with moulded facets."""
    if "blade" in _MESH:
        return _MESH["blade"]
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=6, radius1=0.5, radius2=0.035, depth=1.0)
    me = bpy.data.meshes.new("blade")
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    if hasattr(me, "set_sharp_from_angle"):
        me.set_sharp_from_angle(angle=radians(70))
    me.materials.append(core.MAT_PLAIN)
    _MESH["blade"] = me
    return me


# ---------------------------------------------------------------- printed face
def head_material():
    """Face prints from work/faces_brick/atlas.png projected flat onto the head front (the per-object "face"
    property picks the row), over the object colour (skin)."""
    node = core.node
    m = bpy.data.materials.new("Head")
    m.use_nodes = True
    nt = m.node_tree
    L = nt.links.new
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.3
    b.inputs["Specular IOR Level"].default_value = 0.5
    path = os.path.join(core.MILO, "work", "faces_brick", "atlas.png")
    if not os.path.exists(path):                       # fall back to the cartoon prints rather than fail
        path = os.path.join(core.MILO, "work", "faces", "atlas.png")
    img = bpy.data.images.load(path)
    img.alpha_mode = "STRAIGHT"
    n_faces = img.size[1] // 578
    wd, hd = 1024 * UPX, 578 * UPX
    tc = node(nt, "ShaderNodeTexCoord")
    sep = node(nt, "ShaderNodeSeparateXYZ")
    L(tc.outputs["Object"], sep.inputs[0])

    def M(op, a, b_=None, c=None):
        n = node(nt, "ShaderNodeMath", operation=op)
        for i, v in enumerate((a, b_, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                L(v, n.inputs[i])
        return n.outputs[0]

    u = M("MULTIPLY_ADD", sep.outputs["X"], 1 / wd, 0.5)
    v = M("MULTIPLY_ADD", sep.outputs["Z"], 1 / hd, 0.5 - FACE_ZC / hd)
    attr = node(nt, "ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="face")
    rev = M("SUBTRACT", float(n_faces - 1), attr.outputs["Fac"])
    va = M("DIVIDE", M("ADD", v, rev), float(n_faces))
    comb = node(nt, "ShaderNodeCombineXYZ")
    L(u, comb.inputs[0]); L(va, comb.inputs[1])
    tex = node(nt, "ShaderNodeTexImage", image=img, extension="EXTEND", interpolation="Linear")
    L(comb.outputs[0], tex.inputs[0])
    inside = M("MULTIPLY", M("MULTIPLY", M("GREATER_THAN", u, 0.0), M("LESS_THAN", u, 1.0)),
               M("MULTIPLY", M("GREATER_THAN", v, 0.0), M("LESS_THAN", v, 1.0)))
    front = M("LESS_THAN", sep.outputs["Y"], -0.2)      # printed on the front only (not through to the back)
    a = M("MULTIPLY", M("MULTIPLY", tex.outputs["Alpha"], inside), front)
    oi = node(nt, "ShaderNodeObjectInfo")
    mix = node(nt, "ShaderNodeMix", data_type="RGBA")
    L(a, mix.inputs["Factor"])
    L(oi.outputs["Color"], mix.inputs[6])
    L(tex.outputs["Color"], mix.inputs[7])
    L(mix.outputs[2], b.inputs["Base Color"])
    L(oi.outputs["Alpha"], b.inputs["Alpha"])
    return m


# ---------------------------------------------------------------- the rig
def build_rig(ch, name, skin):
    """Create every body part of Char ch (same attribute names and part names as the R6 rig)."""
    part, empty, soft_box, band_mesh = core.part, core.empty, core.soft_box, core.band_mesh
    ELBOW, FOREARM, HAND = ARM
    W = "#FFFFFF"
    # torso: a straight rounded rectangle; waist peg + hip block below it
    ch.torso = part(name + "_torso", rbox(*TORSO, rv=0.16, re=0.05), (0, 0, (TZ0 + NECK_Z) / 2), TORSO, W, ch.body)
    ch.neck = empty(name + "_neck", (0, 0, NECK_Z), ch.body)
    ch.head = part(name + "_head", core.MESH["head"], HC, (1, 1, 1), skin, ch.neck)
    ch.head["face"] = 0.0
    ch.neckp = part(name + "_neckp", "cyl", (0, 0, 0.07), (0.64, 0.6, 0.2), skin, ch.neck)
    # arms: ball shoulder (sleeve colour) + upper arm, elbow ball + forearm, mitten + thumb, grip
    ch.sh = [empty(name + "_shp", (SHX, 0, SHZ), ch.body), empty(name + "_shn", (-SHX, 0, SHZ), ch.body)]
    ua = (0.54, 0.58, 0.72)
    ch.arm = [part(name + f"_arm{i}", rbox(*ua, rv=0.22, re=0.06), (0, 0, -0.2), ua, skin, s)
              for i, s in enumerate(ch.sh)]
    sv = (0.58, 0.62, 0.62)                             # the shoulder: one rounded cap (sleeve colour)
    ch.sleeve = [part(name + f"_slv{i}", rbox(*sv, rv=0.27, re=0.22, segv=5, sege=4, rims="top"), (0, 0, -0.06), sv, W, s)
                 for i, s in enumerate(ch.sh)]
    ch.elbow = [empty(name + f"_elb{i}", (0, 0, -ELBOW), s) for i, s in enumerate(ch.sh)]
    fa = (0.5, 0.54, FOREARM + 0.18)
    ch.farm = [part(name + f"_farm{i}", rbox(*fa, rv=0.2, re=0.05), (0, 0, -FOREARM / 2 + 0.09), fa, skin, e)
               for i, e in enumerate(ch.elbow)]
    ch.farm += [part(name + f"_elbb{i}", "sphere", (0, 0, 0), (0.52, 0.56, 0.52), skin, e)
                for i, e in enumerate(ch.elbow)]
    ch.wrist = [empty(name + f"_wr{i}", (0, 0, -FOREARM), e) for i, e in enumerate(ch.elbow)]
    ch.hand, ch.grip = [], []
    for i, w in enumerate(ch.wrist):
        inner = -1 if i == 0 else 1                     # thumb on the inner-front corner
        ch.hand.append(part(name + f"_hand{i}", soft_box(0.56, 0.5, 0.5, k=0.42), (0, -0.02, -0.22),
                            (0.56, 0.5, 0.5), skin, w))
        ch.hand.append(part(name + f"_thumb{i}", soft_box(0.18, 0.2, 0.32, k=0.48), (0.25 * inner, -0.2, -0.13),
                            (0.18, 0.2, 0.32), skin, w, rot=(-12, 0, 16 * inner)))
        g = empty(name + f"_grip{i}", (0, -0.07, -HAND / 2), w)
        g.scale = (GRIP_SCALE,) * 3
        ch.grip.append(g)
    # legs: one rounded block per leg on a hip pivot under the hip block, a moulded shoe with a sole
    ch.hip = [empty(name + "_hipp", (0.45, 0, -0.3), ch.body), empty(name + "_hipn", (-0.45, 0, -0.3), ch.body)]
    lg = (0.86, 0.96, 1.42)
    ch.leg = [part(name + f"_leg{i}", rbox(*lg, rv=0.14, re=0.05), (0, 0, -0.65), lg, skin, h)
              for i, h in enumerate(ch.hip)]
    pt = (0.874, 0.974, 0.62)
    ch.pant = [part(name + f"_pnt{i}", rbox(*pt, rv=0.15, re=0.05, rims="top"), (0, 0, -0.35), pt, W, h)
               for i, h in enumerate(ch.hip)]
    hipb = (1.78, 1.0, 0.5)
    ch.pant.append(part(name + "_pelvis", rbox(*hipb, rv=0.16, re=0.05), (0, 0, -0.25), hipb, W, ch.body))
    ch.pant.append(part(name + "_waist", "cyl", (0, 0, 0.07), (1.42, 0.72, 0.18), W, ch.body))
    ch.shoe, ch.sole = [], []
    sh_ = (0.88, 1.18, 0.32)
    for i, h in enumerate(ch.hip):
        ch.shoe.append(part(name + f"_shoe{i}", rbox(*sh_, rv=0.16, re=0.06), (0, -0.1, -1.5), sh_, W, h))
        ch.sole += [part(name + f"_sole{i}", rbox(0.91, 1.21, 0.07, rv=0.17, re=0.02), (0, -0.1, -1.66),
                         (0.91, 1.21, 0.07), "#F4F4F4", h),
                    part(name + f"_toe{i}", rbox(0.66, 0.03, 0.1, rv=0.01, re=0.0), (0, -0.69 - PR, -1.56),
                         (0.66, 0.03, 0.1), "#F4F4F4", h)]
    # crew neckline: a low moulded collar ring round the neck peg
    ch.collar = part(name + "_collar", band_mesh(r=0.4, h=0.06, th=0.12), (0, 0, NECK_Z - 0.01), (1, 1, 1), W,
                     ch.body)


# ---------------------------------------------------------------- hair pieces (one moulded piece each)
def hair_parts(style, col, parent, nm):
    part = core.part
    h = []
    hx, hy, hz = HC
    k = [0]

    def add(mesh, loc, size, rot=(0, 0, 0), name=None):
        if name is None:
            name = f"{nm}_hl{k[0]}"
            k[0] += 1
        h.append(part(name, mesh, (hx + loc[0], hy + loc[1], hz + loc[2]), size, col, parent, rot=rot))
        return h[-1]

    def cap(sz=(1.7, 1.52, 0.6), z=0.5, name=None):
        return add(rbox(*sz, rv=0.44, re=0.24, segv=5, sege=3), (0, 0.02, z), sz, name=name or nm + "_hair")

    def back(z=0.16, sz=(1.7, 0.56, 1.1)):
        add(rbox(*sz, rv=0.26, re=0.16, sege=3), (0, 0.44, z), sz)

    def fringe(xs, z=0.42, size=(0.66, 0.3, 0.36), tilt=-22, sweep=-14):
        for i, x in enumerate(xs):
            add("sphere", (x, -0.66 - 0.02 * (i % 2), z - 0.03 * (i % 2)), size, rot=(tilt, sweep, sweep * 0.6))

    if style == "afro":
        add("sphere", (0, 0.12, 0.42), (2.1, 1.95, 1.5), name=nm + "_afro")
        for i in range(8):
            a = 2 * pi * i / 8
            add("sphere", (0.82 * cos(a), 0.12 + 0.7 * sin(a), 0.62 + 0.1 * (i % 2)), (0.9, 0.9, 0.8))
        add("sphere", (0, 0.08, 1.02), (1.3, 1.2, 0.66))
        return h
    cap()
    if style not in ("milo",):
        back()
    if style == "short":
        add(rbox(1.66, 0.34, 0.3, rv=0.14, re=0.1), (0, -0.62, 0.48), (1.66, 0.34, 0.3), rot=(-14, 0, 0))
        fringe((-0.36, 0.0, 0.36), size=(0.6, 0.26, 0.3))
        for s in (-1, 1):
            add(rbox(0.16, 0.52, 0.5, rv=0.07, re=0.05), (0.82 * s, -0.08, 0.22), (0.16, 0.52, 0.5))
        add("cone", (0.14, 0.32, 0.86), (0.32, 0.3, 0.34), rot=(-30, 20, 0))       # moulded cowlick
    elif style == "spiky":
        fringe((-0.32, 0.06, 0.4), size=(0.54, 0.26, 0.32))
        for i, (dx, dy, rx, ry) in enumerate(((0, 0, 0, 0), (-0.46, 0.1, 8, -20), (0.46, 0.1, 8, 20),
                                              (-0.24, 0.46, -18, -8), (0.24, 0.46, -18, 8), (0, -0.34, 22, 0))):
            add(blade(), (dx, dy, 0.98), (0.5, 0.42, 0.62), rot=(rx, ry, 0), name=f"{nm}_spike{i}")
    elif style == "bun":
        add("sphere", (0, 0.32, 1.0), (0.74, 0.72, 0.66), name=nm + "_bun")
        add("cyl", (0, 0.28, 0.78), (0.56, 0.56, 0.1), rot=(-20, 0, 0))
        add("sphere", (-0.2, -0.66, 0.44), (1.0, 0.3, 0.34), rot=(-18, 0, 12))
        add("sphere", (0.44, -0.6, 0.42), (0.46, 0.26, 0.32), rot=(-18, 0, -10))
    elif style == "ponytail":
        fringe((-0.36, 0.02, 0.38), sweep=14, size=(0.6, 0.26, 0.32))
        add("cyl", (0, 0.72, 0.36), (0.36, 0.36, 0.16), rot=(80, 0, 0))
        add("sphere", (0, 0.86, 0.26), (0.56, 0.56, 0.56), name=nm + "_pt1")
        add(rbox(0.42, 0.4, 0.9, rv=0.19, re=0.14, sege=3), (0, 0.94, -0.26), (0.42, 0.4, 0.9), rot=(-12, 0, 0),
            name=nm + "_pt2")
        add("sphere", (0, 0.99, -0.72), (0.44, 0.42, 0.44), name=nm + "_pt3")
    elif style == "long":
        add(rbox(1.72, 0.5, 1.7, rv=0.22, re=0.14), (0, 0.5, -0.36), (1.72, 0.5, 1.7), name=nm + "_long")
        for s in (-1, 1):
            add(rbox(0.22, 1.0, 1.3, rv=0.1, re=0.08), (0.84 * s, 0.04, -0.2), (0.22, 1.0, 1.3))
            add("sphere", (0.3 * s, -0.66, 0.44), (0.7, 0.26, 0.36), rot=(-20, 0, -16 * s))
    elif style == "milo":
        _milo_hair(add, nm)
    elif style == "swoop":
        add("sphere", (-0.3, -0.24, 0.8), (1.5, 1.0, 0.6), rot=(0, -16, 0), name=nm + "_swoop")
        add("sphere", (0.14, -0.5, 0.86), (1.0, 0.56, 0.54), rot=(-20, -12, -10))
        add("sphere", (0.52, -0.6, 0.44), (0.4, 0.26, 0.38), rot=(-20, 0, -12))
    elif style == "pigtails":
        fringe((-0.36, 0.02, 0.38), size=(0.6, 0.26, 0.3), sweep=0)
        for dx in (-0.98, 0.98):
            s = 1 if dx > 0 else -1
            add("sphere", (0.8 * s, 0.18, 0.36), (0.28, 0.32, 0.32))
            h.append(part(f"{nm}_pig{dx}", "sphere", (hx + dx, hy + 0.2, hz + 0.2), (0.6, 0.6, 0.8), col, parent))
            add("sphere", (dx + 0.1 * s, 0.22, -0.26), (0.46, 0.46, 0.56))
    return h


def curl_mesh():
    """The ahoge: a tapered tube that rises from the crown and curls over (one moulded hook)."""
    if "curl" in _MESH:
        return _MESH["curl"]
    pts = [(0.0, 0, 0.0), (0.0, 0, 0.14), (0.01, 0, 0.28)]
    cx, cz, r = 0.17, 0.3, 0.16
    for k in range(1, 12):
        a = pi - (pi * 1.25) * k / 11                        # from the left of the circle over the top and down
        pts.append((cx + r * cos(a), 0, cz + r * sin(a)))
    n, seg = len(pts), 10
    bm = bmesh.new()
    rings = []
    for i, p in enumerate(pts):
        a, b_ = pts[max(0, i - 1)], pts[min(n - 1, i + 1)]
        tx, tz = b_[0] - a[0], b_[2] - a[2]
        ln = (tx * tx + tz * tz) ** 0.5 or 1.0
        nx, nz = -tz / ln, tx / ln                           # in-plane normal; the other axis is y
        rad = 0.085 * (1 - i / n) + 0.018
        rings.append([bm.verts.new((p[0] + rad * cos(2 * pi * j / seg) * nx, rad * sin(2 * pi * j / seg),
                                    p[2] + rad * cos(2 * pi * j / seg) * nz)) for j in range(seg)])
    for i in range(n - 1):
        for j in range(seg):
            k = (j + 1) % seg
            bm.faces.new((rings[i][j], rings[i][k], rings[i + 1][k], rings[i + 1][j]))
    bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("curl")
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    me.materials.append(core.MAT_PLAIN)
    _MESH["curl"] = me
    return me


def _milo_hair(add, nm):
    """Milo's moulded hair piece: a low crown with big swept-out spikes, a pointed fringe over the forehead,
    sideburn points and the one curl (ahoge) hooking over on top."""
    B = blade()
    add(rbox(1.7, 1.56, 0.56, rv=0.5, re=0.26, segv=5, sege=3), (0, 0.04, 0.52), (1.7, 1.56, 0.56))   # crown
    add(rbox(1.7, 0.6, 0.98, rv=0.26, re=0.16, sege=3), (0, 0.44, 0.14), (1.7, 0.6, 0.98))           # back
    # the outer ring: big spikes leaning out from the crown edge (front ones lean forward over the fringe)
    outer = ((-0.36, -0.42, 34, -14), (0.36, -0.42, 34, 14), (-0.66, -0.1, 12, -50), (0.66, -0.1, 12, 50),
             (-0.56, 0.4, -30, -36), (0.56, 0.4, -30, 36), (0, 0.58, -48, 0))
    for i, (dx, dy, rx, ry) in enumerate(outer):
        add(B, (dx, dy, 0.8), (0.7, 0.56, 0.92), rot=(rx, ry, 0), name=f"{nm}_mspike{i}")
    for dx, dy, rx, ry, s in ((-0.26, -0.06, 10, -16, 0.62), (0.28, 0.0, 6, 18, 0.6), (0, 0.28, -18, 0, 0.62)):
        add(B, (dx, dy, 0.98), (s, s * 0.85, 0.82), rot=(rx, ry, 0))
    # fringe: three wide points hanging over the forehead, the middle one longest
    for x, ln, rz in ((-0.46, 0.5, 14), (0.0, 0.6, 0), (0.46, 0.5, -14)):
        add(B, (x, -0.74, 0.52), (0.54, 0.26, ln), rot=(166, 0, rz))
    for s in (-1, 1):                                        # sideburn points hugging the head
        add(B, (0.85 * s, -0.22, 0.34), (0.2, 0.38, 0.42), rot=(180, 0, -6 * s))
    add(curl_mesh(), (0.02, 0.02, 1.05), (1.4, 1.4, 1.4), rot=(0, 0, 0), name=nm + "_curl1")


# ---------------------------------------------------------------- accessories
def _print(nm, loc, size, col, parent, rot=(0, 0, 0), tint=None):
    """A flat print on the torso front (very thin, just off the surface)."""
    ob = core.part(nm, rbox(size[0], max(size[1], 0.004), size[2], rv=min(0.03, 0.4 * min(size[0], size[2])), re=0.0),
                   loc, size, col, parent, rot=rot)
    if tint:
        ob["tint"] = tint                       # takes that outfit colour (torso = the shirt) in write_outfits
    return ob


def acc_parts(kind, col, ch):
    """Brick versions of the accessories that sit on the head or the torso; None = use core's own builder."""
    part = core.part
    nm, P = ch.name + "_" + kind, []
    hx, hy, hz = HC
    fy = hy - HDP / 2                           # head front (y)
    ty = FRONT - PR                             # torso print plane
    zt = NECK_Z
    if kind == "jacket":
        # torso moulded in the jacket colour (a shell round the torso) with the tee printed down the middle,
        # lighter lapel lines in a V, a printed hem and zip edge, a low moulded collar behind the neck, cuff prints
        c = col or "#1E1E24"
        lit = core.shade(c, 1.22)
        sx, sy, sz = TORSO[0] + 0.02, TORSO[1] + 0.02, NECK_Z - TZ0 + 0.01
        P.append(part(nm + "b", rbox(sx, sy, sz, rv=0.17, re=0.05), (0, 0, (TZ0 + NECK_Z) / 2), (sx, sy, sz), c,
                      ch.body))
        tee = _print(nm + "tee", (0, ty - 0.01, (TZ0 + NECK_Z) / 2 + 0.01), (0.64, 0.004, sz - 0.04), "#FFFFFF",
                     ch.body, tint="torso")
        P.append(tee)
        for s in (-1, 1):
            P.append(_print(nm + f"lap{s}", (0.4 * s, ty - 0.018, 1.38), (0.09, 0.004, 0.84), lit, ch.body,
                            rot=(0, 24 * s, 0)))
            P.append(_print(nm + f"zip{s}", (0.335 * s, ty - 0.018, 0.62), (0.05, 0.004, 0.96), lit, ch.body))
        P.append(_print(nm + "hem", (0, ty - 0.018, TZ0 + 0.1), (1.4, 0.004, 0.08), lit, ch.body))
        P.append(part(nm + "col", core.band_mesh(r=0.5, h=0.16, th=0.1, gap=radians(140), flare=0.05),
                      (0, 0.04, NECK_Z - 0.01), (1, 1, 1), c, ch.body))
        for i, e in enumerate(ch.elbow):
            cf = part(nm + f"cuff{i}", rbox(0.53, 0.57, 0.08, rv=0.21, re=0.02), (0, 0, -ARM[1] + 0.06),
                      (0.53, 0.57, 0.08), lit, e)
            cf["cuff"] = 1
            P.append(cf)
    elif kind == "pendant":                     # printed black cord V and a red pendant (a tiny raised gem)
        for s in (-1, 1):
            P.append(_print(nm + f"cord{s}", (0.14 * s, ty - 0.022, 1.5), (0.035, 0.004, 0.62), "#111111",
                            ch.body, rot=(0, 24 * s, 0)))
        P.append(part(nm + "gem", rbox(0.17, 0.05, 0.25, rv=0.06, re=0.02), (0, ty - 0.04, 1.16),
                      (0.17, 0.05, 0.25), col or "#D81E2A", ch.body))
    elif kind == "glasses":                     # round rims over the printed eyes, arms back to the ears
        c = col or "#141414"
        ez = hz + FACE_ZC + 41 * UPX            # printed eye height
        for dx in (-0.25, 0.25):
            s = 1 if dx > 0 else -1
            P.append(part(nm + f"r{dx}", "ring", (hx + dx, fy - 0.035, ez), (0.42, 1, 0.42), c, ch.neck))
            # hinge bar from the rim to the head's rounded corner, then the arm back along the side
            P.append(part(nm + f"h{dx}", rbox(0.12, 0.04, 0.04, rv=0.015, re=0.0), (hx + 0.5 * s, fy - 0.03, ez + 0.02),
                          (0.12, 0.04, 0.04), c, ch.neck))
            # the arms are printed along the flat sides of the head, back to the ear
            P.append(part(nm + f"a{dx}", rbox(0.004, 0.5, 0.035, rv=0.002, re=0.0),
                          (hx + (HW / 2 + PR) * s, fy + 0.62, ez + 0.02), (0.004, 0.5, 0.035), c, ch.neck))
        P.append(part(nm + "br", rbox(0.1, 0.04, 0.035, rv=0.015, re=0.0), (hx, fy - 0.035, ez + 0.03),
                      (0.1, 0.04, 0.035), c, ch.neck))
    elif kind in ("cap", "cap_back"):
        c = col or "#E5262B"
        P.append(part(nm, rbox(1.8, 1.7, 0.62, rv=0.5, re=0.26, segv=5, sege=3), (hx, hy + 0.0, hz + 0.6),
                      (1.8, 1.7, 0.62), c, ch.neck))
        by = 1.0 if kind == "cap_back" else -1.0
        P.append(part(nm + "b", rbox(1.3, 0.76, 0.07, rv=0.32, re=0.025), (hx, hy + by, hz + 0.34),
                      (1.3, 0.76, 0.07), c, ch.neck, rot=(8 if by < 0 else -8, 0, 0)))
        P.append(part(nm + "k", "cyl", (hx, hy + 0.0, hz + 0.92), (0.2, 0.2, 0.08), c, ch.neck))   # button, no logo
    elif kind == "helmet":
        c = col or "#F2C12E"
        P.append(part(nm, rbox(1.82, 1.66, 1.0, rv=0.5, re=0.36, segv=5, sege=4), (hx, hy + 0.04, hz + 0.34),
                      (1.82, 1.66, 1.0), c, ch.neck))
        P.append(part(nm + "rim", rbox(1.94, 1.78, 0.08, rv=0.5, re=0.03), (hx, hy + 0.04, hz - 0.12),
                      (1.94, 1.78, 0.08), c, ch.neck))
        for dz in (-0.42, -0.6):
            P.append(part(nm + f"m{dz}", rbox(1.1, 0.06, 0.06, rv=0.02, re=0.0), (hx, fy - 0.07, hz + dz),
                          (1.1, 0.06, 0.06), "#9A9A9A", ch.neck))
        P.append(part(nm + "mv", rbox(0.06, 0.06, 0.26, rv=0.02, re=0.0), (hx, fy - 0.07, hz - 0.51),
                      (0.06, 0.06, 0.26), "#9A9A9A", ch.neck))
    elif kind == "hairnet":
        P.append(part(nm, rbox(1.74, 1.56, 0.66, rv=0.46, re=0.28, segv=5, sege=3), (hx, hy + 0.03, hz + 0.52),
                      (1.74, 1.56, 0.66), col or "#9FD3FF", ch.neck))
    elif kind == "firehelmet":
        c = col or "#D7262B"
        P.append(part(nm, rbox(1.78, 1.6, 0.72, rv=0.5, re=0.3, segv=5, sege=3), (hx, hy + 0.04, hz + 0.6),
                      (1.78, 1.6, 0.72), c, ch.neck))
        P.append(part(nm + "b", rbox(2.3, 2.5, 0.07, rv=0.9, re=0.025, segv=6), (hx, hy + 0.2, hz + 0.3),
                      (2.3, 2.5, 0.07), c, ch.neck))
        P.append(part(nm + "s", rbox(0.5, 0.06, 0.4, rv=0.1, re=0.02), (hx, fy - 0.08, hz + 0.62),
                      (0.5, 0.06, 0.4), "#F2C230", ch.neck))
    elif kind == "clothespin":
        for dx in (-0.06, 0.06):
            P.append(part(nm + f"{dx}", rbox(0.09, 0.26, 0.3, rv=0.03, re=0.015), (hx + dx, fy - 0.12, hz - 0.12),
                          (0.09, 0.26, 0.3), "#D9B26F", ch.neck))
    elif kind == "bow":
        c = col or "#E5262B"
        for dx, ry in ((-0.2, -30), (0.2, 30)):
            P.append(part(nm + f"{dx}", "cone", (hx + dx + 0.48, hy + 0.3, hz + 0.98), (0.32, 0.22, 0.48), c,
                          ch.neck, rot=(0, 90 + ry, 0)))
        P.append(part(nm + "k", "sphere", (hx + 0.48, hy + 0.3, hz + 0.98), (0.18, 0.18, 0.18), c, ch.neck))
    elif kind == "shades_up":
        P.append(part(nm, rbox(1.3, 0.16, 0.24, rv=0.06, re=0.03), (hx, fy + 0.12, hz + 0.78), (1.3, 0.16, 0.24),
                      "#141414", ch.neck, rot=(-25, 0, 0)))
    elif kind == "mustache":
        P.append(part(nm, rbox(0.54, 0.06, 0.12, rv=0.05, re=0.02), (hx, fy - 0.02, hz + FACE_ZC - 0.1),
                      (0.54, 0.06, 0.12), col or "#3B2A1A", ch.neck))
    elif kind == "veil":
        P.append(part(nm, rbox(1.7, 0.1, 2.2, rv=0.04, re=0.02), (hx, hy + HDP / 2 + 0.08, hz - 0.2),
                      (1.7, 0.1, 2.2), col or "#FFFFFF", ch.neck))
        P.append(part(nm + "f", "sphere", (hx + 0.55, hy + 0.3, hz + 0.76), (0.38, 0.38, 0.38), "#FF7BAC", ch.neck))
    elif kind == "olives":
        for i, (dx, dz) in enumerate(((-0.42, 0.42), (0.36, 0.5), (0.0, -0.5), (0.5, -0.32))):
            P.append(part(nm + f"{i}", "sphere", (hx + dx, fy - 0.03, hz + dz), (0.22, 0.1, 0.22), "#1A1A1A",
                          ch.neck))
    elif kind == "beak":
        P.append(part(nm, "cone", (hx, fy - 0.2, hz - 0.2), (0.38, 0.38, 0.5), "#F39C12", ch.neck, rot=(90, 0, 0)))
        for i, dy in enumerate((-0.28, 0.0, 0.28)):
            P.append(part(nm + f"comb{i}", "sphere", (hx, hy + dy, hz + 1.0), (0.2, 0.34, 0.44), "#E5262B", ch.neck))
    # ---- torso prints and gear
    elif kind == "shirtfront":
        P.append(_print(nm, (0, ty, 1.12), (0.6, 0.004, 1.36), "#FFFFFF", ch.body))
    elif kind == "tie":
        c = col or "#E5262B"
        P.append(_print(nm, (0, ty - 0.006, 1.2), (0.22, 0.004, 1.0), c, ch.body))
        P.append(_print(nm + "k", (0, ty - 0.006, 1.72), (0.3, 0.004, 0.16), core.shade(c, 0.8), ch.body))
    elif kind == "tux":
        P.append(_print(nm, (0, ty, 1.05), (0.66, 0.004, 1.5), "#FFFFFF", ch.body))
        P.append(_print(nm + "b", (0, ty - 0.006, 1.68), (0.5, 0.004, 0.18), "#E5262B", ch.body))
    elif kind == "vest":
        c = col or "#C9A66B"
        sx, sy, sz = TORSO[0] + 0.02, TORSO[1] + 0.02, NECK_Z - TZ0 - 0.2
        P.append(part(nm, rbox(sx, sy, sz, rv=0.17, re=0.04), (0, 0, TZ0 + 0.1 + sz / 2), (sx, sy, sz), c, ch.body))
        P.append(_print(nm + "v", (0, ty - 0.01, 1.48), (0.5, 0.004, 0.62), "#FFFFFF", ch.body, tint="torso"))
        for dx in (-0.48, 0.48):
            P.append(_print(nm + f"p{dx}", (dx, ty - 0.01, 0.62), (0.42, 0.004, 0.32), core.shade(c, 0.82), ch.body))
    elif kind == "apron":
        P.append(_print(nm, (0, ty, 0.6), (1.4, 0.004, 1.9), col or "#FFFFFF", ch.body))
        P.append(_print(nm + "s", (0, ty - 0.004, 1.62), (0.9, 0.004, 0.06), core.shade(col or "#FFFFFF", 0.85),
                        ch.body))
    elif kind == "stripes":
        for dz in (0.55, 1.25):
            P.append(_print(nm + f"{dz}", (0, ty, dz), (1.4, 0.004, 0.16), "#F2F2F2", ch.body))
    elif kind == "chain":
        c = col or "#F2C12E"
        for s in (-1, 1):
            P.append(_print(nm + f"c{s}", (0.2 * s, ty - 0.006, 1.48), (0.06, 0.004, 0.66), c, ch.body,
                            rot=(0, 30 * s, 0)))
        P.append(part(nm + "d", rbox(0.3, 0.05, 0.32, rv=0.08, re=0.02), (0, ty - 0.03, 1.14), (0.3, 0.05, 0.32),
                      c, ch.body))
    elif kind == "whistle":
        for s in (-1, 1):
            P.append(_print(nm + f"c{s}", (0.16 * s, ty - 0.006, 1.48), (0.03, 0.004, 0.62), "#2B2B2B", ch.body,
                            rot=(0, 26 * s, 0)))
        P.append(part(nm, "cyl", (0.06, ty - 0.08, 1.16), (0.18, 0.18, 0.34), "#C9C9C9", ch.body, rot=(0, 90, 0)))
    elif kind == "headphones":                  # round the neck: the band over the shoulders, cups on the chest
        for s in (-1, 1):
            P.append(part(nm + f"band{s}", rbox(0.12, 0.9, 0.1, rv=0.05, re=0.02), (0.62 * s, -0.08, zt + 0.03),
                          (0.12, 0.9, 0.1), "#F2F2F2", ch.body))
            P.append(part(nm + f"cup{s}", "cyl", (0.44 * s, FRONT - 0.09, zt - 0.2), (0.44, 0.44, 0.16), "#F2F2F2",
                          ch.body, rot=(90, 0, 0)))
            P.append(part(nm + f"pad{s}", "cyl", (0.44 * s, FRONT - 0.18, zt - 0.2), (0.3, 0.3, 0.03), "#2B2B2B",
                          ch.body, rot=(90, 0, 0)))
    elif kind == "dress":                       # an A-line skirt piece over the hips (one moulded slope)
        c = col or "#FFFFFF"
        P.append(part(nm, rbox(2.5, 1.5, 1.05, rv=0.4, re=0.05, taper=0.78), (0, 0, -0.42), (2.5, 1.5, 1.05), c,
                      ch.body))
    elif kind == "tutu":
        P.append(part(nm, rbox(2.6, 1.8, 0.24, rv=0.7, re=0.08), (0, 0, 0.08), (2.6, 1.8, 0.24), col or "#FF8FC8",
                      ch.body))
        P.append(part(nm + "2", rbox(2.9, 2.1, 0.16, rv=0.8, re=0.06), (0, 0, -0.1), (2.9, 2.1, 0.16), "#FFC0E0",
                      ch.body))
    else:
        return None
    return P
