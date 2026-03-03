# "main" script
# has all the streamlit stuff (maybe make classes and stuff in other files.)
# just the declarative UI modules and high-level logic

import os
import streamlit as st
import search
import result
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import util
import spotify_playlist


TITLE_FIX_MD = """
    <div style="
        height: 3em; 
        line-height: 1.5em;
        overflow: hidden; 
        text-overflow: ellipsis;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        white-space: normal;
        font-size: 1.17em;  /* h3 size */
        font-weight: 600;
        margin: 0.4em 0;
    ">
        {t}
    </div>
        """

LOGO_SIZE = (10, 10)


yt_logo = util.get_img_from_url('https://www.youtube.com/s/desktop/3fd9a6f6/img/favicon_32x32.png')


# TODO: fix logo sizing
sc_logo = util.get_img_from_url('https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcS3UekB8iVVIJpXNMQrflhVKClcRdc_JKAPIw&s')


ss = st.session_state
ss.setdefault("job_running", False)
ss.setdefault("q", queue.Queue())               # worker -> UI messages
ss.setdefault("results", [])                    # list aligned to items_snapshot
ss.setdefault("done", 0)
ss.setdefault("total", 0)
ss.setdefault("executor", None)
ss.setdefault("items_snapshot", None)
ss.setdefault("search_results", None)
ss.setdefault("playlist_results", None)  # list of {track_name, status, path?, error?, source_type?, source_url?, source_title?}
ss.setdefault("playlist_details", None)   # {name, image_url} after Load playlist
ss.setdefault("playlist_tracks", None)    # list of {name, artists, duration_ms}
ss.setdefault("playlist_id", None)
ss.setdefault("playlist_url", None)

# frozen items for the current run

def do_rerun():
    if hasattr(st, 'rerun'):
        st.rerun()


def worker(idx: int, out_q: queue.Queue, s_result: result.Result, elem: result.ResultElement):
    try:
        # do the download/work
        elem.download(filepath=s_result.download_path)
        # report progress
        out_q.put(("progress", idx, elem.file_location))
    except Exception as e:
        out_q.put(("error", idx, f"{type(e).__name__}: {e}"))

def start_job(s_result: result.Result, max_workers: int):
    if ss.job_running:
        return
    items = s_result.get_results()
    ss.items_snapshot = list(items)        # freeze inputs for this run
    ss.total = len(ss.items_snapshot)
    ss.results = [None] * ss.total
    ss.errors = {}
    ss.done = 0
    ss.job_running = True

    # IMPORTANT: use the existing queue; do not replace mid-run
    # (but clear any old residual messages)
    try:
        while True:
            ss.q.get_nowait()
    except queue.Empty:
        pass

    ss.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="worker")
    for i, elem in enumerate(ss.items_snapshot):
        ss.executor.submit(worker, i, ss.q, s_result, elem)



st.title("search2mp3")

tab_playlist, tab_search = st.tabs(["Spotify playlist", "Search single track"])

# --- Spotify playlist tab ---
with tab_playlist:
    playlist_url_input = st.text_input(
        label="Playlist URL",
        placeholder="https://open.spotify.com/playlist/...",
        help="Paste a Spotify playlist link. Load to preview, then download.",
        key="playlist_url_input",
    )
    col_load, _ = st.columns([1, 3])
    with col_load:
        load_clicked = st.button("Load playlist", key="load_playlist")
    if load_clicked and playlist_url_input:
        pid = spotify_playlist.parse_playlist_id(playlist_url_input)
        if not pid:
            st.error("Invalid playlist URL.")
        else:
            try:
                with st.spinner("Fetching playlist…"):
                    ss.playlist_details = spotify_playlist.fetch_playlist_details(pid)
                    ss.playlist_tracks = spotify_playlist.fetch_playlist_tracks(pid)
                    ss.playlist_id = pid
                    ss.playlist_url = playlist_url_input
                st.success("Playlist loaded.")
            except Exception as e:
                st.error(f"Could not load playlist: {e}")
                ss.playlist_tracks = None
                ss.playlist_details = None

    if ss.playlist_tracks is not None:
        if not ss.playlist_tracks:
            st.warning("No tracks in this playlist.")
        else:
            st.subheader(ss.playlist_details.get("name", "Playlist") if ss.playlist_details else "Playlist")
            img_url = ss.playlist_details.get("image_url") if ss.playlist_details else None
            if img_url:
                st.image(img_url, width=200)
            # Use a simple table (no st.dataframe) to avoid PyArrow/NumPy compatibility issues
            st.write("**Tracks**")
            for i, t in enumerate(ss.playlist_tracks):
                st.caption(f"{i + 1}. **{t.get('name', '?')}** — {t.get('artists', '')}")

    playlist_track_limit = st.number_input(
        label="Track limit (0 = all)",
        min_value=0,
        value=0,
        step=1,
        help="Set to e.g. 3 for a quick test.",
        key="playlist_track_limit",
    )
    download_clicked = st.button("Download playlist", key="download_playlist")
    if download_clicked:
        url_to_use = playlist_url_input or ss.playlist_url
        if not url_to_use:
            st.warning("Paste a playlist URL first.")
        else:
            pid = spotify_playlist.parse_playlist_id(url_to_use)
            if not pid:
                st.error("Invalid playlist URL.")
            else:
                out_dir = os.path.join("saved_tracks", f"playlist_{pid}")
                os.makedirs(out_dir, exist_ok=True)
                limit = int(playlist_track_limit) if playlist_track_limit and playlist_track_limit > 0 else None
                with st.spinner("Fetching and downloading tracks…"):
                    ss.playlist_results = spotify_playlist.run_pipeline(
                        url_to_use, out_dir, track_limit=limit
                    )
                    ss.playlist_url = url_to_use
                st.success(f"Done. Saved to `{out_dir}`.")

    if ss.playlist_results:
        st.write("**Results**")
        for i, r in enumerate(ss.playlist_results):
            track_name = r.get("track_name", "?")
            src_type = r.get("source_type")
            src_title = r.get("source_title") or ""
            src_url = r.get("source_url")
            if src_type == "yt":
                source_label = "YouTube" + (f": {src_title}" if src_title else "")
            elif src_type == "sc":
                source_label = "SoundCloud" + (f": {src_title}" if src_title else "")
            else:
                source_label = "—"
            status = r.get("status", "")
            if status == "ok":
                status_text = f"✓ `{r.get('path', '')}`"
            else:
                status_text = f"✗ {r.get('error', '')}"
            with st.container(border=True):
                st.markdown(f"**{track_name}**")
                st.caption(f"Source: {source_label}")
                if src_url and src_type:
                    st.caption(f"Link: {src_url}")
                st.write(status_text)

# --- Search single track tab ---
with tab_search:
    st.subheader("Search single track")

    with st.form('search'):
        row = st.columns([4, 1], vertical_alignment='bottom')
        with row[0]:
            search_term = st.text_input(
                label='Search Term',
                help='enter search term (track name - artist)'
            )
        with row[1]:
            submitted = st.form_submit_button(
                label='Search'
            )

    if submitted:
        yt_results_raw = search.search_youtube(search_term=search_term)
        sc_results_raw = search.search_soundcloud(search_term=search_term)
        ss.search_results = result.Result(
            search_term=search_term,
            yt_results=yt_results_raw,
            sc_results=sc_results_raw
        )
        start_job(s_result=ss.search_results, max_workers=10)

    if ss.search_results:
        col1, col2 = st.columns(2)
        with col1:
            for res in ss.search_results.yt_results:
                with st.container(border=True, gap=None):
                    with st.container(vertical_alignment='bottom', gap=None):
                        artist_col, download_col = st.columns([0.78, 0.22], vertical_alignment="center")
                        with artist_col:
                            st.markdown(f'*{res.artist}*')
                        with download_col:
                            if st.button('Save', key=f'save{res.artist}{res.title}{res.plays_formatted}'):
                                res.save_track(download_path='saved_tracks')
                    with st.container():
                        title_col, logo_col = st.columns([0.9, 0.1], vertical_alignment="center")
                        with title_col:
                            st.markdown(TITLE_FIX_MD.format(t=res.title), unsafe_allow_html=True)
                        with logo_col:
                            st.image(yt_logo)
                    st.space(size='small')
                    cover_col, views_len_col = st.columns([0.5, 0.5], vertical_alignment='center')
                    with cover_col:
                        st.image(res.cover)
                    with views_len_col:
                        st.markdown(res.duration_formatted)
                        st.markdown(f'**{res.plays_formatted}**')
                    st.space(size='small')
                    st.audio(res.get_audio(), format='audio/mpeg', end_time=60)
        with col2:
            for res in ss.search_results.sc_results:
                with st.container(border=True, gap=None):
                    with st.container(vertical_alignment='bottom', gap=None):
                        artist_col, download_col = st.columns([0.78, 0.22], vertical_alignment="center")
                        with artist_col:
                            st.markdown(f'*{res.artist}*')
                        with download_col:
                            if st.button('Save', key=f'save_sc_{res.artist}{res.title}{res.plays_formatted}'):
                                res.save_track(download_path='saved_tracks')
                    with st.container():
                        title_col, logo_col = st.columns([0.9, 0.1], vertical_alignment="center")
                        with title_col:
                            st.markdown(TITLE_FIX_MD.format(t=res.title), unsafe_allow_html=True)
                        with logo_col:
                            st.image(sc_logo)
                    st.space(size='small')
                    cover_col, views_len_col = st.columns([0.5, 0.5], vertical_alignment='center')
                    with cover_col:
                        st.image(res.cover)
                    with views_len_col:
                        st.markdown(res.duration_formatted)
                        st.markdown(f'**{res.plays_formatted}** plays')
                    st.space(size='small')
                    st.audio(res.get_audio(), format='audio/mpeg', end_time=60)

    if st.button('Purge Cached Files', key='purge_cached'):
        cur_id = None
        if ss.search_results:
            cur_id = ss.search_results.id
        util.remove_all_except_current(cur_id=cur_id, download_path=result.Result._DL_PATH)

# Progress bar and job_running at page level
bar = st.progress(0 if st.session_state.total == 0 else st.session_state.done / max(1, st.session_state.total))

if ss.job_running:
    # Drain ALL available messages this pass (no time window)
    while True:
        try:
            kind, idx, payload = ss.q.get_nowait()
        except queue.Empty:
            break

        if kind == "progress":
            if 0 <= idx < len(ss.results) and ss.results[idx] is None:
                ss.results[idx] = payload
                ss.done += 1
        elif kind == "error":
            ss.errors[idx] = payload
            # mark slot as done (so the bar advances)
            if 0 <= idx < len(ss.results) and ss.results[idx] is None:
                ss.results[idx] = f"ERROR: {payload}"
                ss.done += 1

    # Update progress + status
    if ss.total > 0:
        bar.progress(ss.done / ss.total)
        # status.write(f"Processed {ss.done}/{ss.total}")
    else:
        # status.warning("Starting…")
        pass
    
#    with log:
#        for i, res in enumerate(ss.results):
#            if res is None:
#                st.write(f"{i+1}. …working…")
#            elif isinstance(res, str) and res.startswith("ERROR:"):
#                st.error(f"{i+1}. {res}")
#            else:
#                st.write(f"{i+1}. {res}")
    # Finish or keep refreshing
    if ss.done >= ss.total and ss.total > 0:
        # status.success("All done!")
        bar.progress(1.0)
        ss.job_running = False
        if ss.executor:
            ss.executor.shutdown(wait=False)
            ss.executor = None
        # ok now add containers of fields
        # st.text(ss.search_results.get_results()[0].title)
    else:
        # keep heartbeat going
        time.sleep(0.2)
        do_rerun()
        st.stop()   # IMPORTANT: end current run immediately after scheduling rerun
else:
    # idle view
    if ss.items_snapshot:
        pass
        # status.info(f"Idle. Last run finished: {ss.done}/{ss.total}.")
        
#        with log:
#            for i, res in enumerate(ss.results):
#                if res is None:
#                    st.write(f"{i+1}. —")
#                elif isinstance(res, str) and res.startswith("ERROR:"):
#                    st.error(f"{i+1}. {res}")
#                else:
#                    st.write(f"{i+1}. {res}")
#    else:
#       status.write("Idle. Submit a search to begin.")
    