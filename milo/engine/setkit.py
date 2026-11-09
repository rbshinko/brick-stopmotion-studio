"""Set-dressing kit (runs inside Blender): bevelled boxes, wall-mounted pieces (windows, doors, frames,
posters, clocks, shelves), furniture clutter, plants, trees, street furniture. Every piece is procedural.
Names: everything is prefixed with the set name, and avoids the name patterns look.texture_world() reads
(..top / ..table / ..bench / _leg<digit> / _floor / _rug / _ceil), so textures only land where asked
through ob["tex"]."""
import os
import random
from math import radians, sin, cos
import bmesh
import bpy
from mathutils import Vector
import core
from core import part, text, lin

REAL = os.environ.get("MILO_LOOK") == "real"
BRICK = os.environ.get("MILO_LOOK") == "brick"
if BRICK:
    import brickkit as BK

# ---------------------------------------------------------------- materials (real look only)
_MAT = {}


def _mat(name, build):
    if name not in _MAT:
        _MAT[name] = build()
    return _MAT[name]


def _sky_card(name, bottom, top, emit):
    """Glass that shows a bright sky: vertical gradient on the object's own height, emissive."""
    def mk():
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        b = nt.nodes["Principled BSDF"]
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = lin(bottom)
        ramp.color_ramp.elements[1].color = lin(top)
        nt.links.new(tc.outputs["Generated"], sep.inputs[0])
        nt.links.new(sep.outputs["Z"], ramp.inputs["Fac"])
        nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
        nt.links.new(ramp.outputs["Color"], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = emit
        b.inputs["Roughness"].default_value = 0.08
        b.inputs["Specular IOR Level"].default_value = 0.6
        return m
    return _mat(name, mk)


def glass_in():
    if BRICK:
        return BK.glass_mat()
    return _sky_card("SetGlassIn", "#F4FBFF", "#8FCBF7", 1.1) if REAL else None


def glass_out():
    if BRICK:
        return BK.glass_mat()
    return _sky_card("SetGlassOut", "#9CC9E6", "#4F8FC4", 0.25) if REAL else None


def glow(level=1.6):
    if not (REAL or BRICK):
        return None
    return _mat(f"SetGlow{level}", lambda: core.material(f"SetGlow{level}", objcolor=True, emission=level))


def leafy():
    """Foliage: object colour, rough, with a soft clumpy noise so leaf balls don't read as plastic."""
    if not REAL:
        return None

    def mk():
        m = bpy.data.materials.new("SetLeaf")
        m.use_nodes = True
        nt = m.node_tree
        L = nt.links.new
        b = nt.nodes["Principled BSDF"]
        b.inputs["Roughness"].default_value = 0.85
        b.inputs["Specular IOR Level"].default_value = 0.12
        oi = nt.nodes.new("ShaderNodeObjectInfo")
        tc = nt.nodes.new("ShaderNodeTexCoord")
        nz = nt.nodes.new("ShaderNodeTexVoronoi")
        nz.inputs["Scale"].default_value = 9.0
        L(tc.outputs["Object"], nz.inputs["Vector"])
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["To Min"].default_value, mr.inputs["To Max"].default_value = 1.08, 0.72
        L(nz.outputs["Distance"], mr.inputs["Value"])
        sc = nt.nodes.new("ShaderNodeVectorMath")
        sc.operation = "SCALE"
        L(oi.outputs["Color"], sc.inputs[0]); L(mr.outputs["Result"], sc.inputs["Scale"])
        L(sc.outputs[0], b.inputs["Base Color"])
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 0.45
        L(nz.outputs["Distance"], bump.inputs["Height"])
        L(bump.outputs["Normal"], b.inputs["Normal"])
        return m
    return _mat("SetLeaf", mk)


def metal():
    if not REAL:
        return None

    def mk():
        m = core.material("SetMetal", objcolor=True, rough=0.28)
        m.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 0.85
        return m
    return _mat("SetMetal", mk)


# ---------------------------------------------------------------- bevelled box
_BOX = {}


def _bev_mesh(dims, bev):
    """Unit-size bevelled cube whose bevel is `bev` world units once the object is scaled to `dims`."""
    dims = tuple(max(1e-3, abs(d)) for d in dims)
    b = min(bev, 0.3 * min(dims))
    key = tuple(round(d, 2) for d in dims) + (round(b, 3),)
    if key in _BOX:
        return _BOX[key]
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * dims[0], v.co.y * dims[1], v.co.z * dims[2]))
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=b, segments=2, profile=0.5, affect="EDGES",
                    clamp_overlap=True)
    for v in bm.verts:
        v.co = Vector((v.co.x / dims[0], v.co.y / dims[1], v.co.z / dims[2]))
    me = core.finish(bm, "bbox")
    _BOX[key] = me
    return me


def bbox(name, loc, dims, col, rot=(0, 0, 0), bev=0.05, tex=None, mat=None, shadow=True):
    """A box with a real bevel (toy-plastic edge highlight). Scale = dims, like core.part, so the toon
    outline and every other per-object rule treat it the same as a plain cube."""
    if bev <= 0:
        ob = part(name, "cube", loc, dims, col, rot=rot, mat=mat, shadow=shadow)
    else:
        ob = bpy.data.objects.new(name, _bev_mesh(dims, bev))
        core.COLL.objects.link(ob)
        ob.location, ob.scale = loc, dims
        ob.rotation_euler = [radians(a) for a in rot]
        ob.color = lin(col)
        if mat is not None:
            ob.material_slots[0].link = "OBJECT"
            ob.material_slots[0].material = mat
        if not shadow:
            ob.visible_shadow = False
    if BRICK:            # no photo textures on bricks; flat tops get studs (or a smooth tile flag)
        BK.auto_studs(ob, dims, rot)
    elif tex:
        ob["tex"] = tex
    return ob


# ---------------------------------------------------------------- wall frames
class Wall:
    """A frame on a wall face: u along the wall, n out of the wall into the room, z up.
    (x, y) is a point on the wall face in set coordinates; rz = 0 for a back wall (room toward -Y),
    90 for a left wall (room toward +X), -90 for a right wall (room toward -X)."""

    brick = None             # brick look: the brickkit.Pending wall behind this face (windows cut holes in it)

    def __init__(self, s, x, y, rz=0):
        self.s, self.x, self.y, self.rz = s, x, y, rz
        self.c, self.sn = cos(radians(rz)), sin(radians(rz))

    def P(self, u, n, z):
        return self.s.P(self.x + u * self.c + n * self.sn, self.y + u * self.sn - n * self.c, z)

    def box(self, nm, u, n, z, du, dn, dz, col, bev=0.04, tex=None, mat=None, shadow=True):
        return bbox(f"{self.s.name}_{nm}", self.P(u, n, z), (du, dn, dz), col, rot=(0, 0, self.rz),
                    bev=bev, tex=tex, mat=mat, shadow=shadow)

    def cyl(self, nm, u, n, z, r, depth, col, mesh="cyl", mat=None):
        """Disc / cylinder whose axis points out of the wall."""
        return part(f"{self.s.name}_{nm}", mesh, self.P(u, n, z), (2 * r, 2 * r, depth), col,
                    rot=(90, 0, self.rz), mat=mat)

    def label(self, nm, body, u, n, z, size, col):
        return text(f"{self.s.name}_{nm}", body, self.P(u, n, z), size, col, rot=(90, 0, self.rz))


def trims(W, nm, u0, u1, h, base=0.6, crown=True, col="#FFFFFF"):
    """Bevelled baseboard along the wall's foot and crown moulding along its top."""
    w, mid = u1 - u0, (u0 + u1) / 2
    W.box(f"{nm}base", mid, 0.08, base / 2, w, 0.16, base, col, bev=0.05)
    if crown:
        W.box(f"{nm}crown", mid, 0.12, h - 0.2, w, 0.24, 0.4, col, bev=0.06)
        W.box(f"{nm}crown2", mid, 0.05, h - 0.55, w, 0.1, 0.12, col, bev=0.03)


def wainscot(W, nm, u0, u1, top, col, rail="#FFFFFF", tex=None):
    """Lower wall in a second pastel (or a texture role, e.g. tiles), capped with a chair rail."""
    w, mid = u1 - u0, (u0 + u1) / 2
    if BRICK and W.brick is not None:       # lower brick courses in the second colour, then the rail
        W.brick.bands.append((top, col))
        W.box(f"{nm}rail", mid, 0.1, BK._snap(top, BK.BRICK_H, W.brick.z0), w, 0.2, 0.22, rail, bev=0.05)
        return
    W.box(f"{nm}wain", mid, 0.03, top / 2, w, 0.06, top, col, bev=0, tex=tex)
    W.box(f"{nm}rail", mid, 0.1, top, w, 0.2, 0.22, rail, bev=0.05)


def window(W, nm, u, z, w, h, cols=2, rows=2, frame="#FFFFFF", sill=True, outside=False,
           glass_col="#BFE6FF", glass_name=None, frame_name=None):
    """Framed window: sky glass, bevelled frame, mullions, sill."""
    gm = glass_out() if outside else glass_in()
    if BRICK and W.brick is not None:       # a real opening in the brick wall: clear pane in the hole
        pw = W.brick
        pw.holes.append((u - w / 2, u + w / 2, z - h / 2, z + h / 2))
        g = W.box(glass_name or f"{nm}gl", u, -pw.T / 2, z, w, 0.1, h, glass_col, bev=0, mat=gm, shadow=False)
        g["brick"] = "glass"
        if pw.room:                         # a printed sky card just outside, like a real tabletop set
            BK.card(f"{W.s.name}_{nm}card", W.P(u, -(pw.T + 2.5), z - h / 2 - 2.5), w + 6, h + 5, rz=W.rz,
                    seed=len(nm))
    else:
        g = W.box(glass_name or f"{nm}gl", u, 0.03, z, w, 0.06, h, glass_col, bev=0, mat=gm, shadow=False)
        if BRICK:
            g["brick"] = "glass"
    t = 0.28
    W.box(frame_name or f"{nm}ft", u, 0.12, z + h / 2 + t / 2, w + 2 * t, 0.24, t, frame, bev=0.05)
    W.box(f"{nm}fb", u, 0.12, z - h / 2 - t / 2, w + 2 * t, 0.24, t, frame, bev=0.05)
    for sd in (-1, 1):
        W.box(f"{nm}fs{sd}", u + sd * (w / 2 + t / 2), 0.12, z, t, 0.24, h, frame, bev=0.05)
    for i in range(1, cols):
        W.box(f"{nm}mv{i}", u - w / 2 + w * i / cols, 0.08, z, 0.14, 0.14, h, frame, bev=0.03)
    for j in range(1, rows):
        W.box(f"{nm}mh{j}", u, 0.08, z - h / 2 + h * j / rows, w, 0.14, 0.14, frame, bev=0.03)
    if sill:
        W.box(f"{nm}sill", u, 0.3, z - h / 2 - t - 0.1, w + 2 * t + 0.5, 0.6, 0.2, frame, bev=0.05)


def door(W, nm, u, w, h, col, frame="#FFFFFF", knob="#E8B931", slab=True, glass=False, side=1, n0=0.0):
    """Door with bevelled casing, raised panels (or a glass light) and a round knob + rose."""
    t = 0.38
    W.box(f"{nm}cl", u - w / 2 - t / 2, n0 + 0.16, h / 2, t, 0.32, h + t, frame, bev=0.06)
    W.box(f"{nm}cr", u + w / 2 + t / 2, n0 + 0.16, h / 2, t, 0.32, h + t, frame, bev=0.06)
    W.box(f"{nm}ch", u, n0 + 0.16, h + t / 2, w + 2 * t, 0.32, t, frame, bev=0.06)
    face = n0 + 0.2
    if slab:
        W.box(f"{nm}slab", u, n0 + 0.1, h / 2, w, 0.2, h, col, bev=0.04)
    pc = _shade(col, 0.88)
    if glass:
        W.box(f"{nm}lite", u, face + 0.01, h * 0.72, w * 0.5, 0.04, h * 0.3, "#CFEFFF", bev=0, mat=glass_in())
        W.box(f"{nm}pn", u, face + 0.03, h * 0.28, w * 0.66, 0.06, h * 0.3, pc, bev=0.03)
    else:
        W.box(f"{nm}pa", u, face + 0.03, h * 0.7, w * 0.66, 0.06, h * 0.34, pc, bev=0.03)
        W.box(f"{nm}pb", u, face + 0.03, h * 0.27, w * 0.66, 0.06, h * 0.34, pc, bev=0.03)
    ku = u + side * (w / 2 - 0.42)
    W.cyl(f"{nm}rose", ku, face + 0.04, h * 0.48, 0.2, 0.08, knob, mat=metal())
    part(f"{W.s.name}_{nm}knob", "sphere", W.P(ku, face + 0.25, h * 0.48), (0.36, 0.36, 0.36), knob, mat=metal())


def picture(W, nm, u, z, w, h, frame="#3B2A1A", art="landscape", body=None, ink="#1E2A5A", bg="#FFFFFF"):
    """Framed picture / poster. art: landscape | portrait | poster (text body) | abstract."""
    W.box(f"{nm}fr", u, 0.07, z, w, 0.14, h, frame, bev=0.04)
    cw, ch = w - 0.36, h - 0.36
    n = 0.15
    if art == "landscape":
        W.box(f"{nm}sky", u, n, z, cw, 0.03, ch, "#9ED3F5", bev=0)
        W.box(f"{nm}hill", u, n + 0.02, z - ch * 0.3, cw, 0.03, ch * 0.4, "#5DAA4A", bev=0)
        W.cyl(f"{nm}sun", u + cw * 0.25, n + 0.03, z + ch * 0.22, min(cw, ch) * 0.13, 0.03, "#FFD84A")
        W.box(f"{nm}hut", u - cw * 0.18, n + 0.04, z - ch * 0.06, cw * 0.18, 0.03, ch * 0.16, "#E86A5A", bev=0)
    elif art == "portrait":
        W.box(f"{nm}bg", u, n, z, cw, 0.03, ch, "#2F4E6E", bev=0)
        W.cyl(f"{nm}head", u, n + 0.02, z + ch * 0.12, min(cw, ch) * 0.2, 0.03, "#E9B98A")
        W.box(f"{nm}body", u, n + 0.02, z - ch * 0.3, cw * 0.6, 0.03, ch * 0.36, "#8E2D2D", bev=0)
    elif art == "abstract":
        W.box(f"{nm}bg", u, n, z, cw, 0.03, ch, "#F4EFE4", bev=0)
        W.cyl(f"{nm}c1", u - cw * 0.18, n + 0.02, z + ch * 0.12, min(cw, ch) * 0.24, 0.03, "#E5262B")
        W.box(f"{nm}b1", u + cw * 0.2, n + 0.02, z - ch * 0.15, cw * 0.3, 0.03, ch * 0.5, "#2D5BFF", bev=0)
        W.box(f"{nm}b2", u - cw * 0.1, n + 0.03, z - ch * 0.32, cw * 0.5, 0.03, ch * 0.1, "#F2C230", bev=0)
    else:   # poster with a word
        W.box(f"{nm}bg", u, n, z, cw, 0.03, ch, bg, bev=0)
        if body:
            sz = min(ch * 0.3, cw * 1.5 / max(3, len(max(body.split("\n"), key=len))))
            W.label(f"{nm}txt", body, u, n + 0.03, z, sz, ink)


def clock(W, nm, u, z, r=0.9, rim="#2B2B2B"):
    W.cyl(f"{nm}rim", u, 0.1, z, r, 0.2, rim)
    W.cyl(f"{nm}face", u, 0.2, z, r * 0.84, 0.04, "#FFFFFF")
    for k in range(12):
        a = radians(k * 30)
        W.box(f"{nm}t{k}", u + sin(a) * r * 0.68, 0.23, z + cos(a) * r * 0.68, 0.06, 0.02, 0.06 if k % 3 else 0.14,
              "#2B2B2B", bev=0)
    W.box(f"{nm}hh", u, 0.25, z + r * 0.2, 0.08, 0.02, r * 0.4, "#1A1A1A", bev=0)        # 12:15
    W.box(f"{nm}mh", u + r * 0.2, 0.26, z, r * 0.55, 0.02, 0.06, "#1A1A1A", bev=0)
    W.cyl(f"{nm}pin", u, 0.27, z, 0.07, 0.03, "#E5262B")


def bookshelf(W, nm, u, w, h, d, shelves=3, wood="#8B5A2B", seed=1, n0=0.0):
    """Open bookcase standing against the wall, filled with books of varied size and colour."""
    rnd = random.Random(seed)
    t = 0.2
    W.box(f"{nm}back", u, n0 + 0.05, h / 2, w, 0.1, h, _shade(wood, 0.8), bev=0, tex="wood")
    for sd in (-1, 1):
        W.box(f"{nm}side{sd}", u + sd * (w / 2 - t / 2), n0 + d / 2, h / 2, t, d, h, wood, bev=0.04, tex="wood")
    W.box(f"{nm}cap", u, n0 + d / 2 + 0.05, h + 0.1, w + 0.2, d + 0.1, 0.2, wood, bev=0.05, tex="wood")
    gap = (h - 0.4) / shelves
    for k in range(shelves):
        z0 = 0.3 + k * gap
        W.box(f"{nm}sh{k}", u, n0 + d / 2, z0, w - 2 * t, d, 0.16, wood, bev=0.03, tex="wood")
        books(W, f"{nm}bk{k}", u - w / 2 + t + 0.1, u + w / 2 - t - 0.1, z0 + 0.08, gap - 0.35, n0 + d * 0.55,
              d * 0.7, rnd)


BOOK_COLS = ["#C0392B", "#2D5BFF", "#2ECC40", "#F2C230", "#8E44AD", "#16A085", "#E67E22", "#34495E",
             "#E5262B", "#1E2A5A", "#F4F4F4", "#7A4A22"]


def books(W, nm, u0, u1, z0, hmax, n, dn, rnd):
    u, i = u0, 0
    while u < u1 - 0.3:
        bw = rnd.uniform(0.22, 0.42)
        if rnd.random() < 0.12 and u > u0 + 0.5:       # a gap with a leaning book
            u += 0.5
            continue
        bh = hmax * rnd.uniform(0.62, 0.95)
        W.box(f"{nm}_{i}", u + bw / 2, n, z0 + bh / 2, bw, dn, bh, rnd.choice(BOOK_COLS), bev=0.03)
        u += bw + 0.02
        i += 1


def _shade(col, k):
    c = col.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(v * k))) for v in (r, g, b))


# ---------------------------------------------------------------- free-standing props (set coords)
def apple(s, nm, x, y, z, col="#D62A2A"):
    part(f"{s.name}_{nm}", "sphere", s.P(x, y, z + 0.22), (0.46, 0.46, 0.42), col)
    part(f"{s.name}_{nm}stem", "cyl", s.P(x, y, z + 0.5), (0.05, 0.05, 0.16), "#5A3A1A")
    part(f"{s.name}_{nm}lf", "sphere", s.P(x + 0.09, y, z + 0.52), (0.16, 0.06, 0.08), "#3FA34D", rot=(0, -30, 0))


def stack(s, nm, x, y, z, n=3, seed=2, w=1.0, d=0.75):
    """A small stack of books lying flat."""
    rnd = random.Random(seed)
    for k in range(n):
        bbox(f"{s.name}_{nm}{k}", s.P(x + rnd.uniform(-0.1, 0.1), y + rnd.uniform(-0.06, 0.06), z + 0.1 + k * 0.2),
             (w * rnd.uniform(0.85, 1.05), d * rnd.uniform(0.85, 1.05), 0.18), rnd.choice(BOOK_COLS),
             rot=(0, 0, rnd.uniform(-12, 12)), bev=0.03)


def pencil_cup(s, nm, x, y, z):
    part(f"{s.name}_{nm}", "cyl", s.P(x, y, z + 0.3), (0.42, 0.42, 0.6), "#2D5BFF")
    for k, (dx, dy, col) in enumerate(((0.06, 0.0, "#F2C230"), (-0.07, 0.05, "#E5262B"), (0.0, -0.07, "#2ECC40"))):
        part(f"{s.name}_{nm}p{k}", "cyl", s.P(x + dx, y + dy, z + 0.75), (0.07, 0.07, 0.75), col,
             rot=(dy * 120, dx * 120, 0))


def laptop(s, nm, x, y, z, col="#9AA3AD", screen="#3A7BD5"):
    """Open laptop facing -Y (toward the default camera)."""
    bbox(f"{s.name}_{nm}base", s.P(x, y, z + 0.04), (1.3, 0.9, 0.08), col, bev=0.02)
    bbox(f"{s.name}_{nm}lid", s.P(x, y + 0.48, z + 0.46), (1.3, 0.08, 0.86), col, rot=(-12, 0, 0), bev=0.02)
    bbox(f"{s.name}_{nm}scr", s.P(x, y + 0.42, z + 0.47), (1.14, 0.03, 0.7), screen, rot=(-12, 0, 0), bev=0,
         mat=glow(1.2))


def mug(s, nm, x, y, z, col="#F4F4F4"):
    part(f"{s.name}_{nm}", "cyl", s.P(x, y, z + 0.22), (0.36, 0.36, 0.44), col)
    part(f"{s.name}_{nm}h", "ring", s.P(x + 0.2, y, z + 0.22), (0.24, 0.24, 0.24), col, rot=(0, 0, 90))


def globe(s, nm, x, y, z):
    part(f"{s.name}_{nm}base", "cyl", s.P(x, y, z + 0.05), (0.6, 0.6, 0.1), "#5A3A1A")
    part(f"{s.name}_{nm}pole", "cyl", s.P(x, y, z + 0.4), (0.07, 0.07, 0.7), "#C9A24A")
    part(f"{s.name}_{nm}", "sphere", s.P(x, y, z + 0.95), (0.9, 0.9, 0.9), "#3C8DDB", rot=(0, 23, 0))
    for k, (dx, dz, sz) in enumerate(((0.18, 0.15, 0.4), (-0.2, -0.1, 0.32), (0.05, -0.3, 0.25))):
        part(f"{s.name}_{nm}land{k}", "sphere", s.P(x + dx, y - 0.3, z + 0.95 + dz), (sz, 0.3, sz * 0.8), "#4FA34D")


def plant(s, nm, x, y, k=1.0, pot="#C8643B", leaf="#2F8F3E", z=0.0):
    """Potted plant: tapered pot with rim, soil, and a clump of leaf balls."""
    if BRICK:
        return BK.plant(s, nm, x, y, k, pot, leaf, z)
    part(f"{s.name}_{nm}pot", "frustum", s.P(x, y, z + 0.8 * k), (1.4 * k, 1.4 * k, 1.6 * k), pot, rot=(180, 0, 0))
    part(f"{s.name}_{nm}rim", "cyl", s.P(x, y, z + 1.6 * k), (1.55 * k, 1.55 * k, 0.22 * k), _shade(pot, 0.9))
    part(f"{s.name}_{nm}soil", "cyl", s.P(x, y, z + 1.68 * k), (1.3 * k, 1.3 * k, 0.06), "#4A2E1A")
    rnd = random.Random(hash(nm) & 0xFFFF)
    for j, (dx, dy, dz, r) in enumerate(((0, 0, 2.7, 1.25), (0.55, 0.15, 2.3, 0.9), (-0.55, -0.1, 2.35, 0.9),
                                         (0.1, -0.5, 2.15, 0.8), (-0.15, 0.45, 3.15, 0.8))):
        part(f"{s.name}_{nm}lf{j}", "sphere", s.P(x + dx * k, y + dy * k, z + dz * k), (r * k * 1.1, r * k, r * k),
             _shade(leaf, rnd.uniform(0.85, 1.15)), mat=leafy())


def tall_plant(s, nm, x, y, k=1.0, pot="#F4F4F4", leaf="#2F8F3E"):
    """Floor plant: pot plus a few long, upward leaves (elongated spheres fanned out)."""
    if BRICK:
        return BK.tall_plant(s, nm, x, y, k, pot, leaf)
    part(f"{s.name}_{nm}pot", "frustum", s.P(x, y, 0.9 * k), (1.6 * k, 1.6 * k, 1.8 * k), pot, rot=(180, 0, 0))
    part(f"{s.name}_{nm}soil", "cyl", s.P(x, y, 1.78 * k), (1.4 * k, 1.4 * k, 0.06), "#4A2E1A")
    for j in range(7):
        a = j * 360 / 7
        tilt = 22 + (j % 3) * 9
        part(f"{s.name}_{nm}lf{j}", "sphere",
             s.P(x + 0.55 * k * cos(radians(a)), y + 0.55 * k * sin(radians(a)), 3.3 * k + (j % 2) * 0.3),
             (0.55 * k, 0.25 * k, 3.0 * k), _shade(leaf, 0.9 + 0.05 * (j % 3)),
             rot=(tilt * sin(radians(a)) * -1, tilt * cos(radians(a)), 0), mat=leafy())


def ceiling_panels(s, xs, ys, h, w=3.2, d=1.6, round_=False):
    """Light fixtures on the ceiling (real look only: there is no ceiling otherwise)."""
    if not REAL:
        return
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            if round_:
                part(f"{s.name}_lampb{i}{j}", "cyl", s.P(x, y, h - 0.12), (w, w, 0.14), "#DDDDDD", shadow=False)
                part(f"{s.name}_lamp{i}{j}", "sphere", s.P(x, y, h - 0.2), (w * 0.85, w * 0.85, 0.6), "#FFF6E3",
                     mat=glow(1.8), shadow=False)
            else:
                bbox(f"{s.name}_lampb{i}{j}", s.P(x, y, h - 0.1), (w + 0.3, d + 0.3, 0.12), "#D8D8D8", bev=0.03,
                     shadow=False)
                bbox(f"{s.name}_lamp{i}{j}", s.P(x, y, h - 0.17), (w, d, 0.06), "#FFF8EC", bev=0, mat=glow(1.6),
                     shadow=False)


def ceiling_grid(s, w, d, h, step=4.0, col="#D9D9D6"):
    """Drop-ceiling T-bar grid (real look only)."""
    if not REAL:
        return
    k, x = 0, -w / 2 + step
    while x < w / 2 - 0.5:
        bbox(f"{s.name}_cgx{k}", s.P(x, 0, h - 0.11), (0.12, d, 0.06), col, bev=0, shadow=False)
        x += step; k += 1
    k, y = 0, -d / 2 + step
    while y < d / 2 - 0.5:
        bbox(f"{s.name}_cgy{k}", s.P(0, y, h - 0.11), (w, 0.12, 0.06), col, bev=0, shadow=False)
        y += step; k += 1


# ---------------------------------------------------------------- outdoors
def tree(s, x, y, k=1.0, seed=0, leaf="#2E8B3A"):
    """Trunk with two branches and 5-6 overlapping leaf clusters, slightly varied greens."""
    if BRICK:
        return BK.tree(s, x, y, k, seed, leaf)
    rnd = random.Random(seed * 131 + int(x * 7) + int(y * 13))
    part(f"{s.name}_trunk{x}{y}", "frustum", s.P(x, y, 2.0 * k), (1.0 * k, 1.0 * k, 4.0 * k), "#6E4423")
    for b, (ang, ry) in enumerate(((35, 0), (-40, 0))):
        part(f"{s.name}_branch{x}{y}{b}", "cyl", s.P(x + 0.55 * k * (1 if ang > 0 else -1), y, 4.2 * k),
             (0.32 * k, 0.32 * k, 1.8 * k), "#6E4423", rot=(0, ang, 0))
    part(f"{s.name}_leaf{x}{y}", "sphere", s.P(x, y, 5.6 * k), (3.6 * k, 3.4 * k, 3.2 * k),
         _shade(leaf, 0.95), mat=leafy())
    clusters = ((-1.5, 0.3, 5.0, 2.6), (1.6, -0.2, 5.1, 2.7), (0.2, -1.2, 4.7, 2.4), (-0.4, 1.2, 6.2, 2.6),
                (0.9, 0.5, 6.7, 2.3), (-1.0, -0.6, 6.4, 2.1))
    for j, (dx, dy, dz, r) in enumerate(clusters):
        part(f"{s.name}_leaf{x}{y}_{j}", "sphere", s.P(x + dx * k, y + dy * k, dz * k),
             (r * k * rnd.uniform(0.95, 1.1), r * k * rnd.uniform(0.95, 1.1), r * k * 0.9),
             _shade(leaf, rnd.uniform(0.82, 1.18)), mat=leafy())


def bush(s, nm, x, y, k=1.0, col="#2F8F3E", seed=0):
    if BRICK:
        return BK.bush(s, nm, x, y, k, col, seed)
    rnd = random.Random(seed)
    for j, (dx, dz, r) in enumerate(((0, 0.75, 1.5), (-1.0, 0.6, 1.15), (1.0, 0.6, 1.2), (0.3, 1.25, 1.0))):
        part(f"{s.name}_{nm}{j}", "sphere", s.P(x + dx * k, y + rnd.uniform(-0.2, 0.2), dz * k),
             (r * k * 1.1, r * k, r * k), _shade(col, rnd.uniform(0.85, 1.15)), mat=leafy())


def fence(s, nm, x0, x1, y, h=2.4, col="#F7F7F2", gaps=()):
    """White picket fence along X, with gaps (x_centre, half_width) for paths."""
    def open_(x):
        return any(abs(x - g) < hw for g, hw in gaps)
    x, i = x0, 0
    while x <= x1:
        if not open_(x):
            bbox(f"{s.name}_{nm}p{i}", s.P(x, y, h / 2), (0.32, 0.14, h), col, bev=0.04)
            part(f"{s.name}_{nm}pt{i}", "prism", s.P(x, y, h), (0.14, 0.32, 0.25), col, rot=(0, 0, 90))
        x += 0.75
        i += 1
    # rails, split around gaps
    segs, a = [], x0
    for g, hw in sorted(gaps):
        if g - hw > a:
            segs.append((a, g - hw))
        a = max(a, g + hw)
    if a < x1:
        segs.append((a, x1))
    for k, (a, b) in enumerate(segs):
        for r, z in enumerate((h * 0.3, h * 0.72)):
            bbox(f"{s.name}_{nm}r{k}{r}", s.P((a + b) / 2, y + 0.12, z), (b - a, 0.1, 0.22), col, bev=0.03)


def street_lamp(s, nm, x, y, h=8.0, col="#3A3F47"):
    part(f"{s.name}_{nm}base", "frustum", s.P(x, y, 0.4), (0.8, 0.8, 0.8), col)
    part(f"{s.name}_{nm}pole", "cyl", s.P(x, y, h / 2), (0.26, 0.26, h), col, mat=metal())
    bbox(f"{s.name}_{nm}arm", s.P(x, y - 0.7, h - 0.1), (0.16, 1.6, 0.16), col, bev=0.03)
    part(f"{s.name}_{nm}hood", "frustum", s.P(x, y - 1.4, h - 0.25), (1.2, 1.2, 0.5), col)
    part(f"{s.name}_{nm}bulb", "sphere", s.P(x, y - 1.4, h - 0.55), (0.75, 0.75, 0.45), "#FFF1C9", mat=glow(2.0))


def mailbox(s, nm, x, y, col="#2D5BFF"):
    bbox(f"{s.name}_{nm}post", s.P(x, y, 1.2), (0.3, 0.3, 2.4), "#7A4A22", bev=0.04, tex="wood")
    bbox(f"{s.name}_{nm}box", s.P(x, y, 2.75), (0.8, 1.4, 0.6), col, bev=0.06)
    part(f"{s.name}_{nm}lid", "cyl", s.P(x, y, 3.05), (0.8, 0.8, 1.4), col, rot=(90, 0, 0))
    bbox(f"{s.name}_{nm}flag", s.P(x + 0.45, y + 0.2, 3.2), (0.06, 0.18, 0.7), "#E5262B", bev=0)


def hydrant(s, nm, x, y, col="#E5262B"):
    part(f"{s.name}_{nm}", "cyl", s.P(x, y, 0.75), (0.7, 0.7, 1.5), col)
    part(f"{s.name}_{nm}cap", "sphere", s.P(x, y, 1.5), (0.72, 0.72, 0.6), col)
    part(f"{s.name}_{nm}nz", "cyl", s.P(x, y, 1.0), (0.35, 0.35, 1.1), col, rot=(0, 90, 0))
