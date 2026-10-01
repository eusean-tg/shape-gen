"""Run in background Blender with --factory-startup; preserve the original scene."""

from pathlib import Path
import json

import bmesh
import bpy


root = Path(__file__).resolve().parent.parent
source = root / "final-v2/preview.blend"
target = root / "final-v2/peasant-editable.blend"
if target.exists():
    raise FileExistsError(target)
bpy.ops.wm.open_mainfile(filepath=str(source))
report = {}
for obj in [o for o in bpy.context.scene.objects if o.type == "MESH"]:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    tag = bm.faces.layers.int.new("audit_original_face")
    for i, face in enumerate(bm.faces):
        face[tag] = i
    uv_layers = list(bm.loops.layers.uv.values())

    def snapshot():
        # Preserve winding (allow a cyclic rotation), all corner UVs, and material.
        result = {}
        for face in bm.faces:
            corners = [
                (tuple(loop.vert.co), tuple(tuple(loop[layer].uv) for layer in uv_layers))
                for loop in face.loops
            ]
            canonical = min(tuple(corners[i:] + corners[:i]) for i in range(len(corners)))
            result[face[tag]] = (canonical, face.material_index, face.smooth)
        return result

    before = snapshot()
    normals = {f[tag]: f.normal.copy() for f in bm.faces}
    original_vertices = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-6)
    assert snapshot() == before, "Welding changed face coordinates, UVs, or materials"
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.normal_update()
    flipped = sum(f.normal.dot(normals[f[tag]]) < -0.99 for f in bm.faces)
    assert flipped == 0, "Recalculation changed face orientation"
    assert snapshot() == before, "Recalculation changed face corners"
    report[obj.name] = {
        "vertices_before": original_vertices,
        "vertices_after": len(bm.verts),
        "faces": len(bm.faces),
        "faces_flipped_by_recalculate": flipped,
        "boundary_edges": sum(e.is_boundary for e in bm.edges),
        "overconnected_edges": sum(len(e.link_faces) > 2 for e in bm.edges),
        "face_coordinates_winding_uvs_materials_unchanged": True,
    }
    bm.faces.layers.int.remove(tag)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()

bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(target))
# Reopen the saved artifact and check geometry and packed texture survive.
bpy.ops.wm.open_mainfile(filepath=str(target))
for name, entry in report.items():
    mesh = bpy.data.objects[name].data
    assert len(mesh.vertices) == entry["vertices_after"]
    assert len(mesh.polygons) == entry["faces"]
    assert len(mesh.uv_layers) > 0
textures = [i for i in bpy.data.images if i.type == "IMAGE" and i.size[0] >= 2048]
assert textures and all(i.packed_file for i in textures), "Missing packed texture"
(root / "diagnostics/editable-validation.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
print(f"Saved and reopened {target}")
