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
        "message": "Video Streaming API Active"
    }

# ================= CLEAN URL =================
def clean_url(url: str):
    # remove playlist / radio noise
    if "list=" in url:
        url = url.split("&list=")[0]
    return url

# ================= YTDLP OPTIONS =================
def base_opts():
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "socket_timeout": 60,
        "format": "best",
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0 Safari/537.36"
            )
        },
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        }
    }

# ================= CORE EXTRACT =================
def extract_video(url: str):
    url = clean_url(url)

    opts = base_opts()

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

        if not info:
            raise Exception("No video info found")

        return info

# ================= INFO =================
@app.get("/info")
def info(url: str):

    try:
        data = extract_video(url)

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
        data = extract_video(url)

        stream_url = data.get("url")

        # fallback safe loop
        if not stream_url:
            for f in data.get("formats", []):
                if f.get("url") and f.get("vcodec") != "none":
                    stream_url = f["url"]
                    break

        return {
            "status": "success",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "duration": data.get("duration"),
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
        opts = base_opts()
        opts["format"] = "bestaudio"

        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info(url, download=False)

            audio_url = data.get("url")

            if not audio_url:
                for f in data.get("formats", []):
                    if f.get("url") and f.get("acodec") != "none":
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
