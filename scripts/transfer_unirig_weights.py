"""Resample UniRig weights onto the exact original vertices, retaining four influences."""
import json
import argparse
from pathlib import Path
import os
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--asset-dir',type=Path,default=ROOT/'assets/peasant-unirig')
parser.add_argument('--bone-names',type=Path,help='Reviewed JSON list matching the predicted skeleton order')
parser.add_argument('--generic-names',action='store_true',help='Retain predicted bone_N names for a new character')
args=parser.parse_args()
OUT=args.asset_dir.resolve()
sys.path.insert(0,str(ROOT/'third_party/UniRig'))
from src.system.skin import reskin

skeleton=np.load(OUT/'data/peasant/predict_skeleton.npz',allow_pickle=True)
skin=np.load(OUT/'data/peasant/predict_skin.npz',allow_pickle=True)
meta=json.loads((OUT/'input.json').read_text())
original=np.load(OUT/'data/peasant/raw_data.npz',allow_pickle=True)
names=['pelvis','spine','chest','upper_chest','neck','head',
       'clavicle.L','upper_arm.L','forearm.L','hand.L','fingers_1.L','fingers_2.L','fingers_tip.L',
       'clavicle.R','upper_arm.R','forearm.R','hand.R','fingers_1.R','fingers_2.R','fingers_tip.R',
       'thigh.L','shin.L','foot.L','toe.L','thigh.R','shin.R','foot.R','toe.R']
if args.bone_names:names=json.loads(args.bone_names.read_text())
if args.generic_names:
    assert not args.bone_names, 'Choose reviewed or generic names, not both'
    names=[f'bone_{i}' for i in range(len(skeleton['joints']))]
assert len(names)==len(skeleton['joints'])==skin['skin'].shape[1]
assert all(str(n)==f'bone_{i}' for i,n in enumerate(skeleton['names']))
parents=skeleton['parents'].tolist()
# The skin stage may normalize the skeleton/mesh again. Fit and verify the
# shared uniform affine transform before querying weights in its coordinate frame.
src=skeleton['joints'].astype(np.float64);dst=skin['joints'].astype(np.float64)
src_center=src.mean(0);dst_center=dst.mean(0)
scale=float(((src-src_center)*(dst-dst_center)).sum()/((src-src_center)**2).sum())
bias=dst_center-scale*src_center
residual=float(np.max(np.abs(src*scale+bias-dst)))
assert residual<2e-6 and scale>0
query=skeleton['vertices']*scale+bias
weights=reskin(sampled_vertices=skin['vertices'],vertices=query,parents=parents,
    faces=skeleton['faces'],sampled_skin=skin['skin'],sample_method='median',alpha=2.0,threshold=.03)
assert np.isfinite(weights).all() and weights.min()>-1e-5
weights=np.maximum(weights,0)
order=np.argsort(-weights,axis=1)[:,:4]
limited=np.zeros_like(weights)
limited[np.arange(len(weights))[:,None],order]=weights[np.arange(len(weights))[:,None],order]
kept=limited.sum(1)
assert (kept>0).all()
limited/=kept[:,None]
world_scale=meta['normalization_half_extent'];world_bias=np.array(meta['normalization_center'])
assert np.max(abs(skeleton['vertices']*world_scale+world_bias-original['vertices']))<2e-6
np.savez(OUT/'rig-data.npz',vertices=original['vertices'],faces=original['faces'],
    joints=skeleton['joints']*world_scale+world_bias,tails=skeleton['tails']*world_scale+world_bias,
    parents=np.array([-1 if p is None else p for p in parents]),names=np.array(names),
    weights=limited,unlimited_weights=weights)
report={'bones':len(names),'weighted_body_vertices':len(weights),'max_influences':4,
    'min_weight':float(limited.min()),'max_weight_sum_error':float(abs(limited.sum(1)-1).max()),
    'mean_discarded_mass':float((1-kept).mean()),'max_discarded_mass':float((1-kept).max()),
    'skin_frame_scale':scale,'skin_frame_bias':bias.tolist(),'skin_frame_fit_max_error':residual,
    'method':'Upstream reskin: median of seven nearest samples, one topology-aware diffusion pass, threshold .03; retain largest four weights and renormalize.',
    'joint_names':{str(i):name for i,name in enumerate(names)}}
(OUT/'weight-transfer.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
