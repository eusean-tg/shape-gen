#!/usr/bin/env python3
"""Build Paint's native extensions locally, without changing the system CUDA driver."""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / ".toolchain"
CUDA = BUILD / "cuda-12.6"
REDIST = "https://developer.download.nvidia.com/compute/cuda/redist/"
ARCHIVES = [
    ("cuda_nvcc/linux-x86_64/cuda_nvcc-linux-x86_64-12.6.85-archive.tar.xz",
     "840deff234d9bef20d6856439c49881cb4f29423b214f9ecd2fa59b7ac323817"),
    ("cuda_cudart/linux-x86_64/cuda_cudart-linux-x86_64-12.6.77-archive.tar.xz",
     "f74689258a60fd9c5bdfa7679458527a55e22442691ba678dcfaeffbf4391ef9"),
    ("cuda_cccl/linux-x86_64/cuda_cccl-linux-x86_64-12.6.77-archive.tar.xz",
     "9c3145ef01f73e50c0f5fcf923f0899c847f487c529817daa8f8b1a3ecf20925"),
]


def download(url, filename, expected):
    path = BUILD / "downloads" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        print(f"Downloading {filename}", flush=True)
        partial = path.with_suffix(path.suffix + ".partial")
        urllib.request.urlretrieve(url, partial)
        partial.rename(path)
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected:
        raise RuntimeError(f"Checksum mismatch: {path}")
    return path


def main():
    os.chdir(ROOT)
    # Bootstrap Python build dependencies before building the two local packages.
    subprocess.run([
        "uv", "sync", "--locked", "--no-install-package", "custom-rasterizer",
        "--no-install-package", "mesh-processor",
    ], check=True)
    mamba = BUILD / "bin/micromamba"
    if not mamba.exists():
        archive = download(
            "https://micro.mamba.pm/api/micromamba/linux-64/2.9.0",
            "micromamba.tar.bz2",
            "8761c382127e6363bd9e0a2451aa3ef90d071a79133f736e2f759a3bf13040dd",
        )
        with tarfile.open(archive) as tar:
            tar.extract("bin/micromamba", BUILD, filter="data")
    env = os.environ.copy()
    env["MAMBA_ROOT_PREFIX"] = str(BUILD / "mamba")
    if not (BUILD / "host/conda-meta/history").exists():
        subprocess.run([
            str(mamba), "create", "-y", "-p", str(BUILD / "host"),
            "--file", str(ROOT / "config/paint-host-toolchain.txt"),
        ], check=True, env=env)
    for relative, checksum in ARCHIVES:
        archive = download(REDIST + relative, Path(relative).name, checksum)
        with tarfile.open(archive) as tar:
            tar.extractall(BUILD / "unpack", filter="data")
            source = BUILD / "unpack" / tar.getnames()[0].split("/")[0]
        shutil.copytree(source, CUDA, dirs_exist_ok=True)
    # PyTorch's NVIDIA wheels already supply the other CUDA development headers.
    for include in (ROOT / ".venv/lib/python3.11/site-packages/nvidia").glob("*/include"):
        shutil.copytree(include, CUDA / "include", dirs_exist_ok=True)
    env["CUDA_HOME"] = str(CUDA)
    env.setdefault("TORCH_CUDA_ARCH_LIST", "8.6")
    env.setdefault("MAX_JOBS", "4")
    subprocess.run([
        str(mamba), "run", "-p", str(BUILD / "host"), "uv", "sync", "--locked",
    ], check=True, env=env)
    subprocess.run([
        "uv", "run", "--locked", "python", "-c",
        "import torch, custom_rasterizer, mesh_processor; "
        "from hy3dgen.texgen import Hunyuan3DPaintPipeline; print('Paint imports OK')",
    ], check=True)


if __name__ == "__main__":
    main()
