"""Render and measure the unchanged peasant's joint topology in background Blender."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import argparse
import sys

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=ROOT/'assets/peasant-deformation-check')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
OUT=args.output.resolve()
SOURCE = ROOT/'assets/peasant-hypaint-experiment/hypaint-imagegen/peasant-hypaint-imagegen.blend'
OUT.mkdir(parents=True,exist_ok=True)
if (OUT/'topology-review.blend').exists(): raise FileExistsError(OUT/'topology-review.blend')
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
scene = bpy.context.scene
objects = [o for o in scene.objects if o.type == 'MESH']
body = next(o for o in objects if o.name == 'Peasant body')
v = np.array([body.matrix_world @ x.co for x in body.data.vertices])
f = np.array([list(p.vertices) for p in body.data.polygons])
centers = v[f].mean(1)
edge_faces = defaultdict(list)
for i, face in enumerate(f):
    for a, b in zip(face, np.roll(face, -1)):
        edge_faces[tuple(sorted((int(a), int(b))))].append(i)

REGIONS = {
    'shoulders': ((-.025, .09, .46), (.40, .22, .17)),
    'elbow-screen-left': ((-.37, .07, .245), (.10, .19, .12)),
    'elbow-screen-right': ((.325, .07, .245), (.10, .19, .12)),
    'hips-tunic': ((-.025, .07, -.085), (.25, .23, .20)),
    'knees': ((-.025, .10, -.51), (.25, .18, .115)),
}
regions = {}
for name, (center, extent) in REGIONS.items():
    mask = (np.abs(centers-np.array(center)) <= np.array(extent)).all(1)
    ids = np.flatnonzero(mask)
    vids = np.unique(f[mask])
    es = [e for e, fs in edge_faces.items() if any(i in ids for i in fs)]
    regions[name] = {'bounds_center': center, 'bounds_half_extents': extent,
                     'face_indices': ids.tolist(), 'vertices': len(vids), 'triangles': len(ids),
                     'boundary_edges_touching_region': sum(len(edge_faces[e]) == 1 for e in es),
                     'overconnected_edges_touching_region': sum(len(edge_faces[e]) > 2 for e in es),
                     'max_edge_length': max(float(np.linalg.norm(v[a]-v[b])) for a,b in es)}
neighbors = defaultdict(set)
for a,b in edge_faces:
    neighbors[a].add(b); neighbors[b].add(a)
unseen = set(range(len(v))); components = []
while unseen:
    stack=[unseen.pop()]; group=set(stack)
    while stack:
        for n in neighbors[stack.pop()]:
            if n in unseen:
                unseen.remove(n);group.add(n);stack.append(n)
    ids=sorted(group)
    components.append({'vertices': len(ids), 'triangles': sum(set(face).issubset(group) for face in f),
                       'boundary_edges': sum(len(fs)==1 for e,fs in edge_faces.items() if e[0] in group),
                       'overconnected_edges': sum(len(fs)>2 for e,fs in edge_faces.items() if e[0] in group),
                       'bounds_min': v[ids].min(0).tolist(), 'bounds_max': v[ids].max(0).tolist()})
defects = [{'vertices': list(e), 'face_count': len(fs), 'face_indices': fs,
            'midpoint': v[list(e)].mean(0).tolist()} for e,fs in edge_faces.items() if len(fs)!=2]
report = {'source': str(SOURCE.relative_to(ROOT)),
          'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
          'mesh_unchanged': True, 'body_vertices': len(v), 'body_triangles': len(f),
          'components': components, 'regions': regions, 'defects': defects,
          'note': 'Region counts use face-centroid boxes; static topology audit, not proof of deformation quality.'}
(OUT/'topology.json').write_text(json.dumps(report, indent=2)+'\n')

overlays = bpy.data.collections.new('Inspection overlays — hide for original texture')
scene.collection.children.link(overlays)
def lines(name, vertices, edges, radius, color):
    if not edges: return
    curve=bpy.data.curves.new(name, 'CURVE');curve.dimensions='3D';curve.resolution_u=1
    curve.bevel_depth=radius;curve.bevel_resolution=0
    for a,b in edges:
        sp=curve.splines.new('POLY');sp.points.add(1)
        sp.points[0].co=(*vertices[a],1);sp.points[1].co=(*vertices[b],1)
    obj=bpy.data.objects.new(name,curve);overlays.objects.link(obj);obj.color=(*color,1)
    return obj
for obj in objects:
    obj.color=(.63,.68,.73,1)
    vertices=[obj.matrix_world@x.co for x in obj.data.vertices]
    lines(obj.name+' edges',vertices,[list(e.vertices) for e in obj.data.edges],.0008,(.015,.023,.035))
lines('Open boundary edges',v,[e for e,fs in edge_faces.items() if len(fs)==1],.0035,(.95,.025,.02))
lines('Edges shared by more than two faces',v,[e for e,fs in edge_faces.items() if len(fs)>2],.005,(1,.45,.015))
scene.render.engine='BLENDER_WORKBENCH'
scene.render.resolution_x=scene.render.resolution_y=960
scene.render.resolution_percentage=100
scene.render.threads_mode='FIXED';scene.render.threads=4
sh=scene.display.shading
sh.light='STUDIO';sh.color_type='OBJECT';sh.show_cavity=True;sh.cavity_type='BOTH'
sh.show_shadows=True;sh.background_type='WORLD'
scene.world.color=(.08,.08,.08)
camera=scene.camera
def render(name,center,direction,scale):
    camera.data.type='ORTHO';camera.data.ortho_scale=scale
    camera.location=Vector(center)+Vector(direction).normalized()*4
    camera.rotation_euler=(Vector(center)-camera.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
render('topology-front',(-.022,.06,-.008),(0,-1,0),2.2)
render('topology-side',(-.022,.06,-.008),(-1,0,0),2.2)
render('topology-back',(-.022,.06,-.008),(0,1,0),2.2)
render('shoulders-front',(-.022,.07,.45),(0,-1,.1),.95)
render('shoulder-underarm',(-.27,.10,.37),(-1,-1,-.25),.55)
render('elbow-front',(-.365,.07,.25),(0,-1,0),.43)
render('elbow-side',(-.365,.07,.25),(-1,0,0),.43)
render('hips-front',(-.022,.07,-.07),(0,-1,0),.68)
render('hips-under',(-.022,.06,-.13),(0,-1,-1),.56)
render('hips-back',(-.022,.07,-.07),(0,1,0),.68)
render('knees-front',(-.022,.10,-.51),(0,-1,0),.59)
render('knee-side',(-.15,.10,-.51),(-1,0,0),.42)
render('overview',(-.022,.06,-.008),(-.5,-1,.02),2.2)
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.shading.type='SOLID';area.spaces.active.shading.color_type='OBJECT'
            area.spaces.active.region_3d.view_location=(-.022,.06,-.008)
            area.spaces.active.region_3d.view_distance=3.2
            area.spaces.active.overlay.show_extras=False
target=OUT/'topology-review.blend'
if target.exists(): raise FileExistsError(target)
bpy.ops.wm.save_as_mainfile(filepath=str(target))
print(json.dumps({'components':components,'regions':{k:{a:b for a,b in val.items() if a!='face_indices'} for k,val in regions.items()}},indent=2))
