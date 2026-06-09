import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from src.core.extractor import nlp_available
from src.utils.constants import FORMAT_COLUMNS, SEPARATORS
from src.utils.exporters import clipboard_html, to_csv_bytes
from src.utils.db import push_entity_map

_NER_TYPES = {"Names", "Organizations", "All"}


def _split_comma_values(cell: str) -> list[str]:
    if not cell:
        return []
    return [part.strip() for part in str(cell).split(",") if part.strip()]


def _filtered_sorted(items: list[str], label: str = "") -> list[str]:
    if st.session_state.get("gmail_only") and label in ("emails", "email"):
        items = [i for i in items if i.endswith("@gmail.com")]
    q = st.session_state.filter_query.strip().lower()
    if q:
        items = [i for i in items if q in i.lower()]
    if st.session_state.sort_alphabetically:
        items = sorted(items)
    return items


def _render_result_block(items: list[str], label: str) -> None:
    items = _filtered_sorted(items, label)
    separator = SEPARATORS[st.session_state.separator]

    count = len(items)
    noun = label.rstrip("s") + ("s" if count != 1 else "")

    st.markdown(
        f'<div class="counter-badge">{count} {noun} found</div>',
        unsafe_allow_html=True,
    )

    if not items:
        st.markdown(
            '<div class="empty-state"><p>No results. Try adjusting your filter.</p></div>',
            unsafe_allow_html=True,
        )
        return

    text_output = separator.join(items)
    st.code(text_output, language=None)

    copy_col, dl_col = st.columns(2)
    with copy_col:
        components.html(clipboard_html(text_output, btn_id=f"copy_{label}"), height=52)
    with dl_col:
        st.download_button(
            "Download CSV",
            data=to_csv_bytes(items, label.rstrip("s")),
            file_name=f"extracted_{label}.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"dl_{label}",
        )


def _render_entity_map() -> None:
    if not nlp_available():
        st.warning(
            "spaCy model not found. Run: `python -m spacy download en_core_web_sm`",
            icon="⚠️",
        )
        return

    rows: list[dict] = st.session_state.entity_map
    if st.session_state.get("hide_no_contact"):
        rows = [r for r in rows if r.get("Emails") or r.get("URLs")]
    if not rows:
        st.markdown(
            '<div class="empty-state"><p>No entities with contact info found in the same block.</p></div>',
            unsafe_allow_html=True,
        )
        return

    fmt = st.session_state.output_format
    all_cols = ["Name", "URLs", "Emails", "Phones"]
    show_cols = FORMAT_COLUMNS.get(fmt, all_cols)

    df_full = pd.DataFrame(rows, columns=["Name", "Emails", "Phones", "URLs"])

    if st.session_state.get("gmail_only") and "Emails" in show_cols:

        def _filter_gmails(cell: str) -> str:
            return ", ".join(e for e in cell.split(", ") if e.endswith("@gmail.com"))

        df_full["Emails"] = df_full["Emails"].apply(_filter_gmails)

    df = df_full[[c for c in show_cols if c in df_full.columns]]

    contact_cols = [c for c in show_cols if c != "Name"]
    if contact_cols:
        df = df[df[contact_cols].apply(lambda r: r.str.strip().any(), axis=1)]

    if df.empty:
        st.info("No results match the current format or filter.")
        return

    separator = SEPARATORS[st.session_state.separator]

    for col in ("Emails", "Phones", "URLs"):
        if col in df.columns:
            split_series = df[col].apply(_split_comma_values)
            max_items = int(split_series.apply(len).max())
            if max_items > 1:
                insert_at = df.columns.get_loc(col)
                expanded = pd.DataFrame(
                    {
                        f"{col} {idx}": split_series.apply(
                            lambda values, i=idx - 1: values[i] if i < len(values) else ""
                        )
                        for idx in range(1, max_items + 1)
                    }
                )
                left = df.iloc[:, :insert_at]
                right = df.iloc[:, insert_at + 1 :]
                df = pd.concat([left, expanded, right], axis=1)
            else:
                df[col] = split_series.apply(lambda values: values[0] if values else "")

    st.markdown(
        f'<div class="counter-badge">{len(df)} {"entity" if len(df) == 1 else "entities"} - {fmt}</div>',
        unsafe_allow_html=True,
    )

    st.dataframe(df, use_container_width=True, hide_index=True)

    tsv_output = df.to_csv(sep="\t", index=False)

    copy_col, txt_col = st.columns(2)
    with copy_col:
        components.html(clipboard_html(tsv_output, btn_id="copy_entity_map"), height=52)
    with txt_col:
        st.download_button(
            "Download TXT",
            data=tsv_output.encode("utf-8"),
            file_name="entity_map.txt",
            mime="text/plain",
            use_container_width=True,
            key="dl_map_txt",
        )

    st.download_button(
        "Download CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="entity_map.csv",
        mime="text/csv",
        use_container_width=True,
        key="dl_map",
    )

    if st.button("Send to Database", use_container_width=True, key="send_db"):
        try:
            n = push_entity_map(st.session_state.entity_map)
            st.success(f"{n} record{'s' if n != 1 else ''} saved to database.")
        except Exception as e:
            st.error(f"Database error: {e}")


def _nlp_warning() -> None:
    st.warning(
        "spaCy model not found. Run: `python -m spacy download en_core_web_sm`",
        icon="⚠️",
    )


def render_output_section() -> None:
    if not st.session_state.has_extracted:
        st.markdown(
            '<div class="card"><div class="empty-state"><p>Paste your text above and click <strong>Extract</strong> to get started.</p></div></div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### Results")
    _render_entity_map()
    st.markdown("</div>", unsafe_allow_html=True)
