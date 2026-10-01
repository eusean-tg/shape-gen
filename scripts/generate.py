"""Generate a dense GLB using local Hunyuan3D-2.0, 2mini, or 2mv weights."""

import argparse
import hashlib
import json
import math
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from reduce_mesh import reduce_mesh, triangle_budget


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIRS = {
    "full": ROOT / "models/hunyuan3d-2/hunyuan3d-dit-v2-0",
    "mini": ROOT / "models/hunyuan3d-2mini/hunyuan3d-dit-v2-mini",
    "mv": ROOT / "models/hunyuan3d-2mv/hunyuan3d-dit-v2-mv",
}


def positive_int(value):
    value = int(value)
    if value < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return value


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Input image, or with --model mv a folder of front/left/back/right.png views")
    parser.add_argument("--model", choices=MODEL_DIRS, default="full", help="Model to use (default: full)")
    parser.add_argument("--target-triangles", type=triangle_budget, help="Also save 02-lowpoly.glb within this triangle budget")
    parser.add_argument("--output-dir", type=Path, help="New asset folder (default: assets/<image stem>-<model>)")
    parser.add_argument("--steps", type=positive_int, default=50)
    parser.add_argument("--resolution", type=positive_int, default=128, help="Mesh grid resolution (default: 128)")
    parser.add_argument("--chunks", type=positive_int, default=1024, help="Decoder query batch size (default: 1024)")
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--guidance", type=float, default=5.0)
    parser.add_argument("--keep-background", action="store_true", help="Skip automatic background removal for opaque images")
    args = parser.parse_args()
    if not math.isfinite(args.guidance) or args.guidance < 0:
        parser.error("--guidance must be finite and nonnegative")
    if args.resolution < 16:
        parser.error("--resolution must be at least 16")
    return args


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_views(source, model):
    if model != "mv":
        if not source.is_file():
            raise ValueError(f"Input image not found: {source}")
        return {"front": source}
    if not source.is_dir():
        raise ValueError("--model mv expects a directory containing front.png and other named views")
    views = {name: source / f"{name}.png" for name in ("front", "left", "back", "right")
             if (source / f"{name}.png").is_file()}
    if "front" not in views or len(views) < 2:
        raise ValueError("Multi-view input needs front.png and at least one of left.png, back.png, right.png")
    return views


def prepare_views(paths, keep_background):
    from PIL import Image, ImageOps

    images, background_removed = {}, {}
    rembg_session = None
    for name, path in paths.items():
        with Image.open(path) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGBA")
        alpha_min, alpha_max = image.getchannel("A").getextrema()
        if alpha_max == 0:
            raise ValueError(f"The {name} input image is fully transparent: {path}")
        remove_background = alpha_min == 255 and not keep_background
        if remove_background:
            print(f"Removing background from {name} on CPU (first use downloads U2Net)...", flush=True)
            from rembg import new_session, remove

            if rembg_session is None:
                rembg_session = new_session("u2net", providers=["CPUExecutionProvider"])
            image = remove(image, session=rembg_session)
        if image.getchannel("A").getbbox() is None:
            raise ValueError(f"No foreground remains in {name} after background removal")
        images[name] = image
        background_removed[name] = remove_background
    return images, background_removed


def load_pipeline(model_dir):
    import torch
    from accelerate import cpu_offload_with_hook
    from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline

    print(f"Loading local FP16 weights from {model_dir.name} into system RAM...", flush=True)
    pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_single_file(
        str(model_dir / "model.fp16.safetensors"),
        str(model_dir / "config.yaml"),
        device="cpu",
        dtype=torch.float16,
        use_safetensors=True,
    )
    # This upstream revision's convenience offload helper refers to an undefined
    # `components` attribute and leaves pipeline.device on CPU. Attach Accelerate
    # hooks explicitly and set the device used to create sampling tensors.
    hooks = []
    previous = None
    for component in (pipeline.conditioner, pipeline.model, pipeline.vae):
        component.eval()
        _, previous = cpu_offload_with_hook(component, "cuda:0", prev_module_hook=previous)
        hooks.append(previous)
    pipeline.device = torch.device("cuda:0")
    return pipeline, hooks


def main():
    args = parse_args()
    model_dir = MODEL_DIRS[args.model]
    source = args.image.expanduser().resolve()
    try:
        paths = source_views(source, args.model)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    for filename in ("model.fp16.safetensors", "config.yaml", "model-info.json"):
        if not (model_dir / filename).is_file():
            raise SystemExit(f"Missing {args.model} model file: {model_dir / filename}")
    output_dir = (args.output_dir or ROOT / "assets" / f"{source.stem}-{args.model}").expanduser().resolve()
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        raise SystemExit(f"Output folder is not empty: {output_dir}\nChoose a new --output-dir to preserve the previous run.")

    import torch

    if not torch.cuda.is_available():
        raise SystemExit("An NVIDIA GPU accessible to PyTorch is required.")
    info = json.loads((model_dir / "model-info.json").read_text())
    if sha256(model_dir / "config.yaml") != info["config_sha256"]:
        raise SystemExit("Model config differs from the verified config.")
    if (model_dir / "model.fp16.safetensors").stat().st_size != info["file"]["size"]:
        raise SystemExit("Model checkpoint size differs from the verified download.")
    images, background_removed = prepare_views(paths, args.keep_background)
    image = images if args.model == "mv" else images["front"]

    output_dir.mkdir(parents=True, exist_ok=True)
    images["front"].save(output_dir / "input.png")
    view_metadata = {}
    if args.model == "mv":
        views_dir = output_dir / "views"
        views_dir.mkdir()
        for name, view in images.items():
            destination = views_dir / f"{name}.png"
            view.save(destination)
            view_metadata[name] = {
                "source": str(paths[name]), "source_sha256": sha256(paths[name]),
                "processed_image": str(destination), "processed_sha256": sha256(destination),
                "background_removed": background_removed[name],
            }
        print(f"Using views: {', '.join(images)}", flush=True)
    metadata = {
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "model": info["repo_id"],
        "model_choice": args.model,
        "subfolder": info["subfolder"],
        "model_revision": info["revision"],
        "checkpoint_sha256": info["sha256"],
        "config_sha256": info["config_sha256"],
        "source_image": str(paths["front"]),
        "source_image_sha256": sha256(paths["front"]),
        "processed_image_sha256": sha256(output_dir / "input.png"),
        "background_removed": any(background_removed.values()),
        "steps": args.steps,
        "resolution": args.resolution,
        "chunks": args.chunks,
        "target_triangles": args.target_triangles,
        "seed": args.seed,
        "guidance": args.guidance,
        "precision": "fp16",
        "offload": "conditioner -> model -> vae, one component on GPU at a time",
        "mesh_extractor": "mc",
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0),
        "dependency_lock_sha256": sha256(ROOT / "uv.lock"),
        "source_commit": subprocess.check_output(
            ["git", "-C", str(ROOT / "third_party/Hunyuan3D-2"), "rev-parse", "HEAD"], text=True
        ).strip(),
    }
    if view_metadata:
        metadata["views"] = view_metadata
    metadata_path = output_dir / "generation.json"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    start = time.monotonic()
    hooks = []
    torch.cuda.reset_peak_memory_stats()
    try:
        pipeline, hooks = load_pipeline(model_dir)
        print(f"Generating: {args.steps} steps, resolution {args.resolution}, chunks {args.chunks}", flush=True)
        mesh = pipeline(
            image=image,
            num_inference_steps=args.steps,
            guidance_scale=args.guidance,
            octree_resolution=args.resolution,
            num_chunks=args.chunks,
            mc_algo="mc",
            generator=torch.Generator(device="cpu").manual_seed(args.seed),
            output_type="trimesh",
        )[0]
        if mesh is None or len(mesh.faces) == 0:
            raise RuntimeError("Generation produced no mesh. See the preceding mesh-extraction error.")
        target = output_dir / "01-dense.glb"
        mesh.export(target)
        metadata.update(dense_mesh_saved=True, vertices=len(mesh.vertices), faces=len(mesh.faces), watertight=bool(mesh.is_watertight))
        print(f"Saved {target} ({len(mesh.vertices):,} vertices, {len(mesh.faces):,} triangles)", flush=True)
        if args.target_triangles is not None:
            for hook in hooks:
                hook.offload()
            torch.cuda.empty_cache()
            print(f"Reducing mesh on CPU to at most {args.target_triangles:,} triangles...", flush=True)
            lowpoly, reduction = reduce_mesh(mesh, args.target_triangles)
            lowpoly.export(output_dir / "02-lowpoly.glb")
            metadata["reduction"] = reduction
            print(f"Saved {output_dir / '02-lowpoly.glb'} ({len(lowpoly.faces):,} triangles)", flush=True)
        metadata["status"] = "complete"
    except Exception as exc:
        metadata.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        if isinstance(exc, torch.cuda.OutOfMemoryError):
            print("GPU memory exhausted. Close GPU-heavy applications; for extraction OOM, lower --resolution and --chunks.", flush=True)
        raise
    finally:
        metadata["elapsed_seconds"] = round(time.monotonic() - start, 2)
        metadata["peak_allocated_vram_mib"] = round(torch.cuda.max_memory_allocated() / 1024**2, 1)
        metadata["peak_reserved_vram_mib"] = round(torch.cuda.max_memory_reserved() / 1024**2, 1)
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
        (output_dir / "notes.md").write_text(
            "# Shape generation\n\n"
            f"- Model: {metadata['model']} / {metadata['subfolder']}\n"
            f"- Status: {metadata['status']}\n"
            f"- Seed: {args.seed}; steps: {args.steps}; guidance: {args.guidance}\n"
            f"- Resolution: {args.resolution}; decoder chunk size: {args.chunks}\n"
            f"- Peak allocated VRAM: {metadata['peak_allocated_vram_mib']} MiB\n"
            f"- Triangle target: {args.target_triangles if args.target_triangles is not None else 'none'}; "
            f"actual: {metadata.get('reduction', {}).get('output_triangles', 'not reduced')}.\n"
            "- Geometry only; no UV unwrap or textures yet.\n"
            "- Full settings and hashes: `generation.json`.\n"
        )
        for hook in hooks:
            hook.offload()
        torch.cuda.empty_cache()
    print(f"Elapsed: {metadata['elapsed_seconds']}s; peak allocated VRAM: {metadata['peak_allocated_vram_mib']} MiB", flush=True)


if __name__ == "__main__":
    main()
