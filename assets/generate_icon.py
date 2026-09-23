"""Regenerates assets/icon.{png,ico,icns}. Run: python assets/generate_icon.py

Dev-time only — not a runtime dependency of the app.
"""
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 512
BG_TOP = (37, 99, 235)      # accent blue
BG_BOTTOM = (29, 78, 216)
GLYPH = (255, 255, 255)
BADGE = (34, 197, 94)       # green "done/renamed" badge
OUT_DIR = Path(__file__).resolve().parent


def rounded_square_gradient(size: int, radius: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    grad = Image.new("RGBA", (size, size))
    for y in range(size):
        t = y / (size - 1)
        r = round(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = round(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = round(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        for x in range(size):
            grad.putpixel((x, y), (r, g, b, 255))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    img.paste(grad, (0, 0), mask)
    return img


def build_icon() -> Image.Image:
    img = rounded_square_gradient(SIZE, radius=SIZE // 4)
    draw = ImageDraw.Draw(img)

    # Play triangle (media), slightly left of center.
    cx, cy = SIZE * 0.44, SIZE * 0.5
    r = SIZE * 0.24
    draw.polygon(
        [(cx - r * 0.6, cy - r), (cx - r * 0.6, cy + r), (cx + r * 0.9, cy)],
        fill=GLYPH,
    )

    # Checkmark badge (renamed/organized), bottom-right, overlapping the edge.
    bx, by, br = SIZE * 0.76, SIZE * 0.74, SIZE * 0.19
    draw.ellipse([bx - br, by - br, bx + br, by + br], fill=BADGE, outline=BG_BOTTOM, width=round(SIZE * 0.02))
    check_w = round(SIZE * 0.03)
    draw.line([(bx - br * 0.5, by), (bx - br * 0.12, by + br * 0.4)], fill=GLYPH, width=check_w, joint="curve")
    draw.line([(bx - br * 0.12, by + br * 0.4), (bx + br * 0.55, by - br * 0.35)], fill=GLYPH, width=check_w, joint="curve")

    return img


def main():
    icon = build_icon()
    icon.save(OUT_DIR / "icon.png")
    icon.save(OUT_DIR / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    icon.save(OUT_DIR / "icon.icns")  # macOS
    print(f"Wrote icon.png, icon.ico, icon.icns to {OUT_DIR}")


if __name__ == "__main__":
    main()
