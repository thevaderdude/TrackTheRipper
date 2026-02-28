#!/usr/bin/env python3
"""
CLI to download a Spotify playlist: fetches tracks and saves best-match YT/SC audio
as ARTIST - TITLE in the given output directory.
Use --tracks-file to run from a JSON track list when Spotify API is unavailable.
"""
import argparse
import json
import os
import spotify_playlist


def main():
    p = argparse.ArgumentParser(description="Download Spotify playlist to best-match audio files.")
    p.add_argument("playlist_url", nargs="?", help="Spotify playlist URL (or use --tracks-file)")
    p.add_argument("-o", "--output-dir", default="saved_tracks", help="Output directory (default: saved_tracks)")
    p.add_argument("-n", "--limit", type=int, default=None, help="Max number of tracks to download (default: all)")
    p.add_argument("--retries", type=int, default=2, help="Retries per track (default: 2)")
    p.add_argument("--tracks-file", help="JSON file with track list (list of {name, artists, duration_ms}) instead of Spotify API")
    args = p.parse_args()

    if args.tracks_file:
        with open(args.tracks_file) as f:
            tracks = json.load(f)
        if args.limit and args.limit > 0:
            tracks = tracks[: args.limit]
        out_dir = os.path.join(args.output_dir, "from_file")
        os.makedirs(out_dir, exist_ok=True)
        print(f"Output directory: {out_dir} (from {args.tracks_file})")
        print("Running pipeline…")
        results = spotify_playlist.run_pipeline_from_tracks(tracks, out_dir, retries_per_track=args.retries)
    elif args.playlist_url:
        playlist_id = spotify_playlist.parse_playlist_id(args.playlist_url)
        if not playlist_id:
            print("Error: invalid playlist URL")
            return 1
        out_dir = os.path.join(args.output_dir, f"playlist_{playlist_id}")
        os.makedirs(out_dir, exist_ok=True)
        print(f"Output directory: {out_dir}")
        print("Running pipeline…")
        results = spotify_playlist.run_pipeline(
            args.playlist_url,
            out_dir,
            track_limit=args.limit,
            retries_per_track=args.retries,
        )
    else:
        print("Error: provide playlist_url or --tracks-file")
        return 1
    ok = sum(1 for r in results if r.get("status") == "ok")
    err = sum(1 for r in results if r.get("status") == "error")
    for r in results:
        if r.get("status") == "ok":
            print(f"  OK  {r.get('track_name', '?')}")
        else:
            print(f"  ERR {r.get('track_name', '?')}: {r.get('error', '')}")
    print(f"Done: {ok} ok, {err} errors.")
    return 0 if err == 0 else 1


if __name__ == "__main__":
    exit(main())
