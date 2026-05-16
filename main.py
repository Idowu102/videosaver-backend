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
        "message": "🚀 Stable Video Backend Active"
    }


# ================= BASE OPTIONS =================
def base_opts():
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 60,

        # 🔥 YouTube stability fix
        "format": "bestvideo+bestaudio/best",

        "merge_output_format": "mp4",

        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web", "tv"]
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

        # OPTIONAL (UNCOMMENT IF YOU ADD cookies.txt)
        # "cookiefile": "cookies.txt",
    }


# ================= SAFE EXTRACT =================
def extract_video(url: str):
    try:
        with yt_dlp.YoutubeDL(base_opts()) as ydl:
            data = ydl.extract_info(url, download=False)
            return data
    except Exception as e:
        raise Exception(f"Extraction failed: {str(e)}")


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

        return {
            "status": "success",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "stream_url": data.get("url")
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

        return {
            "status": "success",
            "title": data.get("title"),
            "audio_url": data.get("url")
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }
