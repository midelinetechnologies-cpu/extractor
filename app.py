import streamlit as st

st.set_page_config(
    page_title="Mail Extractor – mailextractor.in",
    page_icon="✉",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from src.styles import load_css
from src.utils.session_state import init_session_state
from src.components.header import render_header, render_hero
from src.components.input_section import render_input_section
from src.components.controls import render_controls
from src.components.output_section import render_output_section
from src.components.landing import render_features, render_faq, render_footer
from src.components.url_validator import render_url_validator


def main() -> None:
    load_css()
    init_session_state()

    render_header()
    render_hero()

    st.markdown('<div id="tool"></div>', unsafe_allow_html=True)

    left, right = st.columns([1, 1], gap="large")
    with left:
        render_input_section()
        render_controls()
    with right:
        render_output_section()

    with st.expander("🔗 URL Validator"):
        render_url_validator()

    render_features()
    render_faq()
    render_footer()


if __name__ == "__main__":
    main()
