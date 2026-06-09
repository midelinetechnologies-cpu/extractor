import streamlit as st


def render_header() -> None:
    st.markdown(
        """
        <div class="header-card">
            <h1>📧 Email Extractor Pro</h1>
            <p>Extract, filter, and export emails, URLs, and phone numbers from any text</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
