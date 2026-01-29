# "main" script
# has all the streamlit stuff (maybe make classes and stuff in other files.)
# just the declarative UI modules and high-level logic

import streamlit as st 

import search
import result
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import util


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



st.title('Track the Ripper')


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
    # search
    yt_results_raw = search.search_youtube(search_term=search_term)
    sc_results_raw = search.search_soundcloud(search_term=search_term)    
    # construct obj
    ss.search_results = result.Result(
        search_term=search_term,
        yt_results=yt_results_raw,
        sc_results=sc_results_raw
    )
    # display all names

    # download
    # search_results.download_all()
    start_job(s_result=ss.search_results, max_workers=10)

# status = st.empty()
bar = st.progress(0 if st.session_state.total == 0 else st.session_state.done / max(1, st.session_state.total))
# log = st.container()

#TODO: add option do download preview

if ss.search_results:
    # youtube
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
    # soundcloud
    with col2:
        for res in ss.search_results.sc_results:
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
    # likes
    # length, views
    # preview, download

# purge button deletes all files not associated with current query
if st.button('Purge Cached Files'):
    # get current state id
    cur_id = None
    if ss.search_results:
        cur_id = ss.search_results.id
    # remove all files in folder except one with current id
    util.remove_all_except_current(cur_id=cur_id, download_path=result.Result._DL_PATH)

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
    