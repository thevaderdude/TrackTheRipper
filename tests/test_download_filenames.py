"""Tests for download filename sanitization and ARTIST - TITLE format."""
import pytest
import download


def test_sanitize_filename_part_basic():
    assert download.sanitize_filename_part("Artist Name") == "Artist Name"
    assert download.sanitize_filename_part("Track Title") == "Track Title"


def test_sanitize_filename_part_removes_unsafe():
    assert "/" not in download.sanitize_filename_part("a/b")
    assert "\\" not in download.sanitize_filename_part("a\\b")
    assert ":" not in download.sanitize_filename_part("a:b")
    assert "*" not in download.sanitize_filename_part("a*b")
    assert "?" not in download.sanitize_filename_part("a?b")
    assert '"' not in download.sanitize_filename_part('a"b')
    assert "<" not in download.sanitize_filename_part("a<b")
    assert ">" not in download.sanitize_filename_part("a>b")
    assert "|" not in download.sanitize_filename_part("a|b")


def test_sanitize_filename_part_empty_unknown():
    assert download.sanitize_filename_part("") == "Unknown"
    assert download.sanitize_filename_part(None) == "Unknown"


def test_sanitize_filename_part_truncates():
    long_str = "a" * 150
    out = download.sanitize_filename_part(long_str, max_len=100)
    assert len(out) <= 100
    assert out == "a" * 100


def test_sanitize_filename_part_artist_title_pattern():
    artist = download.sanitize_filename_part("Knock2")
    title = download.sanitize_filename_part("come aliv3")
    combined = f"{artist} - {title}"
    assert combined == "Knock2 - come aliv3"
    assert " - " in combined
    assert combined.count(" - ") == 1
