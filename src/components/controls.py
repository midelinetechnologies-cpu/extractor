import streamlit as st
from src.utils.constants import SEPARATORS, OUTPUT_FORMATS, EXTRACTION_TYPES


def render_controls() -> None:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### ⚙️ Options")

    col1, col2 = st.columns(2)

    with col1:
        st.selectbox("Extraction Type", EXTRACTION_TYPES, key="extraction_type")
        st.selectbox("Separator", list(SEPARATORS.keys()), key="separator")

    with col2:
        st.selectbox(
            "Output Format",
            OUTPUT_FORMATS,
            key="output_format",
            index=0,
        )
        st.text_input(
            "Filter (contains)",
            key="filter_query",
            placeholder="e.g. gmail.com",
        )

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.checkbox("Sort alphabetically", key="sort_alphabetically")
    with c2:
        st.checkbox("Gmail only", key="gmail_only")
    with c3:
        st.checkbox("Hide directories", key="hide_directory", value=True)
    with c4:
        st.checkbox("Must have email", key="hide_no_email", value=True)
    with c5:
        st.checkbox("Hide empty email & URL", key="hide_no_contact", value=True)

    st.markdown("</div>", unsafe_allow_html=True)
