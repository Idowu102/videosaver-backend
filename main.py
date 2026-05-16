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
        "message": "🔥 YouTube-Proof Streaming API Active"
    }


# ================= BASE OPTIONS (FIXED) =================
def base_opts():
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "geo_bypass": True,
        "socket_timeout": 60,

        # 🔥 CRITICAL FIX: better YouTube bypass strategy
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web", "tv"]
            }
        },

        # 🔥 IMPORTANT HEADERS (helps bypass bot check)
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },

        # OPTIONAL: add cookies if available
        # "cookiefile": "cookies.txt",
    }


# ================= SAFE EXTRACT =================
def safe_extract(url: str):
    opts = base_opts()

    # 🔥 FIX: always request safest format first
    opts["format"] = "best[ext=mp4]/best"

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    except Exception:
        # fallback mode
        opts["extractor_args"]["youtube"]["player_client"] = ["android"]
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)


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

        formats = data.get("formats", [])

        best = None

        for f in reversed(formats):
            if f.get("url") and f.get("vcodec") != "none":
                best = f["url"]
                break

        if not best:
            best = data.get("url")

        return {
            "status": "success",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "stream_url": best
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

        audio_url = None

        for f in data.get("formats", []):
            if f.get("acodec") != "none" and f.get("url"):
                audio_url = f["url"]

        return {
            "status": "success",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "audio_url": audio_url or data.get("url")
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }
