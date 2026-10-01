"""Rebuild the static comparison gallery from completed local artifacts."""
import html, json
from pathlib import Path

root = Path(__file__).resolve().parent
cases = [
 ('trellis2-repaired', 'TRELLIS.2 · 1024 · extra cleanup', 'trellis2/front1024/01-dense-remesh-clean.glb', '189,699 triangles. Removed non-manifold edges after demo remeshing; still has 977 boundary edges. Source for the second reduction trial.'),
 ('trellis2-bpt-exterior', 'TRELLIS.2 → exterior sampling → BPT · 1,789 tris', 'bpt-exterior1024/02-bpt.glb', 'Experimental visibility-filtered sampling. More coherent than the first BPT trial, but 145 boundary edges and an oversimplified face remain. Can omit deep recesses; not rig-ready.'),
 ('trellis2-decimated-clean', 'Cleaned TRELLIS.2 → decimation · 2,353 tris', 'decimated-clean.glb', 'Blender collapse decimation, targeting the original HY/BPT budget of 2,409 triangles. No extra repair after reduction.'),
 ('trellis2-bpt-clean', 'Cleaned TRELLIS.2 → BPT', 'bpt-clean1024/02-bpt.glb', 'Second BPT trial, same standard settings; input is the export after extra topology cleanup.'),
 ('trellis2-remesh', 'TRELLIS.2 · 1024 · demo remesh', 'trellis2/front1024/01-dense-remesh.glb', 'Single front image. Defined collar, tie and hair layers; topology still needs repair. Remesh target 500k.'),
 ('trellis2-bpt', 'First BPT trial · fragmented', 'bpt-front1024/02-bpt.glb', '1,676 triangles, 48 components. Standard 4,096-point BPT, seed 12345, temperature 0.5. Not a usable replacement.'),
 ('trellis2-decimated', 'First decimation · target missed', 'decimated-front.glb', 'Requested 1,676 triangles; stalled at 72,237 Blender polygons before export. Not a matched-budget comparison.'),
 ('hy-bpt', 'Original HY 2mv → BPT', 'hy-bpt.glb', 'Original four-view baseline, 2,409 triangles. This model saw the rear braid reference.'),
 ('hy-dense', 'Original HY 2mv · dense', 'hy-dense.glb', 'Original four-view baseline, 62,648 triangles. More view information than TRELLIS.2.'),
 ('hy-full', 'HY full · single front · dense', 'hy-full.glb', 'Prior single-front comparison, extraction resolution 384. Same source cutout, model-specific preprocessing.'),
 ('trellis2-remesh512', 'TRELLIS.2 · 512 · demo remesh', 'trellis2/front/01-dense-remesh.glb', 'Lower-resolution run, same seed and front reference. Same remesh recipe as 1024.'),
 ('trellis-front', 'Original TRELLIS · single front', 'front/01-dense-raw.glb', 'Older DINOv2-based model; no clear visual advantage in this example.'),
 ('trellis-multi', 'Original TRELLIS · four views', 'multiview/01-dense-raw.glb', 'Official stochastic multi-image inference. Not a separately trained multiview model; upper braid remains joined.'),
 ('trellis2-front', 'TRELLIS.2 · 512 · raw decoder', 'trellis2/front/01-dense-raw.glb', 'Diagnostic only: raw extraction with many tiny holes and non-manifold edges, before demo cleanup.'),
 ('trellis2-1024', 'TRELLIS.2 · 1024 · raw decoder', 'trellis2/front1024/01-dense-raw.glb', 'Diagnostic only: 3.13 million triangles. Before the official demo geometry export stages.'),
]
failed = []
completed = []
for item in cases:
    _, title, path, _ = item
    if (root/path).exists():
        completed.append(item)
    else:
        metadata = root/Path(path).parent/'bpt.json'
        assert metadata.exists(), path
        data = json.loads(metadata.read_text())
        assert data['status'] == 'failed', path
        failed.append((title, data['error']))
cases = completed
(root/'examples.json').write_text(json.dumps([
    dict(id=key, label=title, src='./'+path, note=note)
    for key, title, path, note in cases], indent=2)+'\n')
angles = [('renders','front','Head and torso'), ('renders','side','Side'),
          ('renders','back-quarter','Back quarter'), ('detail-renders','face','Face'),
          ('detail-renders','knees-back','Rear knees'), ('renders','full','Full body')]
sections = []
for folder, angle, title in angles:
    cards = []
    for key, label, path, note in cases:
        image = f'{folder}/{key}-{angle}.png'
        assert (root/image).exists(), image
        cards.append(f'<article><h3>{html.escape(label)}</h3><a href="{image}"><img loading="lazy" src="{image}" alt="{html.escape(label)}: {title}"></a><p>{html.escape(note)}</p><a href="{path}">Download GLB</a></article>')
    sections.append(f'<section><h2>{title}</h2><div class="row">'+''.join(cards)+'</div></section>')
(root/'gallery.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Makima · TRELLIS geometry comparison</title>
<style>body{font:16px/1.5 system-ui;background:#111821;color:#e1e8ef;margin:24px}a{color:#89cbff}h1{margin-bottom:8px}p{max-width:1000px}.row{display:flex;overflow-x:auto;gap:16px;padding-bottom:16px}article{flex:0 0 300px;background:#202b38;border-radius:8px;padding:12px}article img{width:100%;height:auto}h3{font-size:16px;min-height:48px}article p{font-size:14px;color:#bcc9d7}section{margin:32px 0}</style>
<h1>Makima · TRELLIS geometry comparison</h1>
<p><a href="./">Interactive viewer</a> · <a href="./report.md">Experiment report</a></p>
<p>Untextured clay renders with matching cameras and lighting. Scroll each row horizontally; click an image to enlarge it.
TRELLIS.2 uses one front image, which does not show the rear braid. HY 2mv and the older TRELLIS multiview run use four images.
These are isolated geometry experiments, not rig-ready replacements.</p>
<p>The 1024 TRELLIS.2 dense result has more defined clothing layers. Compare its BPT and ordinary decimation outputs to see which details survive the triangle budget. A closed-looking surface is not proof of clean topology.</p>
'''+''.join(f'<p><strong>Failed trial: {html.escape(title)}</strong> — {html.escape(error)}. No completed mesh is displayed.</p>' for title,error in failed)+''.join(sections)+'</html>')
print(f'Built gallery with {len(cases)} models and {len(cases)*len(angles)} images.')
