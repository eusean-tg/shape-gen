"""Replace only the atlas and semantic face materials in an existing scene."""
import argparse,sys,json
from pathlib import Path
import bpy
import numpy as np
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--textures',type=Path,required=True)
a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
bpy.ops.wm.open_mainfile(filepath=str(a.source.resolve()))
body=bpy.data.objects['Peasant body'];arm=bpy.data.objects['Peasant rig']
image=bpy.data.images.load(str((a.textures/'basecolor.png').resolve()),check_existing=False)
image.name='Teal peasant corrected garment regions';image.pack()
for m in body.data.materials:
 for n in m.node_tree.nodes:
  if n.type=='TEX_IMAGE':n.image=image
labels=np.load(a.textures/'face-regions.npy')
for poly,rid in zip(body.data.polygons,labels):
 poly.material_index=int(rid);body.data.attributes['material_region'].data[poly.index].value=int(rid)
bpy.ops.object.select_all(action='DESELECT');body.select_set(True);arm.select_set(True)
bpy.context.view_layer.objects.active=arm;bpy.context.scene.frame_set(1)
a.output.parent.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(a.output.resolve()))
bpy.ops.export_scene.gltf(filepath=str(a.output.with_suffix('.glb').resolve()),export_format='GLB',use_selection=True,
 export_yup=True,export_skins=True,export_animations=bool(arm.animation_data and arm.animation_data.action),
 export_frame_range=True,export_force_sampling=True,export_def_bones=True,export_materials='EXPORT',
 export_animation_mode='ACTIVE_ACTIONS',export_anim_slide_to_zero=True,export_extras=True)
