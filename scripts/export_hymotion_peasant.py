"""Export only the active generated motion, beginning at time zero."""
from pathlib import Path
import bpy
BASE=Path(__file__).resolve().parents[1]/'assets/peasant-hymotion/walk'
for version in ['retarget','final']:
    path=BASE/version
    bpy.ops.wm.open_mainfile(filepath=str(path/'peasant-walk.blend'))
    bpy.ops.object.select_all(action='DESELECT')
    for name in ['Peasant rig','Peasant body','Original BPT pouch']:bpy.data.objects[name].select_set(True)
    bpy.context.view_layer.objects.active=bpy.data.objects['Peasant rig']
    bpy.ops.export_scene.gltf(filepath=str(path/'peasant-walk.glb'),export_format='GLB',use_selection=True,
        export_yup=True,export_skins=True,export_animations=True,export_frame_range=True,
        export_force_sampling=True,export_def_bones=True,export_materials='EXPORT',
        export_animation_mode='ACTIVE_ACTIONS',export_anim_slide_to_zero=True)
