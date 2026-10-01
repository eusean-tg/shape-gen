"""Create local inference configs with explicit model paths; upstream is untouched."""
from pathlib import Path
import argparse
import yaml

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT/'third_party/UniRig'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--asset-dir',type=Path,default=ROOT/'assets/peasant-unirig')
parser.add_argument('--config-dir',type=Path,default=ROOT/'config/unirig')
args=parser.parse_args()
OUT=args.config_dir.resolve()
ASSET=args.asset_dir.resolve()
OUT.mkdir(parents=True,exist_ok=True)
def read(name):return yaml.safe_load((REPO/'configs'/name).read_text())
def write(name,data):
    path=OUT/(name+'.yaml');path.write_text(yaml.safe_dump(data,sort_keys=False));return str(path)
data=read('data/quick_inference.yaml')
data['predict_dataset_config']['num_workers']=0
data['predict_dataset_config']['datapath_config']={'input_dataset_dir':str(ASSET/'data'),
    'use_prob':False,'data_path':{'inference':[[str(ASSET/'data/inference.txt'),1.0]]}}
data_path=write('data',data)
for stage,task_name,model_name,transform_name,checkpoint in [
    ('skeleton','quick_inference_skeleton_articulationxl_ar_256','unirig_ar_350m_1024_81920_float32','inference_ar_transform','skeleton/articulation-xl_quantization_256/model.ckpt'),
    ('skin','quick_inference_unirig_skin','unirig_skin','inference_skin_transform','skin/articulation-xl/model.ckpt')]:
    task=read('task/'+task_name+'.yaml')
    task['resume_from_checkpoint']=str(ROOT/'models/unirig'/checkpoint)
    task['experiment_name']='peasant_local_'+stage
    task['components']['data']=data_path
    task['trainer']['enable_checkpointing']=False
    task['trainer']['enable_model_summary']=False
    task['trainer']['enable_progress_bar']=False
    task['trainer']['default_root_dir']=str(ASSET/'logs')
    model=read('model/'+model_name+'.yaml')
    transform=read('transform/'+transform_name+'.yaml')
    if stage=='skeleton':
        model['llm']['pretrained_model_name_or_path']=str(ROOT/'models/unirig/opt-350m')
        system=read('system/ar_inference_articulationxl.yaml')
        # Fewer search beams reduce KV-cache VRAM; keep trained model and sampling density.
        system['generate_kwargs']['num_beams']=3
        task['components']['system']=write('skeleton-system',system)
    else:
        # CPU voxelization avoids creating another OpenGL GPU context.
        transform['predict_transform_config']['vertex_group_config']['kwargs']['voxel_skin']['backend']='open3d'
    task['components']['model']=write(stage+'-model',model)
    task['components']['transform']=write(stage+'-transform',transform)
    task['writer']['output_dir']=None
    task['writer']['export_fbx']=None
    task['writer']['export_obj']=None
    write(stage,task)
print(OUT)
