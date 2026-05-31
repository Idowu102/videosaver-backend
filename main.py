import os
import time
import hmac
import hashlib
import base64
import asyncio
import random
import logging
import requests
import redis
import yt_dlp

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor

# =========================================================
# CONFIG
# =========================================================

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_ME_SUPER_SECRET")

PROXIES = os.getenv("PROXY_LIST", "").split(",")  # http://ip:port,http://ip2:port

CACHE_TTL = 60 * 20

redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

app = FastAPI(title="Media CDN Pro v1")

executor = ThreadPoolExecutor(max_workers=10)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cdn")

# =========================================================
# SIGNED URL SYSTEM
# =========================================================

def sign_payload(data: str) -> str:
    sig = hmac.new(SECRET_KEY.encode(), data.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode()

def verify_signature(url: str, exp: str, sig: str):
    if time.time() > float(exp):
        return False

    payload = f"{url}:{exp}"
    expected = sign_payload(payload)

    return hmac.compare_digest(expected, sig)

# =========================================================
# URL VALIDATION
# =========================================================

def valid(url: str):
    host = urlparse(url).netloc.lower()
    allowed = {
        "youtube.com", "www.youtube.com",
        "youtu.be",
        "facebook.com", "www.facebook.com",
        "tiktok.com", "www.tiktok.com",
        "instagram.com", "www.instagram.com"
    }
    return host in allowed

# =========================================================
# PROXY ROTATION
# =========================================================

def get_proxy():
    if not PROXIES or PROXIES == [""]:
        return None
    return random.choice(PROXIES)

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
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/122 Safari/537.36"
            )
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
# CACHE (REDIS)
# =========================================================

def cache_get(key):
    return redis_client.get(key)

def cache_set(key, value):
    redis_client.setex(key, CACHE_TTL, value)

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
# STREAM PROXY CORE
# =========================================================

def stream_bytes(url):
    with requests.get(url, stream=True, timeout=20) as r:
        r.raise_for_status()
        for chunk in r.iter_content(chunk_size=1024 * 512):
            if chunk:
                yield chunk

# =========================================================
# STREAM ENDPOINT (NO DIRECT URL EXPOSURE)
# =========================================================

@app.get("/proxy/stream")
def proxy_stream(url: str, exp: str, sig: str):

    if not verify_signature(url, exp, sig):
        raise HTTPException(403, "invalid signature or expired")

    if not valid(url):
        raise HTTPException(400, "unsupported url")

    cache_key = f"stream:{url}"
    cached = cache_get(cache_key)

    if cached:
        data = eval(cached)
    else:
        data = asyncio.run(extract(url))

        if not data or "error" in data:
            raise HTTPException(502, "extraction failed")

        formats = data.get("formats", [])

        best = max(
            [f for f in formats if f.get("url") and f.get("vcodec") != "none"],
            key=lambda x: x.get("height") or 0,
            default=None
        )

        if not best:
            raise HTTPException(404, "no stream found")

        data = {
            "url": best["url"],
            "title": data.get("title")
        }

        cache_set(cache_key, str(data))

    return StreamingResponse(
        stream_bytes(data["url"]),
        media_type="video/mp4"
    )

# =========================================================
# SIGNED LINK GENERATOR
# =========================================================

@app.get("/sign")
def sign(url: str):

    if not valid(url):
        raise HTTPException(400, "invalid url")

    exp = str(int(time.time() + 3600))
    payload = f"{url}:{exp}"
    sig = sign_payload(payload)

    return {
        "proxy_url": f"/proxy/stream?url={url}&exp={exp}&sig={sig}"
    }

# =========================================================
# INFO ENDPOINT
# =========================================================

@app.get("/info")
async def info(url: str):

    if not valid(url):
        raise HTTPException(400, "invalid url")

    cache_key = f"info:{url}"
    cached = cache_get(cache_key)

    if cached:
        return eval(cached)

    data = await extract(url)

    if not data or "error" in data:
        raise HTTPException(502, "failed")

    result = {
        "title": data.get("title"),
        "duration": data.get("duration"),
        "thumbnail": data.get("thumbnail")
    }

    cache_set(cache_key, str(result))
    return result
