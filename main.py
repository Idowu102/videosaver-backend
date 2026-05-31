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
# CONFIG
# =========================================================

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_ME")

PROXIES = os.getenv("PROXY_LIST", "").split(",")

CACHE_TTL = 60 * 30
RATE_LIMIT = 60  # requests per minute per IP

redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

app = FastAPI(title="Media CDN v2")

executor = ThreadPoolExecutor(max_workers=12)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cdn-v2")

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
# SIGNING (JWT-STYLE LIGHTWEIGHT)
# =========================================================

def sign(payload: dict) -> str:
    data = json.dumps(payload, separators=(",", ":"))
    sig = hmac.new(
        SECRET_KEY.encode(),
        data.encode(),
        hashlib.sha256
    ).digest()

    return base64.urlsafe_b64encode(sig + data.encode()).decode()


def verify(token: str):
    try:
        raw = base64.urlsafe_b64decode(token.encode())
        sig = raw[:32]
        data = raw[32:]

        expected_sig = hmac.new(
            SECRET_KEY.encode(),
            data,
            hashlib.sha256
        ).digest()

        if not hmac.compare_digest(sig, expected_sig):
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
# PROXY ROTATION (EXTRACTION ONLY)
# =========================================================

def get_proxy():
    if not PROXIES or PROXIES == [""]:
        return None
    return random.choice(PROXIES)

# =========================================================
# REDIS CACHE
# =========================================================

def cache_get(key):
    val = redis_client.get(key)
    return json.loads(val) if val else None


def cache_set(key, value):
    redis_client.setex(key, CACHE_TTL, json.dumps(value))

# =========================================================
# YT-DLP OPTIONS (HARDENED)
# =========================================================

def ydl_opts():
    proxy = get_proxy()

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
        logger.exception("extract failed")
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
# STREAM PROXY (REAL CDN STYLE)
# =========================================================

def stream_generator(url):
    with requests.get(url, stream=True, timeout=20) as r:
        r.raise_for_status()
        for chunk in r.iter_content(chunk_size=1024 * 512):
            if chunk:
                yield chunk

# =========================================================
# INFO
# =========================================================

@app.get("/v2/info")
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
# SIGN URL
# =========================================================

@app.get("/v2/sign")
def sign_url(url: str):

    if not valid(url):
        raise HTTPException(400, "invalid url")

    payload = {
        "url": url,
        "exp": int(time.time()) + 3600
    }

    token = sign(payload)

    return {
        "stream": f"/v2/stream?token={token}"
    }

# =========================================================
# STREAM (NO DIRECT URL EXPOSURE)
# =========================================================

@app.get("/v2/stream")
async def stream(token: str, request: Request):

    rate_limit(request.client.host)

    payload = verify(token)

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
