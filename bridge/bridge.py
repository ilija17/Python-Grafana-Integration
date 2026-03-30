import os
import time
import threading
import requests
from flask import Flask, jsonify
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.environ["SPOTIFY_CLIENT_ID"]
CLIENT_SECRET = os.environ["SPOTIFY_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["SPOTIFY_REFRESH_TOKEN"]
HOST = os.environ.get("BRIDGE_HOST", "0.0.0.0")
PORT = int(os.environ.get("BRIDGE_PORT", "5005"))

TOKEN_URL = "https://accounts.spotify.com/api/token"
NOW_PLAYING_URL = "https://api.spotify.com/v1/me/player/currently-playing"

app = Flask(__name__)

token_lock = threading.Lock()
access_token = None
token_expires_at = 0


def refresh_access_token():
    global access_token, token_expires_at

    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": REFRESH_TOKEN,
        },
        auth=(CLIENT_ID, CLIENT_SECRET),
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    with token_lock:
        access_token = data["access_token"]
        token_expires_at = time.time() + data["expires_in"] - 60

    print(f"[token] Refreshed, expires in {data['expires_in']}s")


def get_access_token():
    global access_token, token_expires_at
    if time.time() >= token_expires_at:
        refresh_access_token()
    return access_token


def fetch_now_playing():
    token = get_access_token()
    resp = requests.get(
        NOW_PLAYING_URL,
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )

    if resp.status_code == 204 or resp.status_code == 202:
        return {"is_playing": False}

    if resp.status_code == 401:
        refresh_access_token()
        return {"is_playing": False, "error": "token_refreshed"}

    if resp.status_code != 200:
        return {"is_playing": False, "error": f"spotify_http_{resp.status_code}"}

    data = resp.json()

    if not data.get("is_playing") or not data.get("item"):
        return {"is_playing": False}

    item = data["item"]

    if item["type"] == "track":
        artists = ", ".join(a["name"] for a in item.get("artists", []))
        album = item.get("album", {})
        album_name = album.get("name", "")

        # Get largest album art
        images = album.get("images", [])
        album_art = images[0]["url"] if images else ""

        return {
            "is_playing": True,
            "type": "track",
            "track": item["name"],
            "artist": artists,
            "album": album_name,
            "album_art": album_art,
            "duration_ms": item.get("duration_ms", 0),
            "progress_ms": data.get("progress_ms", 0),
            "track_url": item.get("external_urls", {}).get("spotify", ""),
        }
    elif item["type"] == "episode":
        show = item.get("show", {})
        images = item.get("images", []) or show.get("images", [])
        cover_art = images[0]["url"] if images else ""

        return {
            "is_playing": True,
            "type": "episode",
            "track": item["name"],
            "artist": show.get("name", "Podcast"),
            "album": show.get("name", ""),
            "album_art": cover_art,
            "duration_ms": item.get("duration_ms", 0),
            "progress_ms": data.get("progress_ms", 0),
            "track_url": item.get("external_urls", {}).get("spotify", ""),
        }

    return {"is_playing": False}


cache = {"data": {"is_playing": False}, "fetched_at": 0}
CACHE_TTL = 5  # seconds


def get_cached_now_playing():
    now = time.time()
    if now - cache["fetched_at"] > CACHE_TTL:
        try:
            cache["data"] = fetch_now_playing()
        except Exception as e:
            print(f"[error] Spotify fetch failed: {e}")
            cache["data"] = {"is_playing": False, "error": str(e)}
        cache["fetched_at"] = now
    return cache["data"]


@app.route("/now-playing")
def now_playing():
    data = get_cached_now_playing()
    resp = jsonify(data)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@app.route("/health")
def health():
    return jsonify({"status": "ok", "cache_age": time.time() - cache["fetched_at"]})


if __name__ == "__main__":
    print(f"[startup] Refreshing Spotify token...")
    refresh_access_token()
    print(f"[startup] Bridge running on {HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=False)