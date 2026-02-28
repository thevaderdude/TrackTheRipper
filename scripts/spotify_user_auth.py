#!/usr/bin/env python3
"""
One-time Spotify user login (Authorization Code flow).
Saves a refresh token so the app can read your playlists without logging in again.
Uses requests + direct Spotify Web API URLs (no spotipy).

Before running:
  1. In Spotify Developer Dashboard → your app → "Redirect URIs", add:
     http://127.0.0.1:8080/callback
  2. Ensure your Spotify account is in the app's "User management" (Development Mode).

Run from project root: python scripts/spotify_user_auth.py
"""
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, quote, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

import dsp_secrets

# Must match the URI you add in the Spotify Dashboard
SPOTIFY_REDIRECT_URI = getattr(
    dsp_secrets, "spotify_redirect_uri", "http://127.0.0.1:8080/callback"
)
CACHE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".spotify_oauth_cache")
SCOPE = "playlist-read-private playlist-read-collaborative"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"


def run_local_server(code_holder: list, port: int = 8080):
    """Start a one-request HTTP server to receive the redirect with ?code=..."""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path in ("/callback", "/"):
                qs = parse_qs(parsed.query)
                codes = qs.get("code", [])
                if codes:
                    code_holder.append(codes[0])
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><p>Authorization successful. You can close this tab.</p></body></html>"
                )
            else:
                self.send_response(404)
                self.end_headers()
            # Shutdown after first request so server stops
            self.server.shutdown_request(self)

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("127.0.0.1", port), Handler)
    server.handle_request()


def main():
    print("Spotify user login")
    print("Redirect URI used:", SPOTIFY_REDIRECT_URI)
    print("If you haven't already, add this exact URI in your app's Redirect URIs in the Dashboard.")
    print()

    auth_url = (
        f"{SPOTIFY_AUTH_URL}?"
        f"client_id={dsp_secrets.spotify_client_id}&"
        "response_type=code&"
        f"redirect_uri={quote(SPOTIFY_REDIRECT_URI)}&"
        f"scope={quote(SCOPE)}"
    )
    code_holder = []
    print("Opening browser for Spotify login...")
    import webbrowser
    webbrowser.open(auth_url)
    run_local_server(code_holder)

    if not code_holder:
        print("No authorization code received. Did you approve the app and get redirected back?")
        return 1

    code = code_holder[0]
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
        "client_id": dsp_secrets.spotify_client_id,
        "client_secret": dsp_secrets.spotify_client_secret,
    }
    r = requests.post(
        SPOTIFY_TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    if not r.ok:
        print("Token exchange failed:", r.status_code, r.text)
        return 1

    j = r.json()
    token_info = {
        "access_token": j["access_token"],
        "refresh_token": j["refresh_token"],
        "expires_in": j.get("expires_in", 3600),
    }
    token_info["expires_at"] = int(time.time()) + token_info["expires_in"]

    with open(CACHE_PATH, "w") as f:
        json.dump(token_info, f, indent=2)
    print("Success. Token saved to", CACHE_PATH)
    print("You can now run the app or: python scripts/test_spotify.py <playlist_url>")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
