import pytest
from src.core.extractor import Extractor

ex = Extractor()


class TestEmailExtraction:
    def test_basic(self):
        result = ex.extract_emails("Contact hello@example.com or support@test.org")
        assert "hello@example.com" in result
        assert "support@test.org" in result

    def test_deduplication(self):
        result = ex.extract_emails("a@b.com and A@B.COM", dedupe=True)
        assert len(result) == 1

    def test_no_dedupe(self):
        result = ex.extract_emails("a@b.com and a@b.com", dedupe=False)
        assert len(result) == 2

    def test_empty_input(self):
        assert ex.extract_emails("") == []

    def test_no_emails(self):
        assert ex.extract_emails("no emails here at all") == []

    def test_subdomain_email(self):
        result = ex.extract_emails("test@mail.example.co.uk")
        assert len(result) == 1

    def test_ignore_name_tld_noise(self):
        result = ex.extract_emails("bad@sample.sample.com.read ok@test.com")
        assert "bad@sample.com.read" not in result
        assert "ok@test.com" in result


class TestURLExtraction:
    def test_https(self):
        result = ex.extract_urls("Visit https://example.com for info")
        assert "https://example.com" in result

    def test_http(self):
        result = ex.extract_urls("see http://test.org/path?q=1")
        assert len(result) >= 1

    def test_empty(self):
        assert ex.extract_urls("") == []


class TestPhoneExtraction:
    def test_dashes(self):
        result = ex.extract_phones("Call 555-123-4567 for help")
        assert len(result) >= 1

    def test_empty(self):
        assert ex.extract_phones("") == []
