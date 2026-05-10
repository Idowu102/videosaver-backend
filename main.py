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

# ================= EXTRACT =================

@app.get("/extract")
def extract(url: str):

    try:

        ydl_opts = {

            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "skip_download": True,

            "http_headers": {
                "User-Agent":
                "Mozilla/5.0"
            }
        }

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

                    if not f.get("url"):
                        continue

                    # SKIP DASH AUDIO ONLY
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

            # BEST URL
            best_url = ""

            if len(formats_list) > 0:
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

# ================= AUDIO ONLY =================

@app.get("/audio")
def audio(url: str):

    try:

        ydl_opts = {

            "quiet": True,
            "skip_download": True,

            "format":
                "bestaudio/best"
        }

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