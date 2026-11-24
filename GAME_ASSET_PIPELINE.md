# Game Asset Pipeline: Humanoid v10

## Goal

Turn the existing procedural v9 humanoid into a reusable asset that can be inspected in the same Three.js runtime used by Market Rush.

## What v10 changes

- Keeps `humanoid.py` as the original procedural source of truth.
- Exports the generated character meshes to `exports/humanoid_v10.glb` **before** the original script joins meshes for its studio renders.
- Preserves separate mesh objects and their assigned materials in the GLB.
- Adds a small Three.js viewer at `threejs-test/` with orbit, zoom, pan, wireframe inspection and model-size reporting.
- Leaves the original still-render workflow intact.

## Build

Requires Blender 4.2.1 LTS with the glTF 2.0 exporter enabled.

From the repository root:

```bash
blender --background --factory-startup --python humanoid.py
```

The script writes the existing PNG renders under `renders/` and the game preview asset to `exports/humanoid_v10.glb`.

Override the GLB destination:

```bash
HUM_GLB_OUT=/absolute/path/to/humanoid.glb blender --background --factory-startup --python humanoid.py
```

Skip GLB export while only rendering the original plates:

```bash
HUM_SKIP_GLB=1 blender --background --factory-startup --python humanoid.py
```

## View in Three.js

Start a static server from the repository root (do not open the HTML file directly):

```bash
python -m http.server 8000
```

Open:

```
http://localhost:8000/threejs-test/
```

The viewer expects `exports/humanoid_v10.glb` to exist.

## Current limitations

This is a **static GLB inspection milestone**, not an animation-ready game character.

The existing v9 body and clothing are voxel-remeshed sculptures. Exporting them as separate objects preserves material/object boundaries, but does not create animation-friendly edge flow, UVs, an armature or skin weights. The current face/hair details are also deliberately carried forward as a visual baseline rather than claimed as final game topology.

## Next acceptance gates

1. Run Blender and confirm the GLB exporter completes without errors.
2. Load the GLB in the viewer and verify the full character, materials, scale and orientation.
3. Inspect the head, hands, feet and garment intersections at close range.
4. Profile GLB file size and mesh/triangle counts.
5. Decide whether to retopologise the body or use a deformation-friendly procedural mesh before adding the armature.
6. Add idle/walk/run only after deformation tests pass.


## Automated build check

The GitHub Actions workflow `.github/workflows/humanoid-preview.yml` builds a fast Blender preview, validates the GLB v2 container and scene geometry, checks the viewer JavaScript syntax, and uploads the GLB/render outputs as a short-lived workflow artifact. This is a structural smoke test; it does not replace visual browser inspection or verify animation.
