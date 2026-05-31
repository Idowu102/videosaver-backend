import os
import time
import json
import hmac
import hashlib
import base64
import asyncio
import logging
import random

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

app = FastAPI(title="Media CDN Production v1 (LOCKED)")

executor = ThreadPoolExecutor(max_workers=12)

# =========================================================
# REDIS
# =========================================================

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

CACHE_TTL = 60 * 30
RATE_LIMIT = 60

# =========================================================
# SECURITY KEY
# =========================================================

SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_ME")

# =========================================================
# PROXY LIST (OPTIONAL)
# =========================================================

PROXIES = os.getenv("PROXY_LIST", "").split(",")

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cdn")

# =========================================================
# RATE LIMIT
# =========================================================

def rate_limit(ip: str):
    key = f"rate:{ip}"
    count = redis_client.incr(key)

    if count == 1:
        redis_client.expire(key, 60)

    if count > RATE_LIMIT:
        raise HTTPException(429, "rate limit exceeded")

# =========================================================
# SIGNING
# =========================================================

def sign_payload(data: str) -> str:
    sig = hmac.new(
        SECRET_KEY.encode(),
        data.encode(),
        hashlib.sha256
    ).digest()

    return base64.urlsafe_b64encode(sig + data.encode()).decode()


def verify_token(token: str):
    try:
        raw = base64.urlsafe_b64decode(token.encode())
        sig = raw[:32]
        data = raw[32:]

        expected = hmac.new(
            SECRET_KEY.encode(),
            data,
            hashlib.sha256
        ).digest()

        if not hmac.compare_digest(sig, expected):
            return None

        return json.loads(data)

    except Exception:
        return None

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
# CACHE
# =========================================================

def cache_get(key):
    val = redis_client.get(key)
    return json.loads(val) if val else None


def cache_set(key, value):
    redis_client.setex(key, CACHE_TTL, json.dumps(value))

# =========================================================
# YT-DLP OPTIONS
# =========================================================

def get_proxy():
    if not PROXIES or PROXIES == [""]:
        return None
    return random.choice(PROXIES)


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
# STREAM GENERATOR (PROXY)
# =========================================================

def stream_generator(url):
    with requests.get(url, stream=True, timeout=20) as r:
        r.raise_for_status()
        for chunk in r.iter_content(chunk_size=1024 * 512):
            if chunk:
                yield chunk

# =========================================================
# API v1 INFO
# =========================================================

@app.get("/api/v1/info")
async def info(url: str, request: Request):

    rate_limit(request.client.host)

    if not valid(url):
        raise HTTPException(400, "invalid url")

    cache_key = f"info:{url}"
    cached = cache_get(cache_key)

    if cached:
        return cached

    data = await extract(url)

    if "error" in data:
        raise HTTPException(502, data["error"])

    result = {
        "title": data.get("title"),
        "duration": data.get("duration"),
        "thumbnail": data.get("thumbnail")
    }

    cache_set(cache_key, result)
    return result

# =========================================================
# SIGN URL (SECURE)
# =========================================================

@app.get("/api/v1/sign")
def sign(url: str):

    if not valid(url):
        raise HTTPException(400, "invalid url")

    payload = {
        "url": url,
        "exp": int(time.time()) + 3600
    }

    token = sign_payload(json.dumps(payload))

    return {
        "stream": f"/api/v1/stream?token={token}"
    }

# =========================================================
# STREAM (NO DIRECT URL EXPOSURE)
# =========================================================

@app.get("/api/v1/stream")
async def stream(token: str, request: Request):

    rate_limit(request.client.host)

    payload = verify_token(token)

    if not payload:
        raise HTTPException(403, "invalid token")

    if payload["exp"] < time.time():
        raise HTTPException(403, "expired")

    url = payload["url"]

    if not valid(url):
        raise HTTPException(400, "invalid url")

    cache_key = f"stream:{url}"
    cached = cache_get(cache_key)

    if cached:
        stream_url = cached["url"]
    else:
        data = await extract(url)

        if "error" in data:
            raise HTTPException(502, data["error"])

        best = best_stream(data)

        if not best:
            raise HTTPException(404, "no stream found")

        stream_url = best["url"]
        cache_set(cache_key, {"url": stream_url})

    return StreamingResponse(
        stream_generator(stream_url),
        media_type="video/mp4"
    )

# =========================================================
# AUDIO (OPTIONAL BASIC SUPPORT)
# =========================================================

@app.get("/api/v1/audio")
async def audio(url: str, request: Request):

    rate_limit(request.client.host)

    if not valid(url):
        raise HTTPException(400, "invalid url")

    data = await extract(url)

    if "error" in data:
        raise HTTPException(502, data["error"])

    formats = data.get("formats", [])

    audio_streams = [
        f for f in formats
        if f.get("acodec") != "none"
    ]

    if not audio_streams:
        raise HTTPException(404, "no audio found")

    best = max(audio_streams, key=lambda x: x.get("abr") or 0)

    return {
        "title": data.get("title"),
        "audio_url": best["url"]
    }

# =========================================================
# LEGACY SUPPORT (PREVENT 404 FOREVER)
# =========================================================

@app.get("/stream")
def legacy_stream():
    raise HTTPException(410, "use /api/v1/stream")

@app.get("/audio")
def legacy_audio():
    raise HTTPException(410, "use /api/v1/audio")

@app.get("/info")
def legacy_info():
    raise HTTPException(410, "use /api/v1/info")
