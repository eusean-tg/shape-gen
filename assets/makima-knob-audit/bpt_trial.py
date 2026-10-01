"""Reconstruct a dense mesh with BPT using staged FP16 inference.

Run with .venv-bpt/bin/python, independently of the Hunyuan environment.
The point encoder is unloaded from CUDA before autoregressive generation.
"""
import argparse
from enum import IntEnum
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
REPO = ROOT / "third_party/bpt"


def load_weights(torch, checkpoint):
    # The verified official checkpoint contains unused optimizer state. Map its
    # three legacy metadata types to inert containers, retaining weights_only
    # loading instead of importing DeepSpeed or executing arbitrary pickle code.
    class LossScaler:
        pass

    class FragmentAddress:
        pass

    class ZeroStage(IntEnum):
        disabled = 0
        optimizer_states = 1
        gradients = 2
        weights = 3

    allowed = [
        (LossScaler, "deepspeed.runtime.fp16.loss_scaler.LossScaler"),
        (FragmentAddress, "deepspeed.utils.tensor_fragment.fragment_address"),
        (ZeroStage, "deepspeed.runtime.zero.config.ZeroStageEnum"),
    ]
    with torch.serialization.safe_globals(allowed):
        return torch.load(checkpoint, map_location="cpu", weights_only=True, mmap=True)["model"]


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mesh", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--temperature", type=float, default=0.5)
    parser.add_argument("--max-tokens", type=int, default=10000,
                        help="Safety limit, not a target face count (maximum 10000)")
    parser.add_argument("--encoder-device", choices=["cuda", "cpu"], default="cuda")
    parser.add_argument('--cloud', type=Path, help='Normalized points/normals from the same source mesh')
    parser.add_argument('--top-k', type=int, default=50)
    parser.add_argument('--top-p', type=float, default=.95)
    args = parser.parse_args()
    if not 1 <= args.max_tokens <= 10000:
        parser.error("--max-tokens must be between 1 and 10000")
    if not math.isfinite(args.temperature) or args.temperature <= 0:
        parser.error("--temperature must be finite and positive")
    source = args.mesh.resolve(strict=True)
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error(f"Output folder is not empty: {output}")
    checkpoint = ROOT / "models/bpt/bpt-8-16-500m.pt"
    from setup_bpt import SHA256
    print("Verifying checkpoint...", flush=True)
    if sha256(checkpoint) != SHA256:
        raise RuntimeError("BPT checkpoint checksum mismatch; run scripts/setup_bpt.py")

    import numpy as np
    import torch
    import trimesh
    import yaml
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the mesh generator")
    torch.set_num_threads(4)
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    output.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(REPO))
    from model.model import MeshTransformer
    from model.serializaiton import BPT_deserialize
    from utils import joint_filter

    started = time.monotonic()
    torch.cuda.reset_peak_memory_stats()
    metadata = {
        "input": str(source), "input_sha256": sha256(source),
        "checkpoint_sha256": SHA256,
        "upstream_commit": subprocess.check_output(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip(),
        "seed": args.seed, "temperature": args.temperature,
        "max_tokens": args.max_tokens, "encoder_device": args.encoder_device,
        "precision": "float16", "memory_strategy": "staged encoder/generator",
        "gpu": torch.cuda.get_device_name(), "torch": torch.__version__,
        "status": "running",
    }

    def save_metadata():
        metadata.update({
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "peak_allocated_mib": round(torch.cuda.max_memory_allocated() / 2**20, 1),
            "peak_reserved_mib": round(torch.cuda.max_memory_reserved() / 2**20, 1),
        })
        (output / "bpt.json").write_text(json.dumps(metadata, indent=2) + "\n")

    try:
        mesh = trimesh.load(source, force="mesh", process=False)
        if not len(mesh.faces) or not np.isfinite(mesh.vertices).all():
            raise ValueError("Input must contain finite triangular geometry")
        center = mesh.bounds.mean(axis=0)
        extent = float(mesh.extents.max())
        if extent <= 0:
            raise ValueError("Input mesh has zero extent")
        normalized = mesh.copy()
        normalized.vertices = (normalized.vertices - center) * (1.9 / extent)
        # Match the upstream 50k -> 4096 sampling, without its mesh-object reload bug.
        points, face_ids = normalized.sample(50000, return_index=True)
        cloud = np.concatenate([points, normalized.face_normals[face_ids]], axis=1).astype(np.float16)
        cloud = cloud[np.random.choice(len(cloud), 4096, replace=False)]
        if args.cloud:
            cloud = np.load(args.cloud, allow_pickle=False).astype(np.float16)
            assert cloud.ndim == 2 and cloud.shape[1] == 6 and np.isfinite(cloud).all()
        metadata.update(cloud_sha256=hashlib.sha256(cloud.tobytes()).hexdigest(),
                        point_count=len(cloud), top_k=args.top_k, top_p=args.top_p)
        np.save(output / "input-points.npy", cloud)
        metadata.update({"input_triangles": len(mesh.faces), "input_vertices": len(mesh.vertices),
                         "normalization_center": center.tolist(), "normalization_extent": extent})
        print(f"Input: {len(mesh.faces):,} triangles; constructing model on CPU...", flush=True)
        config = yaml.safe_load((REPO / "config/BPT-open-8k-8-16.yaml").read_text())
        previous_cwd = Path.cwd()
        try:
            # Upstream's point conditioner resolves its YAML relative to the repo.
            os.chdir(REPO)
            model = MeshTransformer(
                dim=config["dim"], attn_depth=config["depth"], max_seq_len=config["max_seq_len"],
                dropout=config["dropout"], mode=config["mode"], num_discrete_coors=2**config["quant_bit"],
                block_size=config["block_size"], offset_size=config["offset_size"],
                conditioned_on_pc=True, use_special_block=config["use_special_block"],
                encoder_name=config["encoder_name"], encoder_freeze=True,
            )
        finally:
            os.chdir(previous_cwd)
        state = load_weights(torch, checkpoint)
        model.load_state_dict(state, strict=True)
        del state
        model.eval().requires_grad_(False)
        metadata["parameters"] = sum(p.numel() for p in model.parameters())
        conditioner = model.conditioner
        encoder_dtype = torch.float16 if args.encoder_device == "cuda" else torch.float32
        conditioner.to(device=args.encoder_device, dtype=encoder_dtype)
        print(f"Encoding 4096 surface points on {args.encoder_device}...", flush=True)
        with torch.inference_mode():
            condition = conditioner(pc=torch.from_numpy(cloud).unsqueeze(0).to(args.encoder_device))
            condition = condition.to("cpu", dtype=torch.float16)
        conditioner.cpu()
        # Detach it so model.cuda() only moves the mesh-generation network.
        model.conditioner = None
        del conditioner
        gc.collect()
        torch.cuda.empty_cache()
        model.half().cuda()
        condition = condition.cuda()
        metadata["generator_resident_mib"] = round(torch.cuda.memory_allocated() / 2**20, 1)
        print(f"Generator loaded: {metadata['generator_resident_mib']:.0f} MiB allocated", flush=True)
        generation_start = time.monotonic()
        codes = torch.empty((1, 0), device="cuda", dtype=torch.long)
        cache = None
        ended = False
        with torch.inference_mode():
            for step in range(args.max_tokens):
                logits, cache = model.forward_on_codes(
                    codes, return_loss=False, return_cache=True, append_eos=False,
                    cond_embeds=condition, cache=cache)
                filtered = joint_filter(logits[:, -1], k=args.top_k, p=args.top_p)
                probabilities = torch.softmax(filtered / args.temperature, dim=-1)
                sample = torch.multinomial(probabilities, 1)
                if sample.item() == model.eos_token_id:
                    ended = True
                    break
                codes = torch.cat((codes, sample), dim=1)
                if (step + 1) % 250 == 0:
                    elapsed = time.monotonic() - generation_start
                    print(f"{step+1} tokens, {elapsed:.1f}s, peak {torch.cuda.max_memory_allocated()/2**20:.0f} MiB", flush=True)
        torch.cuda.synchronize()
        raw_codes = codes[0].cpu().numpy()
        np.save(output / "codes.npy", raw_codes)
        metadata.update({"tokens": len(raw_codes), "ended_with_eos": ended,
                         "generation_seconds": round(time.monotonic() - generation_start, 2)})
        if not ended:
            raise RuntimeError("Reached token limit without EOS; saved tokens, not a complete mesh")
        vertices = BPT_deserialize(raw_codes.copy(), block_size=model.block_size,
                                   offset_size=model.offset_size, use_special_block=model.use_special_block)
        if not len(vertices) or len(vertices) % 3 or not np.isfinite(vertices).all():
            raise RuntimeError("Generated mesh has invalid coordinates")
        faces = np.arange(len(vertices)).reshape(-1, 3)
        result = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        result.merge_vertices()
        result.update_faces(result.unique_faces())
        result.update_faces(result.nondegenerate_faces())
        result.remove_unreferenced_vertices()
        result.fix_normals()
        # Restore source coordinates for direct overlays and subsequent texture baking.
        result.vertices = result.vertices * (extent / 1.9) + center
        result.visual.face_colors = [160, 175, 192, 255]
        result.export(output / "02-bpt.glb")
        result.export(output / "02-bpt.obj")
        edge_counts = np.bincount(result.edges_unique_inverse)
        metadata.update({
            "status": "complete", "output_triangles": len(result.faces),
            "output_vertices": len(result.vertices), "watertight": bool(result.is_watertight),
            "winding_consistent": bool(result.is_winding_consistent),
            "boundary_edges": int((edge_counts == 1).sum()),
            "nonmanifold_edges": int((edge_counts > 2).sum()),
            "connected_components": len(result.split(only_watertight=False)),
            "output_sha256": sha256(output / "02-bpt.glb"),
        })
        save_metadata()
        print(json.dumps(metadata, indent=2), flush=True)
    except Exception as exc:
        metadata.update({"status": "failed", "error": str(exc)})
        save_metadata()
        raise


if __name__ == "__main__":
    import fcntl
    with (Path.home()/'.cache/shape-gen/gpu.lock').open('a') as lock:
        print('Waiting for shared GPU lock', flush=True)
        fcntl.flock(lock, fcntl.LOCK_EX)
        main()
