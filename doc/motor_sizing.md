# 电机选型（Motor Sizing）—— GeesunDog dog1 关节力矩数据与结论

> 数据日期：2026-10-12；机器人：GeesunDog `dog1`（四足，12 自由度（DOF，关节），腿关节位置伺服）
> 策略 checkpoint（检查点）：`logs/rsl_rl/unitree_geesun_dog/2026-10-12_20-24-42/model_3700.pt`
> （3700 轮平地速度跟踪训练；PD 参数见 `UnitreeActuatorCfg_GeesunDog`）

## 1. 目的

给出各关节电机的**峰值力矩（peak torque）**、**持续力矩（RMS（均方根））**与**高分位力矩（P99（99 分位））**需求，供硬件选型参考。

## 2. 测量方法

- 工具：`scripts/rsl_rl/test_walk_torque.py`（加载 checkpoint 进行确定性推理，记录每关节执行器实际施加力矩，输出 CSV（逗号分隔表格））；
- 两种工况：
  - **flat（平地名义工况）**：纯平地、1000 步、全命令范围（±1.0 m/s），日常行走载荷；
  - **complex（复杂地形压力工况）**：混合复杂地形（random_rough（随机粗糙）+ pyramid_stairs（金字塔台阶））全覆盖难度、1000 步，冲击/压力包络；
- **饱和裁剪问题与测量技巧**：执行器的力矩上限由力矩-速度曲线的 `Y1`（同向峰值）/`Y2`（反向峰值）决定
  （`UnitreeActuatorCfg_GeesunDog`：Y1=55.8 / Y2=64.6 N·m）。首次 complex 测量中 5 个关节峰值精确等于
  64.6000 N·m，即被上限裁剪、真实需求未知。为此**临时将 Y1/Y2 放大 ×2（111.6/129.2）重测一次**
  （"unsaturated"未饱和数据），测毕即恢复原值——本页所有"真实峰值"均来自该次放开测量。

## 3. 数据汇总（每关节，单位 N·m）

### 3.1 平地名义工况（flat，1000 步）

| 关节 | Peak（峰值） | P99 | RMS |
|---|---|---|---|
| joint_fl_hip | 34.44 | 16.89 | 6.19 |
| joint_fr_hip | 26.11 | 17.35 | 5.87 |
| joint_hl_hip | 32.06 | 16.34 | 6.05 |
| joint_hr_hip | 36.62 | 14.63 | 5.68 |
| joint_fl_thigh | 30.10 | 19.44 | 6.80 |
| joint_fr_thigh | 29.10 | 16.59 | 5.75 |
| joint_hl_thigh | 28.31 | 15.82 | 5.33 |
| joint_hr_thigh | 37.10 | 13.48 | 4.71 |
| joint_fl_calf | 51.80 | 39.94 | 27.03 |
| joint_fr_calf | 55.80 | 38.96 | 26.71 |
| joint_hl_calf | 59.72 | 38.40 | 27.55 |
| joint_hr_calf | 53.18 | 37.81 | 26.31 |
| **ALL（汇总）** | **59.72** | **36.56** | **16.25** |

行走指标：success_rate（成功率）1.0000，mean_error_xy（线速度误差）0.070 m/s，
mean_error_yaw（角速度误差）0.079 rad/s，average_height（基座高）0.212 m，height_variance（高度方差）6.87e-4。

### 3.2 复杂地形压力工况（complex，1000 步）

| 关节 | Peak（饱和裁剪版） | **真实 Peak（放开 Y1/Y2）** | P99（放开版） | RMS（放开版） |
|---|---|---|---|---|
| joint_fl_hip | 41.73 | **77.45** | 19.98 | 6.85 |
| joint_fr_hip | 57.65 | 48.09 | 19.27 | 6.73 |
| joint_hl_hip | 47.88 | 35.80 | 22.44 | 7.15 |
| joint_hr_hip | 60.92 | 38.81 | 19.29 | 6.84 |
| joint_fl_thigh | 64.60★ | **110.88** | 20.92 | 7.58 |
| joint_fr_thigh | 64.60★ | 75.04 | 20.10 | 6.90 |
| joint_hl_thigh | 31.20 | 33.09 | 16.97 | 5.88 |
| joint_hr_thigh | 53.76 | 35.93 | 15.93 | 5.79 |
| joint_fl_calf | 64.60★ | **87.31** | 43.08 | 26.71 |
| joint_fr_calf | 64.60★ | 59.96 | 43.77 | 26.77 |
| joint_hl_calf | 62.26 | 66.42 | 42.65 | 27.29 |
| joint_hr_calf | 64.60★ | 58.72 | 42.55 | 25.97 |

★ = 首测被 Y2=64.6 上限裁剪。两版行走指标：饱和版 success_rate 0.8125 / 放开版 0.9375，
mean_error_xy 0.104–0.106 m/s，mean_error_yaw 0.149–0.166 rad/s。

> **重要观察：** 放开裁剪后 P99 与 RMS 几乎不变（典型载荷稳定），只有 Peak（峰值）显著抬升
> ——峰值是偶发的动态冲击尖峰（地形磕碰/落地瞬态），不是常态载荷。

## 4. 选型结论

| 关节组 | 真实峰值需求 | P99 参考 | 持续（RMS）需求 | 建议峰值能力（含 1.5–2.0× 裕量） |
|---|---|---|---|---|
| **thigh（大腿）** | **110.9**（fl_thigh） | ~21 | ~7.6 | **≥165–220 N·m** |
| **calf（小腿）** | **87.3**（fl_calf） | ~43 | **~27** | **≥130–175 N·m**，连续 ≥30 N·m |
| **hip（髋）** | **77.5**（fl_hip） | ~20 | ~7 | **≥115–155 N·m** |

- **统一取保守值**：全机 12 个关节可统一按 **峰值 ≥170 N·m、连续 ≥30 N·m** 选型；若分档，hip/thigh 可取峰值 ≥120 N·m 一档、calf ≥130 N·m 一档（fl_thigh 单点 110.9 决定了大腿档位）；
- **热/持续能力**由 RMS（均方根）决定：calf 显著高于其他（~27 vs ~7 N·m），是热设计瓶颈；
- 裕量口径出自 README「策略测试与力矩统计」：`Peak |tau|` 选型建议保留 1.5–2.0 倍安全余量。若只按实测 +20% 应急，最低需求为峰值 ≥135 N·m（fl_thigh）。

## 5. 复测方法（复现命令）

```bash
# 平地名义工况
conda run -n env_isaaclab_sim51 python -u scripts/rsl_rl/test_walk_torque.py \
    --task Unitree-GeesunDog-Velocity --terrain flat --steps 1000

# 复杂地形压力工况（在 unitree_actuators.py 临时把 Y1/Y2 调大后运行，测毕恢复）
conda run -n env_isaaclab_sim51 python -u scripts/rsl_rl/test_walk_torque.py \
    --task Unitree-GeesunDog-Velocity --terrain complex --steps 1000 \
    --output logs/rsl_rl/unitree_geesun_dog/<run>/complex_terrain_stats_unsaturated.csv
```

原始 CSV 位置：`logs/rsl_rl/unitree_geesun_dog/2026-10-12_20-24-42/`
（`flat_terrain_stats.csv`、`complex_terrain_stats.csv`、`complex_terrain_stats_unsaturated.csv`）；
加 `--save_raw` 可另存逐样本 `.npz`（含 torques/positions/velocities）。

## 6. 已知局限（使用本数据前请阅读）

1. **策略只在平地训练过**：complex 工况是未训练地形的压力测试，冲击尖峰偏保守（偏大）；若将来在复杂地形上训练成熟，峰值需求会回落，本结论是安全侧；
2. **PD 参数为质量缩放近似**（GO2 基准 × 质量比 2.7611，见 `UnitreeActuatorCfg_GeesunDog` docstring）：PD 刚度/阻尼影响动态冲击大小，真机若用不同增益需重测；
3. **单次测量**：每工况 1000 步 × 64 环境的统计；峰值是单点极值，P99/RMS 统计性更强。量产前建议多 seed（随机种子）复测取包络；
4. 测量在 IsaacSim（图形仿真器）中进行，接触/摩擦模型与真机有差异，选型裕量不可省。
