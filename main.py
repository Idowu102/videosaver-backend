from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
import yt_dlp
import os
import uuid
import shutil
import socket
import re

# =========================================================
# SOCKET TIMEOUT
# =========================================================

socket.setdefaulttimeout(120)

# =========================================================
# APP
# =========================================================

app = FastAPI(
    title="YouTube Downloader API",
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
# DOWNLOAD DIRECTORY
# =========================================================

DOWNLOAD_DIR = "downloads"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# =========================================================
# HOME
# =========================================================

@app.get("/")
def home():

    return {

        "status": "running",

        "engine":
            "Production YouTube Engine",

        "features": [

            "video download",
            "audio download",
            "stream extraction",
            "youtube shorts support",
            "mobile youtube support",
            "ffmpeg merge",
            "audio mp3 conversion",
            "stable extraction"
        ]
    }

# =========================================================
# URL CLEANER
# =========================================================

def clean_url(url: str):

    url = url.strip()

    # mobile -> desktop
    url = url.replace(
        "m.youtube.com",
        "www.youtube.com"
    )

    # remove playlist
    if "&list=" in url:
        url = url.split("&list=")[0]

    # remove pp
    if "&pp=" in url:
        url = url.split("&pp=")[0]

    # shorts support
    if "youtube.com/shorts/" in url:

        video_id = url.split(
            "/shorts/"
        )[1].split("?")[0]

        url = (
            "https://www.youtube.com/watch?v="
            f"{video_id}"
        )

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
# YT-DLP OPTIONS
# =========================================================

def yt_opts(output_path=None, audio=False):

    # IMPORTANT FIX
    # DO NOT USE ANDROID/IOS CLIENTS
    # THEY REQUIRE PO TOKENS NOW

    if audio:

        fmt = (
            "best[ext=m4a]/"
            "bestaudio/"
            "best"
        )

    else:

        # IMPORTANT FIX
        # progressive mp4 only

        fmt = (
            "best[ext=mp4]/"
            "best"
        )

    opts = {

        "format": fmt,

        "quiet": False,

        "no_warnings": False,

        "noplaylist": True,

        "nocheckcertificate": True,

        "ignoreerrors": False,

        "geo_bypass": True,

        "retries": 10,

        "fragment_retries": 10,

        "socket_timeout": 120,

        # IMPORTANT
        "http_headers": {

            "User-Agent":
                "Mozilla/5.0",

            "Accept-Language":
                "en-US,en;q=0.9",
        },

        # IMPORTANT FIX
        # WEB CLIENT ONLY

        "extractor_args": {

            "youtube": {

                "player_client": [
                    "web"
                ]
            }
        }
    }

    # output
    if output_path:

        opts["outtmpl"] = output_path

    # ffmpeg
    ffmpeg_path = shutil.which("ffmpeg")

    if ffmpeg_path:

        opts["ffmpeg_location"] = ffmpeg_path

    # cookies optional
    if os.path.exists("cookies.txt"):

        opts["cookiefile"] = "cookies.txt"

    return opts

# =========================================================
# SAFE STREAM URL
# =========================================================

def get_stream_url(info, audio=False):

    # direct url
    if info.get("url"):

        return info["url"]

    formats = info.get("formats", [])

    if not formats:

        return None

    # reverse = best first
    for f in reversed(formats):

        if not f.get("url"):
            continue

        # skip no audio
        if audio:

            if f.get("acodec") == "none":
                continue

        return f["url"]

    return None

# =========================================================
# INFO
# =========================================================

@app.get("/info")
def info(url: str):

    url = clean_url(url)

    try:

        opts = yt_opts()

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

            "webpage_url":
                info.get("webpage_url")
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# =========================================================
# STREAM
# =========================================================

@app.get("/stream")
def stream(url: str):

    url = clean_url(url)

    try:

        opts = yt_opts()

        with yt_dlp.YoutubeDL(opts) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

        stream_url = get_stream_url(info)

        if not stream_url:

            raise Exception(
                "No stream URL found"
            )

        return {

            "status": "success",

            "title":
                info.get("title"),

            "thumbnail":
                info.get("thumbnail"),

            "duration":
                info.get("duration"),

            "stream_url":
                stream_url
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# =========================================================
# AUDIO STREAM
# =========================================================

@app.get("/audio-stream")
def audio_stream(url: str):

    url = clean_url(url)

    try:

        opts = yt_opts(audio=True)

        with yt_dlp.YoutubeDL(opts) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

        stream_url = get_stream_url(
            info,
            audio=True
        )

        if not stream_url:

            raise Exception(
                "No audio stream found"
            )

        return {

            "status": "success",

            "title":
                info.get("title"),

            "thumbnail":
                info.get("thumbnail"),

            "audio_url":
                stream_url
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# =========================================================
# DOWNLOAD VIDEO
# =========================================================

@app.get("/download")
def download(url: str):

    url = clean_url(url)

    uid = str(uuid.uuid4())

    output_template = os.path.join(
        DOWNLOAD_DIR,
        f"{uid}.%(ext)s"
    )

    try:

        opts = yt_opts(output_template)

        with yt_dlp.YoutubeDL(opts) as ydl:

            info = ydl.extract_info(
                url,
                download=True
            )

            filename = ydl.prepare_filename(
                info
            )

        # merged file correction
        base = filename.rsplit(".", 1)[0]

        mp4 = base + ".mp4"

        if os.path.exists(mp4):

            filename = mp4

        return FileResponse(

            path=filename,

            media_type="video/mp4",

            filename=os.path.basename(
                filename
            )
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# =========================================================
# DOWNLOAD AUDIO MP3
# =========================================================

@app.get("/audio")
def audio(url: str):

    url = clean_url(url)

    uid = str(uuid.uuid4())

    output_template = os.path.join(
        DOWNLOAD_DIR,
        f"{uid}.%(ext)s"
    )

    try:

        opts = yt_opts(
            output_template,
            audio=True
        )

        # convert to mp3
        opts["postprocessors"] = [{

            "key":
                "FFmpegExtractAudio",

            "preferredcodec":
                "mp3",

            "preferredquality":
                "192",
        }]

        with yt_dlp.YoutubeDL(opts) as ydl:

            info = ydl.extract_info(
                url,
                download=True
            )

            filename = ydl.prepare_filename(
                info
            )

        mp3 = (
            filename.rsplit(".", 1)[0]
            + ".mp3"
        )

        return FileResponse(

            path=mp3,

            media_type="audio/mpeg",

            filename=os.path.basename(mp3)
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# =========================================================
# REDIRECT STREAM
# =========================================================

@app.get("/redirect")
def redirect(url: str):

    url = clean_url(url)

    try:

        opts = yt_opts()

        with yt_dlp.YoutubeDL(opts) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

        stream_url = get_stream_url(info)

        if not stream_url:

            raise Exception(
                "No stream URL found"
            )

        return RedirectResponse(
            url=stream_url
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():

    return {
        "status": "healthy"
    }

# =========================================================
# STARTUP
# =========================================================

print("===================================")
print("YouTube Downloader API Started")
print("===================================")
