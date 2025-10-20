
import requests 
from urllib.parse import quote
import time
from youtube_search import YoutubeSearch
import dsp_secrets

def search_youtube(search_term, limit=5):
    results = YoutubeSearch(search_term, max_results=limit).to_dict()
    results_formatted = []
    for result in results:
        res = {
            'thumbnail': result['thumbnails'][0],
            'url': 'https://www.youtube.com/watch?v=' + result['id'],
            'channel': result['channel'],
            'duration': result['duration'],
            'title': result['title'],
            'views': result['views']
        }
        results_formatted.append(res)
    return results_formatted


# sc search
def search_soundcloud(search_term, limit=5, retries=4):
    search_results = soundcloud_url_call(search_term, limit=limit)
    
    while retries and search_results == {}:
        print(f'Search Failed. Remaining Retries: {retries}')
        retries -= 1
        time.sleep(1)
        search_results = soundcloud_url_call(search_term, limit=limit)
    
    if search_results == {}:
        print('search failed')
        return


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
    return res.json()