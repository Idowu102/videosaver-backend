import os
import time
import json
import hashlib
import random
import logging
import asyncio

import redis
import yt_dlp
import requests

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

# =========================================================
# APP
# =========================================================

app = FastAPI(title="Single Endpoint Media CDN v3")

executor = ThreadPoolExecutor(max_workers=12)

# =========================================================
# REDIS
# =========================================================

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

CACHE_TTL = 60 * 30

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cdn-v3")

# =========================================================
# OPTIONAL PROXY POOL
# =========================================================

PROXIES = os.getenv("PROXY_LIST", "").split(",")

def get_proxy():
    if not PROXIES or PROXIES == [""]:
        return None
    return random.choice(PROXIES)

# =========================================================
# CACHE
# =========================================================

def cache_get(key):
    val = redis_client.get(key)
    return json.loads(val) if val else None


def cache_set(key, value):
    redis_client.setex(key, CACHE_TTL, json.dumps(value))

# =========================================================
# URL VALIDATION
# =========================================================

def valid(url: str):
    host = urlparse(url).netloc.lower()

    allowed = {
        "youtube.com", "www.youtube.com", "youtu.be",
        "facebook.com", "www.facebook.com",
        "tiktok.com", "www.tiktok.com",
        "instagram.com", "www.instagram.com"
    }

    return host in allowed

# =========================================================
# YT-DLP CONFIG
# =========================================================

def ydl_opts():
    opts = {
        "quiet": True,
        "noplaylist": True,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 20,
        "cachedir": False,
        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        },
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "tv", "web"]
            }
        }
    }

    proxy = get_proxy()
    if proxy:
        opts["proxy"] = proxy

    return opts

# =========================================================
# EXTRACTOR
# =========================================================

def extract_sync(url):
    try:
        with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        logger.exception("yt-dlp error")
        return {"error": str(e)}


async def extract(url):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, extract_sync, url)

# =========================================================
# STREAM SELECTOR
# =========================================================

def best_stream(data):
    formats = data.get("formats", [])

    streams = [
        f for f in formats
        if f.get("url") and f.get("vcodec") != "none"
    ]

    if not streams:
        return None

    return max(streams, key=lambda x: x.get("height") or 0)

# =========================================================
# STREAM PROXY (NO LEAKING ORIGIN URL)
# =========================================================

def stream_generator(url):
    with requests.get(url, stream=True, timeout=20) as r:
        r.raise_for_status()

        for chunk in r.iter_content(chunk_size=1024 * 512):
            if chunk:
                yield chunk

# =========================================================
# SINGLE ENDPOINT (THE ENTIRE CDN)
# =========================================================

@app.get("/api/play")
async def play(url: str, request: Request):

    # -------- rate limit light ----------
    ip = request.client.host
    key_rl = f"rl:{ip}"
    count = redis_client.incr(key_rl)
    if count == 1:
        redis_client.expire(key_rl, 60)
    if count > 80:
        raise HTTPException(429, "rate limited")

    # -------- validate ----------
    if not valid(url):
        raise HTTPException(400, "unsupported url")

    # -------- cache ----------
    cache_key = f"play:{url}"
    cached = cache_get(cache_key)

    if cached:
        stream_url = cached["url"]
    else:
        data = await extract(url)

        if "error" in data:
            raise HTTPException(502, data["error"])

        stream = best_stream(data)

        if not stream:
            raise HTTPException(404, "no playable stream found")

        stream_url = stream["url"]

        cache_set(cache_key, {"url": stream_url})

    # -------- stream ----------
    return StreamingResponse(
        stream_generator(stream_url),
        media_type="video/mp4"
    )
