import streamlit as st
from src.core.extractor import get_extractor
from src.core.mapper import build_entity_map
from src.utils.session_state import clear_all


def _do_extract() -> None:
    extractor = get_extractor()
    text: str = st.session_state.input_text
    dedupe: bool = st.session_state.remove_duplicates
    etype: str = st.session_state.extraction_type

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
        hide_directory=st.session_state.hide_directory,
        hide_no_email=st.session_state.hide_no_email,
        hide_no_name=st.session_state.get("hide_no_name", False),
    )
    st.session_state.has_extracted = True
    st.session_state.filter_query = ""


def render_input_section() -> None:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### 📝 Input Text")

    st.text_area(
        label="Paste text",
        label_visibility="collapsed",
        key="input_text",
        height=260,
        placeholder=(
            "Paste your text here…\n\n"
            "Emails, URLs, and phone numbers will be detected automatically."
        ),
    )

    col_btn, col_clear, col_dedup = st.columns([3, 1, 2])

    with col_btn:
        st.button(
            "🔍  Extract",
            on_click=_do_extract,
            use_container_width=True,
            type="primary",
            disabled=not st.session_state.get("input_text", "").strip(),
        )

    with col_clear:
        st.button("🗑️  Clear", on_click=clear_all, use_container_width=True)

    with col_dedup:
        st.checkbox("Remove duplicates", key="remove_duplicates", value=True)

    st.markdown("</div>", unsafe_allow_html=True)
