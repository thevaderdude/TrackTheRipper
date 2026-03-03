"""
Spotify playlist → best-match YT/SC pipeline.
Fetches playlist tracks, scores candidates by views, title similarity, and length,
then downloads with ARTIST - TITLE filenames.
Uses user OAuth if available (run scripts/spotify_user_auth.py once), else client credentials.
Uses non-deprecated Get Playlist Items API. requests + Spotify Web API URLs (no spotipy).
"""
import base64
import json
import os
import re
import time
import difflib
from typing import Optional
from urllib.parse import urlparse

import requests

import dsp_secrets
import search
import download

# Spotify Web API endpoints (like cURL in the docs)
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"

# User auth: cache file (redirect URI is in spotify_user_auth.py)
_SPOTIFY_CACHE_PATH = os.path.join(os.path.dirname(__file__), ".spotify_oauth_cache")

# Scoring weights (tunable)
WEIGHT_VIEWS = 0.4
WEIGHT_TITLE = 0.4
WEIGHT_LENGTH = 0.2
# Minimum duration ratio: candidate must be at least this fraction of Spotify duration
MIN_DURATION_RATIO = 0.7

# Test playlist URLs (for tests)
PLAYLIST_URL_1 = "https://open.spotify.com/playlist/37i9dQZEVXd2ZWQqzKbAfl?si=26bf0aed73f04856"
PLAYLIST_URL_2 = "https://open.spotify.com/playlist/37i9dQZF1E8LQ8CR1hh5Oz?si=a9c8f73dff4941d4"

# Default user-owned playlist for testing (works with Get Playlist Items + user OAuth)
DEFAULT_USER_PLAYLIST_URL = "https://open.spotify.com/playlist/43KVtpxkc3rlkdyGZYCiQk?si=0b848c1afc2440c5"

# Fields to request from Get Playlist Items (track details for downstream: name, artists, duration, album)
# Non-deprecated endpoint uses "item" for the track object in the response
PLAYLIST_ITEMS_FIELDS = "total,limit,offset,items(added_at,item(name,duration_ms,artists(name),album(name)))"


def _track_from_playlist_item(entry: dict) -> Optional[dict]:
    """Get track object from a playlist item. Supports both 'item' (current) and 'track' (legacy) keys."""
    return entry.get("item") or entry.get("track")


def parse_playlist_id(url_or_id: str) -> Optional[str]:
    """
    Extract Spotify playlist ID from URL or return as-is if already an ID.
    Supports:
      - https://open.spotify.com/playlist/ID?si=...
      - spotify:playlist:ID
    """
    if not url_or_id or not isinstance(url_or_id, str):
        return None
    s = url_or_id.strip()
    # spotify:playlist:ID
    if s.startswith("spotify:playlist:"):
        return s.split(":", 2)[-1].split("?")[0] or None
    # URL
    if "open.spotify.com" in s or s.startswith("http"):
        parsed = urlparse(s)
        path = (parsed.path or "").strip("/")
        if path.startswith("playlist/"):
            return path.split("/", 1)[1].split("?")[0] or None
        # path might be "playlist/ID"
        parts = path.split("/")
        if len(parts) >= 2 and parts[0] == "playlist":
            return parts[1].split("?")[0] or None
    # Assume it's already an ID (alphanumeric)
    if re.match(r"^[\w-]+$", s):
        return s
    return None


def _request_client_credentials_token() -> str:
    """Get access token via Client Credentials flow. Raises on failure."""
    data = {"grant_type": "client_credentials"}
    auth = base64.b64encode(
        f"{dsp_secrets.spotify_client_id}:{dsp_secrets.spotify_client_secret}".encode()
    ).decode()
    r = requests.post(
        SPOTIFY_TOKEN_URL,
        data=data,
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _load_oauth_cache() -> Optional[dict]:
    """Load token info from .spotify_oauth_cache. Returns None if missing or invalid JSON."""
    if not os.path.isfile(_SPOTIFY_CACHE_PATH):
        return None
    try:
        with open(_SPOTIFY_CACHE_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return None


def _save_oauth_cache(token_info: dict) -> None:
    """Write token info to .spotify_oauth_cache."""
    with open(_SPOTIFY_CACHE_PATH, "w") as f:
        json.dump(token_info, f, indent=2)


def _refresh_user_token(refresh_token: str) -> dict:
    """Exchange refresh_token for new token_info. Raises on failure."""
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": dsp_secrets.spotify_client_id,
        "client_secret": dsp_secrets.spotify_client_secret,
    }
    r = requests.post(
        SPOTIFY_TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    r.raise_for_status()
    j = r.json()
    token_info = {
        "access_token": j["access_token"],
        "expires_in": j.get("expires_in", 3600),
    }
    if "refresh_token" in j:
        token_info["refresh_token"] = j["refresh_token"]
    token_info["expires_at"] = int(time.time()) + token_info["expires_in"]
    return token_info


def get_access_token(force_client_credentials: bool = False) -> Optional[str]:
    """
    Return an access token. Prefer user OAuth from .spotify_oauth_cache if present and valid,
    otherwise client credentials. Returns None only if both fail.
    Use force_client_credentials=True to skip user cache (e.g. for testing).
    """
    if not force_client_credentials:
        cached = _load_oauth_cache()
        if cached:
            try:
                refresh = cached.get("refresh_token")
                access = cached.get("access_token")
                expires_at = cached.get("expires_at", 0)
                if refresh and (not expires_at or time.time() >= expires_at - 60):
                    refreshed = _refresh_user_token(refresh)
                    if "refresh_token" not in refreshed and refresh:
                        refreshed["refresh_token"] = refresh
                    _save_oauth_cache(refreshed)
                    return refreshed["access_token"]
                if access and expires_at and time.time() < expires_at - 60:
                    return access
                if access and not expires_at:
                    return access
            except Exception:
                pass
    try:
        return _request_client_credentials_token()
    except Exception:
        return None


def get_client_credentials_token() -> Optional[str]:
    """Get app-only (client credentials) token. For testing or when user token is not used."""
    try:
        return _request_client_credentials_token()
    except Exception:
        return None


def request_playlist_tracks_page(
    playlist_id: str,
    access_token: str,
    limit: int = 50,
    offset: int = 0,
    market: str = "US",
    fields: Optional[str] = PLAYLIST_ITEMS_FIELDS,
) -> dict:
    """
    GET one page of playlist items (non-deprecated endpoint).
    Returns raw API response (items, total, next, ...). Each item has track with name, artists, duration_ms, album.
    Uses Authorization: Bearer <token>. Default fields request all track details needed for downstream.
    """
    url = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/items"
    params = {"limit": limit, "offset": offset, "market": market}
    if fields is not None:
        params["fields"] = fields
    r = requests.get(
        url,
        params=params,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def fetch_playlist_details(playlist_id: str) -> dict:
    """
    Fetch playlist metadata (name, cover image). Uses same token as other API calls.
    Returns dict with keys: name (str), image_url (str or None).
    Raises on 404/403 or missing token.
    """
    token = get_access_token()
    if not token:
        raise RuntimeError("Failed to get Spotify access token.")
    url = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}"
    r = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()
    name = (data.get("name") or "").strip() or "Untitled playlist"
    images = data.get("images") or []
    image_url = images[0].get("url") if images else None
    return {"name": name, "image_url": image_url}


def fetch_playlist_tracks(playlist_id: str):
    """
    Fetch all tracks from a Spotify playlist. Uses user OAuth if available,
    else client credentials. Returns list of dicts: name, artists (str), duration_ms.
    """
    token = get_access_token()
    if not token:
        raise RuntimeError("Failed to get Spotify access token (client credentials and user cache failed).")

    tracks = []
    offset = 0
    total = 1
    limit = 50  # API max per request
    while offset < total:
        resp = request_playlist_tracks_page(playlist_id, token, limit=limit, offset=offset, market="US")
        if offset == 0:
            total = resp.get("total", 0)
        for entry in resp.get("items", []):
            t = _track_from_playlist_item(entry)
            if t is None:
                continue
            name = (t.get("name") or "").strip()
            if not name:
                continue
            artists = ", ".join(a.get("name", "") for a in (t.get("artists") or []) if a.get("name"))
            duration_ms = t.get("duration_ms") or 0
            tracks.append({"name": name, "artists": artists, "duration_ms": duration_ms})
        offset += limit
    return tracks


def parse_yt_duration(duration_str: str) -> int:
    """
    Parse YouTube duration string to milliseconds.
    Supports "3:28", "1:23:45", "0:45".
    """
    if not duration_str or not isinstance(duration_str, str):
        return 0
    s = duration_str.strip()
    parts = [p.strip() for p in s.split(":") if p.strip().isdigit()]
    if not parts:
        return 0
    # seconds only
    if len(parts) == 1:
        return int(parts[0]) * 1000
    # M:SS
    if len(parts) == 2:
        return (int(parts[0]) * 60 + int(parts[1])) * 1000
    # H:MM:SS
    if len(parts) >= 3:
        return (int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])) * 1000
    return 0


def parse_yt_views(views_str: str) -> int:
    """
    Parse YouTube views string to integer.
    E.g. "216,105 views", "82,064,907 views", "1.2M views", "500K views".
    """
    if not views_str or not isinstance(views_str, str):
        return 0
    s = views_str.strip().lower().replace(" views", "").replace(" ", "").replace(",", "")
    if not s:
        return 0
    mult = 1
    if s.endswith("m"):
        mult = 1_000_000
        s = s[:-1]
    elif s.endswith("k"):
        mult = 1_000
        s = s[:-1]
    try:
        return int(float(s) * mult)
    except ValueError:
        return 0


def title_similarity(reference: str, candidate: str) -> float:
    """Return similarity in [0, 1] using SequenceMatcher on normalized strings."""
    if not reference and not candidate:
        return 1.0
    if not reference or not candidate:
        return 0.0
    a = reference.lower().strip()
    b = candidate.lower().strip()
    return difflib.SequenceMatcher(None, a, b).ratio()


def length_score(candidate_ms: int, spotify_ms: int) -> float:
    """
    Score by length: prefer >= Spotify length, slight bonus for longer (extended).
    Penalize if much shorter. Returns roughly in [0, 1].
    """
    if spotify_ms <= 0:
        return 1.0
    ratio = candidate_ms / spotify_ms
    if ratio < MIN_DURATION_RATIO:
        return max(0.0, ratio / MIN_DURATION_RATIO) * 0.5  # heavy penalty
    if ratio >= 1.0:
        # Same or longer: full score + small bonus for extended
        return min(1.0, 0.95 + 0.05 * min(ratio - 1.0, 1.0))  # cap bonus
    # Between MIN and 1: linear ramp
    return 0.7 + 0.25 * (ratio - MIN_DURATION_RATIO) / (1.0 - MIN_DURATION_RATIO)


def _normalize_view_score(views: int, max_views: int) -> float:
    """Log-scale normalize views to [0, 1] when max_views > 0."""
    if max_views <= 0 or views <= 0:
        return 0.0
    import math
    log_max = math.log1p(max_views)
    log_v = math.log1p(views)
    return log_v / log_max if log_max > 0 else 0.0


def pick_best_candidate(
    spotify_track: dict,
    yt_results: list,
    sc_results: list,
    weight_views: float = WEIGHT_VIEWS,
    weight_title: float = WEIGHT_TITLE,
    weight_length: float = WEIGHT_LENGTH,
):
    """
    From YT and SC search results, pick the best candidate for this Spotify track.
    Returns dict with keys: url, type ('yt'|'sc'), artist, title; or None if no candidates.
    """
    name = spotify_track.get("name") or ""
    artists = spotify_track.get("artists") or ""
    duration_ms = spotify_track.get("duration_ms") or 0
    reference_str = f"{artists} - {name}"

    candidates = []
    # YT
    for r in yt_results or []:
        if not r:
            continue
        title = (r.get("title") or "").strip()
        channel = (r.get("channel") or "").strip()
        url = r.get("url") or ""
        if not url:
            continue
        dur_ms = parse_yt_duration(r.get("duration") or "")
        views = parse_yt_views(r.get("views") or "")
        candidates.append({
            "type": "yt",
            "url": url,
            "artist": channel,
            "title": title,
            "duration_ms": dur_ms,
            "views": views,
        })
    # SC
    for r in sc_results or []:
        if not r:
            continue
        title = (r.get("title") or "").strip()
        artist = (r.get("artist") or "").strip() or (r.get("username") or "").strip()
        link = r.get("link") or ""
        if not link:
            continue
        dur_ms = r.get("duration_ms") or r.get("duration") or 0
        if isinstance(dur_ms, str):
            dur_ms = 0
        plays = r.get("plays") or r.get("playback_count") or 0
        if isinstance(plays, str):
            plays = parse_yt_views(plays.replace(",", ""))
        candidates.append({
            "type": "sc",
            "url": link,
            "artist": artist,
            "title": title,
            "duration_ms": int(dur_ms),
            "views": int(plays),
        })

    if not candidates:
        return None

    max_views = max(c.get("views", 0) or 0 for c in candidates)
    for c in candidates:
        view_score = _normalize_view_score(c.get("views") or 0, max_views) if max_views else 0
        title_score = title_similarity(reference_str, c.get("title") or "")
        length_score_val = length_score(c.get("duration_ms") or 0, duration_ms)
        c["_view_score"] = view_score
        c["_title_score"] = title_score
        c["_length_score"] = length_score_val
        c["_total"] = (
            weight_views * view_score +
            weight_title * title_score +
            weight_length * length_score_val
        )

    best = max(candidates, key=lambda c: c["_total"])
    return {
        "url": best["url"],
        "type": best["type"],
        "artist": best["artist"],
        "title": best["title"],
    }


def _get_sorted_candidates(
    spotify_track: dict,
    yt_results: list,
    sc_results: list,
    top_n: int = 5,
    weight_views: float = WEIGHT_VIEWS,
    weight_title: float = WEIGHT_TITLE,
    weight_length: float = WEIGHT_LENGTH,
) -> list:
    """
    Return up to top_n candidates sorted by score (best first), each with keys url, type, artist, title.
    Used to try multiple candidates when the first download fails (e.g. 403).
    """
    name = spotify_track.get("name") or ""
    artists = spotify_track.get("artists") or ""
    duration_ms = spotify_track.get("duration_ms") or 0
    reference_str = f"{artists} - {name}"

    candidates = []
    for r in yt_results or []:
        if not r:
            continue
        title = (r.get("title") or "").strip()
        channel = (r.get("channel") or "").strip()
        url = r.get("url") or ""
        if not url:
            continue
        dur_ms = parse_yt_duration(r.get("duration") or "")
        views = parse_yt_views(r.get("views") or "")
        candidates.append({
            "type": "yt",
            "url": url,
            "artist": channel,
            "title": title,
            "duration_ms": dur_ms,
            "views": views,
        })
    for r in sc_results or []:
        if not r:
            continue
        title = (r.get("title") or "").strip()
        artist = (r.get("artist") or "").strip() or (r.get("username") or "").strip()
        link = r.get("link") or ""
        if not link:
            continue
        dur_ms = r.get("duration_ms") or r.get("duration") or 0
        if isinstance(dur_ms, str):
            dur_ms = 0
        plays = r.get("plays") or r.get("playback_count") or 0
        if isinstance(plays, str):
            plays = parse_yt_views(plays.replace(",", ""))
        candidates.append({
            "type": "sc",
            "url": link,
            "artist": artist,
            "title": title,
            "duration_ms": int(dur_ms),
            "views": int(plays),
        })

    if not candidates:
        return []

    max_views = max(c.get("views", 0) or 0 for c in candidates)
    for c in candidates:
        view_score = _normalize_view_score(c.get("views") or 0, max_views) if max_views else 0
        title_score = title_similarity(reference_str, c.get("title") or "")
        length_score_val = length_score(c.get("duration_ms") or 0, duration_ms)
        c["_total"] = (
            weight_views * view_score +
            weight_title * title_score +
            weight_length * length_score_val
        )
    sorted_candidates = sorted(candidates, key=lambda c: c["_total"], reverse=True)
    return [
        {"url": c["url"], "type": c["type"], "artist": c["artist"], "title": c["title"]}
        for c in sorted_candidates[:top_n]
    ]


def _run_download_loop(tracks, output_dir, retries_per_track):
    """
    Shared loop: for each track find best YT/SC candidate and download.
    Returns list of dicts: track_name, status ('ok'|'error'), path?, error?,
    source_type? ('yt'|'sc'), source_url?, source_title?.
    """
    results = []
    for i, st in enumerate(tracks):
        name = st.get("name", "?")
        artists = st.get("artists", "")
        display = f"{artists} - {name}" if artists else name
        last_error = None
        downloaded = False
        for attempt in range(max(1, retries_per_track)):
            if downloaded:
                break
            yt_list = search.search_youtube(f"{artists} - {name}", limit=8)
            sc_list = search.search_soundcloud(f"{artists} - {name}", limit=8)
            if not isinstance(yt_list, list):
                yt_list = []
            if not isinstance(sc_list, list):
                sc_list = []

            # Try up to 5 candidates (best first); when one fails (e.g. 403) try the next
            candidates = _get_sorted_candidates(st, yt_list, sc_list, top_n=5)
            if not candidates:
                last_error = "No search results"
                time.sleep(1 + attempt)
                continue

            for best in candidates:
                try:
                    source_title = f"{best.get('artist', '')} - {best.get('title', '')}".strip() or best.get("title", "") or ""
                    if best["type"] == "yt":
                        path = download.download_yt(
                            best["url"],
                            output_dir,
                            format="mp3",
                            artist=best["artist"],
                            title=best["title"],
                        )
                    else:
                        path = download.download_sc(best["url"], output_dir)
                    results.append({
                        "track_name": display,
                        "status": "ok",
                        "path": path,
                        "source_type": best["type"],
                        "source_url": best["url"],
                        "source_title": source_title or None,
                    })
                    downloaded = True
                    break
                except Exception as e:
                    last_error = str(e)
                    time.sleep(0.5)  # brief pause before trying next candidate
            if downloaded:
                break
            time.sleep(1 + attempt)
        if not downloaded:
            results.append({
                "track_name": display,
                "status": "error",
                "error": last_error or "No search results",
                "source_type": None,
                "source_url": None,
                "source_title": None,
            })
        time.sleep(0.3)  # rate limit between tracks
    return results


def run_pipeline_from_tracks(
    tracks: list,
    output_dir: str,
    retries_per_track: int = 2,
):
    """
    Run the download pipeline from a list of tracks (each dict: name, artists, duration_ms).
    Use when Spotify API is unavailable; e.g. load tracks from a JSON file.
    """
    return _run_download_loop(tracks, output_dir, retries_per_track)


def run_pipeline(
    playlist_url: str,
    output_dir: str,
    track_limit: Optional[int] = None,
    retries_per_track: int = 2,
):
    """
    Full pipeline: fetch playlist, for each track find best YT/SC candidate and download.
    Returns list of per-track results: {track_name, status, path?, error?, source_type?, source_url?, source_title?}.
    """
    playlist_id = parse_playlist_id(playlist_url)
    if not playlist_id:
        return [{"track_name": "", "status": "error", "error": "Invalid playlist URL"}]

    try:
        tracks = fetch_playlist_tracks(playlist_id)
    except Exception as e:
        err_msg = str(e)
        if "404" in err_msg or "Resource not found" in err_msg:
            return [{"track_name": "", "status": "error", "error": "Playlist not found (404). It may be private or deleted."}]
        if "403" in err_msg or "Forbidden" in err_msg:
            return [{"track_name": "", "status": "error", "error": "Spotify API 403 Forbidden. Check app credentials and that the playlist is public, or add your Spotify user in the Developer Dashboard if the app is in Development Mode."}]
        return [{"track_name": "", "status": "error", "error": f"Spotify API error: {err_msg}"}]
    if track_limit is not None and track_limit > 0:
        tracks = tracks[:track_limit]
    return _run_download_loop(tracks, output_dir, retries_per_track)
