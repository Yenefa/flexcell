"""Recorded-observation inference only. No ROS imports or robot commands.

PyTorch uses its torch.cuda API for both CUDA and AMD ROCm. Reports preserve
the actual backend. An unavailable GPU never falls back to CPU.
"""
import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
import traceback

from prepare_artifacts import sha256

ROOT = Path(__file__).resolve().parent


class BlockedEnvironment(RuntimeError):
    pass


def git_revision():
    try:
        return subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL, timeout=5).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def run(args, report):
    import torch

    report['versions'] = {}
    for package in ['torch', 'torchvision', 'lerobot', 'transformers',
                    'safetensors', 'numpy', 'av', 'pyarrow']:
        try:
            report['versions'][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            report['versions'][package] = None
    report['torch_hip_version'] = torch.version.hip
    report['torch_cuda_version'] = torch.version.cuda
    report['torch_gpu_available'] = torch.cuda.is_available()
    device = 'cpu'
    if args.device == 'gpu':
        if not torch.cuda.is_available():
            raise BlockedEnvironment(
                'This Python environment has no usable PyTorch CUDA/ROCm GPU. '
                'This does not prove the physical GPU is absent. '
                'Vulkan/DirectML are not implemented by this runner.')
        device = 'cuda:0'  # Also the correct PyTorch device spelling for AMD ROCm.
        props = torch.cuda.get_device_properties(0)
        report['gpu'] = {
            'backend': 'rocm' if torch.version.hip else 'cuda',
            'name': props.name,
            'total_vram_mib': props.total_memory / 2**20,
        }
        normalized_name = ''.join(c for c in props.name.lower() if c.isalnum())
        expected = ''.join(c for c in args.expected_gpu.lower() if c.isalnum())
        if expected and expected not in normalized_name:
            raise BlockedEnvironment('Unexpected GPU: ' + props.name)
        if expected == 'rx6800' and not torch.version.hip:
            raise BlockedEnvironment('RX 6800 requires an AMD PyTorch backend.')
        # gfx1030 may enumerate successfully yet lack executable kernels.
        try:
            probe = torch.ones((16, 16), device=device)
            product = probe @ probe
            torch.cuda.synchronize()
            if not bool((product == 16).all()):
                raise RuntimeError('GPU matrix multiplication returned wrong values')
            del probe, product
        except RuntimeError as exc:
            raise BlockedEnvironment('GPU kernel probe failed: ' + str(exc)) from exc
        report['gpu_kernel_probe'] = 'PASS'
    elif args.expected_gpu:
        raise ValueError('--expected-gpu is meaningful only with --device gpu')
    report['effective_device'] = device
    if args.probe_only:
        report['status'] = 'ENV_READY'
        return

    report['stage'] = 'verify_assets'
    manifest = json.loads((ROOT / 'inference-assets.json').read_text(encoding='utf-8'))
    for asset in manifest['assets']:
        path = args.assets_dir / asset['path']
        if not path.is_file() or sha256(path) != asset['sha256']:
            raise RuntimeError('Missing/mismatched pinned asset: ' + asset['path'])
    report['verified_assets'] = len(manifest['assets'])

    import av
    import numpy as np
    import pyarrow.parquet as pq
    from PIL import ImageOps
    from lerobot.configs.policies import PreTrainedConfig
    from lerobot.policies.factory import make_pre_post_processors
    from lerobot.policies.smolvla.modeling_smolvla import SmolVLAPolicy

    torch.set_num_threads(2)
    torch.manual_seed(0)
    # Explicit FP32 baseline; retain the checkpoint's 10 sampling steps.
    if args.device == 'gpu':
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.cuda.reset_peak_memory_stats()
    model = args.assets_dir / 'sources/anuaju__smolvla_openmanipulator/nested-008000'
    vlm = args.assets_dir / 'sources/SmolVLM2-500M-config'
    data = args.assets_dir / 'sources/anuaju__openmanipulator_lerobot'
    config = PreTrainedConfig.from_pretrained(model, local_files_only=True)
    config.device = device
    config.vlm_model_name = str(vlm)
    if config.load_vlm_weights or config.num_steps != 10 or config.chunk_size != 50:
        raise RuntimeError('Unexpected published configuration')
    report['stage'] = 'load_model'
    started = time.perf_counter()
    policy = SmolVLAPolicy.from_pretrained(
        model, config=config, local_files_only=True, strict=True).float().eval()
    if args.device == 'gpu':
        torch.cuda.synchronize()
    report['load_seconds'] = time.perf_counter() - started
    report['strict_weights_loaded'] = True
    report['model_parameter_devices'] = sorted({str(p.device) for p in policy.parameters()})
    report['model_parameter_dtypes'] = sorted({str(p.dtype) for p in policy.parameters()})
    if report['model_parameter_devices'] != [device]:
        raise RuntimeError('Model parameters are not entirely on the requested device')
    preprocess, postprocess = make_pre_post_processors(
        config, str(model), preprocessor_overrides={
            'device_processor': {'device': device},
            'tokenizer_processor': {'tokenizer_name': str(vlm)},
        })
    row = pq.read_table(data / 'data__chunk-000__file-000.parquet').slice(0, 1).to_pylist()[0]
    task = pq.read_table(data / 'meta__tasks.parquet').to_pylist()[0]['task']
    with av.open(str(data / 'videos__observation.images.camera1__chunk-000__file-000.mp4')) as video:
        image = ImageOps.pad(next(video.decode(video=0)).to_image().convert('RGB'), (256, 256))
    observation = {
        'observation.state': torch.tensor(row['observation.state'], dtype=torch.float32),
        'observation.images.camera1': torch.from_numpy(np.array(image).copy()).permute(2, 0, 1).float() / 255,
        'task': task,
    }
    report['task'] = task
    report['stage'] = 'inference'
    timings = []
    report['warmup_seconds'] = []
    for index in range(args.warmup + args.repeat):
        if args.device == 'gpu':
            torch.cuda.synchronize()
        started = time.perf_counter()
        with torch.inference_mode():
            batch = preprocess(observation)
            normalized = policy.predict_action_chunk(batch)
            actions = postprocess(normalized)
        if args.device == 'gpu':
            torch.cuda.synchronize()
        elapsed = time.perf_counter() - started
        tensors = {k: v for k, v in batch.items() if isinstance(v, torch.Tensor)}
        if not tensors or any(str(v.device) != device for v in tensors.values()):
            raise RuntimeError('Preprocessed inputs are not on the requested device')
        if str(normalized.device) != device:
            raise RuntimeError('Model output is not on the requested device')
        if list(actions.shape) != [1, 50, 5] or not bool(torch.isfinite(actions).all()):
            raise RuntimeError('Invalid action shape or non-finite output')
        if index < args.warmup:
            report['warmup_seconds'].append(elapsed)
        else:
            timings.append(elapsed)
        print(f'Completed {index + 1}/{args.warmup + args.repeat}: {elapsed:.4f}s', flush=True)
    report['processed_tensors'] = {
        k: {'shape': list(v.shape), 'device': str(v.device), 'dtype': str(v.dtype)}
        for k, v in tensors.items()}
    report['timing'] = {
        'scope': 'preprocess + predict_action_chunk + postprocess (CPU output), synchronized',
        'excluded': 'asset verification, model load, video decode, warmup, finite-value checks',
        'sample_count': len(timings),
        'seconds': timings,
        'p50_seconds': statistics.median(timings),
        'p95_seconds': float(np.percentile(timings, 95)) if len(timings) >= 20 else None,
    }
    report['action_shape'] = list(actions.shape)
    report['all_finite'] = True
    report['first_action'] = actions[0, 0].tolist()
    if args.device == 'gpu':
        report['peak_gpu_allocated_mib'] = torch.cuda.max_memory_allocated() / 2**20
        report['peak_gpu_reserved_mib'] = torch.cuda.max_memory_reserved() / 2**20
    report['status'] = 'PASS'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', choices=['gpu', 'cpu'], default='gpu')
    parser.add_argument('--expected-gpu', default='')
    parser.add_argument('--probe-only', action='store_true')
    parser.add_argument('--assets-dir', type=Path, default=ROOT)
    parser.add_argument('--warmup', type=int, default=3)
    parser.add_argument('--repeat', type=int, default=20)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.warmup < 0 or args.repeat < 1:
        parser.error('--warmup must be >= 0 and --repeat must be >= 1')
    args.assets_dir = args.assets_dir.resolve()
    report = {
        'task_id': 'SMOLVLA-GPU-001',
        'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'repository_commit': git_revision(),
        'python_version': sys.version,
        'platform': platform.platform(),
        'requested_device': args.device,
        'probe_only': args.probe_only,
        'checkpoint': 'anuaju/smolvla_openmanipulator',
        'revision': '660b5d90e0c62b9eec6a996c8ef0122eaa623550',
        'subfolder': 'checkpoints/008000/pretrained_model',
        'weight_sha256': 'e83f42f3fe390f52928dd63c2c5f2638eb76728ca2a91189e6ea2713166eddc6',
        'dataset_revision': '49424a5e690eee0b8c0101630f6baca0ec2864f4',
        'vlm_config_revision': '7b375e1b73b11138ff12fe22c8f2822d8fe03467',
        'sample_row_index': 0,
        'precision': 'float32',
        'seed': 0,
        'sampling_steps': 10,
        'warmup_count': args.warmup,
        'repeat_count': args.repeat,
        'robot_commands_sent': 0,
        'closed_loop_success_measured': False,
        'stage': 'environment',
    }
    try:
        run(args, report)
    except Exception as exc:
        report['status'] = 'BLOCKED_ENV' if isinstance(exc, (BlockedEnvironment, ImportError)) else 'FAIL'
        report['error'] = str(exc)
        report['exception_type'] = type(exc).__name__
        report['traceback'] = traceback.format_exc()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({'status': report['status'], 'report': str(args.report)}), flush=True)
    return 0 if report['status'] in ['PASS', 'ENV_READY'] else 2 if report['status'] == 'BLOCKED_ENV' else 1


if __name__ == '__main__':
    raise SystemExit(main())
