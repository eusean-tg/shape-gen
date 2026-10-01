"""Split a generated 2x2 restyle sheet and check silhouette correspondence."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--guides',type=Path,required=True)
parser.add_argument('--sheet',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
args.output.mkdir(parents=True,exist_ok=True)
sheet=Image.open(args.sheet).convert('RGBA');w,h=sheet.size
assert w==h
views=json.loads((args.guides/'views.json').read_text())
metrics=[]
for i,spec in enumerate(views):
    tile=sheet.crop(((i%2)*w//2,(i//2)*h//2,(i%2+1)*w//2,(i//2+1)*h//2))
    tile.save(args.output/f'{i}.png');spec['image']=f'{i}.png'
    original=np.array(Image.open(args.guides/f'{i}-mask.png'))>127
    rgba=np.array(tile.resize((original.shape[1],original.shape[0]),Image.Resampling.NEAREST))
    if rgba[...,3].min()<128:
        generated=rgba[...,3]>127
    else:generated=rgba[...,:3].min(axis=-1)<240
    intersection=(original&generated).sum();union=(original|generated).sum()
    metrics.append({'view':i,'silhouette_iou':float(intersection/union),
        'source_coverage':float(intersection/original.sum()),
        'generated_pixels_outside_source':int((generated&~original).sum())})
(args.output/'views.json').write_text(json.dumps(views,indent=2)+'\n')
report={'sheet':str(args.sheet.resolve()),'sheet_sha256':hashlib.sha256(args.sheet.read_bytes()).hexdigest(),
        'sheet_size':[w,h],'views':metrics,
        'limitation':'Silhouette correspondence does not verify internal facial feature placement.'}
(args.output/'alignment.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
