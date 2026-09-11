import re
import json
import time
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.yelp.com/",
}


def _fetch(url: str, session: requests.Session) -> BeautifulSoup | None:
    try:
        resp = session.get(url, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except Exception as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return None


def _extract_json_data(soup: BeautifulSoup) -> list[dict]:
    """Try to pull business data from Yelp's embedded JSON in script tags."""
    rows = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("@type") == "LocalBusiness":
                        rows.append(_parse_ld_json(item))
            elif isinstance(data, dict) and data.get("@type") == "LocalBusiness":
                rows.append(_parse_ld_json(data))
        except (json.JSONDecodeError, TypeError):
            continue
    return rows


def _parse_ld_json(item: dict) -> dict:
    addr = item.get("address", {})
    return {
        "name": item.get("name", ""),
        "phone": item.get("telephone", ""),
        "rating": item.get("aggregateRating", {}).get("ratingValue", 0),
        "review_count": item.get("aggregateRating", {}).get("reviewCount", 0),
        "address": addr.get("streetAddress", ""),
        "city": addr.get("addressLocality", ""),
        "state": addr.get("addressRegion", ""),
        "zip_code": addr.get("postalCode", ""),
        "categories": "",
        "url": item.get("url", ""),
        "price_range": item.get("priceRange", ""),
    }


def _scrape_search_page(soup: BeautifulSoup) -> list[dict]:
    """Parse business cards from Yelp search results HTML."""
    results = []

    json_results = _extract_json_data(soup)
    if json_results:
        return json_results

    cards = soup.select('[data-testid="serp-ia-card"]')
    if not cards:
        cards = soup.select("div.container__09f24__FeTO6")
    if not cards:
        cards = soup.select("li.border-color--default__09f24__NPAKY")
    if not cards:
        cards = soup.select("div[class*='container'] h3")
        if cards:
            cards = [h3.find_parent("div", class_=re.compile("container")) for h3 in cards]
            cards = [c for c in cards if c]

    for card in cards:
        biz = _parse_card(card)
        if biz and biz.get("name"):
            results.append(biz)

    return results


def _parse_card(card) -> dict:
    name = ""
    url = ""
    rating = 0
    review_count = 0
    categories = ""
    address = ""
    phone = ""
    price_range = ""

    link = card.select_one("a[href*='/biz/']")
    if link:
        name = link.get_text(strip=True)
        href = link.get("href", "")
        if href.startswith("/"):
            url = "https://www.yelp.com" + href
        else:
            url = href

    if not name:
        h3 = card.find("h3")
        if h3:
            name = h3.get_text(strip=True)
    name = re.sub(r"^\d+\.\s*", "", name)

    rating_el = card.select_one('[aria-label*="star rating"]')
    if rating_el:
        match = re.search(r"([\d.]+)\s*star", rating_el.get("aria-label", ""))
        if match:
            try:
                rating = float(match.group(1))
            except ValueError:
                pass

    review_el = card.find(string=re.compile(r"\d+\s*review"))
    if review_el:
        match = re.search(r"(\d+)", review_el)
        if match:
            review_count = int(match.group(1))

    cat_spans = card.select("a[href*='cflt=']")
    if cat_spans:
        categories = "; ".join(s.get_text(strip=True) for s in cat_spans if s.get_text(strip=True))

    price_el = card.find(string=re.compile(r"^\$+$"))
    if price_el:
        price_range = price_el.strip()

    all_text = card.get_text(" ", strip=True)
    phone_match = re.search(r"\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}", all_text)
    if phone_match:
        phone = phone_match.group(0)

    return {
        "name": name,
        "phone": phone,
        "rating": rating,
        "review_count": review_count,
        "address": address,
        "city": "",
        "state": "",
        "zip_code": "",
        "categories": categories,
        "url": url,
        "price_range": price_range,
    }


def _scrape_biz_page(url: str, session: requests.Session) -> dict:
    """Scrape a single Yelp business page for phone, address, website."""
    soup = _fetch(url, session)
    if not soup:
        return {}

    info = {}

    phone_link = soup.select_one('a[href^="tel:"]')
    if phone_link:
        info["phone"] = phone_link.get_text(strip=True)

    for p_tag in soup.find_all("p"):
        text = p_tag.get_text(strip=True)
        phone_match = re.search(r"\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}", text)
        if phone_match and "phone" not in info:
            info["phone"] = phone_match.group(0)

    addr_tag = soup.select_one("address")
    if addr_tag:
        info["full_address"] = addr_tag.get_text(" ", strip=True)

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if "biz_redir" in href and "url=" in href:
            match = re.search(r"url=([^&]+)", href)
            if match:
                from urllib.parse import unquote
                info["website"] = unquote(match.group(1))
                break

    return info


def search_businesses(
    location: str,
    term: str = "",
    limit: int = 20,
    progress_callback=None,
) -> dict:
    session = requests.Session()
    all_results = []
    pages_needed = (limit + 9) // 10

    for page in range(pages_needed):
        params = {"find_loc": location, "start": page * 10}
        if term:
            params["find_desc"] = term

        url = "https://www.yelp.com/search?" + urlencode(params)
        soup = _fetch(url, session)
        if not soup:
            break

        page_results = _scrape_search_page(soup)
        if not page_results:
            break

        all_results.extend(page_results)

        if progress_callback:
            progress_callback(min(len(all_results), limit), limit)

        if len(all_results) >= limit:
            break

        if page < pages_needed - 1:
            time.sleep(1.5)

    all_results = all_results[:limit]

    biz_urls = [r["url"] for r in all_results if r.get("url") and not r.get("phone")]
    if biz_urls:
        def _enrich(idx_url):
            idx, burl = idx_url
            time.sleep(0.8 * idx)
            return idx, _scrape_biz_page(burl, session)

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(_enrich, (i, u)): i for i, u in enumerate(biz_urls)}
            for future in as_completed(futures):
                try:
                    idx, extra = future.result()
                    if extra:
                        r = next((r for r in all_results if r["url"] == biz_urls[idx]), None)
                        if r:
                            if extra.get("phone") and not r.get("phone"):
                                r["phone"] = extra["phone"]
                            if extra.get("full_address") and not r.get("address"):
                                r["address"] = extra["full_address"]
                            if extra.get("website"):
                                r["website"] = extra["website"]
                except Exception:
                    pass

    return {"businesses": all_results, "total": len(all_results)}


def parse_results(data: dict) -> list[dict]:
    return data.get("businesses", [])
