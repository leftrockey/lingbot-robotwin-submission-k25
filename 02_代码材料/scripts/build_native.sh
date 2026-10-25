#!/bin/bash
# Build the compiled pieces of the lingbot env on a compute node: mplib (no aarch64 wheel), curobo, flash-attn.
# Each step is skipped if its import already works, so this is safe to re-run.
set -eo pipefail
source /path/to/lingbot/run/env.sh
PY=$LB_ENV/bin/python; NJ=${NJ:-64}
export CC=$LB_ENV/bin/aarch64-conda-linux-gnu-gcc CXX=$LB_ENV/bin/aarch64-conda-linux-gnu-g++
export CPATH=$LB_ENV/targets/sbsa-linux/include:${CPATH:-} LIBRARY_PATH=$LB_ENV/targets/sbsa-linux/lib:$LB_ENV/lib:${LIBRARY_PATH:-}
export TORCH_CUDA_ARCH_LIST="9.0" MAX_JOBS=$NJ CMAKE_BUILD_PARALLEL_LEVEL=$NJ
which nvcc; nvcc --version | tail -1
# ---- mplib 0.2.1 ----
if ! $PY -c "import mplib" 2>/dev/null; then
  cd $LB/src/MPlib
  git checkout -q -- CMakeLists.txt
  # drop the pybind11_mkdoc target (needs libclang; docstring headers are already committed) and -Werror
  $PY - <<'PY'
import re
s=open("CMakeLists.txt").read()
s=re.sub(r"# pybind11_mkdoc\n.*?VERBATIM\n\)\n", "", s, flags=re.S)
s=s.replace("add_dependencies(pymp pybind11_mkdoc)\n","").replace(" -Werror","").replace("find_package(Eigen3 3.4.0 REQUIRED)","find_package(Eigen3 REQUIRED)")
s=re.sub(r"add_executable\(test_articulated_model.*?\n.*?\n.*?add_test\(.*?\)\n","",s,flags=re.S)
open("CMakeLists.txt","w").write(s)
PY
  grep -c mkdoc CMakeLists.txt || true
  rm -rf build; LDFLAGS="-L$LB_ENV/lib -Wl,-rpath,$LB_ENV/lib" CMAKE_ARGS="-DCMAKE_PREFIX_PATH=$LB_ENV -DPython_EXECUTABLE=$PY" $PY -m pip install --no-cache-dir --no-build-isolation --no-deps -v . 2>&1 | tail -20
fi
cd $LB && $PY -c "import mplib, mplib.pymp; print('mplib ok', mplib.__file__)"
# RoboTwin's two source patches (script/_install.sh)
SP=$($PY -c "import site;print(site.getsitepackages()[0])")
sed -i -E 's/("r")(\))( as)/\1, encoding="utf-8") as/g' $SP/sapien/wrapper/urdf_loader.py
sed -i -E 's/(if np.linalg.norm\(delta_twist\) < 1e-4 )(or collide )(or not within_joint_limit:)/\1\3/g' $SP/mplib/planner.py
# ---- curobo v0.7.8 ----
if ! $PY -c "import torch, curobo, curobo.curobolib.kinematics_fused_cu" 2>/dev/null; then
  cd $LB/src/RoboTwin/envs
  [ -d curobo ] || git clone -q --branch v0.7.8 --depth 1 https://github.com/NVlabs/curobo.git
  cd curobo && $PY -m pip install --no-cache-dir -e . --no-build-isolation --no-deps 2>&1 | tail -5
fi
$PY -c "import torch, curobo, curobo.curobolib.kinematics_fused_cu; print('curobo ok')"
# ---- flash-attn 2.8.3 ----
if ! $PY -c "import torch, flash_attn" 2>/dev/null; then
  MAX_JOBS=${FA_JOBS:-48} FLASH_ATTN_CUDA_ARCHS=90 FLASH_ATTENTION_FORCE_BUILD=TRUE $PY -m pip install --no-cache-dir --no-build-isolation --no-deps flash-attn==2.8.3 2>&1 | tail -5
fi
$PY -c "import torch, flash_attn; print('flash_attn', flash_attn.__version__)"
cd $LB/src/RoboTwin && $PY script/update_embodiment_config_path.py
echo BUILD_NATIVE_DONE
