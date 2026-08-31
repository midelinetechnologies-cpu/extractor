import io
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime
from typing import List

from src.core.website_scraper import ScrapedContact, scrape_multiple_urls
from src.utils.exporters import clipboard_html


def _init_ws_state() -> None:
    if "ws_results" not in st.session_state:
        st.session_state.ws_results = []
    if "ws_pending" not in st.session_state:
        st.session_state.ws_pending = False


def _request_scrape() -> None:
    st.session_state.ws_pending = True


def _build_dataframe(results: List[ScrapedContact]) -> pd.DataFrame:
    rows = []
    for r in results:
        rows.append({
            "Website": r.url,
            "Page Title": r.page_title,
            "Emails": ", ".join(r.emails) if r.emails else "",
            "Phones": ", ".join(r.phones) if r.phones else "",
            "Contact Names": ", ".join(r.names) if r.names else "",
            "Status": r.status,
        })
    return pd.DataFrame(rows)


def _render_summary(results: List[ScrapedContact]) -> None:
    total = len(results)
    ok = sum(1 for r in results if r.status == "OK")
    with_email = sum(1 for r in results if r.emails)
    with_phone = sum(1 for r in results if r.phones)
    with_name = sum(1 for r in results if r.names)
    total_emails = sum(len(r.emails) for r in results)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Sites", total)
    c2.metric("Fetched OK", ok)
    c3.metric("With Email", with_email)
    c4.metric("With Phone", with_phone)
    c5.metric("Total Emails", total_emails)


def _render_results_table(results: List[ScrapedContact]) -> None:
    df = _build_dataframe(results)
    if df.empty:
        return

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### Extracted Contacts")

    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        hide_empty = st.checkbox("Hide sites with no email", key="ws_hide_empty")
    with filter_col2:
        hide_failed = st.checkbox("Hide failed sites", key="ws_hide_failed")

    if hide_empty:
        df = df[df["Emails"] != ""]
    if hide_failed:
        df = df[df["Status"] == "OK"]

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Website": st.column_config.TextColumn("Website", width="medium"),
            "Page Title": st.column_config.TextColumn("Page Title", width="medium"),
            "Emails": st.column_config.TextColumn("Emails", width="large"),
            "Phones": st.column_config.TextColumn("Phones", width="medium"),
            "Contact Names": st.column_config.TextColumn("Names", width="medium"),
            "Status": st.column_config.TextColumn("Status", width="small"),
        },
    )

    all_emails = []
    for r in results:
        if hide_failed and r.status != "OK":
            continue
        all_emails.extend(r.emails)
    all_emails = list(dict.fromkeys(all_emails))

    if all_emails:
        st.markdown(f"**{len(all_emails)}** unique emails extracted")
        email_text = "\n".join(all_emails)
        st.code(email_text, language=None)

        copy_col, txt_col, xl_col = st.columns(3)
        with copy_col:
            components.html(
                clipboard_html(email_text, btn_id="ws_copy_emails"),
                height=52,
            )
        with txt_col:
            st.download_button(
                "Download TXT",
                data=email_text.encode("utf-8"),
                file_name=f"scraped_emails_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True,
                key="ws_dl_txt",
            )
        with xl_col:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Contacts")
                ws = writer.sheets["Contacts"]
                for col in ws.columns:
                    max_len = max((len(str(c.value)) if c.value else 0) for c in col)
                    ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 70)
            st.download_button(
                "Download Excel",
                data=buf.getvalue(),
                file_name=f"scraped_contacts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="ws_dl_xlsx",
            )

    st.markdown("</div>", unsafe_allow_html=True)


def render_website_extractor() -> None:
    _init_ws_state()

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### Extract Contacts from Websites")
    st.caption(
        "Paste a list of URLs below. The tool will visit each website "
        "(including /contact, /about pages) and extract emails, phone numbers, "
        "and contact names."
    )

    url_input = st.text_area(
        "Enter URLs (one per line, or comma-separated):",
        placeholder="https://example.com\nhttps://another-site.com\nhttps://business-website.com",
        height=140,
        key="ws_input",
    )

    opt_col1, opt_col2 = st.columns(2)
    with opt_col1:
        scrape_subpages = st.checkbox("Scan contact/about pages", value=True, key="ws_subpages")
    with opt_col2:
        max_workers = st.slider("Concurrent requests", 1, 10, 5, key="ws_workers")

    st.button(
        "Extract from Websites",
        type="primary",
        key="ws_extract",
        use_container_width=True,
        on_click=_request_scrape,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.ws_pending:
        st.session_state.ws_pending = False

        raw = url_input.strip()
        if not raw:
            st.warning("Please enter at least one URL.")
        else:
            urls = []
            for part in raw.replace(",", "\n").split("\n"):
                u = part.strip()
                if u:
                    urls.append(u)
            urls = list(dict.fromkeys(urls))

            if not urls:
                st.warning("Please enter at least one URL.")
            else:
                progress = st.progress(0, text="Scraping websites...")

                def update_progress(done, total):
                    progress.progress(
                        done / total,
                        text=f"Scraped {done}/{total} websites...",
                    )

                results = scrape_multiple_urls(
                    urls,
                    timeout=15,
                    max_workers=max_workers,
                    scrape_subpages=scrape_subpages,
                    progress_callback=update_progress,
                )
                progress.empty()
                st.session_state.ws_results = results

    if st.session_state.ws_results:
        results = st.session_state.ws_results

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Summary")
        _render_summary(results)
        st.markdown("</div>", unsafe_allow_html=True)

        _render_results_table(results)
