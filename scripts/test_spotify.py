#!/usr/bin/env python3
"""
Test Spotify API access: client credentials and (if set up) user OAuth.
Run from project root: python scripts/test_spotify.py [playlist_id_or_url]

Uses non-deprecated Get Playlist Items endpoint. User auth required for playlist access.
Optional: pass a playlist ID or URL to test fetching tracks.
"""
import sys
import os

# Run from project root so dsp_secrets and spotify_playlist are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_client_credentials(playlist_id: str):
    """Test client credentials token (playlist/items may return 401 with client creds)."""
    from spotify_playlist import get_client_credentials_token, request_playlist_tracks_page

    print("=== 1. Client credentials ===")
    try:
        token = get_client_credentials_token()
        if not token:
            print("  FAIL: Could not get token (check client ID and secret in dsp_secrets).")
            return None
        request_playlist_tracks_page(playlist_id, token, limit=1, offset=0, market="US")
        print("  OK: Token + playlist items succeeded.")
        return token
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {e}")
        print("  (Get Playlist Items requires user OAuth; run: python scripts/spotify_user_auth.py)")
        import traceback
        traceback.print_exc()
        return None


def test_playlist_with_token(token, playlist_id: str):
    """Fetch one page of playlist items with the given token."""
    from spotify_playlist import request_playlist_tracks_page

    if token is None:
        print("  SKIP: No token.")
        return
    try:
        resp = request_playlist_tracks_page(playlist_id, token, limit=5, offset=0, market="US")
        total = resp.get("total", 0)
        items = resp.get("items", [])
        print(f"  OK: total={total}, first batch={len(items)} items.")
        for i, item in enumerate(items[:3]):
            t = item.get("item") or item.get("track") or {}
            name = t.get("name", "?")
            artists = ", ".join(a.get("name", "") for a in (t.get("artists") or []))
            print(f"      [{i+1}] {artists} - {name}")
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


def test_user_auth(playlist_id: str):
    """Test user OAuth (required for Get Playlist Items)."""
    from spotify_playlist import get_access_token, parse_playlist_id, request_playlist_tracks_page

    print("\n=== 3. User OAuth (for playlist access) ===")
    cache_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".spotify_oauth_cache")
    if not os.path.isfile(cache_path):
        print("  SKIP: No user token. Run: python scripts/spotify_user_auth.py")
        return
    try:
        token = get_access_token(force_client_credentials=False)
        if not token:
            print("  SKIP: User token missing or invalid.")
            return
        print("  OK: User token valid.")
        pid = parse_playlist_id(playlist_id) or playlist_id
        resp = request_playlist_tracks_page(pid, token, limit=5, offset=0, market="US")
        total = resp.get("total", 0)
        items = resp.get("items", [])
        print(f"  OK: playlist items total={total}, first batch={len(items)}.")
        for i, item in enumerate(items[:3]):
            t = item.get("item") or item.get("track") or {}
            name = t.get("name", "?")
            artists = ", ".join(a.get("name", "") for a in (t.get("artists") or []))
            print(f"      [{i+1}] {artists} - {name}")
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


def main():
    from spotify_playlist import DEFAULT_USER_PLAYLIST_URL, parse_playlist_id

    playlist_arg = sys.argv[1] if len(sys.argv) > 1 else None
    if playlist_arg:
        playlist_id = parse_playlist_id(playlist_arg) or playlist_arg
    else:
        playlist_id = parse_playlist_id(DEFAULT_USER_PLAYLIST_URL) or "43KVtpxkc3rlkdyGZYCiQk"

    token = test_client_credentials(playlist_id)
    print(f"\n=== 2. Playlist items (same token) (id={playlist_id}) ===")
    test_playlist_with_token(token, playlist_id)
    test_user_auth(playlist_id)
    print("\nDone.")


if __name__ == "__main__":
    main()
