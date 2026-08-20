import io
import csv
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
from datetime import datetime
from typing import List

from src.core.url_checker import (
    URLResult,
    check_multiple_urls,
    parse_url_input,
)
from src.utils.exporters import clipboard_html


def _init_url_state() -> None:
    if "url_results" not in st.session_state:
        st.session_state.url_results = []
    if "url_history" not in st.session_state:
        st.session_state.url_history = []
    if "uv_pending" not in st.session_state:
        st.session_state.uv_pending = False


def _request_check() -> None:
    st.session_state.uv_pending = True


def _results_to_dataframe(results: List[URLResult]) -> pd.DataFrame:
    data = []
    for i, result in enumerate(results, 1):
        data.append({
            "#": i,
            "URL": result.url,
            "Status": result.status_text,
            "HTTP Code": result.status_code if result.status_code else "N/A",
            "Response Time": result.response_time_str,
            "Content Type": result.content_type if result.content_type else "N/A",
            "Server": result.server if result.server else "N/A",
            "Redirect": result.redirect_url if result.redirect_url else "No",
            "Error": result.error_message if result.error_message else "-",
        })
    return pd.DataFrame(data)


def _results_to_csv(results: List[URLResult]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "S.No", "URL", "Status", "HTTP Code", "Response Time (s)",
        "Content Type", "Server", "Redirect URL", "Error Message", "Checked At",
    ])
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for i, result in enumerate(results, 1):
        writer.writerow([
            i,
            result.url,
            "UP" if result.is_working else "DOWN",
            result.status_code if result.status_code else "N/A",
            f"{result.response_time:.3f}" if result.response_time else "N/A",
            result.content_type if result.content_type else "N/A",
            result.server if result.server else "N/A",
            result.redirect_url if result.redirect_url else "N/A",
            result.error_message if result.error_message else "None",
            timestamp,
        ])
    return output.getvalue()


def _get_summary_stats(results: List[URLResult]) -> dict:
    total = len(results)
    working = sum(1 for r in results if r.is_working)
    down = total - working
    response_times = [r.response_time for r in results if r.response_time is not None]
    avg_rt = sum(response_times) / len(response_times) if response_times else 0
    return {
        "total": total,
        "working": working,
        "down": down,
        "working_pct": (working / total * 100) if total > 0 else 0,
        "down_pct": (down / total * 100) if total > 0 else 0,
        "avg_response_time": avg_rt,
        "max_response_time": max(response_times) if response_times else 0,
        "min_response_time": min(response_times) if response_times else 0,
    }


def _render_summary(results: List[URLResult]) -> None:
    stats = _get_summary_stats(results)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total URLs", stats["total"])
    col2.metric("Working", stats["working"])
    col3.metric("Down", stats["down"])
    col4.metric("Avg Response Time", f"{stats['avg_response_time']:.3f}s")

    if stats["total"] > 0:
        fig = px.pie(
            names=["Working", "Down"],
            values=[stats["working"], stats["down"]],
            color=["Working", "Down"],
            color_discrete_map={"Working": "#4CAF50", "Down": "#F44336"},
            hole=0.4,
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#e2e8f0",
            margin=dict(t=20, b=20, l=20, r=20),
            height=300,
        )
        st.plotly_chart(fig, use_container_width=True)


def _render_results_table(
    results: List[URLResult],
    show_response_time: bool,
    show_headers: bool,
) -> None:
    df = _results_to_dataframe(results)
    columns = ["#", "URL", "Status", "HTTP Code"]
    if show_response_time:
        columns.append("Response Time")
    if show_headers:
        columns += ["Content Type", "Server"]
    columns.append("Error")

    display_df = df[columns].copy()
    display_df["Status"] = display_df["Status"].apply(
        lambda v: f"✅ {v}" if v == "UP" else f"❌ {v}"
    )

    st.dataframe(display_df, use_container_width=True, hide_index=True)


def _render_working_urls(results: List[URLResult]) -> None:
    working_urls = [r.url for r in results if r.is_working]

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### Working URLs")

    if working_urls:
        st.markdown(
            f'<div class="counter-badge">{len(working_urls)} working URL{"s" if len(working_urls) != 1 else ""}</div>',
            unsafe_allow_html=True,
        )

        working_text = "\n".join(working_urls)
        st.code(working_text, language=None)

        copy_col, txt_col, xl_col = st.columns(3)
        with copy_col:
            components.html(
                clipboard_html(working_text, btn_id="copy_working_urls"),
                height=52,
            )
        with txt_col:
            st.download_button(
                "Download TXT",
                data=working_text.encode("utf-8"),
                file_name=f"working_urls_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True,
                key="uv_dl_txt",
            )
        with xl_col:
            df_working = pd.DataFrame(
                {"#": range(1, len(working_urls) + 1), "URL": working_urls}
            )
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                df_working.to_excel(writer, index=False, sheet_name="Working URLs")
                ws = writer.sheets["Working URLs"]
                for col in ws.columns:
                    max_len = max((len(str(c.value)) if c.value else 0) for c in col)
                    ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 70)
            st.download_button(
                "Download Excel",
                data=buf.getvalue(),
                file_name=f"working_urls_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="uv_dl_xlsx",
            )
    else:
        st.markdown(
            '<div class="empty-state"><p>No working URLs found.</p></div>',
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


def render_url_validator() -> None:
    _init_url_state()

    # ── Settings ──
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### Settings")

    s1, s2, s3 = st.columns(3)
    with s1:
        timeout = st.slider("Timeout (seconds)", 1, 30, 10, key="uv_timeout")
    with s2:
        max_workers = st.slider("Concurrent Requests", 1, 20, 10, key="uv_workers")
    with s3:
        verify_ssl = st.checkbox("Verify SSL Certificates", value=True, key="uv_ssl")

    c1, c2 = st.columns(2)
    with c1:
        show_response_time = st.checkbox("Show Response Time", value=True, key="uv_rt")
    with c2:
        show_headers = st.checkbox("Show Headers (Content-Type, Server)", value=False, key="uv_hdr")

    st.markdown("</div>", unsafe_allow_html=True)

    # ── URL Input ──
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("#### Enter URLs")

    url_input = st.text_area(
        "Enter comma-separated URLs:",
        placeholder="https://google.com, https://example.com, https://invalid-url-test.xyz",
        height=120,
        key="uv_input",
    )

    st.button(
        "Check URLs",
        type="primary",
        key="uv_check",
        use_container_width=True,
        on_click=_request_check,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Run check if pending ──
    if st.session_state.uv_pending:
        st.session_state.uv_pending = False
        urls = parse_url_input(url_input)
        if not urls:
            st.warning("Please enter at least one URL.")
        else:
            progress_bar = st.progress(0, text="Checking URLs...")

            def update_progress(done, total):
                progress_bar.progress(done / total, text=f"Checked {done}/{total} URLs")

            results = check_multiple_urls(
                urls,
                timeout=timeout,
                max_workers=max_workers,
                verify_ssl=verify_ssl,
                progress_callback=update_progress,
            )
            progress_bar.empty()

            st.session_state.url_results = results
            st.session_state.url_history.append({
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "count": len(urls),
                "results": results,
            })

    # ── Results ──
    if st.session_state.url_results:
        results = st.session_state.url_results

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Summary")
        _render_summary(results)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("#### Detailed Results")
        _render_results_table(results, show_response_time, show_headers)

        csv_data = _results_to_csv(results)
        st.download_button(
            "Download CSV Report",
            data=csv_data,
            file_name=f"url_status_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
            key="uv_dl_csv",
        )
        st.markdown("</div>", unsafe_allow_html=True)

        _render_working_urls(results)

    # ── History ──
    if st.session_state.url_history:
        with st.expander("History of Past Checks"):
            for entry in reversed(st.session_state.url_history[-10:]):
                up = sum(1 for r in entry["results"] if r.is_working)
                down = len(entry["results"]) - up
                st.write(
                    f"{entry['timestamp']} — {entry['count']} URL(s) checked "
                    f"({up} UP, {down} DOWN)"
                )
