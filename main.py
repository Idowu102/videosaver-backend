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
    version="2026.2"
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
            "stable extraction",
            "nodejs challenge solving",
            "cookies support"
        ]
    }

# =========================================================
# CLEAN URL
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
# YT OPTIONS
# =========================================================

def yt_opts(output_path=None, audio=False):

    # IMPORTANT:
    # avoid protected DASH formats

    if audio:

        fmt = (
            "bestaudio/"
            "best"
        )

    else:

        fmt = (
            "best[ext=mp4]/"
            "best"
        )

    opts = {

        # IMPORTANT
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
        "extract_flat": False,

        # IMPORTANT
        "concurrent_fragment_downloads": 1,

        # IMPORTANT
        "http_headers": {

            "User-Agent":
                "Mozilla/5.0",

            "Accept-Language":
                "en-US,en;q=0.9",
        },

        # IMPORTANT
        # JS challenge solving
        "js_runtimes": ["node"],

        # IMPORTANT
        # use web only
        "extractor_args": {

            "youtube": {

                "player_client": [
                    "web"
                ],

                "player_skip": []
            }
        }
    }

    # output path
    if output_path:

        opts["outtmpl"] = output_path

    # ffmpeg
    ffmpeg_path = shutil.which("ffmpeg")

    if ffmpeg_path:

        opts["ffmpeg_location"] = ffmpeg_path

    # cookies file
    if os.path.exists("cookies.txt"):

        opts["cookiefile"] = "cookies.txt"

    # auto browser cookies
    try:

        import browser_cookie3

        opts["cookiesfrombrowser"] = (
            "chrome",
        )

    except:
        pass

    return opts

# =========================================================
# SAFE STREAM URL
# =========================================================

def get_stream_url(info, audio=False):

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

        # audio only
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

        audio_url = get_stream_url(
            info,
            audio=True
        )

        if not audio_url:

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
                audio_url
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

        # merged correction
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

        # mp3 conversion
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
