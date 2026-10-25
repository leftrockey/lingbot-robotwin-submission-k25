# LingBot-VLA 2.0 × RoboTwin 2.0 — Tianchi preliminary submission (team 具身天命人, 1386132)

> ⚠️ **提交次数提醒**：初赛累计仅 **3 次**提交机会（非每日 3 次）。本仓库内容为提交前快照，**任何再次上传 OSS 前必须确认剩余次数**。详见 [`docs/POSTMORTEM.md`](docs/POSTMORTEM.md) 第 5.1 节。


蚂蚁灵波具身大模型挑战赛（天池）初赛提交材料 — **K=25 推理配置版**。

> **权重文件不在本仓库**（23 GB，超出 GitHub 限制）。
> 完整提交包（含权重）见 HuggingFace：**[rockeeyy/lingbot-robotwin-submission-k25](https://huggingface.co/rockeeyy/lingbot-robotwin-submission-k25)**

| item | value |
|---|---|
| **训练起点** | **LingBot-VLA 2.0**（`robbyant/lingbot-vla-v2-6b`）× **RoboTwin 2.0** Aloha-AgileX clean 数据 |
| 团队 | 具身天命人（team_id **1386132**） |
| 权重 | `main_aug/checkpoints/global_step_51456/hf_ckpt`，FP32 safetensors，24 GB |
| 训练 | 全参数后训练，仅 clean 数据，12 epochs / 51,456 steps，4 × GPU，global batch 128 |
| 推理 | FP32，robot config `robotwin_clean`，**动作执行长度 K=25**（官方默认 50） |
| 结果 | clean **78.18%**（3909/5000） / randomized **49.34%**（2467/5000） |

## 仓库内容

```
01_评测结果/results.json                  本次提交的官方格式结果（K=25，50 任务 × 100 集 × 2 setting）
02_代码材料/                              README / train.sh / eval.sh / configs / src/patches / scripts
04_复现与调优说明/reproduction_report.md  完整实验记录（含 K 配对实验、环境分解、风险披露）
docs/EXPERIMENTS.md                      关键实验结论速览
```

权重与 `lingbotvla_cli.yaml`、`norm_stats/` 在 HuggingFace 包内：

```
03_模型权重/main_aug/
├── lingbotvla_cli.yaml                    训练配置快照（推理必需）
├── norm_stats/robotwin_clean.json         clean-only 归一化统计
└── checkpoints/global_step_51456/hf_ckpt/ 6 个 safetensors 分片（25.50 GB，1708 张量）
```

## 调优方向

### 1. 数据（规则 2.1）

- **仅使用 clean 数据**：RoboTwin 2.0 Aloha-AgileX 50 任务 × 50 条（2,500 条 / 548,893 帧）。randomized 数据未以任何形式参与训练。
- **clean-only 归一化统计**：官方 `robotwin.json` 混入了 randomized 数据，本方案只用 clean 重新计算 `robotwin_clean.json`。
- **训练期图像增强**：颜色抖动 + 随机裁剪（85–100% 缩放回原尺寸）+ 像素高斯噪声（σ≤0.03），均在规则 2.1.1 白名单内，同一样本各帧使用相同参数。
- **修复读帧越界**：clean 包约 25% 的 `cam_high` 视频比 parquet 少 1–2 帧，原代码会越界；打补丁把时间戳截断到实际解码长度，使全部 2,500 条轨迹可用。

### 2. 训练（规则 2.3）

| | 官方 robotwin.yaml | 本方案 |
|---|---|---|
| 数据 | clean + randomized | **仅 clean** |
| GPU | 32 | 4 |
| 全局 batch | 1024 | 128（micro 16 × 4 卡 × 梯度累积 2） |
| 学习率 | 1e-4 → 5e-5 cosine | 5e-5 → 2.5e-5 cosine |
| 步数 | 50,000 | 51,456（12 epochs），分两段续训 |
| 精度 | FP32 | FP32 |

模型结构未改动，沿用官方的深度/视频蒸馏与 MoE 辅助损失。

### 3. 推理策略（规则 2.4）

**核心改动：动作执行长度 K = 25**。模型每次预测 50 步动作，执行其中 25 步后重新推理（replanning），属规则 2.4(一) 明确允许的范围。

同机配对实验（16 个难任务，744 个配对回合，种子取两边交集）：

| setting | K=25 | K=50 | 差 | 显著性 |
|---|---|---|---|---|
| clean | 54.84% | 55.51% | −0.67pp | McNemar χ²=0.09，不显著 |
| randomized | 23.79% | 19.76% | **+4.03pp** | χ²=6.67，**p<0.05 显著** |

结论：clean 上 K=25 与官方默认 K=50 无差异，randomized 上显著更优，因此采用 K=25。

**未采用**（均已实测或受规则限制）：执行 16 步（−4.2pp）、时间集成（−4.1pp）、多噪声样本平均（−1.0pp 且成本 ×4）、BF16（官方说明会明显改变成功率）、多 seed 投票 / 多 checkpoint 集成 / 任务路由（规则 3.3 明文禁止）。

### 4. 评测环境

单节点 **1 × NVIDIA RTX PRO 6000 Blackwell（96 GB, x86_64）**，Ubuntu 22.04，Python 3.12，torch 2.8.0+cu128，驱动 580.95.05，SAPIEN 3.0.0b1 / mplib 0.2.1 / curobo v0.7.8，flash-attn 2.8.3。渲染参数保持官方默认（`samples_per_pixel=32`、`path_depth=8`、denoiser `oidn`）。

**环境差异说明**：上一版提交在 4 × GH200（aarch64）上完成。同一 checkpoint、同一 K 值下，x86 在 clean 上高约 **+11pp**，randomized 上几乎相同（−0.97pp）——clean 场景对渲染路径更敏感。最终成绩以主办方复测为准。

## 复现

```bash
# 1) 准备官方仓库（固定 commit + 打补丁）
git -C lingbot-vla-v2 checkout $(cat 02_代码材料/src/patches/lingbot-vla-v2.BASE_COMMIT)
git -C lingbot-vla-v2 apply 02_代码材料/src/patches/lingbot-vla-v2.patch
git -C RoboTwin checkout $(cat 02_代码材料/src/patches/RoboTwin.BASE_COMMIT)
git -C RoboTwin apply 02_代码材料/src/patches/RoboTwin.patch

# 2) 从 HuggingFace 取权重后直接评测（跳过训练）
ROBOTWIN_DIR=$PWD/RoboTwin LINGBOT_DIR=$PWD/lingbot-vla-v2 \
  CKPT=$PWD/03_模型权重/main_aug/checkpoints/global_step_51456/hf_ckpt \
  bash 02_代码材料/eval.sh
```

`eval.sh` 默认 `USE_LENGTH=25`、FP32 推理，与本次 `results.json` 一致。

> 注意：`--model_path` 必须指向 `.../main_aug/checkpoints/global_step_51456/hf_ckpt`。推理服务会在该路径往上三层查找 `lingbotvla_cli.yaml`，**不要把目录层级压平**。

## 合规声明

- 训练数据仅使用官方 release 的 RoboTwin 2.0 clean 演示，无外部数据、无环境调用、无自建 randomization。
- 训练起点为 `robbyant/lingbot-vla-v2-6b`，未使用官方 RoboTwin 后训练权重作为起点或教师。
- 推理阶段仅加载一份权重，不使用任务 ID/指令路由、多 seed 投票、模型集成或失败重置。
- 未使用 LoRA；未引入额外公开预训练模块。

完整实验记录与风险披露见 [`04_复现与调优说明/reproduction_report.md`](04_复现与调优说明/reproduction_report.md)。

## 引用

```bibtex
@misc{lingbot_robotwin_k25_2026,
  title  = {LingBot-VLA 2.0 x RoboTwin 2.0 - Tianchi preliminary submission (K=25)},
  author = {Team 具身天命人 (ID 1386132)},
  year   = {2026},
  note   = {Weights: https://huggingface.co/rockeeyy/lingbot-robotwin-submission-k25}
}
```
