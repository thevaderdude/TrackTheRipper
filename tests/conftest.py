import pytest

# Playlist URLs used by integration tests (from plan)
PLAYLIST_URL_1 = "https://open.spotify.com/playlist/37i9dQZEVXd2ZWQqzKbAfl?si=26bf0aed73f04856"
PLAYLIST_URL_2 = "https://open.spotify.com/playlist/37i9dQZF1E8LQ8CR1hh5Oz?si=a9c8f73dff4941d4"


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: marks tests that need network/API (deselect with '-m \"not integration\"')")
    config.addinivalue_line("markers", "slow: marks tests as slow (e.g. e2e download)")
