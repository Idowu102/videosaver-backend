from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import asyncio
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

# =========================
# APP
# =========================

app = FastAPI(title="Production Media Gateway API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

executor = ThreadPoolExecutor(max_workers=6)

# =========================
# OPTIONAL REDIS CACHE
# =========================

try:
    import redis
    r = redis.Redis(host="localhost", port=6379, decode_responses=True)
    REDIS = True
except:
    REDIS = False
    r = None


def cache_get(key):
    if REDIS:
        return r.get(key)
    return None


def cache_set(key, value, ttl=3600):
    if REDIS:
        r.setex(key, ttl, value)


def make_key(*args):
    return hashlib.md5("|".join(args).encode()).hexdigest()


# =========================
# URL FIXER
# =========================

def fix_url(url: str):

    url = url.strip()

    # YouTube Shorts → Watch
    if "youtube.com/shorts/" in url:
        vid = url.split("/shorts/")[1].split("?")[0]
        return f"https://www.youtube.com/watch?v={vid}"

    # Block bad Facebook share links
    if "facebook.com/share" in url:
        return None

    return url


def validate_url(url: str):

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


# =========================
# YT-DLP CONFIG
# =========================

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
                "player_client": ["android", "web"]
            }
        }
    }


# =========================
# ASYNC WRAPPER
# =========================

def _extract(url):
    try:
        with yt_dlp.YoutubeDL(ydl_opts()) as ydl:
            return ydl.extract_info(url, download=False)
    except Exception as e:
        return {"error": str(e)}


async def extract(url):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _extract, url)


# =========================
# FORMAT ENGINE
# =========================

def parse_formats(data):

    if not isinstance(data, dict):
        return []

    formats = data.get("formats") or []

    out = []

    for f in formats:
        if not f.get("url"):
            continue

        out.append({
            "id": f.get("format_id"),
            "ext": f.get("ext"),
            "height": f.get("height") or 0,
            "url": f.get("url")
        })

    return sorted(out, key=lambda x: x["height"])


def choose_quality(formats, quality):

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


# =========================
# ROOT
# =========================

@app.get("/")
def root():
    return {
        "status": "production_gateway_online",
        "cache": REDIS
    }


# =========================
# INFO
# =========================

@app.get("/info")
async def info(url: str):

    url = fix_url(url)

    if not url:
        raise HTTPException(400, "Invalid Facebook share link")

    if not validate_url(url):
        raise HTTPException(400, "Unsupported platform")

    key = make_key("info", url)
    cached = cache_get(key)

    if cached:
        return json.loads(cached)

    data = await extract(url)

    if not isinstance(data, dict) or "error" in data:
        raise HTTPException(422, "Media unavailable")

    result = {
        "title": data.get("title"),
        "duration": data.get("duration"),
        "thumbnail": data.get("thumbnail")
    }

    cache_set(key, json.dumps(result))
    return result


# =========================
# FORMATS
# =========================

@app.get("/formats")
async def formats(url: str):

    url = fix_url(url)

    if not url:
        raise HTTPException(400, "Invalid URL")

    data = await extract(url)

    if not isinstance(data, dict):
        raise HTTPException(422, "Failed extraction")

    return {
        "title": data.get("title"),
        "formats": parse_formats(data)
    }


# =========================
# STREAM
# =========================

@app.get("/stream")
async def stream(url: str, quality: str = "best"):

    url = fix_url(url)

    if not url:
        raise HTTPException(400, "Invalid Facebook share link")

    key = make_key(url, quality)
    cached = cache_get(key)

    if cached:
        return json.loads(cached)

    data = await extract(url)

    if not isinstance(data, dict) or "error" in data:
        raise HTTPException(422, "Media unavailable")

    formats = parse_formats(data)
    selected = choose_quality(formats, quality)

    if not selected:
        raise HTTPException(404, "No stream found")

    result = {
        "title": data.get("title"),
        "quality": selected["height"],
        "stream_url": selected["url"]
    }

    cache_set(key, json.dumps(result))
    return result


# =========================
# AUDIO
# =========================

@app.get("/audio")
async def audio(url: str):

    url = fix_url(url)

    if not url:
        raise HTTPException(400, "Invalid link")

    data = await extract(url)

    if not isinstance(data, dict):
        raise HTTPException(422, "Failed extraction")

    formats = parse_formats(data)

    for f in formats:
        if f["ext"] in ["m4a", "mp3", "webm"]:
            return {
                "title": data.get("title"),
                "audio_url": f["url"]
            }

    raise HTTPException(404, "No audio found")
