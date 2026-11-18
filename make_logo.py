# -*- coding: utf-8 -*-
"""
logo 生成器：用 PIL 绘制「批量手机电脑传照片」的应用图标
生成 logo.png (512) 和 logo.ico (多尺寸)
"""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
ICO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")

SIZE = 512


def make_logo() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 渐变风格圆角方形背景（深蓝 → 青）
    bg = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    bgd = ImageDraw.Draw(bg)
    # 用一个简单两色拼接的近似渐变
    for y in range(SIZE):
        t = y / SIZE
        r = int(15 + (56 - 15) * t)
        g = int(23 + (189 - 23) * t)
        b = int(42 + (248 - 42) * t)
        bgd.line([(0, y), (SIZE, y)], fill=(r, g, b, 255))
    # 圆角蒙版
    mask = Image.new("L", (SIZE, SIZE), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=110, fill=255)
    img.paste(bg, (0, 0), mask)
    d = ImageDraw.Draw(img)

    cx, cy = SIZE // 2, SIZE // 2

    # 相机机身
    body_w, body_h = 360, 250
    d.rounded_rectangle(
        [cx - body_w // 2, cy - body_h // 2 + 20, cx + body_w // 2, cy + body_h // 2 + 20],
        radius=48,
        fill=(241, 245, 249, 255),
    )
    # 顶部小突出（快门按钮）
    d.rounded_rectangle([cx + 70, cy - body_h // 2 - 18 + 20, cx + 170, cy - body_h // 2 + 34],
                        radius=14, fill=(241, 245, 249, 255))
    d.ellipse([cx - 150, cy - body_h // 2 + 4, cx - 90, cy - body_h // 2 + 64],
              fill=(239, 68, 68, 255))  # 录制红点

    # 镜头外圈
    lens_r = 110
    d.ellipse([cx - lens_r, cy - lens_r + 20, cx + lens_r, cy + lens_r + 20],
              fill=(30, 41, 59, 255))
    # 镜头内环
    ir = 78
    d.ellipse([cx - ir, cy - ir + 20, cx + ir, cy + ir + 20],
              fill=(56, 189, 248, 255))
    # 高光
    hr = 34
    d.ellipse([cx - 40 - hr // 2, cy - 60 + 20 - hr // 2, cx - 40 + hr // 2 + 10, cy - 60 + 20 + hr // 2 + 10],
              fill=(186, 230, 253, 255))

    # “批量/多张”堆叠小图角标
    badge_r = 70
    bx, by = cx + 150, cy + 130
    d.ellipse([bx - badge_r, by - badge_r, bx + badge_r, by + badge_r],
              fill=(34, 197, 94, 255))
    d.ellipse([bx - badge_r + 8, by - badge_r + 8, bx + badge_r - 8, by + badge_r - 8],
              outline=(255, 255, 255, 255), width=6)
    # 角标内的数字 100
    try:
        font = ImageFont.truetype("arialbd.ttf", 64)
    except Exception:
        try:
            font = ImageFont.truetype("arial.ttf", 64)
        except Exception:
            font = ImageFont.load_default()
    txt = "100"
    bb = d.textbbox((0, 0), txt, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    d.text((bx - tw / 2 - bb[0], by - th / 2 - bb[1] + 4), txt,
           font=font, fill=(255, 255, 255, 255))

    return img


if __name__ == "__main__":
    logo = make_logo()
    logo.save(OUT)
    logo.save(ICO, format="ICO",
              sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("logo.png ->", OUT)
    print("logo.ico ->", ICO)
