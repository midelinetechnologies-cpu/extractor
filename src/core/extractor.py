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
        part = parts[i]
        if part in VALID_TLDS:
            return at + "@" + ".".join(parts[:i + 1])
        # Handle junk appended directly to TLD e.g. "deread" → "de", "comread" → "com"
        for length in range(min(6, len(part) - 1), 1, -1):
            if part[:length] in VALID_TLDS:
                parts[i] = part[:length]
                return at + "@" + ".".join(parts[:i + 1])
    return email


def _is_separator(line: str) -> bool:
    s = line.strip()
    return s in ('·', '•', '-', '|', '—', '·') or re.match(r'^[·•\-\|—\s]+$', s) is not None


def _is_url_line(line: str) -> bool:
    s = line.strip()
    return bool(re.match(r'https?://', s) or re.match(r'^[a-z0-9\-]+\.[a-z]{2,}', s))


def _is_bare_domain(line: str) -> bool:
    return bool(re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}$', line.strip()))


def _is_skip(line: str) -> bool:
    s = line.strip()
    if not s:
        return True
    if re.match(r'https?://', s):
        return True
    if _is_bare_domain(s):
        return True
    if re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', s):
        return True
    if re.match(r'^\+?\d[\d\s\-]{7,}', s):
        return True
    if any(kw in s.lower() for kw in _SKIP_KEYWORDS):
        return True
    return False


@log_call
def extract_names_heuristic(text: str) -> list[str]:
    names = []
    lines = text.split('\n')

    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not _is_url_line(line):
            continue

        # Walk backward up to 3 lines, skipping separators and empty lines
        for back in range(1, 4):
            bi = i - back
            if bi < 0:
                break
            candidate = lines[bi].strip()
            if not candidate:
                continue
            if _is_separator(candidate):
                continue
            if _is_skip(candidate):
                break
            words = candidate.split()
            if 1 <= len(words) <= 8:
                names.append(candidate)
            break

    # Also catch standalone proper-noun lines not followed by a URL
    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if _is_skip(line) or _is_separator(line):
            continue
        if re.match(r'^[A-Z][a-zA-Z\s\&\'\.\-]+$', line) and len(line) > 5:
            words = line.split()
            if 2 <= len(words) <= 8:
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
