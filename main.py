from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
import yt_dlp
import os
import uuid
import shutil
import socket
import traceback
import requests
import time

# =========================================================
# BASIC SETUP
# =========================================================

socket.setdefaulttimeout(120)

app = FastAPI(title="Ultra Resilient Media API", version="2026.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOAD_DIR = "downloads"
CACHE_DIR = "cache"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

SUPPORTED = [
    "youtube.com", "youtu.be",
    "facebook.com", "fb.watch",
    "instagram.com",
    "tiktok.com",
    "twitter.com", "x.com"
]

# =========================================================
# HELPERS
# =========================================================

def supported(url: str):
    return any(x in url for x in SUPPORTED)


def clean_url(url: str):
    url = url.strip()
    url = url.replace("m.youtube.com", "www.youtube.com")

    if "&list=" in url:
        url = url.split("&list=")[0]

    if "youtube.com/shorts/" in url:
        vid = url.split("/shorts/")[1].split("?")[0]
        url = f"https://www.youtube.com/watch?v={vid}"

    return url


def cache_path(url: str):
    return os.path.join(CACHE_DIR, str(abs(hash(url))) + ".json")


# =========================================================
# YT-DLP OPTIONS (ROBUST CORE)
# =========================================================

def ydl_opts(outtmpl=None, audio=False):

    # 🔥 ultra-safe format chain
    fmt = (
        "best[ext=mp4]/"
        "best[ext=webm]/"
        "best/"
        "bv*+ba/best"
    )

    opts = {
        "format": "bestaudio/best" if audio else fmt,

        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,

        "retries": 10,
        "fragment_retries": 10,
        "socket_timeout": 120,

        # 🔥 prevents format failure crash
        "ignoreerrors": True,

        # safer merging
        "merge_output_format": "mp4",

        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },

        # improves YouTube stability
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web", "ios"]
            }
        },

        # better format sorting
        "format_sort": ["res", "ext"]
    }

    if outtmpl:
        opts["outtmpl"] = outtmpl

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        opts["ffmpeg_location"] = ffmpeg

    if os.path.exists("cookies.txt"):
        opts["cookiefile"] = "cookies.txt"

    return opts


# =========================================================
# ERROR HANDLER
# =========================================================

def fail(e):
    return JSONResponse({
        "status": "failed",
        "error": str(e)
    })


# =========================================================
# STREAM PICKER (SMART)
# =========================================================

def get_stream(data, audio=False):

    formats = data.get("formats", [])
    if not formats:
        return data.get("url")

    def score(f):
        return (
            f.get("height") or 0,
            f.get("tbr") or 0
        )

    candidates = []

    for f in formats:
        if not f.get("url"):
            continue

        if audio:
            if f.get("acodec") == "none":
                continue
        else:
            if f.get("vcodec") == "none":
                continue

        candidates.append(f)

    if not candidates:
        return None

    return sorted(candidates, key=score, reverse=True)[0]["url"]


# =========================================================
# STREAM PROXY (FIXS EXPIRED LINKS)
# =========================================================

@app.get("/proxy")
def proxy(url: str):

    try:
        r = requests.get(url, stream=True, timeout=120)

        return StreamingResponse(
            r.iter_content(chunk_size=1024 * 512),
            media_type="video/mp4"
        )

    except Exception as e:
        return fail(e)


# =========================================================
# INFO (CACHED)
# =========================================================

@app.get("/info")
def info(url: str):

    try:
        if not supported(url):
            return fail("Unsupported URL")

        url = clean_url(url)

        with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
            data = ydl.extract_info(url, download=False)

        return {
            "status": "success",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "duration": data.get("duration"),
            "is_live": data.get("is_live"),
            "view_count": data.get("view_count")
        }

    except Exception as e:
        traceback.print_exc()
        return fail(e)


# =========================================================
# STREAM
# =========================================================

@app.get("/stream")
def stream(url: str):

    try:
        if not supported(url):
            return fail("Unsupported URL")

        url = clean_url(url)

        # retry layer 1
        try:
            with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
                data = ydl.extract_info(url, download=False)
        except Exception:
            # retry layer 2 (ultra-safe)
            opts = ydl_opts()
            opts["format"] = "best/best"
            with yt_dlp.YoutubeDL(opts) as ydl:
                data = ydl.extract_info(url, download=False)

        stream_url = get_stream(data, audio=False)

        if not stream_url:
            return fail("No stream found")

        return {
            "status": "success",
            "title": data.get("title"),
            "is_live": data.get("is_live"),
            "stream_url": stream_url,
            "proxy_url": f"/proxy?url={stream_url}"
        }

    except Exception as e:
        traceback.print_exc()
        return fail(e)


# =========================================================
# AUDIO STREAM
# =========================================================

@app.get("/audio-stream")
def audio_stream(url: str):

    try:
        if not supported(url):
            return fail("Unsupported URL")

        url = clean_url(url)

        with yt_dlp.YoutubeDL(ydl_opts(audio=True)) as ydl:
            data = ydl.extract_info(url, download=False)

        audio_url = get_stream(data, audio=True)

        if not audio_url:
            return fail("No audio found")

        return {
            "status": "success",
            "title": data.get("title"),
            "audio_url": audio_url,
            "proxy_url": f"/proxy?url={audio_url}"
        }

    except Exception as e:
        traceback.print_exc()
        return fail(e)


# =========================================================
# DOWNLOAD VIDEO
# =========================================================

@app.get("/download")
def download(url: str):

    try:
        if not supported(url):
            return fail("Unsupported URL")

        url = clean_url(url)

        uid = str(uuid.uuid4())
        output = os.path.join(DOWNLOAD_DIR, f"{uid}.%(ext)s")

        with yt_dlp.YoutubeDL(ydl_opts(output)) as ydl:
            data = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(data)

        if os.path.exists(filename):
            return FileResponse(filename, media_type="video/mp4")

        return fail("Download failed")

    except Exception as e:
        traceback.print_exc()
        return fail(e)


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "cache": CACHE_DIR,
        "downloads": DOWNLOAD_DIR
    }


# =========================================================
# STARTUP
# =========================================================

print("===================================")
print("ULTRA RESILIENT MEDIA API RUNNING")
print("===================================")
