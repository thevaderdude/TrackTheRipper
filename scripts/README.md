# Scripts

## Spotify API

### 1. Test (debug) – `test_spotify.py`

Prints whether **client credentials** and (if set up) **user auth** can call the Spotify API, and shows full errors.

```bash
python scripts/test_spotify.py
python scripts/test_spotify.py "https://open.spotify.com/playlist/..."
```

- **Section 1:** App-only (client credentials) + `playlist_tracks`. Often **403** in Development Mode.
- **Section 2:** Same playlist_tracks call with that client.
- **Section 3:** User OAuth (if you’ve run `spotify_user_auth.py`). Use this to confirm user auth works.

### 2. User login (one-time) – `spotify_user_auth.py`

Run once to log in with your Spotify account. Saves a token so the app can read your playlists without logging in again.

**Before running:**

1. **Redirect URI**  
   In [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) → your app → **Settings** → **Redirect URIs**, add:
   ```text
   http://127.0.0.1:8080/callback
   ```
   Save.

2. **User allowlist (Development Mode)**  
   In the same app → **User management** → add your Spotify email so you can authorize.

**Run:**

```bash
python scripts/spotify_user_auth.py
```

- A browser window opens for Spotify login.
- A local server on port 8080 receives the callback (or you paste the redirect URL if the server isn’t used).
- On success, the token is saved to `.spotify_oauth_cache` in the project root (gitignored).

After that, the main app and `test_spotify.py` will use this user token when calling the Spotify API (and fall back to client credentials if the cache is missing or invalid).

**Optional:** To use a different redirect URI, set it in `dsp_secrets.py`:

```python
spotify_redirect_uri = "http://127.0.0.1:8080/callback"  # must match Dashboard
```
