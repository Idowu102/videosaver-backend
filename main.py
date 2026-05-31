from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
import os
import uuid
import traceback

app = FastAPI(title="Pro Media API")

# -----------------------
# CORS
# -----------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------
# SIMPLE CACHE (Hobby-safe)
# -----------------------
CACHE = {}
CACHE_TTL = 300  # 5 minutes

executor = ThreadPoolExecutor(max_workers=4)

# -----------------------
# HELPERS
# -----------------------
SUPPORTED = ("youtube.com", "youtu.be", "tiktok.com", "facebook.com", "instagram.com")

def is_supported(url: str):
    return any(x in url for x in SUPPORTED)

def clean_url(url: str):
    url = url.strip()
    if "youtube.com/shorts/" in url:
        vid = url.split("/shorts/")[1].split("?")[0]
        return f"https://www.youtube.com/watch?v={vid}"
    return url

def cache_get(key):
    item = CACHE.get(key)
    if not item:
        return None
    if time.time() - item["time"] > CACHE_TTL:
        del CACHE[key]
        return None
    return item["data"]

def cache_set(key, data):
    CACHE[key] = {
        "time": time.time(),
        "data": data
    }

# -----------------------
# YT-DLP OPTIONS
# -----------------------
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

# -----------------------
# SAFE EXTRACT (THREAD)
# -----------------------
def _extract(url, audio=False):
    try:
        with yt_dlp.YoutubeDL(ydl_opts(audio=audio)) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        return {"error": str(e)}

async def extract(url, audio=False):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _extract, url, audio)

# -----------------------
# STREAM PICKER
# -----------------------
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

# -----------------------
# ROUTES
# -----------------------

@app.get("/")
def root():
    return {"status": "online"}

@app.get("/health")
def health():
    return {"status": "ok"}

# -----------------------
# INFO
# -----------------------
@app.get("/info")
async def info(url: str):

    if not is_supported(url):
        raise HTTPException(400, "Unsupported URL")

    url = clean_url(url)
    key = f"info:{url}"

    cached = cache_get(key)
    if cached:
        return cached

    data = await extract(url)

    if not data or "error" in data:
        raise HTTPException(500, "Extraction failed")

    result = {
        "title": data.get("title"),
        "thumbnail": data.get("thumbnail"),
        "duration": data.get("duration"),
    }

    cache_set(key, result)
    return result

# -----------------------
# STREAM
# -----------------------
@app.get("/stream")
async def stream(url: str):

    if not is_supported(url):
        raise HTTPException(400, "Unsupported URL")

    url = clean_url(url)
    key = f"stream:{url}"

    cached = cache_get(key)
    if cached:
        return cached

    data = await extract(url)

    if not data or "error" in data:
        raise HTTPException(500, "Extraction failed (possibly blocked)")

    stream_url = pick_stream(data)

    if not stream_url:
        raise HTTPException(404, "No stream found")

    result = {
        "title": data.get("title"),
        "stream_url": stream_url
    }

    cache_set(key, result)
    return result

# -----------------------
# AUDIO STREAM
# -----------------------
@app.get("/audio-stream")
async def audio_stream(url: str):

    if not is_supported(url):
        raise HTTPException(400, "Unsupported URL")

    url = clean_url(url)
    data = await extract(url, audio=True)

    if not data or "error" in data:
        raise HTTPException(500, "Audio extraction failed")

    audio_url = pick_stream(data)

    if not audio_url:
        raise HTTPException(404, "No audio found")

    return {
        "title": data.get("title"),
        "audio_url": audio_url
    }
