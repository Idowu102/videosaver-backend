from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import socket
import time

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
        "message": "🔥 Video Saver API Active"
    }

# ================= BASE OPTIONS =================
def base_opts():
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "socket_timeout": 60,

        # safer YouTube mode
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        },

        "retries": 3,
    }

# ================= SAFE EXTRACT =================
def safe_extract(url):
    opts = base_opts()
    opts["format"] = "best"

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        raise Exception(str(e))

# ================= INFO =================
@app.get("/info")
def info(url: str = Query(...)):
    try:
        data = safe_extract(url)

        return {
            "status": "success",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "duration": data.get("duration"),
            "extractor": data.get("extractor")
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }

# ================= STREAM =================
@app.get("/stream")
def stream(url: str = Query(...)):
    try:
        data = safe_extract(url)

        stream_url = data.get("url")

        # fallback: formats loop
        if not stream_url and "formats" in data:
            for f in reversed(data["formats"]):
                if f.get("url"):
                    stream_url = f["url"]
                    break

        return {
            "status": "success",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "stream_url": stream_url
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }

# ================= AUDIO =================
@app.get("/audio")
def audio(url: str = Query(...)):
    try:
        opts = base_opts()
        opts["format"] = "bestaudio/best"

        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info(url, download=False)

        audio_url = data.get("url")

        if not audio_url and "formats" in data:
            for f in reversed(data["formats"]):
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
        return {
            "status": "failed",
            "error": str(e)
        }
