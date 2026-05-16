from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp

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
    return {"status": "running"}

@app.get("/extract")
def extract(url: str):
    try:
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "cookiefile": "cookies.txt"
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            return {
                "status": "success",
                "title": info.get("title", ""),
                "thumbnail": info.get("thumbnail", ""),
                "best_download": info["url"]
            }

    except Exception as e:
        return {"status": "failed", "error": str(e)}

@app.get("/audio")
def audio(url: str):
    try:
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "cookiefile": "cookies.txt",
            "format": "bestaudio/best"
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            return {
                "status": "success",
                "audio_url": info["url"]
            }

    except Exception as e:
        return {"status": "failed", "error": str(e)}
