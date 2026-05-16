from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import socket
import os
import uuid
import threading
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

# ================= STORAGE =================
download_progress = {}
lock = threading.Lock()

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ================= USER AGENT =================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
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

        # 🔥 IMPORTANT: fix “not a robot”
        "cookiefile": "cookies.txt",  # optional but recommended

        "http_headers": HEADERS,

        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web", "tv"]
            }
        },

        # retries
        "retries": 5,
        "fragment_retries": 5,
    }

# ================= SMART FORMAT FALLBACK =================
def get_format():
    return [
        "best[ext=mp4]/best",
        "best",
        "bestvideo+bestaudio/best",
    ]

# ================= SAFE EXTRACT =================
def safe_extract(url):
    last_error = None

    for fmt in get_format():
        try:
            ydl_opts = base_opts()
            ydl_opts["format"] = fmt

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)

        except Exception as e:
            last_error = str(e)
            time.sleep(1)

    raise Exception(last_error or "Extraction failed")

# ================= HOME =================
@app.get("/")
def home():
    return {
        "status": "running",
        "message": "🔥 Bulletproof Video Downloader API"
    }

# ================= EXTRACT =================
@app.get("/extract")
def extract(url: str):
    try:
        info = safe_extract(url)

        formats = []

        for f in info.get("formats", []):
            if not f.get("url"):
                continue

            formats.append({
                "format_id": f.get("format_id"),
                "ext": f.get("ext"),
                "quality": f.get("format_note"),
                "filesize": f.get("filesize"),
                "url": f.get("url")
            })

        return {
            "status": "success",
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "best_url": info.get("url"),
            "formats": formats
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
        info = safe_extract(url)

        return {
            "status": "success",
            "title": info.get("title"),
            "audio_url": info.get("url"),
            "thumbnail": info.get("thumbnail")
        }

    except Exception as e:
        return {"status": "failed", "error": str(e)}

# ================= PROGRESS =================
def progress_hook(d):
    file_id = d.get("info_dict", {}).get("id", "global")

    with lock:
        if file_id not in download_progress:
            download_progress[file_id] = {}

        if d["status"] == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1

            download_progress[file_id] = {
                "status": "downloading",
                "percent": round(downloaded / total * 100, 2),
                "speed": d.get("speed"),
                "eta": d.get("eta")
            }

        elif d["status"] == "finished":
            download_progress[file_id] = {
                "status": "finished",
                "percent": 100
            }

# ================= DOWNLOAD =================
def download_task(url, file_id):
    try:
        ydl_opts = base_opts()

        ydl_opts.update({
            "format": "best[ext=mp4]/best",
            "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
            "progress_hooks": [progress_hook]
        })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        with lock:
            download_progress[file_id] = {
                "status": "completed",
                "percent": 100
            }

    except Exception as e:
        with lock:
            download_progress[file_id] = {
                "status": "failed",
                "error": str(e)
            }

# ================= START DOWNLOAD =================
@app.get("/download")
def download(url: str, background_tasks: BackgroundTasks):
    file_id = str(uuid.uuid4())

    download_progress[file_id] = {
        "status": "starting",
        "percent": 0
    }

    background_tasks.add_task(download_task, url, file_id)

    return {
        "status": "started",
        "file_id": file_id
    }

# ================= CHECK PROGRESS =================
@app.get("/progress/{file_id}")
def progress(file_id: str):
    return download_progress.get(file_id, {
        "status": "not_found"
    })
