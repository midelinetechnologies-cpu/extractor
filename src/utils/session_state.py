import streamlit as st

_DEFAULTS: dict = {
    "input_text": "",
    "emails": [],
    "urls": [],
    "phones": [],
    "names": [],
    "orgs": [],
    "entity_map": [],
    "filter_query": "",
    "email_prefix_filter": [],
    "has_extracted": False,
}


def init_session_state() -> None:
    for key, val in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = val


def reset_results() -> None:
    st.session_state.emails = []
    st.session_state.urls = []
    st.session_state.phones = []
    st.session_state.names = []
    st.session_state.orgs = []
    st.session_state.entity_map = []
    st.session_state.has_extracted = False
    st.session_state.filter_query = ""


def clear_all() -> None:
    st.session_state.input_text = ""
    reset_results()
