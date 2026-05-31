import os
import asyncio
import yt_dlp
import requests

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

app = FastAPI(title="Stable Single Endpoint CDN")

executor = ThreadPoolExecutor(max_workers=10)

# -------------------------
# URL VALIDATION
# -------------------------
def valid(url: str):
    host = urlparse(url).netloc.lower()
    allowed = [
        "youtube.com", "www.youtube.com", "youtu.be",
        "facebook.com", "www.facebook.com",
        "tiktok.com", "www.tiktok.com",
        "instagram.com", "www.instagram.com"
    ]
    return any(x in host for x in allowed)

# -------------------------
# YT-DLP OPTIONS
# -------------------------
def ydl_opts():
    return {
        "quiet": True,
        "noplaylist": True,
        "retries": 3,
        "socket_timeout": 20,
        "cachedir": False,
        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        }
    }

# -------------------------
# EXTRACTOR
# -------------------------
def extract_sync(url):
    with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
        return ydl.extract_info(url, download=False)

async def extract(url):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, extract_sync, url)

# -------------------------
# BEST STREAM SELECTOR
# -------------------------
def best_stream(data):
    formats = data.get("formats", [])
    streams = [f for f in formats if f.get("url") and f.get("vcodec") != "none"]

    if not streams:
        return None

    return max(streams, key=lambda x: x.get("height") or 0)

# -------------------------
# STREAM PROXY
# -------------------------
def stream_generator(url):
    with requests.get(url, stream=True, timeout=20) as r:
        r.raise_for_status()
        for chunk in r.iter_content(chunk_size=1024 * 512):
            if chunk:
                yield chunk

# =========================================================
# SINGLE ENDPOINT (ONLY ONE YOU USE)
# =========================================================
@app.get("/api/play")
async def play(url: str, request: Request):

    if not valid(url):
        raise HTTPException(400, "Unsupported URL")

    data = await extract(url)

    if "error" in data:
        raise HTTPException(502, "Extraction failed")

    stream = best_stream(data)

    if not stream:
        raise HTTPException(404, "No stream found")

    stream_url = stream["url"]

    return StreamingResponse(
        stream_generator(stream_url),
        media_type="video/mp4"
    )
