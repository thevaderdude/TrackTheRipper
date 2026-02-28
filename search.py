import requests
from urllib.parse import quote
import time
from youtube_search import YoutubeSearch
import dsp_secrets

DEFAULT_YT_RETRIES = 4
DEFAULT_YT_BACKOFF = 1.5


def search_youtube(search_term, limit=5, retries=None, backoff=None):
    retries = DEFAULT_YT_RETRIES if retries is None else retries
    backoff = DEFAULT_YT_BACKOFF if backoff is None else backoff
    last_error = None
    for attempt in range(max(1, retries)):
        try:
            results = YoutubeSearch(search_term, max_results=limit).to_dict()
            results_formatted = []
            for result in results:
                thumbnails = result.get("thumbnails") or []
                res = {
                    "thumbnail": thumbnails[0] if thumbnails else "",
                    "url": "https://www.youtube.com/watch?v=" + result.get("id", ""),
                    "channel": result.get("channel", ""),
                    "duration": result.get("duration", ""),
                    "title": result.get("title", ""),
                    "views": result.get("views", ""),
                }
                results_formatted.append(res)
            return results_formatted
        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
    print(f"search_youtube failed after {retries} retries: {last_error}")
    return []


# sc search
def search_soundcloud(search_term, limit=5, retries=4):
    search_results = soundcloud_url_call(search_term, limit=limit)
    
    while retries and search_results == {}:
        print(f'Search Failed. Remaining Retries: {retries}')
        retries -= 1
        time.sleep(1)
        search_results = soundcloud_url_call(search_term, limit=limit)
    
    if search_results == {}:
        print("search_soundcloud failed")
        return []

    search_results_formatted = []
    for result in search_results.get('collection'):
        new_res = {
            'cover': result['artwork_url'],
            'comments': result['comment_count'],
            'date': result['created_at'].split('T')[0],
            'duration_ms': result['duration'],
            'duration_formatted': f'{result["duration"]//(1000 * 60)}:{(result["duration"]//1000)%60:02d}',
            'likes': result['likes_count'],
            'plays': result['playback_count'],
            'artist': result.get('publisher_metadata').get('artist') if result.get('publisher_metadata') is not None else '',
            'title': result['title'],
            'username': result['user']['username'],
            'link': result['permalink_url']
        }
        search_results_formatted.append(new_res)

    return search_results_formatted


def soundcloud_url_call(search_term, limit):
    saerch_term_formatted = quote(search_term)
    url_temp = "https://api-v2.soundcloud.com/search/tracks?q={query}&client_id={client_id}&limit={limit}&offset={offset}"
    r_url = url_temp.format(query=saerch_term_formatted, client_id=dsp_secrets.sc_client_id, limit=str(limit), offset="0")
    res = requests.get(r_url)
    try:
        data = res.json()
        return data if isinstance(data, dict) else {}
    except (ValueError, requests.exceptions.JSONDecodeError):
        return {}