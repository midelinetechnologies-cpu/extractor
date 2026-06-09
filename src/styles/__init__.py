import os
import streamlit as st


def load_css() -> None:
    css_path = os.path.join(os.path.dirname(__file__), "custom.css")
    with open(css_path, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
