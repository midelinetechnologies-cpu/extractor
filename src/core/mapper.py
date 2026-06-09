"""
Entity mapping engine — based on test2.py URL-anchored window approach.

Strategy:
  1. Find every https:// URL in the text.
  2. For each URL look backward ≤5 lines for a business/person name.
  3. Scan a ±6-line window around the URL for emails and phones.
  4. Merge records that share the same base domain.
  5. Apply optional filters (hide directories, require email/name).

TSV input (tab-separated) is handled separately via _parse_tsv().
"""

import re
from src.utils.constants import PHONE_REGEX, VALID_TLDS

_phone_re = re.compile(PHONE_REGEX)

# ── Constants ─────────────────────────────────────────────────────────────────

SKIP_KEYWORDS = [
    'contact us', 'read more', 'show number', 'discover more',
    'call us', 'email us', 'address', 'copyright', 'all rights',
    'quick links', 'home ·', 'shop no', 'sector', 'greater noida',
    'uttar pradesh', 'developed by', 'phone', 'mobile', 'timing',
    'near', 'floor', 'block', '›', '...', 'results are',
    'privacy', 'terms', 'feedback', 'update location', 'get directions',
    'book now', 'view details', 'see all', 'load more', 'next',
    'images', 'videos', 'shopping', 'forums', 'tools', 'more',
    'search', 'filter', 'sort', 'page', 'back', 'forward',
    'india', 'delhi', 'mumbai', 'noida', 'ghaziabad', 'location',
    'open hours', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun',
    'am –', 'pm', 'timing', 'hour', 'google', 'bing', 'yahoo',
    'sulekha', 'justdial', 'plumint', 'dialmenow', 'facebook',
    'instagram', 'youtube', 'twitter', 'linkedin', 'threads',
    'sign in', 'sign up', 'login', 'register', 'subscribe',
    'newsletter', 'follow', 'share', 'like', 'comment',
    'services', 'about', 'blog', 'faq', 'policy',
    'get in touch', 'reach us', 'write us', 'message us',
    'scan this', 'qr code', 'experience', 'appointment',
    'instafinancials', 'bizmart', 'slideserve', 'rackons',
    'customercareinfo', 'placementindia',
]

DIRECTORY_DOMAINS = [
    'sulekha.com', 'justdial.com', 'plumint.com', 'dialmenow.in',
    'facebook.com', 'instagram.com', 'youtube.com', 'twitter.com',
    'linkedin.com', 'threads.com', 'instafinancials.com',
    'bizmartcommerce.com', 'slideserve.com', 'rackons.in',
    'customercareinfo.in', 'placementindia.com', 'google.com',
    'bing.com', 'yahoo.com',
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def is_directory_url(url: str) -> bool:
    low = url.lower()
    return any(d in low for d in DIRECTORY_DOMAINS)


def is_skip_line(line: str) -> bool:
    low = line.lower()
    return any(kw in low for kw in SKIP_KEYWORDS)


def looks_like_business_name(line: str) -> bool:
    line = line.strip()
    if not line:
        return False
    if re.search(r'https?://', line):
        return False
    if re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', line):
        return False
    if re.match(r'^\+?\d[\d\s\-]{6,}', line):
        return False
    if is_skip_line(line):
        return False
    words = line.split()
    if not (1 <= len(words) <= 8):
        return False
    if line == line.lower() and len(words) > 2:
        return False
    return True


def _strip_invalid_tld(email: str) -> str:
    at, _, domain = email.partition("@")
    parts = domain.split(".")
    for i in range(len(parts) - 1, 0, -1):
        if parts[i] in VALID_TLDS:
            return at + "@" + ".".join(parts[:i + 1])
    return email


def extract_emails_from_line(line: str) -> list[str]:
    matches = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', line)
    cleaned: list[str] = []
    for email in matches:
        value = _strip_invalid_tld(email.strip().strip(".,;:!?)(").lower())
        cleaned.append(value)
    return cleaned


def extract_url_from_line(line: str) -> list[str]:
    urls = re.findall(r'https?://[^\s\)\]\>\"\'\,]+', line)
    return [re.sub(r'[.,;!\?\)\]\>\'\"]+$', '', u) for u in urls]


def extract_phones_from_line(line: str) -> list[str]:
    found: list[str] = []
    for token in re.split(r'[,;\s]+', line):
        token = token.strip()
        if not token:
            continue
        clean = re.sub(r'[\s\-\.\(\)\+]', '', token)
        if clean.isdigit() and 7 <= len(clean) <= 15:
            found.append(token)
        elif _phone_re.search(token):
            found.append(token)
    return found


def get_base_domain(url: str) -> str:
    url = url.lower().rstrip('/')
    url = re.sub(r'^https?://', '', url)
    return url.split('/')[0]


# ── Core Pipeline ─────────────────────────────────────────────────────────────

def parse_blocks(text: str) -> list[dict]:
    """
    Walk line-by-line, anchor on every https:// URL found.
    For each URL:
      - Name   : look backward ≤5 lines for a business-name candidate.
      - Emails : ±6-line window around the URL line.
      - Phones : same window.
    """
    lines = [l.strip() for l in text.splitlines()]
    n = len(lines)

    # Collect all (line_index, url) pairs
    url_positions: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        for u in extract_url_from_line(line):
            url_positions.append((i, u))

    raw_records: list[dict] = []
    for url_line_idx, url in url_positions:

        # ── Name: walk backward up to 5 lines ────────────────────────────
        name = ''
        for back in range(1, 6):
            bi = url_line_idx - back
            if bi < 0:
                break
            candidate = lines[bi]
            if not candidate:
                continue
            if extract_url_from_line(candidate):   # hit another URL → stop
                break
            if extract_emails_from_line(candidate):
                continue
            if looks_like_business_name(candidate):
                name = candidate
                break

        # ── Emails + Phones: ±6-line window ──────────────────────────────
        emails: list[str] = []
        phones: list[str] = []
        window_start = max(0, url_line_idx - 2)
        window_end   = min(n, url_line_idx + 7)
        for wi in range(window_start, window_end):
            emails.extend(extract_emails_from_line(lines[wi]))
            phones.extend(extract_phones_from_line(lines[wi]))

        emails = list(dict.fromkeys(e.lower() for e in emails))
        phones = list(dict.fromkeys(phones))

        raw_records.append({'name': name, 'emails': emails, 'phones': phones, 'url': url})

    return raw_records


def merge_records(raw_records: list[dict]) -> list[dict]:
    """Merge records that share the same base domain; accumulate emails/phones."""
    domain_map: dict[str, dict] = {}
    for rec in raw_records:
        domain = get_base_domain(rec['url'])
        if domain not in domain_map:
            domain_map[domain] = rec.copy()
            domain_map[domain]['emails'] = list(rec['emails'])
            domain_map[domain]['phones'] = list(rec['phones'])
        else:
            existing = domain_map[domain]
            if not existing['name'] and rec['name']:
                existing['name'] = rec['name']
            existing['emails'] = list(dict.fromkeys(existing['emails'] + rec['emails']))
            existing['phones'] = list(dict.fromkeys(existing['phones'] + rec['phones']))
    return list(domain_map.values())


def build_result_list(
    merged: list[dict],
    hide_directory: bool = True,
    hide_no_email: bool = False,
    hide_no_name: bool = False,
) -> list[dict]:
    seen_emails: set[str] = set()
    rows: list[dict] = []

    for rec in merged:
        url = rec['url'].strip()

        if hide_directory and is_directory_url(url):
            continue

        unique_emails: list[str] = []
        for e in rec['emails']:
            if e not in seen_emails:
                seen_emails.add(e)
                unique_emails.append(e)

        email_str = ', '.join(unique_emails)
        phone_str = ', '.join(rec['phones'])
        name = rec['name'].strip()

        if hide_no_email and not email_str:
            continue
        if hide_no_name and not name:
            continue

        if not url and not email_str and not name:
            continue

        rows.append({'Name': name, 'Emails': email_str, 'Phones': phone_str, 'URLs': url})

    return rows


# ── TSV path (unchanged from previous version) ────────────────────────────────

def _is_tsv(text: str) -> bool:
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) < 2:
        return False
    return sum(1 for l in lines if '\t' in l) / len(lines) >= 0.5


def _parse_tsv(
    text: str,
    hide_directory: bool = True,
    hide_no_email: bool = False,
    hide_no_name: bool = False,
) -> list[dict]:
    """
    Column-order agnostic TSV parser.
    Each column beyond col0 is scanned for its content type
    (emails, URLs, phones) so both:
      col0=name  col1=emails  col2=phones
      col0=name  col1=url     col2=emails
    are handled correctly.
    Records are then merged by base URL domain and filtered the same way
    as the free-text pipeline.
    """
    from src.core.extractor import extract_names_heuristic

    _email_re = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', re.IGNORECASE)
    raw_records: list[dict] = []

    for line in text.splitlines():
        if not line.strip():
            continue
        cols = [c.strip() for c in line.split('\t')]
        col0 = cols[0] if cols else ''

        if _email_re.fullmatch(col0) or re.fullmatch(r'[A-Z0-9/\-]{3,}', col0):
            continue

        names = extract_names_heuristic(col0)
        if not names:
            continue

        primary = max(names, key=len)

        # Scan every non-name column for its content type
        emails: list[str] = []
        phones: list[str] = []
        urls:   list[str] = []
        for col in cols[1:]:
            if not col:
                continue
            emails.extend(_strip_invalid_tld(e.lower()) for e in _email_re.findall(col))
            urls.extend(extract_url_from_line(col))
            phones.extend(extract_phones_from_line(col))

        raw_records.append({
            'name':   primary,
            'emails': list(dict.fromkeys(emails)),
            'phones': list(dict.fromkeys(phones)),
            'url':    urls[0] if urls else '',
        })

    merged = merge_records(raw_records)
    return build_result_list(merged, hide_directory, hide_no_email, hide_no_name)


# ── Public entry point ────────────────────────────────────────────────────────

def build_entity_map(
    text: str,
    hide_directory: bool = True,
    hide_no_email: bool = False,
    hide_no_name: bool = False,
) -> list[dict]:
    if _is_tsv(text):
        return _parse_tsv(text, hide_directory, hide_no_email, hide_no_name)

    raw    = parse_blocks(text)
    merged = merge_records(raw)
    return build_result_list(merged, hide_directory, hide_no_email, hide_no_name)
