from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import yt_dlp
import os
import uuid
import shutil
import socket
import traceback

socket.setdefaulttimeout(120)

app = FastAPI(title="Ultimate Downloader API", version="2026.1")

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
    "facebook.com",
    "fb.watch",
    "instagram.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "reddit.com",
    "pinterest.com",
    "linkedin.com",
    "snapchat.com",
    "threads.net",
    "tumblr.com",
    "vimeo.com",
    "dailymotion.com",
    "whatsapp.com",
    "chat.whatsapp.com"
]


def supported(url: str):
    return any(x in url for x in SUPPORTED)


def clean_url(url: str):
    return url.strip()


def ydl_opts(outtmpl=None, audio=False):

    fmt = "bestaudio/best" if audio else (
        "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
    )

    opts = {
        "format": fmt,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "merge_output_format": "mp4",
        "socket_timeout": 120,
        "retries": 10,
        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        }
    }

    if outtmpl:
        opts["outtmpl"] = outtmpl

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        opts["ffmpeg_location"] = ffmpeg

    return opts


def failed(msg):
    return JSONResponse({"status": "failed", "error": str(msg)})


# =========================================================
# HOME
# =========================================================

@app.get("/")
def home():
    return {"status": "running"}


# =========================================================
# STREAM (WITH QUALITY FIX 🔥)
# =========================================================

@app.get("/stream")
def stream(url: str):

    try:
        if not supported(url):
            return failed("Unsupported URL")

        url = clean_url(url)

        with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
            data = ydl.extract_info(url, download=False)

        formats = data.get("formats", [])

        qualities = {}

        for f in formats:
            if f.get("vcodec") == "none":
                continue

            height = f.get("height")
            if height and f.get("url"):
                qualities[f"{height}p"] = f["url"]

        return {
            "status": "success",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "qualities": qualities
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
        url = clean_url(url)

        with yt_dlp.YoutubeDL(ydl_opts(audio=True)) as ydl:
            data = ydl.extract_info(url, download=False)

        return {
            "status": "success",
            "title": data.get("title"),
            "audio_url": data.get("url")
        }

    except Exception as e:
        return failed(e)


# =========================================================
# INFO
# =========================================================

@app.get("/info")
def info(url: str):

    try:
        url = clean_url(url)

        with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
            data = ydl.extract_info(url, download=False)

        return {
            "status": "success",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "duration": data.get("duration")
        }

    except Exception as e:
        return failed(e)


# =========================================================
# DOWNLOAD VIDEO
# =========================================================

@app.get("/download")
def download(url: str):

    try:
        url = clean_url(url)

        uid = str(uuid.uuid4())
        out = os.path.join(DOWNLOAD_DIR, f"{uid}.%(ext)s")

        with yt_dlp.YoutubeDL(ydl_opts(out)) as ydl:
            data = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(data)

        if os.path.exists(filename):
            return FileResponse(filename, media_type="video/mp4")

        return failed("File not found")

    except Exception as e:
        return failed(e)


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():
    return {"status": "ok"}
