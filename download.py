import os
import re
import time
import yt_dlp
import dsp_secrets

# Use project-local cache dir (avoid .cache which may exist as a file in this repo)
_YT_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ytdlp_cache")

try:
    from sclib import SoundcloudAPI, Track, Playlist
    _sc_api = SoundcloudAPI(client_id=dsp_secrets.sc_client_id)
except ImportError:
    _sc_api = None
    Track = None  # type: ignore

DOWNLOAD_RETRIES = 3
DOWNLOAD_BACKOFF = 2.0

# Characters invalid in filenames (Windows + Unix)
_FILENAME_UNSAFE_RE = re.compile(r'[/\\:*?"<>|]')
_MAX_FILENAME_LEN = 200


def sanitize_filename_part(part: str, max_len: int = 100) -> str:
    """Replace invalid filesystem characters and optionally truncate."""
    if not part or not isinstance(part, str):
        return "Unknown"
    s = _FILENAME_UNSAFE_RE.sub("_", part).strip() or "Unknown"
    if len(s) > max_len:
        s = s[:max_len].rstrip()
    return s


def download_yt(url, filepath, format='wav', artist=None, title=None):
    URLS = [url]
    custom_basename = None
    if artist is not None and title is not None:
        safe_artist = sanitize_filename_part(artist)
        safe_title = sanitize_filename_part(title)
        combined = f"{safe_artist} - {safe_title}"
        if len(combined) > _MAX_FILENAME_LEN:
            safe_title = sanitize_filename_part(title, max_len=_MAX_FILENAME_LEN - len(safe_artist) - 3)
            combined = f"{safe_artist} - {safe_title}"
        custom_basename = combined
    os.makedirs(_YT_CACHE_DIR, exist_ok=True)
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': format,
        }],
        'paths': {'home': filepath},
        'cachedir': _YT_CACHE_DIR,
        # Try alternative YouTube clients to reduce 403 Forbidden
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
    }
    if custom_basename:
        # outtmpl is relative to paths.home, so use basename only to avoid path duplication
        ydl_opts['outtmpl'] = {'default': f'{custom_basename}.%(ext)s'}

    last_error = None
    for attempt in range(DOWNLOAD_RETRIES):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                ydl.download(URLS)
                if custom_basename:
                    file_path = f'{filepath}/{custom_basename}.{format}'
                else:
                    file_path = ydl.prepare_filename(info)
                    if file_path and not file_path.endswith(f'.{format}'):
                        file_path = file_path.rsplit('.', 1)[0] + f'.{format}'
                print(file_path)
            return file_path
        except Exception as e:
            last_error = e
            if attempt < DOWNLOAD_RETRIES - 1:
                time.sleep(DOWNLOAD_BACKOFF * (attempt + 1))
    raise last_error


def download_sc(url, filepath):
    if _sc_api is None:
        raise RuntimeError(
            "SoundCloud support not installed. Install with: pip install soundcloud-lib"
        )
    last_error = None
    for attempt in range(DOWNLOAD_RETRIES):
        try:
            track = _sc_api.resolve(url)
            if type(track) is not Track:
                raise TypeError(f"Expected Track, got {type(track)}")
            safe_artist = sanitize_filename_part(track.artist)
            safe_title = sanitize_filename_part(track.title)
            combined = f"{safe_artist} - {safe_title}"
            if len(combined) > _MAX_FILENAME_LEN:
                safe_title = sanitize_filename_part(track.title, max_len=_MAX_FILENAME_LEN - len(safe_artist) - 3)
                combined = f"{safe_artist} - {safe_title}"
            filename = f'{filepath}/{combined}.mp3'
            with open(filename, 'wb+') as file:
                track.write_mp3_to(file)
            print(f'{filename} downloaded')
            return filename
        except Exception as e:
            last_error = e
            if attempt < DOWNLOAD_RETRIES - 1:
                time.sleep(DOWNLOAD_BACKOFF * (attempt + 1))
    raise last_error