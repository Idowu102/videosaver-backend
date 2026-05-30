from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import yt_dlp
import traceback

app = FastAPI(title="DEBUG MEDIA API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPPORTED = ["youtube.com", "youtu.be"]

def ok_routes():
    print("\n===== ROUTES LOADED =====")
    for r in app.routes:
        print(r.path)
    print("========================\n")

@app.on_event("startup")
def startup():
    ok_routes()

def fail(msg):
    return JSONResponse({"status": "failed", "error": str(msg)})

def safe_extract(url, audio=False):
    try:
        opts = {
            "format": "bestaudio/best" if audio else "bv*+ba/best",
            "noplaylist": True,
            "quiet": True,
            "retries": 3,
            "fragment_retries": 3,
        }

        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info(url, download=False)

        return data if isinstance(data, dict) else None

    except Exception:
        traceback.print_exc()
        return None

def clean(url):
    if "youtube.com/shorts/" in url:
        vid = url.split("/shorts/")[1].split("?")[0]
        return f"https://www.youtube.com/watch?v={vid}"
    return url

# =========================
# STREAM
# =========================
@app.get("/stream")
def stream(url: str):

    try:
        url = clean(url)

        data = safe_extract(url, audio=False)

        if not data:
            return fail("stream extraction failed")

        return {
            "status": "success",
            "title": data.get("title"),
            "stream_url": data.get("url")
        }

    except Exception as e:
        return fail(e)

# =========================
# AUDIO  (THIS IS WHAT WAS MISSING)
# =========================
@app.get("/audio")
def audio(url: str):

    try:
        url = clean(url)

        data = safe_extract(url, audio=True)

        if not data:
            return fail("audio extraction failed")

        return {
            "status": "success",
            "title": data.get("title"),
            "audio_url": data.get("url")
        }

    except Exception as e:
        return fail(e)

# =========================
# INFO
# =========================
@app.get("/info")
def info(url: str):

    try:
        url = clean(url)

        data = safe_extract(url)

        if not data:
            return fail("info extraction failed")

        return {
            "status": "success",
            "title": data.get("title"),
            "duration": data.get("duration")
        }

    except Exception as e:
        return fail(e)
