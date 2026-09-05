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
        <div class="navbar">
            <div class="navbar-brand">
                <div class="navbar-logo">✉</div>
                <div class="navbar-brand-text">
                    <div class="brand-name">Mail Extractor</div>
                    <div class="brand-sub">mailextractor.in</div>
                </div>
            </div>
            <div class="navbar-links">
                <a href="#tool">Tool</a>
                <a href="#features">Features</a>
                <a href="#faq">FAQ</a>
            </div>
            <a class="navbar-cta" href="#tool">✨ Start extracting</a>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero() -> None:
    st.markdown(
        """
        <div class="hero">
            <div class="hero-badge">Free · No sign-up · Runs entirely in your browser</div>
            <h1>Extract every <span class="highlight">email address</span> from any text, file or page</h1>
            <p class="hero-sub">
                Paste content, drop a file or fetch a URL — get a clean, de-duplicated list of emails
                with domain stats and one-click CSV export. Instantly.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
