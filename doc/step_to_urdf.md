# STEP → URDF 转换流程（lingsi_d30w 轮足）

把 `geesun_dog_urdf/geesun-dog/lingsi_d30w/D30W轮足外发.STEP` 转成 Isaac Lab 可用的
URDF + 网格，使 `python scripts/geesun_dog/move_geesun_dog.py --variant lingsi_d30w` 能加载。

## ✅ 当前状态：自动转换已完成（2026-09-30）

```bash
conda activate env_isaaclab_sim51        # 运行环境现成：已装 cadquery-ocp 7.9.x，无需再装
python scripts/lingsi_d30w/step_to_urdf_d30w.py    # 读 STEP + 导出 17 个 STL + 生成 URDF，约 5 分钟
```

`scripts/lingsi_d30w/step_to_urdf_d30w.py` 已用 OpenCASCADE（OCP）直接解析 STEP 装配树完成转换，
产物为**正式资产，保留不删除**（均为真实文件，无符号链接）：

| 产物 | 位置 | 说明 |
|---|---|---|
| `lingsi_d30w.urdf` | `geesun_dog_urdf/geesun-dog/lingsi_d30w/urdf/lingsi_d30w.urdf` | 17 link（base + 4×hip/thigh/calf/wheel）+ 16 关节（含 4 个 `continuous` 轮关节），`--variant lingsi_d30w` 的加载点 |
| 17 个 STL | `geesun_dog_urdf/geesun-dog/lingsi_d30w/meshes/` | 真实几何（`base.stl` 64MB + 各 `link_*_*.stl` 6~35MB，共 321MB，mm→m 已换算） |
| 转换脚本 | `scripts/lingsi_d30w/step_to_urdf_d30w.py` | 路径相对脚本自身推导（`__file__` → 仓库根）。运行环境 `env_isaaclab_sim51` 已装 `cadquery-ocp 7.9.x`（序列类型叫 `TDF_LabelSequence`，无 `OCP.collections` 模块），脚本 import 兼容层覆盖两种 OCP 布局 |

重跑转换或手工标定后，`urdf/lingsi_d30w.urdf` 会被重写/变更，用 `md5sum` 与变更记录核对即可。

自动转换的运动链约定（见脚本 docstring）：STEP 坐标系 x=前(+)、y=左(+)、z=下(+)；
顶层 NAUO1-4=base、NAUO5-8=四腿 hip、NAUO9-12=四腿总成；腿内零件按 bbox z 中心分
thigh（z<150）/calf（150≤z<400）/wheel（z≥400）；hip 轴沿 x（侧摆）、thigh/calf/轮轴沿 y（俯仰/轮转）。

**关节原点为自动估计值，待实测标定**（膝关节取防油 30202 轴承对中心、轮心取轮组件 bbox 中心，
精度约 ±1 cm；hip 轴、thigh 俯仰轴为估计）；关节限位（hip ±0.8、thigh [-2,2.5]、calf [-2.5,0.5] rad）
参照 dog1 给定，需按 D30W 实际行程修正。质量/惯量为粗估。标定后直接改
`geesun_dog_urdf/geesun-dog/lingsi_d30w/urdf/lingsi_d30w.urdf` 即可。

以下为原始手工转换流程（CAD 工具路线），供需要重做运动链或校准时参考。

## 0. 目标产物与代码契约（必须满足）

```
geesun_dog_urdf/geesun-dog/lingsi_d30w/
├── D30W轮足外发.STEP            # 原始文件，保留不动
├── urdf/
│   └── lingsi_d30w.urdf         # 文件名任意，urdf/*.urdf 中排序第一个会被使用
└── meshes/
    ├── base.stl                 # 每个 link 一个二进制 STL（base 躯干）
    ├── link_fl_hip.stl
    └── ...
```

`unitree_rl_lab/assets/robots/unitree.py` 的 `_prepare_geesun_dog_urdf()` 对非 dog1 变体的约定：

1. **URDF 位置**：`lingsi_d30w/urdf/*.urdf` 或 `lingsi_d30w/*.urdf`（取 sorted 后第一个）。
2. **mesh 路径必须写绝对路径**（如 `/home/css/work/unitree/rl/Geesun_robot_rl_lab/geesun_dog_urdf/geesun-dog/lingsi_d30w/meshes/base.stl`）。
   `package://` 重写只处理 `package://dog1/`、`package://dog921/` 前缀，其他前缀**不会**被替换。
3. **关节限位原样保留**（该分支 `has_real_limits=True`，不做任何限位修补），URDF 必须自带
   真实的 `lower/upper`；`effort="0" velocity="0"` 会被自动替换成 `effort="100" velocity="25"`。
4. **关节命名契约（轮子关节必须包含在内）**：
   - 12 个腿关节：`joint_fl_hip / joint_fr_hip / joint_hl_hip / joint_hr_hip`、
     `joint_fl_thigh / joint_fr_thigh / joint_hl_thigh / joint_hr_thigh`、
     `joint_fl_calf / joint_fr_calf / joint_hl_calf / joint_hr_calf`（trot 正弦驱动）。
   - 4 个轮子关节：**`joint_fl_wheel / joint_fr_wheel / joint_hl_wheel / joint_hr_wheel`（必须）**，
     名字含 `wheel` 的关节由脚本以 `--wheel_speed`（默认 10 rad/s）匀速旋转驱动（`move_geesun_dog.py`
     已支持，无需改代码）。
   - 脚本对未知关节名自动容错（base=0/amp=0，不再 KeyError）；但验证轮足必须按上述命名建轮子关节，
     否则轮子不会被驱动、测试覆盖不到轮子。
   - 轮子关节类型用 `continuous`（或限位很宽的 `revolute`），否则线性递增的旋转目标会被限位夹住。
5. 空 STL 自动修复（生成占位圆柱）只对命名恰好为
   `{Link,link}_{fr,fl,hl,hr}_hip.STL` 的文件生效；其他空网格会直接导致导入器崩溃，
   导出后请自行检查 STL 非空（文件大小 > 84 字节）。

## 1. 工具准备

任选其一：

- **FreeCAD**（推荐，免费，GUI + `freecadcmd` 命令行均可）：`sudo apt install freecad`
- SolidWorks（STEP 若源自 SW，原生装配约束最完整）
- Onshape（免费网页版，可直接导出 STL 和读取装配关节轴）

本文以 FreeCAD 为例。

## 2. 拆分装配、确定运动链

1. 用 FreeCAD 打开 `D30W轮足外发.STEP`（213 MB，导入需几分钟）。
2. 在模型树里确认装配层级，确定机器人的运动链：
   - `base_link`（躯干）
   - 每条腿：`hip`（侧摆）→ `thigh`（俯仰）→ `calf`（俯仰）→ 足端（轮/足垫）
   - D30W 是轮足构型，确认每条腿是否带**轮毂电机关节**（见契约 4）。
3. 为每个活动 link 命名（沿用契约 4 的关节名前缀）：
   `link_fl_hip`、`link_fl_thigh`、`link_fl_calf`、…（fl/fr/hl/hr 四条腿）。

## 3. 导出 STL 网格

每个 link 导出一个二进制 STL，**必须缩放到米**（FreeCAD 内部是 mm，STL 无单位，
Isaac 的 URDF 导入器按米读顶点；漏掉这一步模型会大 1000 倍）。

### 3a. FreeCAD GUI 手动导出（link 少时）

1. 选中一个 link 的 Shape → 文件 → 导出 → STL。
2. 用 Mesh Design 工作台：Meshes → 创建网格自形状（偏差 0.5 mm）→ 缩放 0.001 → 导出二进制 STL。

### 3b. freecadcmd 批量导出（推荐）

保存以下脚本为 `export_d30w_stl.py`，在仓库外的临时目录运行（转换产物再拷贝进
`lingsi_d30w/meshes/`）：

```python
"""freecadcmd export_d30w_stl.py <step文件> <输出目录>"""
import os
import sys

import FreeCAD
import Mesh
import MeshPart
import Part

step_path, out_dir = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
os.makedirs(out_dir, exist_ok=True)

doc = FreeCAD.open(step_path)
mat = FreeCAD.Matrix()
mat.scale(0.001, 0.001, 0.001)  # mm -> m

for obj in doc.Objects:
    if not hasattr(obj, "Shape") or obj.Shape.isNull():
        continue
    shape = obj.Shape.transformGeometry(mat)  # 缩放到米
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.0005, Relative=False)
    name = obj.Label.replace(" ", "_")  # 需与 URDF 中 link/mesh 文件名对应
    path = os.path.join(out_dir, f"{name}.stl")
    mesh.write(path)
    print(f"{path}: {mesh.CountFacets} facets")
```

```bash
freecadcmd export_d30w_stl.py "geesun_dog_urdf/geesun-dog/lingsi_d30w/D30W轮足外发.STEP" /tmp/d30w_meshes
```

导出后检查：每个 STL > 84 字节（80 字节头 + 0 三角形的空文件会让 Isaac 导入器崩溃），
且 `obj.Label` 与第 2 步的 link 命名一致。

## 4. 确定关节参数

从 CAD 装配约束/图纸读取每个关节的三项参数，填入 URDF：

| 参数 | 含义 | 获取方法 |
|---|---|---|
| `origin xyz rpy` | 关节在父 link 坐标系中的位置/姿态 | 装配约束的配合面圆心、轴向量；注意单位是**米** |
| `axis xyz` | 转轴方向（单位向量） | 关节铰链轴。**注意坐标系差异**：自动转换（STEP 坐标系 x=前、y=左、z=下）用 hip=+X（侧摆）、thigh/calf/轮=+Y；下文手工模板（常规 z 向上）hip 侧摆多为 +Y、thigh/calf 俯仰多为 +Y，按各自模板核对 |
| `limit lower upper` | 关节限位（rad） | 装配行程；`effort`/`velocity` 不要写 0（会被改成 100/25） |

建议在 FreeCAD 里选中配合面读圆心坐标，或用 `obj.Placement.Base` 批量打印各 link 原点。

## 5. 编写 URDF

`lingsi_d30w/urdf/lingsi_d30w.urdf`，骨架模板（mesh 路径按契约 2 写绝对路径）：

```xml
<?xml version="1.0"?>
<robot name="lingsi_d30w">
  <!-- mesh 根目录写绝对路径 -->
  <link name="base_link">
    <visual>
      <geometry><mesh filename="/home/css/work/unitree/rl/Geesun_robot_rl_lab/geesun_dog_urdf/geesun-dog/lingsi_d30w/meshes/base.stl" scale="1 1 1"/></geometry>
    </visual>
    <collision>
      <geometry><mesh filename="/home/css/work/unitree/rl/Geesun_robot_rl_lab/geesun_dog_urdf/geesun-dog/lingsi_d30w/meshes/base.stl"/></geometry>
    </collision>
    <inertial>
      <mass value="8.0"/>
      <inertia ixx="0.05" ixy="0" ixz="0" iyy="0.05" iyz="0" izz="0.05"/>
    </inertial>
  </link>

  <!-- 一条腿示例（fl）；fr/hl/hr 同构，注意镜像腿的 axis 符号与限位方向 -->
  <link name="link_fl_hip">
    <visual>
      <geometry><mesh filename="/home/css/work/unitree/rl/Geesun_robot_rl_lab/geesun_dog_urdf/geesun-dog/lingsi_d30w/meshes/link_fl_hip.stl"/></geometry>
    </visual>
    <collision>
      <geometry><mesh filename="/home/css/work/unitree/rl/Geesun_robot_rl_lab/geesun_dog_urdf/geesun-dog/lingsi_d30w/meshes/link_fl_hip.stl"/></geometry>
    </collision>
    <inertial>
      <mass value="1.0"/>
      <inertia ixx="0.01" ixy="0" ixz="0" iyy="0.01" iyz="0" izz="0.01"/>
    </inertial>
  </link>

  <joint name="joint_fl_hip" type="revolute">
    <parent link="base_link"/>
    <child link="link_fl_hip"/>
    <origin xyz="0.15 0.10 0.0" rpy="0 0 0"/>   <!-- 实测值 -->
    <axis xyz="0 1 0"/>                          <!-- 实测值 -->
    <limit lower="-0.8" upper="0.8" effort="40" velocity="20"/>  <!-- 实测值 -->
  </joint>

  <!-- joint_fl_thigh: link_fl_hip -> link_fl_thigh，其余同理 -->
  <!-- joint_fl_calf:  link_fl_thigh -> link_fl_calf -->

  <!-- 轮子（必须）：挂在 link_fl_calf 下，type="continuous"，命名含 wheel -->
  <link name="link_fl_wheel">
    <visual>
      <origin rpy="1.5708 0 0"/>   <!-- 圆柱默认沿 z，转到关节轴方向 -->
      <geometry><mesh filename="/home/css/work/unitree/rl/Geesun_robot_rl_lab/geesun_dog_urdf/geesun-dog/lingsi_d30w/meshes/link_fl_wheel.stl"/></geometry>
    </visual>
    <collision>
      <geometry><cylinder radius="0.08" length="0.04"/></geometry>  <!-- 碰撞用简单圆柱即可 -->
    </collision>
    <inertial>
      <mass value="1.5"/>
      <inertia ixx="0.005" ixy="0" ixz="0" iyy="0.005" iyz="0" izz="0.005"/>
    </inertial>
  </link>

  <joint name="joint_fl_wheel" type="continuous">
    <parent link="link_fl_calf"/>
    <child link="link_fl_wheel"/>
    <origin xyz="0 0 -0.25" rpy="0 0 0"/>   <!-- 实测值：轮心位置 -->
    <axis xyz="0 1 0"/>                     <!-- 实测值：轮轴方向 -->
    <limit effort="40" velocity="20"/>      <!-- continuous 无 lower/upper -->
  </joint>
</robot>
```

要点：

- 12 个腿关节 + 4 个轮子关节（`joint_{fl,fr,hl,hr}_wheel`）都要建（契约 4）。
- `inertial` 必须每条 link 都有（质量 > 0，惯量对角正数），否则 PhysX 报错。
- 镜像腿（fr/hr）的 `origin xyz` 的 y 取负、`axis` 符号按实际铰链方向核对，
  限位上下界方向相反（参考 dog1 的 `dog921.urdf` 写法）。
- 轮子关节用 `continuous`；`--wheel_speed` 是匀速旋转目标，被限位夹住就测不出轮转。

## 6. 验证

```bash
# 1. 确认契约：URDF 位置、mesh 绝对路径、关节名、STL 非空
ls geesun_dog_urdf/geesun-dog/lingsi_d30w/urdf/*.urdf
grep -c 'filename="/' geesun_dog_urdf/geesun-dog/lingsi_d30w/urdf/lingsi_d30w.urdf
grep -o 'joint_[a-z]*_[a-z]*' geesun_dog_urdf/geesun-dog/lingsi_d30w/urdf/lingsi_d30w.urdf | sort -u
find geesun_dog_urdf/geesun-dog/lingsi_d30w/meshes -size -85c   # 应无输出

# 2. 不使用缓存的完整测试（与 dog1 流程一致）
rm -rf /tmp/IsaacLab/geesun_dog
python scripts/geesun_dog/move_geesun_dog.py --variant lingsi_d30w --num_steps 300 --headless
```

通过标准（对照 README 的 dog1 验证步骤）：

1. 控制台打印 `Geesun variant: lingsi_d30w` 和
   `Using converted USD: /tmp/IsaacLab/geesun_dog/lingsi_d30w/lingsi_d30w.usd`（无异常栈）。
2. `Loaded robot joints:` 列出 **16 个**关节名（12 腿关节 + `joint_fl_wheel/joint_fr_wheel/joint_hl_wheel/joint_hr_wheel`）。
3. `[step 0]` 的 `joint_pos` 等于站姿基准（thigh/calf 的 base 角、轮子为 0），root 高度 ≈ `--root_z`。
4. `[step 100]` 起腿关节值偏离基准且对角腿成对反相（fl≈hr、fr≈hl），无 NaN、无关节飞掉。
5. **轮子验证（必须）**：`[step 100]` 起 4 个轮子关节角持续变化（不再为 0）。理想情况下步数翻倍
   角度增量近似翻倍（线性旋转）；注意 PD 追匀速目标有滞后（k=30/b=1 追 10 rad/s 的斜坡滞后明显），
   且大角度读数可能 wrap 到 [-π, π] 造成数值跳变——建议用 `--wheel_speed 3` 验证线性、
   用 `--wheel_speed 0` 对照确认轮子静止，两者差异即轮子驱动生效的证据。

## 7. 常见问题

| 症状 | 原因 | 处理 |
|---|---|---|
| 模型大 1000 倍/悬浮 | STL 未从 mm 缩放到 m | 导出脚本里 `mat.scale(0.001,...)` 不可省 |
| URDF 导入器崩溃/段错误 | 空 STL（80 字节头 + 0 三角形） | 检查 `find ... -size -85c`；仅 `*_hip.STL` 命名可被自动修复 |
| `FileNotFoundError: Geesun dog URDF is unavailable` | URDF 没放进 `urdf/` 或目录根 | 对照契约 1 |
| 视觉网格不显示/路径找不到 | 用了 `package://` 或相对路径 | 对照契约 2，改绝对路径 |
| 轮子不转（关节角恒为 0） | 关节名不含 `wheel`，或关节被限位夹住 | 命名 `joint_xx_wheel` 并用 `type="continuous"`（契约 4） |
| 轮子转但角度数值乱跳 | PD 落后 + 角度 wrap 到 [-π, π] | 用 `--wheel_speed 3` 对照 `--wheel_speed 0` 验证增量（验证标准 5） |
| 关节限位奇怪（±π 或全 0） | STEP 导出不带限位 | 对照第 4 步补真实限位 |
| 塌缩成一堆/腿穿模 | 惯量或质量为 0；碰撞网格自交 | 补 `inertial`；碰撞可先用简化包围盒 |
