import io
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime

from src.core.yelp_api import search_businesses, parse_results
from src.utils.exporters import clipboard_html


def _init_state() -> None:
    if "osm_results" not in st.session_state:
        st.session_state.osm_results = []
    if "osm_total" not in st.session_state:
        st.session_state.osm_total = 0
    if "osm_pending" not in st.session_state:
        st.session_state.osm_pending = False


def _request_search() -> None:
    st.session_state.osm_pending = True


def _results_to_df(results: list[dict]) -> pd.DataFrame:
    if not results:
        return pd.DataFrame()
    df = pd.DataFrame(results)
    col_order = [
        "name", "phone", "email", "website", "categories",
        "address", "city", "state", "zip_code", "url",
    ]
    existing = [c for c in col_order if c in df.columns]
    return df[existing]


def _render_summary(results: list[dict], total: int) -> None:
    with_phone = sum(1 for r in results if r.get("phone"))
    with_email = sum(1 for r in results if r.get("email"))
    with_website = sum(1 for r in results if r.get("website"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Found", total)
    c2.metric("With Phone", with_phone)
    c3.metric("With Email", with_email)
    c4.metric("With Website", with_website)


def _render_export(df: pd.DataFrame) -> None:
    tsv_text = df.to_csv(sep="\t", index=False)
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")

    copy_col, csv_col, xl_col = st.columns(3)

    with copy_col:
        components.html(
            clipboard_html(tsv_text, btn_id="copy_osm"),
            height=52,
        )
    with csv_col:
        st.download_button(
            "Download CSV",
            data=csv_bytes,
            file_name=f"osm_leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
            key="osm_dl_csv",
        )
    with xl_col:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="OSM Leads")
            ws = writer.sheets["OSM Leads"]
            for col in ws.columns:
                max_len = max((len(str(c.value)) if c.value else 0) for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 70)
        st.download_button(
            "Download Excel",
            data=buf.getvalue(),
            file_name=f"osm_leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="osm_dl_xlsx",
        )


def render_yelp_leads() -> None:
    _init_state()

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### Local Business Search (OpenStreetMap)")
    st.caption("Find businesses by location and type using free OpenStreetMap data. No API key needed.")

    _LOCATIONS = [
        "",
        # India
        "Delhi, India", "Mumbai, India", "Bangalore, India", "Hyderabad, India",
        "Chennai, India", "Kolkata, India", "Pune, India", "Ahmedabad, India",
        "Jaipur, India", "Lucknow, India", "Chandigarh, India", "Indore, India",
        "Nagpur, India", "Surat, India", "Kochi, India", "Bhopal, India",
        # USA
        "New York, NY", "Los Angeles, CA", "Chicago, IL", "Houston, TX",
        "Austin, TX", "San Francisco, CA", "Miami, FL", "Seattle, WA",
        "Denver, CO", "Boston, MA", "Dallas, TX", "Atlanta, GA",
        # UK
        "London, UK", "Manchester, UK", "Birmingham, UK",
        # Other
        "Toronto, Canada", "Sydney, Australia", "Dubai, UAE", "Singapore",
    ]

    _BUSINESS_TYPES = [
        "",
        "Restaurant", "Cafe", "Coffee Shop", "Bar",
        "Doctor", "Dentist", "Chiropractor", "Veterinary",
        "Plumber", "Electrician", "Car Repair", "Mechanic",
        "Lawyer", "Attorney", "Accountant", "Insurance", "Real Estate",
        "Hair Salon", "Barber", "Nail Salon", "Spa",
        "Gym", "Hotel",
        "Bakery", "Florist", "Butcher",
        "Laundry", "Pet Grooming",
    ]

    col_loc, col_type = st.columns(2)
    with col_loc:
        selected_loc = st.selectbox(
            "Location",
            _LOCATIONS,
            format_func=lambda x: x if x else "— Select a location —",
            key="osm_location_select",
        )
        custom_loc = st.text_input(
            "Or type a custom location",
            placeholder="e.g. Coimbatore, India",
            key="osm_location_custom",
        )
        location = custom_loc.strip() if custom_loc.strip() else selected_loc

    with col_type:
        selected_type = st.selectbox(
            "Business Type",
            _BUSINESS_TYPES,
            format_func=lambda x: x if x else "— Select a type —",
            key="osm_term_select",
        )
        custom_type = st.text_input(
            "Or type a custom business type",
            placeholder="e.g. pharmacy, tailor",
            key="osm_term_custom",
        )
        term = custom_type.strip() if custom_type.strip() else selected_type

    col_limit, col_contact, _ = st.columns([1, 1, 2])
    with col_limit:
        limit = st.selectbox("Max Results", [10, 20, 50, 100], index=1, key="osm_limit")
    with col_contact:
        contact_only = st.checkbox("Only with contact info", value=True, key="osm_contact_only")

    st.button(
        "Search Businesses",
        type="primary",
        use_container_width=True,
        key="osm_search_btn",
        on_click=_request_search,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.osm_pending:
        st.session_state.osm_pending = False
        if not location:
            st.warning("Please enter a location.")
        elif not term or not term.strip():
            st.warning("Please enter a business type (e.g. plumber, restaurant).")
        else:
            progress = st.progress(0, text="Searching OpenStreetMap...")

            def _update(done, total):
                pct = min(done / total, 1.0) if total > 0 else 0
                progress.progress(pct, text=f"Found {done}/{total} businesses...")

            try:
                data = search_businesses(
                    location=location,
                    term=term,
                    limit=limit,
                    with_contact_only=contact_only,
                    progress_callback=_update,
                )
                progress.empty()

                if data.get("error"):
                    st.error(data["error"])
                    return

                st.session_state.osm_results = parse_results(data)
                st.session_state.osm_total = data.get("total", 0)

                if not st.session_state.osm_results:
                    st.info("No businesses found. Try a broader location or different search term.")
            except Exception as e:
                progress.empty()
                st.error(f"Search error: {e}")
                return

    if st.session_state.osm_results:
        results = st.session_state.osm_results

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Summary")
        _render_summary(results, st.session_state.osm_total)
        st.markdown("</div>", unsafe_allow_html=True)

        df = _results_to_df(results)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Results")
        st.dataframe(df, use_container_width=True, hide_index=True)
        _render_export(df)
        st.markdown("</div>", unsafe_allow_html=True)
