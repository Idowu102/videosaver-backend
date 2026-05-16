from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import socket
import time

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
        "message": "🔥 Never-Fail Streaming API Active"
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

        # IMPORTANT
        "cookiefile": "cookies.txt",

        "http_headers": {

            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0 Safari/537.36"
            ),

            "Accept-Language":
                "en-US,en;q=0.9",
        },

        "extractor_args": {

            "youtube": {

                "player_client": [
                    "android",
                    "web",
                    "tv"
                ]
            }
        },

        "retries": 5,
        "fragment_retries": 5,
    }

# ================= SAFE EXTRACT =================

def safe_extract(url):

    modes = [

        "best",

        "best[ext=mp4]/best",

        "bestaudio/best",
    ]

    last_error = None

    for fmt in modes:

        try:

            opts = base_opts()

            opts["format"] = fmt

            with yt_dlp.YoutubeDL(opts) as ydl:

                info = ydl.extract_info(
                    url,
                    download=False
                )

                if info:
                    return info

        except Exception as e:

            last_error = str(e)

            time.sleep(1)

    raise Exception(last_error or "Unable to extract video")

# ================= INFO =================

@app.get("/info")
def info(url: str):

    try:

        info = safe_extract(url)

        return {

            "status": "success",

            "title":
                info.get("title"),

            "thumbnail":
                info.get("thumbnail"),

            "duration":
                info.get("duration"),

            "platform":
                info.get("extractor"),
        }

    except Exception as e:

        return {

            "status": "failed",

            "error":
                str(e)
        }

# ================= STREAM =================

@app.get("/stream")
def stream(url: str):

    try:

        info = safe_extract(url)

        best_url = ""

        for f in reversed(info.get("formats", [])):

            if not f.get("url"):
                continue

            # skip broken formats
            if f.get("acodec") == "none":
                continue

            best_url = f.get("url")

            break

        if best_url == "":

            best_url = info.get("url", "")

        return {

            "status": "success",

            "title":
                info.get("title"),

            "thumbnail":
                info.get("thumbnail"),

            "duration":
                info.get("duration"),

            "stream_url":
                best_url
        }

    except Exception as e:

        return {

            "status": "failed",

            "error":
                str(e)
        }

# ================= AUDIO =================

@app.get("/audio")
def audio(url: str):

    try:

        opts = base_opts()

        opts["format"] = "bestaudio/best"

        with yt_dlp.YoutubeDL(opts) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

            audio_url = ""

            for f in reversed(info.get("formats", [])):

                if not f.get("url"):
                    continue

                if f.get("acodec") == "none":
                    continue

                audio_url = f.get("url")

                break

            if audio_url == "":

                audio_url = info.get("url", "")

            return {

                "status": "success",

                "title":
                    info.get("title"),

                "thumbnail":
                    info.get("thumbnail"),

                "audio_url":
                    audio_url
            }

    except Exception as e:

        return {

            "status": "failed",

            "error":
                str(e)
        }
