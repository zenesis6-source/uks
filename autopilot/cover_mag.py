#!/usr/bin/env python3
"""@uks_camper reel cover, matched to the user's own template (2026-11-27 sample).

    python3 autopilot/cover_mag.py SOURCE OUT.jpg \
        --series "캠핑요리" --title "4단계로 끝내는\\n캠핑 {크림파스타}" [--at 18.5] [--focus-x .5] [--focus-y .5]

Layout, 1080x1920 (all inside the 3:4 grid crop y 240-1680):
  dark green page with faint grain
  y 292   orange tent logo + "U K S  C A M P E R" ............ "ARCHIVE"
  y 330   photo window x 160-920, y 330-1280, soft drop shadow
  y 1345  orange rule + series label
  y 1395  two-line title (Song Myung), {word} in orange
  y 1600  thin rule, then tagline left / @uks_camper right

SOURCE: a video (frame at --at seconds) or an image. Also writes OUT_grid.jpg.
"""
import argparse
import random
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
BG = (46, 74, 58)
CREAM = (244, 238, 226)
MUTED = (176, 190, 178)
ORANGE = (232, 135, 58)
RULE = (92, 116, 100)
FONTS = Path(__file__).parent / "fonts"
TITLE_FONT = FONTS / "GowunBatang-Bold.ttf"   # 고운바탕 Bold, same as reel subtitles
SANS_B = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
SANS_R = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
PHOTO = (160, 330, 920, 1280)
TAGLINE = "준비는 빠르게, 주말은 느리게"
HANDLE = "@uks_camper"


def font(path, size):
    path = str(path)
    if not Path(path).exists():
        path = SANS_B
    try:
        return ImageFont.truetype(path, size, index=1 if path.endswith(".ttc") else 0)
    except OSError:
        return ImageFont.truetype(path, size)


def grab(src, at):
    p = Path(src)
    if p.suffix.lower() in (".mp4", ".mov", ".m4v"):
        tmp = Path(tempfile.mkdtemp()) / "f.png"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(at), "-i", str(p),
                        "-frames:v", "1", str(tmp)], check=True)
        p = tmp
    return Image.open(p).convert("RGB")


def fit(img, box, fx, fy):
    bw, bh = box[2] - box[0], box[3] - box[1]
    s = max(bw / img.width, bh / img.height)
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x = int((img.width - bw) * fx)
    y = int((img.height - bh) * fy)
    return img.crop((x, y, x + bw, y + bh))


def spaced(d, x, y, text, f, fill, gap, anchor_right=False):
    widths = [d.textlength(c, font=f) for c in text]
    total = sum(widths) + gap * (len(text) - 1)
    if anchor_right:
        x -= total
    for c, w in zip(text, widths):
        d.text((x, y), c, font=f, fill=fill, anchor="lm")
        x += w + gap


def rich(d, x, y, line, f, base, hi, stroke):
    on, seg = False, ""
    for ch in line + "\0":
        if ch in "{}\0":
            if seg:
                col = hi if on else base
                d.text((x, y), seg, font=f, fill=col, stroke_width=stroke, stroke_fill=col)
                x += d.textlength(seg, font=f)
                seg = ""
            if ch == "{":
                on = True
            elif ch == "}":
                on = False
        else:
            seg += ch


def page_bg():
    noise = Image.effect_noise((W, H), 12)
    chans = [Image.eval(noise, lambda v, c=c: max(0, min(255, c + (v - 128) // 16))) for c in BG]
    return Image.merge("RGB", chans)


def logo(d, cx, cy, r=23):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=ORANGE)
    t = [(cx, cy - 12), (cx - 13, cy + 10), (cx + 13, cy + 10)]
    d.polygon(t, outline=CREAM, width=3)
    d.line([(cx, cy - 3), (cx - 5, cy + 9)], fill=CREAM, width=2)
    d.line([(cx, cy - 3), (cx + 5, cy + 9)], fill=CREAM, width=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("out")
    ap.add_argument("--series", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--at", type=float, default=0.0)
    ap.add_argument("--focus-x", type=float, default=0.5)
    ap.add_argument("--focus-y", type=float, default=0.5)
    ap.add_argument("--tagline", default=TAGLINE)
    ap.add_argument("--corner", default="ARCHIVE", help="top-right word")
    a = ap.parse_args()

    page = page_bg()
    L, T, R, B = PHOTO

    # photo with soft shadow
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([L + 6, T + 14, R + 6, B + 18], fill=(0, 0, 0, 120))
    sh = sh.filter(ImageFilter.GaussianBlur(16))
    page = Image.alpha_composite(page.convert("RGBA"), sh).convert("RGB")
    page.paste(fit(grab(a.source, a.at), PHOTO, a.focus_x, a.focus_y), (L, T))
    d = ImageDraw.Draw(page)

    # top row
    logo(d, L + 23, 292)
    spaced(d, L + 60, 292, "UKS CAMPER", font(SANS_B, 30), CREAM, 9)
    spaced(d, R, 292, a.corner, font(SANS_B, 30), CREAM, 6, anchor_right=True)

    # series label
    d.line([L, 1345, L + 34, 1345], fill=ORANGE, width=5)
    spaced(d, L + 50, 1345, a.series, font(SANS_B, 32), ORANGE, 4)

    # title
    ft = font(TITLE_FONT, 94)
    y = 1388
    for line in a.title.replace("\\n", "\n").split("\n")[:2]:
        rich(d, L - 2, y, line, ft, CREAM, ORANGE, 2)
        y += 106

    # footer
    d.line([L, 1600, R, 1600], fill=RULE, width=2)
    fs = font(SANS_R, 30)
    d.text((L, 1640), a.tagline, font=fs, fill=MUTED, anchor="lm")
    d.text((R, 1640), HANDLE, font=fs, fill=MUTED, anchor="rm")

    page.save(a.out, quality=93)
    top = (H - 1440) // 2
    page.crop((0, top, W, top + 1440)).resize((360, 480), Image.LANCZOS).save(
        str(Path(a.out).with_name(Path(a.out).stem + "_grid.jpg")), quality=90)
    print("cover:", a.out)


if __name__ == "__main__":
    main()
