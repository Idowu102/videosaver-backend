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
        "message": "🚀 Production Video Engine Active"
    }


# ================= CORE OPTIONS =================
def base_opts():
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 60,

        # 🔥 IMPORTANT FIX FOR YOUTUBE
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web", "tv"]
            }
        },

        # 🔥 Better headers (helps bypass bot checks)
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },

        # OPTIONAL (UNCOMMENT IF YOU HAVE IT)
        # "cookiefile": "cookies.txt",
    }


# ================= SAFE EXTRACTOR =================
def extract_video(url: str):
    opts = base_opts()

    formats_to_try = [
        "best[ext=mp4]/best",
        "best",
        "bestaudio/best"
    ]

    last_error = None

    for fmt in formats_to_try:
        try:
            opts["format"] = fmt

            with yt_dlp.YoutubeDL(opts) as ydl:
                data = ydl.extract_info(url, download=False)

                if data:
                    return data

        except Exception as e:
            last_error = str(e)

    raise Exception(last_error or "Extraction failed")


# ================= INFO =================
@app.get("/info")
def info(url: str = Query(...)):
    try:
        data = extract_video(url)

        return {
            "status": "success",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "duration": data.get("duration"),
            "source": data.get("extractor")
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
        data = extract_video(url)

        stream_url = None

        # pick best playable format
        for f in reversed(data.get("formats", [])):
            if f.get("url") and f.get("vcodec") != "none":
                stream_url = f["url"]
                break

        return {
            "status": "success",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "stream_url": stream_url or data.get("url")
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


# ================= EXTRACT (ANDROID SAFE) =================
@app.get("/extract")
def extract(url: str = Query(...)):
    try:
        data = extract_video(url)

        return {
            "status": "success",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "duration": data.get("duration"),
            "stream_url": data.get("url"),
            "audio_url": data.get("url"),
            "source": data.get("extractor")
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }
