#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clean_videos.py — 删除工程中"录制"的视频文件,防止磁盘空间膨胀.

遍历工程根目录,找出常见视频格式的文件并删除.
默认只做 *预览*(dry-run),打印将要删除的文件及可释放的空间;
只有显式传入 --apply 才会真正删除.

安全设计:
  - 默认排除第三方库目录(如 IsaacLab_v2.3.0 的文档资源),避免误删库文件.
  - 默认不删除,必须先加 --apply 才会落地.
  - 支持 --dry-run 显式调用,并打印每条将被删除的路径.

用法:
  python scripts/clean_videos.py                # 仅预览,打印将删除的内容
  python scripts/clean_videos.py --apply        # 真正删除
  python scripts/clean_videos.py --root /path   # 指定根目录
  python scripts/clean_videos.py --include-lib  # 连第三方库目录也清理
"""

import argparse
import pathlib
import sys

# 常见视频扩展名
DEFAULT_EXTS = {".mp4", ".webm", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".m4v"}

# 默认排除的目录(第三方库 / 文档资源,通常不是"录制"的视频)
DEFAULT_EXCLUDE_DIRS = {"IsaacLab_v2.3.0", "node_modules", ".git"}


def find_videos(root: pathlib.Path, exts, exclude_dirs):
    """返回 (videos, total_bytes)."""
    videos = []
    total = 0
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() not in exts:
            continue
        # 排除指定目录
        if exclude_dirs and (set(p.parts) & exclude_dirs):
            continue
        try:
            sz = p.stat().st_size
        except OSError:
            continue
        videos.append(p)
        total += sz
    return videos, total


def human(n):
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} PiB"


def main():
    parser = argparse.ArgumentParser(description="删除工程中的录制视频文件(默认仅预览).")
    parser.add_argument("--root", type=str, default=None,
                        help="扫描根目录(默认: 脚本所在仓库根目录).")
    parser.add_argument("--ext", type=str, nargs="*", default=None,
                        help="视频扩展名,如 mp4 webm(默认: 常见视频格式).")
    parser.add_argument("--include-lib", action="store_true",
                        help="连第三方库目录(如 IsaacLab_v2.3.0)也一起清理.")
    parser.add_argument("--apply", action="store_true",
                        help="真正删除文件. 不加该参数只做预览.")
    args = parser.parse_args()

    # 仓库根目录 = scripts/ 的上一级
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    root = pathlib.Path(args.root).resolve() if args.root else repo_root

    exts = set("." + e.lower().lstrip(".") for e in (args.ext or DEFAULT_EXTS))
    exclude_dirs = set() if args.include_lib else set(DEFAULT_EXCLUDE_DIRS)

    videos, total = find_videos(root, exts, exclude_dirs)

    print(f"扫描根目录 : {root}")
    print(f"视频扩展名 : {', '.join(sorted(exts))}")
    print(f"排除目录   : {', '.join(sorted(exclude_dirs)) or '(无)'}")
    print(f"匹配文件数 : {len(videos)}")
    print(f"可释放空间 : {human(total)} ({total:,} bytes)")
    print("-" * 60)

    if not videos:
        print("没有找到需要清理的视频文件, 退出.")
        return

    if not args.apply:
        # dry-run: 逐条打印
        for p in videos:
            print(f"  [预览] {p.relative_to(root)}  ({human(p.stat().st_size)})")
        print("-" * 60)
        print("以上为预览, 不会真正删除. 确认无误后加 --apply 执行删除.")
        return

    # 真正删除
    ok = 0
    fail = 0
    for p in videos:
        try:
            p.unlink()
            ok += 1
        except OSError as e:
            fail += 1
            print(f"  [失败] {p}: {e}")
    print(f"删除完成: 成功 {ok} 个, 失败 {fail} 个, 释放约 {human(total)}.")


if __name__ == "__main__":
    main()
