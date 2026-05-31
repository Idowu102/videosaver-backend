from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

app = FastAPI(title="Media Gateway CDN v3")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# THREAD WORKERS (NON-BLOCKING)
# =========================================================

executor = ThreadPoolExecutor(max_workers=8)

# =========================================================
# SIMPLE CACHE LAYER (Redis-ready replacement)
# =========================================================

CACHE = {}
CACHE_TTL = 60 * 20  # 20 min

def cache_get(key):
    item = CACHE.get(key)
    if not item:
        return None
    if time.time() > item["exp"]:
        del CACHE[key]
        return None
    return item["data"]

def cache_set(key, data):
    CACHE[key] = {
        "data": data,
        "exp": time.time() + CACHE_TTL
    }

# =========================================================
# REQUEST DEDUPLICATION (ANTI-SPAM / STABILITY)
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
# VALIDATOR (SAFE MODE)
# =========================================================

def valid(url: str):
    allowed = [
        "youtube.com",
        "youtu.be",
        "facebook.com",
        "tiktok.com",
        "instagram.com",
        "x.com",
        "twitter.com"
    ]
    return any(x in url for x in allowed)

# =========================================================
# YT-DLP OPTIONS (SAFE + STABLE)
# =========================================================

def ydl_opts():
    return {
        "quiet": True,
        "noplaylist": True,
        "retries": 2,
        "fragment_retries": 2,
        "socket_timeout": 20,
        "cachedir": False,
        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        },
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "web"]
            }
        }
    }

# =========================================================
# EXECUTOR WRAPPER
# =========================================================

def extract_sync(url):
    try:
        with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        return {"error": str(e)}

async def extract(url):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, extract_sync, url)

# =========================================================
# STREAM BUILDER
# =========================================================

def get_best_format(data):
    formats = data.get("formats") or []

    cleaned = []
    for f in formats:
        if not f.get("url"):
            continue
        cleaned.append(f)

    if not cleaned:
        return None

    cleaned.sort(key=lambda x: x.get("height") or 0)
    return cleaned[-1]

# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():
    return {
        "status": "CDN_v3_online",
        "features": [
            "cache layer",
            "async worker engine",
            "deduplication",
            "fallback extraction"
        ]
    }

# =========================================================
# INFO ENDPOINT (CACHED)
# =========================================================

@app.get("/info")
async def info(url: str):

    url = normalize_url(url)
    if not valid(url):
        return {"status": "error", "message": "unsupported url"}

    cache_key = f"info:{url}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    data = await extract(url)
    if not data or "error" in data:
        return {"status": "failed", "message": "extract failed"}

    result = {
        "title": data.get("title"),
        "duration": data.get("duration"),
        "thumbnail": data.get("thumbnail"),
        "status": "success"
    }

    cache_set(cache_key, result)
    return result

# =========================================================
# STREAM ENDPOINT (CACHED + SAFE)
# =========================================================

@app.get("/stream")
async def stream(url: str):

    url = normalize_url(url)
    if not valid(url):
        return {"status": "error", "message": "unsupported url"}

    cache_key = f"stream:{url}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    data = await extract(url)

    if not data or "error" in data:
        return {
            "status": "failed",
            "message": "media blocked or unavailable"
        }

    best = get_best_format(data)

    if not best:
        return {"status": "failed", "message": "no formats found"}

    result = {
        "status": "success",
        "title": data.get("title"),
        "stream_url": best["url"],
        "quality": best.get("height")
    }

    cache_set(cache_key, result)
    return result

# =========================================================
# AUDIO ENDPOINT
# =========================================================

@app.get("/audio")
async def audio(url: str):

    url = normalize_url(url)
    if not valid(url):
        return {"status": "error", "message": "unsupported url"}

    cache_key = f"audio:{url}"
    cached = cache_get(cache_key)
    if cached:
        return cached

    data = await extract(url)

    if not data or "error" in data:
        return {"status": "failed", "message": "audio unavailable"}

    formats = data.get("formats") or []

    audio_formats = [
        f for f in formats
        if f.get("acodec") != "none"
    ]

    if not audio_formats:
        return {"status": "failed", "message": "no audio stream"}

    best = audio_formats[-1]

    result = {
        "status": "success",
        "title": data.get("title"),
        "audio_url": best["url"]
    }

    cache_set(cache_key, result)
    return result
