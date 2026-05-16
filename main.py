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
        "message": "🔥 YouTube-Resistant Streaming API"
    }

# ================= CLEAN URL =================
def clean_url(url: str):
    return url.split("&")[0].split("?si=")[0]

# ================= BASE OPTIONS =================
def base_opts():
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "geo_bypass": True,

        # 🔥 IMPORTANT (BYPASS LEVEL 1)
        "cookiefile": "cookies.txt",

        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web", "tv"]
            }
        },

        "http_headers": {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9"
        }
    }

# ================= CORE EXTRACT (WITH FALLBACKS) =================
def extract_video(url: str):
    url = clean_url(url)

    strategies = [
        # Strategy 1 (best)
        {
            "format": "best",
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}}
        },

        # Strategy 2 (android only)
        {
            "format": "best",
            "extractor_args": {"youtube": {"player_client": ["android"]}}
        },

        # Strategy 3 (audio fallback)
        {
            "format": "bestaudio/best",
            "extractor_args": {"youtube": {"player_client": ["android", "web"]}}
        }
    ]

    last_error = None

    for s in strategies:
        try:
            opts = base_opts()
            opts.update(s)

            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)

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
            "platform": data.get("extractor")
        }

    except Exception as e:
        return {"status": "failed", "error": str(e)}

# ================= STREAM =================
@app.get("/stream")
def stream(url: str = Query(...)):
    try:
        data = extract_video(url)

        stream_url = data.get("url")

        # fallback search inside formats
        for f in data.get("formats", []):
            if f.get("url") and f.get("acodec") != "none":
                stream_url = f["url"]

        return {
            "status": "success",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "stream_url": stream_url
        }

    except Exception as e:
        return {"status": "failed", "error": str(e)}

# ================= AUDIO =================
@app.get("/audio")
def audio(url: str = Query(...)):
    try:
        data = extract_video(url)

        audio_url = data.get("url")

        for f in data.get("formats", []):
            if f.get("acodec") != "none" and f.get("url"):
                audio_url = f["url"]

        return {
            "status": "success",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "audio_url": audio_url
        }

    except Exception as e:
        return {"status": "failed", "error": str(e)}

# ================= BACKWARD COMPATIBILITY =================
@app.get("/extract")
def extract(url: str = Query(...)):
    try:
        data = extract_video(url)

        return {
            "status": "success",
            "title": data.get("title"),
            "thumbnail": data.get("thumbnail"),
            "stream_url": data.get("url"),
            "audio_url": data.get("url")
        }

    except Exception as e:
        return {"status": "failed", "error": str(e)}
