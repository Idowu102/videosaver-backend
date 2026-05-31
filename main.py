from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import asyncio
import re
from concurrent.futures import ThreadPoolExecutor

app = FastAPI(title="Media API with Validator Layer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor(max_workers=4)

# =========================================================
# VALIDATOR LAYER (CORE FIX)
# =========================================================

def validate_url(url: str):

    if not url:
        return False, "empty url"

    url = url.strip()

    # block Facebook share redirects (YOUR ERROR)
    if "facebook.com/share" in url:
        return False, "invalid facebook share link"

    # block obvious invalid patterns
    if "/share/r/" in url:
        return False, "expired share link"

    # require supported domains
    allowed = [
        "youtube.com",
        "youtu.be",
        "facebook.com",
        "tiktok.com",
        "instagram.com",
        "twitter.com",
        "x.com"
    ]

    if not any(x in url for x in allowed):
        return False, "unsupported platform"

    return True, url

# =========================================================
# CLEAN URL
# =========================================================

def clean_url(url: str):

    url = url.strip()

    # YouTube shorts fix
    if "youtube.com/shorts/" in url:
        vid = url.split("/shorts/")[1].split("?")[0]
        return f"https://www.youtube.com/watch?v={vid}"

    return url

# =========================================================
# YT-DLP OPTIONS
# =========================================================

def ydl_opts(audio=False):

    return {
        "format": "bestaudio/best" if audio else "bv*+ba/best",
        "quiet": True,
        "noplaylist": True,
        "retries": 2,
        "fragment_retries": 2,
        "socket_timeout": 20,
        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        },
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        }
    }

# =========================================================
# SAFE EXECUTOR WRAPPER
# =========================================================

def _extract(url, audio=False):
    try:
        with yt_dlp.YoutubeDL(ydl_opts(audio=audio)) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        return {"error": str(e)}

async def extract(url, audio=False):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _extract, url, audio)

# =========================================================
# STREAM PICKER (SAFE)
# =========================================================

def pick_stream(data):

    if not isinstance(data, dict):
        return None

    if data.get("url"):
        return data["url"]

    formats = data.get("formats") or []

    for f in reversed(formats):
        if isinstance(f, dict) and f.get("url"):
            return f["url"]

    return None

# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():
    return {"status": "online", "layer": "validator-enabled"}

# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():
    return {"status": "ok"}

# =========================================================
# INFO
# =========================================================

@app.get("/info")
async def info(url: str):

    ok, result = validate_url(url)
    if not ok:
        raise HTTPException(400, result)

    url = clean_url(result)

    data = await extract(url)

    if not isinstance(data, dict) or "error" in data:
        raise HTTPException(422, "media unavailable")

    return {
        "title": data.get("title"),
        "duration": data.get("duration"),
        "thumbnail": data.get("thumbnail")
    }

# =========================================================
# STREAM
# =========================================================

@app.get("/stream")
async def stream(url: str):

    ok, result = validate_url(url)
    if not ok:
        raise HTTPException(400, result)

    url = clean_url(result)

    data = await extract(url)

    if not isinstance(data, dict) or "error" in data:
        raise HTTPException(422, "media unavailable or blocked")

    stream_url = pick_stream(data)

    if not stream_url:
        raise HTTPException(404, "no stream found")

    return {
        "title": data.get("title"),
        "stream_url": stream_url
    }

# =========================================================
# AUDIO STREAM
# =========================================================

@app.get("/audio-stream")
async def audio_stream(url: str):

    ok, result = validate_url(url)
    if not ok:
        raise HTTPException(400, result)

    url = clean_url(result)

    data = await extract(url, audio=True)

    if not isinstance(data, dict) or "error" in data:
        raise HTTPException(422, "audio unavailable")

    audio_url = pick_stream(data)

    if not audio_url:
        raise HTTPException(404, "no audio found")

    return {
        "title": data.get("title"),
        "audio_url": audio_url
    }
