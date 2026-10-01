from shape_api.model_jobs import commands
from shape_api.operations import MODELS
from shape_api.server import ROOT


def test_lato_normal_stage_default_opt_out_and_old_requests(tmp_path):
    parameters = MODELS['lato2-retopology']().model_dump()
    assert parameters['recalculate_normals'] is True
    request = {'operation': 'lato2-retopology', 'parameters': parameters}
    inputs = {'mesh': tmp_path / 'mesh.glb'}
    stages, primary, reports, _ = commands(ROOT, request, tmp_path, inputs)
    assert [name for name, _ in stages] == ['lato2-retopology', 'recalculate-normals']
    assert stages[1][1][0] == ROOT / '.venv/bin/python'
    assert primary == tmp_path / 'result/02-lato2.glb'
    assert 'normal-recalculation.json' in reports
    parameters['recalculate_normals'] = False
    stages, _, reports, _ = commands(ROOT, request, tmp_path, inputs)
    assert len(stages) == 1 and 'normal-recalculation.json' not in reports
    # Requests stored before 0.4.1 retain their explicitly recorded behavior.
    del parameters['recalculate_normals']
    stages, _, reports, _ = commands(ROOT, request, tmp_path, inputs)
    assert len(stages) == 1
