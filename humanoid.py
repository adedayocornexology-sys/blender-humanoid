"""
Humanoid — Blender 4.2.1 LTS  (v9)
Correct human proportions, fused garment solids, real eye sockets, skull-fitted hair.
Renders a full-body plate and a head close-up.
Run: blender.exe --background --factory-startup --python humanoid.py
"""

import bpy
import bmesh
import math
import os
import random
import sys
import time
from mathutils import Vector, Matrix

PREVIEW = os.environ.get("HUM_MODE", "final")
if PREVIEW not in ("form", "light", "final"):
    PREVIEW = "final"

if PREVIEW == "form":
    RES_X, RES_Y = 480, 800
    SAMPLES = 16
elif PREVIEW == "light":
    RES_X, RES_Y = 480, 800
    SAMPLES = 32
else:
    RES_X, RES_Y = 560, 900
    SAMPLES = 24

SUFFIX = "" if PREVIEW == "final" else "_" + PREVIEW

# Renders go next to this script by default; override with HUM_OUT.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
OUT_DIR = os.environ.get("HUM_OUT") or os.path.join(_SCRIPT_DIR, "renders")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_BODY = os.path.join(OUT_DIR, "humanoid_v9%s.png" % SUFFIX)
OUT_HEAD = os.path.join(OUT_DIR, "humanoid_v9_head%s.png" % SUFFIX)
VOXEL_BODY = 0.0055
VOXEL_CLOTH = 0.0050

t_start = time.time()


def log(msg):
    print("[humanoid] %s" % msg)
    sys.stdout.flush()


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def link(obj):
    scene.collection.objects.link(obj)
    return obj


def finish(bm, name):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    return link(bpy.data.objects.new(name, mesh))


def loft(name, sections, segs=40):
    """sections: list of (z, rx, ry, yoff) -> closed lofted solid."""
    bm = bmesh.new()
    rings = []
    for (z, rx, ry, yoff) in sections:
        ring = []
        for s in range(segs):
            a = 2.0 * math.pi * s / segs
            ring.append(bm.verts.new((math.cos(a) * rx, yoff + math.sin(a) * ry, z)))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for s in range(segs):
            bm.faces.new((rings[i][s], rings[i][(s + 1) % segs],
                          rings[i + 1][(s + 1) % segs], rings[i + 1][s]))
    for ring, (z, rx, ry, yoff) in ((rings[0], sections[0]), (rings[-1], sections[-1])):
        cv = bm.verts.new((0.0, yoff, z))
        for s in range(segs):
            bm.faces.new((cv, ring[s], ring[(s + 1) % segs]))
    return finish(bm, name)


def tube(name, pts, radii, segs=28):
    pts = [Vector(p) for p in pts]
    n = len(pts)
    dirs = []
    for i in range(n):
        if i == 0:
            d = pts[1] - pts[0]
        elif i == n - 1:
            d = pts[-1] - pts[-2]
        else:
            d = pts[i + 1] - pts[i - 1]
        dirs.append(d.normalized())

    frames = []
    u = dirs[0].cross(Vector((0.0, 1.0, 0.0)))
    if u.length < 1e-5:
        u = dirs[0].cross(Vector((1.0, 0.0, 0.0)))
    u.normalize()
    for i in range(n):
        d = dirs[i]
        u = (u - d * u.dot(d))
        if u.length < 1e-6:
            u = d.cross(Vector((1.0, 0.0, 0.0)))
        u.normalize()
        v = d.cross(u).normalized()
        frames.append((u, v))

    bm = bmesh.new()
    rings = []
    for i in range(n):
        u, v = frames[i]
        rx, ry = radii[i]
        ring = []
        for s in range(segs):
            a = 2.0 * math.pi * s / segs
            ring.append(bm.verts.new(pts[i] + u * (math.cos(a) * rx) + v * (math.sin(a) * ry)))
        rings.append(ring)
    for i in range(n - 1):
        for s in range(segs):
            bm.faces.new((rings[i][s], rings[i][(s + 1) % segs],
                          rings[i + 1][(s + 1) % segs], rings[i + 1][s]))
    for ring, cpt in ((rings[0], pts[0]), (rings[-1], pts[-1])):
        cv = bm.verts.new(cpt)
        for s in range(segs):
            bm.faces.new((cv, ring[s], ring[(s + 1) % segs]))
    return finish(bm, name)


def ellipsoid(name, loc, scale, segs=32, rings=20, rot=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segs, ring_count=rings, radius=1.0, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    if rot:
        o.rotation_euler = rot
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.ops.object.shade_smooth()
    return o


def activate(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def sphere_cap(name, centre, radius, keep_top, cut, thickness=0.0022):
    """A lid: a spherical shell that hugs the eyeball, cut at the lid line."""
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=44, radius=1.0,
                                         location=centre)
    o = bpy.context.object
    o.name = name
    o.scale = (radius, radius, radius)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    if keep_top:
        doomed = [f for f in bm.faces if f.calc_center_median().z < cut]
    else:
        doomed = [f for f in bm.faces if f.calc_center_median().z > cut]
    if doomed:
        bmesh.ops.delete(bm, geom=doomed, context="FACES")
    bm.to_mesh(o.data)
    bm.free()
    activate(o)
    sol = o.modifiers.new("S", "SOLIDIFY")
    sol.thickness = thickness
    sol.offset = 1.0
    bpy.ops.object.modifier_apply(modifier="S")
    bpy.ops.object.shade_smooth()
    return o


def smooth_obj(obj, factor=0.5, iters=10):
    activate(obj)
    m = obj.modifiers.new("Relax", "SMOOTH")
    m.factor = factor
    m.iterations = iters
    bpy.ops.object.modifier_apply(modifier="Relax")
    bpy.ops.object.shade_smooth()


def remesh(obj, voxel, smooth_iters=6):
    activate(obj)
    obj.data.remesh_voxel_size = voxel
    bpy.ops.object.voxel_remesh()
    smooth_obj(obj, 0.5, smooth_iters)


def add_folds(obj, scale=0.09, strength=0.004):
    tex = bpy.data.textures.new(obj.name + "_Fold", "CLOUDS")
    tex.noise_scale = scale
    tex.noise_depth = 2
    activate(obj)
    m = obj.modifiers.new("Folds", "DISPLACE")
    m.texture = tex
    m.strength = strength
    m.mid_level = 0.5
    m.texture_coords = "GLOBAL"
    bpy.ops.object.modifier_apply(modifier="Folds")
    bpy.ops.object.shade_smooth()


def duplicate(obj, name):
    new = obj.copy()
    new.data = obj.data.copy()
    new.name = name
    link(new)
    return new


# ============================================================================
# 1. TORSO  — real proportions for a 1.79 m figure
# ============================================================================
log("lofting torso")
TORSO = [
    (0.820, 0.104, 0.086, 0.010),
    (0.860, 0.128, 0.096, 0.008),
    (0.905, 0.152, 0.104, 0.006),
    (0.960, 0.162, 0.108, 0.005),
    (1.020, 0.157, 0.106, 0.004),
    (1.080, 0.146, 0.101, 0.003),
    (1.140, 0.147, 0.101, 0.002),
    (1.200, 0.155, 0.106, 0.001),
    (1.260, 0.164, 0.110, 0.000),
    (1.320, 0.170, 0.112, 0.000),
    (1.375, 0.172, 0.111, 0.000),
    (1.415, 0.168, 0.106, 0.002),
    (1.450, 0.148, 0.097, 0.004),
    (1.475, 0.108, 0.081, 0.008),
    (1.500, 0.074, 0.067, 0.011),
    (1.530, 0.062, 0.060, 0.013),
    (1.565, 0.060, 0.058, 0.014),
]
torso = loft("Torso", TORSO, segs=44)

# ============================================================================
# 2. LIMBS
# ============================================================================
log("lofting limbs")
parts = [torso]

ARM_R = [(0.053, 0.051), (0.049, 0.047), (0.046, 0.044), (0.043, 0.041),
         (0.040, 0.038), (0.036, 0.034), (0.031, 0.030)]


def arm_points(side):
    """side -1 = figure's right (viewer left), +1 = figure's left."""
    fwd = 0.0 if side < 0 else 0.020     # left arm swings a touch forward
    return [
        (side * 0.176, 0.000, 1.442),
        (side * 0.196, 0.004, 1.356),
        (side * 0.207, 0.008 + fwd * 0.25, 1.268),
        (side * 0.213, 0.012 + fwd * 0.55, 1.180),
        (side * 0.216, 0.014 + fwd * 0.85, 1.092),
        (side * 0.218, 0.010 + fwd, 1.000),
        (side * 0.220, 0.006 + fwd, 0.928),
    ]


LEG = [(0.088, 0.000, 0.890), (0.093, 0.004, 0.800), (0.096, 0.008, 0.680),
       (0.098, 0.012, 0.560), (0.098, 0.014, 0.495), (0.097, 0.018, 0.400),
       (0.095, 0.012, 0.290), (0.093, 0.008, 0.180), (0.091, 0.006, 0.095)]
LEG_R = [(0.088, 0.084), (0.082, 0.078), (0.076, 0.073), (0.067, 0.065),
         (0.063, 0.061), (0.059, 0.057), (0.052, 0.050), (0.043, 0.042),
         (0.036, 0.035)]

for sx in (-1, 1):
    tag = "R" if sx < 0 else "L"

    # deltoid mass — modest; the shirt defines the shoulder line
    parts.append(ellipsoid("Deltoid_" + tag, (sx * 0.170, 0.002, 1.408),
                           (0.050, 0.054, 0.056), 28, 18))
    parts.append(tube("Arm_" + tag, arm_points(sx), ARM_R, segs=26))
    parts.append(tube("Leg_" + tag, [(sx * x, y, z) for (x, y, z) in LEG],
                      LEG_R, segs=26))

    # ---- hand: palm + fingers + thumb
    wx = sx * 0.220
    parts.append(ellipsoid("Palm_" + tag, (wx, 0.004, 0.892),
                           (0.017, 0.039, 0.046), 24, 16))
    for fi, (dy, ln) in enumerate(((-0.030, 0.050), (-0.010, 0.058),
                                   (0.011, 0.054), (0.030, 0.044))):
        parts.append(tube("Finger%d_%s" % (fi, tag),
                          [(wx + sx * 0.001, 0.004 + dy, 0.872),
                           (wx - sx * 0.002, 0.006 + dy, 0.872 - ln * 0.55),
                           (wx - sx * 0.005, 0.012 + dy, 0.872 - ln)],
                          [(0.0092, 0.0088), (0.0082, 0.0078), (0.0062, 0.0058)],
                          segs=12))
    parts.append(tube("Thumb_" + tag,
                      [(wx - sx * 0.008, -0.030, 0.906),
                       (wx - sx * 0.017, -0.045, 0.890),
                       (wx - sx * 0.023, -0.054, 0.872)],
                      [(0.0110, 0.0106), (0.0096, 0.0092), (0.0074, 0.0070)],
                      segs=12))

    # ---- foot: heel, arch, forefoot, toes
    parts.append(ellipsoid("Heel_" + tag, (sx * 0.092, 0.030, 0.048),
                           (0.041, 0.054, 0.048), 24, 16))
    parts.append(ellipsoid("Mid_" + tag, (sx * 0.092, -0.020, 0.042),
                           (0.043, 0.060, 0.040), 24, 16))
    parts.append(ellipsoid("Fore_" + tag, (sx * 0.092, -0.088, 0.034),
                           (0.045, 0.070, 0.032), 24, 16))
    parts.append(ellipsoid("Toe_" + tag, (sx * 0.092, -0.148, 0.026),
                           (0.040, 0.034, 0.024), 20, 14))

# ============================================================================
# 3. UNIFY BODY
# ============================================================================
log("joining body parts (%d objects)" % len(parts))
bpy.ops.object.select_all(action="DESELECT")
for o in parts:
    o.select_set(True)
bpy.context.view_layer.objects.active = torso
bpy.ops.object.join()
body = bpy.context.object
body.name = "Body"

log("voxel remesh body @ %.4f" % VOXEL_BODY)
remesh(body, VOXEL_BODY, 4)
log("body: %d verts" % len(body.data.vertices))

# ============================================================================
# 4. HEAD
# ============================================================================
log("sculpting head")
HEAD_C = Vector((0.0, 0.014, 1.665))
HEAD_R = Vector((0.0762, 0.0985, 0.1125))

bpy.ops.mesh.primitive_uv_sphere_add(segments=112, ring_count=84, radius=1.0, location=HEAD_C)
head = bpy.context.object
head.name = "Head"
head.scale = HEAD_R
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

# --- base skull shaping (local coords, head centred on origin) ---
for v in head.data.vertices:
    p = v.co.copy()
    if p.z < -0.020:
        f = min(1.0, (-p.z - 0.020) / (HEAD_R.z - 0.020))
        p.x *= (1.0 - 0.20 * (f ** 1.5))
        p.y *= (1.0 - 0.05 * f)
    if p.y > 0.030:
        p.y *= 0.945
    v.co = p

FEATURES = [
    ((0.000, -0.086,  0.024), 0.024, (0.0, -1.0,  0.0),  0.0080),  # nose bridge
    ((0.030, -0.080,  0.021), 0.030, (0.0, -1.0,  0.0),  0.0080),  # brow L
    ((-0.030, -0.080, 0.021), 0.030, (0.0, -1.0,  0.0),  0.0080),  # brow R
    ((0.052, -0.048, -0.004), 0.032, (0.62, -0.78, 0.0), 0.0075),  # cheekbone L
    ((-0.052, -0.048,-0.004), 0.032, (-0.62, -0.78, 0.0), 0.0075),  # cheekbone R
    ((0.000, -0.070, -0.092), 0.036, (0.0, -0.70, -0.72), 0.0080),  # chin
    ((0.031, -0.078,  0.002), 0.030, (0.0,  1.0,  0.0),  0.0050),   # socket L
    ((-0.031, -0.078, 0.002), 0.030, (0.0,  1.0,  0.0),  0.0050),   # socket R
    ((0.047, -0.040, -0.048), 0.026, (0.0,  1.0,  0.0),  0.0040),   # cheek hollow L
    ((-0.047, -0.040,-0.048), 0.026, (0.0,  1.0,  0.0),  0.0040),   # cheek hollow R
    ((0.070, -0.010,  0.044), 0.026, (-1.0, 0.0,  0.0),  0.0045),   # temple L
    ((-0.070, -0.010, 0.044), 0.026, (1.0,  0.0,  0.0),  0.0045),   # temple R
    ((0.000, -0.082,  0.066), 0.040, (0.0, -1.0,  0.0),  0.0040),   # forehead
    ((0.000, -0.094, -0.040), 0.020, (0.0, -1.0,  0.0),  0.0035),   # muzzle
]
for v in head.data.vertices:
    for c, r, d, s in FEATURES:
        w = math.exp(-(((v.co - Vector(c)).length / r) ** 2))
        v.co += Vector(d) * (s * w)
bpy.ops.object.shade_smooth()


def H(lx, ly, lz):
    """Head-local -> world (the head object is offset by HEAD_C)."""
    return (HEAD_C.x + lx, HEAD_C.y + ly, HEAD_C.z + lz)


SKULL = [head]

# ---- nose: tube along the bridge + tip + alae
SKULL.append(tube("Nose",
                  [H(0.0, -0.097, 0.034), H(0.0, -0.101, 0.016),
                   H(0.0, -0.104, 0.000), H(0.0, -0.106, -0.012)],
                  [(0.0060, 0.0054), (0.0072, 0.0066),
                   (0.0086, 0.0078), (0.0090, 0.0082)], segs=20))
SKULL.append(ellipsoid("NoseTip", H(0.0, -0.1068, -0.0158),
                       (0.0092, 0.0094, 0.0078), 24, 16))
for sx in (-1, 1):
    SKULL.append(ellipsoid("Ala_%s" % ("R" if sx < 0 else "L"),
                           H(sx * 0.0108, -0.0990, -0.0168),
                           (0.0062, 0.0072, 0.0054), 20, 14))

# ---- ears
for sx in (-1, 1):
    SKULL.append(ellipsoid("Ear_%s" % ("R" if sx < 0 else "L"),
                           H(sx * 0.0780, -0.008, -0.004),
                           (0.0090, 0.0225, 0.0315), 24, 16,
                           rot=(0.0, sx * 0.14, sx * -0.10)))

# ---- fuse the skull, nose and ears into one surface
log("fusing skull (%d pieces)" % len(SKULL))
bpy.ops.object.select_all(action="DESELECT")
for o in SKULL:
    o.select_set(True)
bpy.context.view_layer.objects.active = head
bpy.ops.object.join()
head = bpy.context.object
head.name = "Head"
activate(head)
head.data.remesh_voxel_size = 0.0022
bpy.ops.object.voxel_remesh()
m = head.modifiers.new("Relax", "SMOOTH")
m.factor = 0.30
m.iterations = 3
bpy.ops.object.modifier_apply(modifier="Relax")
bpy.ops.object.shade_smooth()
log("head: %d verts" % len(head.data.vertices))

# ============================================================================
# 5. HAIR — grown from the skull, natural hairline
# ============================================================================
log("growing hair")
HEAD_PARTS = [head]


def hairline(a):
    """a = angle from the front, 0..pi. Widow's peak, tapered temples, nape."""
    if a < 0.85:
        h = 0.052 - 0.004 * math.cos(2.0 * a)
    elif a < 1.55:
        h = 0.056 + 0.024 * (a - 0.85) / 0.70
    elif a < 2.10:
        h = 0.080 - 0.050 * (a - 1.55) / 0.55
    else:
        h = 0.030 - 0.026 * (a - 2.10) / (math.pi - 2.10)
    return h + 0.0012 * math.sin(a * 17.0) + 0.0007 * math.sin(a * 37.0 + 1.1)


# ---- under-layer: a thin dark shell so no scalp shows between the locks
hair = duplicate(head, "HairBase")
bmh = bmesh.new()
bmh.from_mesh(hair.data)
doomed = []
for f in bmh.faces:
    c = f.calc_center_median()
    ang = math.atan2(c.x, -c.y)
    if c.z <= hairline(abs(ang)) - 0.0015:
        doomed.append(f)
if doomed:
    bmesh.ops.delete(bmh, geom=doomed, context="FACES")
bmh.to_mesh(hair.data)
bmh.free()

for v in hair.data.vertices:
    v.co = v.co + v.normal * 0.0032
bpy.ops.object.shade_smooth()
activate(hair)
sol = hair.modifiers.new("Solidify", "SOLIDIFY")
sol.thickness = 0.0050
sol.offset = 0.0
bpy.ops.object.modifier_apply(modifier="Solidify")
bpy.ops.object.shade_smooth()
HEAD_PARTS.append(hair)


# ---- locks: ~1900 short coils rooted on the scalp, combed back and down
def build_locks(src, count=1900, seed=5):
    rng = random.Random(seed)
    cand = []
    for v in src.data.vertices:
        p = v.co
        if p.z > hairline(abs(math.atan2(p.x, -p.y))) + 0.0010:
            cand.append(v)
    cand.sort(key=lambda v: (round(v.co.z, 4), round(v.co.x, 4), round(v.co.y, 4)))
    stride = max(1, len(cand) // count)
    roots = cand[::stride]

    crown = Vector((0.0, 0.030, 0.088))
    bm = bmesh.new()
    for v in roots:
        p = v.co.copy()
        n = v.normal.copy()
        if n.length < 1e-6:
            continue
        n.normalize()
        flow = p - crown
        if flow.length < 1e-5:
            flow = Vector((0.0, 1.0, 0.0))
        flow = flow - n * flow.dot(n)
        if flow.length < 1e-5:
            flow = Vector((0.0, 0.0, -1.0))
        flow.normalize()

        # short coil: mostly along the normal, leaning with the comb direction
        axis = (n * 1.0 + flow * 0.62).normalized()
        axis = (axis + Vector((rng.uniform(-0.24, 0.24),
                               rng.uniform(-0.24, 0.24),
                               rng.uniform(-0.12, 0.12)))).normalized()

        length = rng.uniform(0.011, 0.025)
        r0 = rng.uniform(0.0032, 0.0050)

        u = axis.cross(Vector((0.0, 0.0, 1.0)))
        if u.length < 1e-4:
            u = axis.cross(Vector((1.0, 0.0, 0.0)))
        u.normalize()
        w = axis.cross(u).normalized()

        base = p - n * 0.0016
        rings = []
        for t, k in ((0.00, 1.00), (0.38, 0.74), (0.70, 0.40), (0.90, 0.16)):
            c = base + axis * (length * t) + n * (0.0032 * t * t)
            ring = []
            for s in range(5):
                a = 2.0 * math.pi * s / 5.0
                ring.append(bm.verts.new(c + u * (math.cos(a) * r0 * k)
                                         + w * (math.sin(a) * r0 * k)))
            rings.append(ring)
        for i in range(len(rings) - 1):
            for s in range(5):
                bm.faces.new((rings[i][s], rings[i][(s + 1) % 5],
                              rings[i + 1][(s + 1) % 5], rings[i + 1][s]))
        tip = bm.verts.new(base + axis * (length * 1.02) + n * 0.0032)
        for s in range(5):
            bm.faces.new((tip, rings[-1][s], rings[-1][(s + 1) % 5]))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("HairLocks")
    bm.to_mesh(mesh)
    bm.free()
    o = link(bpy.data.objects.new("HairLocks", mesh))
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.shade_smooth()
    return o


locks = build_locks(head)
log("hair: %d locks" % (len(locks.data.vertices) // 21))
HEAD_PARTS.append(locks)

# ---- eyes: eyeball, iris, pupil, and lids that hug the eyeball
EYE_R = 0.0120
EYE_Y = -0.0888
EYE_Z = 0.0020
for sx in (-1, 1):
    tag = "R" if sx < 0 else "L"
    ex = sx * 0.0315
    HEAD_PARTS.append(ellipsoid("Eye_" + tag, H(ex, EYE_Y, EYE_Z),
                                (EYE_R, EYE_R, EYE_R), 48, 32))
    HEAD_PARTS.append(ellipsoid("Iris_" + tag, H(ex, EYE_Y - 0.0096, EYE_Z),
                                (0.0058, 0.0030, 0.0058), 32, 20))
    HEAD_PARTS.append(ellipsoid("Pupil_" + tag, H(ex, EYE_Y - 0.0108, EYE_Z),
                                (0.0025, 0.0020, 0.0025), 20, 12))
    HEAD_PARTS.append(sphere_cap("LidUp_" + tag, H(ex, EYE_Y, EYE_Z),
                                 EYE_R + 0.0011, True, 0.0038, 0.0014))
    HEAD_PARTS.append(sphere_cap("LidLo_" + tag, H(ex, EYE_Y, EYE_Z),
                                 EYE_R + 0.0011, False, -0.0052, 0.0014))

# ---- brows: thin, angled, hugging the ridge
for sx in (-1, 1):
    HEAD_PARTS.append(ellipsoid("Brow_%s" % ("R" if sx < 0 else "L"),
                                H(sx * 0.0330, -0.0940, 0.0215),
                                (0.0205, 0.0045, 0.0026), 24, 12,
                                rot=(0.0, sx * 0.20, 0.0)))

# ---- lips: one mouth mass, seam in the middle
HEAD_PARTS.append(ellipsoid("LipUpper", H(0.0, -0.0868, -0.0500),
                            (0.0215, 0.0064, 0.0050), 28, 14))
HEAD_PARTS.append(ellipsoid("LipLower", H(0.0, -0.0864, -0.0578),
                            (0.0195, 0.0074, 0.0056), 28, 14))
HEAD_PARTS.append(ellipsoid("MouthLine", H(0.0, -0.0886, -0.0539),
                            (0.0186, 0.0030, 0.0009), 28, 10))

# ---- diagnostic: what is actually in front of the eye?
log("eye depth check")
bpy.context.view_layer.update()
for tag, ex in (("R", -0.0315), ("L", 0.0315)):
    origin = Vector((ex, -0.40, HEAD_C.z + EYE_Z))
    d = Vector((0.0, 1.0, 0.0))
    for nm in ("Head", "LidUp_" + tag, "LidLo_" + tag, "Eye_" + tag,
               "Iris_" + tag, "Pupil_" + tag):
        o = bpy.data.objects.get(nm)
        if o is None:
            continue
        inv = o.matrix_world.inverted()
        ol = inv @ origin
        dl = (inv.to_3x3() @ d).normalized()
        ok, loc, nor, idx = o.ray_cast(ol, dl)
        if ok:
            log("  %-9s first surface at y=%.4f" % (nm, (o.matrix_world @ loc).y))
        else:
            log("  %-9s no hit" % nm)

# ---- turn the head slightly: engagement, not a mugshot
log("posing head")
pivot = Vector((0.0, 0.014, 1.578))
M = (Matrix.Translation(pivot)
     @ Matrix.Rotation(math.radians(7.0), 4, "Z")
     @ Matrix.Rotation(math.radians(2.0), 4, "Y")
     @ Matrix.Translation(-pivot))
for o in HEAD_PARTS:
    o.matrix_world = M @ o.matrix_world

# ============================================================================
# 6. CLOTHING — fused solids so there are no seams or epaulettes
# ============================================================================
log("building garments")

SHIRT = [
    (0.928, 0.182, 0.128, 0.004),
    (0.975, 0.178, 0.126, 0.004),
    (1.020, 0.172, 0.122, 0.004),
    (1.080, 0.162, 0.117, 0.003),
    (1.140, 0.162, 0.117, 0.002),
    (1.200, 0.168, 0.121, 0.001),
    (1.260, 0.177, 0.125, 0.000),
    (1.320, 0.183, 0.127, 0.000),
    (1.364, 0.188, 0.126, 0.001),
    (1.400, 0.180, 0.120, 0.002),
    (1.432, 0.158, 0.110, 0.004),
    (1.456, 0.126, 0.098, 0.007),
    (1.472, 0.098, 0.088, 0.010),
    (1.484, 0.086, 0.080, 0.012),
]
shirt_parts = [loft("ShirtBody", SHIRT, segs=44)]

SLEEVE_R = [(0.068, 0.066), (0.062, 0.060), (0.056, 0.054),
            (0.050, 0.048), (0.045, 0.043), (0.041, 0.039), (0.037, 0.035)]


def sleeve_points(side):
    fwd = 0.0 if side < 0 else 0.020
    return [
        (side * 0.180, 0.002, 1.362),
        (side * 0.194, 0.004, 1.320),
        (side * 0.207, 0.008 + fwd * 0.25, 1.268),
        (side * 0.213, 0.012 + fwd * 0.55, 1.180),
        (side * 0.216, 0.014 + fwd * 0.85, 1.092),
        (side * 0.218, 0.010 + fwd, 1.000),
        (side * 0.220, 0.006 + fwd, 0.958),
    ]


for sx in (-1, 1):
    shirt_parts.append(tube("Sleeve_" + ("R" if sx < 0 else "L"),
                            sleeve_points(sx), SLEEVE_R, segs=28))

# collar
shirt_parts.append(tube("Collar", [(0.0, 0.012, 1.462), (0.0, 0.014, 1.494),
                                   (0.0, 0.014, 1.522)],
                        [(0.086, 0.078), (0.072, 0.068), (0.070, 0.066)], segs=32))

bpy.ops.object.select_all(action="DESELECT")
for o in shirt_parts:
    o.select_set(True)
bpy.context.view_layer.objects.active = shirt_parts[0]
bpy.ops.object.join()
shirt = bpy.context.object
shirt.name = "Shirt"
remesh(shirt, VOXEL_CLOTH, 2)
add_folds(shirt, 0.11, 0.0042)

TROUSER_HIP = [
    (0.775, 0.078, 0.086, 0.004),
    (0.806, 0.110, 0.098, 0.004),
    (0.846, 0.142, 0.110, 0.005),
    (0.896, 0.168, 0.120, 0.005),
    (0.950, 0.180, 0.124, 0.004),
    (1.005, 0.176, 0.122, 0.003),
    (1.045, 0.166, 0.118, 0.002),
]
trouser_parts = [loft("TrouserHip", TROUSER_HIP, segs=44)]

TLEG = [(0.082, 0.000, 0.940), (0.088, 0.004, 0.830), (0.094, 0.008, 0.690),
        (0.098, 0.012, 0.560), (0.098, 0.014, 0.495), (0.097, 0.018, 0.400),
        (0.095, 0.012, 0.290), (0.093, 0.008, 0.180), (0.092, 0.006, 0.098)]
TLEG_R = [(0.092, 0.090), (0.092, 0.088), (0.086, 0.082), (0.076, 0.074),
          (0.072, 0.070), (0.068, 0.066), (0.061, 0.059), (0.054, 0.052),
          (0.052, 0.050)]

for sx in (-1, 1):
    trouser_parts.append(tube("TrouserLeg_" + ("R" if sx < 0 else "L"),
                              [(sx * x, y, z) for (x, y, z) in TLEG],
                              TLEG_R, segs=28))

bpy.ops.object.select_all(action="DESELECT")
for o in trouser_parts:
    o.select_set(True)
bpy.context.view_layer.objects.active = trouser_parts[0]
bpy.ops.object.join()
trousers = bpy.context.object
trousers.name = "Trousers"
remesh(trousers, VOXEL_CLOTH, 2)
add_folds(trousers, 0.13, 0.0035)

# ---- shoes: sole slab, upper, heel counter, toe box
shoe_parts = []
for sx in (-1, 1):
    tag = "R" if sx < 0 else "L"
    shoe_parts.append(ellipsoid("Sole_" + tag, (sx * 0.092, -0.044, 0.015),
                                (0.047, 0.134, 0.015), 32, 18))
    shoe_parts.append(ellipsoid("Shoe_" + tag, (sx * 0.092, -0.042, 0.048),
                                (0.045, 0.126, 0.036), 32, 20))
    shoe_parts.append(ellipsoid("Heel_" + tag, (sx * 0.092, 0.028, 0.058),
                                (0.042, 0.050, 0.044), 28, 18))
    shoe_parts.append(ellipsoid("ToeBox_" + tag, (sx * 0.092, -0.140, 0.036),
                                (0.040, 0.044, 0.028), 28, 18))
bpy.ops.object.select_all(action="DESELECT")
for o in shoe_parts:
    o.select_set(True)
bpy.context.view_layer.objects.active = shoe_parts[0]
bpy.ops.object.join()
shoes = bpy.context.object
shoes.name = "Shoes"
remesh(shoes, 0.005, 2)

# ============================================================================
# 7. MATERIALS
# ============================================================================
log("materials")


def base_mat(name, color, rough, spec=0.5, metallic=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = (*color, 1.0)
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    if "Specular IOR Level" in b.inputs:
        b.inputs["Specular IOR Level"].default_value = spec
    return m


def skin_material(name, c0, c1, sss=0.16, rough=0.46):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    m.diffuse_color = ((c0[0] + c1[0]) * 0.5, (c0[1] + c1[1]) * 0.5,
                       (c0[2] + c1[2]) * 0.5, 1.0)
    nt = m.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Subsurface Weight"].default_value = sss
    bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.30, 0.16)
    bsdf.inputs["Subsurface Scale"].default_value = 0.020
    if "Specular IOR Level" in bsdf.inputs:
        bsdf.inputs["Specular IOR Level"].default_value = 0.35

    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 26.0
    noise.inputs["Detail"].default_value = 6.0
    noise.inputs["Roughness"].default_value = 0.62

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c0, 1.0)
    ramp.color_ramp.elements[1].color = (*c1, 1.0)
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])

    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.10
    bump.inputs["Distance"].default_value = 0.0016
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def cloth_mat(name, color, rough, weave=140.0, strength=0.22):
    m = base_mat(name, color, rough, 0.16)
    m.diffuse_color = (*color, 1.0)
    nt = m.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes.get("Principled BSDF")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = weave
    noise.inputs["Detail"].default_value = 3.0
    noise.inputs["Roughness"].default_value = 0.55
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = 0.0008
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return m


skin = skin_material("Skin", (0.430, 0.248, 0.180), (0.585, 0.362, 0.268))
lid_skin = skin_material("LidSkin", (0.410, 0.232, 0.168), (0.545, 0.330, 0.244),
                         0.20, 0.40)
eye_white = base_mat("EyeWhite", (0.82, 0.80, 0.78), 0.08, 0.9)
iris_mat = base_mat("Iris", (0.055, 0.032, 0.016), 0.16, 0.9)
pupil_mat = base_mat("Pupil", (0.006, 0.005, 0.005), 0.12, 0.9)
brow_mat = base_mat("Brow", (0.040, 0.026, 0.017), 0.62, 0.20)
lip_mat = base_mat("Lips", (0.300, 0.135, 0.125), 0.42, 0.35)
mouth_mat = base_mat("MouthLine", (0.055, 0.022, 0.020), 0.60, 0.20)
hair_mat = base_mat("Hair", (0.026, 0.018, 0.013), 0.55, 0.28)
shirt_mat = cloth_mat("ShirtCloth", (0.048, 0.066, 0.120), 0.84, 160.0, 0.20)
trouser_mat = cloth_mat("TrouserCloth", (0.062, 0.065, 0.076), 0.86, 130.0, 0.18)
leather_mat = base_mat("ShoeLeather", (0.030, 0.028, 0.027), 0.38, 0.45)
sole_mat = base_mat("ShoeSole", (0.022, 0.022, 0.023), 0.72, 0.25)
floor_mat = base_mat("FloorMat", (0.085, 0.085, 0.092), 0.60, 0.30)

# hair sheen
hb = hair_mat.node_tree.nodes.get("Principled BSDF")
hb.inputs["Anisotropic"].default_value = 0.55 if "Anisotropic" in hb.inputs else 0.0

RULES = [
    ("Shirt", shirt_mat),
    ("Sleeve", shirt_mat),
    ("Collar", shirt_mat),
    ("Trouser", trouser_mat),
    ("Sole", sole_mat),
    ("Shoe", leather_mat),
    ("Pupil", pupil_mat),
    ("Iris", iris_mat),
    ("Eye", eye_white),
    ("Lid", lid_skin),
    ("Brow", brow_mat),
    ("Mouth", mouth_mat),
    ("Lip", lip_mat),
    ("Hair", hair_mat),
]

for ob in bpy.data.objects:
    if ob.type != "MESH":
        continue
    mat = skin
    for prefix, m in RULES:
        if ob.name.startswith(prefix):
            mat = m
            break
    ob.data.materials.clear()
    ob.data.materials.append(mat)

# ============================================================================
# 7B. GAME ASSET EXPORT — preserve modular meshes before the still-render join
# ============================================================================
# v10 exports the current procedural sculpture as a static GLB for Three.js
# inspection. It is intentionally NOT presented as animation-ready: v9's
# voxel-remeshed body and garments still need a deformation/retopology pass.
GLB_OUT = os.environ.get(
    "HUM_GLB_OUT",
    os.path.join(_SCRIPT_DIR, "exports", "humanoid_v10.glb")
)
if os.environ.get("HUM_SKIP_GLB", "0") != "1":
    os.makedirs(os.path.dirname(os.path.abspath(GLB_OUT)), exist_ok=True)
    export_meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for ob in export_meshes:
        ob.select_set(True)
    if export_meshes:
        bpy.context.view_layer.objects.active = export_meshes[0]
        log("exporting %d separate mesh objects to %s" % (len(export_meshes), GLB_OUT))
        bpy.ops.export_scene.gltf(
            filepath=GLB_OUT,
            export_format="GLB",
            use_selection=True,
            export_apply=True
        )
        log("GLB export complete")
    else:
        log("WARNING: no mesh objects available for GLB export")

# ============================================================================
# 8. JOIN
# ============================================================================
log("joining final figure")
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
bpy.ops.object.select_all(action="DESELECT")
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = body
bpy.ops.object.join()
figure = bpy.context.object
figure.name = "Humanoid"
log("figure: %d verts / %d faces" % (len(figure.data.vertices), len(figure.data.polygons)))

# ============================================================================
# 9. LIGHTING
# ============================================================================
def add_area(name, loc, target, energy, size, color=(1, 1, 1)):
    d = bpy.data.lights.new(name, type="AREA")
    d.energy = energy
    d.size = size
    d.color = color
    o = bpy.data.objects.new(name, d)
    o.location = loc
    link(o)
    tgt = bpy.data.objects.new(name + "_T", None)
    tgt.location = target
    link(tgt)
    c = o.constraints.new("TRACK_TO")
    c.target = tgt
    c.track_axis = "TRACK_NEGATIVE_Z"
    c.up_axis = "UP_Y"
    return o


add_area("Key", (-2.20, -2.60, 2.60), (0, 0, 1.30), 430, 2.0, (1.0, 0.935, 0.86))
add_area("Fill", (2.60, -2.00, 1.45), (0, 0, 1.15), 110, 3.0, (0.82, 0.88, 1.0))
add_area("Rim", (1.20, 3.00, 2.60), (0, 0, 1.28), 380, 1.5, (0.86, 0.93, 1.0))

world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.030, 0.034, 0.044, 1.0)
bg.inputs["Strength"].default_value = 1.0

# ============================================================================
# 10. CAMERA
# ============================================================================
cam_data = bpy.data.cameras.new("Camera")
cam_data.lens = 85
cam_data.dof.use_dof = True
cam_data.dof.aperture_fstop = 4.0
cam = bpy.data.objects.new("Camera", cam_data)
cam.location = (1.55, -4.90, 1.02)
link(cam)
target = bpy.data.objects.new("CamTarget", None)
target.location = (0.0, 0.0, 0.94)
link(target)
c = cam.constraints.new("TRACK_TO")
c.target = target
c.track_axis = "TRACK_NEGATIVE_Z"
c.up_axis = "UP_Y"
scene.camera = cam

# ============================================================================
# 11. FLOOR + RENDER
# ============================================================================
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
floor = bpy.context.object
floor.name = "Floor"
floor.data.materials.append(floor_mat)

if PREVIEW == "form":
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "STUDIO"
    sh.color_type = "MATERIAL"
    sh.show_shadows = True
    sh.shadow_intensity = 0.30
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.curvature_ridge_factor = 1.2
    sh.curvature_valley_factor = 1.2
    scene.display.render_aa = "8"
elif PREVIEW == "light":
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.eevee.taa_render_samples = SAMPLES
    try:
        scene.eevee.use_raytracing = True
    except Exception:
        pass
else:
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    try:
        scene.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
scene.render.resolution_x = RES_X
scene.render.resolution_y = RES_Y
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.view_settings.view_transform = "AgX"
try:
    scene.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass

log("render 1: full body")
scene.render.filepath = OUT_BODY
cam_data.dof.focus_distance = 5.05
sys.stdout.flush()
bpy.ops.render.render(write_still=True)

log("render 2: head close-up")
cam.location = (0.13, -0.86, 1.700)
target.location = (0.0, 0.010, 1.662)
cam_data.dof.focus_distance = 0.88
cam_data.dof.aperture_fstop = 2.8
scene.render.resolution_x = 400 if PREVIEW else 480
scene.render.resolution_y = 400 if PREVIEW else 480
scene.render.filepath = OUT_HEAD
sys.stdout.flush()
bpy.ops.render.render(write_still=True)

log("render 3: eye close-up")
cam.location = (0.09, -0.40, 1.672)
target.location = (0.026, -0.08, 1.666)
cam_data.dof.focus_distance = 0.33
cam_data.dof.aperture_fstop = 2.0
scene.render.resolution_x = 360
scene.render.resolution_y = 360
scene.render.filepath = OUT_HEAD.replace(".png", "_eye.png")
sys.stdout.flush()
bpy.ops.render.render(write_still=True)

log("done in %.1fs" % (time.time() - t_start))