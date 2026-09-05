import feedparser
import anthropic
import json
import os
import re
import asyncio
import edge_tts
import requests
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────
# CONFIG — apni values yahan bharo
# ─────────────────────────────────────────
RSS_URL = "https://cointelegraph.com/rss"
ANTHROPIC_KEY = "[your anthropic api key here]"
PEXELS_KEY    = "[your pexels api key here]"
OUTPUT_DIR    = r"E:\shorts_pipeline\output"
MAX_LINES     = 8
TTS_VOICE     = "en-US-AriaNeural"
# ─────────────────────────────────────────

Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
RUN_DIR   = os.path.join(OUTPUT_DIR, TIMESTAMP)
Path(RUN_DIR).mkdir(parents=True, exist_ok=True)


# ── PHASE 1: RSS → SCRIPT ─────────────────
def fetch_latest_article():
    print("[1/4] RSS feed se article fetch ho raha hai...")
    feed = feedparser.parse(RSS_URL)
    if not feed.entries:
        raise ValueError("RSS feed mein koi entry nahi mili.")
    entry = feed.entries[0]
    content = getattr(entry, "summary", "") or ""
    content = re.sub(r"<[^>]+>", "", content).strip()
    article = {
        "title":     entry.get("title", "No title"),
        "content":   content,
        "link":      entry.get("link", ""),
        "published": entry.get("published", str(datetime.now())),
    }
    print(f"    Article: {article['title'][:70]}...")
    return article


def generate_script(article):
    print("[2/4] Claude se script generate ho rahi hai...")
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    prompt = f"""You are a YouTube Shorts scriptwriter.
Convert this article into a punchy, engaging script for a 45-60 second YouTube Short.

Article Title: {article['title']}
Article Content: {article['content'][:1500]}

Rules:
- Write exactly {MAX_LINES} lines
- Each line should be 1 short sentence (max 12 words)
- First line must be a strong hook that grabs attention
- Last line must be a call to action (like, follow, comment)
- Each line needs 1-3 keywords for finding a matching stock video
- Keep it conversational and energetic
- Write in English

Return ONLY a valid JSON object, no extra text, no markdown:
{{
  "title": "short catchy video title",
  "lines": [
    {{
      "line_number": 1,
      "text": "the spoken line here",
      "keywords": ["keyword1", "keyword2"]
    }}
  ]
}}"""
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = message.content[0].text.strip()
    try:
        script = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            script = json.loads(match.group())
        else:
            raise ValueError(f"Claude ka response valid JSON nahi tha:\n{raw}")
    print(f"    Script ready: {len(script['lines'])} lines")
    return script


# ── PHASE 2: SCRIPT → AUDIO ───────────────
async def generate_audio_for_line(line_text, output_path):
    communicate = edge_tts.Communicate(line_text, voice=TTS_VOICE)
    await communicate.save(output_path)


def generate_all_audio(script):
    print("[3/4] edge-tts se audio generate ho rahi hai...")
    audio_files = []
    for line in script["lines"]:
        filename = os.path.join(RUN_DIR, f"line_{line['line_number']:02d}.mp3")
        asyncio.run(generate_audio_for_line(line["text"], filename))
        audio_files.append(filename)
        print(f"    Audio: line {line['line_number']} → {os.path.basename(filename)}")
    return audio_files


# ── PHASE 3: KEYWORDS → PEXELS VIDEOS ────
def fetch_pexels_video(keywords, line_number):
    # pehle specific keywords try karo, phir generic
    queries_to_try = [
        " ".join(keywords[:2]),
        keywords[0] if keywords else "people",
        "people talking",
        "city street",
        "nature background",
    ]
    
    headers = {"Authorization": PEXELS_KEY}
    
    for query in queries_to_try:
        params = {"query": query, "per_page": 5, "orientation": "portrait"}
        try:
            resp = requests.get(
                "https://api.pexels.com/videos/search",
                headers=headers, params=params, timeout=10
            )
            data   = resp.json()
            videos = data.get("videos", [])
            if not videos:
                continue
            
            # random clip chuno taake repeat na ho
            import random
            video = random.choice(videos[:5])
            
            for vf in video.get("video_files", []):
                if vf.get("quality") in ["hd", "sd"]:
                    url      = vf["link"]
                    filename = os.path.join(RUN_DIR, f"clip_{line_number:02d}.mp4")
                    r = requests.get(url, stream=True, timeout=30)
                    with open(filename, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                    print(f"    Clip {line_number}: '{query}' → downloaded")
                    return filename
        except Exception as e:
            print(f"    Query '{query}' failed: {e}")
            continue
    
    print(f"    Clip {line_number}: koi bhi query kaam nahi aayi")
    return None
    headers = {"Authorization": PEXELS_KEY}
    params  = {"query": query, "per_page": 3, "orientation": "portrait"}
    try:
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers, params=params, timeout=10
        )
        data = resp.json()
        videos = data.get("videos", [])
        if not videos:
            print(f"    No video found for: {query}")
            return None
        video_files = videos[0].get("video_files", [])
        # HD ya SD file dhundo
        for vf in video_files:
            if vf.get("quality") in ["hd", "sd"]:
                url      = vf["link"]
                filename = os.path.join(RUN_DIR, f"clip_{line_number:02d}.mp4")
                r = requests.get(url, stream=True, timeout=30)
                with open(filename, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"    Clip {line_number}: {query} → downloaded")
                return filename
    except Exception as e:
        print(f"    Pexels error for line {line_number}: {e}")
    return None


def fetch_all_videos(script):
    print("[4/4] Pexels se video clips download ho rahi hain...")
    video_files = []
    for line in script["lines"]:
        path = fetch_pexels_video(line["keywords"], line["line_number"])
        video_files.append(path)
    return video_files


# ── SAVE MANIFEST ─────────────────────────
def save_manifest(article, script, audio_files, video_files):
    manifest = {
        "generated_at": str(datetime.now()),
        "run_dir":      RUN_DIR,
        "source": {
            "title":     article["title"],
            "link":      article["link"],
            "published": article["published"],
        },
        "script": script,
        "audio_files":  audio_files,
        "video_files":  video_files,
        "status": {
            "phase1_script": True,
            "phase2_audio":  True,
            "phase3_video":  True,
            "phase4_merge":  False,
            "phase5_upload": False,
        }
    }
    path = os.path.join(RUN_DIR, "manifest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"\n    Manifest saved: {path}")
    return path


# ── MAIN ──────────────────────────────────
def run_pipeline():
    print("\n=== YouTube Shorts Pipeline — Phases 1-3 ===\n")
    try:
        article     = fetch_latest_article()
        script      = generate_script(article)
        audio_files = generate_all_audio(script)
        video_files = fetch_all_videos(script)
        manifest    = save_manifest(article, script, audio_files, video_files)

        print("\n✓ Phases 1-3 complete!")
        print(f"  Output folder: {RUN_DIR}")
        print(f"  Audio files:   {len([a for a in audio_files if a])}")
        print(f"  Video clips:   {len([v for v in video_files if v])}")
        print("\n--- Script Preview ---")
        for line in script["lines"]:
            print(f"  {line['line_number']}. {line['text']}")
        return manifest

    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


if __name__ == "__main__":
    run_pipeline()