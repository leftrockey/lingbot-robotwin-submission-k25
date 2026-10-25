# Common environment for every lingbot job.
export LB_ENV=/path/to/mamba/envs/lingbot
export LB=/path/to/lingbot
export PATH=$LB_ENV/bin:$PATH PYTHONNOUSERSITE=1
unset PIP_CONSTRAINT
export CUDA_HOME=$LB_ENV
export HF_HOME=/path/to/scratch/huggingface TORCH_HOME=/path/to/scratch/torch_home
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1
export XDG_CACHE_HOME=$LB/cache
export QWEN3VL_PATH=$LB/models/Qwen3-VL-4B-Instruct QWEN3_PATH=$LB/models/Qwen3-VL-4B-Instruct
export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/nvidia_icd.aarch64.json
export OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8
ulimit -c 0
export LD_PRELOAD=/path/to/lingbot/shim/libaarch64_atomics_shim.so${LD_PRELOAD:+:$LD_PRELOAD}
# GH200: NVIDIA Vulkan ignores CUDA_VISIBLE_DEVICES and SAPIEN's CPU-only build mis-parses multi-domain PCI ids.
export VK_LAYER_PATH=/path/to/lingbot/shim/vklayer VK_INSTANCE_LAYERS=VK_LAYER_LB_device_select
