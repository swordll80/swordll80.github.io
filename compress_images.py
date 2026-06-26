#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
递归压缩当前目录及子目录下的图片文件。

支持格式：
    .jpg .jpeg .png .webp

默认行为：
    生成 xxx.min.jpg / xxx.min.png / xxx.min.webp
    不覆盖原图

用法：
    python compress_images.py

如需覆盖原图：
    python compress_images.py --overwrite

如需调整 JPG/WEBP 质量：
    python compress_images.py --quality 88
"""

import argparse
import os
from pathlib import Path
from PIL import Image, ImageOps


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.2f} MB"


def is_min_file(path: Path) -> bool:
    return path.stem.endswith(".min")


def get_output_path(src: Path, overwrite: bool) -> Path:
    if overwrite:
        return src

    # xxx.jpg -> xxx.min.jpg
    return src.with_name(src.stem + ".min" + src.suffix)


def should_skip(path: Path) -> bool:
    if path.suffix.lower() not in IMAGE_EXTS:
        return True

    if is_min_file(path):
        return True

    return False


def convert_rgba_to_rgb_if_needed(img: Image.Image, background=(255, 255, 255)) -> Image.Image:
    """
    JPEG 不支持透明通道。
    如果 PNG/WebP 带透明通道并保存为 JPEG，需要铺白底。
    当前脚本不会把 PNG 转 JPEG，这里主要用于处理异常模式。
    """
    if img.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", img.size, background)
        bg.paste(img, mask=img.getchannel("A"))
        return bg

    if img.mode == "P":
        return img.convert("RGB")

    if img.mode != "RGB":
        return img.convert("RGB")

    return img


def compress_jpeg(src: Path, dst: Path, quality: int) -> None:
    with Image.open(src) as img:
        img = ImageOps.exif_transpose(img)

        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        img.save(
            dst,
            format="JPEG",
            quality=quality,
            optimize=True,
            progressive=True,
            subsampling="keep",
        )


def compress_png(src: Path, dst: Path) -> None:
    with Image.open(src) as img:
        img = ImageOps.exif_transpose(img)

        # PNG 这里采用无损优化，不强制降色，尽量保持质量。
        img.save(
            dst,
            format="PNG",
            optimize=True,
            compress_level=9,
        )


def compress_webp(src: Path, dst: Path, quality: int) -> None:
    with Image.open(src) as img:
        img = ImageOps.exif_transpose(img)

        save_args = {
            "format": "WEBP",
            "quality": quality,
            "method": 6,
        }

        # 保留透明通道
        if img.mode not in ("RGB", "RGBA"):
            if "A" in img.getbands():
                img = img.convert("RGBA")
            else:
                img = img.convert("RGB")

        img.save(dst, **save_args)


def compress_one(src: Path, quality: int, overwrite: bool) -> tuple[bool, int, int]:
    ext = src.suffix.lower()
    dst = get_output_path(src, overwrite)

    old_size = src.stat().st_size

    # 覆盖模式下，先写到临时文件，成功且更小再替换原图
    tmp_dst = dst
    if overwrite:
        tmp_dst = src.with_name(src.stem + ".__compress_tmp__" + src.suffix)

    if ext in (".jpg", ".jpeg"):
        compress_jpeg(src, tmp_dst, quality)
    elif ext == ".png":
        compress_png(src, tmp_dst)
    elif ext == ".webp":
        compress_webp(src, tmp_dst, quality)
    else:
        return False, old_size, old_size

    new_size = tmp_dst.stat().st_size

    # 如果没有变小，则删除生成文件
    if new_size >= old_size:
        if tmp_dst.exists() and tmp_dst != src:
            tmp_dst.unlink()
        return False, old_size, new_size

    if overwrite:
        os.replace(tmp_dst, src)
        new_size = src.stat().st_size

    return True, old_size, new_size


def main() -> int:
    parser = argparse.ArgumentParser(description="递归压缩当前目录及子目录下的图片文件")
    parser.add_argument(
        "--quality",
        type=int,
        default=88,
        help="JPG/WEBP 压缩质量，默认 88，建议 85~92",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="覆盖原图。默认不覆盖，而是生成 .min 文件",
    )
    args = parser.parse_args()

    quality = max(1, min(args.quality, 100))
    root = Path.cwd()

    print(f"扫描目录: {root}")
    print(f"JPG/WEBP 质量: {quality}")
    print(f"覆盖原图: {'是' if args.overwrite else '否'}")
    print("-" * 80)

    total_files = 0
    compressed_files = 0
    total_old = 0
    total_new = 0

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        if should_skip(path):
            continue

        total_files += 1

        try:
            ok, old_size, new_size = compress_one(path, quality, args.overwrite)
            total_old += old_size

            if ok:
                total_new += new_size
                compressed_files += 1
                ratio = (1 - new_size / old_size) * 100
                print(
                    f"[OK]   {path}  "
                    f"{format_size(old_size)} -> {format_size(new_size)}  "
                    f"减少 {ratio:.1f}%"
                )
            else:
                total_new += old_size
                print(
                    f"[SKIP] {path}  "
                    f"{format_size(old_size)}，压缩后未变小"
                )

        except Exception as e:
            print(f"[ERR]  {path}  {e}")

    print("-" * 80)
    print(f"扫描图片数: {total_files}")
    print(f"成功压缩数: {compressed_files}")
    print(f"原始总大小: {format_size(total_old)}")
    print(f"处理后大小: {format_size(total_new)}")

    if total_old > 0:
        ratio = (1 - total_new / total_old) * 100
        print(f"总体减少: {ratio:.1f}%")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())