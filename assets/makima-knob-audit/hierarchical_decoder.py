"""Auditable fixes for the installed upstream hierarchical decoder, experiment only.

1. Convert integer grid indices to floating point before constructing scale/offset
   tensors. Upstream otherwise truncates a sub-unit cell width to integer zero.
2. Keep interpolated coarse logits outside the queried surface band. The upstream
   NaN sentinel produces invalid vertices with scikit-image Marching Cubes.
"""
import inspect
from hy3dgen.shapegen.models.autoencoders import volume_decoders as upstream

source = inspect.getsource(upstream.HierarchicalVolumeDecoding)
source = source.replace(
    "next_logits = torch.full(next_index.shape, -10000., dtype=dtype, device=device)",
    "next_logits = F.interpolate(grid_logits.unsqueeze(1).float(), size=tuple(grid_size), "
    "mode='trilinear', align_corners=True).squeeze(1).squeeze(0).to(dtype)")
source = source.replace("next_points = torch.stack(nidx, dim=1)",
                        "next_points = torch.stack(nidx, dim=1).float()")
namespace = vars(upstream).copy()
exec(compile(source, __file__, 'exec'), namespace)
HierarchicalVolumeDecoding = namespace['HierarchicalVolumeDecoding']
