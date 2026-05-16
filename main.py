from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import socket
import os
import uuid
import threading
import random
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

# ================= USER AGENTS (ROTATION) =================
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.0 Safari/605.1.15"
]

# ================= HOME =================
@app.get("/")
def home():
    return {
        "status": "running",
        "message": "ANTI-BLOCK PRO YT Downloader Active"
    }

# ================= OPTIONS =================
def get_ydl_opts():
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "socket_timeout": 60,

        # 🔥 IMPORTANT: cookies fix
        "cookiefile": "cookies.txt",

        # 🔥 anti-bot headers
        "http_headers": {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept-Language": "en-US,en;q=0.9"
        },

        # 🔥 stronger YouTube bypass mode
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],
            }
        },

        # retry system
        "retries": 5,
        "fragment_retries": 5,
        "skip_unavailable_fragments": True,
    }

# ================= PROGRESS =================
def progress_hook(d):
    file_id = d.get("info_dict", {}).get("id", "global")

    with lock:
        if file_id not in download_progress:
            download_progress[file_id] = {}

        if d["status"] == "downloading":
            downloaded = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1

            percent = round(downloaded / total * 100, 2)

            download_progress[file_id] = {
                "status": "downloading",
                "percent": percent,
                "speed": d.get("speed"),
                "eta": d.get("eta")
            }

        elif d["status"] == "finished":
            download_progress[file_id] = {
                "status": "finished",
                "percent": 100
            }

# ================= SAFE EXTRACT (WITH RETRIES) =================
def safe_extract(url, retries=3):
    for i in range(retries):
        try:
            ydl_opts = get_ydl_opts()

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)

        except Exception as e:
            msg = str(e)

            # 🔥 wait and retry if blocked
            if "not a robot" in msg.lower() or "sign in" in msg.lower():
                time.sleep(2 + i * 2)
                continue

            raise e

    return None

# ================= EXTRACT =================
@app.get("/extract")
def extract(url: str):
    try:
        info = safe_extract(url)

        if not info:
            return {"status": "failed", "error": "Blocked or not found"}

        formats_list = []

        for f in info.get("formats", []):
            if not f.get("url"):
                continue
            if f.get("vcodec") == "none":
                continue

            formats_list.append({
                "format_id": f.get("format_id"),
                "quality": f.get("format_note"),
                "ext": f.get("ext"),
                "filesize": f.get("filesize"),
                "url": f.get("url")
            })

        return {
            "status": "success",
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "platform": info.get("extractor"),
            "best_url": info.get("url"),
            "formats": formats_list
        }

    except Exception as e:
        return {"status": "failed", "error": str(e)}

# ================= AUDIO =================
@app.get("/audio")
def audio(url: str):
    try:
        info = safe_extract(url)

        if not info:
            return {"status": "failed", "error": "Blocked or not found"}

        return {
            "status": "success",
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "audio_url": info.get("url")
        }

    except Exception as e:
        return {"status": "failed", "error": str(e)}

# ================= DOWNLOAD TASK =================
def download_task(url: str, file_id: str):
    try:
        ydl_opts = get_ydl_opts()

        ydl_opts.update({
            "format": "best",
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

# ================= PROGRESS =================
@app.get("/progress/{file_id}")
def progress(file_id: str):
    return download_progress.get(file_id, {
        "status": "not_found"
    })
