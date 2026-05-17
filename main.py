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
        "engine": "Production Hybrid Engine v2",
        "youtube": "stable"
    }

# ================= CLEAN URL =================
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


# ================= VIDEO ID =================
def get_video_id(url):
    patterns = [
        r"v=([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"shorts/([a-zA-Z0-9_-]{11})",
    ]

    for p in patterns:
        match = re.search(p, url)
        if match:
            return match.group(1)

    return None


# ================= YT-DLP OPTIONS =================
def yt_opts():
    return {
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "ignoreerrors": False,
        "geo_bypass": True,
        "retries": 10,
        "fragment_retries": 10,
        "socket_timeout": 120,
        "noplaylist": True,

        "format": "best",

        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 11) "
                "AppleWebKit/537.36 Chrome/119 Mobile Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },

        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web", "ios"],
            }
        }
    }


# ================= FALLBACK =================
def youtube_fallback(video_id):
    try:
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        r = requests.get(url, timeout=20)

        if r.status_code != 200:
            return None

        data = r.json()

        return {
            "title": data.get("title", "Video"),
            "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            "duration": 0,
            "url": f"https://www.youtube.com/watch?v={video_id}"
        }

    except:
        return None


# ================= CORE ENGINE =================
def safe_extract(url: str, audio=False):
    url = clean_url(url)

    try:
        with yt_dlp.YoutubeDL(yt_opts()) as ydl:
            info = ydl.extract_info(url, download=False)

            if not info:
                raise Exception("No info returned")

            # DIRECT FILE (Facebook, MP4, etc.)
            if info.get("url") and not info.get("formats"):
                return {
                    "title": info.get("title"),
                    "thumbnail": info.get("thumbnail"),
                    "duration": info.get("duration"),
                    "url": info.get("url")
                }

            # FORMATS LOOP (YouTube etc.)
            formats = info.get("formats", [])

            best = None

            for f in reversed(formats):
                if not f.get("url"):
                    continue

                if audio and f.get("acodec") == "none":
                    continue

                best = f.get("url")
                break

            if best:
                return {
                    "title": info.get("title"),
                    "thumbnail": info.get("thumbnail"),
                    "duration": info.get("duration"),
                    "url": best
                }

            # fallback direct url
            if info.get("url"):
                return {
                    "title": info.get("title"),
                    "thumbnail": info.get("thumbnail"),
                    "duration": info.get("duration"),
                    "url": info.get("url")
                }

    except Exception:
        pass

    # fallback youtube
    video_id = get_video_id(url)
    if video_id:
        fb = youtube_fallback(video_id)
        if fb:
            return fb

    raise Exception("Extraction failed")


# ================= API =================
@app.get("/extract")
def extract(url: str):
    try:
        info = safe_extract(url, audio=False)

        return {
            "status": "success",
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "stream_url": info.get("url")
        }

    except Exception as e:
        return {"status": "failed", "error": str(e)}


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
        return {"status": "failed", "error": str(e)}


@app.get("/stream")
def stream(url: str):
    try:
        info = safe_extract(url, audio=False)

        return {
            "status": "success",
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "stream_url": info.get("url")
        }

    except Exception as e:
        return {"status": "failed", "error": str(e)}
