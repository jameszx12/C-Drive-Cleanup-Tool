# -*- coding: utf-8 -*-
"""
C盘垃圾清理工具 - 应用图标生成脚本  V2.5.0
作用：读取 app_icon.svg，用 cairosvg 渲染 → Pillow 合成多尺寸 app_icon.ico，
      供 PyInstaller 打包 exe 时通过 --icon 嵌入。

      SVG 是唯一的设计源文件，改 SVG 后跑一次本脚本即可同步。

运行方式：
    python make_icon.py

依赖：Pillow + cairosvg (pip install Pillow cairosvg)
注意：cairosvg 仅在开发期用于渲染图标，不参与 exe 运行，不影响 exe 体积。
"""
import io
import os
import cairosvg
from PIL import Image


def render_svg(svg_path, size):
    """用 cairosvg 将 SVG 渲染为指定尺寸的 PIL Image。"""
    png_bytes = cairosvg.svg2png(
        url=svg_path,
        output_width=size,
        output_height=size,
    )
    return Image.open(io.BytesIO(png_bytes)).convert("RGBA")


def main():
    out_dir = os.path.dirname(os.path.abspath(__file__))
    svg_path = os.path.join(out_dir, "app_icon.svg")
    ico_path = os.path.join(out_dir, "app_icon.ico")
    png_path = os.path.join(out_dir, "app_icon.png")

    if not os.path.exists(svg_path):
        print(f"[ERROR] 找不到 {svg_path}")
        return

    sizes = [16, 32, 48, 64, 128, 256]
    images = []
    for s in sizes:
        img = render_svg(svg_path, s)
        images.append(img)
        print(f"  [{s}x{s}]  渲染完成")

    # 保存 ICO（多尺寸）
    images[-1].save(
        ico_path,
        format="ICO",
        append_images=images[:-1],
        sizes=[(s, s) for s in sizes],
    )
    print(f"\n[OK] ICO  -> {ico_path}  (sizes: {sizes})")

    # 顺便保存 256 PNG 便于预览
    images[-1].save(png_path, format="PNG")
    print(f"[OK] PNG  -> {png_path}  (256x256)")


if __name__ == "__main__":
    main()
