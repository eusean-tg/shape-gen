---
title: "Next geometry experiments after TRELLIS.2"
summary: "Pre-DeepMesh research options with a later note that geometry experiments were paused."
kind: "research"
status: "historical"
topics: ["geometry", "research", "backlog"]
read_when: "Recover considered options; this is not authorization for new experiments."
---
# Next geometry experiments after TRELLIS.2

**Follow-up:** DeepMesh was subsequently tested on Makima and the simpler teal
peasant. It ran on the 3050, but neither candidate justified replacing the
existing BPT workflow. [Completed experiment and comparison](deepmesh-2026-09-19.md).
The user prefers to pause this research if DeepMesh is not a useful improvement;
do not treat the proposed order below as authorization for more model experiments.
The remaining text records the research assessment before that test.

Checked 2026-09-19. Research and access checks only; no new model installed or
inference run in this pass. See [the completed TRELLIS experiment](makima-trellis-2026-09-19.md).

## Assessment

We have not exhausted the workflow. The previous experiments tested a substantial
set of whole-character Hunyuan/BPT parameters and established that TRELLIS.2
can run on this machine. They did not establish that BPT is the only viable
reconstruction stage, that every dense mesh needs a generative reconstruction,
or that roughly 2k triangles is a suitable final budget for this character.

Preserve Hunyuan 2mv as a source in the next comparison. Changing the reducer
does not require giving up four-view shape conditioning.

## 1. Replace BPT while holding the dense source fixed

**DeepMesh is the most accessible new model test.** Its official implementation
accepts surface points with normals, and the released model is described as
0.5B. The checkpoint repository is public and ungated, labelled MIT. It has
not been run here, and its character fidelity and RTX 3050 memory use remain
unmeasured. Its autoregressive design is related to existing mesh-generation
work, so this is a candidate rather than evidence of an inherent quality leap.
[Official implementation](https://github.com/zhaorw02/DeepMesh),
[weights](https://huggingface.co/zzzrw/DeepMesh).

HF metadata observed: revision `a19a1bff1018eed1cf3506298f8da8d27ae3f678`,
`pytorch_model.bin` 3,632,680,698 bytes. Download size is not peak VRAM use.

**Meta MeshFlow is another technically relevant research candidate.** Its
released pipeline consumes geometry and optionally a reference image; its
continuous output coordinates avoid discrete coordinate quantization. The
implementation documents an approximate vertex-count control when enabled by
the checkpoint configuration. It still needs source geometry, and the geometry
conditioning itself is coarse; continuous output coordinates are not a detail
guarantee. [Official code](https://github.com/facebookresearch/meshflow),
[method and released-model FAQ](https://mesh-flow.github.io/).

However, its weights are manually gated and labelled
`fair-noncommercial-research-license`. An authenticated metadata request for
`meshflow/config.yaml` returned `GatedRepoError` with the current HF login.
DINOv3 approval does not grant access to this separate repository. Do not
present it as an immediately available unrestricted game-asset pipeline.
[Official model card](https://huggingface.co/facebook/meshflow).

## 2. Allocate geometry by region instead of reconstructing the whole body

Engineering hypothesis, not a tested improvement: treat head/hair, torso and
limbs separately, protect useful boundaries, and compare region-aware geometric
reduction against the whole-character neural reconstruction. A head processed
in its own normalized coordinate frame gets finer world-space precision than
the same head inside a full-height character frame. This does not remove BPT's
learned prior, guarantee good cropped-part outputs, or solve assembly seams.

An initial controlled test should keep the dense source fixed and compare
roughly 2.5k, 5k and 8k **total** triangles, with extra allocation around the
face, hair silhouette, collar and deformation regions. The exact counts are
experimental budgets, not a new user requirement. Retain a conventional
reduction control. Assess topology, silhouette and closeups before texturing;
an attractive clay render alone is not a rigging check.

## 3. Test experimental TRELLIS.2 multi-image conditioning

The upstream repository has an open community contribution adding per-view
sampling and prediction averaging. This is an inference-time adaptation of the
single-image model, not a dedicated multiview-trained checkpoint. The discussion
also reports thickness/proportion deviations. It provides an implementation to
inspect and test against our four saved references, not a quality guarantee.
[TRELLIS.2 PR #104](https://github.com/microsoft/TRELLIS.2/pull/104).

Our earlier TRELLIS.2 experiment used one front image. Its results therefore do
not settle whether this adaptation could preserve the rear braid. The original
TRELLIS four-image experiment is a different model and cannot settle that either.

## Recommended order

1. Same existing HY 2mv dense source → DeepMesh, with measured GPU use and saved
   conditioning. Compare to the existing BPT and a region-aware reduction control.
2. Compare actual budgets and inspect face, braid gap, knees, hands and topology.
   If useful detail survives at 5–8k but not 2.5k, record that tradeoff explicitly.
3. Separately evaluate TRELLIS.2 multi-image conditioning, judging dense geometry
   before running another reducer. Do not change generator and reducer together
   and then attribute an improvement to one of them.

Further BPT seed/top-k/top-p searches remain possible, but the coordinate and
conditioning limits already measured make them lower priority than these tests.
