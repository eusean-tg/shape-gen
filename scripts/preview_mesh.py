"""Run with blender --background --factory-startup --python this.py -- mesh.glb."""

import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector


source = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
output = source.parent / "previews"
output.mkdir(exist_ok=True)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=str(source))
meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
points = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
center = (low + high) / 2
extent = max(high - low)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 24
scene.cycles.use_denoising = True
scene.render.resolution_x = 640
scene.render.resolution_y = 640
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.view_settings.view_transform = "Standard"
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.15, 0.15, 0.15, 1)
scene.world.node_tree.nodes["Background"].inputs[1].default_value = 0.6

for name, offset, energy, size in [
    ("Key", (2, -3, 3), 250, 2),
    ("Fill", (-2, -1, 1), 100, 2),
    ("Rim", (1, 3, 2), 180, 2),
]:
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy * extent**2
    data.shape = "DISK"
    data.size = size * extent
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = center + Vector(offset) * extent
    obj.rotation_euler = (center - obj.location).to_track_quat("-Z", "Y").to_euler()

camera = bpy.data.objects.new("Preview Camera", bpy.data.cameras.new("Preview Camera"))
scene.collection.objects.link(camera)
camera.data.type = "ORTHO"
camera.data.ortho_scale = extent * 1.2
scene.camera = camera
for name, angle in [("front", 0), ("three-quarter", 45), ("side", 90), ("back", 180)]:
    radians = math.radians(angle)
    camera.location = center + Vector((math.sin(radians), -math.cos(radians), 0.04)) * extent * 3
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = str(output / f"{name}.png")
    bpy.ops.render.render(write_still=True)

# Save a convenient review scene, with the original exported material intact.
camera.location = center + Vector((1, -2, 0.2)) * extent * 3
camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
bpy.ops.object.select_all(action="DESELECT")
for obj in meshes:
    obj.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == "VIEW_3D":
            area.spaces.active.shading.type = "MATERIAL"
            area.spaces.active.region_3d.view_location = center
            area.spaces.active.region_3d.view_distance = extent * 2
bpy.ops.wm.save_as_mainfile(filepath=str(source.parent / "preview.blend"))
print(f"Saved preview scene and four renders beside {source}")
