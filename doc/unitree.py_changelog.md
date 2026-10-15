# `unitree.py` 修改历史（modification history）

> 仓库相对路径：`source/unitree_rl_lab/unitree_rl_lab/assets/robots/unitree.py`  
> 由 `scripts/tools/export_file_history.py` 生成（`git log --follow`），生成时间：2026-10-14 16:05  
> 共 **10** 次提交触及该文件。

## 提交总览（overview，按时间倒序）

| # | 日期 | 时间 | 哈希（hash） | 作者 | 增/删 | 提交标题（subject） |
|---|---|---|---|---|---|---|
| 1 | 2026-10-14 | 15:35 | `1029bea` | 陈斯斯 | +20 / -18 | fix(actuators): 将D30W电机参数从供应商数据表改为URDF源 |
| 2 | 2026-10-14 | 09:49 | `6558f95` | 陈斯斯 | +206 / -45 | feat(GeesunDog): 为轮足变体lingsi_d30w添加独立任务配置和执行器参数 |
| 3 | 2026-10-12 | 23:33 | `f938bef` | 陈斯斯 | +2 / -3 | feat(geesun_dog): 新增GeesunDog机器人支持及相关训练配置 |
| 4 | 2026-10-10 | 10:28 | `3dc8f5c` | 陈斯斯 | +89 / -19 | feat(geesun_dog): 支持多变体配置（四足/轮式）并完善训练监控逻辑 |
| 5 | 2026-09-30 | 14:53 | `901227f` | 陈斯斯 | +61 / -25 | feat: 新增lingsi_d30w轮足变体资产及自动转换脚本 |
| 6 | 2026-09-24 | 11:09 | `ef3a611` | 陈斯斯 | +96 / -71 | feat: 更新GeesunDog为dog921新版资产并添加仿真支持 |
| 7 | 2026-09-17 | 22:26 | `5e63990` | 陈斯斯 | +9 / -2 | feat(go2, curriculum): 实现两阶段速度课程与地形性能监控 |
| 8 | 2026-09-07 | 23:09 | `700b329` | chensisi | +267 / -0 | feat: add Geesun Dog (dog1) quadruped robot support |
| 9 | 2026-08-31 | 23:18 | `11b3514` | chensisi | +2 / -2 | 更新Unitree模型和ROS目录路径 |
| 10 | 2026-07-11 | 00:34 | `d53498c` | chensisi | +717 / -0 | Initial commit |

## 逐提交详情（detail）

### 1. 2026-10-14 15:35 · `1029bea` · fix(actuators): 将D30W电机参数从供应商数据表改为URDF源

- 作者（author）：陈斯斯
- 该文件改动：+20 / -18 行
- 关键改动位置（hunk 上下文）：
  - `@@ -1009,21 +1009,23 @@ def _prepare_geesun_dog_urdf() -> None:
  - `@@ -1177,10 +1179,10 @@ def ensure_geesun_dog_usd() -> str:
  - `@@ -1188,21 +1190,21 @@ if GEESUN_DOG_WHEEL_LEG:
- 提交正文（commit body）：
  > 更新lingsi_d30w电机的扭矩、速度限制和扭矩-速度曲线参数，依据2026-10-14项目决策，以供应商URDF为参数来源，替代原有的Excel数据表。同时修正了正则表达式中参数归一化逻辑，确保不再超上限设置限制。

### 2. 2026-10-14 09:49 · `6558f95` · feat(GeesunDog): 为轮足变体lingsi_d30w添加独立任务配置和执行器参数

- 作者（author）：陈斯斯
- 该文件改动：+206 / -45 行
- 关键改动位置（hunk 上下文）：
  - `@@ -753,17 +753,48 @@ GEESUN_DOG_VARIANT_SPECS: dict[str, dict] = {
  - `@@ -873,12 +904,24 @@ def _prepare_geesun_dog_urdf() -> None:
  - `@@ -909,6 +952,104 @@ def _prepare_geesun_dog_urdf() -> None:
  - `@@ -1035,21 +1176,51 @@ def ensure_geesun_dog_usd() -> str:
  - `@@ -1074,7 +1245,11 @@ GEESUN_DOG_CFG = UnitreeArticulationCfg(
  - `@@ -1089,31 +1264,17 @@ GEESUN_DOG_CFG = UnitreeArticulationCfg(
- 提交正文（commit body）：
  > - 新增dog1和lingsi_d30w两个独立任务注册，移除旧的通用入口

### 3. 2026-10-12 23:33 · `f938bef` · feat(geesun_dog): 新增GeesunDog机器人支持及相关训练配置

- 作者（author）：陈斯斯
- 该文件改动：+2 / -3 行
- 关键改动位置（hunk 上下文）：
  - `@@ -1036,11 +1036,10 @@ def ensure_geesun_dog_usd() -> str:
- 提交正文（commit body）：
  > 新增内容：

### 4. 2026-10-10 10:28 · `3dc8f5c` · feat(geesun_dog): 支持多变体配置（四足/轮式）并完善训练监控逻辑

- 作者（author）：陈斯斯
- 该文件改动：+89 / -19 行
- 关键改动位置（hunk 上下文）：
  - `@@ -741,6 +741,48 @@ GEESUN_DOG_DIR = next((d for d in _GEESEN_DOG_CANDIDATES if os.path.isdir(d)), _
  - `@@ -990,6 +1032,44 @@ def ensure_geesun_dog_usd() -> str:
  - `@@ -1010,9 +1090,13 @@ GEESUN_DOG_CFG = UnitreeArticulationCfg(
  - `@@ -1033,20 +1117,6 @@ GEESUN_DOG_CFG = UnitreeArticulationCfg(
- 提交正文（commit body）：
  > - 新增GeesunDog多变体规格配置，支持footed dog1和wheel-legged lingsi_d30w

### 5. 2026-09-30 14:53 · `901227f` · feat: 新增lingsi_d30w轮足变体资产及自动转换脚本

- 作者（author）：陈斯斯
- 该文件改动：+61 / -25 行
- 关键改动位置（hunk 上下文）：
  - `@@ -734,6 +734,21 @@ _GEESEN_DOG_CANDIDATES = [
  - `@@ -800,20 +815,33 @@ def _prepare_geesun_dog_urdf() -> None:
  - `@@ -903,12 +931,13 @@ def _prepare_geesun_dog_urdf() -> None:
  - `@@ -916,26 +945,32 @@ def _prepare_geesun_dog_urdf() -> None:
  - `@@ -944,6 +979,7 @@ def ensure_geesun_dog_usd() -> str:
- 提交正文（commit body）：
  > 新增lingsi_d30w轮足变体的完整URDF、STL网格及关节原点配置，新增STEP转URDF的自动转换脚本，支持解析D30W轮足STEP装配树生成17个STL和带4个轮关节的URDF。同时修改机器人加载逻辑支持多变体隔离，更新移动脚本添加变体选择和轮关节驱动功能，补充转换流程文档。

### 6. 2026-09-24 11:09 · `ef3a611` · feat: 更新GeesunDog为dog921新版资产并添加仿真支持

- 作者（author）：陈斯斯
- 该文件改动：+96 / -71 行
- 关键改动位置（hunk 上下文）：
  - `@@ -725,7 +725,14 @@ _GEESUN_REPO_ROOT = (
  - `@@ -796,19 +803,28 @@ def _prepare_geesun_dog_urdf() -> None:
  - `@@ -816,72 +832,73 @@ def _prepare_geesun_dog_urdf() -> None:
  - `@@ -957,18 +974,26 @@ GEESUN_DOG_CFG = UnitreeArticulationCfg(
- 提交正文（commit body）：
  > 新增dog921 URDF、CSV配置文件，修改CMakeLists、launch、package.xml等配置，适配新版机器人资产。调整PPO训练参数、奖励权重，更新仿真脚本支持站立姿态测试、自定义关节角度、PD增益等参数，修复旧版资产的关节限位和网格问题，完善文档说明。

### 7. 2026-09-17 22:26 · `5e63990` · feat(go2, curriculum): 实现两阶段速度课程与地形性能监控

- 作者（author）：陈斯斯
- 该文件改动：+9 / -2 行
- 关键改动位置（hunk 上下文）：
  - `@@ -17,8 +17,9 @@ from isaaclab.utils import configclass
  - `@@ -797,6 +798,8 @@ def _prepare_geesun_dog_urdf() -> None:
  - `@@ -910,6 +913,10 @@ def ensure_geesun_dog_usd() -> str:
- 提交正文（commit body）：
  > 1.  新增针对Go2机器人的稳定性调优PPO配置，修复原基础配置训练发散问题

### 8. 2026-09-07 23:09 · `700b329` · feat: add Geesun Dog (dog1) quadruped robot support

- 作者（author）：chensisi
- 该文件改动：+267 / -0 行
- 关键改动位置（hunk 上下文）：
  - `@@ -715,3 +715,270 @@ for a in UNITREE_G1_29DOF_MIMIC_CFG.actuators.values():
- 提交正文（commit body）：
  > - 新增Geesun Dog四足机器人的URDF修复、资产转换、关节驱动配置

### 9. 2026-08-31 23:18 · `11b3514` · 更新Unitree模型和ROS目录路径

- 作者（author）：chensisi
- 该文件改动：+2 / -2 行
- 关键改动位置（hunk 上下文）：
  - `@@ -17,8 +17,8 @@ from isaaclab.utils import configclass

### 10. 2026-07-11 00:34 · `d53498c` · Initial commit

- 作者（author）：chensisi
- 该文件改动：+717 / -0 行
- 关键改动位置（hunk 上下文）：
  - `@@ -0,0 +1,717 @@

## 当前未提交改动（working tree，工作区）

工作区干净：该文件没有未提交改动。

## 查看完整 diff（差异）的命令

```bash
git --no-pager log --follow --stat -- source/unitree_rl_lab/unitree_rl_lab/assets/robots/unitree.py      # 逐提交统计
git --no-pager log --follow -p -- source/unitree_rl_lab/unitree_rl_lab/assets/robots/unitree.py          # 逐提交完整 diff
git --no-pager show <hash> -- source/unitree_rl_lab/unitree_rl_lab/assets/robots/unitree.py              # 单次提交的 diff
git --no-pager diff -- source/unitree_rl_lab/unitree_rl_lab/assets/robots/unitree.py                     # 当前未提交改动
```
