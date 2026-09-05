import streamlit as st
import requests as req
from src.core.extractor import get_extractor
from src.core.mapper import build_entity_map
from src.utils.session_state import clear_all
from src.utils.logger import log_call
from src.utils.db import push_entity_map

_SAMPLE_TEXT = """\
Company: TechStart Solutions
Website: https://techstart.io
Contact: john@techstart.io, sarah@techstart.io
Phone: +1-555-0123

Acme Corp — https://acme.com
Sales: sales@acme.com
General: info@acme.com
Support: support@acme.com
Phone: +1 800 555 0199

GlobalTech Industries
https://globaltech.net
careers@globaltech.net
hr@globaltech.net
+44 20 7946 0958

Jane Doe — Marketing Director
jane.doe@megacorp.net
https://megacorp.net

Freelancer Portfolio
https://jsmith.dev
hello@jsmith.dev
john.smith@gmail.com"""


def _request_extract() -> None:
    st.session_state._pending_extract = True


def _load_sample() -> None:
    st.session_state.input_text = _SAMPLE_TEXT
    st.session_state._pending_extract = True


@log_call
def _run_extract() -> None:
    extractor = get_extractor()
    text: str = st.session_state.input_text
    dedupe: bool = st.session_state.remove_duplicates
    etype: str = st.session_state.get("extraction_type", "All")
    st.session_state.emails = (
        extractor.extract_emails(text, dedupe) if etype in ("Emails", "All") else []
    )
    st.session_state.urls = (
        extractor.extract_urls(text, dedupe) if etype in ("URLs", "All") else []
    )
    st.session_state.phones = (
        extractor.extract_phones(text, dedupe) if etype in ("Phone Numbers", "All") else []
    )
    st.session_state.names = (
        extractor.extract_names(text, dedupe) if etype in ("Names", "All") else []
    )
    st.session_state.orgs = (
        extractor.extract_orgs(text, dedupe) if etype in ("Organizations", "All") else []
    )
    st.session_state.entity_map = build_entity_map(
        text,
        hide_directory=st.session_state.get("hide_directory", True),
        hide_no_email=st.session_state.get("hide_no_email", True),
        hide_no_name=st.session_state.get("hide_no_name", False),
    )
    st.session_state.has_extracted = True
    st.session_state.filter_query = ""
    st.session_state._pending_extract = False

    try:
        push_entity_map(st.session_state.entity_map)
    except Exception as e:
        st.warning(f"Data saved locally but DB insert failed: {e}")


def render_input_section() -> None:
    tab_paste, tab_upload, tab_fetch = st.tabs(
        ["📋 Paste Text", "📁 Upload File", "🔗 Fetch URL"]
    )

    with tab_paste:
        st.text_area(
            label="Paste text",
            label_visibility="collapsed",
            key="input_text",
            height=220,
            placeholder=(
                "Paste any text, HTML, document content or a page source here...\n\n"
                "Emails are detected live as you type."
            ),
        )
        char_count = len(st.session_state.get("input_text", ""))
        col_count, col_sample = st.columns([1, 1])
        with col_count:
            st.markdown(
                f'<div class="char-count">{char_count} characters</div>',
                unsafe_allow_html=True,
            )
        with col_sample:
            st.button("Load sample", on_click=_load_sample, use_container_width=True)

    with tab_upload:
        uploaded = st.file_uploader(
            "Upload a text file",
            type=["txt", "csv", "html", "htm", "log", "md"],
            label_visibility="collapsed",
        )
        if uploaded is not None:
            try:
                content = uploaded.read().decode("utf-8", errors="replace")
                st.session_state.input_text = content
                st.success(f"Loaded {uploaded.name} ({len(content)} characters)")
            except Exception as e:
                st.error(f"Could not read file: {e}")

    with tab_fetch:
        url_input = st.text_input(
            "URL to fetch",
            placeholder="https://example.com",
            label_visibility="collapsed",
        )
        if st.button("Fetch page", type="primary", use_container_width=True):
            if url_input.strip():
                with st.spinner("Fetching page..."):
                    try:
                        resp = req.get(
                            url_input.strip(),
                            timeout=15,
                            headers={"User-Agent": "Mozilla/5.0 MailExtractor/1.0"},
                        )
                        resp.raise_for_status()
                        st.session_state.input_text = resp.text
                        st.success(f"Fetched {len(resp.text)} characters")
                        st.session_state._pending_extract = True
                    except Exception as e:
                        st.error(f"Fetch failed: {e}")
            else:
                st.warning("Enter a URL first")

    btn_col, clear_col, dedup_col = st.columns([3, 1, 2])
    with btn_col:
        st.button(
            "🔍  Extract",
            on_click=_request_extract,
            use_container_width=True,
            type="primary",
            disabled=not st.session_state.get("input_text", "").strip(),
        )
    with clear_col:
        st.button("Clear", on_click=clear_all, use_container_width=True)
    with dedup_col:
        st.checkbox("Remove duplicates", key="remove_duplicates", value=True)

    if st.session_state.get("_pending_extract"):
        with st.spinner("Extracting..."):
            _run_extract()
