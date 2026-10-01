import numpy as np
import pytest

from scripts.motion_diagnostics import diagnose, world_joints


def motion(speed=0, cyclic=False):
    frames = 120
    root = np.zeros((1, frames, 3))
    root[0, :, 1] = 1
    root[0, :, 2] = np.arange(frames) / 30 * speed
    rotations = np.tile(np.eye(3), (1, frames, 22, 1, 1))
    if cyclic:
        for joint, sign in [(1, 1), (2, -1), (4, -1), (5, 1)]:
            theta = .8 * sign * np.sin(np.arange(frames) / 30 * 2 * np.pi)
            rotations[0, :, joint, 1, 1] = np.cos(theta)
            rotations[0, :, joint, 2, 2] = np.cos(theta)
            rotations[0, :, joint, 1, 2] = -np.sin(theta)
            rotations[0, :, joint, 2, 1] = np.sin(theta)
    rest = np.zeros((22, 3))
    rest[10] = [-.1, -1, 0]
    rest[11] = [.1, -1, 0]
    names = np.array(['Joint' + str(i) for i in range(22)], dtype='<U12')
    names[10], names[11] = 'L_Foot', 'R_Foot'
    return {'transl': root, 'rotations': rotations, 'rest_joints': rest,
            'parents': np.array([-1] + [0] * 21), 'joint_names': names}


def test_constant_velocity_units_and_contacts_include_translation():
    data = motion(speed=1.47)
    result = diagnose(data)
    assert result['root']['horizontal_path_length_source_units'] == pytest.approx(1.47 * 119 / 30)
    assert result['root']['horizontal_speed']['mean'] == pytest.approx(1.47)
    assert result['root_stationary']['tail']['duration_seconds'] == 0
    assert result['prompt_speed_is_constraint'] is False
    assert not result['repetition_search']['candidates']  # traveling rigid statue is not a stride
    assert not any(result['contact_estimates']['feet']['left']['interval_mask'])
    reconstructed = world_joints(data['rotations'][0], data['transl'][0], data['rest_joints'], data['parents'])
    assert np.allclose(reconstructed[:, 10, 2], data['transl'][0, :, 2])


def test_stationary_and_stop_tail_not_confused_with_repetition():
    static = diagnose(motion())
    assert static['root_stationary']['tail']['duration_seconds'] == pytest.approx(119 / 30)
    assert not static['repetition_search']['candidates']
    assert all(static['contact_estimates']['feet']['left']['interval_mask'])
    data = motion(speed=1)
    data['transl'][0, 60:, 2] = 2
    stopped = diagnose(data)
    assert abs(stopped['root_stationary']['tail']['start_frame'] - 60) <= 2
    assert stopped['root_stationary']['tail']['duration_seconds'] > 1.8


def test_cycle_candidates_and_no_world_contact_claims():
    data = motion(speed=1, cyclic=True)
    report = diagnose(data)
    candidates = report['repetition_search']['candidates']
    assert candidates and any(abs(c['duration_seconds'] - 1) < 1e-6 for c in candidates)
    assert all(c['root_motion'] == 'traveling' for c in candidates)
    assert all(c['pose_endpoint_rms_radians'] <= .45 for c in candidates)
    assert report['contact_estimates']['status'] == 'estimated'
    data['joint_names'][:] = 'unknown'
    assert diagnose(data)['contact_estimates']['status'] == 'unavailable'


def test_bad_motion_is_rejected():
    data = motion()
    data['transl'][0, 0, 0] = np.nan
    with pytest.raises(ValueError, match='Nonfinite'):
        diagnose(data)
    data = motion()
    data['parents'][3] = 3
    with pytest.raises(ValueError, match='parents'):
        diagnose(data)
    with pytest.raises(ValueError):
        diagnose(motion(), fps=0)
