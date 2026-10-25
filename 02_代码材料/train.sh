#!/bin/bash
# Reproduce the submitted checkpoint: full-parameter post-training of LingBot-VLA 2.0 (robbyant/lingbot-vla-v2-6b)
# on RoboTwin 2.0 Aloha-AgileX 50 tasks, CLEAN data only (50 episodes/task, official LeRobot v3.0 clean package).
# No randomized data is used anywhere.
#
# Hardware used: 1 node, 4x NVIDIA GH200 (96 GB), aarch64. ~3.7 s/step, ~53 h total.
# Two stages on the same run directory (the second resumes model + optimizer state from the first):
#   stage 1: steps 0 -> 25728 (6 epochs), cosine lr 5e-5 -> 2.5e-5
#   stage 2: resume at 25728 with max_steps 51456 (12 epochs); the cosine schedule is recomputed for the new length,
#            so lr restarts at ~3.7e-5 and decays to 2.5e-5 at 51456.  Submitted checkpoint = global_step_51456/hf_ckpt.
#
# Usage: LINGBOT_DIR=/path/to/lingbot-vla-v2 (with src/patches/lingbot-vla-v2.patch applied) OUT=/path/to/out bash train.sh
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
LINGBOT_DIR=${LINGBOT_DIR:?set LINGBOT_DIR to the patched lingbot-vla-v2 checkout}
OUT=${OUT:-$PWD/ckpt/main_aug}
CFG=$HERE/configs/clean_base.yaml   # edit model/tokenizer/depth/dino paths and data.train_path inside before running
export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0,1,2,3}   # 4 GPUs: global batch 128 = micro 16 x 4 GPUs x accum 2

# robot config + clean-only normalization stats (also contained in the patch)
cp $HERE/configs/robotwin_clean.yaml $LINGBOT_DIR/configs/robot_configs/robotwin_clean.yaml
cp $HERE/configs/robotwin_clean.json $LINGBOT_DIR/assets/norm_stats/robotwin_clean.json

export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export LB_AUG_EXTRA=crop,noise        # extra image augmentation added by our patch (transform.py), on top of colour jitter

common=(--train.output_dir $OUT --train.save_steps 2144
        --train.global_batch_size 128 --train.micro_batch_size 16 --train.gradient_accumulation_steps 2
        --train.lr 5.0e-5 --train.lr_min 2.5e-5 --data.image_augment true --data.num_workers 8)

cd $LINGBOT_DIR
# stage 1: 6 epochs
bash train.sh tasks/vla/train_lingbotvla.py $CFG --train.max_steps 25728 "${common[@]}"
# stage 2: resume (enable_resume: true in the config) and extend to 12 epochs
bash train.sh tasks/vla/train_lingbotvla.py $CFG --train.max_steps 51456 "${common[@]}"

echo "submitted weights: $OUT/checkpoints/global_step_51456/hf_ckpt"
