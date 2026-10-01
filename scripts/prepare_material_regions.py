"""Export the original per-corner UV mesh and hand-authored material regions."""
from pathlib import Path
import json
import bpy
import numpy as np

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'assets/peasant-material-masks';OUT.mkdir(exist_ok=True)
SOURCE=ROOT/'assets/peasant-hymotion/walk/final/peasant-walk.blend'
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
vertices=[];faces=[];uvs=[];labels=[];objects=[]
for name in ['Peasant body','Original BPT pouch']:
    ob=bpy.data.objects[name];v=np.array([tuple(x.co) for x in ob.data.vertices]);f=np.array([list(p.vertices) for p in ob.data.polygons]);uv=np.array([[tuple(ob.data.uv_layers.active.data[i].uv) for i in p.loop_indices] for p in ob.data.polygons]);c=v[f].mean(1)
    lab=np.full(len(f),1,dtype=np.int32) # tunic
    if name=='Original BPT pouch':lab[:]=5
    else:
        # Reviewed in Blender coordinates: Z up; character faces -Y.
        # Shirt hem follows the flared mesh ring, not its previous painted edge.
        lab[c[:,2]<-.067]=2 # trousers
        lab[c[:,2]<-.84]=4 # boots
        # Bare forearms and hands lie outside the torso below the rolled cuff.
        lab[(abs(c[:,0]+.02224)>.28)&(c[:,2]<.31)&(c[:,2]>-.3)]=0
        lab[(c[:,2]>.655)|((c[:,2]>.615)&(abs(c[:,0]+.02224)<.07))]=0
        # Central neck opening below the head; limited to the forward surface.
        lab[(abs(c[:,0]+.02224)<.045)&(c[:,2]>.505)&(c[:,1]<.01)]=0
        # Two detached front tunic flaps belong to the tunic, not the trousers.
        edges={i:set() for i in range(len(v))}
        for tri in f:
            for a in tri:
                edges[int(a)].update(map(int,tri))
        unseen=set(edges);small=set()
        while unseen:
            stack=[unseen.pop()];component=set(stack)
            while stack:
                for j in edges[stack.pop()]&unseen:unseen.remove(j);component.add(j);stack.append(j)
            if len(component)<30:small.update(component)
        lab[np.array([all(int(i) in small for i in t) for t in f])]=1
        # Reviewed projecting tabs under the front/back hem. These are garment
        # geometry; the broader thigh surfaces behind them remain trousers.
        tabs=(c[:,2]<-.067)&(c[:,2]>-.205)&(abs(c[:,0]+.02224)<.083)&((c[:,1]<-.055)|(c[:,1]>.205))
        lab[tabs]=1
    offset=len(vertices);objects.append({'name':name,'vertex_start':offset,'vertex_count':len(v),'face_start':len(faces),'face_count':len(f)})
    vertices.extend(v);faces.extend(f+offset);uvs.extend(uv);labels.extend(lab)
np.savez_compressed(OUT/'regions.npz',vertices=np.array(vertices),faces=np.array(faces),uv=np.array(uvs),labels=np.array(labels,dtype=np.int32))
(OUT/'regions.json').write_text(json.dumps({'source':str(SOURCE),'coordinate_system':'Blender Z-up, forward -Y','objects':objects,'regions':{'0':'skin and preserved head','1':'tunic','2':'trousers','3':'belt (sub-face surface mask)','4':'boots','5':'pouch'},'method':'Hand-authored spatial thresholds and topology components, visually reviewed; not model segmentation.'},indent=2)+'\n')
print(OUT)
