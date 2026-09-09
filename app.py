import streamlit as st

st.set_page_config(
    page_title="Mail Extractor – mailextractor.in",
    page_icon="📧",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from src.styles import load_css
from src.utils.session_state import init_session_state
from src.components.header import render_header
from src.components.input_section import render_input_section
from src.components.controls import render_controls
from src.components.output_section import render_output_section
from src.components.url_validator import render_url_validator
from src.components.lead_extractor_ui import render_lead_extractor


def main() -> None:
    load_css()
    init_session_state()

    render_header()

    tab_extractor, tab_url_checker, tab_lead = st.tabs(
        ["📧 Mail Extractor", "🔗 URL Validator", "🏢 Lead Extractor"]
    )

    with tab_extractor:
        left, right = st.columns([1, 1], gap="large")
        with left:
            render_input_section()
            render_controls()
        with right:
            render_output_section()

    with tab_url_checker:
        render_url_validator()

    with tab_lead:
        render_lead_extractor()


if __name__ == "__main__":
    main()
