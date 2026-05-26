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
# SOCKET TIMEOUT
# =========================================================

socket.setdefaulttimeout(120)

# =========================================================
# APP
# =========================================================

app = FastAPI(
    title="Stable YouTube Downloader API",
    version="2026.5"
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
# URL CHECK
# =========================================================

def is_youtube(url: str):

    return any(x in url for x in [

        "youtube.com",
        "youtu.be"
    ])

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

        video_id = (
            url.split("/shorts/")[1]
            .split("?")[0]
        )

        url = (
            "https://www.youtube.com/watch?v="
            f"{video_id}"
        )

    return url

# =========================================================
# yt-dlp OPTIONS
# =========================================================

def ydl_opts(outtmpl=None, audio=False):

    # IMPORTANT:
    # Avoid unstable DASH extraction

    fmt = (
        "bestaudio/best"
        if audio else
        "best[ext=mp4]/best"
    )

    opts = {

        # =================================================
        # FORMAT
        # =================================================

        "format": fmt,

        # =================================================
        # GENERAL
        # =================================================

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

        # =================================================
        # HEADERS
        # =================================================

        "http_headers": {

            "User-Agent":
                (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                ),

            "Accept-Language":
                "en-US,en;q=0.9",
        },

        # =================================================
        # YOUTUBE CLIENT
        # =================================================

        "extractor_args": {

            "youtube": {

                "player_client": [
                    "web"
                ]
            }
        }
    }

    # =====================================================
    # OUTPUT
    # =====================================================

    if outtmpl:

        opts["outtmpl"] = outtmpl

    # =====================================================
    # FFMPEG
    # =====================================================

    ffmpeg = shutil.which("ffmpeg")

    if ffmpeg:

        opts["ffmpeg_location"] = ffmpeg

    # =====================================================
    # COOKIES
    # =====================================================

    if os.path.exists("cookies.txt"):

        opts["cookiefile"] = "cookies.txt"

    return opts

# =========================================================
# SAFE RESPONSE
# =========================================================

def failed(error):

    return JSONResponse({

        "status": "failed",

        "error": str(error)

    })

# =========================================================
# HEALTH
# =========================================================

@app.get("/")
def home():

    return {

        "status":
            "running",

        "engine":
            "Stable Production Engine",

        "version":
            "2026.5",

        "features": [

            "youtube download",
            "youtube audio",
            "youtube stream",
            "shorts support",
            "mobile youtube support",
            "ffmpeg support",
            "cookies support",
            "stable extraction"
        ]
    }

# =========================================================
# INFO
# =========================================================

@app.get("/info")
def info(url: str):

    try:

        if not is_youtube(url):

            return failed(
                "Only YouTube URLs supported"
            )

        url = clean_url(url)

        with yt_dlp.YoutubeDL(
            ydl_opts()
        ) as ydl:

            data = ydl.extract_info(
                url,
                download=False
            )

        return {

            "status":
                "success",

            "title":
                data.get("title"),

            "thumbnail":
                data.get("thumbnail"),

            "duration":
                data.get("duration"),

            "uploader":
                data.get("uploader"),

            "view_count":
                data.get("view_count")
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

        if not is_youtube(url):

            return failed(
                "Only YouTube URLs supported"
            )

        url = clean_url(url)

        with yt_dlp.YoutubeDL(
            ydl_opts()
        ) as ydl:

            data = ydl.extract_info(
                url,
                download=False
            )

        stream_url = data.get("url")

        # fallback
        if not stream_url:

            for f in reversed(
                data.get("formats", [])
            ):

                if f.get("url"):

                    stream_url = f["url"]
                    break

        if not stream_url:

            return failed(
                "No stream URL found"
            )

        return {

            "status":
                "success",

            "title":
                data.get("title"),

            "thumbnail":
                data.get("thumbnail"),

            "duration":
                data.get("duration"),

            "stream_url":
                stream_url
        }

    except Exception as e:

        traceback.print_exc()

        return failed(e)

# =========================================================
# VIDEO DOWNLOAD
# =========================================================

@app.get("/download")
def download(url: str):

    try:

        if not is_youtube(url):

            return failed(
                "Only YouTube URLs supported"
            )

        url = clean_url(url)

        uid = str(uuid.uuid4())

        output_template = os.path.join(
            DOWNLOAD_DIR,
            f"{uid}.%(ext)s"
        )

        with yt_dlp.YoutubeDL(
            ydl_opts(output_template)
        ) as ydl:

            data = ydl.extract_info(
                url,
                download=True
            )

            filename = ydl.prepare_filename(
                data
            )

        # merged mp4 correction
        base = filename.rsplit(".", 1)[0]

        mp4 = base + ".mp4"

        if os.path.exists(mp4):

            filename = mp4

        if not os.path.exists(filename):

            return failed(
                "Downloaded file missing"
            )

        return FileResponse(

            path=filename,

            media_type="video/mp4",

            filename=os.path.basename(
                filename
            )
        )

    except Exception as e:

        traceback.print_exc()

        return failed(e)

# =========================================================
# AUDIO DOWNLOAD
# =========================================================

@app.get("/audio")
def audio(url: str):

    try:

        if not is_youtube(url):

            return failed(
                "Only YouTube URLs supported"
            )

        url = clean_url(url)

        uid = str(uuid.uuid4())

        output_template = os.path.join(
            DOWNLOAD_DIR,
            f"{uid}.%(ext)s"
        )

        opts = ydl_opts(
            output_template,
            audio=True
        )

        # =================================================
        # MP3 CONVERSION
        # =================================================

        opts["postprocessors"] = [{

            "key":
                "FFmpegExtractAudio",

            "preferredcodec":
                "mp3",

            "preferredquality":
                "192",
        }]

        with yt_dlp.YoutubeDL(opts) as ydl:

            data = ydl.extract_info(
                url,
                download=True
            )

            filename = ydl.prepare_filename(
                data
            )

        mp3 = (
            filename.rsplit(".", 1)[0]
            + ".mp3"
        )

        if not os.path.exists(mp3):

            return failed(
                "MP3 conversion failed"
            )

        return FileResponse(

            path=mp3,

            media_type="audio/mpeg",

            filename=os.path.basename(
                mp3
            )
        )

    except Exception as e:

        traceback.print_exc()

        return failed(e)

# =========================================================
# STARTUP
# =========================================================

print("===================================")
print("Stable YouTube Downloader Started")
print("===================================")
