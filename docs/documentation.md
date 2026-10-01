---
title: "Documentation conventions"
summary: "Frontmatter schema, index rebuild/check commands and published-copy policy."
kind: "reference"
status: "current"
topics: ["documentation", "maintenance"]
read_when: "Add, split or update project documentation."
---
# Documentation conventions

Start with [INDEX.md](INDEX.md) to choose a relevant topic before reading long
files. The README is the product entry point; `docs/` holds installation, reference,
operations and research. Historical reports are evidence for particular runs and
must not silently become current defaults.

## Frontmatter

Every Markdown file in `docs/` has these fields. Use JSON-quoted strings and arrays,
a valid subset of YAML that the index builder can parse without dependencies:

```yaml
---
title: "Short descriptive title"
summary: "What this document contains, including its useful limits."
kind: "reference"
status: "current"
topics: ["api", "animation"]
read_when: "You need the motion output coordinate and array contract."
---
```

- `kind`: `setup`, `reference`, `operations`, `research` or `history`.
- `status`: `current`, `experimental` or `historical`. A dated experiment can still
  be useful while marked historical; the label prevents treating it as current setup.
- `topics`: short searchable tags, preferably reuse existing terms.
- `summary`: factual contents, not a generic “documentation for this feature.”
- `read_when`: the reader's question/task that this file resolves.

All fields are required. Keep values on one line; multiline YAML, unquoted strings,
unknown fields and duplicate keys are rejected. `INDEX.md` is generated and has its
own frontmatter, but is excluded from its source scan to avoid self-indexing.

## Updating docs

1. Edit the focused guide. Split a file when topics have distinct readers or tasks;
   keep an overview linking them. Update metadata when scope changes.
2. Run `python3 scripts/build_docs_index.py` from the repository root.
3. Run `python3 scripts/build_docs_index.py --check`. This also rejects missing or
   invalid frontmatter anywhere under `docs/`, including new subdirectories.
4. Check relative links and the commands affected by your change. Frontmatter
   validity does not verify installation or technical claims.

The index is deterministic and omits timestamps, so unchanged docs do not produce
spurious diffs. `--docs-dir PATH` supports an alternate documentation tree.

## Scope and published copies

The index covers all maintained Markdown under `docs/`, including historical and
research chapters. The README links to [INDEX.md](INDEX.md), which links to
these conventions. Generated per-run reports in `assets/`
and distribution snapshots in `exports/` remain separate evidence/artifacts;
relevant guides link to them. Third-party repositories and installed package docs
are outside this project's documentation scope.

The API serves selected source guides directly as Markdown. Their frontmatter is
included, and changes appear on the next request. Relative source links outside
the four served guide endpoints need a repository checkout; `/docs/` is not a
catch-all file server. Keep repository-only installation paths as plain code text
in served guides, rather than links that appear to resolve on the API.

Refresh mutable `exports/shape-gen-api/` handoff copies and **all** checksum entries
with `python3 scripts/sync_api_handoff.py`; verify them using
`python3 scripts/sync_api_handoff.py --check`. The export README is maintained in
place; the script copies the four guides and client from their canonical sources.
Run this after editing either the source guides/client or the export README. Published `exports/blender-helpers/<version>/` bundles
are immutable and included in Git with their ZIPs: build a new version to publish
changed guides and hashes. Test packaging/storage with
`.venv-api/bin/python -m pytest -q tests/test_release_integrity.py`.

When documenting an experiment, preserve date, inputs, model revisions, measurements,
visual findings and limitations. A successful job or watertight mesh does not
establish art quality, deformation quality or suitability for a particular game.
