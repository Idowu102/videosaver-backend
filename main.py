from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import socket

socket.setdefaulttimeout(60)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "running", "message": "API active"}

# ================= OPTIONS =================
def opts():
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,

        # IMPORTANT FIX
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        },

        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        }
    }

def extract(url: str):
    with yt_dlp.YoutubeDL(opts()) as ydl:
        return ydl.extract_info(url, download=False)

# ================= INFO =================
@app.get("/info")
def info(url: str = Query(...)):
    try:
        data = extract(url)

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
def stream(url: str = Query(...)):
    try:
        data = extract(url)

        # yt-dlp already gives best playable URL
        return {
            "status": "success",
            "title": data.get("title"),
            "stream_url": data.get("url"),
            "thumbnail": data.get("thumbnail")
        }

    except Exception as e:
        return {"status": "failed", "error": str(e)}

# ================= AUDIO =================
@app.get("/audio")
def audio(url: str = Query(...)):
    try:
        ydl_opts = opts()
        ydl_opts["format"] = "bestaudio"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            data = ydl.extract_info(url, download=False)

        return {
            "status": "success",
            "title": data.get("title"),
            "audio_url": data.get("url")
        }

    except Exception as e:
        return {"status": "failed", "error": str(e)}
