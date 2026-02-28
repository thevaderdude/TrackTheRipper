# Scripts

## Spotify API

The app uses **user OAuth** when available (so the non-deprecated Get Playlist Items API works). Run `spotify_user_auth.py` once, then the app and tests use that token. Falls back to client credentials if no user token (client credentials get 401 on Get Playlist Items).

### 1. User login (one-time) – `spotify_user_auth.py`

Run once to log in with your Spotify account. Saves a token to `.spotify_oauth_cache` so the app can read playlists.

**Before running:**

1. **Redirect URI**  
   In [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) → your app → **Settings** → **Redirect URIs**, add:
   ```text
   http://127.0.0.1:8080/callback
   ```
   Save.

2. **User allowlist (Development Mode)**  
   In the same app → **User management** → add your Spotify email.

**Run:**

```bash
python scripts/spotify_user_auth.py
```

A browser opens for Spotify login; on success the token is saved to `.spotify_oauth_cache` (gitignored).

### 2. Test (debug) – `test_spotify.py`

Checks client credentials token and, if you have a user token, playlist access via Get Playlist Items.

```bash
python scripts/test_spotify.py
python scripts/test_spotify.py "https://open.spotify.com/playlist/..."
```

- **Section 1:** Client credentials (token only; playlist/items will 401 with app token).
- **Section 2:** Same token, one page of playlist items (likely 401 without user auth).
- **Section 3:** User OAuth from `.spotify_oauth_cache`; should succeed if you ran `spotify_user_auth.py`.
