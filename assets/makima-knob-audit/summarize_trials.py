"""Collect measured results without treating mesh counts as visual quality."""
from pathlib import Path
import json
p=Path(__file__).resolve().parent
rows=[]
for f in sorted(p.glob('*/trial.json')):
 d=json.loads(f.read_text())
 if d['status']!='complete':continue
 for mesh in d['outputs']:
  rows.append({'stage':'HY','trial':f.parent.name+'/'+mesh['file'],
   'triangles':mesh['triangles'],'boundary_edges':mesh['boundary_edges'],
   'nonmanifold_edges':mesh['nonmanifold_edges'],
   'seconds':round(d['elapsed_seconds'],1),'peak_allocated_mib':round(d['peak_allocated_mib']),
   'peak_reserved_mib':round(d['peak_reserved_mib'])})
for f in sorted(p.glob('*/bpt.json')):
 d=json.loads(f.read_text())
 if d['status']!='complete':continue
 rows.append({'stage':'BPT','trial':f.parent.name,'triangles':d['output_triangles'],
  'boundary_edges':d['boundary_edges'],'nonmanifold_edges':d['nonmanifold_edges'],
  'seconds':d['elapsed_seconds'],'peak_allocated_mib':round(d['peak_allocated_mib']),
  'peak_reserved_mib':round(d['peak_reserved_mib']),'tokens':d['tokens'],'ended_with_eos':d['ended_with_eos']})
(p/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
table=['| Trial | Triangles | Boundary edges | Non-manifold edges | Peak allocated MiB |',
       '|---|---:|---:|---:|---:|']
for d in rows:
 table.append(f"| {d['trial']} | {d['triangles']:,} | {d['boundary_edges']} | {d['nonmanifold_edges']} | {d['peak_allocated_mib']:,} |")
(p/'results.md').write_text('\n'.join(table)+'\n\nMemory is PyTorch allocation, not total GPU usage. Shape extraction trials that reuse a saved latent exclude diffusion sampling. All resolutions/levels in one trial share its run-level peak. Raw marching-cubes degenerate faces are included in the table; cleaned candidate metrics are recorded separately.\n')
print('\n'.join(table))
