#!/usr/bin/env python3
"""导出 git 提交记录（commit，提交）为 Excel（.xlsx）表格。

零依赖实现：只用 Python 标准库（zipfile + XML）生成 xlsx，无需 openpyxl / pandas。
数据来源：git log --all（全部分支的提交）。

用法：
    python scripts/tools/export_commits_xlsx.py                 # 输出 outputs/commits/commits_<日期>.xlsx
    python scripts/tools/export_commits_xlsx.py --out my.xlsx   # 自定义输出路径
"""

import argparse
import datetime as dt
import os
import re
import subprocess
import sys
import zipfile
from xml.sax.saxutils import escape

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAIN_BRANCH = "GEESUN-DOG"


def git(*args):
    """运行 git 命令并返回 stdout 文本。"""
    out = subprocess.run(["git", "--no-pager"] + list(args), cwd=REPO,
                         capture_output=True, text=True, check=True)
    return out.stdout


def git_ok(*args):
    """运行 git 命令，返回退出码是否为 0。"""
    return subprocess.run(["git", "--no-pager"] + list(args), cwd=REPO,
                          capture_output=True, text=True).returncode == 0


SEP = "\x1f"   # unit separator，字段分隔
REC = "\x1e"   # record separator，记录分隔


def collect_bodies():
    """单独抓取提交正文（body，正文）。

    必须与 --numstat 分开抓：git 会把改动统计块打印在下一条格式串之前，
    同一次输出里正文会被截断成第一行，导致中文摘要残缺。
    """
    fmt = REC + SEP.join(["%H", "%b"])
    out = {}
    for rec in git("log", "--all", f"--pretty=format:{fmt}").split(REC):
        rec = rec.strip("\n")
        if not rec.strip():
            continue
        full, _, body = rec.partition(SEP)
        out[full.strip()] = body.strip()
    return out


def collect_commits():
    """解析全部提交：哈希、作者、邮箱、日期时间、标题、正文、改动文件数/增/删。"""
    fmt = REC + SEP.join(["%h", "%H", "%an", "%ae", "%ad", "%s"])
    bodies = collect_bodies()
    raw = git("log", "--all", f"--pretty=format:{fmt}",
              "--date=format:%Y-%m-%d|%H:%M", "--numstat")
    commits = []
    for rec in raw.split(REC):
        rec = rec.strip("\n")
        if not rec.strip():
            continue
        head, _, numstat = rec.partition("\n")
        parts = head.split(SEP)
        if len(parts) < 6:
            continue
        h, full, an, ae, when, subject = parts[:6]
        body = bodies.get(full.strip(), "")
        file_rows = []
        for line in numstat.splitlines():
            cols = line.split("\t")
            if len(cols) < 3 or not cols[0].strip():
                continue
            path = unquote_path(cols[2])
            if " => " in path:                      # 重命名（rename）：取新名字
                path = path.split(" => ")[-1].strip(" }{")
            binary = not cols[0].isdigit()          # 二进制文件（binary）在 numstat 里是 "-"
            file_rows.append(dict(path=path, binary=binary,
                                  ins=int(cols[0]) if cols[0].isdigit() else 0,
                                  dele=int(cols[1]) if cols[1].isdigit() else 0))
        commits.append(dict(hash=h, full=full, author=an, email=ae,
                            date=when.split("|")[0], time=when.split("|")[1],
                            subject=subject.strip(), body=body.strip(),
                            file_rows=file_rows, files=len(file_rows),
                            ins=sum(f["ins"] for f in file_rows),
                            dele=sum(f["dele"] for f in file_rows)))
    commits.sort(key=lambda c: (c["date"], c["time"]), reverse=True)
    return commits


def refs_for(h):
    """返回指向该提交的分支（branch）tip、标签（tag）、以及包含它的分支列表。"""
    tips = []
    for line in git("for-each-ref",
                    "--format=%(refname:short)\t%(objectname:short)",
                    "refs/heads", "refs/remotes").splitlines():
        if "\t" in line:
            ref, obj = line.split("\t")
            if obj == h:
                tips.append(ref)
    tags = [t for t in git("tag", "--points-at", h).split() if t]
    contains = set()
    for b in git("branch", "-a", "--contains", h).splitlines():
        b = b.lstrip("*+ ").strip().replace("remotes/origin/", "origin/")
        if b:
            contains.add(b)
    return tips, tags, sorted(contains)


def commit_type(subject):
    """从提交标题解析类型（type，提交类型）。"""
    m = re.match(r"^([a-zA-Z]+)(\([^)]*\))?(!)?:", subject)
    if m:
        t = m.group(1).lower()
        if "feat" in subject.lower() and t == "refactor":
            return "refactor+feat"
        return t
    if subject.lower().startswith("initial"):
        return "initial"
    return "无前缀"


def commit_scope(subject):
    """从提交标题解析主题（scope，影响范围）。"""
    m = re.match(r"^[a-zA-Z]+(\(([^)]*)\))?(!)?:", subject)
    if m and m.group(2):
        return m.group(2)
    return ""


# ---------------------------------------------------------------- 人工标注
# 元组：(哈希, 阶段, 主题 scope, 中文摘要)
P5 = "阶段五 双变体独立任务与训练（2026-10 上旬）"
P4 = "阶段四 lingsi_d30w 轮足变体接入（2026-09-29~30）"
P3 = "阶段三 GO2 课程学习 + 自动化调参（2026-09 中下旬）"
P2 = "阶段二 GeesunDog 接入 + 力矩统计（2026-09 上旬）"
P1 = "阶段一 仓库基座与版本适配（2026-07~08）"

META = [
    ("6558f95", P5, "GeesunDog（Geesun 狗）",
     "为轮足变体 lingsi_d30w 建独立任务注册 + D30W 专用执行器（actuator）参数（取自厂商 Excel）；"
     "URDF 命名映射与碰撞体优化；新增 d30w 专用 monitor/autotune（监控/自动调参）脚本支持并发训练"),
    ("8c21776", P5, "资产（asset）",
     "新增四足机器人 A01mw 的 URDF（统一机器人描述格式）模型与文档"),
    ("7404b32", P5, "lingsi_d30w",
     "改用厂家直接提供的 URDF 资源，删除 STEP→URDF 转换脚本"),
    ("fa19232", P5, "资产（asset）",
     "替换四足 URDF：机器人命名、连杆/关节结构、惯性参数、碰撞几何；删除旧 STL（网格）改用 SolidWorks 新导出"),
    ("f938bef", P5, "geesun_dog",
     "GeesunDog 独立执行器参数 + 独立 PPO（近端策略优化）训练类 + 环境配置；专属 TensorBoard（张量可视化面板）监控脚本；"
     "回放跟随相机；移除 boxes 子地形；电机选型文档；监控恶化判据豁免；Go2 学习率与测试脚本地形选项"),
    ("aca0888", P5, "g1-29dof",
     "任务注册切到 UnitreeG1PPORunnerCfg（constant LR 固定学习率，避免 adaptive 自适应学习率早期钉死）"),
    ("3dc8f5c", P5, "geesun_dog",
     "多变体规格（footed dog1 / wheel-legged 轮足 lingsi_d30w）；关节惩罚与接触检测适配结构差异；新增 --calf_amp_deg；"
     "PPO 网络宽度与奖励权重调整；监控避免恢复中毒的 checkpoint（检查点）；num_envs（并行环境数）对齐实机"),
    ("6869093", P4, "lingsi_d30w",
     "变体状态更新（URDF+STL 已就绪可直接加载）与 base.stl 抽稀说明"),
    ("757d344", P4, "lingsi_d30w",
     "base.stl 抽稀 131 万→23.7 万面（65MB→12MB），消除 GitHub 大文件警告"),
    ("4cb3af8", P4, "lingsi_d30w",
     "移除 zxxx 重复资产目录（与 meshes/、urdf/ 完全相同，本地保留不入库）"),
    ("901227f", P4, "lingsi_d30w",
     "轮足变体完整 URDF/STL/关节原点；STEP→URDF 自动转换脚本（解析 D30W 装配树，生成 17 个 STL + 4 个轮关节）；"
     "机器人加载支持多变体隔离；move 脚本变体选择与轮驱动"),
    ("db48358", P4, "monitor（监控）",
     "监控周期定为 6 小时；训练文档与配置更新；环境设置优化"),
    ("58dd88d", P3, "monitor（监控）",
     "监控/自动调参周期 4h→6h；新增 tb_notes.py 为 65 条 TensorBoard 曲线加中文备注（独立 run 展示）；"
     "瞬态恶化容忍（连续两次复现才触发自动干预）"),
    ("ef3a611", P3, "geesun_dog",
     "升级到 dog921 新版资产（URDF/CSV/CMakeLists/launch/package.xml）；PPO 参数与奖励权重调整；"
     "仿真脚本支持站立姿态、自定义关节角、PD 增益；修复旧资产关节限位与网格问题"),
    ("caa9907", P3, "go2",
     "GO2 步态训练全流程优化 + 自动化调参：TensorBoard 曲线分析工具、monitor/autotune 脚本、"
     "PPO 超参与课程逻辑重构、修复 editable（可编辑）安装问题、测试用例"),
    ("5e63990", P3, "go2 / curriculum（课程学习）",
     "两阶段速度课程（阶段1 固定 ±0.25 m/s，达标后解锁更大范围）；带迟滞的严格 terrain_levels（地形等级）更新；"
     "分地形性能统计入 TensorBoard；课程状态持久化；Go2 稳定性调优 PPO 配置修复训练发散；模型路径改环境变量"),
    ("724902c", P3, "training（训练）",
     "训练监控与结果验证手册；PhysX（物理引擎）溢出原理/排查/修复；README 安装-训练-验证流程；"
     "自动化监控脚本；修复速度课程状态不持久化；FAQ"),
    ("6950c60", P3, "locomotion（运动）",
     "Go2 num_envs 8000→12000；地形课程新增降级阈值与保持区间；PPO 隐藏层适配视觉输入；README 命令更新"
     "（仅在 origin/kaifa 分支，未合入主线）"),
    ("44ba005", P2, "geesun_dog",
     "新增 geesun dog1 完整 ROS（机器人操作系统）包（urdf/meshes/launch/config）；删除 unitree_model 下旧 dog1 网格；"
     "文档标记该模型不可用于训练；完善 .gitignore"),
    ("5b2b745", P2, "urdf",
     "四足 URDF 连杆/关节配置更新：STL 换基础几何、关节限位与连杆姿态、关节轴方向"),
    ("c3e038e", P2, "scripts（脚本）",
     "仿真电机模型原理详解入 ai_qa.md；README 用 test_flat_walk.py 取代旧脚本 + 多地形测试与电机选型指南；"
     "删除 record_torque_stats.py 并合并功能"),
    ("700b329", P2, "geesun_dog",
     "Geesun Dog（dog1）四足支持：URDF 修复、资产转换、关节驱动；速度跟踪 RL（强化学习）环境与推理脚本；"
     "修复 SolidWorks 导出 URDF 的空网格/缺失限位"),
    ("43c0d46", P2, "assets（资产）",
     "unitree_model/geesun_dog 资产纳入版本管理，移除 unitree_model gitlink（子模块链接）"),
    ("7b7333f", P2, "scripts（脚本）",
     "record_torque_stats.py 参数格式化 + stdout/stderr 显式 flush（刷新）避免 Isaac Sim 管道输出截断；"
     "新增 test_flat_walk.py 平地形策略测试与扭矩/行走性能统计"),
    ("b430472", P2, "scripts（脚本）",
     "record_torque_stats.py 使用说明、参数列表与输出格式文档"),
    ("3fba94c", P2, "rsl_rl",
     "关节扭矩统计脚本：峰值 / 99 分位 / RMS（均方根），辅助电机选型；支持步数、热身步数、输出路径、原始采样保存"),
    ("4c1e443", P2, "env（环境）",
     "conda 环境名 env_isaaclab→env_isaaclab_sim5；Go2 play 默认加载路径；go2-g1-walk.md 训练验证问题；"
     "新增 submodule（子模块）unitree_model；新增 ai_qa.md"),
    ("70cefde", P2, "docs（文档）",
     "新增 .clinerules/go2-g1-walk.md（机器人配置与训练任务）与 AGENTS.md；"
     "兼容不同 Isaac Lab 版本的预训练 checkpoint 导入路径"),
    ("3710aee", P1, "README",
     "添加 Unitree-G1 与 Go2 的任务运行与推理示例（中文标题，无提交类型前缀）"),
    ("11b3514", P1, "paths（路径）",
     "更新 Unitree 模型与 ROS 目录路径（中文标题，无提交类型前缀）"),
    ("f57c38b", P1, "rsl_rl/train",
     "移除冗余 model 配置 workaround（变通代码），直接用 agent_cfg 字典初始化 runner；因需固定 IsaacLab 3.2.0"),
    ("2f386c3", P1, "rsl_rl/train",
     "修复 rsl-rl 5.x 需要 actor/critic 配置项、Hydra from_dict 破坏原配置的问题（手动补全+清理）"),
    ("7caa541", P1, "curriculum（课程学习）",
     "新增 terrain_levels_vel 自适应地形课程（按指令速度动态调升级阈值）；Go2/G1 地形生成比例合并简化；"
     "训练/推理命令加 conda 前缀；新增 git 提交规范配置文件"),
    ("1854c88", P1, "README",
     "训练任务示例与 tensorboard 启动命令；修复 unitree.py 模型/ROS 本地路径；G1/Go2 启用多地形训练；"
     "开启 height_scanner（高度扫描传感器）观测项"),
    ("d53498c", P1, "全仓库",
     "Initial commit（初始提交）：仓库基线导入，所有分支的共同根"),
]
META_MAP = {h: (phase, scope, summary) for h, phase, scope, summary in META}

# ---------------------------------------------------------------- 自动摘要
CHECKPOINT_PAT = re.compile(r"^(cline checkpoint|index on |untracked files on |wip on |on \S+: )",
                            re.IGNORECASE)
PHASES_BY_DATE = [
    ("2026-07-01", "阶段一 仓库基座与版本适配（2026-07~08）"),
    ("2026-09-01", "阶段二 GeesunDog 接入 + 力矩统计（2026-09 上旬）"),
    ("2026-09-12", "阶段三 GO2 课程学习 + 自动化调参（2026-09 中下旬）"),
    ("2026-09-29", "阶段四 lingsi_d30w 轮足变体接入（2026-09-29~30）"),
    ("2026-10-01", "阶段五 双变体独立任务与训练（2026-10 上旬）"),
    ("2026-10-15", "阶段六 传感器与地形课程迭代（2026-10 中下旬）"),
]


def is_checkpoint(subject):
    """判断是否为工具自动生成的检查点提交（checkpoint，检查点）。"""
    return bool(CHECKPOINT_PAT.match(subject))


def auto_phase(date):
    """按提交日期自动归入阶段（phase，阶段）：取起始日期不晚于该提交日期的最后一个阶段。"""
    phase = PHASES_BY_DATE[0][1]
    for start, name in PHASES_BY_DATE:
        if date >= start:
            phase = name
    return phase


def auto_summary(c):
    """从提交正文（body，正文）自动生成中文摘要：去编号、拼句、截断到 200 字。"""
    lines = []
    for raw_line in c["body"].splitlines():
        line = raw_line.strip().strip("`").strip()
        if not line or line in {"```", "---", "***", "msg", "-", ".", "#"}:
            continue
        line = re.sub(r"^\s*\d+[\.、)]\s*", "", line)
        line = re.sub(r"^[-*]\s+", "", line)
        lines.append(line)
    text = ""
    for line in lines:                      # 冒号结尾的行直接续接，其余用分号拼接
        if not text:
            text = line
        elif text.endswith(("：", ":", "，", ",")):
            text += " " + line
        else:
            text += "；" + line
    text = re.sub(r"\s+", " ", text).strip("； ")
    text = re.sub(r"[；;]\s*[；;]", "；", text).strip("； ")
    # 正文过短（如只写了 "msg"）时回退到提交标题，避免出现无意义摘要
    if len(text) < 8:
        text = c["subject"]
    return text[:200]


def checkpoint_summary(c):
    """检查点提交（checkpoint）的中文摘要：这类提交由 IDE（集成开发环境）插件自动生成，非人工编码提交。"""
    s = c["subject"]
    m = re.search(r"session=(\S+)\s+run=(\d+)", s)
    if m:
        return f"Cline 检查点自动提交（checkpoint）：会话 session={m.group(1)}，第 {m.group(2)} 次运行"
    low = s.lower()
    tail = re.sub(r"`+", "", s[9:]).strip(" ：:")
    if low.startswith("index on "):
        return "Cline 检查点自动提交（checkpoint）：索引快照（index snapshot）" + tail[:70]
    if low.startswith("untracked files on "):
        return "Cline 检查点自动提交（checkpoint）：未跟踪文件快照（untracked snapshot）"
    return "Cline 检查点自动提交（checkpoint）：IDE 插件自动保存的工作快照（work snapshot）"




# ---------------------------------------------------------------- 文件分类
CODE_CAT = "代码（code）"
EXT_CODE = {"py", "pyi", "sh", "bash", "zsh", "c", "h", "cpp", "cc", "cxx", "hpp", "js",
            "ts", "m", "cu", "cuh", "go", "rs", "ipynb", "lua", "awk", "sed"}
EXT_ASSET = {"stl", "obj", "dae", "usd", "usda", "usdc", "usdz", "blend", "step", "stp",
             "png", "jpg", "jpeg", "gif", "bmp", "svg", "glb", "gltf", "fbx", "ply",
             "xlsx", "xls", "csv", "mtl", "ttf", "otf"}
EXT_CONFIG = {"yaml", "yml", "json", "toml", "ini", "cfg", "xml", "cmake", "launch",
              "urdf", "xacro", "service", "pc", "properties", "in", "patch", "diff",
              "gitignore", "gitmodules", "gitattributes", "editorconfig", "flake8",
              "clang-format", "gitkeep", "lock"}
EXT_DOC = {"md", "rst", "txt", "tex", "org", "adoc"}
SPECIAL_CONFIG = {"CMakeLists.txt", "Makefile", "package.xml", "requirements.txt",
                  ".gitignore", ".gitmodules", ".gitattributes", ".editorconfig",
                  ".flake8", ".clang-format", "Dockerfile", ".dockerignore"}


def unquote_path(p):
    """还原 git 对非 ASCII 路径的引号 + 八进制转义（如 "...\345\205\263..."）。"""
    p = p.strip()
    if not (p.startswith('"') and p.endswith('"')):
        return p
    p, out, i = p[1:-1], bytearray(), 0
    while i < len(p):
        ch = p[i]
        if ch == "\\" and i + 1 < len(p):
            n = p[i + 1:i + 4]
            if len(n) == 3 and all(c in "01234567" for c in n):
                out.append(int(n, 8))
                i += 4
                continue
            nxt = p[i + 1]
            if nxt in '"\\':
                out.append(ord(nxt))
            elif nxt == "n":
                out.append(10)
            elif nxt == "t":
                out.append(9)
            else:
                out.extend(nxt.encode("utf-8"))
            i += 2
            continue
        out.extend(ch.encode("utf-8"))
        i += 1
    return out.decode("utf-8", "replace")


def classify_file(path):
    """把文件路径归入类别（category）：代码 / 文档 / 模型资产 / 配置 / 会话记录 / 日志 / 其他。"""
    base = os.path.basename(path)
    ext = base.rsplit(".", 1)[-1].lower() if "." in base else ""
    if base.startswith(("session-", "session_")):
        return "会话记录（session）"
    if ext == "log":
        return "日志（log）"
    if ext in EXT_ASSET:
        return "模型/资产（asset）"
    if ext in EXT_CODE:
        return CODE_CAT
    if base in SPECIAL_CONFIG:
        return "配置（config）"
    if ext in EXT_CONFIG:
        return "配置（config）"
    if ext in EXT_DOC:
        return "文档（doc）"
    return "其他（other）"


# ---------------------------------------------------------------- xlsx 写出
STYLES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="4">
<font><sz val="11"/><name val="Calibri"/></font>
<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>
<font><b/><sz val="14"/><color rgb="FF1F4E78"/><name val="Calibri"/></font>
<font><b/><sz val="11"/><color rgb="FF1F4E78"/><name val="Calibri"/></font>
</fonts>
<fills count="3">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF4472C4"/><bgColor indexed="6"/></patternFill></fill>
</fills>
<borders count="2">
<border><left/><right/><top/><bottom/><diagonal/></border>
<border><left style="thin"><color rgb="FFBFBFBF"/></left><right style="thin"><color rgb="FFBFBFBF"/></right><top style="thin"><color rgb="FFBFBFBF"/></top><bottom style="thin"><color rgb="FFBFBFBF"/></bottom><diagonal/></border>
</borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="8">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="3" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment horizontal="left" vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment horizontal="right" vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment horizontal="left" vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinName="1"/></cellStyles>
</styleSheet>"""

SHEET_TMPL = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<sheetViews><sheetView showGridLines="1" workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
<sheetFormatPr defaultRowHeight="16"/>
<cols>{cols}</cols>
<sheetData>{rows}</sheetData>
<autoFilter ref="A1:{last}{nrows}"/>
</worksheet>"""


def col_letter(idx):
    """1 基列号转 Excel 列字母（1->A，27->AA）。"""
    s = ""
    while idx:
        idx, r = divmod(idx - 1, 26)
        s = chr(65 + r) + s
    return s


def cell(ref, value, style):
    """生成一个单元格 XML：int 写数值（v），其余写内联字符串（inlineStr）。"""
    if isinstance(value, bool):
        value = str(value)
    if isinstance(value, int):
        return f'<c r="{ref}" s="{style}"><v>{value}</v></c>'
    return (f'<c r="{ref}" s="{style}" t="inlineStr">'
            f'<is><t xml:space="preserve">{escape(str(value))}</t></is></c>')


def sheet_xml(headers, rows, widths, row_height=None):
    """把表头 + 数据行渲染成一张工作表（sheet）的 XML。

    row_height=None：行高自适应（auto-fit）—— 不写 ht / customHeight 属性，
    由 Excel / WPS / LibreOffice 依据自动换行（wrapText）后的文本高度自行撑开行高。
    row_height=数字：固定行高（写 ht + customHeight="1"，不再自适应）。
    表头行始终固定 34 磅，保证标题整齐。
    """
    def open_tag(r):
        if row_height is None:
            return f'<row r="{r}">'
        return f'<row r="{r}" ht="{row_height}" customHeight="1">'

    header_cells = "".join(cell(f"{col_letter(i + 1)}1", h, 1) for i, h in enumerate(headers))
    parts = [f'<row r="1" ht="34" customHeight="1">{header_cells}</row>']
    for r, row in enumerate(rows, start=2):
        cs = []
        for i, v in enumerate(row):
            st = 3 if isinstance(v, int) else 2
            cs.append(cell(f"{col_letter(i + 1)}{r}", v, st))
        parts.append(f"{open_tag(r)}{''.join(cs)}</row>")
    cols = "".join(f'<col min="{i + 1}" max="{i + 1}" width="{w}" customWidth="1"/>'
                   for i, w in enumerate(widths))
    return SHEET_TMPL.format(cols=cols, rows="".join(parts),
                             last=col_letter(len(headers)), nrows=len(rows) + 1)

# ---------------------------------------------------------------- 工作簿组装
CT_TMPL = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
           '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
           '<Default Extension="xml" ContentType="application/xml"/>'
           '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
           '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
           '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
           '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
           '{overrides}</Types>')

ROOT_RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
             '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
             '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
             '</Relationships>')

APP_XML = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
           '<Application>export_commits_xlsx.py</Application></Properties>')


def write_xlsx(path, sheets, title):
    """sheets: [(工作表名, 表头, 数据行, 列宽, 行高)]；写出 xlsx（Excel 文件）。"""
    today = dt.date.today().isoformat()
    core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            f'<dc:title>{escape(title)}</dc:title><dc:creator>export_commits_xlsx.py</dc:creator>'
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{today}T00:00:00Z</dcterms:created>'
            f'<dcterms:modified xsi:type="dcterms:W3CDTF">{today}T00:00:00Z</dcterms:modified>'
            '</cp:coreProperties>')
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType='
        f'"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, len(sheets) + 1))
    wb = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
          '<sheets>' + "".join(
              f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
              for i, (name, _, _, _, _) in enumerate(sheets, start=1)) + '</sheets></workbook>')
    wb_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
               + "".join(
                   f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                   f'relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
                   for i in range(1, len(sheets) + 1))
               + f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/'
                 f'officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CT_TMPL.format(overrides=overrides))
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("docProps/core.xml", core)
        z.writestr("docProps/app.xml", APP_XML)
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/styles.xml", STYLES_XML)
        for i, (_, headers, rows, widths, rh) in enumerate(sheets, start=1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", sheet_xml(headers, rows, widths, rh))



# ---------------------------------------------------------------- 组装数据
TYPE_CN = {"feat": "新功能", "docs": "文档", "chore": "杂务/构建配置", "fix": "缺陷修复",
           "refactor": "重构", "perf": "性能优化", "initial": "初始提交",
           "refactor+feat": "重构 + 新功能", "无前缀": "中文标题（未套提交规范）",
           "checkpoint": "检查点自动提交（IDE 插件生成，非人工编码）"}

OVERVIEW_HEADERS = ["序号", "Commit（提交哈希）", "日期", "时间", "作者", "类型（type）",
                    "主题（scope）", "来源（source）", "阶段（phase）", "中文摘要",
                    "提交标题（subject）",
                    "文件数", "新增行", "删除行",
                    "代码文件数", "代码新增行", "代码删除行",
                    "非代码文件数", "非代码新增行", "非代码删除行", "非代码构成",
                    "所在分支（branch）", "标签（tag）", "是否合入主线 GEESUN-DOG"]
OVERVIEW_WIDTHS = [5, 16, 11, 7, 22, 12, 20, 22, 34, 52, 34, 7, 8, 8, 9, 9, 9, 11, 11, 11, 24, 26, 18, 14]


def annotate(commits):
    """为每条提交补上阶段 / 主题 / 中文摘要 / 来源 / 分支 / 标签 / 是否合入主线。

    中文摘要来源优先级：人工标注表 META_MAP（按完整哈希 full hash 前缀匹配）
    > 提交正文自动生成（auto_summary）> 检查点专用摘要 > 提交标题。
    返回"摘要仅等于标题（正文为空）"的提交哈希列表，用于提示。
    """
    missing = []
    for c in commits:
        meta = next((v for k, v in META_MAP.items() if c["full"].startswith(k)), None)
        c["checkpoint"] = is_checkpoint(c["subject"])
        c["source"] = "检查点（checkpoint，工具自动）" if c["checkpoint"] else "人工提交（manual）"
        if meta:
            phase, scope, summary = meta
        else:
            phase, scope = auto_phase(c["date"]), commit_scope(c["subject"])
            summary = checkpoint_summary(c) if c["checkpoint"] else auto_summary(c)
            if summary == c["subject"]:
                missing.append(c["hash"])
        c["phase"], c["scope"], c["summary"] = phase, scope, summary
        c["type"] = "checkpoint" if c["checkpoint"] else commit_type(c["subject"])
        if not c["scope"]:
            c["scope"] = "cline-checkpoint" if c["checkpoint"] else commit_scope(c["subject"])
        tips, tags, contains = refs_for(c["hash"])
        c["tips"], c["tags"], c["contains"] = tips, tags, contains
        c["merged"] = "是" if git_ok("merge-base", "--is-ancestor", c["hash"], MAIN_BRANCH) else "否"
        code_rows = [f for f in c["file_rows"] if classify_file(f["path"]) == CODE_CAT]
        nc_rows = [f for f in c["file_rows"] if classify_file(f["path"]) != CODE_CAT]
        c["code_files"], c["code_ins"], c["code_dele"] = (
            len(code_rows), sum(f["ins"] for f in code_rows), sum(f["dele"] for f in code_rows))
        c["nc_files"], c["nc_ins"], c["nc_dele"] = (
            len(nc_rows), sum(f["ins"] for f in nc_rows), sum(f["dele"] for f in nc_rows))
        mix = {}
        for f in nc_rows:
            key = classify_file(f["path"]).split("（")[0]
            mix[key] = mix.get(key, 0) + 1
        c["nc_mix"] = " ".join(f"{k}×{v}" for k, v in sorted(mix.items())) or "-"
    return missing


def sheets_part1(commits):
    """构造前 3 张工作表（sheet）：提交总览 / 按类型 / 按月份。"""
    rows = []
    for i, c in enumerate(commits, start=1):
        tips = ("（tip: " + ",".join(c["tips"]) + "）") if c["tips"] else ""
        rows.append([i, c["hash"], c["date"], c["time"], f'{c["author"]} <{c["email"]}>',
                     c["type"], c["scope"], c["source"], c["phase"], c["summary"], c["subject"],
                     c["files"], c["ins"], c["dele"],
                     c["code_files"], c["code_ins"], c["code_dele"],
                     c["nc_files"], c["nc_ins"], c["nc_dele"], c["nc_mix"],
                     " ".join(c["contains"]) + tips, " ".join(c["tags"]) or "-", c["merged"]])
    overview = ("提交总览", OVERVIEW_HEADERS, rows, OVERVIEW_WIDTHS, None)

    by_type = {}
    for c in commits:
        by_type.setdefault(c["type"], []).append(c["hash"])
    t_rows = []
    for t, hs in sorted(by_type.items(), key=lambda kv: -len(kv[1])):
        t_rows.append([t, TYPE_CN.get(t, "-"), len(hs),
                       f"{len(hs) * 100.0 / len(commits):.1f}%", " ".join(hs[:6])])
    t_rows.append(["合计", "-", len(commits), "100.0%", f"共 {len(commits)} 条提交（commit）"])
    by_type_sheet = ("按类型统计", ["类型（type）", "中文释义", "条数", "占比", "代表 Commit"],
                     t_rows, [16, 26, 8, 9, 60], None)

    by_month = {}
    for c in commits:
        by_month.setdefault(c["date"][:7], []).append(c)
    m_rows = []
    for m in sorted(by_month, reverse=True):
        cs = by_month[m]
        phases = sorted({c["phase"].split("（")[0].strip() for c in cs if c["phase"] != "未标注"})
        m_rows.append([m, len(cs), sum(c["ins"] for c in cs), sum(c["dele"] for c in cs),
                       "；".join(phases) or "-"])
    m_rows.append(["合计", len(commits), sum(c["ins"] for c in commits),
                   sum(c["dele"] for c in commits), "全部提交（commit）"])
    by_month_sheet = ("按月份统计", ["月份（month）", "提交数", "新增行", "删除行", "覆盖阶段"],
                      m_rows, [12, 9, 9, 9, 70], None)
    return [overview, by_type_sheet, by_month_sheet]

def sheets_part2(commits):
    """构造后 3 张工作表（sheet）：分支拓扑 / 变更规模 Top10 / 说明。"""
    b_rows = []
    refs = [line.split("\t") for line in
            git("for-each-ref", "--format=%(refname:short)\t%(objectname:short)",
                "refs/heads", "refs/remotes").splitlines() if "\t" in line]
    for ref, tip in refs:
        if ref.endswith("/HEAD"):
            continue
        n = int(git("rev-list", "--count", ref).strip())
        merged = "是" if git_ok("merge-base", "--is-ancestor", ref, MAIN_BRANCH) else "否"
        kind = ("当前分支（HEAD）" if ref == MAIN_BRANCH
                else "远端分支（remote）" if ref.startswith("origin/") else "本地分支（local）")
        b_rows.append([ref, tip, n, merged, kind])
    b_rows.sort(key=lambda r: (r[0].startswith("origin/"), r[0]))
    branch_sheet = ("分支拓扑", ["分支（branch）", "tip（最新提交）", "提交数", "是否合入主线", "性质"],
                    b_rows, [30, 16, 9, 14, 24], None)

    top = sorted(commits, key=lambda c: -c["files"])[:10]
    top_rows = [[i, c["hash"], c["date"], c["files"], c["ins"], c["dele"], c["summary"][:70]]
                for i, c in enumerate(top, start=1)]
    top_sheet = ("变更规模Top10", ["排名", "Commit", "日期", "文件数", "新增行", "删除行", "摘要"],
                 top_rows, [6, 14, 12, 8, 8, 8, 70], None)

    notes = [
        ["生成脚本", "scripts/tools/export_commits_xlsx.py（零依赖：标准库 zipfile + XML 生成 xlsx）"],
        ["数据来源", "git log --all（全部分支提交）+ git numstat（改动统计）+ git branch --contains（分支归属）"],
        ["重新生成", "/home/css/miniconda3/envs/env_isaaclab_sim51/bin/python scripts/tools/export_commits_xlsx.py"],
        ["统计口径", "非代码文件（STL 网格 / MD 文档 / CSV / URDF / xlsx / session 记录等）同样逐条记录，并在「提交总览」里与代码分列统计"],
        ["中文摘要来源", "优先取人工标注表（基线 35 条提交）；其余提交由提交正文（commit body）自动生成——去编号、拼句、截断 200 字；"
                         "正文为空的回退为提交标题（subject）"],
        ["检查点提交（checkpoint）", "由 IDE（集成开发环境）插件自动生成的工作快照（标题形如 cline checkpoint / index on / untracked files on），"
                                     "类型标为 checkpoint、来源列标为「检查点（工具自动）」；加 --no-checkpoint 可剔除，只统计人工提交"],
        ["阶段（phase）", "基线 35 条为人工划分；其余按提交日期自动归入 6 个阶段，2026-10-15 之后为「阶段六 传感器与地形课程迭代」"],
        ["代码口径", "代码（code）= 源码扩展名：.py/.sh/.c/.cpp/.h/.js/.ts/.ipynb 等；"
                     "文档（doc）= .md/.rst/.txt；模型资产（asset）= .stl/.obj/.usd/.png/.csv/.xlsx 等；"
                     "CMakeLists.txt、package.xml、requirements.txt、.gitignore 等归入配置（config）；二进制文件（binary）行数记 0"],
        ["总体统计", "「总体统计」表给出累计修改的代码行数量、累计修改的代码文件数量（去重）、非代码文件数量等；"
                     "类别明细见「按文件类别统计」，扩展名明细见「按扩展名统计」，热点文件见「Top20代码文件」"],
        ["作者身份", "chensisi <chensisi@example.com> 为早期占位邮箱；2026-09-11 起统一为 陈斯斯 <25589311@qq.com>，同一人"],
        ["阶段划分", "按提交时间人工归入 5 个阶段，仅用于阅读，不改变 git 历史本身"],
        ["未合入主线", "origin/main、origin/kaifa、origin/dev/g1-go2-walking 上的提交不在 GEESUN-DOG 历史中，做消融实验前需确认基线（baseline）"],
        ["标签（tag）", "tag 11 -> 44ba005；tag go2-ht-10xw-20261010 -> aca0888（Go2 height_scanner 高度扫描传感器 10 倍权重实验节点）"],
        ["生成时间", dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
    ]
    note_sheet = ("说明", ["项目", "内容"], notes, [16, 110], None)
    return [branch_sheet, top_sheet, note_sheet]


def sheets_part3(commits):
    """构造总体统计（overall statistics）/ 按文件类别 / 按扩展名 / Top 代码文件 三张表。"""
    all_files = [f for c in commits for f in c["file_rows"]]
    code = [f for f in all_files if classify_file(f["path"]) == CODE_CAT]
    noncode = [f for f in all_files if classify_file(f["path"]) != CODE_CAT]
    binary = [f for f in all_files if f["binary"]]
    code_lines = sum(f["ins"] + f["dele"] for f in code)
    all_lines = sum(f["ins"] + f["dele"] for f in all_files)
    uniq = lambda xs: len(set(xs))  # noqa: E731

    total_rows = [
        ["提交总数（commit）", len(commits), "git log --all 全分支去重后的提交条数"],
        ["累计修改的代码文件数量（去重，unique）", uniq(f["path"] for f in code), "被改动过的代码文件有多少个"],
        ["累计修改的代码文件次数（含重复）", len(code), "同一文件被多次提交会重复计数"],
        ["累计代码新增行", sum(f["ins"] for f in code), "只统计代码（code）类文件"],
        ["累计代码删除行", sum(f["dele"] for f in code), "只统计代码（code）类文件"],
        ["累计修改的代码行数量（新增+删除）", code_lines, "代码改动总量，用于衡量真实编码工作量"],
        ["累计修改的非代码文件数量（去重）", uniq(f["path"] for f in noncode), "STL（网格）/MD（Markdown）/CSV/URDF 等"],
        ["累计修改的非代码文件次数（含重复）", len(noncode), "非代码改动同样逐条记录"],
        ["累计非代码新增行", sum(f["ins"] for f in noncode), "二进制文件（binary）行数记 0"],
        ["累计非代码删除行", sum(f["dele"] for f in noncode), "二进制文件（binary）行数记 0"],
        ["二进制文件（binary）改动次数", len(binary), "numstat 显示为 \"-\"，无法统计行数"],
        ["全部改动行（代码 + 非代码）", all_lines, "与 git shortstat 口径一致"],
        ["代码行占全部改动行比例", f"{(code_lines * 100.0 / all_lines) if all_lines else 0:.1f}%", "衡量提交里代码的纯度"],
        ["平均每条提交改动代码行", f"{code_lines / len(commits):.1f}", "code_lines / 提交数"],
        ["涉及代码文件最多的提交", max(commits, key=lambda c: c["code_files"])["hash"],
         f"{max(c['code_files'] for c in commits)} 个代码文件"],
    ]
    total_sheet = ("总体统计", ["指标（metric）", "数值", "说明"], total_rows, [40, 14, 60], None)

    cat = {}
    for f in all_files:
        k = classify_file(f["path"])
        d = cat.setdefault(k, dict(n=0, paths=set(), ins=0, dele=0))
        d["n"] += 1
        d["paths"].add(f["path"])
        d["ins"] += f["ins"]
        d["dele"] += f["dele"]
    cat_rows = []
    for k, d in sorted(cat.items(), key=lambda kv: -(kv[1]["ins"] + kv[1]["dele"])):
        lines = d["ins"] + d["dele"]
        cat_rows.append([k, d["n"], len(d["paths"]), d["ins"], d["dele"], lines,
                         f"{lines * 100.0 / all_lines:.1f}%" if all_lines else "-"])
    cat_rows.append(["合计", len(all_files), uniq(f["path"] for f in all_files),
                     sum(f["ins"] for f in all_files), sum(f["dele"] for f in all_files),
                     all_lines, "100.0%"])
    cat_sheet = ("按文件类别统计", ["类别（category）", "文件次数", "去重文件数", "新增行",
                                    "删除行", "改动行", "占比"], cat_rows, [24, 10, 11, 9, 9, 9, 9], None)

    exts = {}
    for f in all_files:
        base = os.path.basename(f["path"])
        ext = base.rsplit(".", 1)[-1].lower() if "." in base else "(无扩展名)"
        d = exts.setdefault(ext, dict(n=0, paths=set(), ins=0, dele=0, cat=classify_file(f["path"])))
        d["n"] += 1
        d["paths"].add(f["path"])
        d["ins"] += f["ins"]
        d["dele"] += f["dele"]
    ext_rows = [[e, d["cat"], d["n"], len(d["paths"]), d["ins"], d["dele"], d["ins"] + d["dele"]]
                for e, d in sorted(exts.items(), key=lambda kv: -kv[1]["n"])]
    ext_sheet = ("按扩展名统计", ["扩展名（extension）", "归类", "文件次数", "去重文件数",
                                  "新增行", "删除行", "改动行"], ext_rows, [16, 22, 10, 11, 9, 9, 9], None)

    files = {}
    for c in commits:
        for f in c["file_rows"]:
            if classify_file(f["path"]) != CODE_CAT:
                continue
            d = files.setdefault(f["path"], dict(n=0, ins=0, dele=0, last=c["date"]))
            d["n"] += 1
            d["ins"] += f["ins"]
            d["dele"] += f["dele"]
            d["last"] = max(d["last"], c["date"])
    top_files = sorted(files.items(), key=lambda kv: (-kv[1]["n"], -(kv[1]["ins"] + kv[1]["dele"])))[:20]
    file_rows_out = [[i, p, d["n"], d["ins"], d["dele"], d["ins"] + d["dele"], d["last"]]
                     for i, (p, d) in enumerate(top_files, start=1)]
    files_sheet = ("Top20代码文件", ["排名", "代码文件路径（path）", "改动次数", "新增行",
                                     "删除行", "改动行", "最近改动日期"], file_rows_out,
                   [6, 62, 10, 9, 9, 9, 12], None)
    return [total_sheet, cat_sheet, ext_sheet, files_sheet]


def write_csv(path, headers, rows):
    """附带导出 CSV（逗号分隔表）总览，便于其他工具读取。"""
    import csv
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description="导出 git 提交记录（commit）为 Excel（xlsx）表格")
    ap.add_argument("--out", default=None,
                    help="输出 xlsx 路径（默认 outputs/commits/commits_<日期>.xlsx）")
    ap.add_argument("--row-height", type=int, default=0,
                    help="数据行固定行高（磅，point）；默认 0 = 行高自适应（auto-fit，按换行后文本自动撑开）")
    ap.add_argument("--no-checkpoint", action="store_true",
                    help="剔除检查点自动提交（checkpoint，IDE 插件生成的工作快照），只统计人工提交")
    args = ap.parse_args()

    commits = collect_commits()
    missing = annotate(commits)
    total_all = len(commits)
    n_cp = sum(1 for c in commits if c["checkpoint"])
    if args.no_checkpoint:
        commits = [c for c in commits if not c["checkpoint"]]
    if missing:
        print(f"[warn] {len(missing)} 条提交正文为空，中文摘要回退为提交标题："
              f"{' '.join(missing[:15])}{' ...' if len(missing) > 15 else ''}", file=sys.stderr)
    print(f"[info] 全部分支提交（commit）{total_all} 条 = 人工提交 {total_all - n_cp} 条 + "
          f"检查点自动提交（checkpoint）{n_cp} 条"
          f"{'；本次已剔除检查点' if args.no_checkpoint else '；本次检查点已纳入并单独标注'}")
    all_sheets = sheets_part1(commits) + sheets_part2(commits) + sheets_part3(commits)
    order = ["提交总览", "总体统计", "按文件类别统计", "按扩展名统计", "Top20代码文件",
             "按类型统计", "按月份统计", "分支拓扑", "变更规模Top10", "说明"]
    sheets = [next(s for s in all_sheets if s[0] == name) for name in order]
    fixed_h = args.row_height if args.row_height > 0 else None
    sheets = [s[:4] + (fixed_h,) for s in sheets]

    out = args.out or os.path.join(REPO, "outputs", "commits",
                                   f"commits_{dt.date.today():%Y%m%d}.xlsx")
    write_xlsx(out, sheets, "Geesun_robot_rl_lab 提交记录（commit）汇总")
    csv_path = os.path.splitext(out)[0] + "_overview.csv"
    write_csv(csv_path, sheets[0][1], sheets[0][2])
    print(f"[ok] 已导出 {len(commits)} 条提交 -> {out}")
    print(f"[ok] 共 {len(sheets)} 张工作表：{', '.join(s[0] for s in sheets)}")
    print(f"[ok] 附带 CSV -> {csv_path}")


if __name__ == "__main__":
    main()

