from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import socket

socket.setdefaulttimeout(30)

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
    return {
        "status": "running",
        "message": "Advanced Video Downloader Backend"
    }

def get_ydl_opts():
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "cookiefile": "cookies.txt",
        "nocheckcertificate": True,
        "extract_flat": False,
        "geo_bypass": True,

        "extractor_args": {
            "youtube": {
                "player_client": ["android"]
            },
            "facebook": {
                "allow_unplayable_formats": ["true"]
            }
        },

        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/137.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9"
        }
    }

# ================= VIDEO =================

@app.get("/extract")
def extract(url: str):

    try:

        ydl_opts = get_ydl_opts()

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

            if not info:
                return {
                    "status": "failed",
                    "error": "Video not found"
                }

            formats_list = []

            for f in info.get("formats", []):

                if not f.get("url"):
                    continue

                if f.get("vcodec") == "none":
                    continue

                formats_list.append({

                    "format_id":
                        f.get("format_id", ""),

                    "quality":
                        f.get("format_note", "unknown"),

                    "ext":
                        f.get("ext", ""),

                    "filesize":
                        f.get("filesize", 0),

                    "url":
                        f.get("url", "")
                })

            # BEST FORMAT WITH AUDIO
            best_url = ""

            for f in reversed(info.get("formats", [])):

                if not f.get("url"):
                    continue

                if f.get("vcodec") == "none":
                    continue

                if f.get("acodec") == "none":
                    continue

                best_url = f.get("url", "")
                break

            return {

                "status": "success",

                "title":
                    info.get("title", "Unknown"),

                "thumbnail":
                    info.get("thumbnail", ""),

                "duration":
                    info.get("duration", 0),

                "platform":
                    info.get("extractor", "unknown"),

                "best_download":
                    best_url,

                "formats":
                    formats_list
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

        ydl_opts = get_ydl_opts()

        ydl_opts["format"] = "bestaudio/best"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

            return {

                "status": "success",

                "title":
                    info.get("title", "Unknown"),

                "thumbnail":
                    info.get("thumbnail", ""),

                "audio_url":
                    info.get("url", "")
            }

    except Exception as e:

        return {
            "status": "failed",
            "error": str(e)
        }
