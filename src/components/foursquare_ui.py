import io
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime

from src.core.foursquare import search_places, CATEGORY_MAP
from src.utils.exporters import clipboard_html

_LOCATIONS = [
    "",
    "Delhi, India", "Mumbai, India", "Bangalore, India", "Hyderabad, India",
    "Chennai, India", "Kolkata, India", "Pune, India", "Ahmedabad, India",
    "Jaipur, India", "Lucknow, India", "Chandigarh, India", "Indore, India",
    "Nagpur, India", "Surat, India", "Kochi, India", "Bhopal, India",
    "New York, USA", "Los Angeles, USA", "Chicago, USA", "Houston, USA",
    "Austin, USA", "San Francisco, USA", "Miami, USA", "Seattle, USA",
    "Denver, USA", "Boston, USA", "Dallas, USA", "Atlanta, USA",
    "London, UK", "Manchester, UK", "Birmingham, UK",
    "Toronto, Canada", "Sydney, Australia", "Dubai, UAE", "Singapore",
]

_CATEGORIES = [""] + sorted(CATEGORY_MAP.keys())

_RADIUS_OPTIONS = {
    "1 km": 1000,
    "5 km": 5000,
    "10 km": 10000,
    "25 km": 25000,
    "50 km": 50000,
}


def _init_state() -> None:
    if "fsq_results" not in st.session_state:
        st.session_state.fsq_results = []
    if "fsq_total" not in st.session_state:
        st.session_state.fsq_total = 0
    if "fsq_pending" not in st.session_state:
        st.session_state.fsq_pending = False


def _request_search() -> None:
    st.session_state.fsq_pending = True


def _results_to_df(results: list[dict]) -> pd.DataFrame:
    if not results:
        return pd.DataFrame()
    df = pd.DataFrame(results)
    col_order = [
        "name", "phone", "email", "website", "categories",
        "address", "city", "state", "postcode", "country", "rating",
    ]
    existing = [c for c in col_order if c in df.columns]
    return df[existing]


def _render_summary(results: list[dict]) -> None:
    with_phone = sum(1 for r in results if r.get("phone"))
    with_email = sum(1 for r in results if r.get("email"))
    with_website = sum(1 for r in results if r.get("website"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Found", len(results))
    c2.metric("With Phone", with_phone)
    c3.metric("With Email", with_email)
    c4.metric("With Website", with_website)


def _render_export(df: pd.DataFrame) -> None:
    tsv_text = df.to_csv(sep="\t", index=False)
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")

    copy_col, csv_col, xl_col = st.columns(3)

    with copy_col:
        components.html(
            clipboard_html(tsv_text, btn_id="copy_fsq"),
            height=52,
        )
    with csv_col:
        st.download_button(
            "Download CSV",
            data=csv_bytes,
            file_name=f"foursquare_leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
            key="fsq_dl_csv",
        )
    with xl_col:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Foursquare Leads")
            ws = writer.sheets["Foursquare Leads"]
            for col in ws.columns:
                max_len = max((len(str(c.value)) if c.value else 0) for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 70)
        st.download_button(
            "Download Excel",
            data=buf.getvalue(),
            file_name=f"foursquare_leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="fsq_dl_xlsx",
        )


def render_foursquare_leads() -> None:
    _init_state()

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### Foursquare Lead Finder")
    st.caption(
        "Search businesses worldwide using Foursquare Places API. "
        "Free tier: 1,000 calls/day. Set FOURSQUARE_API_KEY in your .env file."
    )

    col_loc, col_type = st.columns(2)
    with col_loc:
        selected_loc = st.selectbox(
            "Location",
            _LOCATIONS,
            format_func=lambda x: x if x else "— Select a location —",
            key="fsq_location_select",
        )
        custom_loc = st.text_input(
            "Or type a custom location",
            placeholder="e.g. Coimbatore, India",
            key="fsq_location_custom",
        )
        location = custom_loc.strip() if custom_loc.strip() else selected_loc

    with col_type:
        category_key = st.selectbox(
            "Business Type",
            _CATEGORIES,
            format_func=lambda x: x if x else "— Select a type —",
            key="fsq_category_select",
        )
        custom_cat = st.text_input(
            "Or type a Foursquare category ID",
            placeholder="e.g. 13065 for Restaurant",
            key="fsq_category_custom",
        )
        final_category = custom_cat.strip() if custom_cat.strip() else category_key

    col_radius, col_limit, _ = st.columns([1, 1, 2])
    with col_radius:
        radius_label = st.selectbox(
            "Search Radius",
            list(_RADIUS_OPTIONS.keys()),
            index=2,
            key="fsq_radius",
        )
        radius = _RADIUS_OPTIONS[radius_label]
    with col_limit:
        limit = st.selectbox("Max Results", [10, 20, 50], index=2, key="fsq_limit")

    st.button(
        "Search Foursquare",
        type="primary",
        use_container_width=True,
        key="fsq_search_btn",
        on_click=_request_search,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.fsq_pending:
        st.session_state.fsq_pending = False
        if not location:
            st.warning("Please select or type a location.")
        elif not final_category:
            st.warning("Please select or type a business type.")
        else:
            progress = st.progress(0, text="Searching Foursquare...")

            def _update(done, total):
                pct = min(done / total, 1.0) if total > 0 else 0
                progress.progress(pct, text=f"Found {done} businesses...")

            try:
                data = search_places(
                    location=location,
                    category_key=final_category,
                    radius=radius,
                    limit=limit,
                    progress_callback=_update,
                )
                progress.empty()

                if data.get("error"):
                    st.error(data["error"])
                    return

                st.session_state.fsq_results = data.get("results", [])
                st.session_state.fsq_total = data.get("total", 0)

                if not st.session_state.fsq_results:
                    st.info("No businesses found. Try a larger radius or different category.")
            except ValueError as e:
                progress.empty()
                st.error(str(e))
                return
            except Exception as e:
                progress.empty()
                st.error(f"Search error: {e}")
                return

    if st.session_state.fsq_results:
        results = st.session_state.fsq_results

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Summary")
        _render_summary(results)
        st.markdown("</div>", unsafe_allow_html=True)

        col_fe, col_fp = st.columns(2)
        with col_fe:
            email_only = st.checkbox("Only with email", key="fsq_email_only")
        with col_fp:
            phone_only = st.checkbox("Only with phone", key="fsq_phone_only")

        filtered = results
        if email_only:
            filtered = [r for r in filtered if r.get("email")]
        if phone_only:
            filtered = [r for r in filtered if r.get("phone")]

        df = _results_to_df(filtered)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"#### Results ({len(filtered)} businesses)")
        st.dataframe(df, use_container_width=True, hide_index=True)
        _render_export(df)
        st.markdown("</div>", unsafe_allow_html=True)
