import csv
import io
import json
import pandas as pd


def to_csv_bytes(items: list[str], header: str = "value") -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([header])
    writer.writerows([[item] for item in items])
    return buf.getvalue().encode("utf-8")


def to_json_bytes(items: list[str]) -> bytes:
    return json.dumps(items, indent=2).encode("utf-8")


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=True, sheet_name="Contacts")
        ws = writer.sheets["Contacts"]
        for col in ws.columns:
            max_len = max((len(str(c.value)) if c.value else 0) for c in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 70)
    return buf.getvalue()


def clipboard_html(text: str, btn_id: str = "copy_btn") -> str:
    escaped_js = text.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
    return f"""
    <button id="{btn_id}" style="
      width:100%;background:#1a2332;color:#4d8bf5;
      border:1px solid #4d8bf5;padding:8px 16px;
      border-radius:8px;cursor:pointer;font-size:14px;
      font-family:sans-serif;transition:all .2s;
    " onclick="(function(){{
      var btn = document.getElementById('{btn_id}');
      var txt = `{escaped_js}`;
      function ok(){{
        btn.innerHTML = '&#10003; Copied!';
        btn.style.borderColor = '#10b981';
        btn.style.color = '#10b981';
        setTimeout(function(){{
          btn.innerHTML = '&#128203; Copy to Clipboard';
          btn.style.borderColor='#4d8bf5';
          btn.style.color='#4d8bf5';
        }}, 2000);
      }}
      try {{
        (window.parent || window).navigator.clipboard.writeText(txt).then(ok);
      }} catch(e) {{
        var ta = document.createElement('textarea');
        ta.value = txt;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        ok();
      }}
    }})()">&#128203; Copy to Clipboard</button>
    """
