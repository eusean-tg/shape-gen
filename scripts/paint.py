#!/usr/bin/env python3
"""Texture an existing mesh with local Hunyuan3D-2 Paint and Delight models."""

import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import traceback
from types import MethodType

# All model components are downloaded beforehand. No implicit network requests.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mesh", type=Path)
    parser.add_argument("--image", type=Path, help="Defaults to input.png beside the mesh")
    parser.add_argument("--output-dir", type=Path, help="Must be new or empty")
    parser.add_argument("--steps", type=int, default=30, help="Paint sampling steps (Delight uses 50)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--texture-size", type=int, choices=[512, 1024, 2048], default=1024)
    parser.add_argument("--render-size", type=int, choices=[512, 1024, 2048], default=1024)
    parser.add_argument("--preserve-uvs", action="store_true", help="Keep existing validated UVs instead of running xatlas")
    args = parser.parse_args()
    args.mesh = args.mesh.resolve()
    args.image = (args.image or args.mesh.parent / "input.png").resolve()
    args.output_dir = (args.output_dir or args.mesh.parent / (args.mesh.stem + "-paint")).resolve()
    for path in [args.mesh, args.image]:
        if not path.is_file():
            parser.error(f"Missing input: {path}")
    if args.steps < 1 or not 0 <= args.seed < 2**32:
        parser.error("Steps must be positive; seed must be in [0, 2**32)")
    if args.output_dir.exists() and (not args.output_dir.is_dir() or any(args.output_dir.iterdir())):
        parser.error(f"Output directory must be empty: {args.output_dir}")
    return args


def run(args, metadata):
    import numpy as np
    from PIL import Image
    import torch
    import trimesh
    from hy3dgen.texgen.pipelines import Hunyuan3DPaintPipeline, Hunyuan3DTexGenConfig
    from hy3dgen.texgen.utils.dehighlight_utils import Light_Shadow_Remover
    from hy3dgen.texgen.utils.multiview_utils import Multiview_Diffusion_Net
    from hy3dgen.texgen.utils.uv_warp_utils import mesh_uv_wrap

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU required")
    torch.cuda.reset_peak_memory_stats()
    metadata["gpu"] = torch.cuda.get_device_name()

    def stage(name):
        metadata["stage"] = name
        (args.output_dir / "paint.json").write_text(json.dumps(metadata, indent=2) + "\n")
        print(f"\n[{time.strftime('%H:%M:%S')}] {name}", flush=True)

    def release(model):
        model.pipeline.maybe_free_model_hooks()
        model.pipeline.remove_all_hooks()
        model.pipeline.to("cpu")

    class StagedPaint(Hunyuan3DPaintPipeline):
        def load_models(self):
            # The upstream constructor loads both networks onto CUDA at once.
            # Load and release each explicitly below instead.
            pass

    model_root = ROOT / "models/hunyuan3d-2"
    config = Hunyuan3DTexGenConfig(
        str(model_root / "hunyuan3d-delight-v2-0"),
        str(model_root / "hunyuan3d-paint-v2-0"),
        "hunyuan3d-paint-v2-0",
    )
    config.device = "cpu"  # Model constructors stay on CPU; renderer uses CUDA.
    config.render_size = args.render_size
    config.texture_size = args.texture_size
    painter = StagedPaint(config)
    mesh = trimesh.load(args.mesh, force="mesh", process=False)
    if not len(mesh.faces) or not np.isfinite(mesh.vertices).all():
        raise ValueError("Mesh is empty or contains non-finite coordinates")
    metadata["input_triangles"] = len(mesh.faces)
    original_bounds = mesh.bounds.copy()
    original_triangles = mesh.triangles.copy()
    original_uv = None
    if args.preserve_uvs:
        original_uv = getattr(mesh.visual, "uv", None)
        if original_uv is None or len(original_uv) != len(mesh.vertices) or not np.isfinite(original_uv).all():
            raise ValueError("--preserve-uvs requires finite per-vertex UVs on the input")
        original_uv = original_uv.copy()
    with Image.open(args.image) as image:
        reference = painter.recenter_image(image.convert("RGBA"))
    reference.save(args.output_dir / "reference.png")

    with torch.inference_mode():
        stage("Delight: remove lighting from the reference")
        delight = Light_Shadow_Remover(config)
        delight.pipeline.enable_vae_slicing()
        delight.pipeline.enable_model_cpu_offload()
        reference = delight(reference)
        reference.save(args.output_dir / "delighted.png")
        release(delight)
        del delight
        gc.collect()
        torch.cuda.empty_cache()

        stage("Keep existing UVs and render six geometry views" if args.preserve_uvs else "UV unwrap and render six geometry views")
        if not args.preserve_uvs:
            mesh = mesh_uv_wrap(mesh)
        # UV seams duplicate vertices but must not alter the source surface.
        if not np.allclose(mesh.triangles, original_triangles, atol=1e-6, rtol=0):
            raise RuntimeError("UV unwrap unexpectedly changed the surface")
        painter.render.load_mesh(mesh)
        elevs, azims, weights = config.candidate_camera_elevs, config.candidate_camera_azims, config.candidate_view_weights
        normals = painter.render_normal_multiview(elevs, azims)
        positions = painter.render_position_multiview(elevs, azims)
        views_dir = args.output_dir / "views"
        views_dir.mkdir()
        (args.output_dir / "views.json").write_text(json.dumps([
            {"elevation": e, "azimuth": a, "weight": w, "image": f"views/{i}-paint.png"}
            for i, (e, a, w) in enumerate(zip(elevs, azims, weights))
        ], indent=2) + "\n")
        for i, (normal, position) in enumerate(zip(normals, positions)):
            normal.save(views_dir / f"{i}-normal.png")
            position.save(views_dir / f"{i}-position.png")
        camera_info = [
            (((azim // 30) + 9) % 12) // {-20: 1, 0: 1, 20: 1, -90: 3, 90: 3}[elev]
            + {-20: 0, 0: 12, 20: 24, -90: 36, 90: 40}[elev]
            for azim, elev in zip(azims, elevs)
        ]

        stage("Paint: load the multiview model")
        multiview = Multiview_Diffusion_Net(config)
        pipeline = multiview.pipeline
        pipeline.enable_vae_slicing()
        pipeline.enable_model_cpu_offload()
        pipeline.set_progress_bar_config(disable=False)
        # Upstream reads learned embeddings directly from the offloaded UNet.
        # Its encode_prompt moves only the positive embedding to CUDA, leaving
        # the negative one on CPU. Place both explicitly before denoising.
        def denoise_on_device(self, *positional, **kwargs):
            for key in ("prompt_embeds", "negative_prompt_embeds"):
                if kwargs.get(key) is not None:
                    kwargs[key] = kwargs[key].to(self._execution_device)
            return type(self).denoise(self, *positional, **kwargs)

        pipeline.denoise = MethodType(denoise_on_device, pipeline)
        # Reduce the intermediate feed-forward activation batch, preserving
        # all six views and their cross-view attention.
        for module in pipeline.unet.modules():
            if type(module).__name__ == "BasicTransformerBlock":
                module.set_chunk_feed_forward(chunk_size=1, dim=0)
        torch.manual_seed(args.seed)
        np.random.seed(args.seed)
        stage("Paint: generate six texture views")
        views = pipeline(
            [reference.resize((512, 512))],
            num_inference_steps=args.steps,
            generator=torch.Generator(device="cpu").manual_seed(args.seed),
            width=512, height=512, num_in_batch=6,
            camera_info_gen=[camera_info], camera_info_ref=[[0]],
            normal_imgs=[[im.resize((512, 512)) for im in normals]],
            position_imgs=[[im.resize((512, 512)) for im in positions]],
        ).images
        for i, view in enumerate(views):
            view.save(views_dir / f"{i}-paint.png")
        release(multiview)
        del pipeline, multiview, module
        gc.collect()
        torch.cuda.empty_cache()

        stage("Project texture views onto UVs and fill uncovered areas")
        views = [view.resize((args.render_size, args.render_size)) for view in views]
        texture, mask = painter.bake_from_multiview(views, elevs, azims, weights, method=config.merge_method)
        mask_np = (mask.squeeze(-1).cpu().numpy() * 255).astype(np.uint8)
        Image.fromarray(mask_np).save(args.output_dir / "projection-mask.png")
        texture = painter.texture_inpaint(texture, mask_np)
        if not torch.isfinite(texture).all():
            raise RuntimeError("Texture contains non-finite values")
        painter.render.set_texture(texture)
        textured = painter.render.save_mesh()
        textured.visual.material.image.save(args.output_dir / "basecolor.png")
        output = args.output_dir / "03-textured.glb"
        textured.export(output)

    stage("Validate textured GLB")
    loaded = trimesh.load(output, force="mesh", process=False)
    if len(loaded.faces) != metadata["input_triangles"] or not np.allclose(loaded.bounds, original_bounds, atol=1e-6):
        raise RuntimeError("Export changed mesh geometry")
    if loaded.visual.kind != "texture" or len(loaded.visual.uv) != len(loaded.vertices):
        raise RuntimeError("Export has no usable texture coordinates")
    if args.preserve_uvs and not np.allclose(loaded.visual.uv[loaded.faces], original_uv[mesh.faces], atol=1e-7, rtol=0):
        raise RuntimeError("Paint changed the supplied UV layout")
    if not np.allclose(loaded.triangles, original_triangles, atol=1e-6, rtol=0):
        raise RuntimeError("Paint changed triangle coordinates or winding")
    material = loaded.visual.material
    embedded = getattr(material, "baseColorTexture", None)
    if embedded is None:
        embedded = getattr(material, "image", None)
    if embedded is None or embedded.size != (args.texture_size, args.texture_size):
        raise RuntimeError("Export is missing its embedded texture")
    metadata.update(
        output=str(output), output_sha256=sha256(output), output_triangles=len(loaded.faces),
        peak_cuda_allocated_mib=round(torch.cuda.max_memory_allocated() / 2**20, 1),
        peak_cuda_reserved_mib=round(torch.cuda.max_memory_reserved() / 2**20, 1),
        embedded_texture_size=list(embedded.size),
    )
    print(f"\nSaved {output}", flush=True)


def main():
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    metadata = {
        "status": "running", "mesh": str(args.mesh), "mesh_sha256": sha256(args.mesh),
        "image": str(args.image), "image_sha256": sha256(args.image),
        "steps": args.steps, "delight_steps": 50, "seed": args.seed,
        "texture_size": args.texture_size, "render_size": args.render_size,
        "view_size": 512, "view_count": 6, "model": "hunyuan3d-paint-v2-0",
        "preserve_uvs": args.preserve_uvs,
        "upstream_commit": subprocess.check_output(
            ["git", "-C", str(ROOT / "third_party/Hunyuan3D-2"), "rev-parse", "HEAD"], text=True
        ).strip(),
    }
    provenance = ROOT / "models/hunyuan3d-2/paint-model-info.json"
    if provenance.is_file():
        metadata["model_provenance"] = json.loads(provenance.read_text())
    try:
        run(args, metadata)
        metadata["status"] = "complete"
    except BaseException as exc:
        metadata["status"] = "failed"
        metadata["error"] = str(exc)
        metadata["traceback"] = traceback.format_exc()
        raise
    finally:
        metadata["elapsed_seconds"] = round(time.monotonic() - start, 2)
        (args.output_dir / "paint.json").write_text(json.dumps(metadata, indent=2) + "\n")


if __name__ == "__main__":
    main()
