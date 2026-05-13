from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import socket
import time
import random

socket.setdefaulttimeout(30)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= USER AGENTS =================

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/136.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.0 Safari/605.1.15",
]

# ================= CORE ENGINE =================

def build_opts(extra=None):

    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,

        # cookies (VERY IMPORTANT)
        "cookiefile": "cookies.txt",

        # stability
        "nocheckcertificate": True,
        "geo_bypass": True,
        "retries": 10,
        "fragment_retries": 10,
        "socket_timeout": 30,

        # anti-bot rotation
        "http_headers": {
            "User-Agent": random.choice(UA_POOL),
            "Accept-Language": "en-US,en;q=0.9",
        },

        # multi-client extraction
        "extractor_args": {
            "youtube": {
                "player_client": ["web", "android", "tv"]
            }
        },

        # best format
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
    }

    if extra:
        opts.update(extra)

    return opts


# ================= RETRY ENGINE =================

def safe_extract(url, retries=3):

    last_error = None

    for i in range(retries):

        try:
            opts = build_opts()

            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if info:
                return info

        except Exception as e:
            last_error = str(e)
            time.sleep(1.5)

    return {"error": last_error}


# ================= HOME =================

@app.get("/")
def home():
    return {
        "status": "running",
        "system": "ULTRA PRO DOWNLOADER",
        "version": "3.0"
    }


# ================= EXTRACT =================

@app.get("/extract")
def extract(url: str):

    info = safe_extract(url)

    if "error" in info:
        return {
            "status": "failed",
            "error": info["error"]
        }

    formats = []

    for f in info.get("formats", []):

        if not f.get("url"):
            continue

        if f.get("vcodec") == "none":
            continue

        formats.append({
            "id": f.get("format_id"),
            "quality": f.get("format_note"),
            "ext": f.get("ext"),
            "size": f.get("filesize", 0),
            "url": f.get("url")
        })

    best = formats[-1]["url"] if formats else ""

    return {
        "status": "success",
        "title": info.get("title"),
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "platform": info.get("extractor"),
        "best_download": best,
        "formats": formats
    }


# ================= AUDIO =================

@app.get("/audio")
def audio(url: str):

    try:
        opts = build_opts({"format": "bestaudio/best"})

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        return {
            "status": "success",
            "title": info.get("title"),
            "audio_url": info.get("url")
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }


# ================= DIRECT DOWNLOAD LINK =================

@app.get("/download")
def download(url: str):

    try:
        opts = build_opts({
            "format": "bestvideo+bestaudio/best",
        })

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        return {
            "status": "success",
            "title": info.get("title"),
            "download_url": info.get("url"),
            "ext": "mp4"
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }
