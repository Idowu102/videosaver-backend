from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
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
        "message": "🔥 Video Saver API Working"
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

        # IMPORTANT FIX
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        },

        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

# ================= CLEAN URL =================
def clean_url(url: str):
    return url.split("&")[0].split("?si=")[0]

# ================= SAFE EXTRACT =================
def safe_extract(url: str):
    url = clean_url(url)

    opts = base_opts()

    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)

# ================= INFO =================
@app.get("/info")
def info(url: str = Query(...)):
    try:
        info = safe_extract(url)

        return {
            "status": "success",
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "platform": info.get("extractor")
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
        info = safe_extract(url)

        stream_url = info.get("url")

        # fallback: pick best format
        for f in info.get("formats", []):
            if f.get("url") and f.get("acodec") != "none":
                stream_url = f["url"]

        return {
            "status": "success",
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
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
            info = ydl.extract_info(clean_url(url), download=False)

        audio_url = info.get("url")

        for f in info.get("formats", []):
            if f.get("acodec") != "none" and f.get("url"):
                audio_url = f["url"]

        return {
            "status": "success",
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "audio_url": audio_url
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }

# ================= BACKWARD COMPATIBILITY (IMPORTANT) =================
@app.get("/extract")
def extract(url: str = Query(...)):
    try:
        info = safe_extract(url)

        return {
            "status": "success",
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "stream_url": info.get("url"),
            "audio_url": info.get("url")
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }
