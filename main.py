from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
import yt_dlp
import socket
import re
import os
import time
import hashlib
from urllib.parse import urlparse, parse_qs

# =========================================================
# SOCKET TIMEOUT
# =========================================================

socket.setdefaulttimeout(120)

# =========================================================
# APP
# =========================================================

app = FastAPI(
    title="Production YouTube Backend",
    version="3.0.0"
)

# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# SIMPLE MEMORY CACHE
# =========================================================

CACHE = {}
CACHE_TTL = 300  # 5 mins


def cache_key(url, audio=False):
    raw = f"{url}:{audio}"
    return hashlib.md5(raw.encode()).hexdigest()


def get_cache(url, audio=False):
    key = cache_key(url, audio)

    if key not in CACHE:
        return None

    item = CACHE[key]

    if time.time() > item["expires"]:
        del CACHE[key]
        return None

    return item["data"]


def set_cache(url, data, audio=False):
    key = cache_key(url, audio)

    CACHE[key] = {
        "data": data,
        "expires": time.time() + CACHE_TTL
    }


# =========================================================
# HOME
# =========================================================

@app.get("/")
def home():
    return {
        "status": "running",
        "engine": "Production Hybrid Engine",
        "version": "3.0.0",
        "features": [
            "youtube extraction",
            "audio extraction",
            "stream support",
            "cache system",
            "shorts support",
            "mobile youtube support",
            "fallback clients",
            "cookies support",
            "retry engine",
            "format fallback"
        ]
    }


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


# =========================================================
# URL NORMALIZER
# =========================================================

def clean_url(url: str):

    url = url.strip()

    # mobile youtube -> desktop
    url = url.replace("m.youtube.com", "www.youtube.com")

    # remove playlist
    if "&list=" in url:
        url = url.split("&list=")[0]

    # remove pp param
    if "&pp=" in url:
        url = url.split("&pp=")[0]

    # shorts support
    if "youtube.com/shorts/" in url:

        video_id = url.split("/shorts/")[1].split("?")[0]

        url = f"https://www.youtube.com/watch?v={video_id}"

    return url


# =========================================================
# VIDEO ID
# =========================================================

def get_video_id(url):

    patterns = [
        r"v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"shorts/([a-zA-Z0-9_-]{11})",
    ]

    for pattern in patterns:

        match = re.search(pattern, url)

        if match:
            return match.group(1)

    return None


# =========================================================
# THUMBNAIL FALLBACK
# =========================================================

def thumbnail_fallback(video_id):

    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


# =========================================================
# YT-DLP OPTIONS
# =========================================================

def yt_opts(fmt="best", audio=False):

    opts = {

        # logging
        "quiet": True,
        "no_warnings": True,

        # retries
        "retries": 10,
        "fragment_retries": 10,

        # timeout
        "socket_timeout": 120,

        # youtube
        "noplaylist": True,
        "extract_flat": False,
        "geo_bypass": True,

        # IMPORTANT
        "ignoreerrors": False,

        # SSL
        "nocheckcertificate": True,

        # format
        "format": fmt,

        # cookies support
        "cookiefile": "cookies.txt"
        if os.path.exists("cookies.txt")
        else None,

        # headers
        "http_headers": {

            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 11; SM-G991B) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/120.0 Mobile Safari/537.36"
            ),

            "Accept-Language":
                "en-US,en;q=0.9",
        },

        # extractor strategy
        "extractor_args": {

            "youtube": {

                # IMPORTANT
                "player_client": [
                    "android",
                    "web",
                    "ios",
                    "tv_embedded"
                ]
            }
        }
    }

    return opts


# =========================================================
# FORMAT SELECTOR
# =========================================================

def get_format_priority(audio=False):

    if audio:

        return [

            # best audio m4a
            "bestaudio[ext=m4a]",

            # any audio
            "bestaudio",

            # fallback
            "best"
        ]

    return [

        # merged best mp4
        "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",

        # progressive mp4
        "best[ext=mp4]",

        # fallback
        "best"
    ]


# =========================================================
# EXTRACT URL FROM FORMATS
# =========================================================

def extract_stream_url(info, audio=False):

    # direct
    if info.get("url"):
        return info["url"]

    formats = info.get("formats", [])

    if not formats:
        return None

    # reverse = best first
    for f in reversed(formats):

        if not f.get("url"):
            continue

        # audio filtering
        if audio and f.get("acodec") == "none":
            continue

        return f["url"]

    return None


# =========================================================
# MAIN EXTRACTION ENGINE
# =========================================================

def safe_extract(url, audio=False):

    url = clean_url(url)

    # =====================================================
    # CACHE
    # =====================================================

    cached = get_cache(url, audio)

    if cached:
        return cached

    formats = get_format_priority(audio)

    last_error = None

    for fmt in formats:

        try:

            opts = yt_opts(fmt, audio)

            with yt_dlp.YoutubeDL(opts) as ydl:

                info = ydl.extract_info(url, download=False)

            if not info:
                continue

            stream_url = extract_stream_url(info, audio)

            if not stream_url:
                continue

            data = {

                "title":
                    info.get("title", "YouTube Video"),

                "thumbnail":
                    info.get("thumbnail")
                    or thumbnail_fallback(
                        get_video_id(url)
                    ),

                "duration":
                    info.get("duration", 0),

                "stream_url":
                    stream_url,

                "webpage_url":
                    info.get("webpage_url", url),

                "uploader":
                    info.get("uploader"),

                "view_count":
                    info.get("view_count"),

                "like_count":
                    info.get("like_count"),

                "ext":
                    info.get("ext"),

                "format":
                    fmt
            }

            set_cache(url, data, audio)

            return data

        except Exception as e:

            last_error = str(e)

            continue

    raise HTTPException(
        status_code=500,
        detail=f"Extraction failed: {last_error}"
    )


# =========================================================
# EXTRACT
# =========================================================

@app.get("/extract")
def extract(url: str):

    data = safe_extract(url)

    return {
        "status": "success",
        **data
    }


# =========================================================
# STREAM
# =========================================================

@app.get("/stream")
def stream(url: str):

    data = safe_extract(url)

    return {
        "status": "success",
        **data
    }


# =========================================================
# AUDIO
# =========================================================

@app.get("/audio")
def audio(url: str):

    data = safe_extract(url, audio=True)

    return {
        "status": "success",
        **data
    }


# =========================================================
# REDIRECT STREAM
# =========================================================

@app.get("/redirect")
def redirect(url: str):

    data = safe_extract(url)

    return RedirectResponse(
        url=data["stream_url"]
    )


# =========================================================
# AUDIO REDIRECT
# =========================================================

@app.get("/audio-redirect")
def audio_redirect(url: str):

    data = safe_extract(url, audio=True)

    return RedirectResponse(
        url=data["stream_url"]
    )


# =========================================================
# VIDEO INFO ONLY
# =========================================================

@app.get("/info")
def info(url: str):

    url = clean_url(url)

    opts = yt_opts("best")

    try:

        with yt_dlp.YoutubeDL(opts) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

        return {

            "status": "success",

            "title":
                info.get("title"),

            "thumbnail":
                info.get("thumbnail"),

            "duration":
                info.get("duration"),

            "uploader":
                info.get("uploader"),

            "view_count":
                info.get("view_count"),

            "like_count":
                info.get("like_count"),

            "webpage_url":
                info.get("webpage_url"),
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# =========================================================
# CLEAR CACHE
# =========================================================

@app.get("/clear-cache")
def clear_cache():

    CACHE.clear()

    return {
        "status": "success",
        "message": "cache cleared"
    }


# =========================================================
# STARTUP MESSAGE
# =========================================================

print("===================================")
print("Production YouTube Backend Started")
print("===================================")
