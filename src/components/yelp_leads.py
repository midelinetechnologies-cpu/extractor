import io
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime

from src.core.yelp_api import search_businesses, parse_results
from src.utils.exporters import clipboard_html


def _init_yelp_state() -> None:
    if "yelp_results" not in st.session_state:
        st.session_state.yelp_results = []
    if "yelp_total" not in st.session_state:
        st.session_state.yelp_total = 0
    if "yelp_pending" not in st.session_state:
        st.session_state.yelp_pending = False


def _request_search() -> None:
    st.session_state.yelp_pending = True


def _results_to_df(results: list[dict]) -> pd.DataFrame:
    if not results:
        return pd.DataFrame()
    df = pd.DataFrame(results)
    col_order = [
        "name", "phone", "categories", "rating", "review_count",
        "address", "city", "state", "zip_code", "website", "url",
    ]
    existing = [c for c in col_order if c in df.columns]
    return df[existing]


def _render_summary(results: list[dict], total: int) -> None:
    with_phone = sum(1 for r in results if r.get("phone"))
    avg_rating = sum(r.get("rating", 0) for r in results) / len(results) if results else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Showing", len(results))
    c2.metric("Total on Yelp", total)
    c3.metric("With Phone", with_phone)
    c4.metric("Avg Rating", f"{avg_rating:.1f}")


def _render_export(df: pd.DataFrame) -> None:
    tsv_text = df.to_csv(sep="\t", index=False)
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")

    copy_col, csv_col, xl_col = st.columns(3)

    with copy_col:
        components.html(
            clipboard_html(tsv_text, btn_id="copy_yelp"),
            height=52,
        )
    with csv_col:
        st.download_button(
            "Download CSV",
            data=csv_bytes,
            file_name=f"yelp_leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
            key="yelp_dl_csv",
        )
    with xl_col:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Yelp Leads")
            ws = writer.sheets["Yelp Leads"]
            for col in ws.columns:
                max_len = max((len(str(c.value)) if c.value else 0) for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 70)
        st.download_button(
            "Download Excel",
            data=buf.getvalue(),
            file_name=f"yelp_leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="yelp_dl_xlsx",
        )


def render_yelp_leads() -> None:
    _init_yelp_state()

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### Yelp Business Search")
    st.caption("Search Yelp for local businesses by location and type. No API key needed.")

    col_loc, col_type = st.columns(2)
    with col_loc:
        location = st.text_input(
            "Location",
            placeholder="New York, NY  or  90210  or  Chicago, IL",
            key="yelp_location",
        )
    with col_type:
        term = st.text_input(
            "Business Type",
            placeholder="plumber, restaurant, dentist, lawyer ...",
            key="yelp_term",
        )

    col_limit, _ = st.columns([1, 3])
    with col_limit:
        limit = st.selectbox("Results", [10, 20, 30, 50], index=1, key="yelp_limit")

    st.button(
        "Search Yelp",
        type="primary",
        use_container_width=True,
        key="yelp_search_btn",
        on_click=_request_search,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.yelp_pending:
        st.session_state.yelp_pending = False
        if not location:
            st.warning("Please enter a location.")
        else:
            progress = st.progress(0, text="Searching Yelp...")

            def _update(done, total):
                progress.progress(done / total, text=f"Found {done}/{total} businesses...")

            try:
                data = search_businesses(
                    location=location,
                    term=term,
                    limit=limit,
                    progress_callback=_update,
                )
                progress.empty()
                st.session_state.yelp_results = parse_results(data)
                st.session_state.yelp_total = data.get("total", 0)
            except Exception as e:
                progress.empty()
                st.error(f"Yelp search error: {e}")
                return

    if st.session_state.yelp_results:
        results = st.session_state.yelp_results

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Summary")
        _render_summary(results, st.session_state.yelp_total)
        st.markdown("</div>", unsafe_allow_html=True)

        df = _results_to_df(results)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Results")
        st.dataframe(df, use_container_width=True, hide_index=True)
        _render_export(df)
        st.markdown("</div>", unsafe_allow_html=True)
