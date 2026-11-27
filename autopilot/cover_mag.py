#!/usr/bin/env python3
"""@uks_camper magazine-style reel cover (the template on the existing reels).

    python3 autopilot/cover_mag.py SOURCE OUT.jpg \
        --series "억스 세팅" --title "캠핑 크림파스타\\n{4단계}로 끝" --no 6 [--at 18.5] [--focus-x 0.5] [--focus-y 0.5]

Layout (1080x1920, everything inside the 3:4 profile-grid crop y 240-1680):
  dark green page #2E493A
  top row:    orange dot logo + "UKS CAMPER" (letter-spaced) ........ "No.06"
  photo:      4:5 window, x 158-922, y 330-1283
  label:      "— 시리즈" in orange
  title:      two lines, bold serif, left aligned, {word} in orange
  rule line, then tagline left and @uks_camper right

SOURCE is a video (frame at --at seconds) or an image.
Writes OUT and OUT_grid.jpg (how it looks on the profile grid).
"""
import argparse
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
BG = (46, 73, 58)
CREAM = (243, 238, 226)
MUTED = (160, 178, 165)
ORANGE = (226, 141, 78)
LOGO = (224, 172, 120)
SERIF = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
SANS = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
SANS_REG = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
KR = 1                      # Korean face inside the CJK collections
PHOTO = (158, 330, 922, 1283)
TAGLINE = "평일은 빠르게, 주말은 느리게"
HANDLE = "@uks_camper"


def font(path, size):
    try:
        return ImageFont.truetype(path, size, index=KR)
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


def spaced(d, xy, text, f, fill, gap):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) + gap
    return x


def rich_line(d, xy, line, f, base, hi):
    x, y = xy
    on, seg = False, ""
    for ch in line + "\0":
        if ch in "{}\0":
            if seg:
                col = hi if on else base
                d.text((x, y), seg, font=f, fill=col, stroke_width=1, stroke_fill=col)
                x += d.textlength(seg, font=f)
                seg = ""
            on = (ch == "{") if ch in "{}" else on
        else:
            seg += ch


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("out")
    ap.add_argument("--series", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--no", type=int, required=True)
    ap.add_argument("--at", type=float, default=0.0)
    ap.add_argument("--focus-x", type=float, default=0.5)
    ap.add_argument("--focus-y", type=float, default=0.5)
    ap.add_argument("--tagline", default=TAGLINE)
    a = ap.parse_args()

    page = Image.new("RGB", (W, H), BG)
    page.paste(fit(grab(a.source, a.at), PHOTO, a.focus_x, a.focus_y), PHOTO[:2])
    d = ImageDraw.Draw(page)
    L, R = PHOTO[0], PHOTO[2]

    # top row
    d.ellipse([L, 268, L + 46, 314], fill=LOGO)
    d.ellipse([L + 12, 280, L + 34, 302], fill=(238, 196, 150))
    spaced(d, (L + 62, 270), "UKS CAMPER", font(SANS, 34), CREAM, 5)
    no = f"No.{a.no:02d}"
    fno = font(SANS, 34)
    width = sum(d.textlength(c, font=fno) + 4 for c in no) - 4
    spaced(d, (R - width, 272), no, fno, CREAM, 4)

    # series label
    fl = font(SANS, 40)
    d.line([L, 1338, L + 40, 1338], fill=ORANGE, width=5)
    d.text((L + 54, 1312), a.series, font=fl, fill=ORANGE)

    # title
    ft = font(SERIF, 96)
    y = 1372
    for line in a.title.replace("\\n", "\n").split("\n")[:2]:
        rich_line(d, (L - 4, y), line, ft, CREAM, ORANGE)
        y += 116

    # rule + footer
    d.line([L, 1612, R, 1612], fill=(88, 112, 96), width=2)
    fs = font(SANS, 28)
    d.text((L, 1626), a.tagline, font=fs, fill=MUTED)
    d.text((R - d.textlength(HANDLE, font=fs), 1626), HANDLE, font=fs, fill=MUTED)

    page.save(a.out, quality=93)
    top = (H - 1440) // 2
    page.crop((0, top, W, top + 1440)).resize((360, 480), Image.LANCZOS).save(
        str(Path(a.out).with_name(Path(a.out).stem + "_grid.jpg")), quality=90)
    print("cover:", a.out)


if __name__ == "__main__":
    main()
