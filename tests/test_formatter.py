import json
import pytest
from src.core.formatter import format_items


ITEMS = ["alpha@test.com", "beta@test.com"]


def test_plain_text_newline():
    result = format_items(ITEMS, "Plain Text", "\n", "email")
    assert result == "alpha@test.com\nbeta@test.com"


def test_plain_text_comma():
    result = format_items(ITEMS, "Plain Text", ", ", "email")
    assert result == "alpha@test.com, beta@test.com"


def test_json_format():
    result = format_items(ITEMS, "JSON", "\n", "email")
    assert json.loads(result) == ITEMS


def test_csv_format():
    result = format_items(ITEMS, "CSV", "\n", "email")
    assert "email" in result
    assert "alpha@test.com" in result
    assert "beta@test.com" in result


def test_html_format_email():
    result = format_items(["a@b.com"], "HTML", "\n", "email")
    assert 'href="mailto:a@b.com"' in result
    assert "<a" in result


def test_html_format_url():
    result = format_items(["https://x.com"], "HTML", "\n", "url")
    assert 'href="https://x.com"' in result


def test_tsv_format():
    result = format_items(ITEMS, "TSV", "\n", "email")
    lines = result.split("\n")
    assert lines[0] == "email"
    assert "alpha@test.com" in lines


def test_empty_items():
    assert format_items([], "Plain Text", "\n") == ""
    assert format_items([], "JSON", "\n") == ""
