import streamlit as st


def render_features() -> None:
    st.markdown(
        """
        <div class="features-section" id="features">
            <h2>Why Mail Extractor?</h2>
            <p class="features-sub">Built for speed, privacy and clean output.</p>
            <div class="features-grid">
                <div class="feature-card">
                    <div class="feature-icon speed">⚡</div>
                    <h3>Instant &amp; live</h3>
                    <p>Emails are detected as you type — no upload, no wait, no processing queue. Extraction happens in milliseconds.</p>
                </div>
                <div class="feature-card">
                    <div class="feature-icon privacy">🛡</div>
                    <h3>100% private</h3>
                    <p>Everything runs inside your browser. Your text, files and data never touch a server. Close the tab, it's gone.</p>
                </div>
                <div class="feature-card">
                    <div class="feature-icon export">⬇</div>
                    <h3>Export anywhere</h3>
                    <p>Copy with one click or download as CSV / TXT with domain and occurrence metadata for your CRM or sheet.</p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_faq() -> None:
    st.markdown(
        """
        <div class="faq-section" id="faq">
            <h2>Frequently asked questions</h2>

            <details class="faq-item">
                <summary>How does the email extractor work?</summary>
                <div class="faq-answer">
                    We scan your text, file content or fetched page HTML with a regex pattern compliant with RFC 5322.
                    Every match is normalised to lowercase, de-duplicated and counted, then shown with its domain and
                    whether it looks like a shared role account (info@, sales@, …).
                </div>
            </details>

            <details class="faq-item">
                <summary>Can I extract emails from a file?</summary>
                <div class="faq-answer">
                    Yes — switch to the "Upload File" tab and drop any .txt, .csv, or .html file. The content is read
                    locally and parsed the same way as pasted text.
                </div>
            </details>

            <details class="faq-item">
                <summary>Why does fetching a URL sometimes fail?</summary>
                <div class="faq-answer">
                    Some sites block automated requests, require JavaScript rendering, or return CAPTCHAs. If a fetch
                    fails, try copying the page source manually and pasting it into the text input instead.
                </div>
            </details>

            <details class="faq-item">
                <summary>Does it verify if emails are valid?</summary>
                <div class="faq-answer">
                    The extractor checks format validity against RFC 5322 and filters known-invalid TLDs, but it does
                    not perform SMTP verification or inbox checks. The output is syntactically valid addresses found
                    in your input.
                </div>
            </details>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_footer() -> None:
    st.markdown(
        """
        <div class="site-footer">
            <div class="footer-brand">
                <div class="footer-logo">✉</div>
                <span>Mail Extractor</span>
            </div>
            <div class="footer-copy">© 2026 mailextractor.in · All processing happens locally in your browser.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
