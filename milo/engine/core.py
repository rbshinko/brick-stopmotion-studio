"""Milo engine core (runs inside Blender): scene setup, materials, meshes, keyframes, the R6
character rig, accessories, puffs and drifting particles. Episode-agnostic; build.py drives it."""
import bpy, bmesh, math, os, random, sys
from math import radians, sin, cos, pi
from mathutils import Vector, Euler

ENGINE = os.path.dirname(os.path.abspath(__file__))
MILO = os.path.dirname(ENGINE)
FPS = 30
NF = 1          # set by init()
SNAP, LEAD, OVERSHOOT, G = 0.14, 0.075, 2.2, 78.0
random.seed(7)
BRICK = os.environ.get("MILO_LOOK") == "brick"     # our original toy brick figure (engine/brickfig.py)
if ENGINE not in sys.path:
    sys.path.insert(0, ENGINE)


def frame(t):
    return int(round(t * FPS))


def init(n_frames):
    global NF
    NF = n_frames
    SC.frame_start, SC.frame_end = 0, NF - 1


# ---------------------------------------------------------------- helpers
def lin(h, a=1.0):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c) + (a,)


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def smooth(u):
    u = clamp(u)
    return u * u * (3 - 2 * u)


def back(u):
    u = clamp(u)
    c1, c3 = OVERSHOOT, OVERSHOOT + 1
    return 1 + c3 * (u - 1) ** 3 + c1 * (u - 1) ** 2


def heading_to(d):
    """Root z-rotation (deg) that points a character's face (-Y) along d."""
    return math.degrees(math.atan2(d[0], -d[1]))


def wrap(a):
    return (a + 180) % 360 - 180


def facing(hd):
    r = radians(hd)
    return Vector((sin(r), -cos(r), 0))


# ---------------------------------------------------------------- scene
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = FPS
    sc.frame_start, sc.frame_end = 0, NF - 1
    sc.render.resolution_x, sc.render.resolution_y = 1080, 1920
    try:
        sc.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        sc.render.engine = "BLENDER_EEVEE"
    ee = sc.eevee
    ee.taa_render_samples = 32
    for attr, val in (("use_shadows", True), ("use_raytracing", True)):
        if hasattr(ee, attr):
            setattr(ee, attr, val)
    for owner in (sc.render, ee):
        if hasattr(owner, "use_motion_blur"):
            owner.use_motion_blur = False
    vs = sc.view_settings
    vs.view_transform, vs.look, vs.exposure, vs.gamma = "Standard", "None", 0.0, 1.0
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.image_settings.compression = 15
    sc.render.film_transparent = False
    return sc


SC = reset()
COLL = SC.collection


def node(nt, kind, **kw):
    n = nt.nodes.new(kind)
    for k, v in kw.items():
        setattr(n, k, v)
    return n


def material(name, color=None, emission=0.0, alpha=1.0, objcolor=False, rough=0.6):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = rough
    b.inputs["Specular IOR Level"].default_value = 0.25
    if objcolor:
        oi = node(nt, "ShaderNodeObjectInfo")
        nt.links.new(oi.outputs["Color"], b.inputs["Base Color"])
        nt.links.new(oi.outputs["Alpha"], b.inputs["Alpha"])      # object colour alpha = ghost fade
        if hasattr(m, "surface_render_method"):
            m.surface_render_method = "DITHERED"
        if emission:
            nt.links.new(oi.outputs["Color"], b.inputs["Emission Color"])
    elif color:
        b.inputs["Base Color"].default_value = lin(color)
        if emission:
            b.inputs["Emission Color"].default_value = lin(color)
    b.inputs["Emission Strength"].default_value = emission
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
        if hasattr(m, "surface_render_method"):
            m.surface_render_method = "DITHERED"
        else:
            m.blend_method = "HASHED"
    return m


MAT_PLAIN = material("Plain", objcolor=True)
MAT_GLOW = material("Glow", objcolor=True, emission=6.0)
MAT_PUFF = material("Puff", color="#FFFFFF", emission=1.3, alpha=0.72)
MAT_STAR = material("Star", color="#FFE14D", emission=1.3)
MAT_POLLEN = material("Pollen", color="#F7D23E", emission=0.5, alpha=0.85)


def head_material():
    if BRICK:
        import brickfig
        return brickfig.head_material()
    m = bpy.data.materials.new("Head")
    m.use_nodes = True
    nt = m.node_tree
    L = nt.links.new
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.55
    b.inputs["Specular IOR Level"].default_value = 0.25
    img = bpy.data.images.load(os.path.join(MILO, "work", "faces_real" if os.environ.get("MILO_LOOK") == "real" else "faces", "atlas.png"))
    img.alpha_mode = "STRAIGHT"
    n_faces = img.size[1] // 578
    big = 1.4                               # faces 1.4x the old size (judge: read from further away)
    arc = radians(130 * big)
    h_img = 1.25 * big                      # decal taller than the head; features sit in its middle 45%
    lift = 0.07                             # and a little higher on the head (under the fringe)
    tc = node(nt, "ShaderNodeTexCoord")
    sep = node(nt, "ShaderNodeSeparateXYZ")
    L(tc.outputs["Object"], sep.inputs[0])

    def math_(op, a, b_=None, c=None):
        n = node(nt, "ShaderNodeMath", operation=op)
        for i, v in enumerate((a, b_, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                L(v, n.inputs[i])
        return n.outputs[0]

    negy = math_("MULTIPLY", sep.outputs["Y"], -1.0)
    ang = math_("ARCTAN2", sep.outputs["X"], negy)
    u = math_("MULTIPLY_ADD", ang, 1 / arc, 0.5)
    v = math_("MULTIPLY_ADD", sep.outputs["Z"], 1 / h_img, 0.5 - lift / h_img)
    attr = node(nt, "ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="face")
    rev = math_("SUBTRACT", float(n_faces - 1), attr.outputs["Fac"])
    va = math_("DIVIDE", math_("ADD", v, rev), float(n_faces))
    comb = node(nt, "ShaderNodeCombineXYZ")
    L(u, comb.inputs[0]); L(va, comb.inputs[1])
    tex = node(nt, "ShaderNodeTexImage", image=img, extension="EXTEND", interpolation="Linear")
    L(comb.outputs[0], tex.inputs[0])
    mask = math_("MULTIPLY", math_("MULTIPLY", math_("GREATER_THAN", u, 0.0), math_("LESS_THAN", u, 1.0)),
                 math_("MULTIPLY", math_("GREATER_THAN", v, 0.0), math_("LESS_THAN", v, 1.0)))
    a = math_("MULTIPLY", tex.outputs["Alpha"], mask)
    oi = node(nt, "ShaderNodeObjectInfo")
    mix = node(nt, "ShaderNodeMix", data_type="RGBA")
    L(a, mix.inputs["Factor"])
    L(oi.outputs["Color"], mix.inputs[6])
    L(tex.outputs["Color"], mix.inputs[7])
    L(mix.outputs[2], b.inputs["Base Color"])
    L(oi.outputs["Alpha"], b.inputs["Alpha"])
    return m


MAT_HEAD = head_material()
sys.path.insert(0, ENGINE)
from facelist import FACES
FACE_IDS = {n: i for i, n in enumerate(FACES)}


def grass_material():
    m = bpy.data.materials.new("Grass")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.9
    b.inputs["Specular IOR Level"].default_value = 0.1
    tc = node(nt, "ShaderNodeTexCoord")
    nz = node(nt, "ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 0.22
    nz.inputs["Detail"].default_value = 1.5
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    ramp = node(nt, "ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[0].color = 0.0, lin("#3D8C21")
    ramp.color_ramp.elements[1].position, ramp.color_ramp.elements[1].color = 0.5, lin("#4FA32B")
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return m


def world():
    w = bpy.data.worlds.new("Sky")
    SC.world = w
    w.use_nodes = True
    nt = w.node_tree
    out = nt.nodes["World Output"]
    for n in list(nt.nodes):
        if n != out:
            nt.nodes.remove(n)
    tc = node(nt, "ShaderNodeTexCoord")
    sep = node(nt, "ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    mr = node(nt, "ShaderNodeMapRange")
    mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = 0.0, 0.6
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    ramp = node(nt, "ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = lin("#B8D9FF")
    ramp.color_ramp.elements[1].color = lin("#3378F7")
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    cam_bg = node(nt, "ShaderNodeBackground")
    light_bg = node(nt, "ShaderNodeBackground")
    light_bg.inputs["Strength"].default_value = 0.7
    for bg in (cam_bg, light_bg):
        nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    lp = node(nt, "ShaderNodeLightPath")
    mix = node(nt, "ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(light_bg.outputs[0], mix.inputs[1])
    nt.links.new(cam_bg.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])


world()
sun_data = bpy.data.lights.new("Sun", "SUN")
sun_data.energy = 3.5
sun_data.color = lin("#FFE9C9")[:3]
sun_data.angle = radians(1.5)
sun_data.use_shadow = True
sun = bpy.data.objects.new("Sun", sun_data)
COLL.objects.link(sun)
sun.rotation_euler = Euler((radians(90 - 42), 0, radians(-30)))   # 42 deg above the horizon


# ---------------------------------------------------------------- meshes
def finish(bm, name, mat=None, smooth_=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth_:
        me.shade_smooth()
        if hasattr(me, "set_sharp_from_angle"):
            me.set_sharp_from_angle(angle=radians(40))
    me.materials.append(mat or MAT_PLAIN)
    return me


def mk_meshes():
    M = {}
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0); M["cube"] = finish(bm, "cube")
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=14, radius=0.5)
    M["sphere"] = finish(bm, "sphere", smooth_=True)
    M["sphere"].shade_smooth()
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=0.5, radius2=0.5, depth=1.0)
    M["cyl"] = finish(bm, "cyl", smooth_=True)
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.5, radius2=0.0, depth=1.0)
    M["cone"] = finish(bm, "cone", smooth_=True)
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=0.5, radius2=0.3, depth=1.0)
    M["frustum"] = finish(bm, "frustum", smooth_=True)
    # head: cylinder r 0.62, h 1.22, 0.22 bevel on both rims
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=0.62, radius2=0.62, depth=1.22)
    rims = [e for e in bm.edges if any(len(f.verts) > 4 for f in e.link_faces)]
    bmesh.ops.bevel(bm, geom=rims, offset=0.22, segments=5, profile=0.5, affect="EDGES")
    me = bpy.data.meshes.new("head")
    bm.to_mesh(me); bm.free()
    me.shade_smooth()
    me.materials.append(MAT_HEAD)
    M["head"] = me
    if BRICK:                                    # rounded-box toy head (no cylinder, no stud)
        import brickfig
        M["head"] = brickfig.head_mesh(MAT_HEAD)
    # roof prism: base y -0.5..0.5 at z 0, ridge at z 1, length 1 along x
    bm = bmesh.new()
    v = [bm.verts.new(p) for p in ((-.5, -.5, 0), (-.5, .5, 0), (-.5, 0, 1), (.5, -.5, 0), (.5, .5, 0), (.5, 0, 1))]
    for f in ((0, 2, 1), (3, 4, 5), (0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)):
        bm.faces.new([v[i] for i in f])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    M["prism"] = finish(bm, "prism")
    # five-point star, flat in XZ, 0.1 thick
    bm = bmesh.new()
    rings = []
    for y in (-0.05, 0.05):
        pts = []
        for i in range(10):
            a = pi / 2 + i * pi / 5
            r = 0.5 if i % 2 == 0 else 0.22
            pts.append(bm.verts.new((r * cos(a), y, r * sin(a))))
        c = bm.verts.new((0, y, 0))
        rings.append((pts, c))
    for pts, c in rings:
        for i in range(10):
            bm.faces.new((c, pts[i], pts[(i + 1) % 10]))
    for i in range(10):
        a, b_ = rings[0][0], rings[1][0]
        bm.faces.new((a[i], a[(i + 1) % 10], b_[(i + 1) % 10], b_[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    M["star"] = finish(bm, "star", MAT_STAR)
    # flat ring (glasses rim), facing -Y: outer r 0.5, inner r 0.4, 0.06 thick
    bm = bmesh.new()
    segs, rings_ = 28, []
    for y in (-0.03, 0.03):
        rings_.append([[bm.verts.new((r * cos(2 * pi * i / segs), y, r * sin(2 * pi * i / segs)))
                        for i in range(segs)] for r in (0.5, 0.4)])
    for i in range(segs):
        j = (i + 1) % segs
        for side in range(2):
            o, n = rings_[side][0], rings_[side][1]
            bm.faces.new((o[i], o[j], n[j], n[i]))
        for k in range(2):
            a, b_ = rings_[0][k], rings_[1][k]
            bm.faces.new((a[i], a[j], b_[j], b_[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    M["ring"] = finish(bm, "ring", smooth_=True)
    return M


MESH = mk_meshes()
_BEVELLED = {}


def bevel_box(sx, sy, sz):
    """A unit cube with toy-plastic rounded edges that look even once the object is scaled to (sx, sy, sz):
    built at real size, bevelled ~6% of the smallest side (3 segments), then shrunk back to unit size.
    One mesh per distinct size, shared by every part of that size (crowds reuse them)."""
    key = (round(abs(sx), 3), round(abs(sy), 3), round(abs(sz), 3))
    if key in _BEVELLED:
        return _BEVELLED[key]
    dims = [max(1e-3, d) for d in key]
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=dims, verts=bm.verts)
    r = min(0.14, 0.065 * min(dims) + 0.012 * (sum(dims) / 3))
    r = min(r, 0.45 * min(dims))
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=r, segments=3, profile=0.5, affect="EDGES",
                    clamp_overlap=True)
    bmesh.ops.scale(bm, vec=[1 / d for d in dims], verts=bm.verts)
    me = bpy.data.meshes.new("bcube")
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    if hasattr(me, "set_sharp_from_angle"):
        me.set_sharp_from_angle(angle=radians(65))
    me.materials.append(MAT_PLAIN)
    _BEVELLED[key] = me
    return me


_SOFT = {}


def soft_box(sx, sy, sz, k=0.4, seg=4):
    """A toy-soft rounded block (mittens, thumbs, sneaker toes): like bevel_box but the edges round off by
    k x the smallest side (0.5 = a capsule across that side), smooth-shaded, one piece. Unit size like bcube."""
    key = (round(abs(sx), 3), round(abs(sy), 3), round(abs(sz), 3), round(k, 3), seg)
    if key in _SOFT:
        return _SOFT[key]
    dims = [max(1e-3, d) for d in key[:3]]
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=dims, verts=bm.verts)
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(0.499, k) * min(dims), segments=seg, profile=0.5,
                    affect="EDGES", clamp_overlap=True)
    bmesh.ops.scale(bm, vec=[1 / d for d in dims], verts=bm.verts)
    me = bpy.data.meshes.new("sbox")
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    me.materials.append(MAT_PLAIN)
    _SOFT[key] = me
    return me


def band_mesh(r=0.5, h=0.3, th=0.08, gap=0.0, flare=0.0, dip=0.0, segs=40):
    """A collar band round the neck (unit-free: build at real size, used with scale 1). Ring of radius r (to the
    middle of the wall), wall height h and thickness th, open over the front by `gap` (radians, 0 = closed);
    the top flares out by `flare`, and the front dips down by `dip` (a crew neckline)."""
    key = ("band", r, h, th, gap, flare, dip, segs)
    if key in _SOFT:
        return _SOFT[key]
    bm = bmesh.new()
    a0, a1 = -pi / 2 + gap / 2, 3 * pi / 2 - gap / 2          # angle 0 = +X, -pi/2 = front (-Y)
    n = segs if gap else segs
    rows = []
    for i in range(n + (1 if gap else 0)):
        a = a0 + (a1 - a0) * i / n
        front = max(0.0, -sin(a)) ** 2                           # 1 at the front, 0 at the sides/back
        dz = -dip * front
        prof = ((r - th / 2, 0), (r + th / 2, 0), (r + th / 2 + flare, h), (r - th / 2 + flare, h))
        rows.append([bm.verts.new((rr * cos(a), rr * sin(a), z + dz)) for rr, z in prof])
    for i in range(len(rows) - (1 if gap else 0)):
        A, B = rows[i], rows[(i + 1) % len(rows)]
        for k in range(4):
            bm.faces.new((A[k], A[(k + 1) % 4], B[(k + 1) % 4], B[k]))
    if gap:
        bm.faces.new(rows[0][::-1]); bm.faces.new(rows[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("band")
    bm.to_mesh(me)
    bm.free()
    me.shade_smooth()
    if hasattr(me, "set_sharp_from_angle"):
        me.set_sharp_from_angle(angle=radians(60))
    me.materials.append(MAT_PLAIN)
    _SOFT[key] = me
    return me


def shade(hexcol, f):
    """hexcol darkened (f < 1) or lightened toward white (f > 1)."""
    h = hexcol.lstrip("#")
    c = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    c = [v * f if f <= 1 else v + (255 - v) * (f - 1) for v in c]
    return "#" + "".join(f"{int(max(0, min(255, v))):02X}" for v in c)


def empty(name, loc=(0, 0, 0), parent=None):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_size = 0.3
    COLL.objects.link(ob)
    ob.parent = parent
    ob.location = loc
    return ob


def part(name, mesh, loc, size, color, parent=None, rot=(0, 0, 0), mat=None, shadow=True):
    """mesh: a MESH key, "bcube" (bevelled box sized to `size`), "sbox" (toy-soft rounded block), or a bpy mesh."""
    me = (bevel_box(*size) if mesh == "bcube" else soft_box(*size) if mesh == "sbox"
          else mesh if not isinstance(mesh, str) else MESH[mesh])
    ob = bpy.data.objects.new(name, me)
    COLL.objects.link(ob)
    ob.parent = parent
    ob.location = loc
    ob.scale = size
    ob.rotation_euler = Euler([radians(a) for a in rot])
    ob.color = lin(color) if isinstance(color, str) else color
    if mat is not None:
        ob.material_slots[0].link = "OBJECT"
        ob.material_slots[0].material = mat
    if not shadow:
        ob.visible_shadow = False
    return ob


FONT = bpy.data.fonts.load(os.path.join(MILO, "assets", "fonts", "Montserrat-ExtraBold.ttf"))


def text(name, body, loc, size, color, rot=(90, 0, 0)):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body, cu.font, cu.size = body, FONT, size
    cu.align_x, cu.align_y = "CENTER", "CENTER"
    cu.extrude = 0.04
    cu.materials.append(MAT_PLAIN)
    ob = bpy.data.objects.new(name, cu)
    COLL.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = Euler([radians(a) for a in rot])
    ob.color = lin(color)
    return ob


# ---------------------------------------------------------------- keyframes
def _fcurve(idb, path, index):
    if path.startswith('["'):
        idb.keyframe_insert(data_path=path, frame=0)
        index = 0
    else:
        idb.keyframe_insert(data_path=path, index=index, frame=0)
    ad = idb.animation_data
    fcs = None
    try:
        from bpy_extras import anim_utils
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        fcs = cb.fcurves
    except Exception:
        fcs = ad.action.fcurves
    return fcs.find(path, index=max(0, index))


def keys(idb, path, index, frames, values):
    """One constant key per given frame."""
    fc = _fcurve(idb, path, index)
    kp = fc.keyframe_points
    kp.add(len(frames) - len(kp))
    kp.foreach_set("co", [x for f, v in zip(frames, values) for x in (float(f), float(v))])
    kp.foreach_set("interpolation", [0] * len(frames))   # CONSTANT
    fc.update()


def step_keys(idb, path, index, changes):
    """changes: [(frame, value)] -> constant keys only where the value changes."""
    changes = sorted(changes, key=lambda c: c[0])      # stable: same-frame changes keep their order
    out, last = [], None
    for f, v in changes:
        f = max(0, min(NF - 1, f))
        if out and out[-1][0] == f:
            out[-1] = (f, v)
        elif v != last:
            out.append((f, v))
        last = out[-1][1]
    if not out or out[0][0] != 0:
        out.insert(0, (0, out[0][1] if out else 0))
    keys(idb, path, index, [f for f, _ in out], [v for _, v in out])


# ---------------------------------------------------------------- characters
# Joints (degrees): sh = shoulder pitch (negative raises the arm forward), sp = abduct (positive = out to
# the side), sz = shoulder yaw (positive swings the arm in across the chest), el = elbow (negative bends the
# forearm forward/up), suffix p = the +X arm (holds props), n = the other arm. lean/twist/tilt = body
# pitch/yaw/roll, nod/turnh = head, crouch = body drop, hips swing the legs. fwp/fwn (0..1) roll a shoulder
# forward and in, so hands can reach the face / cross the chest in front of the torso.
# Grips: a held prop stays upright and facing forward in every pose by itself; gpx/gpy (gnx/gny) only add
# an extra prop rotation (the phone pose turns the screen toward the face).
POSES = {
    "idle": {"shp": -5, "shn": -6, "spp": 3, "spn": 4, "szp": 8, "szn": 6, "elp": -16, "eln": -22, "tilt": 1.5, "roll": -3},
    "crowd": {"shp": -62, "shn": -62, "elp": -28, "eln": -28},
    "stiff": {"spp": -4, "spn": -4, "lean": -3, "nod": -4},
    "hold": {"shp": -52, "shn": -52, "spp": -6, "spn": -6, "szp": 12, "szn": 12, "elp": -38, "eln": -38},
    "hold1": {"shp": -32, "spp": -4, "szp": 12, "elp": -58, "shn": -5, "spn": 3, "szn": 8, "eln": -16},
    "shock": {"shp": -35, "shn": -45, "spp": 40, "spn": 36, "elp": -45, "eln": -52, "lean": -8, "nod": -8, "roll": 6, "tilt": 2},
    "shock2": {"shp": -160, "shn": -160, "spp": 15, "spn": 15, "elp": -15, "eln": -15, "lean": -6, "nod": -10},
    "scared": {"shp": -78, "shn": -78, "spp": -8, "spn": -8, "szp": 22, "szn": 22, "elp": -60, "eln": -60,
               "lean": -8, "crouch": -0.25, "nod": 5, "roll": -6, "tilt": 3, "twist": 6},
    "akimbo": {"shp": 10, "shn": 10, "spp": 42, "spn": 42, "szp": -50, "szn": -50, "elp": -75, "eln": -75, "tilt": 3, "roll": 5},
    "proud": {"shp": 10, "shn": 10, "spp": 42, "spn": 42, "szp": -50, "szn": -50, "elp": -75, "eln": -75,
              "lean": -4, "nod": -6, "tilt": -3, "roll": -6},
    "nod": {"shp": 10, "shn": 10, "spp": 42, "spn": 42, "szp": -50, "szn": -50, "elp": -75, "eln": -75, "nod": 8},
    "salute": {"shp": -150, "spp": -40, "elp": -35, "nod": -4, "shn": -4, "spn": 3, "eln": -12},
    "king": {"shp": -170, "spp": 8, "shn": 12, "spn": 38, "eln": -20, "lean": -5, "twist": -8, "nod": -6},
    "sword": {"shp": -118, "spp": 12, "shn": 20, "spn": 30, "eln": -25, "lean": 8, "hipp": -25, "hipn": 20,
              "twist": 14},
    "ahh": {"shp": -20, "shn": -20, "spp": 25, "spn": 25, "elp": -20, "eln": -20, "lean": -14, "nod": -22},
    "ahh2": {"shp": -35, "shn": -35, "spp": 35, "spn": 35, "elp": -25, "eln": -25, "lean": -20, "nod": -30,
             "crouch": 0.1},
    "sneeze": {"shp": 30, "shn": 30, "spp": 15, "spn": 15, "elp": -10, "eln": -10, "lean": 11, "nod": 7,
               "crouch": -0.15},
    "lookdown": {"shp": -32, "shn": -32, "spp": 12, "spn": 12, "szp": 10, "szn": 10, "elp": -48, "eln": -48, "lean": 6,
                 "nod": 28},
    "cheer": {"shp": -160, "shn": -150, "spp": 22, "spn": 26, "elp": -18, "eln": -26, "nod": -8, "roll": 8, "tilt": -3},
    "ballet": {"shp": -165, "shn": -165, "spp": -18, "spn": -18, "elp": -12, "eln": -12, "nod": -6},
    "twitch": {"nod": -6, "twist": 6, "shp": -10, "elp": -20, "eln": -12, "turnh": 8},
    "whistle": {"shp": -150, "spp": -35, "elp": -30, "nod": -5, "eln": -14},
    # ---- expressive set (2026-11): one-handed gestures use the p (prop) arm
    "point": {"shp": -92, "szp": -24, "elp": -4, "shn": -5, "spn": 3, "szn": 8, "eln": -18, "nod": -3, "twist": -10,
              "tilt": -3, "roll": 5},
    "facepalm": {"fwn": 1, "shn": -105, "szn": 60, "eln": -30, "shp": -4, "spp": 4, "szp": 6, "elp": -14, "nod": 20,
                 "lean": 6, "tilt": 4, "roll": -8},
    "shrug": {"shp": -12, "shn": -18, "spp": 24, "spn": 22, "szp": -42, "szn": -38, "elp": -88, "eln": -80,
              "nod": -6, "turnh": 8, "tilt": 4, "roll": 10},
    "thinkchin": {"fwp": 0.98, "shp": -64, "szp": 61, "elp": -66, "spp": 4, "fwn": 1, "shn": -47, "szn": 50, "eln": -36,
                  "spn": -6, "nod": -8, "turnh": -10, "tilt": -3, "roll": -8},
    "phone": {"fwp": 1, "shp": -40, "szp": 45, "elp": -62, "gpx": -90, "gpy": 180, "nod": 22, "shn": -5,
              "spn": 3, "szn": 8, "eln": -16, "roll": 6, "tilt": 3},
    "holdout": {"shp": -82, "szp": 14, "elp": -8, "lean": -2, "nod": -2, "shn": -5, "spn": 3, "szn": 8,
                "eln": -16, "tilt": -3, "twist": -10, "roll": 5},
    "show": {"shp": -50, "szp": 18, "elp": -62, "gpx": 18, "nod": -3, "twist": -8, "shn": -5, "spn": 3,
             "szn": 8, "eln": -16, "tilt": 3, "roll": 7},
    # folded arms: forearms level across the chest, the prop-side one higher and in front (no interpenetration)
    "crossarms": {"fwp": 1, "shp": 0, "spp": 85, "szp": 78, "elp": -90, "fwn": 1.3, "shn": 0, "spn": 15, "szn": 82,
                  "eln": -85, "lean": -4, "nod": -5, "turnh": 6, "tilt": 4, "roll": -7, "twist": 8},
    "panic": {"shp": -165, "shn": -165, "spp": 30, "spn": 30, "szp": 40, "szn": 40, "elp": -62, "eln": -62,
              "lean": -4, "nod": -6, "tilt": 3},
    "wave": {"shp": -100, "szp": -50, "elp": -70, "shn": -5, "spn": 3, "szn": 8, "eln": -16, "nod": -4,
             "turnh": 6, "tilt": -4, "roll": 8, "twist": -6},
    "fistpump": {"shp": -150, "spp": 15, "szp": 10, "elp": -110, "shn": 6, "spn": 12, "eln": -40, "lean": -4,
                 "nod": -8, "tilt": -5, "roll": 6, "twist": -8},
    "raise": {"shp": -170, "spp": 10, "elp": -5, "shn": 8, "spn": 25, "eln": -20, "nod": -12, "lean": -3, "tilt": -4, "roll": -6},
    "lean": {"tilt": 7, "twist": 8, "shp": 10, "spp": 42, "szp": -50, "elp": -75, "shn": -5, "spn": 3, "szn": 8,
             "eln": -16, "hipn": 8, "nod": 3, "turnh": -6, "roll": -8},
    "eat": {"fwp": 1, "shp": -82, "szp": 50, "elp": -42, "nod": -6, "shn": -5, "spn": 3, "szn": 8, "eln": -16, "roll": 5, "tilt": 2},
    "sad": {"nod": 24, "lean": 8, "shp": 4, "shn": 4, "szp": 15, "szn": 15, "elp": -6, "eln": -10, "roll": 8, "tilt": 3},
    "angry": {"shp": 8, "shn": 8, "spp": 14, "spn": 14, "elp": -32, "eln": -36, "lean": 7, "nod": 4, "roll": -5, "twist": 6, "tilt": -2},
    "clap": {"fwp": 0.32, "fwn": 0.32, "shp": -96, "shn": -96, "szp": 31, "szn": 31, "spp": 10, "spn": 10, "elp": -5,
             "eln": -5, "nod": -4, "roll": 6, "tilt": 2},
    "carry": {"shp": -45, "shn": -45, "szp": 28, "szn": 28, "elp": -45, "eln": -45, "roll": -4, "lean": -2},
    # mic: fist at chest height in front of the chin, the grille beside the mouth (not over the face)
    "mic": {"shp": -40, "szp": 35, "elp": -75, "shn": -20, "spn": 30, "eln": -24, "nod": -8, "lean": -3, "roll": -6, "tilt": -3, "twist": -8},
}
# poses that keep moving while held: (joint, amplitude deg, Hz)
POSE_ANIM = {"wave": [("spp", 20, 2.6)], "panic": [("szp", 8, 5.0), ("szn", 8, 5.0), ("turnh", 7, 2.5)],
             "clap": [("szp", 10, 4.0), ("szn", 10, 4.0)], "fistpump": [("elp", 14, 3.0)]}
# crowd members told to react together each pick one of these (deterministic per member)
POSE_VARIANTS = {"shock": ["shock", "shock", "shock2", "scared", "panic", "ahh"],
                 "scared": ["scared", "scared", "panic", "shock", "shock2"],
                 "cheer": ["cheer", "cheer", "fistpump", "clap", "wave", "shock2"],
                 "clap": ["clap", "clap", "cheer", "fistpump"], "wave": ["wave", "wave", "cheer", "point"],
                 "point": ["point", "point", "shock", "facepalm"]}
FACE_VARIANTS = {"shock": ["shock", "shock", "scared", "ahh", "stars"], "scared": ["scared", "scared", "shock", "cry"],
                 "grin": ["grin", "grin", "smile", "laughcry", "wink"], "smile": ["smile", "grin", "smug"]}
# idle variety for crowds: (pose, weight); statues are frozen mid-joke
CROWD_POSES = [("idle", 3), ("crowd", 2), ("crossarms", 2), ("thinkchin", 1), ("lean", 2), ("point", 1),
               ("shrug", 1), ("wave", 2), ("clap", 2), ("cheer", 1), ("akimbo", 2), ("fistpump", 1), ("sad", 1)]
STATUE_POSES = [("mic", 4), ("shrug", 3), ("shock", 2), ("facepalm", 2), ("point", 2), ("akimbo", 1),
                ("thinkchin", 1), ("fistpump", 1), ("cheer", 1), ("wave", 1), ("panic", 1), ("lean", 1), ("ahh", 1)]
CROWD_FACES = ["smile", "smile", "grin", "grin", "smug", "wink", "sideeye", "deadpan", "laughcry", "shock",
               "stars", "determined"]
STATUE_FACES = ["grin", "grin", "wink", "smug", "laughcry", "shock", "ahh", "teary", "cry", "deadpan", "sideeye"]
JOINTS = ["shp", "shn", "spp", "spn", "szp", "szn", "elp", "eln", "fwp", "fwn", "gpx", "gpy", "gnx", "gny",
          "hipp", "hipn", "lean", "twist", "tilt", "nod", "turnh", "roll", "crouch"]
HC = (0, 0, 0.64)          # head centre in neck space (sits on the torso: no gap)
NECK_Z = 2.0               # neck (torso top) in body space
SHX, SHZ = 1.5, 1.5        # shoulder pivots in body space
HIDES_HAIR = {"helmet", "hairnet", "firehelmet"}
SKINS = ["#F5C59A", "#E0A878", "#C68642", "#8D5524", "#FFDBAC", "#F1C27D"]
CLOTH = ["#E5262B", "#2D5BFF", "#2ECC40", "#FFD21F", "#FF7A1A", "#8E44AD", "#16C2C2", "#FF5FA2",
         "#1E2A5A", "#F2F2F2", "#2B2B2B", "#7ED957", "#3FA9F5", "#B5651D"]
HAIRC = ["#1A1A1A", "#4A2E1A", "#8B4513", "#E67E22", "#F2D16B", "#5B3A1E", "#9E9E9E"]
STYLES = ["short", "spiky", "bun", "ponytail", "long", "afro"]
# arm segments (shoulder space): upper arm +0.5..-0.5, elbow at -0.5, forearm 0.82, hand 0.44
ELBOW, FOREARM, HAND = 0.5, 0.82, 0.44
if BRICK:
    import brickfig
    HC, NECK_Z, (SHX, SHZ), (ELBOW, FOREARM, HAND) = brickfig.HC, brickfig.NECK_Z, (brickfig.SHX, brickfig.SHZ), brickfig.ARM


def hair_parts(style, col, parent, nm):
    """Layered hair: a cap, a back piece, then style pieces (bevelled chunks, rounded locks, spikes) and a
    fringe that hangs over the forehead. Every piece is named <nm>_hair / _hl<k> / a style name (look.HAIR_RE)."""
    if BRICK:
        return brickfig.hair_parts(style, col, parent, nm)
    h = []
    hx, hy, hz = HC
    k = [0]

    def add(mesh, loc, size, rot=(0, 0, 0), name=None):
        if name is None:
            name = f"{nm}_hl{k[0]}"
            k[0] += 1
        h.append(part(name, mesh, (hx + loc[0], hy + loc[1], hz + loc[2]), size, col, parent, rot=rot))
        return h[-1]

    def fringe(xs, z=0.52, y=-0.56, size=(0.62, 0.3, 0.36), tilt=-24, sweep=-16):
        """Bangs: overlapping swept locks across the forehead (each a flattened rounded chunk)."""
        for i, x in enumerate(xs):
            add("sphere", (x, y - 0.02 * (i % 2), z - 0.035 * (i % 2)), size, rot=(tilt, sweep, sweep * 0.6))

    if style != "afro":
        add("sphere", (0, 0.04, 0.47), (1.4, 1.4, 0.68), name=nm + "_hair")
        add("sphere", (0, 0.2, 0.16), (1.36, 1.02, 1.0))                 # back of the head down to the nape
    if style == "short":
        fringe((-0.3, 0.02, 0.32))
        for s in (-1, 1):
            add("sphere", (0.6 * s, -0.12, 0.3), (0.28, 0.5, 0.5))      # sideburn tufts
        add("cone", (0.12, 0.3, 0.86), (0.3, 0.3, 0.4), rot=(-30, 20, 0))   # cowlick at the crown
    elif style == "spiky":
        fringe((-0.26, 0.06, 0.34), size=(0.5, 0.28, 0.34))
        for i, (dx, dy, rx, ry) in enumerate(((0, 0, 0, 0), (-0.38, 0.1, 8, -18), (0.38, 0.1, 8, 18),
                                              (-0.2, 0.42, -18, -8), (0.2, 0.42, -18, 8), (0, -0.3, 22, 0))):
            add("cone", (dx, dy, 0.9), (0.45, 0.45, 0.62), rot=(rx, ry, 0), name=f"{nm}_spike{i}")
    elif style == "bun":
        add("sphere", (0, 0.25, 0.98), (0.66, 0.66, 0.62), name=nm + "_bun")
        add("cyl", (0, 0.22, 0.78), (0.5, 0.5, 0.1), rot=(-20, 0, 0))     # hair tie
        add("sphere", (-0.18, -0.56, 0.53), (0.86, 0.3, 0.34), rot=(-18, 0, 14))   # side-swept fringe
        add("sphere", (0.38, -0.5, 0.5), (0.4, 0.26, 0.32), rot=(-18, 0, -10))
    elif style == "ponytail":
        fringe((-0.3, 0.02, 0.32), sweep=14)
        add("cyl", (0, 0.6, 0.42), (0.34, 0.34, 0.16), rot=(80, 0, 0))   # tie
        add("sphere", (0, 0.72, 0.32), (0.52, 0.52, 0.52), name=nm + "_pt1")
        add("cyl", (0, 0.8, -0.22), (0.36, 0.36, 0.9), rot=(-12, 0, 0), name=nm + "_pt2")
        add("sphere", (0, 0.84, -0.68), (0.4, 0.4, 0.44), name=nm + "_pt3")
    elif style == "long":
        add("bcube", (0, 0.42, -0.3), (1.34, 0.46, 1.42), name=nm + "_long")
        for s in (-1, 1):
            add("bcube", (0.6 * s, 0.02, -0.18), (0.22, 0.86, 1.18))       # side curtains
            add("sphere", (0.26 * s, -0.58, 0.52), (0.62, 0.26, 0.34), rot=(-20, 0, -16 * s))   # centre part
    elif style == "afro":
        add("sphere", (0, 0.15, 0.45), (1.75, 1.65, 1.3), name=nm + "_afro")
        for i in range(8):
            a = 2 * pi * i / 8
            add("sphere", (0.68 * cos(a), 0.15 + 0.6 * sin(a), 0.7 + 0.12 * (i % 2)), (0.8, 0.8, 0.72))
        add("sphere", (0, 0.1, 1.0), (1.1, 1.0, 0.6))
    elif style == "milo":
        # messy red spikes in two rings, spiky fringe over the forehead, and the one curl (ahoge) on top
        h[0].scale = (1.44, 1.44, 0.74)
        for i, (dx, dy, rx, ry) in enumerate(((0, -0.5, 28, 0), (-0.42, -0.4, 22, -25), (0.42, -0.4, 22, 25),
                                              (-0.62, 0.05, 0, -50), (0.62, 0.05, 0, 50), (-0.4, 0.45, -30, -25),
                                              (0.4, 0.45, -30, 25), (0, 0.6, -45, 0))):
            add("cone", (dx, dy, 0.62), (0.55, 0.55, 0.75), rot=(rx, ry, 0), name=f"{nm}_mspike{i}")
        for i, (dx, dy, rx, ry, s) in enumerate(((-0.2, -0.1, 12, -12, 0.5), (0.22, -0.05, 10, 14, 0.48),
                                                 (0, 0.25, -14, 0, 0.5), (-0.3, 0.3, -18, -20, 0.42),
                                                 (0.32, 0.28, -16, 22, 0.42))):
            add("cone", (dx, dy, 0.88), (s, s, 0.7), rot=(rx, ry, 0))     # inner ring, taller
        for i, x in enumerate((-0.4, -0.14, 0.14, 0.4)):                  # fringe spikes over the forehead
            add("cone", (x, -0.6, 0.56), (0.3, 0.22, 0.36), rot=(160, 0, 10 * x / 0.4))
        for s in (-1, 1):                                                   # sideburn locks hugging the head
            add("cone", (0.6 * s, -0.12, 0.36), (0.2, 0.42, 0.5), rot=(180, 0, -8 * s))
        add("cone", (0.05, 0.05, 1.12), (0.22, 0.22, 0.75), rot=(0, 25, 0), name=nm + "_curl1")
        add("cone", (0.32, 0.05, 1.42), (0.18, 0.18, 0.45), rot=(0, 125, 0), name=nm + "_curl2")
    elif style == "swoop":
        add("sphere", (-0.25, -0.2, 0.78), (1.3, 0.9, 0.55), rot=(0, -18, 0), name=nm + "_swoop")
        add("sphere", (0.12, -0.42, 0.86), (0.9, 0.5, 0.5), rot=(-20, -12, -10))      # quiff
        add("sphere", (0.45, -0.5, 0.5), (0.36, 0.24, 0.36), rot=(-20, 0, -12))
    elif style == "pigtails":
        fringe((-0.3, 0.02, 0.32), size=(0.56, 0.3, 0.34), sweep=0)
        for dx in (-0.78, 0.78):
            s = 1 if dx > 0 else -1
            add("sphere", (0.62 * s, 0.18, 0.42), (0.26, 0.3, 0.3))                   # tie
            h.append(part(f"{nm}_pig{dx}", "sphere", (hx + dx, hy + 0.2, hz + 0.25), (0.55, 0.55, 0.75), col,
                          parent))
            add("sphere", (dx + 0.1 * s, 0.22, -0.18), (0.42, 0.42, 0.52))
    return h


def acc_parts(kind, col, ch):
    """Accessory objects for one character. Returns the list of objects."""
    if BRICK:
        P = brickfig.acc_parts(kind, col, ch)
        if P is not None:
            return P
    nm, P = ch.name + "_" + kind, []
    hx, hy, hz = HC
    if kind == "dress":
        P.append(part(nm, "frustum", (0, 0, -1.0), (3.6, 2.6, 2.1), col or "#FFFFFF", ch.body))
    elif kind == "veil":
        P.append(part(nm, "bcube", (hx, hy + 0.66, hz - 0.1), (1.5, 0.12, 2.1), col or "#FFFFFF", ch.neck))
        P.append(part(nm + "f", "sphere", (hx + 0.45, hy + 0.3, hz + 0.62), (0.35, 0.35, 0.35), "#FF7BAC", ch.neck))
    elif kind == "tux":
        P.append(part(nm, "bcube", (0, -0.5, 1.15), (0.7, 0.06, 1.6), "#FFFFFF", ch.body))
        P.append(part(nm + "b", "bcube", (0, -0.55, 1.8), (0.62, 0.08, 0.26), "#E5262B", ch.body))
    elif kind == "vest":
        P.append(part(nm, "bcube", (0, 0, 1.2), (2.08, 1.08, 1.55), col or "#C9A66B", ch.body))
        for dx in (-0.5, 0.5):
            P.append(part(nm + f"p{dx}", "bcube", (dx, -0.56, 0.95), (0.5, 0.05, 0.42), "#A88850", ch.body))
    elif kind == "apron":
        P.append(part(nm, "bcube", (0, -0.53, 0.55), (1.7, 0.06, 2.5), col or "#FFFFFF", ch.body))
    elif kind == "hairnet":
        P.append(part(nm, "sphere", (hx, hy + 0.06, hz + 0.5), (1.42, 1.42, 0.7), col or "#9FD3FF", ch.neck))
    elif kind == "helmet":
        P.append(part(nm, "sphere", (hx, hy + 0.1, hz + 0.32), (1.52, 1.52, 1.12), col or "#F2C12E", ch.neck))
        for dz in (-0.2, -0.38):
            P.append(part(nm + f"m{dz}", "bcube", (hx, hy - 0.74, hz + dz), (1.0, 0.08, 0.08), "#9A9A9A", ch.neck))
        P.append(part(nm + "mv", "bcube", (hx, hy - 0.74, hz - 0.29), (0.08, 0.08, 0.26), "#9A9A9A", ch.neck))
    elif kind == "firehelmet":
        P.append(part(nm, "sphere", (hx, hy + 0.05, hz + 0.6), (1.46, 1.46, 0.82), col or "#D7262B", ch.neck))
        P.append(part(nm + "b", "cyl", (hx, hy + 0.2, hz + 0.52), (1.95, 2.1, 0.08), col or "#D7262B", ch.neck))
    elif kind == "clothespin":
        for dx in (-0.07, 0.07):
            P.append(part(nm + f"{dx}", "bcube", (hx + dx, hy - 0.66, hz - 0.03), (0.11, 0.28, 0.34), "#D9B26F", ch.neck))
    elif kind == "tutu":
        P.append(part(nm, "cyl", (0, 0, 0.08), (3.0, 2.4, 0.32), col or "#FF8FC8", ch.body))
        P.append(part(nm + "2", "cyl", (0, 0, -0.14), (3.3, 2.7, 0.2), "#FFC0E0", ch.body))
    elif kind == "whistle":
        P.append(part(nm, "cyl", (0.35, -0.56, 1.35), (0.2, 0.2, 0.34), "#C9C9C9", ch.body, rot=(0, 90, 0)))
    elif kind in ("cap", "cap_back"):
        P.append(part(nm, "sphere", (hx, hy + 0.06, hz + 0.52), (1.4, 1.4, 0.64), col or "#E5262B", ch.neck))
        by = 0.78 if kind == "cap_back" else -0.78
        P.append(part(nm + "b", "bcube", (hx, hy + by, hz + 0.45), (0.95, 0.75, 0.08), col or "#E5262B", ch.neck))
    elif kind == "shirtfront":
        P.append(part(nm, "bcube", (0, -0.51, 1.2), (0.6, 0.04, 1.6), "#FFFFFF", ch.body))
    elif kind == "tie":
        P.append(part(nm, "bcube", (0, -0.54, 1.25), (0.26, 0.05, 1.3), col or "#E5262B", ch.body))
    elif kind == "stripes":
        for dz in (0.5, 1.4):
            P.append(part(nm + f"{dz}", "bcube", (0, 0, dz), (2.04, 1.04, 0.16), "#F2F2F2", ch.body))
    # ---- Milo cast signatures
    elif kind == "jacket":
        # an open jacket worn as a shell over the tee: a body a size bigger than the torso, two front panels
        # standing off the shirt, lapels folded back in a V, a stand-up collar round the back of the neck, a hem
        # band, and cuffs on the forearms (the sleeves themselves are the arm colour: sleeve_col)
        c = col or "#1E1E24"
        lit = shade(c, 1.14)
        P.append(part(nm + "b", "bcube", (0, 0.07, 1.0), (2.18, 0.98, 2.1), c, ch.body))
        for s in (-1, 1):
            P.append(part(nm + f"f{s}", "bcube", (0.77 * s, -0.52, 0.98), (0.62, 0.15, 2.12), c, ch.body))
            P.append(part(nm + f"lap{s}", "bcube", (0.5 * s, -0.62, 1.58), (0.34, 0.07, 0.92), lit, ch.body,
                          rot=(-6, 21 * s, 0)))
            P.append(part(nm + f"hem{s}", "bcube", (0.77 * s, -0.53, 0.1), (0.66, 0.2, 0.2), lit, ch.body))
        P.append(part(nm + "hemb", "bcube", (0, 0.1, 0.1), (2.24, 0.96, 0.2), lit, ch.body))
        P.append(part(nm + "col", band_mesh(r=0.56, h=0.4, th=0.12, gap=radians(118), flare=0.1), (0, 0.03, 1.94),
                      (1, 1, 1), c, ch.body))
        for i, e in enumerate(ch.elbow):
            cf = part(nm + f"cuff{i}", "bcube", (0, 0, -FOREARM + 0.16), (1.08, 1.08, 0.26), lit, e)
            cf["cuff"] = 1
            P.append(cf)
    elif kind == "pendant":          # black cord V and a red pendant
        for dx, rz in ((-0.2, -24), (0.2, 24)):
            P.append(part(nm + f"cord{dx}", "bcube", (dx, -0.53, 1.62), (0.05, 0.03, 0.85), "#111111", ch.body,
                          rot=(0, rz, 0)))
        P.append(part(nm + "gem", "bcube", (0, -0.56, 1.12), (0.24, 0.07, 0.4), col or "#D81E2A", ch.body))
    elif kind == "glasses":          # round black rims, bridge and arms, over the eyes
        for dx in (-0.27, 0.27):
            P.append(part(nm + f"r{dx}", "ring", (hx + dx, hy - 0.66, hz + 0.19), (0.58, 1, 0.58), col or "#141414",
                          ch.neck))
            P.append(part(nm + f"a{dx}", "bcube", (hx + dx * 2.2, hy - 0.3, hz + 0.21), (0.05, 0.7, 0.05),
                          col or "#141414", ch.neck))
        P.append(part(nm + "br", "bcube", (hx, hy - 0.67, hz + 0.21), (0.1, 0.04, 0.04), col or "#141414", ch.neck))
    elif kind == "headphones":       # round the neck
        P.append(part(nm + "band", "bcube", (0, 0.3, 2.1), (1.5, 0.16, 0.16), "#F2F2F2", ch.body))
        for dx in (-0.62, 0.62):
            P.append(part(nm + f"cup{dx}", "cyl", (dx, -0.1, 2.15), (0.5, 0.5, 0.26), "#F2F2F2", ch.body,
                          rot=(0, 90, 0)))
    elif kind == "bow":
        for dx, ry in ((-0.22, -30), (0.22, 30)):
            P.append(part(nm + f"{dx}", "cone", (hx + dx + 0.35, hy + 0.3, hz + 0.95), (0.3, 0.2, 0.45),
                          col or "#E5262B", ch.neck, rot=(0, 90 + ry, 0)))
    elif kind == "shades_up":
        P.append(part(nm, "bcube", (hx, hy - 0.35, hz + 0.75), (1.1, 0.2, 0.22), "#141414", ch.neck, rot=(-25, 0, 0)))
    elif kind == "chain":
        P.append(part(nm, "bcube", (0, -0.53, 1.6), (1.1, 0.05, 0.1), col or "#F2C12E", ch.body))
        P.append(part(nm + "d", "bcube", (0, -0.55, 1.35), (0.28, 0.06, 0.32), col or "#F2C12E", ch.body))
    elif kind == "mustache":
        P.append(part(nm, "bcube", (hx, hy - 0.63, hz + 0.0), (0.52, 0.07, 0.13), col or "#3B2A1A", ch.neck))
    # ---- transformation looks (forms)
    elif kind == "rock":
        P.append(part(nm, "sphere", (0, 0, 0.0), (3.2, 2.6, 3.4), col or "#8A8A8A", ch.body))
        for i, (dx, dz) in enumerate(((-0.9, 0.9), (0.8, -0.6), (0.2, 1.4))):
            P.append(part(nm + f"l{i}", "sphere", (dx, -0.9, dz), (0.9, 0.6, 0.7), "#767676", ch.body))
    elif kind == "paper":
        P.append(part(nm, "bcube", (0, -0.1, -0.2), (2.6, 1.3, 3.9), col or "#F7F7F2", ch.body, rot=(0, 0, 4)))
        for dz in (-1.2, -0.6, 0.0, 0.6):
            P.append(part(nm + f"ln{dz}", "bcube", (0, -0.77, dz), (2.2, 0.03, 0.06), "#9CC3F0", ch.body))
    elif kind == "scissors":
        for s in (-1, 1):
            P.append(part(nm + f"bl{s}", "bcube", (0.9 * s, -0.3, 2.4), (0.4, 0.2, 3.4), "#C9CED6", ch.body,
                          rot=(0, 18 * s, 0)))
            P.append(part(nm + f"h{s}", "ring", (0.75 * s, -0.6, -0.2), (1.4, 2.0, 1.4), "#E5262B", ch.body))
    elif kind == "pizza":            # a slice on the chest with pepperoni
        P.append(part(nm, "prism", (0, -0.56, 2.0), (0.12, 1.9, 2.1), "#F4B942", ch.body, rot=(0, 180, 90)))
        P.append(part(nm + "crust", "bcube", (0, -0.6, 1.95), (2.0, 0.16, 0.3), "#C9822E", ch.body))
        for i, (dx, dz) in enumerate(((0, 1.3), (-0.4, 0.8), (0.4, 0.75), (0, 0.45))):
            P.append(part(nm + f"p{i}", "cyl", (dx, -0.64, dz), (0.42, 0.42, 0.06), "#C0392B", ch.body,
                          rot=(90, 0, 0)))
    elif kind == "pep_arms":
        for i, s in enumerate(ch.sh):
            P.append(part(nm + f"{i}u", "cyl", (0, -0.52, -0.1), (0.42, 0.42, 0.06), "#C0392B", s, rot=(90, 0, 0)))
            P.append(part(nm + f"{i}f", "cyl", (0, -0.5, -0.4), (0.42, 0.42, 0.06), "#C0392B", ch.elbow[i],
                          rot=(90, 0, 0)))
    elif kind == "olives":
        for i, (dx, dz) in enumerate(((-0.35, 0.45), (0.3, 0.55), (0.0, -0.4), (0.45, -0.25))):
            P.append(part(nm + f"{i}", "sphere", (hx + dx, hy - 0.6, hz + dz), (0.2, 0.12, 0.2), "#1A1A1A", ch.neck))
    elif kind == "feathers":
        for i, (dx, dz) in enumerate(((-0.6, 1.6), (0.6, 1.5), (0, 0.9), (-0.7, 0.4), (0.7, 0.5), (0, 1.9))):
            P.append(part(nm + f"{i}", "sphere", (dx, -0.45, dz), (0.8, 0.5, 0.7), "#FFFFFF", ch.body))
    elif kind == "beak":
        P.append(part(nm, "cone", (hx, hy - 0.8, hz - 0.12), (0.35, 0.35, 0.5), "#F39C12", ch.neck, rot=(90, 0, 0)))
        for i, dy in enumerate((-0.25, 0.0, 0.25)):
            P.append(part(nm + f"comb{i}", "sphere", (hx, hy + dy, hz + 0.95), (0.18, 0.3, 0.4), "#E5262B", ch.neck))
    elif kind == "wings":
        for i, s in enumerate(ch.sh):
            P.append(part(nm + f"{i}", "bcube", (0.5 if i == 0 else -0.5, 0.1, -0.6), (0.5, 1.4, 1.8), "#FFFFFF", s))
    elif kind == "lunchbox":
        P.append(part(nm, "bcube", (0, -0.45, 0), (1.1, 0.8, 0.5), col or "#3FA9F5", ch.grip[0]))
    else:
        raise KeyError(kind)
    return P


class Char:
    ALL = []

    def __init__(self, name, pos, hd=0.0, skin="#F1C27D", hair="short", hair_col="#4A2E1A",
                 outfits=None, outfit="own", face="smile", scale=1.0, crowd=False, props=()):
        self.name, self.scale, self.crowd = name, scale, crowd
        self.pos0, self.hd0 = Vector((pos[0], pos[1], pos[2] if len(pos) > 2 else 0.0)), hd
        self.root = empty(name, self.pos0)
        self.root.scale = (scale,) * 3
        self.body = empty(name + "_body", (0, 0, 2), self.root)
        if BRICK:
            brickfig.build_rig(self, name, skin)
        else:
            self._rig_r6(name, skin)
        self.skin, self.hair_col = skin, hair_col
        self._finish(name, hair, hair_col, outfits, outfit, face, crowd, props)

    def _rig_r6(self, name, skin):
        self.torso = part(name + "_torso", "bcube", (0, 0, 1), (2, 1, 2), "#FFFFFF", self.body)
        self.neck = empty(name + "_neck", (0, 0, 2), self.body)
        self.head = part(name + "_head", "head", HC, (1, 1, 1), skin, self.neck)
        self.head["face"] = 0.0
        self.neckp = part(name + "_neckp", "cyl", (0, 0, 0.08), (0.82, 0.82, 0.3), skin, self.neck)
        # arms: shoulder -> upper arm (+ sleeve) -> elbow -> forearm -> wrist -> mitten hand -> grip (props)
        self.sh = [empty(name + "_shp", (1.5, 0, 1.5), self.body), empty(name + "_shn", (-1.5, 0, 1.5), self.body)]
        self.arm = [part(name + f"_arm{i}", "bcube", (0, 0, 0.0), (1, 1, 1.0), skin, s) for i, s in enumerate(self.sh)]
        self.sleeve = [part(name + f"_slv{i}", "bcube", (0, 0, 0.135), (1.04, 1.04, 0.79), "#FFFFFF", s)   # top 0.03 above the arm's (no z-fight)
                       for i, s in enumerate(self.sh)]
        self.elbow = [empty(name + f"_elb{i}", (0, 0, -ELBOW), s) for i, s in enumerate(self.sh)]
        # forearm reaches up into the upper arm so the elbow never opens a gap when it bends
        self.farm = [part(name + f"_farm{i}", "bcube", (0, 0, -FOREARM / 2 + 0.12), (0.96, 0.96, FOREARM + 0.24),
                          skin, e) for i, e in enumerate(self.elbow)]
        self.wrist = [empty(name + f"_wr{i}", (0, 0, -FOREARM), e) for i, e in enumerate(self.elbow)]
        self.hand, self.grip = [], []
        for i, w in enumerate(self.wrist):
            inner = -1 if i == 0 else 1                  # thumb on the inner-front corner
            # one soft toy mitten + a rounded thumb (no finger planks); a held prop swaps in props._fist
            self.hand.append(part(name + f"_hand{i}", "sbox", (0, -0.02, -0.25), (0.84, 0.8, 0.58), skin, w))
            self.hand.append(part(name + f"_thumb{i}", soft_box(0.26, 0.28, 0.44, k=0.48), (0.34 * inner, -0.25, -0.17),
                                  (0.26, 0.28, 0.44), skin, w, rot=(-10, 0, 14 * inner)))
            self.grip.append(empty(name + f"_grip{i}", (0, -0.1, -HAND / 2), w))
        self.hip = [empty(name + "_hipp", (0.5, 0, 0), self.body), empty(name + "_hipn", (-0.5, 0, 0), self.body)]
        self.leg = [part(name + f"_leg{i}", "bcube", (0, 0, -0.81), (1, 1, 1.62), skin, h) for i, h in enumerate(self.hip)]
        self.pant = [part(name + f"_pnt{i}", "bcube", (0, 0, -0.4), (1.03, 1.03, 0.8), "#FFFFFF", h)
                     for i, h in enumerate(self.hip)]
        # sneakers: a high ankle collar, a lower vamp running forward past the leg with a tongue and a lace strip
        # on top, a rounded rubber toe cap, and a rubber sole that sticks out all round (shoe colour = upper,
        # sole colour = sole + toe cap + laces)
        self.shoe, self.sole = [], []
        for i, h in enumerate(self.hip):
            self.shoe += [part(name + f"_shoe{i}", "bcube", (0, 0.04, -1.72), (1.08, 1.0, 0.42), "#FFFFFF", h),
                          part(name + f"_vamp{i}", "sbox", (0, -0.5, -1.8), (1.0, 0.72, 0.3), "#FFFFFF", h),
                          part(name + f"_tongue{i}", "sbox", (0, -0.47, -1.63), (0.46, 0.2, 0.22), "#FFFFFF", h,
                               rot=(-18, 0, 0))]
            self.sole += [part(name + f"_sole{i}", "bcube", (0, -0.2, -1.95), (1.12, 1.5, 0.14), "#F4F4F4", h),
                          part(name + f"_toe{i}", soft_box(0.98, 0.3, 0.26, k=0.48), (0, -0.78, -1.84),
                               (0.98, 0.3, 0.26), "#F4F4F4", h),
                          part(name + f"_lace{i}", "bcube", (0, -0.62, -1.655), (0.38, 0.3, 0.05), "#F4F4F4", h,
                               rot=(-8, 0, 0))]
        # tee neckline: a ribbed crew collar round the neck, a shade darker than the shirt
        self.collar = part(name + "_collar", band_mesh(r=0.46, h=0.12, th=0.1, dip=0.1), (0, 0, 1.97), (1, 1, 1),
                           "#FFFFFF", self.body)

    def _finish(self, name, hair, hair_col, outfits, outfit, face, crowd, props):
        self.hair = hair_parts(hair, hair_col, self.neck, name)
        self.outfits = outfits or {"own": dict(shirt=random.choice(CLOTH), sleeve="short",
                                                pants=random.choice(CLOTH), plen="long", shoes="#2B2B2B", acc=[])}
        self.acc = {}
        for o in self.outfits.values():
            for a in o.get("acc", []):
                kind, _, col = a.partition(":")
                if a not in self.acc:
                    self.acc[a] = acc_parts(kind, col or None, self)
        self.props = {}
        for p in props:
            self.props[p] = self.make_prop(p)
        # timelines
        self.moves = []            # (start, kind, data)
        self.poses = [(-10.0, "crowd" if crowd else "idle")]
        self.faces = [(-10.0, face)]
        self.wears = [(-10.0, outfit)]
        self.flails = []
        self.bob_windows = []      # crowd bob on
        self.extra = []            # callables(t) -> dict of overrides
        self.sizes = []            # (t, factor, dur): shrink / grow, back-eased
        self.lifts = []            # (t, dz, dur): float up / drop
        self.phase = random.random() * 10
        self.idle_hz, self.bob_hz = 0.7, 1.6   # breathing / crowd-bob rates (crowds stagger them)
        self.jbias = {}            # constant joint offsets on top of every pose (a crowd member's head turn)
        self.freeze = set()        # outfits that hold perfectly still (statues): no breathing, bob or pose wiggle
        self.variants = None       # crowd: random.Random picking a pose/face variant for staged reactions
        self.hide_shots = set()
        Char.ALL.append(self)

    def make_prop(self, p):
        nm = self.name + "_" + p
        g = self.grip[0]
        if p == "basket":
            o = [part(nm, "bcube", (0, -0.45, 0), (1.0, 0.6, 0.8), "#A0522D", g)]
            o += [part(nm + f"f{i}", "sphere", (-0.3 + 0.3 * i, -0.8, 0), (0.38,) * 3, "#FF7BAC", g)
                  for i in range(3)]
        elif p == "tissuebox":
            o = [part(nm, "bcube", (0, -0.45, 0), (0.95, 0.6, 0.7), "#7FD3D3", g),
                 part(nm + "t", "bcube", (0, -0.85, 0), (0.32, 0.5, 0.06), "#FFFFFF", g)]
        elif p == "tissue":
            o = [part(nm, "bcube", (0, -0.7, 0), (0.62, 1.4, 0.06), "#FFFFFF", g)]
        elif p == "cap_back":
            self.cap_e = empty(nm + "_e", HC, self.neck)
            hx, hy, hz = 0, 0, 0
            o = [part(nm, "sphere", (hx, hy + 0.06, hz + 0.52), (1.4, 1.4, 0.64), "#E5262B", self.cap_e),
                 part(nm + "b", "bcube", (hx, hy + 0.78, hz + 0.45), (0.95, 0.75, 0.08), "#E5262B", self.cap_e)]
        else:
            raise KeyError(p)
        return o

    # ---- timeline API
    def place(self, t, pos, hd=None):
        self.moves.append((t, "place", (Vector((pos[0], pos[1], pos[2] if len(pos) > 2 else 0.0)), hd)))

    def run(self, t0, t1, p1, mode="run"):
        self.moves.append((t0, "run", (t1, Vector((p1[0], p1[1], 0.0)), mode)))

    def turn(self, t, hd, lead=LEAD):
        self.moves.append((t - lead, "turn", hd))

    def turn_to(self, t, target, lead=LEAD):
        p, _, _ = self.base(t)
        self.turn(t, heading_to(Vector((target[0], target[1], p.z)) - p), lead)

    def spin(self, t0, t1, n=1):
        self.moves.append((t0, "spin", (t1, n)))

    def at(self, t, pose=None, face=None, lead=LEAD):
        if pose and pose not in POSES:
            raise KeyError(f"unknown pose {pose}")
        if self.variants:              # a crowd reacting together: each member picks its own take on it
            pose = pose and self.variants.choice(POSE_VARIANTS.get(pose, [pose]))
            face = face and self.variants.choice(FACE_VARIANTS.get(face, [face]))
        if pose:
            self.poses.append((t - lead, pose))
        if face:
            self.faces.append((t - lead, face))

    def wear(self, t, outfit):
        self.wears.append((t, outfit))

    def flail(self, t0, t1):
        self.flails.append((t0, t1))

    def resize(self, t, factor, dur=0.3, lead=LEAD):
        self.sizes.append((t - lead, factor, dur))

    def lift(self, t, dz, dur=0.5, lead=LEAD):
        self.lifts.append((t - lead, dz, dur))

    def size_at(self, t):
        f = 1.0
        for ts, k, d in sorted(self.sizes):
            if ts <= t:
                f = f + (k - f) * back((t - ts) / d)
        return f

    def lift_at(self, t):
        z = 0.0
        for ts, dz, d in sorted(self.lifts):
            if ts <= t:
                z = z + (dz - z) * smooth((t - ts) / d)
        return z

    # ---- evaluation
    def base(self, t):
        pos, hd, run = self.pos0.copy(), self.hd0, None
        for start, kind, d in sorted(self.moves, key=lambda m: m[0]):
            if start > t:
                break
            if kind == "place":
                pos = d[0].copy()
                if d[1] is not None:
                    hd = d[1]
            elif kind == "run":
                t1, p1, mode = d
                p1 = Vector((p1.x, p1.y, pos.z))
                dv = p1 - pos
                hd = heading_to(dv)
                if t <= t1:
                    pos = pos + dv * ((t - start) / (t1 - start))
                    run = (mode, t - start)
                else:
                    pos = p1
            elif kind == "turn":
                hd = hd + wrap(d - hd) * back((t - start) / SNAP)
            elif kind == "spin":
                t1, n = d
                hd = hd + 360 * n * smooth((t - start) / (t1 - start))
        return pos, hd, run

    def pose_at(self, t):
        ps = sorted(self.poses)
        i = max(k for k, (ts, _) in enumerate(ps) if ts <= t)
        cur = POSES[ps[i][1]]
        prev = POSES[ps[i - 1][1]] if i > 0 else cur
        e = back((t - ps[i][0]) / SNAP)
        j = {k: prev.get(k, 0.0) + (cur.get(k, 0.0) - prev.get(k, 0.0)) * e for k in JOINTS}
        for k, amp, hz in (() if self.frozen(t) else POSE_ANIM.get(ps[i][1], ())):
            j[k] += amp * min(1.0, e) * sin(2 * pi * hz * (t - ps[i][0]) + self.phase)
        return j

    def frozen(self, t):
        return bool(self.freeze) and max(self.wears, key=lambda w: w[0] if w[0] <= t else -1e9)[1] in self.freeze

    def face_at(self, t):
        return max((x for x in self.faces if x[0] <= t), key=lambda x: x[0])[1]

    def channels(self, t):
        pos, hd, run = self.base(t)
        j = self.pose_at(t)
        bounce = 0.0
        ph = self.phase
        if run:
            mode, tr = run
            if mode == "flail":
                self._flail(j, tr)
            else:
                k = 0.5 if mode == "walk" else 1.0
                s = sin(2 * pi * 2.6 * tr)
                j["hipp"], j["hipn"] = -52 * k * s, 52 * k * s
                j["shp"], j["shn"] = 58 * k * s, -58 * k * s
                j["spp"] = j["spn"] = 4
                j["szp"] = j["szn"] = 6
                j["elp"], j["eln"] = -30 - 25 * k * max(0, -s), -30 - 25 * k * max(0, s)
                j["lean"] += 9 * k
                bounce = 0.16 * k * abs(s)
        for a, b_ in self.flails:
            if a <= t <= b_:
                self._flail(j, t - a)
        for k, v in self.jbias.items():
            j[k] += v
        if self.frozen(t):
            pass                   # a statue: not even breathing
        elif self.crowd and any(a <= t < b_ for a, b_ in self.bob_windows):
            w = 2 * pi * self.bob_hz * t + ph
            bounce += 0.45 * 0.5 * (1 - cos(w))
            j["shp"] += 12 * sin(w)
            j["shn"] += 12 * sin(w + 0.6)
        else:
            w = 2 * pi * self.idle_hz * t + ph
            bounce += 0.035 * sin(w)
            j["shp"] += 2.5 * sin(w)
            j["shn"] += 2.5 * sin(w + 1)
        for fn in self.extra:
            fn(t, j)
        return pos, hd, j, bounce

    @staticmethod
    def _flail(j, tr):
        a, l = 2 * pi * 3.1 * tr, 2 * pi * 3.6 * tr
        j["shp"], j["shn"] = -150 + 28 * sin(a), -150 - 28 * sin(a)
        j["spp"] = j["spn"] = 18
        j["elp"], j["eln"] = -30 + 25 * sin(a), -30 - 25 * sin(a)
        j["hipp"], j["hipn"] = 32 * sin(l), -32 * sin(l)

    def head_top(self, t):
        pos, _, _ = self.base(t)
        pos = pos + Vector((0, 0, self.lift_at(t)))
        return pos + Vector((0, 0, 6.3 * self.scale * self.size_at(t))), pos

    def head_pos(self, t):
        """World position of the head centre at time t (for camera framing)."""
        pos, _, _ = self.base(t)
        return pos + Vector((0, 0, self.lift_at(t) + (2 + NECK_Z + HC[2]) * self.scale * self.size_at(t)))

    # ---- outfit colours and accessory visibility
    def write_outfits(self):
        """Outfit fields: shirt pants shoes sleeve plen acc, plus optional sleeve_col, sole, skin, hair_col,
        alpha (ghosts), headless (head, hair and head gear hidden) and parts={torso,slv,arm,pnt,leg,shoe,sole,hand,head,hair: colour} (statues)."""
        def apply(o):
            sl = o.get("sleeve", "short")
            pl = o.get("plen", "long")
            skin = o.get("skin", self.skin)
            slv = o.get("sleeve_col", o["shirt"])
            shoes = o.get("shoes", "#2B2B2B")
            lum = sum(int(shoes.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) / 765
            c = {
                "torso": o["shirt"], "slv": slv,
                "arm": slv if sl == "long" else skin,
                "pnt": o["pants"], "leg": o["pants"] if pl == "long" else skin,
                "shoe": shoes, "sole": o.get("sole", "#C9CCD6" if lum > 0.8 else "#F4F4F4"),
                "hand": skin, "head": skin, "hair": o.get("hair_col", self.hair_col),
            }
            pt = {k: v for k, v in o.get("parts", {}).items() if k not in ("acc", "cuff")}
            for k, src in (("sole", "shoe"), ("hand", "arm")):     # forms that only recolour the old parts
                if src in pt and k not in pt:
                    c[k] = pt[src]
            c.update(pt)
            tl = sum(int(c["torso"].lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) / 765
            c.setdefault("collar", shade(c["torso"], 1.25 if tl < 0.22 else 0.8))   # ribbing: a shade off the shirt
            return c
        keys_ = ("torso", "slv", "arm", "pnt", "leg", "shoe", "sole", "hand", "head", "hair", "collar")
        changes = {k: [] for k in keys_}
        vis = {a: [] for a in self.acc}
        hair_vis, head_vis, alpha = [], [], []
        on_head = {a for a, obs in self.acc.items() if any(under(ob, self.neck) for ob in obs)}
        for t, name in sorted(self.wears):
            f = max(0, frame(t))
            o = self.outfits[name]
            for k, c in apply(o).items():
                changes[k].append((f, c))
            for a in self.acc:
                vis[a].append((f, a in o.get("acc", []) and not (o.get("headless") and a in on_head)))
            hair_vis.append((f, not o.get("headless") and
                             not any(a.partition(":")[0] in HIDES_HAIR for a in o.get("acc", []))))
            head_vis.append((f, not o.get("headless")))
            alpha.append((f, o.get("alpha", 1.0)))
        fists = [ob for obs in self.acc.values() for ob in obs if "fist" in ob]
        objs = {"torso": [self.torso], "slv": self.sleeve, "arm": self.arm + self.farm, "pnt": self.pant,
                "leg": self.leg, "shoe": self.shoe, "sole": self.sole, "hand": self.hand + fists,
                "head": [self.head, self.neckp], "hair": self.hair, "collar": [self.collar]}
        for obs in self.acc.values():           # prints that take an outfit colour (brick: the tee under a jacket)
            for ob in obs:
                if "tint" in ob and ob["tint"] in objs:
                    objs[ob["tint"]] = objs[ob["tint"]] + [ob]
        for k, ch in changes.items():
            if k == "hair" and len(set(c for _, c in ch)) == 1 and ch[0][1] == self.hair_col:
                continue          # hair keeps its build colour
            for ob in objs[k]:
                for ci in range(3):
                    step_keys(ob, "color", ci, [(f, lin(c)[ci]) for f, c in ch])
        # stone forms grey the gear too: parts["acc"] = every accessory/prop (not the pendant gem, which glows),
        # parts["cuff"] = only the jacket cuffs (stone arms)
        tints = [(max(0, frame(t)), self.outfits[nm_].get("parts", {})) for t, nm_ in sorted(self.wears)]
        if any("acc" in p or "cuff" in p for _, p in tints):
            for obs in self.acc.values():
                for ob in obs:
                    if ob.name.endswith("_pendantgem") or "fist" in ob or "tint" in ob:
                        continue
                    base = tuple(ob.color)
                    seq = []
                    for f, p in tints:
                        tc = p.get("acc") or (p.get("cuff") if "cuff" in ob else None)
                        seq.append((f, lin(tc) if tc else base))
                    if any(v != base for _, v in seq):
                        for ci in range(3):
                            step_keys(ob, "color", ci, [(f, v[ci]) for f, v in seq])
        if len(set(a for _, a in alpha)) > 1 or alpha[0][1] < 1:
            body = [self.torso, self.head, self.neckp, self.collar] + self.sleeve + self.arm + self.farm + self.hand + self.pant
            body += self.leg + self.shoe + self.sole + self.hair
            body += [ob for obs in self.acc.values() for ob in obs]
            for ob in body:
                step_keys(ob, "color", 3, alpha)
        for a, ch in vis.items():
            for ob in self.acc[a]:
                step_keys(ob, "hide_render", -1, [(f, 0.0 if v else 1.0) for f, v in ch])
        # a hand holding a prop closes into the prop's fist: hide the open mitten (and its thumb) meanwhile
        held_by = {a: ob["fist"] for a, obs in self.acc.items() for ob in obs if "fist" in ob}
        for i in (0, 1):
            hv = [(max(0, frame(t)), any(held_by.get(a) == i for a in self.outfits[name].get("acc", [])))
                  for t, name in sorted(self.wears)]
            if any(v for _, v in hv):
                for ob in self.hand[2 * i:2 * i + 2]:
                    step_keys(ob, "hide_render", -1, [(f, 1.0 if v else 0.0) for f, v in hv])
        if len(set(v for _, v in head_vis)) > 1 or not head_vis[0][1]:      # headless form: head + neck peg go
            for ob in (self.head, self.neckp):
                step_keys(ob, "hide_render", -1, [(f, 0.0 if v else 1.0) for f, v in head_vis])
        if len(set(v for _, v in hair_vis)) > 1 or not hair_vis[0][1]:
            for ob in self.hair:
                step_keys(ob, "hide_render", -1, [(f, 0.0 if v else 1.0) for f, v in hair_vis])

    def write_motion(self, hidden_frames):
        frames = list(range(NF))
        names = ("x", "y", "z", "rz", "bz", "brx", "bry", "brz", "nrx", "nry", "nrz", "s0x", "s0y", "s0z", "s1x", "s1y",
                 "s1z", "e0", "e1", "f0", "f1", "g0x", "g0y", "g1x", "g1y", "h0", "h1", "s")
        ch = {k: [] for k in names}
        for f in frames:
            t = f / FPS
            pos, hd, j, bounce = self.channels(t)
            ch["x"].append(pos.x); ch["y"].append(pos.y)
            ch["z"].append(-1000.0 if f in hidden_frames else pos.z + self.lift_at(t))
            ch["s"].append(self.scale * self.size_at(t))
            ch["rz"].append(radians(hd))
            ch["bz"].append(2 + j["crouch"] + bounce)
            ch["brx"].append(radians(j["lean"])); ch["bry"].append(radians(j["tilt"]))
            ch["brz"].append(radians(j["twist"]))
            ch["nrx"].append(radians(j["nod"])); ch["nrz"].append(radians(j["turnh"]))
            ch["nry"].append(radians(j["roll"]))
            ch["s0x"].append(radians(j["shp"])); ch["s0y"].append(radians(-j["spp"])); ch["s0z"].append(radians(-j["szp"]))
            ch["s1x"].append(radians(j["shn"])); ch["s1y"].append(radians(j["spn"])); ch["s1z"].append(radians(j["szn"]))
            ch["e0"].append(radians(j["elp"])); ch["e1"].append(radians(j["eln"]))
            ch["f0"].append(j["fwp"]); ch["f1"].append(j["fwn"])
            # grips keep a held prop upright: undo the arm's pitch, then add the pose's own prop turn
            ch["g0x"].append(radians(-90 - j["shp"] - j["elp"] + j["gpx"])); ch["g0y"].append(radians(j["gpy"]))
            ch["g1x"].append(radians(-90 - j["shn"] - j["eln"] + j["gnx"])); ch["g1y"].append(radians(j["gny"]))
            ch["h0"].append(radians(j["hipp"])); ch["h1"].append(radians(j["hipn"]))
        K = lambda ob, path, i, v: keys(ob, path, i, frames, v)
        K(self.root, "location", 0, ch["x"]); K(self.root, "location", 1, ch["y"]); K(self.root, "location", 2, ch["z"])
        K(self.root, "rotation_euler", 2, ch["rz"])
        if self.sizes:
            for ax in range(3):
                K(self.root, "scale", ax, ch["s"])
        K(self.body, "location", 2, ch["bz"])
        K(self.body, "rotation_euler", 0, ch["brx"]); K(self.body, "rotation_euler", 2, ch["brz"])
        if any(ch["bry"]):
            K(self.body, "rotation_euler", 1, ch["bry"])
        K(self.neck, "rotation_euler", 0, ch["nrx"]); K(self.neck, "rotation_euler", 2, ch["nrz"])
        if any(ch["nry"]):                     # head tilt (roll), + = toward the +X (prop-hand) shoulder
            K(self.neck, "rotation_euler", 1, ch["nry"])
        for i, s in enumerate(self.sh):
            for ax, c in enumerate("xyz"):
                K(s, "rotation_euler", ax, ch[f"s{i}{c}"])
            K(self.elbow[i], "rotation_euler", 0, ch[f"e{i}"])
            if any(ch[f"f{i}"]):               # shoulder rolled forward/in
                sg = 1 if i == 0 else -1
                K(s, "location", 0, [sg * (SHX - 0.2 * v) for v in ch[f"f{i}"]])
                K(s, "location", 1, [-0.45 * v for v in ch[f"f{i}"]])
                K(s, "location", 2, [SHZ - 0.05 * v for v in ch[f"f{i}"]])
            if self.grip[i].children:          # only hands that hold something need their grip keyed
                K(self.grip[i], "rotation_euler", 0, ch[f"g{i}x"])
                if any(ch[f"g{i}y"]):
                    K(self.grip[i], "rotation_euler", 1, ch[f"g{i}y"])
        K(self.hip[0], "rotation_euler", 0, ch["h0"]); K(self.hip[1], "rotation_euler", 0, ch["h1"])
        if any(ch["bry"]):                     # a body tilt shifts the weight: the legs stay planted, upright
            for h in self.hip:
                K(h, "rotation_euler", 1, [-v for v in ch["bry"]])
        step_keys(self.head, '["face"]', 0, [(max(0, frame(t)), float(FACE_IDS[fc])) for t, fc in self.faces])


def under(ob, anc):
    """True if ob hangs (directly or through other objects) from anc."""
    p = ob.parent
    while p is not None:
        if p == anc:
            return True
        p = p.parent
    return False


def outfit(shirt, pants, shoes="#2B2B2B", sleeve="short", plen="long", acc=()):
    return dict(shirt=shirt, pants=pants, shoes=shoes, sleeve=sleeve, plen=plen, acc=list(acc))


# ---------------------------------------------------------------- puffs & particles
PUFFS = []
CAM = None


def puff(t, pos, size=1.0):
    PUFFS.append((t, Vector(pos), size))


def build_puffs():
    for n, (t, pos, s) in enumerate(PUFFS):
        root = empty(f"puff{n}", pos)
        con = root.constraints.new("TRACK_TO")
        con.target, con.track_axis, con.up_axis = CAM, "TRACK_NEGATIVE_Y", "UP_Z"
        f0, f1 = frame(t), frame(t + 0.6) + 1
        frames = list(range(max(0, f0 - 1), min(NF, f1 + 1)))
        rnd = random.Random(n)
        for i in range(9):
            a = 2 * pi * i / 8 + rnd.uniform(-0.3, 0.3)
            off = Vector((cos(a), rnd.uniform(-0.3, 0.3), sin(a))) * (0 if i == 8 else s * 0.55)
            r = s * rnd.uniform(0.5, 0.8) * (1.25 if i == 8 else 1.0)
            ob = part(f"puff{n}_s{i}", "sphere", off, (0.001,) * 3, "#FFFFFF", root, mat=MAT_PUFF, shadow=False)
            sc_, lx, lz = [], [], []
            for f in frames:
                u = f / FPS - t
                if u < 0 or u >= 0.55:
                    k = 0.0001
                    d = 0
                elif u < 0.14:
                    k = 0.35 + 0.65 * (1 - (1 - u / 0.14) ** 2)
                    d = 0
                else:
                    v = (u - 0.14) / 0.41
                    k = (1 - v * v) * (1 + 0.25 * v)
                    d = 0.5 * s * v
                sc_.append(max(0.0001, 2 * r * k))
                lx.append(off.x + cos(a) * d); lz.append(off.z + sin(a) * d)
            for ax in range(3):
                keys(ob, "scale", ax, frames, sc_)
            keys(ob, "location", 0, frames, lx); keys(ob, "location", 2, frames, lz)
            step_keys(ob, "hide_render", -1, [(0, 1.0), (f0, 0.0), (frame(t + 0.55), 1.0)])
        for i in range(7):
            a = 2 * pi * i / 7 + rnd.uniform(-0.2, 0.2)
            ob = part(f"puff{n}_star{i}", "star", (0, -0.4, 0), (0.001,) * 3, "#FFE14D", root, shadow=False)
            sc_, lx, lz, ry = [], [], [], []
            for f in frames:
                u = (f / FPS - t) / 0.6
                if u < 0 or u >= 1:
                    k, rr = 0.0001, 0
                else:
                    k = 0.42 * s * min(1, u / 0.12) * (1 - u ** 3)
                    rr = s * (0.3 + 1.7 * (1 - (1 - u) ** 2))
                sc_.append(max(0.0001, k))
                lx.append(cos(a) * rr); lz.append(sin(a) * rr)
                ry.append(2 * pi * 1.5 * max(0, u) * (1 if i % 2 else -1))
            for ax in range(3):
                keys(ob, "scale", ax, frames, sc_)
            keys(ob, "location", 0, frames, lx); keys(ob, "location", 2, frames, lz)
            keys(ob, "rotation_euler", 1, frames, ry)
            step_keys(ob, "hide_render", -1, [(0, 1.0), (f0, 0.0), (frame(t + 0.6), 1.0)])


def drifting(name, n, r_rng, path_fn, t_on, mat=MAT_POLLEN, t_off=None):
    """n spheres whose position per frame comes from path_fn(i, t) -> (Vector, scale_mult)."""
    frames = list(range(NF))
    rnd = random.Random(name)
    for i in range(n):
        r = rnd.uniform(*r_rng)
        ob = part(f"{name}{i}", "sphere", (0, 0, -1000), (2 * r,) * 3, "#F7D23E", mat=mat, shadow=False)
        xs, ys, zs, ss = [], [], [], []
        for f in frames:
            t = f / FPS
            if t < t_on or (t_off is not None and t >= t_off):
                xs.append(0); ys.append(0); zs.append(-1000); ss.append(2 * r)
                continue
            p, m = path_fn(i, t, rnd)
            xs.append(p.x); ys.append(p.y); zs.append(p.z); ss.append(max(0.0001, 2 * r * m))
        keys(ob, "location", 0, frames, xs); keys(ob, "location", 1, frames, ys); keys(ob, "location", 2, frames, zs)
        for ax in range(3):
            keys(ob, "scale", ax, frames, ss)


