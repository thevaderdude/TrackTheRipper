import search
import download
import pprint
import options

search_term = input('Enter Search Term:')

yt_res = search.search_youtube(search_term)

sc_res = search.search_soundcloud(search_term)

full_res = yt_res + sc_res
print('Youtube')
for i in range(len(full_res)):
    if i == len(yt_res):
        print('SoundCloud')
    print(f"{i}:")
    pprint.pprint(full_res[i])

idx = int(input('Choose number track from list above:'))

if 0 <= idx < 5: # youtube
    download.download_yt(full_res[idx]['url'], filepath=options.download_path)
elif 5 <= idx <= 9: #soundcloud
    download.download_sc(full_res[idx]['link'], filepath=options.download_path)
else: 
    print('error invalid input')