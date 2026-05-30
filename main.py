from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import yt_dlp
import traceback
import redis
import json
import hashlib

# =========================
# APP
# =========================

app = FastAPI(title="Resilient Media API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# REDIS (CACHE LAYER)
# =========================

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

CACHE_TTL = 3600 * 24  # 24 hours

# =========================
# SUPPORTED
# =========================

SUPPORTED = ["youtube.com", "youtu.be"]

def supported(url):
    return any(x in url for x in SUPPORTED)

# =========================
# CACHE KEY
# =========================

def key(url):
    return hashlib.md5(url.encode()).hexdigest()

# =========================
# CLEAN URL
# =========================

def clean(url):
    if "youtube.com/shorts/" in url:
        vid = url.split("/shorts/")[1].split("?")[0]
        return f"https://www.youtube.com/watch?v={vid}"
    return url

# =========================
# CACHE HELPERS
# =========================

def get_cache(k):
    v = r.get(k)
    return json.loads(v) if v else None

def set_cache(k, v):
    r.setex(k, CACHE_TTL, json.dumps(v))

# =========================
# YT-DLP OPTIONS (SAFE)
# =========================

def opts():
    return {
        "format": "bv*+ba/best",
        "noplaylist": True,
        "quiet": True,
        "retries": 2,
        "fragment_retries": 2,
        "socket_timeout": 20,
        "ignoreerrors": False,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        }
    }

# =========================
# SAFE EXTRACT
# =========================

def extract(url):
    try:
        with yt_dlp.YoutubeDL(opts()) as ydl:
            data = ydl.extract_info(url, download=False)

        if not isinstance(data, dict):
            return None

        return data

    except yt_dlp.utils.DownloadError as e:
        return {"error": "blocked_by_youtube", "detail": str(e)}

    except Exception as e:
        return {"error": "network_or_unknown", "detail": str(e)}

# =========================
# STREAM PICK
# =========================

def pick(data):
    if not isinstance(data, dict):
        return None

    formats = data.get("formats")

    if not formats:
        return data.get("url")

    for f in reversed(formats):
        if f and f.get("url"):
            return f["url"]

    return None

# =========================
# INFO
# =========================

@app.get("/info")
def info(url: str):

    if not supported(url):
        return JSONResponse({"status": "failed", "error": "unsupported"})

    url = clean(url)
    k = key("info:" + url)

    cached = get_cache(k)
    if cached:
        return {"status": "cached", "data": cached}

    data = extract(url)

    if isinstance(data, dict) and "error" in data:
        set_cache(k, data)
        return JSONResponse({"status": "failed", **data})

    if not data:
        return JSONResponse({"status": "failed", "error": "extract_failed"})

    result = {
        "title": data.get("title"),
        "duration": data.get("duration"),
        "thumbnail": data.get("thumbnail")
    }

    set_cache(k, result)

    return {"status": "success", "data": result}

# =========================
# STREAM
# =========================

@app.get("/stream")
def stream(url: str):

    if not supported(url):
        return JSONResponse({"status": "failed", "error": "unsupported"})

    url = clean(url)
    k = key("stream:" + url)

    cached = get_cache(k)
    if cached:
        return {"status": "cached", "stream": cached}

    data = extract(url)

    if isinstance(data, dict) and "error" in data:
        set_cache(k, data)
        return JSONResponse({"status": "failed", **data})

    stream_url = pick(data)

    if not stream_url:
        return JSONResponse({"status": "failed", "error": "no_stream_found"})

    set_cache(k, stream_url)

    return {
        "status": "success",
        "stream": stream_url,
        "title": data.get("title")
    }

# =========================
# AUDIO
# =========================

@app.get("/audio")
def audio(url: str):

    if not supported(url):
        return JSONResponse({"status": "failed", "error": "unsupported"})

    url = clean(url)
    k = key("audio:" + url)

    cached = get_cache(k)
    if cached:
        return {"status": "cached", "audio": cached}

    data = extract(url)

    if isinstance(data, dict) and "error" in data:
        set_cache(k, data)
        return JSONResponse({"status": "failed", **data})

    audio_url = pick(data)

    if not audio_url:
        return JSONResponse({"status": "failed", "error": "no_audio_found"})

    set_cache(k, audio_url)

    return {
        "status": "success",
        "audio": audio_url,
        "title": data.get("title")
    }

# =========================
# HEALTH
# =========================

@app.get("/health")
def health():
    return {"status": "ok"}
