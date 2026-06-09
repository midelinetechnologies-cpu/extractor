import csv
import io
import json


def format_items(
    items: list[str],
    format_type: str,
    separator: str,
    label: str = "value",
) -> str:
    if not items:
        return ""

    if format_type == "Plain Text":
        return separator.join(items)

    if format_type == "CSV":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([label])
        writer.writerows([[item] for item in items])
        return buf.getvalue()

    if format_type == "JSON":
        return json.dumps(items, indent=2)

    if format_type == "HTML":
        if label == "email":
            tags = [f'<a href="mailto:{i}">{i}</a>' for i in items]
        elif label == "url":
            tags = [f'<a href="{i}" target="_blank">{i}</a>' for i in items]
        else:
            tags = [f"<span>{i}</span>" for i in items]
        return "<br>\n".join(tags)

    if format_type == "TSV":
        return "\n".join([label, *items])

    return separator.join(items)
