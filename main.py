from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import socket
import re
import requests

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
        "engine": "Production Hybrid Engine",
        "youtube": "optimized"
    }

# ================= URL CLEANER =================

def clean_url(url: str):

    url = url.strip()

    if "&list=" in url:
        url = url.split("&list=")[0]

    if "&pp=" in url:
        url = url.split("&pp=")[0]

    if "youtube.com/shorts/" in url:

        video_id = url.split("/shorts/")[1].split("?")[0]

        url = f"https://www.youtube.com/watch?v={video_id}"

    return url

# ================= GET VIDEO ID =================

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

# ================= YT OPTIONS =================

def yt_opts(format_type="best"):

    return {

        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "ignoreerrors": True,
        "geo_bypass": True,
        "retries": 10,
        "fragment_retries": 10,
        "socket_timeout": 120,
        "noplaylist": True,
        "extract_flat": False,
        "format": format_type,

        # IMPORTANT
        "cookiefile": "cookies.txt",

        "http_headers": {

            "User-Agent":
                "com.google.android.youtube/19.09.37 (Linux; U; Android 11)",

            "Accept-Language":
                "en-US,en;q=0.9",
        },

        "extractor_args": {

            "youtube": {

                "player_client": [
                    "android",
                    "ios",
                    "web",
                    "tv_embedded"
                ],

                "player_skip": [
                    "configs",
                    "webpage"
                ]
            }
        }
    }

# ================= YOUTUBE FALLBACK =================

def youtube_fallback(video_id):

    try:

        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"

        r = requests.get(url, timeout=20)

        if r.status_code != 200:
            return None

        data = r.json()

        thumb = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

        return {
            "title": data.get("title", "YouTube Video"),
            "thumbnail": thumb,
            "duration": 0,
            "url": f"https://www.youtube.com/watch?v={video_id}"
        }

    except:
        return None

# ================= SAFE EXTRACT =================

def safe_extract(url, audio=False):

    url = clean_url(url)

    formats = []

    if audio:

        formats = [
            "bestaudio[ext=m4a]",
            "bestaudio",
            "best"
        ]

    else:

        formats = [
    "18",   # 360p mp4 + audio
    "22",   # 720p mp4 + audio
    "best[ext=mp4]",
    "best"
]

    last_error = None

    for fmt in formats:

        try:

            opts = yt_opts(fmt)

            with yt_dlp.YoutubeDL(opts) as ydl:

                info = ydl.extract_info(url, download=False)

                if info:

                    if info.get("url"):
                        return info

                    formats_data = info.get("formats", [])

                    for f in reversed(formats_data):

                        if not f.get("url"):
                            continue

                        if audio and f.get("acodec") == "none":
                            continue

                        return {
                            "title": info.get("title"),
                            "thumbnail": info.get("thumbnail"),
                            "duration": info.get("duration"),
                            "url": f.get("url")
                        }

        except Exception as e:

            last_error = str(e)
            continue

    video_id = get_video_id(url)

    if video_id:

        fallback = youtube_fallback(video_id)

        if fallback:
            return fallback

    raise Exception(last_error or "Extraction failed")

# ================= EXTRACT =================

@app.get("/extract")
def extract(url: str):

    try:

        info = safe_extract(url)

        video_url = info.get("url")

        return {
            "status": "success",
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),

            # FIX
            "best_download": video_url,
            "stream_url": video_url
        }

    except Exception as e:

        return {
            "status": "failed",
            "error": str(e)
        }

# ================= STREAM =================

@app.get("/stream")
def stream(url: str):

    try:

        info = safe_extract(url)

        return {
            "status": "success",
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "stream_url": info.get("url")
        }

    except Exception as e:

        return {
            "status": "failed",
            "error": str(e)
        }

# ================= AUDIO =================

@app.get("/audio")
def audio(url: str):

    try:

        info = safe_extract(url, audio=True)

        return {
            "status": "success",
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "audio_url": info.get("url")
        }

    except Exception as e:

        return {
            "status": "failed",
            "error": str(e)
        }
