import io
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import date, timedelta, datetime

from src.core.merchant_genius import search_stores
from src.utils.exporters import clipboard_html


def _init_mg_state() -> None:
    if "mg_results" not in st.session_state:
        st.session_state.mg_results = []
    if "mg_pending" not in st.session_state:
        st.session_state.mg_pending = False


def _request_search() -> None:
    st.session_state.mg_pending = True


def _results_to_df(results: list[dict]) -> pd.DataFrame:
    if not results:
        return pd.DataFrame()
    df = pd.DataFrame(results)
    col_order = [
        "name", "domain", "email", "phone",
        "currency", "language", "description", "platform",
    ]
    existing = [c for c in col_order if c in df.columns]
    return df[existing]


def _render_summary(results: list[dict]) -> None:
    with_email = sum(1 for r in results if r.get("email"))
    with_phone = sum(1 for r in results if r.get("phone"))
    currencies = set(r.get("currency", "") for r in results if r.get("currency"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Stores", len(results))
    c2.metric("With Email", with_email)
    c3.metric("With Phone", with_phone)
    c4.metric("Currencies", len(currencies))


def _render_export(df: pd.DataFrame) -> None:
    tsv_text = df.to_csv(sep="\t", index=False)
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")

    copy_col, csv_col, xl_col = st.columns(3)

    with copy_col:
        components.html(
            clipboard_html(tsv_text, btn_id="copy_mg"),
            height=52,
        )
    with csv_col:
        st.download_button(
            "Download CSV",
            data=csv_bytes,
            file_name=f"merchant_genius_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
            key="mg_dl_csv",
        )
    with xl_col:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="MG Leads")
            ws = writer.sheets["MG Leads"]
            for col in ws.columns:
                max_len = max((len(str(c.value)) if c.value else 0) for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 70)
        st.download_button(
            "Download Excel",
            data=buf.getvalue(),
            file_name=f"merchant_genius_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="mg_dl_xlsx",
        )


def _render_filters(results: list[dict]) -> list[dict]:
    col_email, col_lang = st.columns(2)
    with col_email:
        email_only = st.checkbox("Only with email", key="mg_email_only")
    with col_lang:
        languages = sorted(set(r.get("language", "") for r in results if r.get("language")))
        lang_filter = st.multiselect("Filter by language", languages, key="mg_lang_filter")

    filtered = results
    if email_only:
        filtered = [r for r in filtered if r.get("email")]
    if lang_filter:
        filtered = [r for r in filtered if r.get("language") in lang_filter]
    return filtered


def render_merchant_genius() -> None:
    _init_mg_state()

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### Merchant Genius — Shopify Store Directory")
    st.caption("Browse newly launched Shopify stores by date. Extracts store name, domain, email, phone, currency & language.")

    col_date, col_days = st.columns(2)
    with col_date:
        default_date = date.today() - timedelta(days=1)
        selected_date = st.date_input(
            "Start Date",
            value=default_date,
            max_value=date.today(),
            key="mg_date",
        )
    with col_days:
        days = st.selectbox(
            "Days to scrape",
            [1, 3, 5, 7],
            index=0,
            key="mg_days",
        )

    st.button(
        "Fetch Stores",
        type="primary",
        use_container_width=True,
        key="mg_search_btn",
        on_click=_request_search,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.mg_pending:
        st.session_state.mg_pending = False
        progress = st.progress(0, text="Fetching from Merchant Genius...")

        def _update(done, total):
            progress.progress(
                done / total,
                text=f"Scraped {done}/{total} date pages...",
            )

        try:
            results = search_stores(
                date_str=selected_date.isoformat(),
                days=days,
                progress_callback=_update,
            )
            progress.empty()
            st.session_state.mg_results = results
            if not results:
                st.info("No stores found for the selected date(s).")
        except Exception as e:
            progress.empty()
            st.error(f"Scraping error: {e}")
            return

    if st.session_state.mg_results:
        results = st.session_state.mg_results

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Summary")
        _render_summary(results)
        st.markdown("</div>", unsafe_allow_html=True)

        filtered = _render_filters(results)

        df = _results_to_df(filtered)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"#### Results ({len(filtered)} stores)")
        st.dataframe(df, use_container_width=True, hide_index=True)
        _render_export(df)
        st.markdown("</div>", unsafe_allow_html=True)
