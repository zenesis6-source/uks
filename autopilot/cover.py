#!/usr/bin/env python3
"""Make a 1080x1920 reel cover in the feed style (see .claude/instagram/feed.md).

    python3 autopilot/cover.py SOURCE OUT.jpg --series "느려터진 주말" --title "이 불, 몇 초까지\\n볼 수 있어요?" [--at 2.0] [--focus-x 0.5]

SOURCE can be a video (frame taken at --at seconds) or an image/screenshot.
Text sits inside the 3:4 profile-grid crop (y 240-1680). Also writes OUT_grid.jpg,
the way the cover looks on the profile grid.
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from edit import W, H, render_card  # noqa: E402


def frame(src, at):
    tmp = Path(tempfile.mkdtemp()) / "f.png"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(at), "-i", str(src),
                    "-frames:v", "1", str(tmp)], check=True)
    return Image.open(tmp)


def fill(img, fx):
    img = img.convert("RGB")
    s = max(W / img.width, H / img.height)
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    x = int((img.width - W) * fx)
    y = (img.height - H) // 2
    return img.crop((x, y, x + W, y + H))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("out")
    ap.add_argument("--series", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--at", type=float, default=0.0)
    ap.add_argument("--focus-x", type=float, default=0.5)
    a = ap.parse_args()
    src = Path(a.source)
    if src.suffix.lower() in (".mp4", ".mov", ".m4v"):
        base = frame(src, a.at)
    else:
        base = Image.open(src)
    img = fill(base, a.focus_x).convert("RGBA")
    tmp = Path(tempfile.mkdtemp())
    for i, card in enumerate([{"text": a.series, "y": 290, "size": 38},
                              {"text": a.title.replace("\\n", "\n"), "y": 372, "size": 60}]):
        p = tmp / f"c{i}.png"
        render_card(card, p)
        img.alpha_composite(Image.open(p))
    img = img.convert("RGB")
    img.save(a.out, quality=92)
    top = (H - 1440) // 2
    grid = img.crop((0, top, W, top + 1440)).resize((360, 480))
    grid.save(str(Path(a.out).with_name(Path(a.out).stem + "_grid.jpg")), quality=88)
    print("cover:", a.out)


if __name__ == "__main__":
    main()
