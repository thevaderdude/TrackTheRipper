#!/usr/bin/env python3
"""
One-time Spotify user login (Authorization Code flow).
Saves a refresh token so the app can read your playlists without logging in again.

Before running:
  1. In Spotify Developer Dashboard → your app → "Redirect URIs", add:
     http://127.0.0.1:8080/callback
  2. Ensure your Spotify account is in the app's "User management" (Development Mode).

Run from project root: python scripts/spotify_user_auth.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dsp_secrets

# Must match the URI you add in the Spotify Dashboard
SPOTIFY_REDIRECT_URI = getattr(
    dsp_secrets, "spotify_redirect_uri", "http://127.0.0.1:8080/callback"
)
CACHE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".spotify_oauth_cache")
SCOPE = "playlist-read-private playlist-read-collaborative"


def main():
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    from spotipy.cache_handler import CacheFileHandler

    print("Spotify user login")
    print("Redirect URI used:", SPOTIFY_REDIRECT_URI)
    print("If you haven't already, add this exact URI in your app's Redirect URIs in the Dashboard.")
    print()

    cache_handler = CacheFileHandler(cache_path=CACHE_PATH)
    auth = SpotifyOAuth(
        client_id=dsp_secrets.spotify_client_id,
        client_secret=dsp_secrets.spotify_client_secret,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SCOPE,
        cache_handler=cache_handler,
        open_browser=True,
    )

    # get_access_token(check_cache=True): uses cache if valid; else opens browser / local server
    try:
        token = auth.get_access_token(check_cache=True)
    except Exception as e:
        print("Auth failed:", e)
        return 1

    if token:
        print("Success. Token saved to", CACHE_PATH)
        print("You can now run the app or: python scripts/test_spotify.py <playlist_url>")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
