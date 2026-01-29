from PIL import Image
import requests
from io import BytesIO
import os
import shutil


def get_img_from_url(url, size=None):
    response = requests.get(url)
    raw_img = Image.open(BytesIO(response.content))
    if size is None:
        return raw_img
    else:
        return raw_img.resize(size)


def remove_all_except_current(cur_id, download_path='test_downloads'):
    all_paths = os.listdir(download_path)
    if cur_id:
        all_paths.remove(cur_id)
    for path in all_paths:
        shutil.rmtree(os.path.join(download_path, path))