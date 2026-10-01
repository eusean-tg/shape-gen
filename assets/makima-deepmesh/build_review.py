"""Build the two-character DeepMesh/BPT comparison once inference is complete."""
from pathlib import Path
import json,html
r=Path(__file__).resolve().parent
examples=[];sections=[]
angles=[('renders','full','Full body'),('renders','front','Head and torso'),('renders','side','Side'),('renders','back-quarter','Back quarter'),('detail-renders','face','Face'),('detail-renders','knees-back','Rear knees')]
for subject,title in [('teal','Teal peasant'),('makima','Makima')]:
 data=json.loads((r/subject/'trial.json').read_text())
 variants=[('dense',f'{subject}-dense.glb','Hunyuan dense source','Identical source supplied to both reconstruction models.'),
           ('bpt',f'{subject}-bpt.glb','Existing BPT','Existing baseline; triangle count is not forced to match DeepMesh.')]
 if data['status']=='complete':
  note=f"{data['output_triangles']:,} triangles · {data['boundary_edges']} boundary edges · {data['nonmanifold_edges']} non-manifold edges · {data['elapsed_seconds']:.0f}s. One seed, temperature 0.5; no manual geometry repair."
  variants.insert(0,('deepmesh',f'{subject}/02-deepmesh.glb','DeepMesh',note))
 else:
  assert data['status']=='failed'
  sections.append(f'<p><strong>{title} DeepMesh failed:</strong> {html.escape(data["error"])}</p>')
 for key,path,label,note in variants:
  assert (r/path).exists()
  examples.append(dict(id=f'{subject}-{key}',label=f'{title} · {label}',src='./'+path,note=note))
 sections.append(f'<h2>{title}</h2>')
 for folder,angle,angle_label in angles:
  cards=[]
  for key,path,label,note in variants:
   image=f'{folder}/{subject}-{key}-{angle}.png';assert (r/image).exists(),image
   cards.append(f'<article><h4>{label}</h4><a href="{image}"><img loading="lazy" src="{image}" alt="{title}, {label}, {angle_label}"></a><p>{html.escape(note)}</p><a href="{path}">Download GLB</a></article>')
  sections.append(f'<h3>{angle_label}</h3><div class="row">'+''.join(cards)+'</div>')
(r/'examples.json').write_text(json.dumps(examples,indent=2)+'\n')
(r/'gallery.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DeepMesh · low-poly comparison</title><style>body{font:16px/1.5 system-ui;background:#111821;color:#e1e8ef;margin:24px}a{color:#89cbff}.row{display:flex;gap:16px;overflow-x:auto}article{flex:0 0 300px;background:#202b38;border-radius:8px;padding:12px}img{width:100%;height:auto}h4{margin:0 0 8px}article p{font-size:14px;color:#bcc9d7}body>p{max-width:1000px}</style>
<h1>DeepMesh · low-poly comparison</h1><p><a href="./">Interactive viewer</a> · <a href="./report.md">Experiment report</a></p>
<p>Same dense input per character. Neutral clay, matching cameras and lighting; click images to enlarge. One DeepMesh candidate per character. Judge the teal peasant for the intended low-poly style; Makima is the harder secondary example. Output triangle counts differ. These static meshes have not been rigged or textured.</p>
'''+''.join(sections)+'</html>')
print(f'Built {len(examples)} model entries.')
