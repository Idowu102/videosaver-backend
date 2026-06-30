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
@app.get("/version")
def version():
    return {
        "yt_dlp": yt_dlp.version.__version__
    }
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
    
     # Facebook
    "facebook.com",
    "fb.watch",

    # Instagram
    "instagram.com",

    # TikTok
    "tiktok.com",

    # Twitter / X
    "twitter.com",
    "x.com",

    # Reddit
    "reddit.com",

    # Pinterest
    "pinterest.com",

    # LinkedIn
    "linkedin.com",

    # Snapchat
    "snapchat.com",

    # Threads
    "threads.net",

    # Tumblr
    "tumblr.com",

    # Vimeo
    "vimeo.com",

    # Dailymotion
    "dailymotion.com",

    # WhatsApp
    "whatsapp.com",
    "chat.whatsapp.com"
]

# =========================================================
# CHECK URL
# =========================================================

def supported(url: str):
    if not url:
        return False

    url = url.lower().strip()

    return any(domain in url for domain in SUPPORTED)

# =========================================================
# CLEAN URL
# =========================================================

def clean_url(url: str):
    return url.strip()

# =========================================================
# yt-dlp OPTIONS
# =========================================================

def ydl_opts(outtmpl=None, audio=False, quality="best"):

    if audio:
        fmt = "bestaudio/best"
    else:
        if quality == "best":
            fmt = "bestvideo+bestaudio/best"
        else:
            height = quality.replace("p", "")
            fmt = (
                f"bestvideo[height<={height}]+bestaudio/"
                f"best[height<={height}]/"
                "best"
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
        "merge_output_format": "mp4",

        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },

        "extractor_args": {
            "youtube": {
                "player_client": [
                    "android",
                    "web",
                    "ios"
                ]
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
# SAFE ERROR
# =========================================================

def failed(error):

    return JSONResponse({

        "status": "failed",
        "error": str(error)
    })

# =========================================================
# STREAM PICKER
# =========================================================

def get_stream(data, audio=False):

    # direct stream
    if data.get("url"):

        return data["url"]

    formats = data.get("formats", [])

    if not formats:

        return None

    # reverse for better quality first
    for f in reversed(formats):

        if not f.get("url"):
            continue

        # audio filter
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
        "status": "running",
        "engine": "stable-downloader-engine",
        "features": [
            "facebook",
            "instagram",
            "tiktok",
            "twitter",
            "x",
            "reddit",
            "vimeo",
            "video download",
            "audio download",
            "stream extraction"
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
            "view_count": data.get("view_count"),
        }

    except Exception as e:
        traceback.print_exc()
        return failed(str(e))

# =========================================================
# STREAM
# =========================================================

from urllib.parse import quote

BASE_URL = "https://videosaver-backend-production.up.railway.app"

@app.get("/stream")
def stream(url: str):

    try:

        if not supported(url):
            return failed("Unsupported URL")

        url = clean_url(url)

        with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
            data = ydl.extract_info(url, download=False)

        qualities = []
        urls = {}

        for f in data.get("formats", []):

            if f.get("vcodec") == "none":
                continue

            if not f.get("height"):
                continue

            quality = f"{f['height']}p"

            if quality not in urls:

                urls[quality] = (
                    f"{BASE_URL}/download"
                    f"?url={quote(url)}"
                    f"&quality={quote(quality)}"
                )

                qualities.append(quality)

        qualities.sort(
            key=lambda x: int(x.replace("p","")),
            reverse=True
        )

        return {
            "status":"success",
            "title":data.get("title"),
            "thumbnail":data.get("thumbnail"),
            "qualities":qualities,
            "urls":urls
        }

    except Exception as e:
        traceback.print_exc()
        return failed(str(e))
# =========================================================
# VIDEO DOWNLOAD
# =========================================================

@app.get("/download")
def download(url: str, quality: str = "best"):

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
    ydl_opts(output, quality=quality)
) as ydl:

            data = ydl.extract_info(
                url,
                download=True
            )

            filename = ydl.prepare_filename(
                data
            )

        # merged correction
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

        # MP3 CONVERSION
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

        "status": "healthy"
    }

# =========================================================
# STARTUP
# =========================================================

print("===================================")
print("Ultimate Downloader API Started")
print("===================================")
