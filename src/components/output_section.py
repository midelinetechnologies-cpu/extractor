import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from src.utils.constants import FORMAT_COLUMNS, SEPARATORS, GENERIC_EMAIL_PREFIXES
from src.utils.exporters import clipboard_html, to_csv_bytes


def _split_comma_values(cell: str) -> list[str]:
    if not cell:
        return []
    return [part.strip() for part in str(cell).split(",") if part.strip()]


def _passes_prefix_filter(email: str) -> bool:
    prefixes = [p.lower() for p in st.session_state.get("email_prefix_filter", [])]
    if not prefixes:
        return True
    return any(email.lower().startswith(p) for p in prefixes)


def _compute_stats(entity_map: list[dict]) -> dict:
    all_emails: list[str] = []
    for row in entity_map:
        emails_str = row.get("Emails", "")
        if emails_str:
            all_emails.extend([e.strip() for e in emails_str.split(",") if e.strip()])

    unique = set(all_emails)
    domains = set(e.split("@")[1] for e in unique if "@" in e)

    role_prefixes = {p.rstrip("@") for p in GENERIC_EMAIL_PREFIXES}
    role_count = sum(
        1 for e in unique if e.split("@")[0].lower() in role_prefixes
    )

    return {
        "unique": len(unique),
        "total": len(all_emails),
        "domains": len(domains),
        "roles": role_count,
    }


def _render_stats(stats: dict) -> None:
    st.markdown(
        f"""
        <div class="stats-row">
            <div class="stat-card">
                <div class="stat-icon email">✉</div>
                <div class="stat-info">
                    <div class="stat-value">{stats["unique"]}</div>
                    <div class="stat-label">Unique emails</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon matches">🔍</div>
                <div class="stat-info">
                    <div class="stat-value">{stats["total"]}</div>
                    <div class="stat-label">Total matches</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon domains">📁</div>
                <div class="stat-info">
                    <div class="stat-value">{stats["domains"]}</div>
                    <div class="stat-label">Domains</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon roles">👥</div>
                <div class="stat-info">
                    <div class="stat-value">{stats["roles"]}</div>
                    <div class="stat-label">Role accounts</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_entity_map() -> None:
    rows: list[dict] = st.session_state.entity_map
    if st.session_state.get("hide_no_contact"):
        rows = [r for r in rows if r.get("Emails") or r.get("URLs")]
    if not rows:
        st.markdown(
            """
            <div class="empty-state">
                <div class="empty-state-icon">✉</div>
                <h3>No emails found yet</h3>
                <p>Paste some text, upload a file or fetch a URL to start extracting email addresses.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    fmt = st.session_state.get("output_format", "Name + Website + Email + Phone")
    all_cols = ["Name", "URLs", "Emails", "Phones"]
    show_cols = FORMAT_COLUMNS.get(fmt, all_cols)

    df_full = pd.DataFrame(rows, columns=["Name", "Emails", "Phones", "URLs"])

    if st.session_state.get("gmail_only") and "Emails" in show_cols:
        def _filter_gmails(cell: str) -> str:
            return ", ".join(e for e in cell.split(", ") if e.endswith("@gmail.com"))
        df_full["Emails"] = df_full["Emails"].apply(_filter_gmails)

    if "Emails" in show_cols:
        def _filter_prefixes(cell: str) -> str:
            return ", ".join(
                e for e in cell.split(", ") if e.strip() and _passes_prefix_filter(e.strip())
            )
        df_full["Emails"] = df_full["Emails"].apply(_filter_prefixes)

        if st.session_state.get("email_prefix_filter"):
            df_full = df_full[df_full["Emails"].str.strip().astype(bool)]

    if st.session_state.get("hide_role_accounts") and "Emails" in df_full.columns:
        role_prefixes = {p.rstrip("@") for p in GENERIC_EMAIL_PREFIXES}

        def _remove_roles(cell: str) -> str:
            return ", ".join(
                e for e in cell.split(", ")
                if e.strip() and e.strip().split("@")[0].lower() not in role_prefixes
            )
        df_full["Emails"] = df_full["Emails"].apply(_remove_roles)

    if df_full.empty:
        st.info("No emails match the current filter.")
        return

    q = st.session_state.get("filter_query", "").strip().lower()
    if q and "Emails" in df_full.columns:
        df_full = df_full[df_full["Emails"].fillna("").str.lower().str.contains(q, regex=False)]

    if df_full.empty:
        st.info("No results match the current filter.")
        return

    df = df_full[[c for c in show_cols if c in df_full.columns]]

    contact_cols = [c for c in show_cols if c != "Name"]
    if contact_cols:
        df = df[df[contact_cols].apply(lambda r: r.str.strip().any(), axis=1)]

    if df.empty:
        st.info("No results match the current format or filter.")
        return

    for col in ("Emails", "Phones", "URLs"):
        if col in df.columns:
            split_series = df[col].apply(_split_comma_values)
            max_items = int(split_series.apply(len).max())
            if col == "Phones":
                max_items = min(max_items, 2)
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
                right = df.iloc[:, insert_at + 1:]
                df = pd.concat([left, expanded, right], axis=1)
            else:
                df[col] = split_series.apply(lambda values: values[0] if values else "")

    st.markdown(
        f'<div class="counter-badge">{len(df)} {"entity" if len(df) == 1 else "entities"} — {fmt}</div>',
        unsafe_allow_html=True,
    )

    st.dataframe(df, use_container_width=True, hide_index=True)

    tsv_output = df.to_csv(sep="\t", index=False)

    copy_col, csv_col, txt_col = st.columns(3)
    with copy_col:
        components.html(clipboard_html(tsv_output, btn_id="copy_entity_map"), height=52)
    with csv_col:
        st.download_button(
            "⬇ CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="entity_map.csv",
            mime="text/csv",
            use_container_width=True,
            key="dl_map_csv",
        )
    with txt_col:
        st.download_button(
            "⬇ TXT",
            data=tsv_output.encode("utf-8"),
            file_name="entity_map.txt",
            mime="text/plain",
            use_container_width=True,
            key="dl_map_txt",
        )


def render_output_section() -> None:
    entity_map = st.session_state.get("entity_map", [])
    stats = _compute_stats(entity_map) if entity_map else {"unique": 0, "total": 0, "domains": 0, "roles": 0}

    _render_stats(stats)

    filter_col, hide_col = st.columns([3, 1])
    with filter_col:
        st.text_input(
            "Filter",
            key="filter_query",
            placeholder="Filter by email, name or domain...",
            label_visibility="collapsed",
        )
    with hide_col:
        st.checkbox("Hide role accounts", key="hide_role_accounts")

    if not st.session_state.has_extracted:
        st.markdown(
            """
            <div class="results-card">
                <div class="empty-state">
                    <div class="empty-state-icon">✉</div>
                    <h3>No emails found yet</h3>
                    <p>Paste some text, upload a file or fetch a URL to start extracting email addresses.</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    _render_entity_map()
