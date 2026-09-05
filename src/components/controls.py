import streamlit as st
from src.utils.constants import SEPARATORS, OUTPUT_FORMATS, EXTRACTION_TYPES, GENERIC_EMAIL_PREFIXES


def render_controls() -> None:
    with st.expander("Advanced options"):
        col1, col2 = st.columns(2)

        with col1:
            st.selectbox("Output Format", OUTPUT_FORMATS, key="output_format", index=0)
            st.selectbox("Separator", list(SEPARATORS.keys()), key="separator")

        with col2:
            st.selectbox("Extraction Type", EXTRACTION_TYPES, key="extraction_type")
            st.multiselect(
                label="Prefix filter",
                options=GENERIC_EMAIL_PREFIXES,
                default=st.session_state.get("email_prefix_filter", []),
                key="email_prefix_filter",
                placeholder="All emails — select prefixes to filter...",
            )

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.checkbox("Sort alphabetically", key="sort_alphabetically")
        with c2:
            st.checkbox("Gmail only", key="gmail_only")
        with c3:
            st.checkbox("Hide directories", key="hide_directory", value=True)
        with c4:
            st.checkbox("Must have email", key="hide_no_email", value=True)
