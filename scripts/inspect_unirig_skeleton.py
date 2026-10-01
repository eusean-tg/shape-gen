"""Measure and plot predicted joints against the unchanged peasant geometry."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/peasant-unirig'
data=np.load(OUT/'data/peasant/predict_skeleton.npz',allow_pickle=True)
meta=json.loads((OUT/'input.json').read_text())
original=np.load(OUT/'data/peasant/raw_data.npz',allow_pickle=True)
center=np.array(meta['normalization_center']);scale=meta['normalization_half_extent']
vertices=data['vertices']*scale+center
assert np.max(abs(vertices-original['vertices']))<2e-6
assert np.array_equal(data['faces'],original['faces'])
joints=data['joints']*scale+center;tails=data['tails']*scale+center
parents=data['parents'].tolist();names=data['names'].tolist()
assert np.isfinite(joints).all() and np.isfinite(tails).all()
assert parents[0] is None or parents[0]==-1
for i,p in enumerate(parents[1:],1):assert 0<=p<i
report={'bone_count':len(joints),'max_mesh_mapping_error':float(np.max(abs(vertices-original['vertices']))),
        'coordinates':'Blender world coordinates; original normalization inverted.',
        'bones':[{'index':i,'name':str(names[i]),'parent':p,'head':joints[i].tolist(),
            'tail':tails[i].tolist(),'length':float(np.linalg.norm(tails[i]-joints[i]))}
            for i,p in enumerate(parents)]}
(OUT/'skeleton-review.json').write_text(json.dumps(report,indent=2)+'\n')
faces=data['faces'];edges=np.unique(np.sort(np.concatenate([faces[:,[0,1]],faces[:,[1,2]],faces[:,[2,0]]]),axis=1),axis=0)
fig,axes=plt.subplots(1,2,figsize=(12,11),layout='constrained')
for ax,indices,title in zip(axes,[[0,2],[1,2]],['Front: X / Z','Side: Y / Z']):
    ax.add_collection(LineCollection(vertices[edges][:,:,indices],colors='#b2bdc9',linewidths=.35,alpha=.55))
    ax.add_collection(LineCollection(np.stack([joints[:,indices],tails[:,indices]],axis=1),colors='#008b79',linewidths=2))
    ax.scatter(joints[:,indices[0]],joints[:,indices[1]],s=15,c='#cd4c20',zorder=4)
    for i,p in enumerate(joints):
        ax.annotate(str(i),p[indices],xytext=(4,2),textcoords='offset points',fontsize=7,color='#572b10')
    ax.autoscale();ax.set_aspect('equal');ax.set_title(title);ax.grid(alpha=.15)
fig.suptitle('UniRig predicted skeleton — numbered joints on the original mesh',fontsize=15)
fig.savefig(OUT/'skeleton-review.png',dpi=150)
print(json.dumps(report,indent=2))
