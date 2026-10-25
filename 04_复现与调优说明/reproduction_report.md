# 复现与调优说明

## 1. 基础信息

- 团队名称：具身天命人（team_id 1386132）
- 使用模型版本：LingBot-VLA 2.0，基座 `robbyant/lingbot-vla-v2-6b`，全参数后训练
- 代码版本 / Commit：
  - lingbot-vla-v2：`be969b8fd117fb70550c5d4bf4bc328211b5b1b6` + `02_代码材料/src/patches/lingbot-vla-v2.patch`
  - RoboTwin：`13c3c47ff4312dd62484bcd51be034af55c062d1`（官方固定版本）+ `02_代码材料/src/patches/RoboTwin.patch`
- 提交 checkpoint 名称：`03_模型权重/main_aug/checkpoints/global_step_51456/hf_ckpt`（12 遍数据，FP32 safetensors）

## 2. 训练复现

- 使用数据集：RoboTwin 2.0 Aloha-AgileX 50 个任务的 clean 数据，每任务 50 条（官方 LeRobot v3.0 clean 包，共 2,500 条 / 548,893 帧）
- 是否使用 randomized 数据训练：**否**。归一化统计量也只在 clean 数据上重新计算（官方 `robotwin.json` 混入了 randomized 数据，未使用）。训练期间未调用仿真环境、未使用任何外部数据。
- 一键训练脚本：`02_代码材料/train.sh`（单节点 4 卡；两段训练写入同一输出目录，第二段自动续训）
- 训练配置文件：`02_代码材料/configs/clean_base.yaml`（官方 `configs/vla/robotwin/robotwin.yaml` 改为我们的路径），其余超参在 `train.sh` 中以命令行覆盖
- robot config：`02_代码材料/configs/robotwin_clean.yaml`，归一化统计 `02_代码材料/configs/robotwin_clean.json`；模型配置 `02_代码材料/configs/model_config.json`

## 3. 评测复现

- 一键评测脚本：`02_代码材料/eval.sh`（clean 与 randomized 两个 setting，各 50 任务 × 100 回合，结束后生成官方格式 `results.json`）
- checkpoint 加载方式：推理服务 `deploy/lingbot_vla_v2_policy.py --model_path <checkpoint> --use_fp32 True --use_bf16 False`；`eval.sh` 中 `CKPT` 默认指向 `03_模型权重/main_aug/checkpoints/global_step_51456/hf_ckpt`
- 推理配置（**最终测评将使用 `eval.sh` 中的这组参数**）：

  | 参数 | 取值 | 说明 |
  | --- | --- | --- |
  | `USE_LENGTH` | **25** | 每预测 50 步动作，执行其中 25 步后重新推理（replanning）。规则 2.4(一) 允许 |
  | 推理精度 | `use_fp32=True`, `use_bf16=False` | FP32，与官方 release 验证设置一致 |
  | `use_compile` | `True` | 默认值，未修改 |
  | robot config | `robotwin_clean` | clean-only 归一化统计，与训练一致 |
  | 动作平滑 / temporal ensemble / 置信度门控 | **未使用** | 规则 2.4 未明确判定，未采用 |
  | 多 seed 投票 / 多 checkpoint 集成 / 任务路由 | **未使用** | 规则 3.3 明文禁止 |

- clean setting 评测命令：`eval.sh` 中的
  `start_eval.sh --model_path $CKPT --robo_name robotwin_clean --task_config demo_clean --num_tasks 50 --use_length 25 --use_fp32 True ...`
- randomized setting 评测命令：同上，`--task_config demo_randomized`
- **评测环境**：单节点 **1 × NVIDIA RTX PRO 6000 Blackwell Server Edition（96 GB, x86_64）**，Ubuntu 22.04，Python 3.12，**torch 2.8.0+cu128**，NVIDIA 驱动 580.95.05，SAPIEN 3.0.0b1 / mplib 0.2.1 / curobo v0.7.8，flash-attn 2.8.3。
  - 每张 GPU 运行 1 个 FP32 推理服务（约 27 GB）+ 8 个仿真进程。
  - 渲染设置保持官方默认：`sapien.render.set_ray_tracing_samples_per_pixel(32)`、`path_depth(8)`、denoiser `oidn`（`LB_RT_SPP` 未设置）。
  - 计分口径：每任务取种子顺序上前 100 个有效种子（`seed = 100000` 起），与官方顺序评测一致；仿真器偶发崩溃（Vulkan DeviceLost）回合计为失败，clean 4/5000、randomized 19/5000。

### 3.1 与上一版（GH200）评测环境的差异说明

上一版提交在 **4 × NVIDIA GH200（aarch64）** 上完成，本版在 **x86_64** 上重测。同一 checkpoint、同一 K 值在两种平台上的差异**集中在 clean setting**：

| 16 个难任务 | clean | randomized |
| --- | --- | --- |
| K=50, x86 本机 | 55.51% | 19.85% |
| K=50, GH200 上一版 | 44.38% | 20.81% |
| **环境差异（x86 − GH200）** | **+11.14pp** | **−0.97pp** |

clean 场景（简单背景）对渲染路径更敏感，aarch64 上成功率明显偏低；randomized 场景因背景本身高度随机，环境差异几乎为零。因此本版 clean 的绝对值高于上一版，**主要来自评测平台差异，而非推理参数改动**（参数改动的影响见第 5 节配对实验）。

### 3.2 评测环境一致性校准

为确认本机环境与官方标准环境一致，使用官方发布权重 `robbyant/lingbot-vla-v2-6b-robotwin`（配官方 `robotwin.yaml` 与 `robotwin.json` 归一化统计）在**本机**做了 6 任务对照测试，平均约 **80%**，与官方公布的 x86 基准 83.5% 一致（差 3.2pp 以内）。

> 该权重**仅用于环境一致性验证**，未作为训练起点、未用于蒸馏、未参与本提交权重的任何训练环节（规则 3.2 / 3.5）。验证完成后已从工作目录移除。

## 4. 代码改动说明

- 是否修改 LingBot-VLA 2.0 官方代码：是（`src/patches/lingbot-vla-v2.patch`）
  - `lingbotvla/data/vla_data/base_dataset.py`：视频时间戳截断到实际解码长度（clean 包约 25% 的 `cam_high` 视频比 parquet 少 1–2 帧，原代码会读帧越界）。
  - `lingbotvla/data/vla_data/transform.py`：可选额外图像增强 `LB_AUG_EXTRA=crop,noise`（随机裁剪 85–100% 后缩放回原尺寸、像素高斯噪声 σ≤0.03），同一样本的各帧使用相同参数。
  - `tasks/vla/train_lingbotvla.py`：`LB_STOP_AT_STEPS`，在指定存档步后正常退出（用于按作业时限分段训练，不影响结果）。
  - `deploy/lingbot_vla_v2_policy.py`：可选多噪声样本共识 `LB_NOISE_K`（已测试，**未用于提交结果**；不设置时行为不变）。
  - 新增 `assets/norm_stats/robotwin_clean.json`、`configs/robot_configs/robotwin_clean.yaml`。
- 是否修改 RoboTwin 官方评测代码：是（`src/patches/RoboTwin.patch`），**评测协议与计分不变**
  - `envs/_base_task.py`：渲染采样数可用 `LB_RT_SPP` 覆盖（默认值不变，提交结果用默认值）。
  - `script/eval_policy_client_lingbotvla.py`（及 `script/deploy/`）：LingBot 官方评测客户端，增加逐回合结果记录与断点续跑（`lb_resume.jsonl`）、耗时统计、可选的按种子分摊并行（`LB_SEED_START/LB_SEED_STRIDE/LB_RESUME_TAG`）、可选时间集成（`LB_TE_EXEC`，已测试，**未用于提交结果**）。这些环境变量均不设置时与官方客户端行为一致。
  - 评测启动脚本 `02_代码材料/scripts/start_eval.sh` 为官方 `experiment/robotwin/start_robotwin_infer_and_eval.sh` 的副本，增加多个仿真共用一个推理服务（`SIMS_PER_SERVER`，推理服务每次请求独立完整前向，无状态）、任务子集、GPU 偏移、可跨作业续跑的运行目录。

## 5. 调优说明

### 5.1 训练参数（相对官方 robotwin.yaml）

| | 官方（clean+randomized） | 本方案（仅 clean） |
| --- | --- | --- |
| GPU | 32 | 4（单节点） |
| 全局 batch | 1024 | 128（micro 16 × 4 卡 × 梯度累积 2） |
| 学习率 | 1e-4 → 5e-5 cosine | 5e-5 → 2.5e-5 cosine |
| 步数 | 50,000 | 51,456（12 遍），分两段：0→25,728（6 遍），再续训到 51,456（cosine 按新长度重算） |
| 精度 | FP32 | FP32 |

训练长度依据：第 1 遍 clean 32.0%（10 任务子集）→ 第 6 遍 56.4% → 第 12 遍约 58.9%；在 16 个最难任务上逐种子配对，12 遍比 6 遍 clean +6.1pp（约 3.8σ），randomized +1.9pp。

### 5.2 数据处理方式

只用 clean 数据；clean-only 归一化统计；修复短视频读帧越界；颜色抖动 + 随机裁剪 + 像素噪声增强（只作用于训练）。未使用 randomized 数据、未做目标重标注、未使用 LLM 生成指令。

### 5.3 模型结构改动

无。沿用官方结构与深度/视频蒸馏、MoE 辅助损失。

### 5.4 推理策略：动作执行长度（K）的配对实验

**方法**：固定 checkpoint、精度（FP32）、采样设置，只改变每轮执行的步数 K。选 16 个最难任务（按 K=25 两 setting 平均成功率排序），在 **同一台 x86 机器**上分别以 K=25 和 K=50 各跑 50 个种子，取两边实际种子交集（平均每任务 46 个种子，共 744 个配对回合）逐种子比较。

| setting | K=25 | K=50 | 差 | McNemar（K25独赢/K50独赢/平） | 显著性 |
| --- | --- | --- | --- | --- | --- |
| clean | 54.84% | 55.51% | **−0.67pp** | 86 / 91 / 567 | χ²=0.09，不显著 |
| randomized | 23.79% | 19.76% | **+4.03pp** | 78 / 48 / 618 | χ²=6.67，**p<0.05 显著** |

**结论**：
- clean 上 K=25 与 K=50 无差异（−0.67pp，统计不显著）；
- randomized 上 K=25 显著更优（+4.03pp，95% CI 约 [+1.07, +6.99]）。该结论与上一版在 GH200 上的配对实验（randomized +4.5pp）一致，可互相印证。
- 因此本版采用 **K=25**：clean 不损失，randomized 有稳定收益。

**风险披露**：任务级波动较大。clean 上 `open_microwave`（1500 步长程任务）从 K=50 的 93.8% 降至 K=25 的 43.8%，是明确的退化；同时 `move_can_pot`（+27.1pp）、`blocks_ranking_size`（+8.7pp）、`place_a2b_right`（+8.2pp）、`handover_block`（+6.1pp）等提升，总体打平。randomized 侧无任何任务下降超过 20pp。

**未采用的方案**（均已实测或规则限制）：
- 执行 16 步：比 25 步 −4.2pp；
- 时间集成（每 10 步重规划 + 指数加权）：比 25 步 −4.1pp；
- 25 步 + 4 噪声样本平均：比 25 步 −1.0pp 且推理成本 ×4；
- BF16 推理：官方说明会明显改变成功率，未采用。

### 5.5 主要提升点

1. 只用 clean 数据时，延长训练到 12 遍（clean +2.5pp）。
2. 推理侧执行长度 K=25：randomized 显著 +4.03pp，clean 持平。
3. 修复 clean 数据包中视频帧数不匹配导致的读帧问题，使全部 2,500 条轨迹可用。
4. 在 x86 平台上完成全量评测（clean 场景的成功率显著高于 aarch64 平台，见 3.1）。

## 6. 评测结果

| setting | 平均成功率 | 回合数 |
| --- | --- | --- |
| clean | **78.18%**（3,909 / 5,000） | 50 任务 × 100 |
| randomized | **49.34%**（2,467 / 5,000） | 50 任务 × 100 |

- 每个 setting 50 任务 × 100 回合，**执行长度 25**，FP32 推理，`robotwin_clean` 归一化统计。
- 仿真器崩溃回合计为失败：clean 4 个、randomized 19 个。
- 逐任务结果见 `01_评测结果/results.json`。
- 本表在本团队 x86 评测环境下测得（见第 3 节）。同一 checkpoint 在 GH200（aarch64）上的上一版结果为 clean 58.98% / randomized 40.68%，差异原因见 3.1。最终成绩以主办方复测为准。

## 7. 提交物结构

```
具身天命人_初赛提交材料/
├── 01_评测结果/
│   └── results.json                                   # 本次提交（K=25）
├── 02_代码材料/
│   ├── README.md
│   ├── train.sh / eval.sh
│   ├── configs/                                        # clean_base / robotwin_clean / model_config
│   ├── scripts/                                        # launcher、评分、环境辅助
│   └── src/patches/                                     # 对官方仓库的补丁
├── 03_模型权重/
│   └── main_aug/
│       ├── lingbotvla_cli.yaml                         # 训练配置快照（推理必需）
│       ├── norm_stats/robotwin_clean.json              # clean-only 归一化统计
│       └── checkpoints/global_step_51456/hf_ckpt/      # FP32 safetensors（--model_path 指向此目录）
└── 04_复现与调优说明/
    └── reproduction_report.md
```
