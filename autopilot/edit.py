#!/usr/bin/env python3
"""Cut raw footage into a 1080x1920 Reel from an edit plan.

    python3 autopilot/edit.py plan.json

plan.json:
{
  "output": "work/out.mp4",
  "clips": [
    {"src": "raw.mp4", "in": 2.0, "out": 5.5},
    {"src": "raw.mp4", "in": 10, "out": 14, "speed": 1.0, "focus_x": 0.5}
  ],
  "cards": [
    {"start": 0.0, "end": 3.0, "text": "불 앞에 앉은 우리 가족,\\n뭘 했을까요?", "pos": "top"},
    {"start": 4.0, "end": 7.0, "text": "아무것도요.", "pos": "middle"}
  ],
  "audio": {"original_volume": 1.0, "music": null, "music_volume": 0.25},
  "fade_out": 0.6
}

- clips play in order. Times are seconds in the source file.
- focus_x (0..1) picks where to crop a horizontal shot. 0.5 = centre.
- speed 0.5..2.0 slows or speeds a clip (audio follows).
- cards are times on the FINISHED reel. pos: top | middle | low.
  Cards are drawn inside Instagram's safe zone (y 230-1440, right 230px clear).
- audio is normalised to -14 LUFS, Instagram's playback level.

Output: H.264 + AAC, 30fps, 1080x1920, the format Instagram accepts as-is.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_SIZE = 64
TEXT_LEFT, TEXT_RIGHT = 230, W - 230      # centred, right 230px kept clear
SAFE_TOP, SAFE_BOTTOM = 230, 1440
POS_Y = {"top": 330, "middle": 860, "low": 1240}


def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"ffmpeg failed:\n{' '.join(cmd)}\n{r.stderr[-2000:]}")
    return r


def has_audio(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a",
                        "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    return bool(r.stdout.strip())


def atempo(speed):
    parts, s = [], speed
    while s > 2.0:
        parts.append("atempo=2.0")
        s /= 2.0
    while s < 0.5:
        parts.append("atempo=0.5")
        s /= 0.5
    parts.append(f"atempo={s:.4f}")
    return ",".join(parts)


def cut_clip(clip, dst, base):
    src = Path(clip["src"])
    if not src.is_absolute():
        src = (base / src).resolve()
    t0, t1 = float(clip["in"]), float(clip["out"])
    if t1 <= t0:
        sys.exit(f"clip {clip}: out must be after in")
    speed = float(clip.get("speed", 1.0))
    fx = min(max(float(clip.get("focus_x", 0.5)), 0.0), 1.0)
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,"
          f"crop={W}:{H}:(iw-{W})*{fx}:(ih-{H})/2,"
          f"setpts=PTS/{speed},fps={FPS},setsar=1,format=yuv420p")
    cmd = ["ffmpeg", "-hide_banner", "-y", "-ss", str(t0), "-to", str(t1), "-i", str(src)]
    if has_audio(src):
        af = f"{atempo(speed)},aresample=48000,aformat=channel_layouts=stereo"
        cmd += ["-vf", vf, "-af", af]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                "-vf", vf, "-map", "0:v", "-map", "1:a", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k", str(dst)]
    sh(cmd)
    return (t1 - t0) / speed


def wrap(text, font, max_w, draw):
    lines = []
    for para in text.split("\n"):
        cur = ""
        for ch in para:
            trial = cur + ch
            if draw.textlength(trial, font=font) <= max_w or not cur:
                cur = trial
            else:
                # break at the last space if there is one
                if " " in cur:
                    head, tail = cur.rsplit(" ", 1)
                    lines.append(head)
                    cur = tail + ch
                else:
                    lines.append(cur)
                    cur = ch
        lines.append(cur)
    return [l.strip() for l in lines]


def render_card(card, dst):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, int(card.get("size", FONT_SIZE)))
    max_w = TEXT_RIGHT - TEXT_LEFT
    lines = wrap(card["text"], font, max_w, d)
    asc, desc = font.getmetrics()
    lh = int((asc + desc) * 1.25)
    block_h = lh * len(lines)
    y = int(card["y"]) if "y" in card else POS_Y.get(card.get("pos", "middle"), POS_Y["middle"])
    y = min(max(y, SAFE_TOP), SAFE_BOTTOM - block_h)
    cx = (TEXT_LEFT + TEXT_RIGHT) // 2
    for i, line in enumerate(lines):
        tw = d.textlength(line, font=font)
        x = cx - tw / 2
        yy = y + i * lh
        for dx, dy in ((0, 4), (2, 4), (-2, 4), (0, 6)):          # soft drop shadow
            d.text((x + dx, yy + dy), line, font=font, fill=(0, 0, 0, 150))
        d.text((x, yy), line, font=font, fill=(255, 255, 255, 255),
               stroke_width=3, stroke_fill=(0, 0, 0, 200))
    img.save(dst)
    return {"lines": lines, "top": y, "bottom": y + block_h}


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    plan_path = Path(sys.argv[1]).resolve()
    base = plan_path.parent
    plan = json.loads(plan_path.read_text())
    out = Path(plan.get("output", "reel.mp4"))
    if not out.is_absolute():
        out = base / out
    out.parent.mkdir(parents=True, exist_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix="reel_"))
    try:
        total = 0.0
        list_file = tmp / "list.txt"
        with list_file.open("w") as lf:
            for i, clip in enumerate(plan["clips"]):
                seg = tmp / f"seg_{i:03d}.mp4"
                total += cut_clip(clip, seg, base)
                lf.write(f"file '{seg}'\n")
        joined = tmp / "joined.mp4"
        sh(["ffmpeg", "-hide_banner", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_file), "-c", "copy", str(joined)])

        inputs = ["-i", str(joined)]
        audio_cfg = plan.get("audio", {}) or {}
        music = audio_cfg.get("music")
        n = 1
        music_idx = None
        if music:
            mp = Path(music) if Path(music).is_absolute() else base / music
            inputs += ["-stream_loop", "-1", "-i", str(mp)]
            music_idx = n
            n += 1

        filters, last = [], "0:v"
        report = []
        for j, card in enumerate(plan.get("cards", [])):
            png = tmp / f"card_{j:02d}.png"
            info = render_card(card, png)
            inputs += ["-loop", "1", "-t", f"{total:.3f}", "-i", str(png)]
            s, e = float(card["start"]), float(card["end"])
            nxt = f"v{j}"
            filters.append(f"[{last}][{n}:v]overlay=0:0:enable='between(t,{s},{e})'[{nxt}]")
            last, n = nxt, n + 1
            report.append((s, e, info))

        fade = float(plan.get("fade_out", 0) or 0)
        vchain = f"[{last}]"
        if fade > 0:
            filters.append(f"{vchain}fade=t=out:st={max(total - fade, 0):.3f}:d={fade}[vout]")
        else:
            filters.append(f"{vchain}null[vout]")

        ov = float(audio_cfg.get("original_volume", 1.0))
        a = f"[0:a]volume={ov}[a0]"
        filters.append(a)
        amix_src = "[a0]"
        if music_idx is not None:
            mv = float(audio_cfg.get("music_volume", 0.25))
            filters.append(f"[{music_idx}:a]volume={mv},aresample=48000[am]")
            filters.append(f"[a0][am]amix=inputs=2:duration=first:dropout_transition=0[amx]")
            amix_src = "[amx]"
        afade = f",afade=t=out:st={max(total - fade, 0):.3f}:d={fade}" if fade > 0 else ""
        filters.append(f"{amix_src}loudnorm=I=-14:TP=-1.5:LRA=11{afade},aresample=48000[aout]")

        sh(["ffmpeg", "-hide_banner", "-y", *inputs,
            "-filter_complex", ";".join(filters),
            "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.3f}",
            "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
            "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", str(out)])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"REEL  {out}  ·  {total:.1f}s  ·  {len(plan['clips'])} clips  ·  {len(report)} cards")
    for s, e, info in report:
        print(f"  {s:5.1f}-{e:5.1f}s  y {info['top']}-{info['bottom']}  {' / '.join(info['lines'])}")
    if total < 3:
        print("  WARN shorter than 3s: Instagram will refuse it")
    if total > 90:
        print("  WARN over 90s: fine for Instagram, long for this channel")


if __name__ == "__main__":
    main()
