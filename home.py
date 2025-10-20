# "main" script
# has all the streamlit stuff (maybe make classes and stuff in other files.)
# just the declarative UI modules and high-level logic

import streamlit as st 

import search
import result

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
    st.header(f'Showing Results for {search_term}')

# col1, col2 = st.columns(2, vertical_alignment='center')



    