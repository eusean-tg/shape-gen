"""Regression checks for the reported backward idle arms and inner sleeve dye."""
import json
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'assets/teal-peasant'
OUT = BASE / 'idle-sleeve-fix'
textures = BASE / 'collar-fix/textures'
old = np.load(OUT / 'before/collar-fix/textures/surface-regions.npz')
new = np.load(textures / 'surface-regions.npz')
mesh = np.load(BASE / 'model/mesh.npz')
weights = json.loads((BASE / 'rig/arm-weight-repair.json').read_text())
region, xyz, face_ids = new['region'], new['xyz'], new['face_ids']
occupied = face_ids >= 0
mask_image = bpy.data.images.load(str(textures / 'clothing-mask.png'))
mask_image.colorspace_settings.name = 'Non-Color'
pixels = np.empty(len(mask_image.pixels), np.float32)
mask_image.pixels.foreach_get(pixels)
dye = np.rint(pixels.reshape(region.shape + (4,))[::-1, :, 0] * 255).astype(np.uint8)
report = {'sleeves': {}}

# Independently established arm vertices from the earlier deformation repair.
# Check every covered texel, including the previously missed inner surfaces.
for side in ['L', 'R']:
    arm_faces = np.isin(mesh['faces'], weights[side]['vertices']).all(axis=1)
    sleeve = occupied & arm_faces[face_ids.clip(0)] & (xyz[:, :, 2] > 1.01)
    inner = sleeve & (abs(xyz[:, :, 0]) < .21)
    assert sleeve.sum() > 10000 and inner.sum() > 1000, side
    assert np.all(region[sleeve] == 1), (side, 'Incorrect sleeve base texture')
    assert np.all(dye[sleeve] == 3), (side, 'Sleeve affected by another dye')
    report['sleeves'][side] = {'checked_texels': int(sleeve.sum()),
                             'inner_texels': int(inner.sum())}
torso = occupied & (abs(xyz[:, :, 0]) < .16) & (xyz[:, :, 2] > 1.2) & (xyz[:, :, 2] < 1.4)
assert np.all(region[torso] == 0) and np.all(dye[torso] == 1), 'Sleeve mask spilled onto torso'
changed = occupied & (region != old['region'])
assert np.all(old['region'][changed] == 0)
assert np.isin(region[changed], [1, 5]).all()
assert xyz[changed, 2].min() > 1.13 and xyz[changed, 2].max() < 1.405
report['changed_texels'] = int(changed.sum())
report['torso_texels_checked'] = int(torso.sum())
report['skin_hair_neckline_trousers_unchanged'] = True

bpy.ops.wm.open_mainfile(filepath=str(BASE / 'idle-set/final/teal-character.blend'))
arm = bpy.data.objects['Peasant rig']
arm.animation_data.action = bpy.data.actions['Idle_Breathe']
arm.animation_data.action_slot = arm.animation_data.action.slots[0]
offsets = {side: [] for side in ['L', 'R']}
for frame in np.arange(1, 241.01, .5):
    bpy.context.scene.frame_set(int(frame), subframe=float(frame % 1))
    for side in offsets:
        shoulder = arm.pose.bones['upper_arm.' + side].head
        wrist = arm.pose.bones['hand.' + side].head
        # Blender forward is -Y. Wrists should sit ahead of the shoulders.
        forward = shoulder.y - wrist.y
        assert .06 < forward < .14, (side, frame, forward)
        offsets[side].append(forward)
report['quiet_idle_wrist_ahead_of_shoulder'] = {
    side: {'min': min(values), 'max': max(values)} for side, values in offsets.items()}
(OUT / 'regression-validation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
