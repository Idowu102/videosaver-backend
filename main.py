from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import socket
import re

socket.setdefaulttimeout(120)

app = FastAPI()

# ================= CORS =================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= HOME =================

@app.get("/")
def home():
    return {
        "status": "running",
        "engine": "yt-dlp production engine",
        "version": "stable"
    }

# ================= URL NORMALIZER =================

def clean_url(url: str):
    url = url.strip()

    # normalize mobile
    url = url.replace("m.youtube.com", "www.youtube.com")

    # remove playlist noise
    if "&list=" in url:
        url = url.split("&list=")[0]

    if "&pp=" in url:
        url = url.split("&pp=")[0]

    # shorts → watch
    if "youtube.com/shorts/" in url:
        vid = url.split("/shorts/")[1].split("?")[0]
        url = f"https://www.youtube.com/watch?v={vid}"

    return url

# ================= VIDEO ID =================

def get_video_id(url):
    patterns = [
        r"v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"shorts/([a-zA-Z0-9_-]{11})",
    ]

    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)

    return None

# ================= YT-DLP OPTIONS =================

def yt_opts(fmt="best", audio=False):

    return {
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 120,
        "noplaylist": True,
        "format": fmt,

        # IMPORTANT: DO NOT HIDE ERRORS
        "ignoreerrors": False,

        # cookies optional
        "cookiefile": "cookies.txt",

        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 11) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/117.0 Mobile Safari/537.36"
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

# ================= CORE EXTRACTOR =================

def extract_youtube(url: str, audio: bool = False):

    url = clean_url(url)

    # format strategy
    if audio:
        formats = [
            "bestaudio[ext=m4a]/bestaudio/best",
        ]
    else:
        formats = [
            "best[ext=mp4]+bestaudio/best",
            "best[ext=mp4]",
            "best"
        ]

    last_error = None

    for fmt in formats:
        try:
            opts = yt_opts(fmt, audio)

            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if not info:
                continue

            # pick best playable URL safely
            stream_url = None

            # case 1: direct
            if info.get("url"):
                stream_url = info["url"]

            # case 2: formats fallback
            if not stream_url and info.get("formats"):
                for f in reversed(info["formats"]):
                    if not f.get("url"):
                        continue

                    if audio and f.get("acodec") == "none":
                        continue

                    stream_url = f["url"]
                    break

            if not stream_url:
                continue

            return {
                "title": info.get("title"),
                "thumbnail": info.get("thumbnail"),
                "duration": info.get("duration"),
                "url": stream_url
            }

        except Exception as e:
            last_error = str(e)
            continue

    raise HTTPException(
        status_code=500,
        detail=f"yt-dlp failed: {last_error}"
    )

# ================= EXTRACT =================

@app.get("/extract")
def extract(url: str):
    info = extract_youtube(url, audio=False)

    return {
        "status": "success",
        "title": info["title"],
        "thumbnail": info["thumbnail"],
        "duration": info["duration"],
        "stream_url": info["url"],
        "download_url": info["url"]
    }

# ================= STREAM =================

@app.get("/stream")
def stream(url: str):
    info = extract_youtube(url, audio=False)

    return {
        "status": "success",
        "title": info["title"],
        "thumbnail": info["thumbnail"],
        "duration": info["duration"],
        "stream_url": info["url"]
    }

# ================= AUDIO =================

@app.get("/audio")
def audio(url: str):
    info = extract_youtube(url, audio=True)

    return {
        "status": "success",
        "title": info["title"],
        "thumbnail": info["thumbnail"],
        "audio_url": info["url"]
    }
