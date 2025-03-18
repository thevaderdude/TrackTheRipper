import yt_dlp
from sclib import SoundcloudAPI, Track, Playlist

api = SoundcloudAPI()  



def download_yt(url, filepath):

    URLS = [url]
    ydl_opts = {
    'format': 'wav/bestaudio/best',
    # ℹ️ See help(yt_dlp.postprocessor) for a list of available Postprocessors and their arguments
    'postprocessors': [{  # Extract audio using ffmpeg
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'wav',
    }],
    'paths': {
        'home': filepath
    }
}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        error_code = ydl.download(URLS)


def download_sc(url, filepath):
    track = api.resolve(url)

    assert type(track) is Track

    filename = f'{filepath}/{track.artist} - {track.title}.mp3'
    
    with open(filename, 'wb+') as file:
        track.write_mp3_to(file)