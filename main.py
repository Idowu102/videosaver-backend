from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
import logging
from urllib.parse import urlparse

app = FastAPI(title="Media Gateway CDN v4")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("yt-gateway")

# =========================================================
# THREAD POOL
# =========================================================

executor = ThreadPoolExecutor(max_workers=8)

# =========================================================
# CACHE
# =========================================================

CACHE = {}
CACHE_TTL = 60 * 20

def cache_get(key):
    item = CACHE.get(key)
    if not item:
        return None
    if time.time() > item["exp"]:
        CACHE.pop(key, None)
        return None
    return item["data"]

def cache_set(key, data):
    CACHE[key] = {
        "data": data,
        "exp": time.time() + CACHE_TTL
    }

# =========================================================
# INFLIGHT DEDUP
# =========================================================

INFLIGHT = {}

def inflight_key(url, mode):
    return f"{url}:{mode}"

# =========================================================
# URL NORMALIZER
# =========================================================

def normalize_url(url: str):
    url = url.strip()

    if "youtube.com/shorts/" in url:
        vid = url.split("/shorts/")[1].split("?")[0]
        return f"https://www.youtube.com/watch?v={vid}"

    return url

# =========================================================
# SAFE DOMAIN VALIDATION
# =========================================================

def valid(url: str):
    host = urlparse(url).netloc.lower()

    allowed = {
        "youtube.com", "www.youtube.com",
        "youtu.be",
        "facebook.com", "www.facebook.com",
        "tiktok.com", "www.tiktok.com",
        "instagram.com", "www.instagram.com",
        "x.com", "twitter.com"
    }

    return host in allowed

# =========================================================
# YT-DLP OPTIONS
# =========================================================

def ydl_opts():
    return {
        "quiet": True,
        "noplaylist": True,
        "cachedir": False,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 20,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0 Safari/537.36"
            )
        },
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "tv", "web"]
            }
        }
    }

# =========================================================
# SYNC EXTRACTION
# =========================================================

def extract_sync(url):
    try:
        with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        logger.exception("yt-dlp failed")
        return {"error": str(e)}

# =========================================================
# ASYNC WRAPPER + DEDUP
# =========================================================

async def extract(url, mode="default"):
    key = inflight_key(url, mode)

    if key in INFLIGHT:
        return await INFLIGHT[key]

    loop = asyncio.get_running_loop()
    task = loop.run_in_executor(executor, extract_sync, url)

    INFLIGHT[key] = task

    try:
        return await task
    finally:
        INFLIGHT.pop(key, None)

# =========================================================
# FORMAT SELECTORS
# =========================================================

def best_video(data):
    formats = data.get("formats") or []

    candidates = [
        f for f in formats
        if f.get("url") and f.get("vcodec") != "none"
    ]

    if not candidates:
        return None

    return max(candidates, key=lambda x: x.get("height") or 0)


def best_audio(data):
    formats = data.get("formats") or []

    candidates = [
        f for f in formats
        if f.get("url") and f.get("acodec") != "none"
    ]

    if not candidates:
        return None

    return max(candidates, key=lambda x: x.get("abr") or 0)

# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "media-gateway-v4"
    }

# =========================================================
# INFO
# =========================================================

@app.get("/info")
async def info(url: str):

    url = normalize_url(url)
    if not valid(url):
        raise HTTPException(400, "unsupported url")

    cache_key = f"info:{url}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    data = await extract(url, "info")

    if not data or "error" in data:
        raise HTTPException(502, str(data.get("error", "extract failed")))

    result = {
        "title": data.get("title"),
        "duration": data.get("duration"),
        "thumbnail": data.get("thumbnail"),
        "status": "success"
    }

    cache_set(cache_key, result)
    return result

# =========================================================
# STREAM
# =========================================================

@app.get("/stream")
async def stream(url: str):

    url = normalize_url(url)
    if not valid(url):
        raise HTTPException(400, "unsupported url")

    cache_key = f"stream:{url}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    data = await extract(url, "stream")

    if not data or "error" in data:
        raise HTTPException(502, str(data.get("error", "extract failed")))

    best = best_video(data)

    if not best:
        raise HTTPException(404, "no video stream found")

    result = {
        "status": "success",
        "title": data.get("title"),
        "stream_url": best["url"],
        "quality": best.get("height")
    }

    cache_set(cache_key, result)
    return result

# =========================================================
# AUDIO
# =========================================================

@app.get("/audio")
async def audio(url: str):

    url = normalize_url(url)
    if not valid(url):
        raise HTTPException(400, "unsupported url")

    cache_key = f"audio:{url}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    data = await extract(url, "audio")

    if not data or "error" in data:
        raise HTTPException(502, str(data.get("error", "extract failed")))

    best = best_audio(data)

    if not best:
        raise HTTPException(404, "no audio stream found")

    result = {
        "status": "success",
        "title": data.get("title"),
        "audio_url": best["url"]
    }

    cache_set(cache_key, result)
    return result
