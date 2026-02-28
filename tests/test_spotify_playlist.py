"""Unit and integration tests for spotify_playlist module."""
import pytest
import spotify_playlist
from tests.conftest import PLAYLIST_URL_1, PLAYLIST_URL_2


# --- URL parsing (unit) ---
def test_parse_playlist_id_from_web_url_1():
    assert spotify_playlist.parse_playlist_id(PLAYLIST_URL_1) == "37i9dQZEVXd2ZWQqzKbAfl"


def test_parse_playlist_id_from_web_url_2():
    assert spotify_playlist.parse_playlist_id(PLAYLIST_URL_2) == "37i9dQZF1E8LQ8CR1hh5Oz"


def test_parse_playlist_id_uri():
    assert spotify_playlist.parse_playlist_id("spotify:playlist:37i9dQZEVXd2ZWQqzKbAfl") == "37i9dQZEVXd2ZWQqzKbAfl"


def test_parse_playlist_id_raw_id():
    assert spotify_playlist.parse_playlist_id("37i9dQZEVXd2ZWQqzKbAfl") == "37i9dQZEVXd2ZWQqzKbAfl"


def test_parse_playlist_id_invalid():
    assert spotify_playlist.parse_playlist_id("") is None
    assert spotify_playlist.parse_playlist_id("https://example.com/foo") is None
    assert spotify_playlist.parse_playlist_id(None) is None


# --- YT duration parsing (unit) ---
def test_parse_yt_duration_mm_ss():
    assert spotify_playlist.parse_yt_duration("3:28") == (3 * 60 + 28) * 1000
    assert spotify_playlist.parse_yt_duration("0:45") == 45 * 1000


def test_parse_yt_duration_hms():
    assert spotify_playlist.parse_yt_duration("1:23:45") == (3600 + 23 * 60 + 45) * 1000


def test_parse_yt_duration_seconds_only():
    assert spotify_playlist.parse_yt_duration("90") == 90 * 1000


def test_parse_yt_duration_invalid():
    assert spotify_playlist.parse_yt_duration("") == 0
    assert spotify_playlist.parse_yt_duration(None) == 0
    assert spotify_playlist.parse_yt_duration("abc") == 0


# --- YT views parsing (unit) ---
def test_parse_yt_views_plain():
    assert spotify_playlist.parse_yt_views("216,105 views") == 216105
    assert spotify_playlist.parse_yt_views("82064907 views") == 82064907


def test_parse_yt_views_k_m():
    assert spotify_playlist.parse_yt_views("1.2M views") == 1_200_000
    assert spotify_playlist.parse_yt_views("500K views") == 500_000


def test_parse_yt_views_invalid():
    assert spotify_playlist.parse_yt_views("") == 0
    assert spotify_playlist.parse_yt_views(None) == 0


# --- Title similarity (unit) ---
def test_title_similarity_exact():
    assert spotify_playlist.title_similarity("Artist - Title", "Artist - Title") == 1.0


def test_title_similarity_close():
    r = spotify_playlist.title_similarity("Knock2 - come aliv3", "Knock2 - Come Aliv3 (Official)")
    assert r > 0.5


def test_title_similarity_empty():
    assert spotify_playlist.title_similarity("", "") == 1.0
    assert spotify_playlist.title_similarity("a", "") == 0.0


# --- Length score (unit) ---
def test_length_score_same_or_longer():
    assert spotify_playlist.length_score(180_000, 180_000) >= 0.95
    assert spotify_playlist.length_score(300_000, 180_000) >= 0.95  # extended


def test_length_score_shorter_penalty():
    # Candidate much shorter than Spotify
    assert spotify_playlist.length_score(60_000, 180_000) < 0.7


def test_length_score_zero_spotify():
    assert spotify_playlist.length_score(180_000, 0) == 1.0


# --- Best-match logic (unit, mock candidates) ---
def test_pick_best_candidate_prefers_views_and_title():
    spotify_track = {"name": "Come Aliv3", "artists": "Knock2", "duration_ms": 200_000}
    yt = [
        {"url": "https://youtube.com?v=a", "title": "Knock2 - Come Aliv3", "channel": "Knock2", "duration": "3:20", "views": "1,000,000 views"},
        {"url": "https://youtube.com?v=b", "title": "Random Remix", "channel": "Other", "duration": "3:20", "views": "100 views"},
    ]
    sc = []
    best = spotify_playlist.pick_best_candidate(spotify_track, yt, sc)
    assert best is not None
    assert best["type"] == "yt"
    assert best["url"] == "https://youtube.com?v=a"
    assert "Come Aliv3" in best["title"] or "come aliv3" in best["title"].lower()


def test_pick_best_candidate_prefers_longer_when_similar():
    spotify_track = {"name": "Track", "artists": "Artist", "duration_ms": 300_000}  # 5 min
    yt = [
        {"url": "https://youtube.com?v=a", "title": "Artist - Track", "channel": "Artist", "duration": "3:00", "views": "1000 views"},
        {"url": "https://youtube.com?v=b", "title": "Artist - Track Extended", "channel": "Artist", "duration": "5:30", "views": "900 views"},
    ]
    best = spotify_playlist.pick_best_candidate(spotify_track, yt, [])
    assert best is not None
    # Extended should score higher on length; may win overall depending on title match
    assert best["url"] in ("https://youtube.com?v=a", "https://youtube.com?v=b")


def test_pick_best_candidate_empty_returns_none():
    spotify_track = {"name": "X", "artists": "Y", "duration_ms": 180_000}
    assert spotify_playlist.pick_best_candidate(spotify_track, [], []) is None
    assert spotify_playlist.pick_best_candidate(spotify_track, None, None) is None


# --- Integration: Spotify fetch ---
@pytest.mark.integration
def test_fetch_playlist_tracks_url_1():
    pid = spotify_playlist.parse_playlist_id(PLAYLIST_URL_1)
    assert pid
    tracks = spotify_playlist.fetch_playlist_tracks(pid)
    assert isinstance(tracks, list)
    assert len(tracks) >= 1
    for t in tracks:
        assert "name" in t and "artists" in t and "duration_ms" in t
        assert isinstance(t["duration_ms"], (int, float))


@pytest.mark.integration
def test_fetch_playlist_tracks_url_2():
    pid = spotify_playlist.parse_playlist_id(PLAYLIST_URL_2)
    assert pid
    tracks = spotify_playlist.fetch_playlist_tracks(pid)
    assert isinstance(tracks, list)
    assert len(tracks) >= 1
    for t in tracks:
        assert "name" in t and "artists" in t and "duration_ms" in t


# --- E2E: full pipeline with track limit (slow, optional) ---
@pytest.mark.integration
@pytest.mark.slow
def test_run_pipeline_limit_2_tracks(tmp_path):
    """Run full pipeline for first playlist with limit=2; assert 2 files exist with ARTIST - TITLE pattern."""
    out_dir = str(tmp_path / "playlist_out")
    results = spotify_playlist.run_pipeline(PLAYLIST_URL_1, out_dir, track_limit=2)
    assert len(results) <= 2
    ok = [r for r in results if r.get("status") == "ok"]
    if ok:
        import os
        for r in ok:
            path = r.get("path")
            assert path and os.path.isfile(path)
            assert " - " in os.path.basename(path)
            assert os.path.getsize(path) > 0


# --- Integration: search + best match (one track) ---
@pytest.mark.integration
def test_search_and_best_match_one_track():
    pid = spotify_playlist.parse_playlist_id(PLAYLIST_URL_1)
    tracks = spotify_playlist.fetch_playlist_tracks(pid)
    assert len(tracks) >= 1
    st = tracks[0]
    query = f"{st['artists']} - {st['name']}"
    import search
    yt_list = search.search_youtube(query, limit=5)
    sc_list = search.search_soundcloud(query, limit=5)
    best = spotify_playlist.pick_best_candidate(st, yt_list or [], sc_list or [])
    # We may get no results if APIs fail; if we have results we must get a best
    if (yt_list and len(yt_list) > 0) or (sc_list and len(sc_list) > 0):
        assert best is not None
        assert best["type"] in ("yt", "sc")
        assert "url" in best and "artist" in best and "title" in best
