# -*- coding: utf-8 -*-
"""
C盘垃圾清理工具 - 应用图标生成脚本  V2.2.1
作用：根据 app_icon.svg 的设计，用 Pillow 生成多尺寸 app_icon.ico，
      供 PyInstaller 打包 exe 时通过 --icon 嵌入。

运行方式：
    python make_icon.py

依赖：Pillow (pip install Pillow)
注意：此脚本仅用于开发期生成图标资源，不参与 exe 运行，因此不会影响 exe 体积。
"""
import math
import os
from PIL import Image, ImageDraw, ImageFont

# 与 app_icon.svg 一致的配色
C_BLUE_TOP = (59, 130, 246, 255)     # #3b82f6
C_BLUE_BOTTOM = (30, 58, 138, 255)   # #1e3a8a
C_WHITE = (255, 255, 255, 255)
C_GREEN = (16, 185, 129, 255)        # #10b981


def _get_font(size):
    """优先使用 Windows 自带的 Arial Bold，找不到则用默认字体。"""
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def make_icon(size=256):
    """生成指定尺寸的图标。小尺寸（<48）省略右下角徽章以保证清晰度。"""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. 渐变背景（垂直，近似 SVG 对角线渐变）
    grad = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(grad)
    for y in range(size):
        t = y / max(size - 1, 1)
        r = int(C_BLUE_TOP[0] + (C_BLUE_BOTTOM[0] - C_BLUE_TOP[0]) * t)
        g = int(C_BLUE_TOP[1] + (C_BLUE_BOTTOM[1] - C_BLUE_TOP[1]) * t)
        b = int(C_BLUE_TOP[2] + (C_BLUE_BOTTOM[2] - C_BLUE_TOP[2]) * t)
        gdraw.line([(0, y), (size, y)], fill=(r, g, b, 255))

    # 2. 圆角方形 mask（裁剪渐变为圆角方形）
    mask = Image.new("L", (size, size), 0)
    mdraw = ImageDraw.Draw(mask)
    margin = max(1, 8 * size // 256)
    radius = 48 * size // 256
    mdraw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=radius, fill=255
    )
    img.paste(grad, (0, 0), mask)

    # 3. 白色 C 字母（粗体居中）
    font_size = max(8, int(size * 0.72))
    font = _get_font(font_size)
    text = "C"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (size - tw) // 2 - bbox[0]
    ty = (size - th) // 2 - bbox[1] - max(1, size // 64)  # 略微上移给徽章留位
    draw.text((tx, ty), text, fill=C_WHITE, font=font)

    # 4. 右下角绿色徽章（仅大尺寸绘制，避免小尺寸糊掉）
    if size >= 48:
        gcx = int(size * 0.766)
        gcy = int(size * 0.766)
        gr = max(4, 26 * size // 256)
        # 白色描边圆
        stroke = max(2, 4 * size // 256)
        draw.ellipse(
            [gcx - gr - stroke, gcy - gr - stroke, gcx + gr + stroke, gcy + gr + stroke],
            fill=C_WHITE
        )
        # 绿色圆
        draw.ellipse(
            [gcx - gr, gcy - gr, gcx + gr, gcy + gr],
            fill=C_GREEN
        )
        # 白色 4 角星
        s_outer = max(3, 14 * size // 256)
        s_inner = max(1, 4 * size // 256)
        points = []
        for i in range(8):
            angle = math.radians(i * 45 - 90)
            rad = s_outer if i % 2 == 0 else s_inner
            points.append((
                gcx + rad * math.cos(angle),
                gcy + rad * math.sin(angle),
            ))
        draw.polygon(points, fill=C_WHITE)

    return img


def main():
    out_dir = os.path.dirname(os.path.abspath(__file__))
    ico_path = os.path.join(out_dir, "app_icon.ico")
    png_path = os.path.join(out_dir, "app_icon.png")

    # 每个尺寸独立绘制（小尺寸省略徽章，更清晰）
    sizes = [16, 32, 48, 64, 128, 256]
    images = [make_icon(s) for s in sizes]

    # 保存 ICO（多尺寸）
    images[-1].save(
        ico_path,
        format="ICO",
        append_images=images[:-1],
        sizes=[(s, s) for s in sizes],
    )
    print(f"[OK] ICO  -> {ico_path}  (sizes: {sizes})")

    # 顺便保存一个 256 PNG 便于预览
    make_icon(256).save(png_path, format="PNG")
    print(f"[OK] PNG  -> {png_path}  (256x256)")


if __name__ == "__main__":
    main()
