"""Check the image-to-mesh dependencies without downloading model weights."""

import platform
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pymeshlab
import torch
import torch.nn.functional as F
import trimesh
from hy3dgen.rembg import BackgroundRemover
from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline
from hy3dgen.shapegen.models.autoencoders import MCSurfaceExtractor


def main():
    print(f"Python: {platform.python_version()}")
    for package in ("torch", "torchvision", "hy3dgen", "diffusers", "transformers"):
        print(f"{package}: {version(package)}")
    if not torch.cuda.is_available():
        raise RuntimeError("PyTorch cannot access the NVIDIA GPU")
    print(f"GPU: {torch.cuda.get_device_name(0)}; CUDA runtime: {torch.version.cuda}")

    # Exercise the half-precision math used by shape generation.
    with torch.inference_mode():
        matrix = torch.ones((32, 32), device="cuda", dtype=torch.float16)
        torch.testing.assert_close(matrix @ matrix, torch.full_like(matrix, 32))
        query = torch.randn((1, 2, 32, 64), device="cuda", dtype=torch.float16)
        attention = F.scaled_dot_product_attention(query, query, query)
        assert torch.isfinite(attention).all().item()
    torch.cuda.synchronize()
    print("CUDA FP16 matrix multiplication and attention: OK")

    # Extract a sphere using Hunyuan's standard marching-cubes path.
    axis = torch.linspace(-1, 1, 17)
    x, y, z = torch.meshgrid(axis, axis, axis, indexing="ij")
    field = (0.5 - torch.sqrt(x * x + y * y + z * z)).unsqueeze(0)
    surface = MCSurfaceExtractor()(field, mc_level=0, bounds=1.0, octree_resolution=16)[0]
    assert surface is not None and len(surface.mesh_f) > 0
    mesh = trimesh.Trimesh(vertices=surface.mesh_v, faces=surface.mesh_f)
    mesh_set = pymeshlab.MeshSet()
    mesh_set.add_mesh(pymeshlab.Mesh(np.asarray(mesh.vertices), np.asarray(mesh.faces)))
    assert mesh_set.current_mesh().face_number() > 0
    with TemporaryDirectory() as directory:
        output = Path(directory) / "sphere.glb"
        mesh.export(output)
        restored = trimesh.load(output, force="mesh")
        assert len(restored.faces) == len(mesh.faces)
    print("Mesh extraction, PyMeshLab, and GLB export/import: OK")
    print(f"Pipeline import: {Hunyuan3DDiTFlowMatchingPipeline.__name__}")
    print(f"Background removal import: {BackgroundRemover.__name__}")
    print("Environment ready. Model weights and full inference are not tested here.")


if __name__ == "__main__":
    main()
