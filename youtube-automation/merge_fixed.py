import json
import os
import glob
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from moviepy import VideoFileClip, AudioFileClip, CompositeVideoClip, ImageClip, concatenate_videoclips

# ─────────────────────────────────────────
OUTPUT_DIR = r"E:\shorts_pipeline\output"
TARGET_W   = 1080
TARGET_H   = 1920
# ─────────────────────────────────────────


def get_latest_run():
    runs = sorted(glob.glob(os.path.join(OUTPUT_DIR, "*")), reverse=True)
    for run in runs:
        if os.path.exists(os.path.join(run, "manifest.json")):
            return run
    raise ValueError("Koi run folder nahi mila.")


def load_manifest(run_dir):
    with open(os.path.join(run_dir, "manifest.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def crop_to_portrait(clip):
    w, h = clip.size
    target_ratio = TARGET_W / TARGET_H
    if w / h > target_ratio:
        new_w = int(h * target_ratio)
        x1 = (w - new_w) // 2
        clip = clip.cropped(x1=x1, y1=0, x2=x1+new_w, y2=h)
    else:
        new_h = int(w / target_ratio)
        y1 = (h - new_h) // 2
        clip = clip.cropped(x1=0, y1=y1, x2=w, y2=y1+new_h)
    return clip.resized((TARGET_W, TARGET_H))


def make_caption_clip(text, duration, video_w, video_h):
    """PIL se caption image banao — reliable aur fast"""
    text = text.replace("\u2014", "-").replace("\u2013", "-")

    font_size  = 52
    padding    = 20
    max_width  = video_w - 80

    # font load karo
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()

    # word wrap karo
    words    = text.split()
    lines    = []
    cur_line = []
    dummy_img = Image.new("RGBA", (1, 1))
    draw      = ImageDraw.Draw(dummy_img)

    for word in words:
        test_line = " ".join(cur_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w    = bbox[2] - bbox[0]
        if w <= max_width:
            cur_line.append(word)
        else:
            if cur_line:
                lines.append(" ".join(cur_line))
            cur_line = [word]
    if cur_line:
        lines.append(" ".join(cur_line))

    # text block size calculate karo
    line_height = font_size + 8
    text_h      = len(lines) * line_height
    text_w      = max(
        draw.textbbox((0, 0), line, font=font)[2]
        for line in lines
    )

    box_w = text_w + padding * 2
    box_h = text_h + padding * 2

    # caption image banao
    img  = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # semi-transparent background
    draw.rounded_rectangle(
        [0, 0, box_w - 1, box_h - 1],
        radius=12,
        fill=(0, 0, 0, 160)
    )

    # text draw karo
    for i, line in enumerate(lines):
        bbox   = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        x      = (box_w - line_w) // 2
        y      = padding + i * line_height

        # shadow
        draw.text((x+2, y+2), line, font=font, fill=(0, 0, 0, 200))
        # main text
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))

    # ImageClip banao — center of screen
    cap_x = (video_w - box_w) // 2
    cap_y = (video_h - box_h) // 2

    arr  = np.array(img)
    clip = (ImageClip(arr)
            .with_position((cap_x, cap_y))
            .with_duration(duration))
    return clip


def build_video(run_dir, manifest):
    print("\n=== Phase 4: Video Merge ===\n")

    lines       = manifest["script"]["lines"]
    audio_files = manifest["audio_files"]
    video_files = manifest["video_files"]
    available   = [v for v in video_files if v and os.path.exists(v)]

    if not available:
        raise ValueError("Koi video clip nahi mili!")

    print(f"  Lines: {len(lines)} | Audio: {len(audio_files)} | Clips: {len(available)}")

    final_clips = []
    clip_index  = 0

    for i, line in enumerate(lines):
        audio_path = audio_files[i] if i < len(audio_files) else None
        if not audio_path or not os.path.exists(audio_path):
            print(f"  Line {line['line_number']}: audio nahi mila, skip")
            continue

        audio_clip = AudioFileClip(audio_path)
        audio_dur  = audio_clip.duration
        print(f"  Line {line['line_number']}: {audio_dur:.1f}s — \"{line['text'][:50]}\"")

        vpath      = available[clip_index % len(available)]
        clip_index += 1
        vid        = VideoFileClip(vpath)
        vid        = crop_to_portrait(vid)

        if vid.duration < audio_dur:
            loops = int(audio_dur / vid.duration) + 1
            vid   = concatenate_videoclips([vid] * loops)
        vid = vid.subclipped(0, audio_dur)

        # PIL caption
        caption = make_caption_clip(line["text"], audio_dur, TARGET_W, TARGET_H)
        composed = CompositeVideoClip([vid, caption])
        final_clips.append(composed.with_audio(audio_clip))

    if not final_clips:
        raise ValueError("Koi clip nahi bani!")

    print(f"\n  {len(final_clips)} clips merging...")
    final = concatenate_videoclips(final_clips, method="compose")

    out = os.path.join(run_dir, "final_short.mp4")
    print(f"  Exporting → {out}  ({final.duration:.1f}s)")

    final.write_videofile(
        out,
        fps=30,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=os.path.join(run_dir, "temp_audio.m4a"),
        remove_temp=True,
        logger="bar",
    )

    manifest["status"]["phase4_merge"] = True
    manifest["final_video"] = out
    with open(os.path.join(run_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Phase 4 complete! → {out}")
    return out


if __name__ == "__main__":
    run_dir  = get_latest_run()
    print(f"Run folder: {run_dir}")
    manifest = load_manifest(run_dir)
    build_video(run_dir, manifest)
