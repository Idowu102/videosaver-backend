from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import yt_dlp
import os
import uuid
import shutil
import socket
import traceback

# =========================================================
# SOCKET
# =========================================================

socket.setdefaulttimeout(120)

# =========================================================
# APP
# =========================================================

app = FastAPI(
    title="Ultimate Downloader API",
    version="2026.1"
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
# STORAGE
# =========================================================

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# =========================================================
# SUPPORTED DOMAINS
# =========================================================

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

def supported(url: str):
    return any(x in url for x in SUPPORTED)

# =========================================================
# CLEAN URL
# =========================================================

def clean_url(url: str):
    url = url.strip()

    url = url.replace("m.youtube.com", "www.youtube.com")

    if "&list=" in url:
        url = url.split("&list=")[0]

    if "&pp=" in url:
        url = url.split("&pp=")[0]

    if "youtube.com/shorts/" in url:
        vid = url.split("/shorts/")[1].split("?")[0]
        url = f"https://www.youtube.com/watch?v={vid}"

    return url

# =========================================================
# yt-dlp OPTIONS (FIXED)
# =========================================================

def ydl_opts(outtmpl=None, audio=False):

    # ✅ FIXED FORMAT SELECTION (IMPORTANT)
    if audio:
        fmt = "bestaudio/best"
    else:
        fmt = "bv*+ba/best"

    opts = {
        "format": fmt,

        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "ignoreerrors": False,

        "geo_bypass": True,
        "retries": 10,
        "fragment_retries": 10,
        "socket_timeout": 120,

        "extract_flat": False,

        # safer than forcing mp4
        "merge_output_format": "mkv",

        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },

        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web", "ios"]
            }
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

# =========================================================
# ERROR RESPONSE
# =========================================================

def failed(error):
    return JSONResponse({
        "status": "failed",
        "error": str(error)
    })

# =========================================================
# STREAM PICKER (IMPROVED)
# =========================================================

def get_stream(data, audio=False):

    formats = data.get("formats", [])
    if not formats:
        return None

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

    best = sorted(candidates, key=score, reverse=True)[0]
    return best["url"]

# =========================================================
# HOME
# =========================================================

@app.get("/")
def home():
    return {
        "status": "running",
        "engine": "stable-youtube-engine",
        "features": [
            "youtube",
            "facebook",
            "instagram",
            "tiktok",
            "twitter",
            "shorts support",
            "audio download",
            "video download",
            "stream extraction",
            "cookies support"
        ]
    }

# =========================================================
# INFO
# =========================================================

@app.get("/info")
def info(url: str):
    try:
        if not supported(url):
            return failed("Unsupported URL")

        url = clean_url(url)

        with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
            data = ydl.extract_info(url, download=False)

        return {
            "status": "success",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "duration": data.get("duration"),
            "uploader": data.get("uploader"),
            "view_count": data.get("view_count")
        }

    except Exception as e:
        traceback.print_exc()
        return failed(e)

# =========================================================
# STREAM
# =========================================================

@app.get("/stream")
def stream(url: str):
    try:
        if not supported(url):
            return failed("Unsupported URL")

        url = clean_url(url)

        with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
            data = ydl.extract_info(url, download=False)

        stream_url = get_stream(data, audio=False)

        if not stream_url:
            return failed("No stream found")

        return {
            "status": "success",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "duration": data.get("duration"),
            "stream_url": stream_url
        }

    except Exception as e:
        traceback.print_exc()
        return failed(e)

# =========================================================
# AUDIO STREAM
# =========================================================

@app.get("/audio-stream")
def audio_stream(url: str):
    try:
        if not supported(url):
            return failed("Unsupported URL")

        url = clean_url(url)

        with yt_dlp.YoutubeDL(ydl_opts(audio=True)) as ydl:
            data = ydl.extract_info(url, download=False)

        audio_url = get_stream(data, audio=True)

        if not audio_url:
            return failed("No audio found")

        return {
            "status": "success",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "audio_url": audio_url
        }

    except Exception as e:
        traceback.print_exc()
        return failed(e)

# =========================================================
# DOWNLOAD VIDEO
# =========================================================

@app.get("/download")
def download(url: str):
    try:
        if not supported(url):
            return failed("Unsupported URL")

        url = clean_url(url)

        uid = str(uuid.uuid4())
        output = os.path.join(DOWNLOAD_DIR, f"{uid}.%(ext)s")

        with yt_dlp.YoutubeDL(ydl_opts(output)) as ydl:
            data = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(data)

        if os.path.exists(filename):
            return FileResponse(
                path=filename,
                media_type="video/mp4",
                filename=os.path.basename(filename)
            )

        return failed("Downloaded file missing")

    except Exception as e:
        traceback.print_exc()
        return failed(e)

# =========================================================
# AUDIO DOWNLOAD
# =========================================================

@app.get("/audio")
def audio(url: str):
    try:
        if not supported(url):
            return failed("Unsupported URL")

        url = clean_url(url)

        uid = str(uuid.uuid4())
        output = os.path.join(DOWNLOAD_DIR, f"{uid}.%(ext)s")

        opts = ydl_opts(output, audio=True)

        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]

        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(data)

        mp3 = filename.rsplit(".", 1)[0] + ".mp3"

        if not os.path.exists(mp3):
            return failed("MP3 conversion failed")

        return FileResponse(
            path=mp3,
            media_type="audio/mpeg",
            filename=os.path.basename(mp3)
        )

    except Exception as e:
        traceback.print_exc()
        return failed(e)

# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():
    return {"status": "healthy"}

# =========================================================
# STARTUP
# =========================================================

print("===================================")
print("Ultimate Downloader API Started")
print("===================================")
