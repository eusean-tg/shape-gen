"""Staged HY-Motion Lite inference: offloaded full Qwen weights, then CUDA motion."""
import argparse
import gc
import json
import os
from pathlib import Path
import resource
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('stage',choices=['encode','motion'])
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--prompt',default='A person walks forward at a relaxed pace, with natural arm swings.')
parser.add_argument('--duration',type=float,default=4.0)
parser.add_argument('--seed',type=int,default=12345)
args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
os.environ['HF_HUB_OFFLINE']='1';os.environ['DISABLE_PROMPT_ENGINEERING']='True'
os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF','expandable_segments:True')
os.environ.setdefault('OMP_NUM_THREADS','6');os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
repo=ROOT/'third_party/HY-Motion-1.0';os.chdir(repo);sys.path.insert(0,str(repo))
import numpy as np
import torch
torch.set_num_threads(6)
started=time.monotonic();torch.cuda.reset_peak_memory_stats()
report={'stage':args.stage,'prompt':args.prompt,'seed':args.seed,'duration':args.duration,'status':'running'}
try:
    if args.stage=='encode':
        if (out/'features.pt').exists():raise FileExistsError(out/'features.pt')
        from transformers import AutoModel,AutoTokenizer
        from accelerate import cpu_offload
        from hymotion.network.text_encoders import text_encoder as te
        te.SENTENCE_EMB_LAYOUT['clipl']['module_path']=str(ROOT/'models/hy-motion/clip-vit-large-patch14')
        enc=te.HYTextModel(llm_type=None,sentence_emb_type='clipl').eval().to('cuda')
        with torch.inference_mode():clip=enc.encode_sentence_emb([args.prompt]).cpu()
        enc.cpu();del enc;gc.collect();torch.cuda.empty_cache()
        qpath=ROOT/'models/hy-motion/Qwen3-8B'
        tokenizer=AutoTokenizer.from_pretrained(qpath,local_files_only=True,padding_side='right')
        print('Loading full BF16 Qwen3-8B on CPU, then offloading layers to CUDA.',flush=True)
        qwen=AutoModel.from_pretrained(qpath,local_files_only=True,torch_dtype=torch.bfloat16,
            low_cpu_mem_usage=True,attn_implementation='sdpa').eval().requires_grad_(False)
        helper=te.HYTextModel(llm_type=None,sentence_emb_type=None)
        helper.llm_type='qwen3';helper.llm_tokenizer=tokenizer;helper.llm_text_encoder=qwen
        crop=helper._compute_crop_start()
        messages=helper.apply_text_to_template(args.prompt,te.LLM_ENCODER_LAYOUT['qwen3']['template'])
        rendered=tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=False,enable_thinking=False)
        batch=tokenizer([rendered],return_length=False,return_overflowing_tokens=False,
            truncation=True,return_attention_mask=True,max_length=crop+128,padding='max_length',return_tensors='pt')
        cpu_offload(qwen,execution_device=torch.device('cuda'),offload_buffers=True)
        print('Encoding prompt with sequential offload.',flush=True)
        with torch.inference_mode():
            result=qwen(input_ids=batch['input_ids'].cuda(),attention_mask=batch['attention_mask'].cuda(),
                        use_cache=False,output_hidden_states=False)
            context=result.last_hidden_state[:,crop:crop+128].contiguous().cpu()
        features={'text_vec_raw':clip,'text_ctxt_raw':context,
                  'text_ctxt_raw_length':(batch['attention_mask'].sum(-1)-crop).clamp(min=0,max=128)}
        assert all(torch.isfinite(t).all() for t in features.values())
        assert features['text_ctxt_raw_length'].item()>0
        torch.save(features,out/'features.pt')
        report.update(crop_start=crop,context_length=int(features['text_ctxt_raw_length'].item()),
            features={k:list(v.shape) for k,v in features.items()},
            qwen='Full BF16 AutoModel backbone, sequential CPU offload, final hidden state; no LM logits or KV cache.')
    else:
        if (out/'motion.npz').exists():raise FileExistsError(out/'motion.npz')
        encoding_report=json.loads((out/'encode-run.json').read_text())
        assert encoding_report['status']=='complete' and encoding_report['prompt']==args.prompt,'Cached features belong to another prompt or failed encoding.'
        import yaml
        from hymotion.utils.loaders import load_object
        from hymotion.utils.geometry import rot6d_to_rotation_matrix
        config=yaml.safe_load((ROOT/'models/hy-motion/tencent/HY-Motion-1.0-Lite/config.yml').read_text())
        pipeline=load_object(config['train_pipeline'],config['train_pipeline_args'],
            network_module=config['network_module'],network_module_args=config['network_module_args'])
        ckpt=ROOT/'models/hy-motion/tencent/HY-Motion-1.0-Lite/latest.ckpt'
        # Official pinned checkpoint, hash verified by the download manifest.
        state=torch.load(ckpt,map_location='cpu',weights_only=False)['model_state_dict']
        mismatch=pipeline.load_state_dict(state,strict=False)
        expected_buffers={f'body_model.{k}' for k in ('v_template','j_template','skin_weights','skin_indices','parents')}
        assert set(mismatch.missing_keys)<=expected_buffers,mismatch
        assert not mismatch.unexpected_keys,mismatch
        del state;gc.collect()
        pipeline.eval().requires_grad_(False).cuda()
        features={k:v.cuda() for k,v in torch.load(out/'features.pt',weights_only=True).items()}
        print('Generating with the original 50-step Euler schedule, FP32 motion weights.',flush=True)
        with torch.inference_mode():
            motion=pipeline.generate(args.prompt,[args.seed],args.duration,cfg_scale=5.,
                use_special_game_feat=False,hidden_state_dict=features)
        arrays={k:v.float().cpu().numpy() for k,v in motion.items() if isinstance(v,torch.Tensor)}
        arrays['rotations']=rot6d_to_rotation_matrix(motion['rot6d']).numpy()
        arrays['rest_joints']=pipeline.body_model.j_template.cpu().numpy()
        arrays['parents']=pipeline.body_model.parents.cpu().numpy()
        arrays['joint_names']=np.array(pipeline.body_model.joint_names)
        assert all(np.isfinite(v).all() for v in arrays.values() if v.dtype.kind in 'fc')
        assert arrays['rotations'].shape==(1,round(args.duration*30),22,3,3)
        np.savez_compressed(out/'motion.npz',**arrays)
        report.update(frames=arrays['rotations'].shape[1],fps=30,validation_steps=50,
            learned_checkpoint_keys_exact=True,template_buffers_from_repo=mismatch.missing_keys,
            shapes={k:list(v.shape) for k,v in arrays.items()})
    torch.cuda.synchronize();report['status']='complete'
except BaseException as e:
    report.update(status='failed',error=repr(e));raise
finally:
    report.update(seconds=time.monotonic()-started,peak_cuda_allocated_mib=torch.cuda.max_memory_allocated()/2**20,
        peak_cuda_reserved_mib=torch.cuda.max_memory_reserved()/2**20,
        peak_process_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
    (out/(args.stage+'-run.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)
