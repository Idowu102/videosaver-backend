from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import yt_dlp
import traceback

app = FastAPI(title="Stable Media API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# SUPPORT CHECK
# =========================

SUPPORTED = ["youtube.com", "youtu.be"]

def supported(url: str):
    return any(x in url for x in SUPPORTED)

# =========================
# CLEAN URL
# =========================

def clean_url(url: str):
    url = url.strip()

    if "youtube.com/shorts/" in url:
        vid = url.split("/shorts/")[1].split("?")[0]
        return f"https://www.youtube.com/watch?v={vid}"

    return url

# =========================
# SAFE YT-DLP OPTIONS
# =========================

def ydl_opts():
    return {
        "format": "bv*+ba/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "fragment_retries": 3,
        "socket_timeout": 30,
        "ignoreerrors": False,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        },
        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        }
    }

# =========================
# SAFE RESPONSE
# =========================

def fail(msg):
    return JSONResponse({
        "status": "failed",
        "error": str(msg)
    })

# =========================
# EXTRACT SAFE
# =========================

def extract(url: str):
    try:
        with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
            data = ydl.extract_info(url, download=False)

        return data if isinstance(data, dict) else None

    except Exception as e:
        return {"error": str(e)}

# =========================
# STREAM PICKER
# =========================

def get_stream(data):
    if not isinstance(data, dict):
        return None

    formats = data.get("formats")

    if not formats:
        return data.get("url")

    for f in reversed(formats):
        if isinstance(f, dict) and f.get("url"):
            return f["url"]

    return None

# =========================
# INFO
# =========================

@app.get("/info")
def info(url: str):

    try:
        if not supported(url):
            return fail("unsupported url")

        url = clean_url(url)
        data = extract(url)

        if not data or "error" in data:
            return fail("extract failed or blocked")

        return {
            "status": "success",
            "title": data.get("title"),
            "duration": data.get("duration"),
            "thumbnail": data.get("thumbnail")
        }

    except Exception as e:
        traceback.print_exc()
        return fail(e)

# =========================
# STREAM
# =========================

@app.get("/stream")
def stream(url: str):

    try:
        if not supported(url):
            return fail("unsupported url")

        url = clean_url(url)
        data = extract(url)

        if not data or "error" in data:
            return fail("extract failed or blocked by youtube")

        stream_url = get_stream(data)

        if not stream_url:
            return fail("no stream found")

        return {
            "status": "success",
            "title": data.get("title"),
            "stream_url": stream_url
        }

    except Exception as e:
        traceback.print_exc()
        return fail(e)

# =========================
# AUDIO
# =========================

@app.get("/audio")
def audio(url: str):

    try:
        if not supported(url):
            return fail("unsupported url")

        url = clean_url(url)

        # audio mode
        opts = ydl_opts()
        opts["format"] = "bestaudio/best"

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                data = ydl.extract_info(url, download=False)
        except Exception as e:
            return fail(str(e))

        if not data or "error" in data:
            return fail("audio extract failed")

        audio_url = get_stream(data)

        if not audio_url:
            return fail("no audio found")

        return {
            "status": "success",
            "title": data.get("title"),
            "audio_url": audio_url
        }

    except Exception as e:
        traceback.print_exc()
        return fail(e)

# =========================
# HEALTH CHECK
# =========================

@app.get("/health")
def health():
    return {"status": "ok"}
