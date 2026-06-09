import re
from src.utils.constants import EMAIL_REGEX, URL_REGEX, PHONE_REGEX

_email_re = re.compile(EMAIL_REGEX, re.IGNORECASE)
_phone_re = re.compile(PHONE_REGEX)
_url_re = re.compile(URL_REGEX, re.IGNORECASE)
_BLOCK_SPLIT = re.compile(r'\n\s*\n')


def _extract_phones_broad(text: str) -> list[str]:
    found: list[str] = []
    for token in re.split(r'[,;\s]+', text):
        token = token.strip()
        if not token:
            continue
        clean = re.sub(r'[\s\-\.\(\)\+]', '', token)
        if clean.isdigit() and 7 <= len(clean) <= 15:
            found.append(token)
        elif _phone_re.search(token):
            found.append(token)
    return list(dict.fromkeys(found))


def _is_tsv(text: str) -> bool:
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) < 2:
        return False
    tab_lines = sum(1 for l in lines if '\t' in l)
    return (tab_lines / len(lines)) >= 0.5


def _parse_tsv(text: str) -> list[dict]:
    from src.core.extractor import extract_names_heuristic
    bucket: dict[str, dict] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        cols = [c.strip() for c in line.split('\t')]
        col0 = cols[0] if len(cols) > 0 else ''
        col1 = cols[1] if len(cols) > 1 else ''
        col2 = cols[2] if len(cols) > 2 else ''
        col3 = cols[3] if len(cols) > 3 else ''
        if _email_re.fullmatch(col0) or re.fullmatch(r'[A-Z0-9/\-]{3,}', col0):
            continue
        names = extract_names_heuristic(col0)
        if not names:
            continue
        primary = max(names, key=len)
        emails = [e.lower() for e in _email_re.findall(col1)] if col1 else []
        phones = _extract_phones_broad(col2) if col2 else []
        urls = _url_re.findall(col3 or col1) if (col3 or col1) else []
        urls += _url_re.findall(col1) if col1 else []
        if primary not in bucket:
            bucket[primary] = {"name": primary, "emails": set(), "phones": set(), "urls": set()}
        bucket[primary]["emails"].update(emails)
        bucket[primary]["phones"].update(phones)
        bucket[primary]["urls"].update(urls)
    return _to_rows(bucket)


def _safe_urls(block: str, emails: list[str]) -> list[str]:
    email_domains = {e.split("@")[1].lower().rstrip(".") for e in emails}
    return [u for u in _url_re.findall(block) if u.lower().rstrip("/").rstrip(".") not in email_domains]


def _collect_block(block: str, nlp=None, extract_names_heuristic=None) -> dict[str, dict]:
    emails = [e.lower() for e in _email_re.findall(block)]
    phones = _phone_re.findall(block)
    urls = _safe_urls(block, emails)
    if not (emails or phones or urls):
        return {}
    seen: set[str] = set()
    entities: list[str] = []
    for name in extract_names_heuristic(block):
        if name not in seen:
            seen.add(name)
            entities.append(name)
    if nlp is not None:
        doc = nlp(block)
        for ent in doc.ents:
            if ent.label_ in {"PERSON", "ORG"}:
                name = ent.text.strip()
                if name not in seen:
                    seen.add(name)
                    entities.append(name)
    if not entities:
        return {}
    bucket: dict[str, dict] = {}
    for name in entities:
        if name not in bucket:
            bucket[name] = {"name": name, "emails": set(), "phones": set(), "urls": set()}
        bucket[name]["emails"].update(emails)
        bucket[name]["phones"].update(phones)
        bucket[name]["urls"].update(urls)
    return bucket


def _merge(master: dict, patch: dict) -> None:
    for name, data in patch.items():
        if name not in master:
            master[name] = data
        else:
            master[name]["emails"].update(data["emails"])
            master[name]["phones"].update(data["phones"])
            master[name]["urls"].update(data["urls"])


def _to_rows(bucket: dict) -> list[dict]:
    return [
        {"Name": v["name"], "Emails": ", ".join(sorted(v["emails"])),
         "Phones": ", ".join(sorted(v["phones"])), "URLs": ", ".join(sorted(v["urls"]))}
        for v in bucket.values() if v["emails"] or v["phones"] or v["urls"]
    ]


def build_entity_map(text: str) -> list[dict]:
    if _is_tsv(text):
        return _parse_tsv(text)
    from src.core.extractor import _load_nlp, extract_names_heuristic
    nlp = _load_nlp()
    blocks = _BLOCK_SPLIT.split(text)
    if len(blocks) == 1:
        blocks = text.splitlines()
    master: dict[str, dict] = {}
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        patch = _collect_block(block, nlp=nlp, extract_names_heuristic=extract_names_heuristic)
        _merge(master, patch)
    return _to_rows(master)
