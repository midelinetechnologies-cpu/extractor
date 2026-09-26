import re
import time
import logging
import requests
from bs4 import BeautifulSoup
from datetime import date, timedelta

logger = logging.getLogger(__name__)

_BASE = "https://www.merchantgenius.io"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.merchantgenius.io/",
}

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"\+?[\d\s.()\-]{7,20}")


def _fetch(url: str, session: requests.Session) -> BeautifulSoup | None:
    try:
        resp = session.get(url, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return None


def scrape_date_page(
    target_date: str,
    session: requests.Session,
) -> list[dict]:
    url = f"{_BASE}/shop/date/{target_date}"
    soup = _fetch(url, session)
    if not soup:
        return []
    return _parse_listing_page(soup)


def _parse_listing_page(soup: BeautifulSoup) -> list[dict]:
    rows = []

    containers = soup.select("div.blogContainer")
    if containers:
        by_domain: dict[str, dict] = {}
        for c in containers:
            biz = _parse_blog_container(c)
            if not biz.get("domain"):
                continue
            existing = by_domain.get(biz["domain"])
            if existing is None:
                by_domain[biz["domain"]] = biz
                rows.append(biz)
            else:
                for k, v in biz.items():
                    if v and not existing.get(k):
                        existing[k] = v
        return rows

    cards = soup.select("div.card, div.store-card, div.shop-card")
    if not cards:
        cards = soup.select("div.col-md-6, div.col-lg-4, div.col-md-4")
    if not cards:
        cards = _find_store_blocks(soup)

    for card in cards:
        biz = _parse_store_card(card)
        if biz and biz.get("name") and biz["name"] not in ("", "My Store"):
            rows.append(biz)

    if not rows:
        rows = _fallback_text_parse(soup)

    return rows


def _icon_text(card, icon: str) -> str:
    """Text that follows an <img src='/{icon}.png'> marker in a card footer."""
    img = card.find("img", src=re.compile(rf"/{icon}\.png$"))
    if not img:
        return ""
    parts = []
    for sib in img.next_siblings:
        if getattr(sib, "name", None) in ("img", "br"):
            break
        parts.append(sib.get_text(" ") if hasattr(sib, "get_text") else str(sib))
    return " ".join("".join(parts).split())


def _parse_blog_container(card) -> dict:
    name = ""
    domain = ""
    detail_url = ""
    description = ""
    currency = (card.get("data-currency") or "").strip()
    language = (card.get("data-language") or "").strip()

    link = card.find("a", href=re.compile(r"/shop/url/"))
    if link:
        href = link.get("href", "")
        detail_url = _BASE + href if href.startswith("/") else href
        domain = href.split("/shop/url/")[-1]

    h2 = card.find("h2")
    if h2:
        type_span = h2.find("span", class_="typeText")
        if type_span:
            domain = domain or type_span.get_text(strip=True)
        for s in h2.strings:
            text = s.strip()
            if text and text != domain:
                name = text
                break
        br = (h2.find_parent("a") or h2).find_next_sibling("br")
        if br:
            nxt = br.next_sibling
            desc_text = nxt.get_text(strip=True) if hasattr(nxt, "get_text") else str(nxt or "").strip()
            if desc_text and "no description" not in desc_text.lower():
                description = desc_text[:300]

    lang_match = re.search(r"\(\s*([A-Z]{3})\s*/\s*([^)]+?)\s*\)", card.get_text(" ", strip=True))
    if lang_match:
        currency = currency or lang_match.group(1)
        language = lang_match.group(2)

    email = ""
    em = _EMAIL_RE.search(_icon_text(card, "email"))
    if em:
        email = em.group(0)

    phone = ""
    phone_text = _icon_text(card, "phone")
    digits = re.sub(r"\D", "", phone_text)
    if 7 <= len(digits) <= 15:
        phone = phone_text

    return {
        "name": name or domain,
        "domain": domain,
        "email": email,
        "phone": phone,
        "currency": currency,
        "language": language,
        "description": description,
        "detail_url": detail_url,
        "platform": "Shopify",
    }


def _find_store_blocks(soup: BeautifulSoup) -> list:
    blocks = []
    for a in soup.find_all("a", href=re.compile(r"/shop/url/")):
        parent = a.find_parent("div")
        if parent and parent not in blocks:
            blocks.append(parent)
    return blocks


def _parse_store_card(card) -> dict:
    name = ""
    domain = ""
    email = ""
    phone = ""
    currency = ""
    language = ""
    description = ""
    detail_url = ""

    link = card.find("a", href=re.compile(r"/shop/url/"))
    if link:
        name = link.get_text(strip=True)
        name = re.sub(r"🔒\s*$", "", name).strip()
        href = link.get("href", "")
        if href:
            detail_url = _BASE + href if href.startswith("/") else href
            domain = href.split("/shop/url/")[-1] if "/shop/url/" in href else ""

    if not name:
        h_tag = card.find(["h3", "h4", "h5", "strong"])
        if h_tag:
            name = h_tag.get_text(strip=True)
            name = re.sub(r"🔒\s*$", "", name).strip()

    card_text = card.get_text(" ", strip=True)

    email_match = _EMAIL_RE.search(card_text)
    if email_match:
        email = email_match.group(0)

    phone_label = card.find(string=re.compile(r"phone|tel", re.I))
    if phone_label:
        parent = phone_label.find_parent()
        if parent:
            p_match = _PHONE_RE.search(parent.get_text())
            if p_match:
                digits = re.sub(r"\D", "", p_match.group(0))
                if 7 <= len(digits) <= 15:
                    phone = p_match.group(0).strip()

    if not phone:
        tel_link = card.find("a", href=re.compile(r"^tel:"))
        if tel_link:
            phone = tel_link.get_text(strip=True)

    if not phone:
        p_match = _PHONE_RE.search(card_text)
        if p_match and not _EMAIL_RE.match(p_match.group(0)):
            digits = re.sub(r"\D", "", p_match.group(0))
            if 7 <= len(digits) <= 15:
                phone = p_match.group(0).strip()

    cur_match = re.search(r"\b([A-Z]{3})\s*/\s*(\w+)", card_text)
    if cur_match:
        currency = cur_match.group(1)
        language = cur_match.group(2)

    desc_el = card.find("p")
    if desc_el:
        desc_text = desc_el.get_text(strip=True)
        if desc_text and "no description" not in desc_text.lower() and len(desc_text) > 10:
            description = desc_text[:300]

    return {
        "name": name,
        "domain": domain,
        "email": email,
        "phone": phone,
        "currency": currency,
        "language": language,
        "description": description,
        "detail_url": detail_url,
        "platform": "Shopify",
    }


def _fallback_text_parse(soup: BeautifulSoup) -> list[dict]:
    rows = []
    seen_domains = set()

    for a in soup.find_all("a", href=re.compile(r"/shop/url/")):
        href = a.get("href", "")
        domain = href.split("/shop/url/")[-1] if "/shop/url/" in href else ""
        if not domain or domain in seen_domains:
            continue
        seen_domains.add(domain)

        name = a.get_text(strip=True)
        name = re.sub(r"🔒\s*$", "", name).strip()
        name = re.sub(r"^\d+\.\s*", "", name).strip()

        parent = a.find_parent("div") or a.find_parent("li") or a.find_parent("tr")
        email = ""
        phone = ""
        currency = ""
        language = ""

        if parent:
            block_text = parent.get_text(" ", strip=True)
            em = _EMAIL_RE.search(block_text)
            if em:
                email = em.group(0)
            cur = re.search(r"\b([A-Z]{3})\s*/\s*(\w+)", block_text)
            if cur:
                currency = cur.group(1)
                language = cur.group(2)
            pm = _PHONE_RE.search(block_text)
            if pm and not _EMAIL_RE.match(pm.group(0)):
                digits = re.sub(r"\D", "", pm.group(0))
                if 7 <= len(digits) <= 15:
                    phone = pm.group(0).strip()

        rows.append({
            "name": name if name and name != domain else domain,
            "domain": domain,
            "email": email,
            "phone": phone,
            "currency": currency,
            "language": language,
            "description": "",
            "detail_url": _BASE + href if href.startswith("/") else href,
            "platform": "Shopify",
        })

    return rows


def search_stores(
    date_str: str = "",
    days: int = 1,
    progress_callback=None,
) -> list[dict]:
    session = requests.Session()
    all_results = []

    if date_str:
        start = date.fromisoformat(date_str)
    else:
        start = date.today() - timedelta(days=1)

    dates = [start - timedelta(days=i) for i in range(days)]
    total = len(dates)

    for idx, d in enumerate(dates):
        page_results = scrape_date_page(d.isoformat(), session)
        all_results.extend(page_results)

        if progress_callback:
            progress_callback(idx + 1, total)

        if idx < total - 1:
            time.sleep(1.5)

    return all_results
