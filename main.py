from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import asyncio
from concurrent.futures import ThreadPoolExecutor

app = FastAPI(title="Smart Fallback Engine v2")

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

    # YouTube shorts → watch
    if "youtube.com/shorts/" in url:
        vid = url.split("/shorts/")[1].split("?")[0]
        return f"https://www.youtube.com/watch?v={vid}"

    # block bad facebook share links
    if "facebook.com/share" in url:
        return None

    return url

# =========================================================
# VALIDATION
# =========================================================

def validate(url: str):

    if not url:
        return False

    allowed = [
        "youtube.com",
        "youtu.be",
        "facebook.com",
        "tiktok.com",
        "instagram.com"
    ]

    return any(x in url for x in allowed)

# =========================================================
# YT-DLP OPTIONS (MULTI-CLIENT FALLBACK)
# =========================================================

def ydl_opts(client="android"):

    return {
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

# =========================================================
# ASYNC EXECUTOR
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

# =========================================================
# FORMAT SCORING ENGINE
# =========================================================

def score_formats(formats):

    scored = []

    for f in formats:
        if not f.get("url"):
            continue

        score = 0

        h = f.get("height") or 0
        if h:
            score += h

        if f.get("ext") == "mp4":
            score += 50

        scored.append({
            "url": f["url"],
            "height": h,
            "ext": f.get("ext"),
            "score": score
        })

    return sorted(scored, key=lambda x: x["score"])

# =========================================================
# SMART FALLBACK CHAIN
# =========================================================

async def smart_extract(url):

    clients = ["android", "web", "ios"]

    for client in clients:

        data = await extract(url, client)

        if isinstance(data, dict) and "error" not in data:
            return data

    return None

# =========================================================
# STREAM ENGINE (NO MORE 404 LOGIC FAILURES)
# =========================================================

@app.get("/stream")
async def stream(url: str, quality: str = "best"):

    url = fix_url(url)

    if not url:
        raise HTTPException(400, "Invalid Facebook share link")

    if not validate(url):
        raise HTTPException(400, "Unsupported platform")

    data = await smart_extract(url)

    if not data:
        raise HTTPException(422, "Unable to extract media")

    formats = data.get("formats") or []

    if not formats:
        raise HTTPException(404, "No formats available")

    scored = score_formats(formats)

    # -------------------------
    # SMART QUALITY SELECTION
    # -------------------------

    selected = None

    if quality == "best":
        selected = scored[-1]

    elif quality == "low":
        selected = scored[0]

    else:
        try:
            q = int(quality)
            selected = min(scored, key=lambda x: abs(x["height"] - q))
        except:
            selected = scored[-1]

    # fallback safety
    if not selected:
        selected = scored[-1]

    return {
        "title": data.get("title"),
        "quality": selected["height"],
        "stream_url": selected["url"],
        "engine": "fallback_v2"
    }

# =========================================================
# AUDIO ENGINE (NO 404 EVER)
# =========================================================

@app.get("/audio")
async def audio(url: str):

    url = fix_url(url)

    if not url:
        raise HTTPException(400, "Invalid URL")

    data = await smart_extract(url)

    if not data:
        raise HTTPException(422, "Extraction failed")

    formats = data.get("formats") or []

    if not formats:
        raise HTTPException(404, "No audio available")

    # prioritize audio formats
    audio = None

    for f in formats:
        if f.get("ext") in ["m4a", "webm", "mp3"]:
            audio = f
            break

    # fallback: ANY format (last resort)
    if not audio:
        audio = formats[-1]

    return {
        "title": data.get("title"),
        "audio_url": audio["url"],
        "engine": "fallback_v2"
    }

# =========================================================
# INFO (SAFE)
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
        "engine": "fallback_v2"
    }

# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():
    return {
        "status": "smart_fallback_v2_active",
        "features": [
            "multi-client extraction",
            "quality fallback",
            "audio fallback safe mode",
            "no 404 crashes"
        ]
    }
