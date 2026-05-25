from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
import yt_dlp
import os
import uuid
import shutil
import subprocess

app = FastAPI()

# =====================================================
# CORS
# =====================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# DOWNLOAD FOLDER
# =====================================================

DOWNLOAD_DIR = "downloads"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# =====================================================
# HOME
# =====================================================

@app.get("/")
def home():
    return {
        "status": "running",
        "engine": "PRO DOWNLOAD ENGINE"
    }

# =====================================================
# CLEAN URL
# =====================================================

def clean_url(url: str):

    url = url.strip()

    url = url.replace(
        "m.youtube.com",
        "www.youtube.com"
    )

    if "&list=" in url:
        url = url.split("&list=")[0]

    if "&pp=" in url:
        url = url.split("&pp=")[0]

    if "youtube.com/shorts/" in url:

        vid = url.split("/shorts/")[1].split("?")[0]

        url = f"https://www.youtube.com/watch?v={vid}"

    return url

# =====================================================
# YT OPTIONS
# =====================================================

def yt_opts(output_path, audio=False):

    if audio:

        fmt = "bestaudio[ext=m4a]/bestaudio"

    else:

        fmt = "bestvideo+bestaudio/best"

    return {

        "format": fmt,

        "outtmpl": output_path,

        "quiet": False,

        "noplaylist": True,

        "nocheckcertificate": True,

        "ignoreerrors": False,

        "geo_bypass": True,

        "retries": 10,

        "fragment_retries": 10,

        "socket_timeout": 120,

        # IMPORTANT
        "merge_output_format": "mp4",

        # cookies optional
        "cookiefile":
            "cookies.txt"
            if os.path.exists("cookies.txt")
            else None,

        # FFmpeg
        "ffmpeg_location": shutil.which("ffmpeg"),

        "extractor_args": {
            "youtube": {
                "player_client": [
                    "android",
                    "web",
                    "ios"
                ]
            }
        },

        "http_headers": {

            "User-Agent":
                "Mozilla/5.0",

            "Accept-Language":
                "en-US,en;q=0.9",
        }
    }

# =====================================================
# VIDEO INFO
# =====================================================

@app.get("/info")
def info(url: str):

    url = clean_url(url)

    try:

        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

        return {

            "status": "success",

            "title":
                info.get("title"),

            "thumbnail":
                info.get("thumbnail"),

            "duration":
                info.get("duration"),

            "uploader":
                info.get("uploader"),
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# =====================================================
# DOWNLOAD VIDEO
# =====================================================

@app.get("/download")
def download(url: str):

    url = clean_url(url)

    uid = str(uuid.uuid4())

    output_template = os.path.join(
        DOWNLOAD_DIR,
        f"{uid}.%(ext)s"
    )

    try:

        opts = yt_opts(output_template)

        with yt_dlp.YoutubeDL(opts) as ydl:

            info = ydl.extract_info(
                url,
                download=True
            )

            filename = ydl.prepare_filename(info)

        # merged file correction
        base = filename.rsplit(".", 1)[0]

        final_mp4 = base + ".mp4"

        if os.path.exists(final_mp4):
            filename = final_mp4

        return FileResponse(
            path=filename,
            media_type="video/mp4",
            filename=os.path.basename(filename)
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# =====================================================
# DOWNLOAD AUDIO
# =====================================================

@app.get("/audio")
def audio(url: str):

    url = clean_url(url)

    uid = str(uuid.uuid4())

    output_template = os.path.join(
        DOWNLOAD_DIR,
        f"{uid}.%(ext)s"
    )

    try:

        opts = yt_opts(
            output_template,
            audio=True
        )

        # audio extraction
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]

        with yt_dlp.YoutubeDL(opts) as ydl:

            info = ydl.extract_info(
                url,
                download=True
            )

            filename = ydl.prepare_filename(info)

        mp3 = filename.rsplit(".", 1)[0] + ".mp3"

        return FileResponse(
            path=mp3,
            media_type="audio/mpeg",
            filename=os.path.basename(mp3)
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# =====================================================
# STREAM VIDEO
# =====================================================

@app.get("/stream")
def stream(url: str):

    url = clean_url(url)

    try:

        opts = {
            "quiet": True,
            "format": "best",
            "noplaylist": True,
            "extractor_args": {
                "youtube": {
                    "player_client": [
                        "android",
                        "web"
                    ]
                }
            }
        }

        with yt_dlp.YoutubeDL(opts) as ydl:

            info = ydl.extract_info(
                url,
                download=False
            )

        stream_url = info.get("url")

        if not stream_url:

            formats = info.get("formats", [])

            for f in reversed(formats):

                if f.get("url"):

                    stream_url = f["url"]

                    break

        if not stream_url:

            raise Exception(
                "No stream URL found"
            )

        return {
            "status": "success",
            "stream_url": stream_url
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
