"""Author sleeve/hand weights using disconnected below-armpit topology.

Run with the project Python. Leaves the learned UniRig result untouched.
This is an asset-specific correction, not a general automatic rigging solver.
"""
import json
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

BASE = Path(__file__).resolve().parents[1] / 'assets/teal-peasant'
data = dict(np.load(BASE / 'rig/rig-data.npz'))
v, f, original = data['vertices'], data['faces'], data['weights']
w = original.copy()
names = data['names'].tolist()
edges = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
edges = edges[(v[edges, 2] < 1.34).all(axis=1)]
graph = coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])), shape=(len(v), len(v)))
_, components = connected_components(graph, directed=False)

def smooth(x):
    x = np.clip(x, 0, 1)
    return x*x*(3-2*x)

report = {}
for side, sign in [('L', 1), ('R', -1)]:
    seed = np.argmin(np.linalg.norm(v - [sign*.30, .03, .9], axis=1))
    ids = np.flatnonzero(components == components[seed])
    assert len(ids) == 84 and np.all(v[ids, 0]*sign > .16)
    upper, fore, hand = [names.index(n+'.'+side) for n in ['upper_arm', 'forearm', 'hand']]
    elbow, wrist = data['joints'][fore], data['joints'][hand]
    axis = (elbow - wrist) / np.linalg.norm(elbow - wrist)
    # One coherent weight band around each joint, independent of surface side.
    upper_weight = smooth(((v[ids]-elbow) @ axis + .070) / .140)
    hand_weight = 1-smooth(((v[ids]-wrist) @ axis + .045) / .090)
    w[ids] = 0
    w[ids, upper] = upper_weight
    w[ids, hand] = hand_weight
    w[ids, fore] = 1-upper_weight-hand_weight
    unrelated = [i for i in range(len(names)) if i not in [upper, fore, hand]]
    report[side] = {'vertices': ids.tolist(),
                   'old_max_unrelated_weight': float(original[ids][:, unrelated].sum(1).max()),
                   'new_max_unrelated_weight': float(w[ids][:, unrelated].sum(1).max())}

changed = np.flatnonzero(np.any(w != original, axis=1))
assert np.min(w) >= 0 and np.max(abs(w.sum(1)-1)) < 2e-7
data['weights'] = w
np.savez_compressed(BASE/'rig/refined-rig-data.npz', **data)
report['changed_vertices'] = changed.tolist()
report['method'] = 'Topology-isolated lower arms; smooth upper-arm/forearm/hand bands. Other vertex weights unchanged.'
(BASE/'rig/arm-weight-repair.json').write_text(json.dumps(report, indent=2)+'\n')
print('Refined', len(changed), 'vertices; raw UniRig weights preserved.')
