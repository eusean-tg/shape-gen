"""Reduce an untextured mesh to a triangle budget on CPU."""

import argparse
import hashlib
import json
import time
from pathlib import Path


def triangle_budget(value):
    value = int(value)
    if value < 4:
        raise argparse.ArgumentTypeError("triangle budget must be at least 4")
    return value


def reduce_mesh(mesh, target_triangles):
    """Return geometry within the budget, preserving topology where possible.

    Raise if preservation constraints prevent meeting the budget. Input geometry
    is never mutated. Materials and UVs are outside this geometry-only stage.
    """
    import numpy as np
    import pymeshlab
    import trimesh

    if target_triangles < 4:
        raise ValueError("triangle budget must be at least 4")
    if not len(mesh.faces) or not np.isfinite(mesh.vertices).all():
        raise ValueError("Input must contain a nonempty mesh with finite vertices")
    before = len(mesh.faces)
    if before <= target_triangles:
        reduced = trimesh.Trimesh(vertices=mesh.vertices.copy(), faces=mesh.faces.copy(), process=False)
    else:
        mesh_set = pymeshlab.MeshSet()
        mesh_set.add_mesh(pymeshlab.Mesh(vertex_matrix=np.asarray(mesh.vertices), face_matrix=np.asarray(mesh.faces)))
        mesh_set.apply_filter(
            "meshing_decimation_quadric_edge_collapse",
            targetfacenum=target_triangles,
            qualitythr=1.0,
            preserveboundary=True,
            boundaryweight=3.0,
            preservenormal=True,
            preservetopology=True,
            autoclean=True,
        )
        result = mesh_set.current_mesh()
        reduced = trimesh.Trimesh(vertices=result.vertex_matrix().copy(), faces=result.face_matrix().copy(), process=False)
    actual = len(reduced.faces)
    if actual == 0 or not np.isfinite(reduced.vertices).all():
        raise RuntimeError("Simplification produced an empty or invalid mesh")
    if actual > target_triangles:
        raise RuntimeError(
            f"Could only reduce to {actual} triangles while preserving topology; "
            f"budget was {target_triangles}. Increase the target or repair the mesh."
        )
    return reduced, {
        "method": "quadric_edge_collapse",
        "target_triangles": target_triangles,
        "input_triangles": before,
        "output_triangles": actual,
        "vertices": len(reduced.vertices),
        "watertight": bool(reduced.is_watertight),
        "preserve_topology": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mesh", type=Path)
    parser.add_argument("--target-triangles", type=triangle_budget, required=True)
    parser.add_argument("--output", type=Path, help="Output GLB (default: 02-lowpoly.glb beside input)")
    args = parser.parse_args()
    source = args.mesh.expanduser().resolve()
    output = (args.output or source.with_name("02-lowpoly.glb")).expanduser().resolve()
    if not source.is_file():
        parser.error(f"Input mesh not found: {source}")
    if output.suffix.lower() != ".glb":
        parser.error("--output must have a .glb extension")
    record = output.with_suffix(".json")
    if output.exists() or record.exists():
        parser.error(f"Output or metadata already exists: {output}; choose a new --output")
    import trimesh

    mesh = trimesh.load(source, force="mesh")
    start = time.monotonic()
    reduced, stats = reduce_mesh(mesh, args.target_triangles)
    stats["elapsed_seconds"] = round(time.monotonic() - start, 3)
    stats["source"] = str(source)
    with source.open("rb") as stream:
        stats["source_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    reduced.export(output)
    record.write_text(json.dumps(stats, indent=2) + "\n")
    print(f"{stats['input_triangles']:,} -> {stats['output_triangles']:,} triangles: {output}")


if __name__ == "__main__":
    main()
