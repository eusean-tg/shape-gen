"""Export the welded authoring body to UniRig arrays without changing topology."""
from pathlib import Path
import hashlib
import json
import bpy
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/peasant-unirig'
SOURCE=ROOT/'assets/peasant-hypaint-experiment/hypaint-imagegen/peasant-hypaint-imagegen.blend'
(OUT/'data/peasant').mkdir(parents=True,exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
obj=bpy.data.objects['Peasant body']
vertices=np.array([obj.matrix_world@v.co for v in obj.data.vertices],dtype=np.float32)
faces=np.array([list(f.vertices) for f in obj.data.polygons],dtype=np.int64)
normals=np.array([obj.matrix_world.to_3x3()@v.normal for v in obj.data.vertices],dtype=np.float32)
face_normals=np.array([obj.matrix_world.to_3x3()@f.normal for f in obj.data.polygons],dtype=np.float32)
np.savez(OUT/'data/peasant/raw_data.npz',vertices=vertices,faces=faces,
    vertex_normals=normals,face_normals=face_normals,joints=None,skin=None,parents=None,
    names=None,matrix_local=None,tails=None,no_skin=None,path=None,cls=None)
(OUT/'data/inference.txt').write_text('peasant\n')
lo,hi=vertices.min(0),vertices.max(0)
report={'source':str(SOURCE),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'object':obj.name,'vertices':len(vertices),'triangles':len(faces),
        'coordinates':'Blender world coordinates, Z up, character faces -Y; same as upstream extractor.',
        'normalization_center':((lo+hi)/2).tolist(),'normalization_half_extent':float(max(hi-lo)/2),
        'pouch':'Separate rigid accessory; excluded from skeleton/skin prediction and attached to pelvis later.',
        'source_topology_and_uvs_unchanged':True}
(OUT/'input.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
