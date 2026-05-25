from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import yt_dlp
import os
import uuid
import shutil
import socket
import re

socket.setdefaulttimeout(120)

app = FastAPI(title="Stable YouTube API", version="1.0")

# ================= CORS =================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= STORAGE =================
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ================= SUPPORT CHECK =================
def is_youtube(url: str):
    return "youtube.com" in url or "youtu.be" in url

# ================= CLEAN URL =================
def clean_url(url: str):
    url = url.strip()
    url = url.replace("m.youtube.com", "www.youtube.com")

    if "&list=" in url:
        url = url.split("&list=")[0]

    if "&pp=" in url:
        url = url.split("&pp=")[0]

    if "youtube.com/shorts/" in url:
        vid = url.split("/shorts/")[1].split("?")[0]
        return f"https://www.youtube.com/watch?v={vid}"

    return url

# ================= OPTIONS =================
def ydl_opts(outtmpl=None, audio=False):

    fmt = "bestaudio/best" if audio else "best[ext=mp4]/best"

    opts = {
        "format": fmt,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "retries": 10,
        "fragment_retries": 10,
        "socket_timeout": 120,
        "http_headers": {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
        },
        "extractor_args": {
            "youtube": {
                "player_client": ["web"]
            }
        }
    }

    if outtmpl:
        opts["outtmpl"] = outtmpl

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        opts["ffmpeg_location"] = ffmpeg

    return opts

# ================= HOME =================
@app.get("/")
def home():
    return {
        "status": "running",
        "engine": "stable-youtube-api",
        "endpoints": [
            "/info",
            "/stream",
            "/download",
            "/audio"
        ]
    }

# ================= INFO =================
@app.get("/info")
def info(url: str):

    if not is_youtube(url):
        return {"status": "error", "message": "Only YouTube supported"}

    url = clean_url(url)

    try:
        with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
            data = ydl.extract_info(url, download=False)

        return {
            "status": "success",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "duration": data.get("duration"),
            "uploader": data.get("uploader"),
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

# ================= STREAM =================
@app.get("/stream")
def stream(url: str):

    if not is_youtube(url):
        return {"status": "error", "message": "Only YouTube supported"}

    url = clean_url(url)

    try:
        with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
            data = ydl.extract_info(url, download=False)

        stream_url = data.get("url")

        if not stream_url:
            for f in reversed(data.get("formats", [])):
                if f.get("url"):
                    stream_url = f["url"]
                    break

        return {
            "status": "success",
            "title": data.get("title"),
            "stream_url": stream_url
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

# ================= DOWNLOAD VIDEO =================
@app.get("/download")
def download(url: str):

    if not is_youtube(url):
        return {"status": "error", "message": "Only YouTube supported"}

    url = clean_url(url)

    file_id = str(uuid.uuid4())
    out = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")

    try:
        with yt_dlp.YoutubeDL(ydl_opts(out)) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        mp4 = filename.rsplit(".", 1)[0] + ".mp4"

        if os.path.exists(mp4):
            filename = mp4

        return FileResponse(filename, media_type="video/mp4")

    except Exception as e:
        return {"status": "error", "message": str(e)}

# ================= AUDIO =================
@app.get("/audio")
def audio(url: str):

    if not is_youtube(url):
        return {"status": "error", "message": "Only YouTube supported"}

    url = clean_url(url)

    file_id = str(uuid.uuid4())
    out = os.path.join(DOWNLOAD_DIR, f"{file_id}.%(ext)s")

    try:
        opts = ydl_opts(out, audio=True)

        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        mp3 = filename.rsplit(".", 1)[0] + ".mp3"

        if not os.path.exists(mp3):
            return {"status": "error", "message": "MP3 conversion failed"}

        return FileResponse(mp3, media_type="audio/mpeg")

    except Exception as e:
        return {"status": "error", "message": str(e)}
