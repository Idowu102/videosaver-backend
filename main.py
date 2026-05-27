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
    title="Video Downloader API",
    version="1.0"
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
# SUPPORTED
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

# =========================================================
# CHECK URL
# =========================================================

def supported(url: str):

    return any(x in url for x in SUPPORTED)

# =========================================================
# CLEAN URL
# =========================================================

def clean_url(url: str):

    url = url.strip()

    # mobile youtube
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

        vid = (
            url.split("/shorts/")[1]
            .split("?")[0]
        )

        url = (
            "https://www.youtube.com/watch?v="
            f"{vid}"
        )

    return url

# =========================================================
# yt-dlp OPTIONS
# =========================================================

def ydl_opts(outtmpl=None, audio=False):

    fmt = (
        "bestaudio/best"
        if audio else
        "bestvideo+bestaudio/best"
    )

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

        "extractor_args": {

            "youtube": {

                "player_client": [
                    "web"
                ]
            }
        }
    }

    # output
    if outtmpl:

        opts["outtmpl"] = outtmpl

    # ffmpeg
    ffmpeg = shutil.which("ffmpeg")

    if ffmpeg:

        opts["ffmpeg_location"] = ffmpeg

    # cookies.txt support
    if os.path.exists("cookies.txt"):

        opts["cookiefile"] = "cookies.txt"

    return opts

# =========================================================
# SAFE ERROR
# =========================================================

def failed(error):

    return JSONResponse({

        "status":
            "failed",

        "error":
            str(error)
    })

# =========================================================
# GET STREAM URL
# =========================================================

def get_stream(data, audio=False):

    if data.get("url"):

        return data["url"]

    formats = data.get("formats", [])

    if not formats:

        return None

    for f in reversed(formats):

        if not f.get("url"):
            continue

        if audio:

            if f.get("acodec") == "none":
                continue

        return f["url"]

    return None

# =========================================================
# HOME
# =========================================================

@app.get("/")
def home():

    return {

        "status":
            "running",

        "engine":
            "stable-production"
    }

# =========================================================
# INFO
# =========================================================

@app.get("/info")
def info(url: str):

    try:

        if not supported(url):

            return failed(
                "Unsupported URL"
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
                data.get("uploader")
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

            return failed(
                "Unsupported URL"
            )

        url = clean_url(url)

        with yt_dlp.YoutubeDL(
            ydl_opts()
        ) as ydl:

            data = ydl.extract_info(
                url,
                download=False
            )

        if not data:

            return failed(
                "No media found"
            )

        stream_url = get_stream(data)

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
# AUDIO STREAM
# =========================================================

@app.get("/audio-stream")
def audio_stream(url: str):

    try:

        if not supported(url):

            return failed(
                "Unsupported URL"
            )

        url = clean_url(url)

        with yt_dlp.YoutubeDL(
            ydl_opts(audio=True)
        ) as ydl:

            data = ydl.extract_info(
                url,
                download=False
            )

        audio_url = get_stream(
            data,
            audio=True
        )

        if not audio_url:

            return failed(
                "No audio stream found"
            )

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

        return failed(e)

# =========================================================
# VIDEO DOWNLOAD
# =========================================================

@app.get("/download")
def download(url: str):

    try:

        if not supported(url):

            return failed(
                "Unsupported URL"
            )

        url = clean_url(url)

        uid = str(uuid.uuid4())

        output = os.path.join(
            DOWNLOAD_DIR,
            f"{uid}.%(ext)s"
        )

        with yt_dlp.YoutubeDL(
            ydl_opts(output)
        ) as ydl:

            data = ydl.extract_info(
                url,
                download=True
            )

            filename = ydl.prepare_filename(
                data
            )

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

        if not supported(url):

            return failed(
                "Unsupported URL"
            )

        url = clean_url(url)

        uid = str(uuid.uuid4())

        output = os.path.join(
            DOWNLOAD_DIR,
            f"{uid}.%(ext)s"
        )

        opts = ydl_opts(
            output,
            audio=True
        )

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
print("Downloader API Started")
print("===================================")
