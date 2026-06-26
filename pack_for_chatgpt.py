#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
pack_for_chatgpt.py

用途：
    自动打包当前目录下的 HTML 项目源码，方便发送给 ChatGPT 修正。

特点：
    1. 保留目录结构
    2. 跳过 png/jpg/jpeg/gif/webp/ico 等图片和二进制文件
    3. 跳过 .git、node_modules、dist、build 等目录
    4. 生成 PROJECT_TREE.txt，方便 ChatGPT 理解目录结构
    5. 生成 PACK_LIST.txt，记录实际打包的文件
    6. 输出 zip 文件：chatgpt_pack_YYYYMMDD_HHMMSS.zip

用法：
    python pack_for_chatgpt.py
"""

import os
import sys
import zipfile
from pathlib import Path
from datetime import datetime


# 允许打包的文本源码文件
INCLUDE_EXTS = {
    ".html",
    ".htm",
    ".css",
    ".js",
    ".mjs",
    ".json",
    ".md",
    ".txt",
    ".svg",
    ".xml",
    ".yml",
    ".yaml",
    ".ini",
    ".conf",
    ".cfg",
}


# 明确跳过的文件后缀
SKIP_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".bmp",
    ".tif",
    ".tiff",
    ".psd",
    ".ai",
    ".mp4",
    ".mp3",
    ".wav",
    ".avi",
    ".mov",
    ".zip",
    ".rar",
    ".7z",
    ".gz",
    ".tar",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".bin",
    ".dat",
    ".db",
    ".sqlite",
}


# 跳过的目录
SKIP_DIRS = {
    ".git",
    ".svn",
    ".hg",
    ".idea",
    ".vscode",
    "node_modules",
    "dist",
    "build",
    "out",
    "target",
    "__pycache__",
    ".cache",
    ".next",
    ".nuxt",
    ".codebuddy",
    ".workbuddy",
}


# 跳过的文件名
SKIP_FILES = {
    "compress_images.py",
    "pack_for_chatgpt.py",
}


def is_text_file_by_ext(path: Path) -> bool:
    return path.suffix.lower() in INCLUDE_EXTS


def should_skip_dir(path: Path) -> bool:
    return path.name in SKIP_DIRS


def should_skip_file(path: Path) -> bool:
    name = path.name
    ext = path.suffix.lower()

    if name in SKIP_FILES:
        return True

    if ext in SKIP_EXTS:
        return True

    # 防止重复打包之前生成的压缩包
    if name.startswith("chatgpt_pack_") and name.endswith(".zip"):
        return True

    return False


def safe_read_text(path: Path) -> str:
    """
    尝试读取文本文件，用于判断是否为可读文本。
    不强制转换内容，只用于跳过明显的二进制文件。
    """
    try:
        data = path.read_bytes()

        # 简单判断二进制文件
        if b"\x00" in data[:4096]:
            return ""

        for enc in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
            try:
                return data.decode(enc)
            except UnicodeDecodeError:
                pass

        return data.decode("utf-8", errors="ignore")

    except Exception:
        return ""


def collect_files(root: Path):
    files = []

    for dirpath, dirnames, filenames in os.walk(root):
        current_dir = Path(dirpath)

        # 原地修改 dirnames，避免继续进入跳过目录
        dirnames[:] = [
            d for d in dirnames
            if not should_skip_dir(current_dir / d)
        ]

        for filename in filenames:
            path = current_dir / filename

            if should_skip_file(path):
                continue

            if not is_text_file_by_ext(path):
                continue

            # 过滤异常二进制伪装文件
            text = safe_read_text(path)
            if text == "":
                continue

            files.append(path)

    files.sort(key=lambda p: str(p.relative_to(root)).lower())
    return files


def build_project_tree(root: Path, packed_files):
    packed_set = {p.resolve() for p in packed_files}
    lines = []

    def walk_dir(path: Path, prefix: str = ""):
        try:
            entries = sorted(
                list(path.iterdir()),
                key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except Exception:
            return

        entries = [
            e for e in entries
            if not (
                e.is_dir() and should_skip_dir(e)
            )
        ]

        visible_entries = []
        for e in entries:
            if e.is_dir():
                visible_entries.append(e)
            else:
                if e.resolve() in packed_set:
                    visible_entries.append(e)
                elif e.suffix.lower() in SKIP_EXTS:
                    # 图片等资源不打包，但在目录树中显示为 skipped，方便理解结构
                    visible_entries.append(e)

        for index, entry in enumerate(visible_entries):
            is_last = index == len(visible_entries) - 1
            connector = "└── " if is_last else "├── "
            next_prefix = prefix + ("    " if is_last else "│   ")

            rel = entry.relative_to(root)

            if entry.is_dir():
                lines.append(prefix + connector + entry.name + "/")
                walk_dir(entry, next_prefix)
            else:
                mark = ""
                if entry.resolve() not in packed_set:
                    mark = "  [skipped]"
                lines.append(prefix + connector + entry.name + mark)

    lines.append(root.name + "/")
    walk_dir(root)
    return "\n".join(lines) + "\n"


def build_pack_list(root: Path, packed_files):
    lines = []
    lines.append("PACK_LIST")
    lines.append("=" * 80)
    lines.append(f"Root: {root}")
    lines.append(f"Packed file count: {len(packed_files)}")
    lines.append("")

    for path in packed_files:
        rel = path.relative_to(root)
        size = path.stat().st_size
        lines.append(f"{rel.as_posix()}    {size} bytes")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    root = Path.cwd()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"chatgpt_pack_{timestamp}.zip"
    zip_path = root / zip_name

    print(f"当前目录: {root}")
    print("开始扫描文件...")

    packed_files = collect_files(root)

    if not packed_files:
        print("没有找到可打包的源码文件。")
        return 1

    project_tree = build_project_tree(root, packed_files)
    pack_list = build_pack_list(root, packed_files)

    print(f"找到源码文件: {len(packed_files)} 个")
    print(f"开始生成压缩包: {zip_name}")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 写入目录结构说明
        zf.writestr("PROJECT_TREE.txt", project_tree)

        # 写入打包文件列表
        zf.writestr("PACK_LIST.txt", pack_list)

        # 写入源码文件
        for path in packed_files:
            rel = path.relative_to(root)
            zf.write(path, rel.as_posix())

    print("-" * 80)
    print(f"打包完成: {zip_path}")
    print(f"打包文件数: {len(packed_files)}")
    print("")
    print("已跳过常见图片/二进制文件，例如：")
    print("  png, jpg, jpeg, gif, webp, ico, mp4, zip, exe, dll")
    print("")
    print("可直接把这个 zip 文件发给 ChatGPT：")
    print(f"  {zip_name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())