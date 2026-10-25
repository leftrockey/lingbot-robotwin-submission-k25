# Minimal stand-in for conda.sh: the official RoboTwin launcher only calls `conda activate <env>` /
# `conda deactivate`; both sides live in the single micromamba env below.
LB_ENV=/path/to/mamba/envs/lingbot
conda() {
  case "$1" in
    activate) export PATH="$LB_ENV/bin:$PATH" CONDA_PREFIX="$LB_ENV" PYTHONNOUSERSITE=1 ;;
    deactivate) : ;;
    *) echo "fake conda: unsupported '$*'" >&2; return 1 ;;
  esac
}
