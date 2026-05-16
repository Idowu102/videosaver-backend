from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import socket
import os
import uuid
import threading

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

# ================= HOME =================
@app.get("/")
def home():
    return {
        "status": "running",
        "message": "YT Downloader API Active"
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
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/137.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9"
        },
        "extractor_args": {
            "youtube": {
                "player_client": ["web", "android"]
            }
        }
    }

# ================= PROGRESS HOOK =================
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

# ================= EXTRACT =================
@app.get("/extract")
def extract(url: str):
    try:
        ydl_opts = get_ydl_opts()
        ydl_opts["format"] = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

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
        ydl_opts = get_ydl_opts()
        ydl_opts["format"] = "bestaudio/best"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            return {
                "status": "success",
                "title": info.get("title"),
                "thumbnail": info.get("thumbnail"),
                "audio_url": info.get("url")
            }

    except Exception as e:
        return {"status": "failed", "error": str(e)}

# ================= DOWNLOAD =================
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

# ================= CHECK PROGRESS =================
@app.get("/progress/{file_id}")
def progress(file_id: str):
    return download_progress.get(file_id, {
        "status": "not_found"
    })
