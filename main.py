from fastapi import FastAPI
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
        "message": "🔥 Stable Streaming API Active"
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

        "cookiefile": "cookies.txt",

        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },

       "extractor_args": {
    "youtube": {
        "player_client": ["web", "android"]
    }
}
    }

# ================= CLEAN URL =================
def clean_url(url: str):
    url = url.split("&list=")[0]
    url = url.split("&pp=")[0]
    url = url.split("&start_radio=")[0]
    return url

# ================= SAFE EXTRACT =================
def safe_extract(url):

    url = clean_url(url)

    opts = base_opts()
    opts["format"] = "best"

    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)

# ================= INFO =================
@app.get("/info")
def info(url: str):

    try:
        data = safe_extract(url)

        return {
            "status": "success",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "duration": data.get("duration"),
            "platform": data.get("extractor")
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
        data = safe_extract(url)

        stream_url = data.get("url")

        # fallback safe method
        if not stream_url:
            formats = data.get("formats", [])
            for f in formats:
                if f.get("url") and f.get("vcodec") != "none":
                    stream_url = f["url"]
                    break

        if not stream_url:
            return {
                "status": "failed",
                "error": "No playable stream found"
            }

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
            "audio_url": audio_url
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }
