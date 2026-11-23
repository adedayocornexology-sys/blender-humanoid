"""Probe what this machine can actually do: CPU, RAM, GPU, EEVEE vs Cycles speed."""
import bpy
import os
import sys
import time
import platform

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
OUT_DIR = os.environ.get("HUM_OUT") or os.path.join(_SCRIPT_DIR, "renders")
os.makedirs(OUT_DIR, exist_ok=True)

def log(m):
    print("[probe] %s" % m)
    sys.stdout.flush()

log("blender %s" % bpy.app.version_string)
log("python %s" % platform.python_version())
log("cpu logical cores: %s" % os.cpu_count())
log("platform: %s" % platform.platform())

try:
    import gpu
    log("gpu vendor: %s" % gpu.platform.vendor_get())
    log("gpu renderer: %s" % gpu.platform.renderer_get())
    log("gpu version: %s" % gpu.platform.version_get())
    log("gpu backend: %s" % gpu.platform.backend_type_get())
except Exception as e:
    log("gpu module failed: %r" % (e,))

engines = [i.identifier for i in
           bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
log("engines: %s" % engines)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=48, radius=1.0,
                                     location=(0, 0, 1))
sp = bpy.context.object
m = bpy.data.materials.new("M")
m.use_nodes = True
m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.5, 0.3, 0.2, 1)
sp.data.materials.append(m)

ld = bpy.data.lights.new("L", "AREA")
ld.energy = 400
ld.size = 2.0
lo = bpy.data.objects.new("L", ld)
lo.location = (-2, -3, 3)
sc.collection.objects.link(lo)

cd = bpy.data.cameras.new("C")
cd.lens = 85
co = bpy.data.objects.new("C", cd)
co.location = (0, -5, 1.2)
co.rotation_euler = (1.55, 0, 0)
sc.collection.objects.link(co)
sc.camera = co

sc.render.resolution_x = 480
sc.render.resolution_y = 800
sc.render.image_settings.file_format = "PNG"

for eng, tag, samples in (("BLENDER_EEVEE_NEXT", "EEVEE", 32),
                          ("BLENDER_EEVEE_NEXT", "EEVEE", 8),
                          ("CYCLES", "CYCLES", 16)):
    try:
        sc.render.engine = eng
        if eng == "CYCLES":
            sc.cycles.device = "CPU"
            sc.cycles.samples = samples
            sc.cycles.use_denoising = True
        else:
            sc.eevee.taa_render_samples = samples
        sc.render.filepath = os.path.join(OUT_DIR, "probe_%s_%d.png" % (tag, samples))
        t = time.time()
        bpy.ops.render.render(write_still=True)
        log("%s @ %d samples: %.1fs" % (tag, samples, time.time() - t))
    except Exception as e:
        log("%s failed: %r" % (tag, e))

log("done")
