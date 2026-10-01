---
title: "Git repository and large-file policy"
summary: "Git inclusion rules, ignored weights/runtime data and separate asset backups."
kind: "operations"
status: "current"
topics: ["git", "storage", "backup"]
read_when: "Prepare a commit, move to a fresh clone or decide what to back up."
---
# Git repository and large-file policy

Initialized locally on 2026-09-21. This repository versions the implementation
and its documentation; it is not a backup of all generated assets on this machine.

## What belongs in Git

- Python runners, API implementation, tests, configuration and dependency locks.
- Preview/React source, experiment scripts and small JSON/text reports under
  `assets/`; source and metadata under `exports/`.
- Small immutable `exports/blender-helpers/<version>/bundle.zip` source/doc bundles,
  together with their `manifest.json` and `release.json`. This narrow ZIP exception
  keeps helper downloads available in a fresh clone.
- Research notes and download/setup scripts. Preserve upstream licenses alongside
  any included vendor source.

## What stays outside Git

- `models/`: downloaded model weights and their local metadata/cache.
- `third_party/`: separate upstream checkouts and their build products.
- `.venv*/`, `.toolchain/`, caches and installed packages.
- `var/`: API database, uploaded inputs, job output and runtime state.
- Generated meshes (including `assets/**/*-mesh.json` and `assets/**/mesh.json`
  geometry arrays), Blender projects, textures, recordings and PDFs. Other archives
  remain ignored; only the small helper source bundles above are included.
- Auth tokens, private keys and `.env` files. The service token is managed outside
  this repository, under `~/.config/shape-gen/`.

The `.gitignore` uses source allowlists inside `assets/` and `exports/` so new
binary formats in those folders are ignored by default. Small reports can still
contain machine-specific paths, input descriptions and identifiers; this is not
an anonymized public release. JSON exclusion is filename-based, not content-aware:
name new geometry dumps `*-mesh.json` or `mesh.json`; a differently named JSON can
still contain large arrays. The release check recursively scans Git-eligible asset
JSON for dictionaries containing both a `vertices` list and a `faces` list. It does
not detect every possible geometry encoding, renamed keys or other large arrays.
Review the staged diff before publishing.

## Working with a fresh clone

A clone contains code and reports, not a ready-to-run deployment. Follow the
README and stage-specific setup scripts to obtain upstream repositories, install
isolated environments and download models under their original license terms.
The main `pyproject.toml` uses local `third_party/Hunyuan3D-2` dependencies, so
those sources must exist before syncing its environment. Some experiments also
require their saved inputs, which must be restored or regenerated separately.

Keep checkpoint revisions and hashes in setup scripts/reports when adding new
models. Do not upload tens of gigabytes of pretrained weights to this repository;
use the upstream model host. Back up irreplaceable references and accepted Blender
assets separately. Back up published helper release directories as complete units,
including their exact ZIP bytes; rebuilding an old version from changed source
does not reproduce its hash. If a published ZIP is missing, restore its exact bytes
from Git or a release backup. Use release attachments/object storage for distributable
character bundles; Git LFS can be considered later for selected authored assets
if its storage and bandwidth costs are acceptable.

## Before committing or pushing

```sh
git status --short
git add .
git diff --cached --stat
git diff --cached
```

Do not use `git add -f` for weights or generated assets. Git ignore rules do not
apply to files already tracked, and do not impose a file-size limit: review any
new large source/report files too. Committing a large file and deleting it in a
later commit leaves the original bytes in history.

Initializing Git and editing these files does not change or restart the running
API. Remote configuration and publishing are separate steps.
