"""Typed GPU-operation contracts and validated input roles."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Parameters(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    seed: int = Field(default=12345, ge=0, le=4294967295, strict=True)


class ShapeParameters(Parameters):
    model: Literal['full', 'mini', 'mv'] = 'mini'
    steps: int = Field(default=50, ge=1, le=100, strict=True)
    resolution: Literal[64, 128, 192, 256] = 128
    chunks: int = Field(default=1024, ge=256, le=8192, strict=True)
    guidance: float = Field(default=5, ge=0, le=20)
    keep_background: bool = False


class BPTParameters(Parameters):
    temperature: float = Field(default=.5, gt=0, le=2)
    max_tokens: int = Field(default=10000, ge=250, le=10000, strict=True)
    encoder_device: Literal['cuda', 'cpu'] = 'cuda'


class DeepMeshParameters(Parameters):
    temperature: float = Field(default=.5, gt=0, le=2)
    max_tokens: int = Field(default=30000, ge=250, le=30000, strict=True)
    max_seconds: int = Field(default=900, ge=30, le=1000, strict=True)


class Lato2Parameters(Parameters):
    target_vertices: int = Field(default=1200, ge=200, le=5000, strict=True)
    vertex_steps: int = Field(default=24, ge=1, le=50, strict=True)
    topology_steps: int = Field(default=50, ge=1, le=100, strict=True)
    guidance: float = Field(default=3, ge=0, le=10)
    fill_quad_rings: bool = True
    recalculate_normals: bool = Field(default=True, strict=True)


class TrellisParameters(Parameters):
    steps: int = Field(default=25, ge=1, le=50, strict=True)
    mode: Literal['stochastic', 'multidiffusion'] = 'stochastic'


class Trellis2Parameters(Parameters):
    steps: int = Field(default=12, ge=1, le=50, strict=True)
    resolution: Literal[512, 1024] = 512
    remesh: bool = True
    remesh_target: int = Field(default=500000, ge=10000, le=500000, strict=True)


class PaintParameters(Parameters):
    steps: int = Field(default=30, ge=1, le=50, strict=True)
    texture_size: Literal[512, 1024, 2048] = 1024
    render_size: Literal[512, 1024] = 1024
    preserve_uvs: bool = True


class RigParameters(Parameters):
    pass


class RawMotionParameters(Parameters):
    prompt: str = Field(min_length=3, max_length=500)
    duration: Literal[4.0] = 4.0

    @field_validator('prompt')
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError('Prompt must not be blank')
        return value


MODELS = {'hunyuan-shape': ShapeParameters, 'bpt-retopology': BPTParameters,
          'deepmesh-retopology': DeepMeshParameters, 'lato2-retopology': Lato2Parameters,
          'trellis-shape': TrellisParameters, 'trellis2-shape': Trellis2Parameters,
          'hy3d-paint': PaintParameters, 'unirig': RigParameters, 'hymotion': RawMotionParameters}
ROLES = {'hunyuan-shape': {'front': 'image', 'left': 'image', 'back': 'image', 'right': 'image'},
         'trellis-shape': {'front': 'image', 'left': 'image', 'back': 'image', 'right': 'image'},
         'trellis2-shape': {'front': 'image'},
         'deepmesh-retopology': {'mesh': 'mesh'}, 'lato2-retopology': {'mesh': 'mesh'},
         'bpt-retopology': {'mesh': 'mesh'}, 'hy3d-paint': {'mesh': 'mesh', 'reference': 'image'},
         'unirig': {'mesh': 'mesh-data'}, 'hymotion': {}}
REQUIRED = {'hunyuan-shape': {'front'}, 'bpt-retopology': {'mesh'},
            'trellis-shape': {'front'}, 'trellis2-shape': {'front'},
            'deepmesh-retopology': {'mesh'}, 'lato2-retopology': {'mesh'},
            'hy3d-paint': {'mesh', 'reference'}, 'unirig': {'mesh'}, 'hymotion': set()}
DESCRIPTIONS = {
    'trellis-shape': 'Experimental original TRELLIS geometry, one or multiple foreground RGBA cutouts. Staged GPU/CPU extraction, Y-up GLB.',
    'trellis2-shape': 'Experimental TRELLIS.2 geometry, one foreground RGBA cutout. Optional demo remeshing; no texture generation.',
    'deepmesh-retopology': 'Experimental static GLB to low-poly GLB/OBJ. Requires EOS within token/time bounds; holes remain possible.',
    'lato2-retopology': 'Experimental static GLB to low-poly GLB/OBJ, with CPU normal recalculation by default and retained raw output. Target vertices is conditioning, not an exact count; topology defects remain possible.',
    'hunyuan-shape': 'PNG/JPEG reference(s) to dense untextured GLB. Full, mini or multiview.',
    'bpt-retopology': 'Static dense GLB to reconstructed low-poly GLB/OBJ. Token cap is not a triangle target.',
    'hy3d-paint': 'Static mesh plus reference image to textured GLB/atlas; Delight included.',
    'unirig': 'Numeric Blender mesh arrays to predicted joints, parents and four-influence skin weights. Bone names are generic.',
    'hymotion': 'Text to raw HY-Motion body rotations, root travel, joint names and rest joints. Retarget on the consumer.'}


def validate_inputs(operation, inputs, parameters, store):
    roles = ROLES[operation]
    if not REQUIRED[operation] <= inputs.keys() or inputs.keys() - roles.keys():
        raise ValueError(f'{operation} requires {sorted(REQUIRED[operation])}; allowed inputs: {sorted(roles)}')
    for role, asset_id in inputs.items():
        asset = store.asset(asset_id)
        if asset is None:
            raise ValueError(f'Unknown input asset for {role}: {asset_id}')
        if asset['kind'] != roles[role]:
            raise ValueError(f'Input {role} requires {roles[role]}, got {asset["kind"]}')
        if operation in {'trellis-shape', 'trellis2-shape'} and asset.get('has_foreground_alpha') is False:
            raise ValueError('TRELLIS inputs require foreground RGBA cutouts; remove backgrounds on the consumer')
    if operation == 'hunyuan-shape':
        if parameters['model'] == 'mv' and len(inputs) < 2:
            raise ValueError('Multiview requires front and at least one other view')
        if parameters['model'] != 'mv' and set(inputs) != {'front'}:
            raise ValueError('Single-view models accept only the front input')
    if operation == 'hy3d-paint' and parameters['preserve_uvs']:
        if not store.asset(inputs['mesh']).get('has_uv', False):
            raise ValueError('preserve_uvs requires a mesh with UVs; unwrap on the Mac first or explicitly disable it')
    if operation == 'trellis-shape' and parameters['mode'] == 'stochastic' and parameters['steps'] < len(inputs):
        raise ValueError('Stochastic multiview needs at least as many steps as input views')


def catalog():
    return [{'name': name, 'description': DESCRIPTIONS[name], 'input_kinds': ROLES[name],
             'required_inputs': sorted(REQUIRED[name]), 'parameters_schema': model.model_json_schema(),
             'experimental': name in EXPERIMENTAL,
             'runs_blender': False} for name, model in MODELS.items()]


EXPERIMENTAL = {'trellis-shape', 'trellis2-shape', 'deepmesh-retopology', 'lato2-retopology'}
