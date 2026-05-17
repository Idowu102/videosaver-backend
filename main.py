from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import socket
import re
import requests

socket.setdefaulttimeout(120)

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
        "engine": "Stable Download Engine v1"
    }


# ================= CLEAN URL =================
def clean_url(url: str):
    url = url.strip()

    if "&list=" in url:
        url = url.split("&list=")[0]

    if "youtube.com/shorts/" in url:
        vid = url.split("/shorts/")[1].split("?")[0]
        url = f"https://www.youtube.com/watch?v={vid}"

    return url


# ================= OPTIONS =================
def ydl_opts():
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "format": "best",
        "geo_bypass": True,
        "socket_timeout": 120,
        "retries": 5,
        "http_headers": {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
        },
    }


# ================= CORE EXTRACT =================
def extract_info(url: str):
    url = clean_url(url)

    with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
        info = ydl.extract_info(url, download=False)

        if not info:
            raise Exception("No info found")

        # direct file (facebook, mp4, etc.)
        if info.get("url") and not info.get("formats"):
            return {
                "title": info.get("title"),
                "thumbnail": info.get("thumbnail"),
                "url": info.get("url")
            }

        # formats fallback
        for f in reversed(info.get("formats", [])):
            if f.get("url"):
                return {
                    "title": info.get("title"),
                    "thumbnail": info.get("thumbnail"),
                    "url": f.get("url")
                }

        return {
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "url": info.get("url")
        }


@app.get("/extract")
def extract(url: str):
    try:
        data = extract_info(url)
        return {
            "status": "success",
            "title": data["title"],
            "thumbnail": data["thumbnail"],
            "stream_url": data["url"]
        }
    except Exception as e:
        return {"status": "failed", "error": str(e)}


@app.get("/audio")
def audio(url: str):
    try:
        data = extract_info(url)
        return {
            "status": "success",
            "title": data["title"],
            "audio_url": data["url"]
        }
    except Exception as e:
        return {"status": "failed", "error": str(e)}
