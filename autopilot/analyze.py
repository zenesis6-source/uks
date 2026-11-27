#!/usr/bin/env python3
"""Look at a raw video before editing it.

    python3 autopilot/analyze.py raw.mp4 out_dir/

Writes into out_dir:
  analysis.json   duration, size, fps, rotation, audio loudness, scene cuts,
                  quiet stretches, and a per-second motion score
  sheet_XX.jpg    contact sheets: one frame per second with its timestamp, so
                  Claude (or you) can see every second of the footage at once

No network, nothing uploaded. Needs ffmpeg/ffprobe and Pillow.
"""
import json
import math
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
THUMB_W = 216          # each frame in the sheet, keeps 9:16 at 216x384
COLS = 6
ROWS = 4               # 24 seconds per sheet


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(path):
    r = run(["ffprobe", "-v", "error", "-print_format", "json",
             "-show_streams", "-show_format", str(path)])
    data = json.loads(r.stdout or "{}")
    v = next((s for s in data.get("streams", []) if s["codec_type"] == "video"), {})
    a = next((s for s in data.get("streams", []) if s["codec_type"] == "audio"), None)
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(sd["rotation"])
    rot = int(v.get("tags", {}).get("rotate", rot))
    w, h = v.get("width", 0), v.get("height", 0)
    if abs(rot) in (90, 270):
        w, h = h, w
    num, den = (v.get("avg_frame_rate", "0/1").split("/") + ["1"])[:2]
    fps = float(num) / float(den) if float(den) else 0.0
    return {
        "duration": float(data.get("format", {}).get("duration", 0)),
        "width": w, "height": h, "rotation": rot, "fps": round(fps, 2),
        "vertical": h > w,
        "has_audio": a is not None,
    }


def scenes(path, threshold=0.3):
    r = run(["ffmpeg", "-hide_banner", "-i", str(path), "-an",
             "-vf", f"scdet=threshold={threshold * 100}:sc_pass=0",
             "-f", "null", "-"])
    cuts = [round(float(t), 2) for t in re.findall(r"lavfi\.scd\.time:\s*([\d.]+)", r.stderr)]
    return cuts


def motion(path, duration):
    """Mean absolute frame difference per second. 0 = frozen, higher = moving."""
    r = run(["ffmpeg", "-hide_banner", "-i", str(path), "-an",
             "-vf", "scale=160:-2,format=gray,tblend=all_mode=difference,signalstats,"
                    "metadata=print:key=lavfi.signalstats.YAVG",
             "-f", "null", "-"])
    vals = [float(x) for x in re.findall(r"YAVG=([\d.]+)", r.stderr)]
    if not vals:
        return []
    per_sec = max(1, int(round(len(vals) / max(duration, 0.1))))
    out = []
    for i in range(0, len(vals), per_sec):
        chunk = vals[i:i + per_sec]
        out.append(round(sum(chunk) / len(chunk), 2))
    return out


def audio(path):
    r = run(["ffmpeg", "-hide_banner", "-i", str(path), "-vn",
             "-af", "ebur128=peak=true,silencedetect=noise=-40dB:d=1.5",
             "-f", "null", "-"])
    lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    quiet = [[round(max(s, 0), 2), round(e, 2)] for s, e in zip(starts, ends)]
    return {"integrated_lufs": float(lufs[-1]) if lufs else None, "quiet_stretches": quiet}


def sheets(path, duration, out_dir):
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-hide_banner", "-y", "-i", str(path), "-vf",
         f"fps=1,scale={THUMB_W}:-2", "-q:v", "4", str(frames_dir / "f_%04d.jpg")])
    files = sorted(frames_dir.glob("f_*.jpg"))
    if not files:
        return []
    font = ImageFont.truetype(FONT, 20)
    first = Image.open(files[0])
    tw, th = first.size
    per = COLS * ROWS
    made = []
    for s in range(0, len(files), per):
        batch = files[s:s + per]
        rows = math.ceil(len(batch) / COLS)
        sheet = Image.new("RGB", (COLS * tw, rows * th), "black")
        d = ImageDraw.Draw(sheet)
        for i, f in enumerate(batch):
            x, y = (i % COLS) * tw, (i // COLS) * th
            sheet.paste(Image.open(f).resize((tw, th)), (x, y))
            sec = s + i
            label = f"{sec // 60}:{sec % 60:02d}"
            d.rectangle([x, y, x + 64, y + 28], fill="black")
            d.text((x + 4, y + 2), label, font=font, fill="yellow")
        name = out_dir / f"sheet_{s // per + 1:02d}.jpg"
        sheet.save(name, quality=85)
        made.append(str(name))
    return made


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    info = probe(src)
    info["source"] = str(src)
    info["scene_cuts"] = scenes(src)
    info["motion_per_second"] = motion(src, info["duration"])
    info["audio"] = audio(src) if info["has_audio"] else None
    info["sheets"] = sheets(src, info["duration"], out_dir)
    (out_dir / "analysis.json").write_text(json.dumps(info, ensure_ascii=False, indent=2))

    print(f"{src.name}: {info['duration']:.1f}s  {info['width']}x{info['height']}  "
          f"{info['fps']}fps  {'vertical' if info['vertical'] else 'HORIZONTAL - will be cropped'}")
    print(f"scene cuts: {info['scene_cuts'] or 'none (one continuous shot)'}")
    if info["audio"]:
        print(f"loudness: {info['audio']['integrated_lufs']} LUFS  "
              f"quiet stretches: {info['audio']['quiet_stretches'] or 'none'}")
    else:
        print("no audio track")
    m = info["motion_per_second"]
    if m:
        still = [i for i, v in enumerate(m) if v < 0.5]
        print(f"motion: avg {sum(m) / len(m):.2f}, near-still seconds: {still or 'none'}")
    for s in info["sheets"]:
        print("sheet:", s)
    print("analysis:", out_dir / "analysis.json")


if __name__ == "__main__":
    main()
