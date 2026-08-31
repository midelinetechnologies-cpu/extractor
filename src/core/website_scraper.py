import re
import requests
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse
from typing import Callable, Optional

from bs4 import BeautifulSoup

from src.utils.constants import EMAIL_REGEX, PHONE_REGEX, VALID_TLDS

CONTACT_PATHS = [
    "/contact", "/contact-us", "/contactus",
    "/about", "/about-us", "/aboutus",
    "/team", "/our-team",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

_email_re = re.compile(EMAIL_REGEX, re.IGNORECASE)
_phone_re = re.compile(PHONE_REGEX)

_JUNK_EMAIL_PATTERNS = re.compile(
    r"(\.png|\.jpg|\.gif|\.svg|\.webp|\.css|\.js|wixpress|sentry|cloudflare|example\.com)",
    re.IGNORECASE,
)

_NAME_RE = re.compile(r"^[A-Z][a-z]+(?:\s[A-Z][a-z]+){1,3}$")


@dataclass
class ScrapedContact:
    url: str
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    page_title: str = ""
    status: str = "OK"
    error: str = ""


def _strip_invalid_tld(email: str) -> str:
    at, _, domain = email.partition("@")
    parts = domain.split(".")
    for i in range(len(parts) - 1, 0, -1):
        part = parts[i]
        if part in VALID_TLDS:
            return at + "@" + ".".join(parts[: i + 1])
        for length in range(min(6, len(part) - 1), 1, -1):
            if part[:length] in VALID_TLDS:
                parts[i] = part[:length]
                return at + "@" + ".".join(parts[: i + 1])
    return email


def _fetch_page(url: str, timeout: int = 15) -> Optional[str]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None


def _extract_visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "meta", "link"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)


def _extract_title(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.find("title")
    return title.get_text(strip=True) if title else ""


def _extract_emails_from_html(html: str, text: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    found = set()

    for mailto in soup.select("a[href^='mailto:']"):
        email = mailto["href"].replace("mailto:", "").split("?")[0].strip().lower()
        if "@" in email:
            found.add(email)

    for match in _email_re.findall(text):
        cleaned = match.strip().strip(".,;:!?)(").lower()
        cleaned = _strip_invalid_tld(cleaned)
        if not _JUNK_EMAIL_PATTERNS.search(cleaned):
            found.add(cleaned)

    for match in _email_re.findall(html):
        cleaned = match.strip().strip(".,;:!?)(").lower()
        cleaned = _strip_invalid_tld(cleaned)
        if not _JUNK_EMAIL_PATTERNS.search(cleaned):
            found.add(cleaned)

    return sorted(found)


def _extract_phones_from_text(html: str, text: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    found = set()

    for tel in soup.select("a[href^='tel:']"):
        phone = tel["href"].replace("tel:", "").strip()
        if phone:
            found.add(phone)

    for match in _phone_re.findall(text):
        found.add(match.strip())

    return sorted(found)


def _extract_names_from_html(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    names = set()

    for meta in soup.find_all("meta"):
        name_attr = (meta.get("name") or meta.get("property") or "").lower()
        if name_attr in ("author", "article:author", "creator"):
            content = (meta.get("content") or "").strip()
            if content and _NAME_RE.match(content):
                names.add(content)

    schema_types = soup.find_all(attrs={"itemtype": re.compile(r"schema\.org/Person", re.I)})
    for person in schema_types:
        name_el = person.find(attrs={"itemprop": "name"})
        if name_el:
            text = name_el.get_text(strip=True)
            if _NAME_RE.match(text):
                names.add(text)

    for ld in soup.find_all("script", type="application/ld+json"):
        try:
            import json
            data = json.loads(ld.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and item.get("@type") in ("Person", "Organization"):
                    n = item.get("name", "")
                    if isinstance(n, str) and _NAME_RE.match(n):
                        names.add(n)
        except Exception:
            pass

    for tag in soup.find_all(class_=re.compile(r"(team|staff|author|founder|ceo|director|name)", re.I)):
        text = tag.get_text(strip=True)
        if _NAME_RE.match(text) and len(text) < 60:
            names.add(text)

    return sorted(names)


def _discover_contact_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    found = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        text = a.get_text(strip=True).lower()
        if any(kw in href or kw in text for kw in ("contact", "about", "team", "our-team", "staff")):
            full = urljoin(base_url, a["href"])
            parsed = urlparse(full)
            base_parsed = urlparse(base_url)
            if parsed.netloc == base_parsed.netloc:
                found.add(full)
    return list(found)[:6]


def scrape_single_url(url: str, timeout: int = 15, scrape_subpages: bool = True) -> ScrapedContact:
    result = ScrapedContact(url=url)

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    html = _fetch_page(url, timeout)
    if not html:
        result.status = "FAILED"
        result.error = "Could not fetch page"
        return result

    result.page_title = _extract_title(html)
    text = _extract_visible_text(html)
    all_emails = set(_extract_emails_from_html(html, text))
    all_phones = set(_extract_phones_from_text(html, text))
    all_names = set(_extract_names_from_html(html))

    if scrape_subpages:
        sub_urls = set()
        for path in CONTACT_PATHS:
            sub_urls.add(urljoin(url, path))
        sub_urls.update(_discover_contact_links(html, url))
        sub_urls.discard(url)

        for sub_url in list(sub_urls)[:8]:
            sub_html = _fetch_page(sub_url, timeout=10)
            if not sub_html:
                continue
            sub_text = _extract_visible_text(sub_html)
            all_emails.update(_extract_emails_from_html(sub_html, sub_text))
            all_phones.update(_extract_phones_from_text(sub_html, sub_text))
            all_names.update(_extract_names_from_html(sub_html))

    result.emails = sorted(all_emails)
    result.phones = sorted(all_phones)
    result.names = sorted(all_names)
    return result


def scrape_multiple_urls(
    urls: list[str],
    timeout: int = 15,
    max_workers: int = 5,
    scrape_subpages: bool = True,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> list[ScrapedContact]:
    results: list[ScrapedContact] = []
    total = len(urls)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(scrape_single_url, url, timeout, scrape_subpages): url
            for url in urls
        }
        done_count = 0
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:
                results.append(ScrapedContact(
                    url=futures[future], status="ERROR", error=str(exc),
                ))
            done_count += 1
            if progress_callback:
                progress_callback(done_count, total)

    url_order = {u: i for i, u in enumerate(urls)}
    results.sort(key=lambda r: url_order.get(r.url, len(urls)))
    return results
