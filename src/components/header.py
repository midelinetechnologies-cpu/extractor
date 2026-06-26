import streamlit as st

_OG_TAGS = """
<head>
  <meta property="og:title"       content="Mail Extractor">
  <meta property="og:site_name"   content="mailextractor.in">
  <meta property="og:description" content="Extract emails, URLs, and phone numbers from any text — fast and free.">
  <meta property="og:url"         content="https://mailextractor.in">
  <meta property="og:type"        content="website">
  <meta name="application-name"   content="Mail Extractor">
  <meta name="twitter:title"      content="Mail Extractor">
  <meta name="twitter:description" content="Extract emails, URLs, and phone numbers from any text.">
</head>
"""


def render_header() -> None:
    st.markdown(_OG_TAGS, unsafe_allow_html=True)
    st.markdown(
        """
        <div class="header-card">
            <h1>📧 Mail Extractor</h1>
            <p>Extract, filter, and export emails, URLs, and phone numbers from any text</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
