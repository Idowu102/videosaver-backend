from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import yt_dlp
import traceback
import os

app = FastAPI(title="Robust Media API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# OPTIONAL COOKIES SUPPORT
# =========================

COOKIES_FILE = "cookies.txt"
USE_COOKIES = os.path.exists(COOKIES_FILE)

SUPPORTED = [
    "youtube.com",
    "youtu.be",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
]

def supported(url: str):
    return any(x in url for x in SUPPORTED)

# =========================
# CLEAN URL
# =========================

def clean_url(url: str):
    url = url.strip()

    if "youtube.com/shorts/" in url:
        vid = url.split("/shorts/")[1].split("?")[0]
        return f"https://www.youtube.com/watch?v={vid}"

    return url

# =========================
# SAFE YT-DLP OPTIONS
# =========================

def ydl_opts(audio=False):
    opts = {
        "format": "bv*+ba/best/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
        "ignoreerrors": False,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        }
    }

    if audio:
        opts["format"] = "bestaudio/best"

    if USE_COOKIES:
        opts["cookiefile"] = COOKIES_FILE

    return opts

# =========================
# ERROR RESPONSE
# =========================

def fail(msg):
    return JSONResponse({
        "status": "failed",
        "error": str(msg)
    })

# =========================
# SAFE EXTRACT (WITH FALLBACK)
# =========================

def extract(url: str, audio=False):

    try:
        with yt_dlp.YoutubeDL(ydl_opts(audio=audio)) as ydl:
            data = ydl.extract_info(url, download=False)

        if isinstance(data, dict):
            return data

        return None

    except Exception:
        # 🔥 fallback mode (weaker but more compatible)
        try:
            with yt_dlp.YoutubeDL({
                "format": "worst/best",
                "quiet": True,
                "noplaylist": True
            }) as ydl:
                data = ydl.extract_info(url, download=False)

            return data if isinstance(data, dict) else None

        except Exception:
            return None

# =========================
# STREAM PICKER
# =========================

def get_stream(data, audio=False):

    if not isinstance(data, dict):
        return None

    formats = data.get("formats")

    if not formats:
        return data.get("url")

    best = None

    for f in formats:
        if not isinstance(f, dict):
            continue

        if not f.get("url"):
            continue

        if audio and f.get("acodec") == "none":
            continue
        if not audio and f.get("vcodec") == "none":
            continue

        best = f

    return best["url"] if best else data.get("url")

# =========================
# INFO
# =========================

@app.get("/info")
def info(url: str):

    try:
        if not supported(url):
            return fail("unsupported url")

        url = clean_url(url)
        data = extract(url)

        if not data:
            return fail("yt-dlp failed (blocked or unavailable)")

        return {
            "status": "success",
            "title": data.get("title"),
            "duration": data.get("duration"),
            "thumbnail": data.get("thumbnail"),
            "uploader": data.get("uploader"),
        }

    except Exception as e:
        traceback.print_exc()
        return fail(e)

# =========================
# STREAM
# =========================

@app.get("/stream")
def stream(url: str):

    try:
        if not supported(url):
            return fail("unsupported url")

        url = clean_url(url)
        data = extract(url)

        if not data:
            return fail("blocked_or_failed_extraction")

        stream_url = get_stream(data, audio=False)

        if not stream_url:
            return fail("no_stream_found")

        return {
            "status": "success",
            "title": data.get("title"),
            "stream_url": stream_url
        }

    except Exception as e:
        traceback.print_exc()
        return fail(e)

# =========================
# AUDIO
# =========================

@app.get("/audio")
def audio(url: str):

    try:
        if not supported(url):
            return fail("unsupported url")

        url = clean_url(url)
        data = extract(url, audio=True)

        if not data:
            return fail("blocked_or_failed_extraction")

        audio_url = get_stream(data, audio=True)

        if not audio_url:
            return fail("no_audio_found")

        return {
            "status": "success",
            "title": data.get("title"),
            "audio_url": audio_url
        }

    except Exception as e:
        traceback.print_exc()
        return fail(e)

# =========================
# HEALTH
# =========================

@app.get("/health")
def health():
    return {"status": "ok"}
