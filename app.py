import threading
import streamlit as st


def _start_api() -> None:
    import uvicorn
    from api import app as fastapi_app
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000, log_level="warning")


threading.Thread(target=_start_api, daemon=True).start()

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


def main() -> None:
    load_css()
    init_session_state()

    render_header()

    left, right = st.columns([1, 1], gap="large")

    with left:
        render_input_section()
        render_controls()

    with right:
        render_output_section()


if __name__ == "__main__":
    main()
