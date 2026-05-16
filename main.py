from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import os
import socket

socket.setdefaulttimeout(60)

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
        "message": "🔥 STABLE STREAMING API ACTIVE"
    }

# ================= CLEAN URL =================
def clean_url(url: str):
    url = url.split("&list=")[0]
    url = url.split("&pp=")[0]
    url = url.replace("shorts/", "watch?v=")
    return url


# ================= YT-DLP OPTIONS =================
def ydl_opts():
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,

        # 🔥 IMPORTANT FIX (BOT BYPASS)
        "cookiefile": "cookies.txt",   # MUST exist

        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web", "tv"]
            }
        },

        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },

        "retries": 10,
        "fragment_retries": 10,
    }


# ================= SAFE EXTRACT =================
def safe_extract(url: str):

    url = clean_url(url)

    formats = [
        "bestvideo+bestaudio/best",
        "best[ext=mp4]/best",
        "best",
    ]

    last_error = None

    for f in formats:
        try:
            opts = ydl_opts()
            opts["format"] = f

            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)

        except Exception as e:
            last_error = str(e)

    raise Exception(last_error or "Extraction failed")


# ================= INFO =================
@app.get("/info")
def info(url: str):
    try:
        data = safe_extract(url)

        return {
            "status": "success",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "duration": data.get("duration")
        }

    except Exception as e:
        return {"status": "failed", "error": str(e)}


# ================= STREAM =================
@app.get("/stream")
def stream(url: str):
    try:
        data = safe_extract(url)

        stream_url = data.get("url")

        if not stream_url:
            for f in data.get("formats", []):
                if f.get("url") and f.get("vcodec") != "none":
                    stream_url = f["url"]
                    break

        return {
            "status": "success",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "stream_url": stream_url
        }

    except Exception as e:
        return {"status": "failed", "error": str(e)}


# ================= AUDIO =================
@app.get("/audio")
def audio(url: str):
    try:
        data = safe_extract(url)

        audio_url = data.get("url")

        if not audio_url:
            for f in data.get("formats", []):
                if f.get("acodec") != "none" and f.get("url"):
                    audio_url = f["url"]
                    break

        return {
            "status": "success",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "audio_url": audio_url
        }

    except Exception as e:
        return {"status": "failed", "error": str(e)}
