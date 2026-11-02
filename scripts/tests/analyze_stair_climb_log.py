#!/usr/bin/env python3
"""分析 validate_stair_climb.sh（原名 P5.sh）产生的 /tmp/stair_climb.log，按其判读标准给出 PASS/FAIL 结论。

用法: python3 scripts/tests/analyze_stair_climb_log.py [日志路径，默认 /tmp/stair_climb.log]

判读标准（来自 validate_stair_climb.sh 头部注释）:
  dz = 基座世界高度 - 地形原点高度 = 相对出生点坑底地面的高度
  站立 dz ~ 0.63 m; 爬上一级 0.16 m 台阶 -> dz 稳定 ~ 0.79 m 且不回落
  max(dz) <= 0.65 -> 没有爬升;  max(dz) >= 0.75 -> 真的爬上去过
"""
import re
import sys

LOG = sys.argv[1] if len(sys.argv) > 1 else "/tmp/stair_climb.log"

DZ_FAIL, DZ_PASS = 0.65, 0.75  # 与 validate_stair_climb.sh 头部注释一致

try:
    text = open(LOG, errors="replace").read()
except OSError as e:
    print(f"[FAIL] 无法读取 {LOG}: {e}")
    sys.exit(2)

blocks = re.split(r"={5}\s*RUN\s+(\d+)\s*={5}", text)
if len(blocks) < 3:
    print("[FAIL] 没有任何 '===== RUN n =====' 标记: 脚本没跑起来")
    sys.exit(1)

fatal_pat = re.compile(
    r"Traceback \(most recent call last\)|\[ERROR\]|CUDA out of memory"
    r"|Segmentation fault|does not resolve to a file",
)
# Isaac Sim(仿真器) 启动期固有噪声，与策略无关:
#   omni.kit.test / isaacsim.test.docstring / omni.graph 测试扩展导入失败
#   (conda 自带 libstdc++ 的 CXXABI_1.3.15 与 libicui18n.so.78 不匹配, 每次启动必报)
noise_pat = re.compile(
    r"omni\.(ext|graph|kit)|custom_importer|_internal\.py|libstdc|CXXABI|libicu"
    r"|TestOgn|extscache|isaacsim[/\\]kit|isaacsim\.test|docstring"
    r"|importlib|import_module|_bootstrap|circular import"
    r"|Failed to import python module",
)

overall = True
for i in range(1, len(blocks), 2):
    run, body = blocks[i], blocks[i + 1]
    dzs = [float(v) for v in re.findall(r"dz=([-+0-9.]+)", body)]
    steps = [int(s) for s in re.findall(r"\[PROBE\] step\s+(\d+)", body)]
    lvls = [int(v) for v in re.findall(r"\blvl=(\d+)", body)]
    # 按空行分段: 段内任一行命中噪声 -> 整段忽略(Isaac Sim 的报错段必含其自身路径);
    # 其余段中再找致命行。真正的 play.py/训练崩溃段不含噪声词, 不会被误滤。
    fatals = []
    for para in re.split(r"\n\s*\n", body):
        if noise_pat.search(para):
            continue
        fatals.extend(ln for ln in para.splitlines() if fatal_pat.search(ln))
    print(f"\n===== RUN {run} =====")
    print(f"  PROBE 采样数 : {len(steps)}"
          + (f"  (step {steps[0]}..{steps[-1]})" if steps else "  <- 缺采样!"))
    if not dzs:
        print("  结论: FAIL — 没有 [PROBE] 数据(启动即崩溃或被 timeout(超时) 杀掉)")
        overall = False
        continue
    mx, mn = max(dzs), min(dzs)
    tail = dzs[-max(1, len(dzs) // 5):]  # 最后 1/5 采样
    tail_min = min(tail)
    verdict = ("PASS 真的爬上去了" if mx >= DZ_PASS
               else "PARTIAL 半途(0.65~0.75 之间)" if mx > DZ_FAIL
               else "FAIL 没有爬升")
    ok = mx >= DZ_PASS and not fatals
    overall &= ok
    print(f"  dz 范围      : {mn:.2f} ~ {mx:.2f} m   max(dz)={mx:.2f}")
    print(f"  末段最小 dz  : {tail_min:.2f} m  ({'站稳未回落' if tail_min > DZ_FAIL else '⚠ 回落到站立高度,可能爬上去又掉下来'})")
    print(f"  terrain level(地形等级): {sorted(set(lvls)) if lvls else 'N/A'}")
    print(f"  致命错误     : {len(fatals)} 条" + (f"\n    例: {fatals[0][:160]}" if fatals else ""))
    print(f"  结论: {verdict}" + ("" if ok else "  <- 未达标"))

print("\n========== 总体结论:", "PASS" if overall else "FAIL/PARTIAL (见上)", "==========")
sys.exit(0 if overall else 1)
