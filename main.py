from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import asyncio
from concurrent.futures import ThreadPoolExecutor

app = FastAPI(title="Stable Media Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor(max_workers=6)

# =========================================================
# URL FIXER
# =========================================================

def fix_url(url: str):

    url = url.strip()

    # YouTube Shorts → Watch
    if "youtube.com/shorts/" in url:
        vid = url.split("/shorts/")[1].split("?")[0]
        return f"https://www.youtube.com/watch?v={vid}"

    # block invalid facebook share links
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
        "twitter.com",
        "x.com"
    ]

    return any(x in url for x in allowed)

# =========================================================
# YT-DLP CORE
# =========================================================

def ydl_opts():

    return {
        "quiet": True,
        "noplaylist": True,
        "retries": 2,
        "fragment_retries": 2,
        "socket_timeout": 20,
        "cachedir": False,
        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        },
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web", "ios"]
            }
        }
    }


def _extract(url):
    try:
        with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        return {"error": str(e)}


async def extract(url):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _extract, url)

# =========================================================
# FORMAT PROCESSOR
# =========================================================

def get_formats(data):

    if not isinstance(data, dict):
        return []

    formats = data.get("formats") or []

    clean = []

    for f in formats:
        if not f.get("url"):
            continue

        clean.append({
            "url": f["url"],
            "height": f.get("height") or 0,
            "ext": f.get("ext"),
            "vcodec": f.get("vcodec"),
            "acodec": f.get("acodec")
        })

    return sorted(clean, key=lambda x: x["height"])


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
# SMART EXTRACT (FALLBACK SAFE)
# =========================================================

async def smart_extract(url):

    data = await extract(url)

    if isinstance(data, dict) and "error" not in data:
        return data

    return None

# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():
    return {
        "status": "stable_engine_online",
        "features": [
            "no crash mode",
            "smart fallback",
            "shorts support",
            "safe audio handling"
        ]
    }

# =========================================================
# STREAM
# =========================================================

@app.get("/stream")
async def stream(url: str, quality: str = "best"):

    url = fix_url(url)

    if not url:
        raise HTTPException(400, "Unsupported Facebook share link")

    if not validate(url):
        raise HTTPException(400, "Unsupported platform")

    data = await smart_extract(url)

    if not data:
        raise HTTPException(422, "Extraction failed")

    formats = get_formats(data)

    if not formats:
        raise HTTPException(404, "No stream available")

    selected = pick_best(formats, quality)

    return {
        "title": data.get("title"),
        "quality": selected["height"],
        "stream_url": selected["url"],
        "engine": "stable_v1"
    }

# =========================================================
# AUDIO (NO MORE 404 EVER)
# =========================================================

@app.get("/audio")
async def audio(url: str):

    url = fix_url(url)

    if not url:
        raise HTTPException(400, "Unsupported Facebook share link")

    data = await smart_extract(url)

    if not data:
        raise HTTPException(422, "Extraction failed")

    formats = get_formats(data)

    if not formats:
        raise HTTPException(404, "No media found")

    # 1. real audio-only
    audio_formats = [
        f for f in formats
        if f["acodec"] != "none" and f["vcodec"] == "none"
    ]

    # 2. fallback: any playable stream
    fallback = formats

    chosen = None

    if audio_formats:
        chosen = audio_formats[-1]
    elif fallback:
        chosen = fallback[-1]

    if not chosen:
        raise HTTPException(404, "No audio stream available")

    return {
        "title": data.get("title"),
        "audio_url": chosen["url"],
        "engine": "stable_v1"
    }

# =========================================================
# INFO
# =========================================================

@app.get("/info")
async def info(url: str):

    url = fix_url(url)

    if not url:
        raise HTTPException(400, "Invalid URL")

    data = await smart_extract(url)

    if not data:
        raise HTTPException(422, "Failed extraction")

    return {
        "title": data.get("title"),
        "duration": data.get("duration"),
        "thumbnail": data.get("thumbnail"),
        "engine": "stable_v1"
    }
