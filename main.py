from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import yt_dlp
import traceback

app = FastAPI(title="Verified Stable Media API")

# =========================
# CORS
# =========================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# SUPPORTED URLS
# =========================

SUPPORTED = ["youtube.com", "youtu.be"]

def is_supported(url: str):
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
# YT-DLP OPTIONS
# =========================

def ydl_opts(audio=False):
    return {
        "format": "bestaudio/best" if audio else "bv*+ba/best",
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
# ERROR RESPONSE
# =========================

def fail(msg):
    return JSONResponse({
        "status": "failed",
        "error": str(msg)
    })

# =========================
# SAFE EXTRACT
# =========================

def extract(url: str, audio=False):
    try:
        with yt_dlp.YoutubeDL(ydl_opts(audio=audio)) as ydl:
            data = ydl.extract_info(url, download=False)

        return data if isinstance(data, dict) else None

    except Exception:
        traceback.print_exc()
        return None

# =========================
# STREAM PICKER
# =========================

def pick_stream(data):
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
# STARTUP DEBUG (IMPORTANT)
# =========================

@app.on_event("startup")
def startup_check():
    print("\n==============================")
    print(" ROUTES LOADED INTO FASTAPI")
    print("==============================")
    for r in app.routes:
        print(r.path)
    print("==============================\n")

# =========================
# INFO ENDPOINT
# =========================

@app.get("/info")
def info(url: str):

    try:
        if not is_supported(url):
            return fail("unsupported url")

        url = clean_url(url)
        data = extract(url)

        if not data:
            return fail("yt-dlp failed or blocked")

        return {
            "status": "success",
            "title": data.get("title"),
            "duration": data.get("duration"),
            "thumbnail": data.get("thumbnail"),
            "uploader": data.get("uploader")
        }

    except Exception as e:
        return fail(e)

# =========================
# STREAM ENDPOINT
# =========================

@app.get("/stream")
def stream(url: str):

    try:
        if not is_supported(url):
            return fail("unsupported url")

        url = clean_url(url)
        data = extract(url)

        if not data:
            return fail("yt-dlp extraction failed")

        stream_url = pick_stream(data)

        if not stream_url:
            return fail("no stream found")

        return {
            "status": "success",
            "title": data.get("title"),
            "stream_url": stream_url
        }

    except Exception as e:
        return fail(e)

# =========================
# AUDIO ENDPOINT
# =========================

@app.get("/audio")
def audio(url: str):

    try:
        if not is_supported(url):
            return fail("unsupported url")

        url = clean_url(url)
        data = extract(url, audio=True)

        if not data:
            return fail("audio extraction failed")

        audio_url = pick_stream(data)

        if not audio_url:
            return fail("no audio found")

        return {
            "status": "success",
            "title": data.get("title"),
            "audio_url": audio_url
        }

    except Exception as e:
        return fail(e)

# =========================
# HEALTH
# =========================

@app.get("/health")
def health():
    return {"status": "ok"}
