from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import yt_dlp
import traceback
import socket

# =========================
# APP SETUP
# =========================

socket.setdefaulttimeout(120)

app = FastAPI(title="Mobile Stable Media API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# SUPPORT CHECK
# =========================

SUPPORTED = [
    "youtube.com",
    "youtu.be",
    "facebook.com",
    "fb.watch",
    "instagram.com",
    "tiktok.com",
    "twitter.com",
    "x.com"
]

def is_supported(url: str):
    return any(x in url for x in SUPPORTED)

# =========================
# CLEAN URL
# =========================

def clean_url(url: str):
    url = url.strip()

    if "youtube.com/shorts/" in url:
        vid = url.split("/shorts/")[1].split("?")[0]
        return f"https://www.youtube.com/watch?v={vid}"

    if "&list=" in url:
        url = url.split("&list=")[0]

    return url

# =========================
# SAFE YT-DLP OPTIONS
# =========================

def ydl_opts():
    return {
        # SAFE FORMAT (prevents crashes)
        "format": "bv*+ba/best/best",

        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,

        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 60,

        # IMPORTANT: do NOT use ignoreerrors
        "ignoreerrors": False,

        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        }
    }

# =========================
# ERROR HANDLER
# =========================

def fail(msg):
    return JSONResponse({
        "status": "failed",
        "error": str(msg)
    })

# =========================
# STREAM PICKER (SAFE)
# =========================

def get_stream(data, audio=False):

    if not isinstance(data, dict):
        return None

    formats = data.get("formats")

    if not formats:
        return data.get("url")

    candidates = []

    for f in formats:
        if not isinstance(f, dict):
            continue

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

    return sorted(
        candidates,
        key=lambda x: (x.get("height") or 0, x.get("tbr") or 0),
        reverse=True
    )[0]["url"]

# =========================
# INFO ENDPOINT
# =========================

@app.get("/info")
def info(url: str):

    try:
        if not is_supported(url):
            return fail("Unsupported URL")

        url = clean_url(url)

        try:
            with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
                data = ydl.extract_info(url, download=False)
        except Exception:
            return fail("Extraction failed")

        if not data or not isinstance(data, dict):
            return fail("No data returned")

        return {
            "status": "success",
            "title": data.get("title"),
            "duration": data.get("duration"),
            "thumbnail": data.get("thumbnail"),
            "is_live": data.get("is_live")
        }

    except Exception as e:
        traceback.print_exc()
        return fail(e)

# =========================
# STREAM ENDPOINT
# =========================

@app.get("/stream")
def stream(url: str):

    try:
        if not is_supported(url):
            return fail("Unsupported URL")

        url = clean_url(url)

        try:
            with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
                data = ydl.extract_info(url, download=False)
        except Exception:
            return fail("Extraction failed")

        if not data or not isinstance(data, dict):
            return fail("No stream data")

        stream_url = get_stream(data, audio=False)

        if not stream_url:
            return fail("No stream found")

        return {
            "status": "success",
            "title": data.get("title"),
            "stream_url": stream_url,
            "is_live": data.get("is_live")
        }

    except Exception as e:
        traceback.print_exc()
        return fail(e)

# =========================
# AUDIO ENDPOINT (FIXED)
# =========================

@app.get("/audio")
def audio(url: str):

    try:
        if not is_supported(url):
            return fail("Unsupported URL")

        url = clean_url(url)

        try:
            with yt_dlp.YoutubeDL({
                **ydl_opts(),
                "format": "bestaudio/best"
            }) as ydl:
                data = ydl.extract_info(url, download=False)
        except Exception:
            return fail("Audio extraction failed")

        if not data or not isinstance(data, dict):
            return fail("No audio data")

        audio_url = get_stream(data, audio=True)

        if not audio_url:
            return fail("No audio found")

        return {
            "status": "success",
            "title": data.get("title"),
            "audio_url": audio_url
        }

    except Exception as e:
        traceback.print_exc()
        return fail(e)

# =========================
# HEALTH CHECK
# =========================

@app.get("/health")
def health():
    return {
        "status": "ok"
    }
