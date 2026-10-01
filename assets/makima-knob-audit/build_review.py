"""Build a static gallery and a saved-model list from completed experiments."""
from pathlib import Path
import html,json

p=Path(__file__).resolve().parent
cases=[
 ('recommended','Gap experiment · poorer face and knee fidelity','bpt-mv-original/02-bpt-closed.glb','Original white-background views → MV at 384 → standard BPT. Larger braid gap, but worse face and knee shapes in visual review; not an accepted replacement. Two tiny holes filled; 2,178 triangles, watertight.'),
 ('original-dense','Original dense · mv / 192','original-dense.glb','Original API run; background removal enabled.'),
 ('original-bpt','Original BPT · 2,409 triangles','original-bpt.glb','Original 4,096-point conditioning, temperature 0.5.'),
 ('mv384','MV · resolution 384','mv-resolutions/r384-iso0.glb','Same latent shape as baseline; finer extraction.'),
 ('mv512','MV · resolution 512','mv-resolutions/r512-iso0.glb','Same latent shape; finer extraction preserves the existing joins.'),
 ('mv-original','MV · original backgrounds','mv-original-fixed/r384-iso0.glb','Original white backgrounds, resolution 384. Changes both masking and framing.'),
 ('mini','Mini · front view','mini/r384-iso0.glb','Front image only. Hidden braid is not reconstructed.'),
 ('full','Full · front view','full/r384-iso0.glb','Front image only. Hidden braid is not reconstructed.'),
 ('mv-guidance3','MV · guidance 3','mv-guidance3/r384-iso0.glb','Processed views, 50 steps, guidance 3.'),
 ('mv-steps75','MV · 75 steps','mv-steps75/r384-iso0.glb','Processed views, guidance 5, 75 steps.'),
 ('mv512-minus','MV · isosurface −0.02','mv-resolutions/r512-iso-0.02.glb','Global field threshold adjustment; not a semantic separation control.'),
 ('mv512-plus','MV · isosurface +0.02','mv-resolutions/r512-iso0.02.glb','Global field threshold adjustment; not a semantic separation control.'),
 ('bpt-temp03','BPT · temperature 0.3','bpt-temp03/02-bpt.glb','Exact original input points, original generation seed.'),
 ('bpt-seed24680','BPT · seed 24680','bpt-seed24680/02-bpt.glb','Exact original input points, temperature 0.5; generation seed changed.'),
 ('bpt-coverage','BPT · coverage sampling','bpt-coverage/02-bpt.glb','4,096 farthest-point samples from a saved candidate point cloud.'),
 ('bpt-8192','BPT · 8,192 points','bpt-8192/02-bpt.glb','Experimental doubled point count; outside advertised 4,096-point recipe.'),
 ('bpt-mv512','BPT · 512-resolution source','bpt-mv512/02-bpt.glb','Standard BPT settings; denser source surface.'),
 ('bpt-mv-original','BPT · original-background source','bpt-mv-original/02-bpt.glb','Standard BPT settings; source has improved upper braid separation.'),
]
cases.sort(key=lambda case: 0 if case[0]=='original-bpt' else 1)
examples=[];sections=[];manifest=json.loads((p/'render-list.json').read_text())
for key,title,path,note in cases:
 manifest[key]=path
 if not (p/path).exists():continue
 examples.append(dict(id=key,label=title,src='./'+path,note=note))
 figures=''.join(f'<a href="renders/{key}-{angle}.png"><img loading="lazy" src="renders/{key}-{angle}.png" alt="{html.escape(title)} {angle}"></a>' for angle in ['front','side','back-quarter'] if (p/f'renders/{key}-{angle}.png').exists())
 stats=''
 meta=p/path.split('/')[0]/'bpt.json'
 if meta.exists():
  d=json.loads(meta.read_text())
  stats=f"{d.get('output_triangles'):,} triangles · {d.get('boundary_edges')} boundary edges · {d.get('nonmanifold_edges')} non-manifold edges · {d.get('tokens')} tokens"
 if key=='recommended':stats='2,178 triangles · 0 boundary edges · 0 non-manifold edges · consistent winding'
 sections.append(f'<section><h2>{html.escape(title)}</h2><p>{html.escape(note)} <a href="{path}">Download GLB</a></p><p>{stats}</p><div class="views">{figures}</div></section>')
(p/'examples.json').write_text(json.dumps(examples,indent=2)+'\n')
(p/'render-list.json').write_text(json.dumps(manifest,indent=2)+'\n')
details='<section><h2>Visual review: gap gain, overall quality regression</h2><p>The original-background result was rejected as an overall replacement: the face and rear knees look worse. The dense meshes contain rounded knee folds; BPT approximates these with broad angular ledges. Watertightness does not establish visual quality.</p>'
for region in ['face','knees-back']:
 details+=f'<h3>{region}</h3><div class="views">'
 for key,label in [('mv384','Processed views · dense 384'),('mv-original','Original backgrounds · dense 384'),('original-bpt','Original BPT'),('recommended','Gap experiment · BPT')]:
  details+=f'<a style="width:25%" href="detail-renders/{key}-{region}.png">{label}<img loading="lazy" src="detail-renders/{key}-{region}.png" alt="{label} {region}"></a>'
 details+='</div>'
details+='</section>'
(p/'gallery.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Makima geometry comparisons</title><style>body{background:#171d24;color:#dce3ed;font:16px system-ui;margin:2rem auto;max-width:1500px;padding:0 1rem}a{color:#90c9ff}section{border-top:1px solid #526070;padding:1rem 0}.views{display:flex;gap:8px}.views a{width:33.33%}img{width:100%}h2{margin-bottom:.4rem}p{max-width:1000px}</style><h1>Makima: Hunyuan and BPT knob audit</h1><p><a href="./">Open interactive 3D viewer</a>. Same neutral material and camera recipe across these renders. Framing follows each model's bounds. Surface polish, preserved gaps, and topology are separate criteria; higher triangle counts are not quality scores.</p>'''+'<h2>Braid separation: before and after BPT</h2><div class="views compare"><a style="width:50%" href="renders/original-bpt-side.png">Original BPT<img src="renders/original-bpt-side.png" alt="Original BPT side view"></a><a style="width:50%" href="renders/recommended-side.png">Original-background candidate<img src="renders/recommended-side.png" alt="Gap experiment side view"></a></div>'+details+''.join(sections)+'</html>')
print(f'Built review for {len(examples)} completed meshes.')
