from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import asyncio
from concurrent.futures import ThreadPoolExecutor

app = FastAPI(title="Production Stable Media Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor(max_workers=6)

# =========================================================
# OPTIONAL COOKIES (USER PROVIDED ONLY)
# =========================================================

COOKIE_FILE = "cookies.txt"

# =========================================================
# URL FIXER
# =========================================================

def fix_url(url: str):
    url = url.strip()

    if "youtube.com/shorts/" in url:
        vid = url.split("/shorts/")[1].split("?")[0]
        return f"https://www.youtube.com/watch?v={vid}"

    if "facebook.com/share" in url:
        return None

    return url


def validate(url: str):
    if not url:
        return False

    allowed = [
        "youtube.com",
        "youtu.be",
        "facebook.com",
        "tiktok.com",
        "instagram.com",
        "x.com",
        "twitter.com"
    ]

    return any(x in url for x in allowed)

# =========================================================
# YT-DLP OPTIONS (SAFE MODE)
# =========================================================

def ydl_opts(client="android"):

    opts = {
        "quiet": True,
        "noplaylist": True,
        "retries": 1,
        "fragment_retries": 1,
        "socket_timeout": 20,
        "cachedir": False,
        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        },
        "extractor_args": {
            "youtube": {
                "player_client": [client]
            }
        }
    }

    # OPTIONAL cookies (ONLY if file exists)
    try:
        import os
        if os.path.exists(COOKIE_FILE):
            opts["cookiefile"] = COOKIE_FILE
    except:
        pass

    return opts

# =========================================================
# ASYNC EXECUTION
# =========================================================

def _extract(url, client):
    try:
        with yt_dlp.YoutubeDL(ydl_opts(client)) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        return {"error": str(e)}


async def extract(url, client="android"):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _extract, url, client)


async def smart_extract(url):

    clients = ["android", "web", "ios"]

    for c in clients:
        data = await extract(url, c)
        if isinstance(data, dict) and "error" not in data:
            return data

    return None

# =========================================================
# FORMAT ENGINE
# =========================================================

def clean_formats(data):

    formats = data.get("formats") or []

    out = []

    for f in formats:
        if not f.get("url"):
            continue

        out.append({
            "url": f["url"],
            "height": f.get("height") or 0,
            "ext": f.get("ext"),
            "vcodec": f.get("vcodec"),
            "acodec": f.get("acodec")
        })

    return sorted(out, key=lambda x: x["height"])


def pick_best(formats, quality):

    if not formats:
        return None

    if quality == "best":
        return formats[-1]

    if quality == "low":
        return formats[0]

    try:
        q = int(quality)
        return min(formats, key=lambda x: abs(x["height"] - q))
    except:
        return formats[-1]

# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():
    return {
        "status": "production_engine_online",
        "features": [
            "multi-client fallback",
            "safe extraction",
            "no crash mode",
            "cookie support (optional)"
        ]
    }

# =========================================================
# INFO
# =========================================================

@app.get("/info")
async def info(url: str):

    url = fix_url(url)

    if not url:
        return {"status": "error", "message": "Unsupported URL"}

    data = await smart_extract(url)

    if not data:
        return {"status": "failed", "message": "Media unavailable"}

    return {
        "status": "success",
        "title": data.get("title"),
        "duration": data.get("duration"),
        "thumbnail": data.get("thumbnail")
    }

# =========================================================
# STREAM
# =========================================================

@app.get("/stream")
async def stream(url: str, quality: str = "best"):

    url = fix_url(url)

    if not url:
        return {"status": "error", "message": "Invalid URL"}

    if not validate(url):
        return {"status": "error", "message": "Unsupported platform"}

    data = await smart_extract(url)

    if not data:
        return {
            "status": "failed",
            "message": "Extraction blocked (platform restriction or login required)"
        }

    formats = clean_formats(data)

    if not formats:
        return {"status": "failed", "message": "No formats found"}

    selected = pick_best(formats, quality)

    return {
        "status": "success",
        "title": data.get("title"),
        "quality": selected["height"],
        "stream_url": selected["url"]
    }

# =========================================================
# AUDIO (ROBUST FALLBACK)
# =========================================================

@app.get("/audio")
async def audio(url: str):

    url = fix_url(url)

    if not url:
        return {"status": "error", "message": "Invalid URL"}

    data = await smart_extract(url)

    if not data:
        return {
            "status": "failed",
            "message": "Audio unavailable (blocked or restricted)"
        }

    formats = clean_formats(data)

    if not formats:
        return {"status": "failed", "message": "No media formats"}

    audio_only = [
        f for f in formats
        if f["acodec"] != "none" and f["vcodec"] == "none"
    ]

    chosen = None

    if audio_only:
        chosen = audio_only[-1]
    else:
        chosen = formats[-1]  # fallback ANY

    return {
        "status": "success",
        "title": data.get("title"),
        "audio_url": chosen["url"]
    }
