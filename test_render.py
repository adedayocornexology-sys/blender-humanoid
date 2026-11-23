import bpy, time, sys, os

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
OUT_DIR = os.environ.get("HUM_OUT") or os.path.join(_SCRIPT_DIR, "renders")
os.makedirs(OUT_DIR, exist_ok=True)

# Start from a completely empty scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# --- geometry: a subdivided sphere to stress the pipeline ---
bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=1.0)
obj = bpy.context.object
sub = obj.modifiers.new("Subdivision", "SUBSURF")
sub.levels = 2
sub.render_levels = 2
bpy.ops.object.shade_smooth()

# --- material ---
mat = bpy.data.materials.new("Skin")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
if bsdf:
    bsdf.inputs["Base Color"].default_value = (0.8, 0.6, 0.5, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.5
obj.data.materials.append(mat)

# --- camera ---
bpy.ops.object.camera_add(location=(0.0, -6.0, 1.0), rotation=(1.42, 0.0, 0.0))
bpy.context.scene.camera = bpy.context.object

# --- light ---
bpy.ops.object.light_add(type="AREA", location=(3.0, -3.0, 4.0))
bpy.context.object.data.energy = 1200

# --- render settings: Cycles on CPU (no GPU needed) ---
sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = 16
sc.cycles.use_denoising = False
sc.render.resolution_x = 400
sc.render.resolution_y = 400
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = os.path.join(OUT_DIR, "test_render.png")

print("=== starting render ===")
sys.stdout.flush()
t0 = time.time()
bpy.ops.render.render(write_still=True)
elapsed = time.time() - t0
print("=== RENDER_SECONDS: %.1f ===" % elapsed)
sys.stdout.flush()
