import re
from src.utils.constants import EMAIL_REGEX, URL_REGEX, PHONE_REGEX, VALID_TLDS
from src.utils.logger import log_call

_SKIP_KEYWORDS = [
    'contact us', 'read more', 'show number', 'discover more',
    'call us', 'email us', 'address', 'copyright', 'all rights',
    'quick links', 'home ·', 'shop no', 'sector', 'greater noida',
    'uttar pradesh', 'developed by', 'phone', 'mobile', 'timing',
    'near', 'floor', 'block', '›', '...', 'results are',
    'privacy', 'terms', 'feedback', 'update location',
]


def _strip_invalid_tld(email: str) -> str:
    at, _, domain = email.partition("@")
    parts = domain.split(".")
    for i in range(len(parts) - 1, 0, -1):
        if parts[i] in VALID_TLDS:
            return at + "@" + ".".join(parts[:i + 1])
    return email


@log_call
def extract_names_heuristic(text: str) -> list[str]:
    names = []
    lines = text.split('\n')
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        if re.match(r'https?://', line):
            continue
        if re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', line):
            continue
        if re.match(r'^\+?\d[\d\s\-]{7,}', line):
            continue
        if any(kw in line.lower() for kw in _SKIP_KEYWORDS):
            continue
        words = line.split()
        if 2 <= len(words) <= 8:
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if re.match(r'https?://', next_line) or re.match(r'^[a-z0-9\-]+\.[a-z]{2,}', next_line):
                    names.append(line)
                    continue
            if re.match(r'^[A-Z][a-zA-Z\s\&\'\.\-]+$', line) and len(line) > 5:
                names.append(line)
    return list(dict.fromkeys(names))


def get_extractor() -> "Extractor":
    return Extractor()


class Extractor:
    def __init__(self) -> None:
        self._email_re = re.compile(EMAIL_REGEX, re.IGNORECASE)
        self._url_re = re.compile(URL_REGEX, re.IGNORECASE)
        self._phone_re = re.compile(PHONE_REGEX)

    @log_call
    def extract_emails(self, text: str, dedupe: bool = True) -> list[str]:
        raw = self._email_re.findall(text)
        found: list[str] = []
        for email in raw:
            cleaned = email.strip().strip(".,;:!?)(").lower()
            cleaned = _strip_invalid_tld(cleaned)
            found.append(cleaned)
        if dedupe:
            found = list(dict.fromkeys(found))
        return found

    @log_call
    def extract_urls(self, text: str, dedupe: bool = True) -> list[str]:
        # Collect email domains so we can strip them from URL results
        email_domains = {
            m.split("@")[1].lower().rstrip(".")
            for m in self._email_re.findall(text)
        }
        found = [
            u for u in self._url_re.findall(text)
            if u.lower().rstrip("/").rstrip(".") not in email_domains
        ]
        if dedupe:
            found = list(dict.fromkeys(found))
        return found

    @log_call
    def extract_phones(self, text: str, dedupe: bool = True) -> list[str]:
        found = self._phone_re.findall(text)
        if dedupe:
            found = list(dict.fromkeys(found))
        return found

    @log_call
    def extract_names(self, text: str, dedupe: bool = True) -> list[str]:  # noqa: ARG002
        return extract_names_heuristic(text)

    def extract_orgs(self, *_) -> list[str]:
        return []
