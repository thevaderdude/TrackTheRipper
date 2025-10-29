# has 2 classes: result, result element
import download
import shutil
import os
import uuid

class Result:
    _DL_PATH = 'test_downloads'

    def __init__(self, search_term, yt_results, sc_results):

        # basic
        self.search_term = search_term
        self.yt_results_raw = yt_results
        self.sc_results_raw = sc_results

        self.id = uuid.uuid4().__str__()
        self.download_path = os.path.join(self._DL_PATH, self.id)
        os.makedirs(self.download_path, exist_ok=True)

        # create into transformed vars
        self.yt_results = [ResultElement(res, type='yt') for res in self.yt_results_raw]
        self.sc_results = [ResultElement(res, type='sc') for res in self.sc_results_raw] if len(self.sc_results_raw) > 0 else []

        self.is_downloaded = False

    def get_count_results(self):
        return len(self.yt_results) + len(self.sc_results)

    def get_results(self):
        return self.yt_results + self.sc_results
    
    def download_all(self):
        for result in self.get_results():
            result.download(self.download_path)
        
        self.is_downloaded = True

class ResultElement:

    def __init__(self, attrs, type):
        self.attrs_raw = attrs
        self.type = type

        print(attrs)

        if type == 'yt':
            self.cover = attrs['thumbnail']
            self.url = attrs['url']
            self.duration_formatted = attrs['duration']
            self.title = attrs['title']
            self.artist = attrs['channel']
            self.plays_formatted = attrs['views']

        elif type == 'sc':
            self.cover = attrs['cover']
            self.url = attrs['link']
            self.duration_formatted = attrs['duration_formatted']
            self.title = attrs['title']
            self.artist = attrs['artist'] if attrs['artist'] != '' else attrs['username']
            self.plays_formatted = f"{attrs['plays']:,}"

        self.file_location = None

        self.is_downloaded = False

    def download(self, filepath):
        if self.type == 'yt':
            self.file_location = download.download_yt(self.url, filepath=filepath, format='mp3')
        elif self.type == 'sc':
            self.file_location = download.download_sc(self.url, filepath=filepath)
        
        self.is_downloaded = True

    def save_track(self, download_path):
        if self.type == 'sc':
            shutil.copy(self.file_location, download_path)
        elif self.type == 'yt':
            download.download_yt(self.url, filepath=download_path, format='wav')

    def clear(self):
        if os.path.exists(self.file_location):
            os.remove(self.file_location)
            self.is_downloaded = False
    
