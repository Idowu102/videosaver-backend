from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import socket

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
        "engine": "Pro Stable Engine v2"
    }


# ================= OPTIONS =================
def opts():
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": "best",
        "socket_timeout": 120,
        "retries": 10,
        "http_headers": {
            "User-Agent": "Mozilla/5.0",
        }
    }


# ================= CORE =================
def extract(url: str):
    with yt_dlp.YoutubeDL(opts()) as ydl:
        info = ydl.extract_info(url, download=False)

        if not info:
            raise Exception("No data")

        # direct file (Facebook, mp4, etc.)
        if info.get("url") and not info.get("formats"):
            return {
                "title": info.get("title"),
                "thumbnail": info.get("thumbnail"),
                "url": info.get("url")
            }

        # best format loop
        for f in info.get("formats", []):
            if f.get("url"):
                return {
                    "title": info.get("title"),
                    "thumbnail": info.get("thumbnail"),
                    "url": f.get("url")
                }

        return {
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "url": info.get("url")
        }


# ================= STREAM =================
@app.get("/extract")
def extract_route(url: str):
    try:
        data = extract(url)
        return {
            "status": "success",
            "title": data["title"],
            "thumbnail": data["thumbnail"],
            "stream_url": data["url"]
        }
    except Exception as e:
        return {"status": "failed", "error": str(e)}


# ================= AUDIO =================
@app.get("/audio")
def audio_route(url: str):
    try:
        data = extract(url)
        return {
            "status": "success",
            "title": data["title"],
            "audio_url": data["url"]
        }
    except Exception as e:
        return {"status": "failed", "error": str(e)}
