from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
import yt_dlp
import os
import uuid
import shutil
import socket
import re
import traceback

# =========================================================
# SOCKET TIMEOUT
# =========================================================

socket.setdefaulttimeout(120)

# =========================================================
# APP
# =========================================================

app = FastAPI(
    title="YouTube Downloader API",
    version="2026.3"
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
# DOWNLOADS DIR
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
            "Ultimate Production Engine",

        "version":
            "2026.3",

        "features": [

            "video download",
            "audio download",
            "youtube streaming",
            "youtube shorts",
            "mobile youtube",
            "cookies support",
            "ffmpeg support",
            "nodejs challenge solving",
            "stable extraction",
            "redirect streaming",
            "safe fallback engine"
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
# YT OPTIONS
# =========================================================

def yt_opts(output_path=None, audio=False):

    # IMPORTANT:
    # Avoid DASH formats
    # Use stable formats only

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

        # =================================================
        # FORMAT
        # =================================================

        "format": fmt,

        # =================================================
        # GENERAL
        # =================================================

        "quiet": False,

        "no_warnings": False,

        "noplaylist": True,

        "nocheckcertificate": True,

        "ignoreerrors": False,

        "geo_bypass": True,

        "retries": 10,

        "fragment_retries": 10,

        "socket_timeout": 120,

        "extract_flat": False,

        "concurrent_fragment_downloads": 1,

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
        # JS RUNTIME
        # =================================================

        "js_runtimes": ["node"],

        # =================================================
        # YOUTUBE
        # =================================================

        "extractor_args": {

            "youtube": {

                # IMPORTANT
                # WEB ONLY

                "player_client": [

                    "web"
                ],

                # IMPORTANT
                "player_skip": []
            }
        }
    }

    # =====================================================
    # OUTPUT
    # =====================================================

    if output_path:

        opts["outtmpl"] = output_path

    # =====================================================
    # FFMPEG
    # =====================================================

    ffmpeg_path = shutil.which("ffmpeg")

    if ffmpeg_path:

        opts["ffmpeg_location"] = ffmpeg_path

    # =====================================================
    # COOKIES FILE
    # =====================================================

    if os.path.exists("cookies.txt"):

        opts["cookiefile"] = "cookies.txt"

    # =====================================================
    # BROWSER COOKIES
    # =====================================================

    try:

        import browser_cookie3

        opts["cookiesfrombrowser"] = (
            "chrome",
        )

    except:
        pass

    return opts

# =========================================================
# STREAM URL EXTRACTOR
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

        # audio mode
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

    try:

        url = clean_url(url)

        opts = yt_opts()

        with yt_dlp.YoutubeDL(opts) as ydl:

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
                data.get("view_count"),

            "webpage_url":
                data.get("webpage_url")
        }

    except Exception as e:

        traceback.print_exc()

        return {

            "status":
                "failed",

            "error":
                str(e)
        }

# =========================================================
# STREAM
# =========================================================

@app.get("/stream")
def stream(url: str):

    try:

        url = clean_url(url)

        opts = yt_opts()

        with yt_dlp.YoutubeDL(opts) as ydl:

            data = ydl.extract_info(
                url,
                download=False
            )

        if not data:

            return {

                "status":
                    "failed",

                "error":
                    "No video info extracted"
            }

        stream_url = get_stream_url(data)

        if not stream_url:

            return {

                "status":
                    "failed",

                "error":
                    "No stream URL found"
            }

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

        return {

            "status":
                "failed",

            "error":
                str(e)
        }

# =========================================================
# AUDIO STREAM
# =========================================================

@app.get("/audio-stream")
def audio_stream(url: str):

    try:

        url = clean_url(url)

        opts = yt_opts(audio=True)

        with yt_dlp.YoutubeDL(opts) as ydl:

            data = ydl.extract_info(
                url,
                download=False
            )

        audio_url = get_stream_url(
            data,
            audio=True
        )

        if not audio_url:

            return {

                "status":
                    "failed",

                "error":
                    "No audio stream found"
            }

        return {

            "status":
                "success",

            "title":
                data.get("title"),

            "thumbnail":
                data.get("thumbnail"),

            "audio_url":
                audio_url
        }

    except Exception as e:

        traceback.print_exc()

        return {

            "status":
                "failed",

            "error":
                str(e)
        }

# =========================================================
# DOWNLOAD VIDEO
# =========================================================

@app.get("/download")
def download(url: str):

    try:

        url = clean_url(url)

        uid = str(uuid.uuid4())

        output_template = os.path.join(
            DOWNLOAD_DIR,
            f"{uid}.%(ext)s"
        )

        opts = yt_opts(output_template)

        with yt_dlp.YoutubeDL(opts) as ydl:

            data = ydl.extract_info(
                url,
                download=True
            )

            filename = ydl.prepare_filename(
                data
            )

        # mp4 correction
        base = filename.rsplit(".", 1)[0]

        mp4 = base + ".mp4"

        if os.path.exists(mp4):

            filename = mp4

        if not os.path.exists(filename):

            return {

                "status":
                    "failed",

                "error":
                    "Downloaded file missing"
            }

        return FileResponse(

            path=filename,

            media_type="video/mp4",

            filename=os.path.basename(
                filename
            )
        )

    except Exception as e:

        traceback.print_exc()

        return {

            "status":
                "failed",

            "error":
                str(e)
        }

# =========================================================
# DOWNLOAD AUDIO
# =========================================================

@app.get("/audio")
def audio(url: str):

    try:

        url = clean_url(url)

        uid = str(uuid.uuid4())

        output_template = os.path.join(
            DOWNLOAD_DIR,
            f"{uid}.%(ext)s"
        )

        opts = yt_opts(
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

            return {

                "status":
                    "failed",

                "error":
                    "MP3 conversion failed"
            }

        return FileResponse(

            path=mp3,

            media_type="audio/mpeg",

            filename=os.path.basename(mp3)
        )

    except Exception as e:

        traceback.print_exc()

        return {

            "status":
                "failed",

            "error":
                str(e)
        }

# =========================================================
# REDIRECT STREAM
# =========================================================

@app.get("/redirect")
def redirect(url: str):

    try:

        url = clean_url(url)

        opts = yt_opts()

        with yt_dlp.YoutubeDL(opts) as ydl:

            data = ydl.extract_info(
                url,
                download=False
            )

        stream_url = get_stream_url(data)

        if not stream_url:

            return {

                "status":
                    "failed",

                "error":
                    "No redirect stream URL found"
            }

        return RedirectResponse(
            url=stream_url
        )

    except Exception as e:

        traceback.print_exc()

        return {

            "status":
                "failed",

            "error":
                str(e)
        }

# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():

    return {

        "status":
            "healthy"
    }

# =========================================================
# STARTUP
# =========================================================

print("===================================")
print("YouTube Downloader API Started")
print("===================================")
