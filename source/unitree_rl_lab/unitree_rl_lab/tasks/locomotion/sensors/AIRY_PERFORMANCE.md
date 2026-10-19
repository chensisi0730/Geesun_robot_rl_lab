# Airy 96线激光雷达 —— 仿真建模与性能实测记录

> 记录日期：2026-10-15　硬件来源：实机 PRO 版规格（用户确认）+ 产品图纸
> 相关代码：`sensors/airy_cfg.py`（规格与配置）、`sensors/airy_bev.py`（BEV 投影）、
> 验证脚本 `scripts/diagnose/verify_airy_lidar.py` / `verify_airy_bev.py`

## 一、实机规格与建模决策

| 项 | 实机 PRO 版 | 仿真建模 | 备注 |
|---|---|---|---|
| 激光雷达数量 | **2 台**（头部 + 尾部） | **1 台**（头部） | 实测约束，见第五节 |
| 线数（垂直） | 96 | 96 | **不可降**，这是台阶高度分辨率的来源 |
| 视场角 | 水平 360° × 垂直 90°（半球） | 同 | 半球**朝下**，已实测验证 |
| 测距 | 30 m @ 10% 反射率 | `max_distance=30.0` | 近裁剪 0.2 m |
| 水平角分辨率 | 未公开（数字扫描，非机械旋转） | **0.8°**（见第四节实测） | 唯一可调旋钮，且只影响显存 |
| 更新频率 | 主动式 | 50 Hz（与控制同步） | 非 30 fps 相机，无需帧复用 |
| 摄像头 | 2 个（前后各 1），130° 广角 640×360 @ 30fps，普通 RGB | **暂不建模** | 无深度，且需渲染路线，会把训练规模打到几百 envs |

**建模路线**：光线投射（`MultiMeshRayCasterCfg` + `LidarPatternCfg`），不渲染图像。
原因是保住 4096 envs 的训练规模 —— 实测渲染相机做不到。

**为什么用 `MultiMeshRayCasterCfg` 而不是 `RayCasterCfg`**：
`RayCaster` 在 `len(mesh_prim_paths) == 1` 时**只读该路径下第一个匹配的 `UsdGeomMesh`**
（`isaaclab/sensors/ray_caster/ray_caster.py` 的 `get_first_matching_child_prim`），
其余网格被静默丢弃。实测：地面先生成时，94% 的命中点落在地面平面，
z > 0.10 m 的障碍完全检测不到。对只扫地面的 `height_scanner` 够用，对 LiDAR 完全不可用。
`MultiMeshRayCasterCfg` 继承自 `RayCasterCfg`（保留 `pattern_cfg`，因此仍支持 `LidarPatternCfg`），
但会对**所有**列出的网格投射；其 `data.ray_hits_w` 布局不变，另有 `ray_mesh_ids` 标明命中来源。

## 二、半球朝向：已实测确认为「朝下」

这是整个建模唯一未验证的假设（规格只写"垂直90°半球"，没说哪个半球）。用地面覆盖判定：

```
[VERDICT] DOWN: ground covered out to 15.11 m  ->  the 90 deg hemisphere points DOWN
```

三种朝向的判别标准：

| 俯视/侧视图表现 | 结论 |
|---|---|
| 完整地面环带（覆盖到 15.11 m） | ✅ 朝下（当前设置） |
| 只有地平线附近窄带 | 朝上，需翻转 `AIRY_VERTICAL_FOV_RANGE` |
| 大量天空 | 装反了 |

若将来实机确认是朝上，只需改 `airy_cfg.py` 的 `AIRY_VERTICAL_FOV_RANGE = (0.0, 90.0)`，其余不动。

## 三、BEV 观测：几何精度实测

点云 86,400 rays/env 无法直接进观测（维度爆炸），故投影为**极坐标最大高度栅格**：
36 方位扇区（360° 全向，10°/bin）× 20 距离环（log 间距，近密远疏）= **720 维**。

场景：平地 + 0.15 m 台阶@3 m + 0.30 m 矮箱@5 m + 0.90 m 高箱@5 m(侧) + 2.0 m 墙@6 m

```
all_passed: True
  True  step_top@(az=0,r=3m)~0.15                      实测 0.150（误差 0）
  True  lowbox_top@(az=0,r=5m)~0.3                     实测 0.277（误差 0.023）
  True  tall_obstacles_saturate_at_sensor_height(0.5m, downward hemisphere)
  True  forward_rising_profile(step<box<wall)
```

前向剖面（20 个距离环的真实高度）：

| ring | 9 | 10 | 11 | 12 | 13 | 14 | 15 |
|---|---|---|---|---|---|---|---|
| 高度 m | 0.150 | 0.150 | 0.150 | 0 | 0.277 | 0.500 | 0 |
| 对应真值 | ← 台阶 0.15 m（r≈2.4~4.3）→ | | | ←矮箱→ | ←墙→ | |

### ⚠️ 固有限制：高度天花板 = 传感器安装高度

`wall_top=0.500`（墙真值 2.0 m）与 `highbox=0.500`（真值 0.9 m）**不是缺陷，是物理正确**：
传感器装在 0.5 m 高且半球朝下，**物理上不可能看到高于自身安装高度物体的顶面**。

- 对爬楼梯**无影响**：台阶 0~0.2 m，远低于 0.5 m，实测 0.15 m 精确还原。
- 但若将来需要感知"高于 0.5 m 的障碍"（上高台、越栏杆），朝下半球的 Airy 做不到，
  届时需调整安装高度或改为双半球。

## 四、性能实测（RTX 5090 / 32 GB，50 Hz 控制预算 = 20 ms/step）

测量命令（`scripts/diagnose/verify_airy_lidar.py`）：

```bash
python scripts/diagnose/verify_airy_lidar.py --headless --envs 4096 --horizontal_res 0.8
```

| envs | h_res | rays/env | 总 rays | ms/step | Mrays/s | 占 20 ms 预算 | 显存 | 结果 |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.4° | 86,400 | 86 K | 0.40 | 214 | 2.0% | — | OK |
| 64 | 0.4° | 86,400 | 5.53 M | 1.53 | 3,623 | 7.7% | — | OK |
| 512 | 0.4° | 86,400 | 44.2 M | 0.35 | 125,392 | 1.8% | — | OK |
| 4096 | 0.4° | 86,400 | 353.9 M | 0.39 | 901,361 | 2.0% | ~28 GB → 需再分配 3.96 GB 失败 | ❌ OOM |
| **4096** | **0.8°** | **43,200** | **176.9 M** | **0.44** | **398,382** | **2.2%** | **26.2 / 32.6 GB** | ✅ 通过 |

### 三个结论

**1）算力完全可行，余量约 25 倍**

4096 envs（实际训练规模）下整套 Airy 96 线只占 **0.39~0.44 ms/step = 控制预算的 ~2%**。

**2）512 → 4096 开销几乎不变，说明 GPU 并行已饱和**

envs 翻 8 倍，时间只从 0.35 涨到 0.39 ms。**反过来，64 envs 反而更慢（1.53 ms）**，
是小规模下固定开销（kernel launch + CPU-GPU 同步）主导——
**小规模测量数字不能用来外推，必须在目标 env 数上实测**。

**3）真正的瓶颈是显存，且是硬约束**

`_update_ray_infos` 需要再分配一个同尺寸张量：
`4096 × 86,400 × 3 × 4 B = 3.96 GiB`，叠加 Isaac Sim 与训练占用后在 32 GB 卡上 OOM。

## 五、由此确定的两项建模参数

### `AIRY_HORIZONTAL_RES`: 0.4° → **0.8°**

```python
# airy_cfg.py
AIRY_HORIZONTAL_RES: float = 0.8
```

**降分辨率不省算力**（0.39 → 0.44 ms，反而略增，因为垂直 96 线才是计算主导），
**纯粹是为省显存**。精度无损的三重证据：

1. BEV 精度不变：0.8° 时一个 10° 方位 bin 仍有 **12.5 个采样点**，
   而栅格取的是 bin 内**最大值**——台阶棱边是面状目标而非点状目标，统计上完全够。
2. 命中率不变：`0.4° → 85256/86400 = 98.68%`，`0.8° → 42630/43200 = 98.68%`，完全一致。
3. 半球朝向判定不变：`VERDICT DOWN` 保持。

### LiDAR 实例数：2 台 → **1 台**

**这是实测硬约束，不是建模偷懒**：Airy 本身 360° 全向，1 台已覆盖前后，
第 2 台**不增加任何信息**却要多吃 ~8~12 GB 显存 → 必然 OOM。
`AIRY_TAIL_OFFSET` 常量保留，仅当未来消融证明尾部扫描有独立信息时才加回。

### 显存保护

`velocity_env_cfg.py` 的 `__post_init__` 里加了断言，env 数 × rays/env 估算超阈值直接报错。

⚠️ **不能用"rays × 3 × 4 bytes × 2 buffers"估算**——这种朴素公式对实测 26.2 GB 的场景只算出 **4.0 GB**，
漏掉了 per-env 的 mesh BVH 和 ray-info 缓冲，**低估 6.6 倍**，是比没有保护更危险的假保护
（0.4° 时它算 8.0 GB < 阈值，断言不触发但实际必然 OOM）。

改用两点实测标定：

```
total_GB ≈ 2.0（Isaac Sim + mesh BVH 固定开销）
         + 1.4e-7 × rays_per_env × num_envs
```

该公式在高 ray 数处**故意高估**（0.4° 预测 ~51 GB，真值 ~31.7 GB），
宁可误报也不静默 OOM。实测输出：

```
[airy] 4096 envs x 43200 rays/env ~ 26.8 GB VRAM     # 实测 26.2 GB，误差 2%
```

---

## 六、消融配置（第 3 步产物）

四个 task **共享同一份 policy 观测（实测 57 维 proprioception）**，只改 critic 特权观测，
因此 actor 结构不变、已训 checkpoint 的 actor 可复用：

| 配置 | task id 后缀 | critic 外部感知 | critic 维度（实测） |
|---|---|---|---|
| **A** 基线 | `""`（现有 task） | height_scanner 187 | **263** |
| **B** 替代 | `-AiryReplace` | Airy BEV 720（无 height_scanner） | **796** |
| **C** 叠加 | `-AiryStacked` | height_scanner 187 + Airy BEV 720 | **983** |
| **D** 纯 proprio | `-ProprioOnly` | 无 | **76** |

维度由 `scripts/diagnose/smoke_env_obs.py` **实测**得到（非推导）：
policy = `base_ang_vel 3 + projected_gravity 3 + velocity_commands 3 + joint_pos_rel 16 +
joint_vel_rel 16 + last_action 16 = 57`，action_dim = 16
（D30W 是 **16** 个驱动关节，不是 12）。critic 差值自洽校验：
796−263 = 533、983−796 = 187、263−76 = 187，与 height_scanner=187 / airy_bev=720 吻合。

- **B 是终点形态**：去掉仿真特权信息，policy 的感知形状与实机一致，可真正 sim2real。
- **D 是下界**：完全无外部感知时性能的下限，LiDAR 必须超过它才有意义。
- 各配置写**各自独立的 `experiment_name`**，可在 TensorBoard 并排对比。
- ⚠️ 改 critic 观测会改变 value net 输入层，**四个配置都必须从头训**，checkpoint 之间不可迁移。

### ⚠️ 基线必须保持零改动

LiDAR 只通过 `RobotSceneCfgAiry`（scene 子类）引入，**仅 B/C 使用**。基线的
`RobotSceneCfg` 与 `CriticCfg` 不含任何 LiDAR 字段。三个原因：

1. 消融对照的前提是 A 不带 LiDAR，否则 A↔B 的差异不再是"有无 LiDAR"
2. 基线改动会让**所有已训 checkpoint 作废**（critic 263 → 983）
3. 基线会白占 ~26 GB 显存去读一个它根本不用的传感器

冒烟测试正是靠这一条抓到的：早期版本把 LiDAR 直接加进了基线，仅靠"检查配置对象"无法发现。

## 七、尚未实施（按计划）

- **域随机化**：`AIRY_RANDOMISATION` 已定义外参 ±3 cm/±2°、测距噪声、丢点率 0~15%、
  延迟 0~50 ms 等范围，但**尚未接入** `randomize_ray_caster` 事件项。
- **policy 接入**：当前仅 critic 观测，policy 仍是 57 维 proprioception。接入 policy 会让**所有旧 checkpoint 作废**。
- **RGB 摄像头**：已确认暂不接入策略（无深度 + 渲染路线代价过大）。

## 九、height_scanner（高度扫描传感器）观测被 clip 饱和 —— 2026-10-15 实测发现

### 现象

`mdp.height_scan`（Isaac Lab `isaaclab/envs/mdp/observations.py:297`）：

```python
return sensor.data.pos_w[:, 2] - sensor.data.ray_hits_w[..., 2] - offset   # offset 默认 0.5
```

任务把传感器吊在 `base_link` 上方 20 m（`OffsetCfg(pos=(0,0,20))`），`ray_alignment="yaw"`
（光线垂直向下），于是：

```
sensor_pos_w.z = base_z + 20 ≈ 0.61 + 20 = 20.61      # lingsi_d30w 站立高度（unitree.py:1274）
hit_z          ≈ 0 .. 0.23                            # 地形面 / 楼梯踏步
raw            ≈ 19.9 .. 20.1
clip=(-1.0, 5.0)  →  187 个格子全部 = 5.0（常数）
```

**即 height_scanner 的 187 维在修复前是 187 个常数，不携带任何地形信息。**
A（基线）与 D（ProprioOnly，纯本体感知）的差值衡量的是"多 187 个常数输入"，不是高度感知收益。
Isaac Lab 上游 stock 配置同病（`isaaclab_tasks/.../velocity/velocity_env_cfg.py:112-185`：
`offset (0,0,20)` + 默认 `offset=0.5` + `clip=(-1,1)` → 饱和在 1.0）。

### 修复（1 处 1 个数，观测维度不变）

```python
height_scanner = ObsTerm(
    func=mdp.height_scan,
    params={"sensor_cfg": SceneEntityCfg("height_scanner"), "offset": 20.5},  # 抵消 20 m 吊挂
    clip=(-1.0, 1.0),
)
# 输出 = base_z - hit_z - 0.5 ∈ [-0.3, +0.2]，0.05~0.23 m 踏步全分辨率可见
```

已同步改动的 3 处：`lingsi_d30w/velocity_env_cfg.py` 的 `ObservationsCfg.CriticCfg`（config A）
与 `ObservationsCfgAiryStacked.CriticCfg`（config C）、`go2/velocity_env_cfg.py` 的 `CriticCfg`
（保证 GO2 ↔ D30W 跨体消融口径一致）。

**维度不变（187）** → value（价值）网络输入层 shape 不变 → checkpoint（检查点）shape 兼容；
但这 187 维语义变了，严格消融仍建议 fresh（重训）。

### 验证（exit 0 = ALIVE，exit 1 = SATURATED）

```bash
python scripts/diagnose/verify_height_scan_alive.py --headless --num_envs 16 --offset 20.5
# 产物 outputs/verify_height_scan/stats.json
# 判据：clipped.std >= 0.02 且 frac_at_upper_clip < 0.99
```

脚本同时**逐项实测观测宽度**（不硬编码），坐实消融维度表：

| 配置 | 组成 | critic 维度 | policy 维度 |
|---|---|---|---|
| A 基线 | 76 + 187 | **263** | 57 |
| B 替代 | 76 + 720 | **796** | 57 |
| C 叠加 | 76 + 187 + 720 | **983** | 57 |
| D 下界 | 76 | **76** | 57 |

（旧文档里的 936 / 956 / 1676 / 216 与 policy 49 是硬编码假设，已作废。）

### 对既有结论的影响

- 已完成的 `unitree_geesun_lingsi_d30w_ht_stairs*` 各 run 的 critic 里，那 187 维是常数
  → 这些 run 的 TensorBoard 曲线**不能**用来论证 height_scanner 收益；
- 修复后必须 fresh 重训 A，才能与 D 做有意义的减法；
- 感知路线（激光雷达 → 17×11 感知高度图，config E）必须与修复后的 A **同口径**
  （`base_z - hit_z - 0.5`、同 clip、同 187 维），否则 A vs E 比较的是两个不同尺度的高度项。

---

## 十、复现命令汇总

```bash
# height_scanner 观测是否活着（A 基线先决条件）
python scripts/diagnose/verify_height_scan_alive.py --headless --num_envs 16 --offset 20.5
python scripts/diagnose/verify_height_scan_alive.py --headless --num_envs 16 \
    --task Unitree-GeesunDog-LingsiD30W-Velocity-AiryStacked
```

```bash
# 第 1 步：传感器建模 + 半球朝向 + 几何精度
python scripts/diagnose/verify_airy_lidar.py --headless --envs 1

# 性能实测（务必在目标 env 数上跑，小规模数字不可外推）
python scripts/diagnose/verify_airy_lidar.py --headless --envs 4096 --horizontal_res 0.8

# 第 2 步：BEV 栅格 vs 已知几何
python scripts/diagnose/verify_airy_bev.py --headless
```

产物落在 `outputs/verify_airy*/`：`stats.json`（数值）、`bev.png`（BEV 热力图）、
`points_env0.csv` / `points_head.ply`（原始点云）。