# "main" script
# has all the streamlit stuff (maybe make classes and stuff in other files.)
# just the declarative UI modules and high-level logic

import streamlit as st 

import search
import result
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue



ss = st.session_state
ss.setdefault("job_running", False)
ss.setdefault("q", queue.Queue())               # worker -> UI messages
ss.setdefault("results", [])                    # list aligned to items_snapshot
ss.setdefault("done", 0)
ss.setdefault("total", 0)
ss.setdefault("executor", None)
ss.setdefault("items_snapshot", None)           # frozen items for the current run

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
    search_results = result.Result(
        search_term=search_term,
        yt_results=yt_results_raw,
        sc_results=sc_results_raw
    )
    # download
    # search_results.download_all()
    start_job(s_result=search_results, max_workers=8)
    st.header(f'Showing Results for {search_term}')

status = st.empty()
bar = st.progress(0 if st.session_state.total == 0 else st.session_state.done / max(1, st.session_state.total))
log = st.container()

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
        status.write(f"Processed {ss.done}/{ss.total}")
    else:
        status.warning("Starting…")

    with log:
        for i, res in enumerate(ss.results):
            if res is None:
                st.write(f"{i+1}. …working…")
            elif isinstance(res, str) and res.startswith("ERROR:"):
                st.error(f"{i+1}. {res}")
            else:
                st.write(f"{i+1}. {res}")

    # Finish or keep refreshing
    if ss.done >= ss.total and ss.total > 0:
        status.success("All done!")
        bar.progress(1.0)
        ss.job_running = False
        if ss.executor:
            ss.executor.shutdown(wait=False)
            ss.executor = None
    else:
        # keep heartbeat going
        time.sleep(0.2)
        do_rerun()
        st.stop()   # IMPORTANT: end current run immediately after scheduling rerun
else:
    # idle view
    if ss.items_snapshot:
        status.info(f"Idle. Last run finished: {ss.done}/{ss.total}.")
        with log:
            for i, res in enumerate(ss.results):
                if res is None:
                    st.write(f"{i+1}. —")
                elif isinstance(res, str) and res.startswith("ERROR:"):
                    st.error(f"{i+1}. {res}")
                else:
                    st.write(f"{i+1}. {res}")
    else:
        status.write("Idle. Submit a search to begin.")