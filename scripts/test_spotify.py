#!/usr/bin/env python3
"""
Test Spotify API access: client credentials and (if set up) user auth.
Run from project root: python scripts/test_spotify.py [playlist_id_or_url]

Prints full errors for debugging. Optional: pass a playlist ID or URL to test
fetching that playlist's tracks.
"""
import sys
import os

# Run from project root so dsp_secrets and spotify_playlist are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dsp_secrets


def test_client_credentials(playlist_id: str):
    """Test app-only (client credentials) token; then try playlist_tracks (no /me/ with client creds)."""
    import spotipy
    from spotipy.oauth2 import SpotifyClientCredentials

    print("=== 1. Client credentials (app-only) ===")
    try:
        client = SpotifyClientCredentials(
            client_id=dsp_secrets.spotify_client_id,
            client_secret=dsp_secrets.spotify_client_secret,
        )
        sp = spotipy.Spotify(client_credentials_manager=client)
        # Client credentials don't have /me/; test with playlist_tracks
        sp.playlist_tracks(playlist_id, limit=1, offset=0, market="US")
        print("  OK: Client credentials token + playlist_tracks succeeded.")
        return sp
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_playlist_tracks(sp, playlist_id: str):
    """Test playlist_tracks(playlist_id)."""
    print(f"\n=== 2. Get playlist tracks (id={playlist_id}) ===")
    if sp is None:
        print("  SKIP: No Spotify client (client credentials failed).")
        return
    try:
        resp = sp.playlist_tracks(playlist_id, limit=5, offset=0, market="US")
        total = resp.get("total", 0)
        items = resp.get("items", [])
        print(f"  OK: total={total}, first batch={len(items)} items.")
        for i, item in enumerate(items[:3]):
            t = item.get("track") or {}
            name = t.get("name", "?")
            artists = ", ".join(a.get("name", "") for a in (t.get("artists") or []))
            print(f"      [{i+1}] {artists} - {name}")
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


def test_user_auth(playlist_id: str = None):
    """Test user auth (OAuth) if .spotify_oauth_cache exists."""
    from spotify_playlist import get_spotify_client, parse_playlist_id

    print("\n=== 3. User auth (OAuth) ===")
    cache_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".spotify_oauth_cache")
    if not os.path.isfile(cache_path):
        print("  SKIP: No user token. Run: python scripts/spotify_user_auth.py")
        return
    try:
        sp = get_spotify_client()
        if sp is None:
            print("  SKIP: User token missing or invalid.")
            return
        print("  OK: User token valid.")
        if playlist_id:
            playlist_id = parse_playlist_id(playlist_id) or playlist_id
            resp = sp.playlist_tracks(playlist_id, limit=5, offset=0, market="US")
            total = resp.get("total", 0)
            print(f"  OK: playlist_tracks total={total}.")
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


def main():
    playlist_arg = sys.argv[1] if len(sys.argv) > 1 else None
    if playlist_arg:
        from spotify_playlist import parse_playlist_id
        playlist_id = parse_playlist_id(playlist_arg) or playlist_arg
    else:
        playlist_id = "37i9dQZF1DXcBWIGoYBM5M"  # Today's Top Hits

    sp = test_client_credentials(playlist_id)
    test_playlist_tracks(sp, playlist_id)
    test_user_auth(playlist_id)
    print("\nDone.")


if __name__ == "__main__":
    main()
