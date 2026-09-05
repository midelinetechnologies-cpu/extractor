import io
import re
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime

from src.core.lead_scraper import LeadScraper
from src.utils.exporters import clipboard_html
from src.utils.db import push_lead_cards


def _init_lead_state() -> None:
    if "lead_results" not in st.session_state:
        st.session_state.lead_results = []
    if "lead_pending" not in st.session_state:
        st.session_state.lead_pending = False


def _request_extract() -> None:
    st.session_state.lead_pending = True


def _parse_urls(raw: str) -> list[str]:
    if not raw or not raw.strip():
        return []
    parts = re.split(r'[,;\n\r]+', raw)
    return [p.strip() for p in parts if p.strip()]


def _results_to_df(results: list[dict]) -> pd.DataFrame:
    rows = []
    for r in results:
        rows.append({
            'Domain': r.get('domain', r.get('url', '')),
            'Organization': r.get('org_name', ''),
            'Business Type': r.get('business_type', ''),
            'Confidence': f"{r.get('business_confidence', 0)}%",
            'Industry': r.get('industry', ''),
            'Offerings': '; '.join(r.get('offerings', [])),
            'Description': r.get('description', ''),
            'Emails': '; '.join(r.get('emails', [])),
            'Phones': '; '.join(r.get('phones', [])),
            'Address': ' | '.join(r.get('addresses', [])),
            'Facebook': r.get('social_links', {}).get('facebook', ''),
            'Twitter': r.get('social_links', {}).get('twitter', ''),
            'LinkedIn': r.get('social_links', {}).get('linkedin', ''),
            'Instagram': r.get('social_links', {}).get('instagram', ''),
            'YouTube': r.get('social_links', {}).get('youtube', ''),
            'Tech Stack': '; '.join(r.get('tech_stack', [])),
            'Pages Crawled': r.get('pages_crawled', 0),
            'Status': r.get('status', ''),
        })
    return pd.DataFrame(rows)


def _render_summary(results: list[dict]) -> None:
    total = len(results)
    success = sum(1 for r in results if r.get('status') == 'success')
    failed = total - success
    has_email = sum(1 for r in results if r.get('emails'))

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total URLs", total)
    col2.metric("Successful", success)
    col3.metric("Failed", failed)
    col4.metric("With Emails", has_email)


def _render_lead_cards(results: list[dict]) -> None:
    success_results = [r for r in results if r.get('status') == 'success']
    if not success_results:
        st.info("No websites could be reached.")
        return

    for r in success_results:
        with st.expander(f"**{r.get('org_name', r.get('domain', 'Unknown'))}** — {r.get('business_type', 'Unknown')}", expanded=False):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Domain:** {r.get('domain', '')}")
                st.markdown(f"**Type:** {r.get('business_type', 'N/A')} ({r.get('business_confidence', 0)}%)")
                if r.get('secondary_type'):
                    st.markdown(f"**Also:** {r['secondary_type']}")
                st.markdown(f"**Industry:** {r.get('industry', 'N/A')}")
                if r.get('offerings'):
                    st.markdown(f"**Offerings:** {', '.join(r['offerings'][:8])}")
                if r.get('tech_stack'):
                    st.markdown(f"**Tech Stack:** {', '.join(r['tech_stack'])}")

            with c2:
                emails = r.get('emails', [])
                st.markdown(f"**Emails:** {', '.join(emails) if emails else 'None found'}")
                phones = r.get('phones', [])
                st.markdown(f"**Phones:** {', '.join(phones) if phones else 'None found'}")
                addresses = r.get('addresses', [])
                if addresses:
                    st.markdown(f"**Address:** {addresses[0]}")
                social = r.get('social_links', {})
                if social:
                    links = [f"[{k.title()}]({v})" for k, v in social.items()]
                    st.markdown(f"**Social:** {' | '.join(links)}")
                st.markdown(f"**Pages crawled:** {r.get('pages_crawled', 0)}")

            if r.get('description'):
                st.caption(r['description'][:200])


def _render_export_buttons(df: pd.DataFrame) -> None:
    tsv_text = df.to_csv(sep='\t', index=False)
    csv_bytes = df.to_csv(index=False).encode('utf-8-sig')

    copy_col, txt_col, xl_col = st.columns(3)

    with copy_col:
        components.html(
            clipboard_html(tsv_text, btn_id="copy_leads"),
            height=52,
        )
    with txt_col:
        st.download_button(
            "Download TXT",
            data=tsv_text.encode('utf-8'),
            file_name=f"leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True,
            key="le_dl_txt",
        )
    with xl_col:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Leads")
            ws = writer.sheets["Leads"]
            for col in ws.columns:
                max_len = max((len(str(c.value)) if c.value else 0) for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 70)
        st.download_button(
            "Download Excel",
            data=buf.getvalue(),
            file_name=f"leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="le_dl_xlsx",
        )


def render_lead_extractor() -> None:
    _init_lead_state()

    # ── Input ──
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### Enter URLs to Extract Leads")

    url_input = st.text_area(
        "Enter URLs (one per line or comma-separated):",
        placeholder="example.com, another-site.io\nhttps://somecompany.com",
        height=140,
        key="le_input",
    )

    col_btn, col_workers = st.columns([3, 1])
    with col_btn:
        st.button(
            "Extract Leads",
            type="primary",
            key="le_extract",
            use_container_width=True,
            on_click=_request_extract,
        )
    with col_workers:
        max_workers = st.number_input("Threads", min_value=1, max_value=20, value=5, key="le_workers")

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Run extraction ──
    if st.session_state.lead_pending:
        st.session_state.lead_pending = False
        urls = _parse_urls(url_input)
        if not urls:
            st.warning("Please enter at least one URL.")
        else:
            progress_bar = st.progress(0, text="Extracting leads...")

            def update_progress(done, total):
                progress_bar.progress(
                    done / total,
                    text=f"Processed {done}/{total} URLs",
                )

            scraper = LeadScraper()
            results = scraper.process_urls(
                urls,
                max_workers=max_workers,
                progress_callback=update_progress,
            )
            progress_bar.empty()

            st.session_state.lead_results = results

            try:
                saved = push_lead_cards(results)
                st.toast(f"Saved {saved} lead cards to DB")
            except Exception as e:
                st.warning(f"Could not save to DB: {e}")

    # ── Results ──
    if st.session_state.lead_results:
        results = st.session_state.lead_results

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Summary")
        _render_summary(results)
        st.markdown("</div>", unsafe_allow_html=True)

        # Lead cards
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Lead Cards")
        _render_lead_cards(results)
        st.markdown("</div>", unsafe_allow_html=True)

        # Full data table
        df = _results_to_df(results)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Full Results Table")
        st.dataframe(df, use_container_width=True, hide_index=True)

        _render_export_buttons(df)
        st.markdown("</div>", unsafe_allow_html=True)
