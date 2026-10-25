#!/bin/bash
# pip-side install of the single lingbot env (LingBot inference/training + RoboTwin sim). Compiled pieces
# (mplib, curobo, flash-attn) are built on the GPU node by build_native.sh.
set -eo pipefail
E=/path/to/mamba/envs/lingbot
R=/path/to/lingbot/src/lingbot-vla-v2
export PYTHONNOUSERSITE=1 PIP_NO_INPUT=1; unset PIP_CONSTRAINT
PIP="$E/bin/python -m pip install --no-cache-dir"
chk(){ $E/bin/python -c "import torch;assert torch.__version__.startswith('2.8.0'),torch.__version__;print('torch ok',torch.__version__)"; }
$PIP -U pip "setuptools<70" wheel
grep -vE "^(torch|torchvision|torchaudio|torchcodec)==" $R/requirements.txt > /tmp/lb_req_$$.txt
$PIP torchdata==0.11.0 -r /tmp/lb_req_$$.txt; chk
$PIP "torchcodec==0.7.*" --no-deps || echo "WARN torchcodec unavailable (pyav fallback)"
$PIP numpydantic==1.9.0 --no-deps
$PIP --no-deps "lerobot @ https://github.com/huggingface/lerobot/archive/refs/tags/v0.4.2.tar.gz"
$PIP -e $R --no-deps
$PIP -r $R/requirements-depth.txt; chk
$E/bin/python - <<PY
import site; from pathlib import Path
p=Path(site.getsitepackages()[0])/"stablevla_local_depth.pth"
p.write_text("$R/lingbotvla/models/vla/vision_models/morgbd_clean/3rd/utils3d\n"); print("wrote",p)
PY
$PIP -e $R/lingbotvla/models/vla/vision_models/lingbot-depth --no-deps
$PIP -e $R/lingbotvla/models/vla/vision_models/MoGe; chk
$PIP huggingface_hub==0.34.0
# ---- RoboTwin sim side (official pins, except sapien 3.0.0b1 has no aarch64 wheel -> 3.0.3) ----
$PIP "https://github.com/haosulab/SAPIEN/releases/download/3.0.3/sapien-3.0.3-cp312-cp312-linux_aarch64.whl"
$PIP transforms3d==0.4.2 gymnasium==0.29.1 "open3d>=0.18" toppra pydantic zarr "pyglet<2" moviepy termcolor warp-lang==1.12.0; chk
$PIP numpy==1.26.4 scipy==1.13.1; chk
$E/bin/python -m pip check || echo "WARN pip check issues (expected for --no-deps pins)"
echo PIP_INSTALL_DONE
