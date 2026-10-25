# LingBot-VLA 2.0 × RoboTwin 2.0 — clean-only post-training

## What is submitted

| item | value |
|---|---|
| base model | `robbyant/lingbot-vla-v2-6b` |
| training data | RoboTwin 2.0 Aloha-AgileX, 50 tasks × 50 episodes, **clean only** (official LeRobot v3.0 clean package, 2,500 episodes / 548,893 frames). No randomized data is used. |
| training | full-parameter, FP32, official recipe (Muon, depth + video distillation, MoE aux losses), global batch 128, 51,456 steps = 12 epochs |
| weights | `03_模型权重/main_aug/checkpoints/global_step_51456/hf_ckpt/` (FP32 safetensors) — pass this directory as `--model_path` / `CKPT` |
| inference | FP32 server, robot config `robotwin_clean`; actions executed per call = `USE_LENGTH` in eval.sh, default **25** (K=25). The `results.json` shipped in `01_评测结果/` was produced with `USE_LENGTH=25`, FP32. |

## Submitted weights layout (required by the inference server)

```
03_模型权重/
└── main_aug/
    ├── lingbotvla_cli.yaml                         # training config snapshot — REQUIRED by inference
    ├── norm_stats/robotwin_clean.json              # clean-only normalization statistics
    └── checkpoints/
        └── global_step_51456/
            └── hf_ckpt/                            # FP32 safetensors + config + tokenizer
```

`eval.sh` resolves `CKPT` to `../03_模型权重/main_aug/checkpoints/global_step_51456/hf_ckpt`.

The inference server loads the training config from
`Path(model_path).parent.parent.parent / 'lingbotvla_cli.yaml'`
(see `deploy/lingbot_vla_v2_policy.py`), i.e. from `03_模型权重/main_aug/lingbotvla_cli.yaml` here.
That file is normally written at the very start of training by
`save_args(args, args.train.output_dir)` (`lingbotvla/utils/arguments.py`); the copy shipped in this
package is the same configuration reconstructed from `configs/clean_base.yaml` plus the `train.sh`
overrides. Only non-structural settings (lr, batch sizes, steps, workers) differ from the run, so the
model definition is identical.

> **Keep the directory depth when relocating.** Three levels above `hf_ckpt` must contain
> `lingbotvla_cli.yaml`. Compressing `main_aug/checkpoints/global_step_51456/hf_ckpt` into a single
> `checkpoint/` directory will make the inference server fail with `FileNotFoundError`.

`norm_stats_file` inside `lingbotvla_cli.yaml` is relative to the LingBot repo root
(`assets/norm_stats/robotwin_clean.json`, added by `src/patches/lingbot-vla-v2.patch`).

## Layout

```
configs/
  clean_base.yaml          training config (official configs/vla/robotwin/robotwin.yaml + our paths; overrides in train.sh)
  robotwin_clean.yaml      robot config (same feature mapping as official robotwin.yaml, clean-only norm stats)
  robotwin_clean.json      normalization stats computed on the clean training set only
  model_config.json        model config of the submitted checkpoint (copy of checkpoint/config.json)
src/patches/
  lingbot-vla-v2.patch     against lingbot-vla-v2.BASE_COMMIT
  RoboTwin.patch           against RoboTwin.BASE_COMMIT (official pinned revision)
src/aarch64_shims/         only needed on aarch64 hosts (see below)
scripts/                   launcher, client generator, scoring, environment helpers
train.sh                   reproduces the checkpoint (2 stages, same run directory)
eval.sh                    50 tasks × clean/randomized × 100 episodes → official results.json (scripts/make_results_json.py)
```

## Code changes (src/patches)

lingbot-vla-v2
- `lingbotvla/data/vla_data/base_dataset.py`: clamp video timestamps to the decoded length (≈25 % of `cam_high` videos in the
  clean package are 1–2 frames shorter than their parquet; without the clamp those samples fail to load).
- `lingbotvla/data/vla_data/transform.py`: optional extra augmentation `LB_AUG_EXTRA=crop,noise` (random 85–100 % crop
  resized back, Gaussian pixel noise σ≤0.03), applied identically to all frames of a sample, on top of `data.image_augment`.
- `tasks/vla/train_lingbotvla.py`: `LB_STOP_AT_STEPS` — stop cleanly after a given save step (used to split training into
  wall-time chunks; no effect on the result).
- `deploy/lingbot_vla_v2_policy.py`: optional multi-noise consensus `LB_NOISE_K` (tested, **not used** in the submission).
- `assets/norm_stats/robotwin_clean.json`, `configs/robot_configs/robotwin_clean.yaml`: clean-only statistics/config.

RoboTwin
- `envs/_base_task.py`: render samples-per-pixel overridable via `LB_RT_SPP` (default unchanged).
- `script/eval_policy_client_lingbotvla.py` (+ `script/deploy/`): official LingBot client plus per-episode resume records,
  optional seed-strided workers and optional temporal ensembling (`LB_TE_EXEC`, tested, **not used**). With these variables
  unset it behaves exactly like the official client.

## Dependencies / installation

1. LingBot-VLA 2.0: follow the official README of lingbot-vla-v2 (`pip install -r requirements.txt && pip install -e .`, plus
   `requirements-depth.txt`; flash-attn 2.8.3), download `robbyant/lingbot-vla-v2-6b`, `Qwen/Qwen3-VL-4B-Instruct` and the MoGe-2 depth model.
2. RoboTwin 2.0: follow `experiment/robotwin/README.md` of lingbot-vla-v2 (official pinned RoboTwin revision, SAPIEN, mplib, curobo,
   assets download), then apply `src/patches/RoboTwin.patch`.
3. Data: official RoboTwin LeRobot v3.0 package, clean part only; list it in a train-path file like `scripts/train_clean.txt`
   (`<robot_config_name> <dataset_dir>`).
4. Apply `src/patches/lingbot-vla-v2.patch`; set the model/data paths in `configs/clean_base.yaml`.

## Evaluation environment (this submission)

The `results.json` in `01_评测结果/` was produced on:

| item | value |
|---|---|
| GPU | 1 × NVIDIA RTX PRO 6000 Blackwell Server Edition (96 GB), **x86_64** |
| OS / driver | Ubuntu 22.04, NVIDIA driver 580.95.05, CUDA 12.8 |
| Python / torch | Python 3.12, **torch 2.8.0+cu128**, flash-attn 2.8.3 |
| sim stack | SAPIEN 3.0.0b1, mplib 0.2.1, curobo v0.7.8, numpy 1.26.4 |
| inference | FP32 server (`--use_fp32 True --use_bf16 False`), 1 server + 8 sim processes per GPU |
| rendering | official defaults: `set_ray_tracing_samples_per_pixel(32)`, `path_depth(8)`, denoiser `oidn` (`LB_RT_SPP` unset) |
| concurrency | `SIMS_PER_SERVER=8`, one GPU |

The previous submission was evaluated on 4 × NVIDIA GH200 (aarch64). On the same checkpoint and same
action-chunk length, the x86 run is about **+11 pp higher on clean** and **≈0 on randomized**, because
the clean scenes are more sensitive to the rendering path. See `04_复现与调优说明/reproduction_report.md`
§3.1 for the measured breakdown. Final scores are subject to the organiser's re-evaluation.

## Environment

Same as the official LingBot-VLA and RoboTwin 2.0 instructions (RoboTwin at the pinned commit in `RoboTwin.BASE_COMMIT`).
Our runs used one conda env for both the policy server and the simulator: Python 3.12, torch 2.8.0+cu129.
On x86_64 nothing beyond the official setup is required.

aarch64 (NVIDIA GH200) notes — only if you reproduce on ARM:
- SAPIEN nightly `3.0.4.dev20261009` aarch64 wheel; preload `aarch64_shims/aarch64_atomics_shim.c` (compiled) for missing
  `__aarch64_*_sync` symbols; mplib v0.2.1, curobo v0.7.8 and flash-attn 2.8.3 built from source (`scripts/build_native.sh`).
- `aarch64_shims/vklayer`: Vulkan layer that exposes only the GPU in `CUDA_VISIBLE_DEVICES` (multi-PCI-domain fix).
- zarr 2.18.3 + numcodecs 0.15.1.

## Reproduce

```bash
git -C lingbot-vla-v2 checkout $(cat src/patches/lingbot-vla-v2.BASE_COMMIT) && git -C lingbot-vla-v2 apply src/patches/lingbot-vla-v2.patch
git -C RoboTwin checkout $(cat src/patches/RoboTwin.BASE_COMMIT) && git -C RoboTwin apply src/patches/RoboTwin.patch
# edit model / data paths in configs/clean_base.yaml, then
LINGBOT_DIR=$PWD/lingbot-vla-v2 OUT=$PWD/ckpt/main_aug bash train.sh
ROBOTWIN_DIR=$PWD/RoboTwin LINGBOT_DIR=$PWD/lingbot-vla-v2 CKPT=$PWD/ckpt/main_aug/checkpoints/global_step_51456/hf_ckpt bash eval.sh
```

### Evaluating the submitted package directly

To evaluate the shipped weights instead of reproducing training from scratch, point `CKPT` at the
submitted `hf_ckpt` and skip training:

```bash
ROBOTWIN_DIR=$PWD/RoboTwin LINGBOT_DIR=$PWD/lingbot-vla-v2 \
  CKPT=$PWD/../03_模型权重/main_aug/checkpoints/global_step_51456/hf_ckpt bash eval.sh
```

See `../04_复现与调优说明/reproduction_report.md` for the training/inference decisions and all ablations.
