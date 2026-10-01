---
title: "Motion diagnostics"
summary: "Definitions and limits of root travel, speed, stationary tails, repeats and estimated contacts."
kind: "reference"
status: "current"
topics: ["motion", "diagnostics"]
read_when: "Select a motion crop or interpret numerical motion diagnostics."
---
# Motion diagnostics

API 0.4.2; diagnostic version 1.0.1, schema version 1.0.0. These are descriptive measurements of
raw HY-Motion data, separate from numerical validation and visual acceptance.
Diagnostic 1.0.1 corrects the smoothing description only; calculations and schema
are unchanged. Existing published 1.0.0 reports remain immutable.

## Retrieve

- New `hymotion` and legacy `hymotion-retarget` jobs publish
  `motion-diagnostics.json` in their motion output directory. Download through the
  ordinary artifact manifest to get its immutable SHA-256.
- `GET /jobs/{id}/motion-diagnostics` returns `{job_id, delivery, scope, diagnostics}`.
  All routes require the usual bearer header. The job must have succeeded.
- For older jobs, including `35bce30559134b0eace24d4f5626649a`, that endpoint computes
  the report on demand from the stored raw motion using the current analyzer.
  It does not regenerate motion, run Blender or alter the original artifact set.
  Save the response if pinning a historical analysis: a future analyzer version
  may change an on-demand result. The report includes analyzer version/hash and
  source NPZ hash. New jobs serve their published report instead.
- The downloadable helper bundle includes `scripts/motion_diagnostics.py` for local
  analysis with NumPy, with optional `--fps` and `--stationary-threshold` settings.
  Changing a local fps interprets the samples at that playback rate; it does not
  regenerate or resample the motion. API reports always use the current runner's 30 fps.

## Units and root motion

Axes are HY-Motion source **Y-up, +Z forward**, horizontal plane XZ. Reported travel
uses the `transl` array. Distances are **source model units**; speeds are source
units/second. Interpreting one source unit as one metre gives m/s, but target rig
proportions, retarget scale and playback speed can change the runtime value.

`root` includes signed XYZ displacement, horizontal net displacement, horizontal
path length, full 3D path length and speed statistics. Net displacement and path
length differ if the root sways, turns or retraces its path.

`speed_over_time` contains 119 intervals for a 120-sample motion: start/end times,
horizontal finite-difference speed and a centered five-interval smoothed speed.
The raw values remain available. Smoothed speed drives stationary/traveling
thresholds, candidate mean horizontal speed and candidate moving-interval fraction.
Whole-clip `root.horizontal_speed` statistics and path length use the raw series.
The five-interval window uses edge padding and can shift inferred transition times.

**A numerical speed in the prompt is not an endpoint speed constraint.** The API
does not parse a number from prose and treat it as an achieved target, and this
release introduces no speed-control parameter. Exact speed must be established
through local retargeting, stride/contact cleanup and runtime checks.

## Stationary tail

`root_stationary` lists contiguous intervals whose smoothed horizontal root speed
is at most **0.15 source units/second**. It includes the terminal run as `tail`
and the complementary `traveling_spans`. A zero-duration tail means the final
interval exceeded that threshold. This describes the root only; the character
may keep moving limbs or jog in place with a stationary root.

For the reported jogging job, this definition detects a tail from zero-based
sample **55** to **119**: **1.833–3.967 seconds**, lasting **2.133 seconds**.
Its horizontal root path length is approximately **3.226 source units** and
whole-clip average horizontal speed is **0.813 source units/second**. These are
measurements of that exact raw NPZ, not the locally corrected runtime clip.

## Candidate repeating segments

The search compares same-joint local rotations across candidate boundary pairs
0.5–2.0 seconds apart. It requires endpoint RMS angular difference <=0.45 radians
and pose excursion >=0.10 radians, then ranks pose and nearby-phase similarity
plus root-velocity mismatch. These are disclosed heuristics, not confidence scores.
Traveling candidates must have at least 80% moving intervals. Up to five traveling
and five near-stationary candidates are returned separately by `root_motion` label,
with traveling candidates listed first. A quieter stationary tail therefore does
not displace all the traveling candidates.

Each candidate reports boundaries, duration, pose/velocity mismatch, mean speed,
root displacement and—when another complete period exists—the next-period pose
RMS difference. The search can return no candidates. Repeated endpoint poses do
not establish a seamless loop; mirrored gait phases, contacts and motion transitions
still need review. A near-stationary match is not evidence of traveling locomotion.

Frame indices are zero-based. `end_frame` is the inclusive endpoint **boundary**;
the proposed period is `(end-start)/fps`. Blender's supplied retargeter uses
sample index + 1. Decide whether to keep a duplicated endpoint when constructing
your local loop; the API does not crop or modify the returned motion.

In the reported jogging job, one early candidate is samples 10–37 (0.333–1.233 s),
with a 0.9-second boundary period. Treat it as a place to inspect, not an approved
crop or a promise of 1.47 m/s.

## Estimated contacts

`contact_estimates` uses forward kinematics from `rest_joints`, `parents`, the
22 body rotations and root translation. **Do not use `keypoints3d` as world-space
positions directly:** the installed upstream body model omits `transl` from those
joint outputs. The analyzer avoids that ambiguity by reconstructing the joints.

For `L_Foot` and `R_Foot`, the estimator checks a toe-joint height within 0.06
source units of the minimum observed toe height, and 3D interval speed <=0.25
source units/second. It returns interval masks and spans, explicitly labeled
**estimated**. These joints are not the mesh soles. Terrain, shoe geometry,
occlusion and physical contact are not modeled. Missing foot names yield
`unavailable`; no contact labels are fabricated.

These diagnostics never promote the candidate to visual acceptance, enforce a
requested speed, lock feet, fit a loop, or change a successful validation into a
quality guarantee.
