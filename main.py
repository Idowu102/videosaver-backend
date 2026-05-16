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
    return {"status": "running", "message": "Video Saver API Working"}

def base_opts():
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "socket_timeout": 60,
        "cookiefile": "cookies.txt",

        # IMPORTANT FIX
        "format": "best",

        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

def clean_url(url: str):
    if "&" in url:
        url = url.split("&")[0]
    return url

def safe_extract(url: str):
    url = clean_url(url)

    with yt_dlp.YoutubeDL(base_opts()) as ydl:
        return ydl.extract_info(url, download=False)

@app.get("/extract")
def extract(url: str = Query(...)):
    try:
        info = safe_extract(url)

        best_url = ""

        for f in info.get("formats", []):
            if f.get("url"):
                best_url = f["url"]

        return {
            "status": "success",
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "best_download": best_url
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }

@app.get("/audio")
def audio(url: str = Query(...)):
    try:
        opts = base_opts()
        opts["format"] = "bestaudio"

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(clean_url(url), download=False)

        audio_url = ""

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
