from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import yt_dlp
import os
import uuid
import shutil
import socket
import traceback

socket.setdefaulttimeout(120)

app = FastAPI(title="Ultimate Stable Downloader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

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

# =========================
# SAFE CHECK
# =========================

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
# OPTIONS
# =========================

def ydl_opts(audio=False, outtmpl=None):

    fmt = "bestaudio/best" if audio else (
        "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best"
    )

    opts = {
        "format": fmt,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 60,
        "ignoreerrors": False,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        },
        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        }
    }

    if outtmpl:
        opts["outtmpl"] = outtmpl

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        opts["ffmpeg_location"] = ffmpeg

    if os.path.exists("cookies.txt"):
        opts["cookiefile"] = "cookies.txt"

    return opts

# =========================
# SAFE ERROR
# =========================

def fail(msg):
    return JSONResponse({
        "status": "failed",
        "error": str(msg)
    })

# =========================
# SAFE EXTRACT (CRASH PROOF)
# =========================

def extract(url, audio=False):
    try:
        with yt_dlp.YoutubeDL(ydl_opts(audio=audio)) as ydl:
            data = ydl.extract_info(url, download=False)

        if not isinstance(data, dict):
            return None

        return data

    except Exception as e:
        return {"error": str(e)}

# =========================
# STREAM PICKER (FIXED)
# =========================

def get_stream(data, audio=False):

    if not isinstance(data, dict):
        return None

    if data.get("url"):
        return data["url"]

    formats = data.get("formats") or []

    for f in reversed(formats):
        try:
            if not f.get("url"):
                continue

            if audio and f.get("acodec") == "none":
                continue

            return f["url"]

        except:
            continue

    return None

# =========================
# HOME
# =========================

@app.get("/")
def home():
    return {
        "status": "running",
        "engine": "stable-youtube-engine"
    }

# =========================
# INFO
# =========================

@app.get("/info")
def info(url: str):
    try:
        if not supported(url):
            return fail("unsupported url")

        data = extract(clean_url(url))

        if not data or "error" in data:
            return fail(data)

        return {
            "status": "success",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "duration": data.get("duration"),
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

        data = extract(clean_url(url))

        if not data or "error" in data:
            return fail("youtube blocked or failed extraction")

        stream_url = get_stream(data)

        if not stream_url:
            return fail("no stream found")

        return {
            "status": "success",
            "title": data.get("title"),
            "stream_url": stream_url
        }

    except Exception as e:
        traceback.print_exc()
        return fail(e)

# =========================
# AUDIO STREAM
# =========================

@app.get("/audio-stream")
def audio_stream(url: str):
    try:
        if not supported(url):
            return fail("unsupported url")

        data = extract(clean_url(url), audio=True)

        if not data or "error" in data:
            return fail("audio extraction failed")

        audio_url = get_stream(data, audio=True)

        if not audio_url:
            return fail("no audio found")

        return {
            "status": "success",
            "title": data.get("title"),
            "audio_url": audio_url
        }

    except Exception as e:
        traceback.print_exc()
        return fail(e)

# =========================
# DOWNLOAD VIDEO
# =========================

@app.get("/download")
def download(url: str):
    try:
        if not supported(url):
            return fail("unsupported url")

        uid = str(uuid.uuid4())
        out = os.path.join(DOWNLOAD_DIR, f"{uid}.%(ext)s")

        with yt_dlp.YoutubeDL(ydl_opts(outtmpl=out)) as ydl:
            data = ydl.extract_info(clean_url(url), download=True)
            filename = ydl.prepare_filename(data)

        if not os.path.exists(filename):
            return fail("file missing")

        return FileResponse(filename, media_type="video/mp4")

    except Exception as e:
        traceback.print_exc()
        return fail(e)

# =========================
# DOWNLOAD AUDIO
# =========================

@app.get("/audio")
def audio(url: str):
    try:
        if not supported(url):
            return fail("unsupported url")

        uid = str(uuid.uuid4())
        out = os.path.join(DOWNLOAD_DIR, f"{uid}.%(ext)s")

        opts = ydl_opts(outtmpl=out, audio=True)

        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]

        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info(clean_url(url), download=True)
            filename = ydl.prepare_filename(data)

        mp3 = filename.rsplit(".", 1)[0] + ".mp3"

        if not os.path.exists(mp3):
            return fail("mp3 conversion failed")

        return FileResponse(mp3, media_type="audio/mpeg")

    except Exception as e:
        traceback.print_exc()
        return fail(e)

# =========================
# HEALTH
# =========================

@app.get("/health")
def health():
    return {"status": "ok"}
