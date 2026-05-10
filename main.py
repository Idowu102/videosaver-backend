from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp

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
        "message": "Video Saver Backend Running"
    }

# ================= YT-DLP OPTIONS =================

def get_ydl_opts():

    return {

        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,

        # Important
        "extract_flat": False,
        "nocheckcertificate": True,

        # safer format
        "format": "best",

        # browser headers
        "http_headers": {
            "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
        },

        # YouTube anti-bot bypass
        "extractor_args": {
            "youtube": {
                "player_client": [
                    "android",
                    "web_creator",
                    "web"
                ]
            }
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

            formats = info.get("formats", [])

            for f in formats:

                video_url = f.get("url")

                if not video_url:
                    continue

                # skip audio-only
                if f.get("vcodec") == "none":
                    continue

                formats_list.append({

                    "format_id":
                        f.get("format_id", ""),

                    "quality":
                        f.get("format_note", "unknown"),

                    "ext":
                        f.get("ext", ""),

                    "url":
                        video_url
                })

            # Best video URL
            best_url = ""

            for f in reversed(formats_list):

                if f["url"]:

                    best_url = f["url"]
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

        ydl_opts["format"] = "bestaudio"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

            formats = info.get("formats", [])

            audio_url = ""

            for f in reversed(formats):

                if f.get("acodec") != "none":

                    if f.get("url"):

                        audio_url = f.get("url")
                        break

            return {

                "status": "success",

                "title":
                    info.get("title", "Unknown"),

                "thumbnail":
                    info.get("thumbnail", ""),

                "audio_url":
                    audio_url
            }

    except Exception as e:

        return {

            "status": "failed",
            "error": str(e)
        }
