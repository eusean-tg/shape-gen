"""Descriptive HY-Motion measurements. NumPy only; no model or Blender dependency."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

VERSION = '1.0.1'
SCHEMA_VERSION = '1.0.0'


def spans(mask, fps):
    """Consecutive true interval runs as zero-based sample-boundary pairs."""
    changes = np.diff(np.r_[False, mask, False].astype(int))
    return [{'start_frame': int(a), 'end_frame': int(b), 'start_seconds': a / fps,
             'end_seconds': b / fps, 'duration_seconds': (b - a) / fps}
            for a, b in zip(np.flatnonzero(changes == 1), np.flatnonzero(changes == -1))]


def angles(a, b):
    cosine = (np.sum(a * b, axis=(-2, -1)) - 1) / 2
    return np.arccos(np.clip(cosine, -1, 1))


def world_joints(rotations, root, rest, parents):
    """FK from rest offsets. Upstream keypoints3d omit transl; do not use them here."""
    count = rotations.shape[1]
    if rest.shape[0] < count or parents.shape[0] < count:
        raise ValueError('Rest skeleton is smaller than the animated body skeleton')
    positions = np.empty((len(root), count, 3))
    global_rotations = np.empty_like(rotations)
    for i in range(count):
        parent = int(parents[i])
        if i == 0 and parent == -1:
            positions[:, i] = root + rest[i]
            global_rotations[:, i] = rotations[:, i]
        elif 0 <= parent < i:
            positions[:, i] = positions[:, parent] + np.einsum(
                'tij,j->ti', global_rotations[:, parent], rest[i] - rest[parent])
            global_rotations[:, i] = global_rotations[:, parent] @ rotations[:, i]
        else:
            raise ValueError('Expected one root at joint zero and topologically ordered parents')
    return positions


def repeating_candidates(rotations, root, velocity, speed, fps, stationary_threshold):
    """Rank endpoint/nearby-pose matches; exclude still poses and stop transitions."""
    found = []
    first_lag, last_lag = max(4, int(np.ceil(.5 * fps))), int(2 * fps)
    for lag in range(first_lag, min(last_lag, len(root) - 1) + 1):
        endpoint = np.sqrt(np.mean(angles(rotations[:-lag], rotations[lag:]) ** 2, axis=1))
        for start in np.flatnonzero(endpoint <= .45):
            start, end = int(start), int(start + lag)
            excursion = float(np.sqrt(np.mean(angles(rotations[start:end + 1], rotations[start]) ** 2)))
            if excursion < .10:
                continue
            moving_fraction = float(np.mean(speed[start:end] > stationary_threshold))
            mean_speed = float(np.mean(speed[start:end]))
            # Don't suggest crossing from travel to a stop as a locomotion cycle.
            if moving_fraction < .8 and mean_speed > stationary_threshold:
                continue
            offsets = [k for k in range(-2, 3) if start + k >= 0 and end + k < len(root)]
            window_error = float(np.sqrt(np.mean(angles(rotations[np.array(offsets) + start],
                                                          rotations[np.array(offsets) + end]) ** 2)))
            v_start = velocity[start:min(start + 3, len(velocity))].mean(0)
            v_end = velocity[max(0, end - 3):end].mean(0)
            velocity_error = float(np.linalg.norm(v_end - v_start))
            score = float(endpoint[start] + .5 * window_error + .1 * min(velocity_error, 5))
            next_error = None
            if end + lag < len(root):
                next_error = float(np.sqrt(np.mean(angles(rotations[start:end + 1],
                                                         rotations[end:end + lag + 1]) ** 2)))
            found.append({'start_frame': start, 'end_frame': end,
                          'start_seconds': start / fps, 'end_seconds': end / fps,
                          'duration_seconds': lag / fps,
                          'root_motion': 'traveling' if mean_speed > stationary_threshold else 'near-stationary',
                          'mean_horizontal_speed_source_units_per_second': mean_speed,
                          'moving_interval_fraction': moving_fraction,
                          'root_displacement_xyz': (root[end] - root[start]).tolist(),
                          'pose_endpoint_rms_radians': float(endpoint[start]),
                          'pose_neighborhood_rms_radians': window_error,
                          'pose_excursion_rms_radians': excursion,
                          'root_velocity_endpoint_difference_source_units_per_second': velocity_error,
                          'next_cycle_pose_rms_radians': next_error,
                          'ranking_score': score})
    selected = []
    # Keep traveling options even when the stationary tail has easier pose matches.
    for category in ['traveling', 'near-stationary']:
        group = []
        for candidate in sorted((x for x in found if x['root_motion'] == category), key=lambda x: x['ranking_score']):
            if any(abs(candidate['start_frame'] - other['start_frame']) < fps * .2 and
                   abs(candidate['end_frame'] - other['end_frame']) < fps * .2 for other in group):
                continue
            group.append(candidate)
            if len(group) == 5:
                break
        selected.extend(group)
    return selected


def diagnose(data, fps=30, stationary_threshold=.15):
    if not np.isfinite(fps) or fps <= 0 or not np.isfinite(stationary_threshold) or stationary_threshold < 0:
        raise ValueError('Invalid fps or stationary threshold')
    translation = np.asarray(data['transl'], dtype=np.float64)
    rotation_data = np.asarray(data['rotations'], dtype=np.float64)
    if translation.ndim != 3 or translation.shape[0] != 1 or translation.shape[2] != 3:
        raise ValueError('Expected transl shaped (1, frames, 3)')
    root = translation[0]
    if len(root) < 4 or rotation_data.shape != (1, len(root), 22, 3, 3):
        raise ValueError('Expected at least four frames and 22 rotation joints')
    rotations = rotation_data[0]
    if not np.isfinite(root).all() or not np.isfinite(rotations).all():
        raise ValueError('Nonfinite motion')
    if np.max(np.abs(rotations @ rotations.swapaxes(-1, -2) - np.eye(3))) > 1e-4 or \
            np.max(np.abs(np.linalg.det(rotations) - 1)) > 1e-4:
        raise ValueError('Invalid rotation matrices')
    delta = np.diff(root, axis=0)
    velocity = delta[:, [0, 2]] * fps
    speed = np.linalg.norm(velocity, axis=1)
    smoothed = np.convolve(np.pad(speed, (2, 2), mode='edge'), np.ones(5) / 5, mode='valid')
    stationary = smoothed <= stationary_threshold
    runs = spans(stationary, fps)
    tail = runs[-1] if runs and runs[-1]['end_frame'] == len(root) - 1 else {
        'start_frame': len(root) - 1, 'end_frame': len(root) - 1,
        'start_seconds': (len(root) - 1) / fps, 'end_seconds': (len(root) - 1) / fps, 'duration_seconds': 0.0}
    rest, parents = np.asarray(data['rest_joints']), np.asarray(data['parents'])
    if rest.ndim != 2 or rest.shape[1] != 3 or not np.isfinite(rest).all():
        raise ValueError('Invalid rest joints')
    joints = world_joints(rotations, root, rest, parents)
    names = [str(n) for n in data['joint_names']]
    contacts = {'status': 'unavailable', 'reason': 'L_Foot and R_Foot body joint names required'}
    if all(name in names[:22] for name in ['L_Foot', 'R_Foot']):
        feet = joints[:, [names.index('L_Foot'), names.index('R_Foot')]]
        floor = float(np.min(feet[:, :, 1]))
        feet_speed = np.linalg.norm(np.diff(feet, axis=0), axis=2) * fps
        height = np.maximum(feet[:-1, :, 1], feet[1:, :, 1]) - floor
        contacts = {'status': 'estimated', 'floor_reference_y': floor,
                    'method': 'Forward kinematics from rest skeleton + rotations + transl; low toe-joint height and low 3D interval speed.',
                    'height_threshold_source_units': .06, 'speed_threshold_source_units_per_second': .25,
                    'limitations': 'Toe joints are not the sole surface. Floor is minimum observed toe-joint height; no terrain, shoe geometry or contact solver. Not ground truth.',
                    'feet': {side: {'interval_mask': ((height[:, i] <= .06) & (feet_speed[:, i] <= .25)).tolist(),
                                    'spans': spans((height[:, i] <= .06) & (feet_speed[:, i] <= .25), fps)}
                             for i, side in enumerate(['left', 'right'])}}
    candidates = repeating_candidates(rotations, root, velocity, smoothed, fps, stationary_threshold)
    return {
        'schema_version': SCHEMA_VERSION, 'diagnostic_version': VERSION, 'status': 'measured',
        'visual_acceptance': 'pending', 'fps': fps, 'frames': len(root),
        'sample_span_seconds': (len(root) - 1) / fps,
        'coordinates': 'HY-Motion source Y-up, +Z forward; horizontal plane XZ',
        'units': 'Source model units. Speeds become m/s only if one source unit is interpreted as one metre; target rig scale and runtime playback can change them.',
        'prompt_speed_is_constraint': False,
        'frame_convention': 'Zero-based samples; end_frame is the inclusive endpoint boundary. Candidate period = (end-start)/fps. Blender retarget frames are sample indices + 1.',
        'root': {'start_xyz': root[0].tolist(), 'end_xyz': root[-1].tolist(),
                 'displacement_xyz': (root[-1] - root[0]).tolist(),
                 'horizontal_net_displacement_source_units': float(np.linalg.norm((root[-1] - root[0])[[0, 2]])),
                 'horizontal_path_length_source_units': float(speed.sum() / fps),
                 'path_length_3d_source_units': float(np.linalg.norm(delta, axis=1).sum()),
                 'horizontal_speed': {'mean': float(speed.mean()), 'median': float(np.median(speed)),
                                      'min': float(speed.min()), 'max': float(speed.max()), 'p95': float(np.percentile(speed, 95)),
                                      'units': 'source units per second'}},
        'speed_over_time': {'interval_start_seconds': (np.arange(len(speed)) / fps).tolist(),
                            'interval_end_seconds': (np.arange(1, len(root)) / fps).tolist(),
                            'horizontal_source_units_per_second': speed.tolist(),
                            'smoothed_horizontal_source_units_per_second': smoothed.tolist(),
                            'smoothing': 'Centered five-interval moving mean, edge padding; stationary/traveling thresholds and candidate mean speed/moving-interval fraction. Root summary statistics use raw speed.'},
        'root_stationary': {'threshold_source_units_per_second': stationary_threshold,
                            'method': 'Contiguous smoothed horizontal-root-speed intervals at/below threshold. Does not imply the limbs are still.',
                            'spans': runs, 'tail': tail,
                            'traveling_spans': spans(~stationary, fps)},
        'contact_estimates': contacts,
        'repetition_search': {'status': 'candidates' if candidates else 'no_candidates',
                              'period_range_seconds': [.5, 2.0], 'maximum_candidates_per_root_motion': 5,
                              'method': 'Same-joint local-rotation endpoint RMS <= .45 rad; pose excursion >= .10 rad; nearby pose matching and root-velocity mismatch ranking. Traveling spans require >=80% moving intervals.',
                              'ranking': 'Lower is better: endpoint RMS + 0.5*neighborhood RMS + 0.1*min(root-velocity mismatch,5). Heuristic, not confidence.',
                              'limitations': 'Endpoint similarity is not proof of periodic motion. Review candidates before cropping; phase/contact, seam blending and exact runtime speed need local cleanup.',
                              'candidates': candidates},
    }


def diagnose_file(source, fps=30, stationary_threshold=.15):
    source = Path(source)
    with np.load(source, allow_pickle=False) as archive:
        report = diagnose(archive, fps, stationary_threshold)
    report['source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    report['analyzer_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('motion', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fps', type=float, default=30)
    parser.add_argument('--stationary-threshold', type=float, default=.15)
    args = parser.parse_args()
    report = diagnose_file(args.motion, args.fps, args.stationary_threshold)
    with args.output.open('x') as file:
        json.dump(report, file, indent=2, allow_nan=False)
        file.write('\n')
    print(json.dumps({'status': report['status'], 'root': report['root'],
                      'stationary_tail': report['root_stationary']['tail'],
                      'repeating_candidates': report['repetition_search']['candidates']}, indent=2))
