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
        "message": "Advanced Video Downloader Backend"
    }

# ================= COMMON YTDLP OPTIONS =================

def get_ydl_opts():

    return {

        # IMPORTANT
        "cookiefile": "cookies.txt",

        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,

        # Better bypass
        "extractor_retries": 3,

        "http_headers": {

            "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        }
    }

# ================= EXTRACT VIDEO =================

@app.get("/extract")
def extract(url: str):

    try:

        ydl_opts = get_ydl_opts()

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

            if info is None:

                return {
                    "status": "failed",
                    "error": "Video not found"
                }

            # ================= FORMATS =================

            formats_list = []

            if "formats" in info:

                for f in info["formats"]:

                    # Skip invalid
                    if not f.get("url"):
                        continue

                    # Skip audio only
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

            # ================= BEST URL =================

            best_url = ""

            if len(formats_list) > 0:

                # Pick highest quality
                best_url = formats_list[-1]["url"]

            return {

                "status": "success",

                "title":
                    info.get(
                        "title",
                        "Unknown"
                    ),

                "thumbnail":
                    info.get(
                        "thumbnail",
                        ""
                    ),

                "duration":
                    info.get(
                        "duration",
                        0
                    ),

                "platform":
                    info.get(
                        "extractor",
                        "unknown"
                    ),

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

        # Best audio
        ydl_opts["format"] = "bestaudio/best"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

            audio_url = info.get("url", "")

            return {

                "status": "success",

                "title":
                    info.get(
                        "title",
                        "Unknown"
                    ),

                "thumbnail":
                    info.get(
                        "thumbnail",
                        ""
                    ),

                "audio_url":
                    audio_url
            }

    except Exception as e:

        return {

            "status": "failed",

            "error": str(e)
        }
