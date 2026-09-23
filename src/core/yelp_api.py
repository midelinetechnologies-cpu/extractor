"""
Lead extractor built on free APIs — no keys, no signup, no scraping.

Pipeline:
  1. Nominatim (OSM geocoder)     -> "Austin, TX" becomes a bounding box
  2. Overpass API (OpenStreetMap) -> all businesses matching the term in that box

License: OSM data is open (ODbL). If you publish/redistribute the data,
attribute it as "© OpenStreetMap contributors".

Etiquette (public servers):
  - Nominatim: max 1 request/second, identify yourself via User-Agent
  - Overpass:  1 request per search (this module never spams it)
"""

import re
import time
import logging
import requests

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Two public Overpass instances with automatic failover
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

_HEADERS = {"User-Agent": "MailExtractor/1.0 (mailextractor.in)"}

# ---------------------------------------------------------------------------
# Search term -> OSM tag filters. Anything not listed here falls back to a
# case-insensitive regex across the main POI keys (shop/amenity/craft/office/
# healthcare/leisure/tourism), so unmapped terms still work.
# ---------------------------------------------------------------------------
CATEGORY_MAP = {
    "restaurant":   ['["amenity"="restaurant"]'],
    "cafe":         ['["amenity"="cafe"]'],
    "coffee shop":  ['["amenity"="cafe"]'],
    "bar":          ['["amenity"="bar"]', '["amenity"="pub"]'],
    "hair salon":   ['["shop"="hairdresser"]', '["shop"="beauty"]'],
    "barber":       ['["shop"="hairdresser"]'],
    "nail salon":   ['["shop"="beauty"]'],
    "spa":          ['["leisure"="spa"]', '["shop"="beauty"]'],
    "gym":          ['["leisure"="fitness_centre"]'],
    "dentist":      ['["amenity"="dentist"]', '["healthcare"="dentist"]'],
    "doctor":       ['["amenity"="doctors"]', '["healthcare"="doctor"]'],
    "chiropractor": ['["healthcare"="chiropractor"]'],
    "plumber":      ['["craft"="plumber"]'],
    "electrician":  ['["craft"="electrician"]'],
    "car repair":   ['["shop"="car_repair"]'],
    "mechanic":     ['["shop"="car_repair"]'],
    "real estate":  ['["office"="estate_agent"]'],
    "lawyer":       ['["office"="lawyer"]'],
    "attorney":     ['["office"="lawyer"]'],
    "accountant":   ['["office"="accountant"]', '["office"="tax_advisor"]'],
    "insurance":    ['["office"="insurance"]'],
    "hotel":        ['["tourism"="hotel"]', '["tourism"="guest_house"]'],
    "bakery":       ['["shop"="bakery"]'],
    "florist":      ['["shop"="florist"]'],
    "butcher":      ['["shop"="butcher"]'],
    "laundry":      ['["shop"="dry_cleaning"]', '["shop"="laundry"]'],
    "pet grooming": ['["shop"="pet_grooming"]'],
    "veterinary":   ['["amenity"="veterinary"]'],
}

_FALLBACK_KEYS = "|".join(
    ["shop", "amenity", "craft", "office", "healthcare", "leisure", "tourism"]
)

_PHONE_RE = re.compile(r"\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}")

_last_geocode = 0.0


def _geocode(location: str, session: requests.Session):
    """'Austin, TX' -> (south, west, north, east) bounding box, or None."""
    global _last_geocode
    wait = 1.1 - (time.time() - _last_geocode)
    if wait > 0:
        time.sleep(wait)  # Nominatim policy: max 1 req/sec
    _last_geocode = time.time()

    try:
        resp = session.get(
            NOMINATIM_URL,
            params={"q": location, "format": "json", "limit": 1},
            headers=_HEADERS,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("Geocoding failed for %r: %s", location, e)
        return None

    if not data:
        return None
    # Nominatim boundingbox = [south, north, west, east]
    south, north, west, east = (float(x) for x in data[0]["boundingbox"])
    return south, west, north, east


def _filters_for_term(term: str) -> list[str]:
    t = (term or "").strip().lower()
    if t in CATEGORY_MAP:
        return CATEGORY_MAP[t]
    escaped = re.escape(t)
    return [f'[~"^({_FALLBACK_KEYS})$"~"{escaped}",i]']


def _build_query(filters: list[str], bbox: tuple) -> str:
    south, west, north, east = bbox
    body = "\n".join(
        f"  nwr{f}({south:.5f},{west:.5f},{north:.5f},{east:.5f});"
        for f in filters
    )
    return f"[out:json][timeout:120];\n(\n{body}\n);\nout center;"


def _run_overpass(query: str, session: requests.Session) -> list[dict]:
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            resp = session.post(endpoint, data={"data": query}, timeout=180)
            if resp.status_code in (429, 502, 504):
                logger.warning("Overpass %s busy (%s), trying mirror…",
                               endpoint, resp.status_code)
                continue
            resp.raise_for_status()
            return resp.json().get("elements", [])
        except Exception as e:
            logger.warning("Overpass %s failed: %s", endpoint, e)
    return []


def _normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return raw.strip()


def _parse_element(el: dict) -> dict | None:
    tags = el.get("tags", {})
    name = tags.get("name", "").strip()
    if not name:
        return None

    phone_raw = (tags.get("phone") or tags.get("contact:phone")
                 or tags.get("telephone") or "")
    m = _PHONE_RE.search(phone_raw)
    phone = _normalize_phone(m.group(0)) if m else phone_raw.strip()

    website = (tags.get("website") or tags.get("contact:website") or "").strip()
    email   = (tags.get("email")   or tags.get("contact:email")   or "").strip()

    street = " ".join(x for x in (tags.get("addr:housenumber", ""),
                                  tags.get("addr:street", "")) if x)

    category = next(
        (tags[k] for k in ("shop", "amenity", "craft", "office",
                           "healthcare", "leisure", "tourism") if k in tags),
        "",
    )

    lat = el.get("lat") or el.get("center", {}).get("lat", "")
    lon = el.get("lon") or el.get("center", {}).get("lon", "")

    return {
        "name": name,
        "phone": phone,
        "email": email,               # bonus: OSM sometimes has it
        "website": website,
        "rating": 0,                  # ratings don't exist in open data
        "review_count": 0,
        "address": street,
        "city": tags.get("addr:city", ""),
        "state": tags.get("addr:state", "") or tags.get("addr:province", ""),
        "zip_code": tags.get("addr:postcode", ""),
        "categories": category,
        "price_range": "",
        "lat": lat,
        "lon": lon,
        "url": f"https://www.openstreetmap.org/{el.get('type', 'node')}/{el.get('id', '')}",
        "source": "openstreetmap",
    }


def search_businesses(
    location: str,
    term: str = "",
    limit: int = 20,
    with_contact_only: bool = True,
    progress_callback=None,
) -> dict:
    """
    Drop-in replacement for the old Yelp scraper (same return shape).

    with_contact_only: keep only businesses that have a phone, email, or
        website — recommended for lead lists, since a large share of OSM
        entries have no contact info at all.
    """
    session = requests.Session()

    if not (term or "").strip():
        return {"businesses": [], "total": 0,
                "error": "A search term is required (e.g. 'plumber')"}

    bbox = _geocode(location, session)
    if not bbox:
        return {"businesses": [], "total": 0,
                "error": f"Could not geocode location {location!r}"}

    query = _build_query(_filters_for_term(term), bbox)
    elements = _run_overpass(query, session)
    logger.info("Overpass returned %d raw elements for %r in %r",
                len(elements), term, location)

    businesses, seen = [], set()
    for el in elements:
        biz = _parse_element(el)
        if not biz:
            continue

        key = (biz["name"].lower(),
               f"{biz['lat']:.4f},{biz['lon']:.4f}" if biz["lat"] else biz["address"].lower())
        if key in seen:
            continue
        seen.add(key)

        if with_contact_only and not (biz["phone"] or biz["email"] or biz["website"]):
            continue

        businesses.append(biz)
        if progress_callback:
            progress_callback(len(businesses), limit)
        if len(businesses) >= limit:
            break

    return {"businesses": businesses, "total": len(businesses)}


def parse_results(data: dict) -> list[dict]:
    return data.get("businesses", [])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    data = search_businesses("Austin, TX", term="plumber", limit=25)
    for b in parse_results(data):
        print(f"{b['name']:<38} {b['phone']:<16} {b['website']}")

# import re
# import json
# import time
# import logging
# import requests
# from bs4 import BeautifulSoup
# from urllib.parse import urlencode, urljoin
# from concurrent.futures import ThreadPoolExecutor, as_completed

# logger = logging.getLogger(__name__)

# _HEADERS = {
#     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
#                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
#     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
#     "Accept-Language": "en-US,en;q=0.9",
#     "Accept-Encoding": "gzip, deflate, br",
#     "Referer": "https://www.yelp.com/",
# }


# def _fetch(url: str, session: requests.Session) -> BeautifulSoup | None:
#     try:
#         resp = session.get(url, headers=_HEADERS, timeout=20)
#         resp.raise_for_status()
#         return BeautifulSoup(resp.text, "lxml")
#     except Exception as e:
#         logger.warning("Failed to fetch %s: %s", url, e)
#         return None


# def _extract_json_data(soup: BeautifulSoup) -> list[dict]:
#     """Try to pull business data from Yelp's embedded JSON in script tags."""
#     rows = []
#     for script in soup.find_all("script", type="application/ld+json"):
#         try:
#             data = json.loads(script.string)
#             if isinstance(data, list):
#                 for item in data:
#                     if isinstance(item, dict) and item.get("@type") == "LocalBusiness":
#                         rows.append(_parse_ld_json(item))
#             elif isinstance(data, dict) and data.get("@type") == "LocalBusiness":
#                 rows.append(_parse_ld_json(data))
#         except (json.JSONDecodeError, TypeError):
#             continue
#     return rows


# def _parse_ld_json(item: dict) -> dict:
#     addr = item.get("address", {})
#     return {
#         "name": item.get("name", ""),
#         "phone": item.get("telephone", ""),
#         "rating": item.get("aggregateRating", {}).get("ratingValue", 0),
#         "review_count": item.get("aggregateRating", {}).get("reviewCount", 0),
#         "address": addr.get("streetAddress", ""),
#         "city": addr.get("addressLocality", ""),
#         "state": addr.get("addressRegion", ""),
#         "zip_code": addr.get("postalCode", ""),
#         "categories": "",
#         "url": item.get("url", ""),
#         "price_range": item.get("priceRange", ""),
#     }


# def _scrape_search_page(soup: BeautifulSoup) -> list[dict]:
#     """Parse business cards from Yelp search results HTML."""
#     results = []

#     json_results = _extract_json_data(soup)
#     if json_results:
#         return json_results

#     cards = soup.select('[data-testid="serp-ia-card"]')
#     if not cards:
#         cards = soup.select("div.container__09f24__FeTO6")
#     if not cards:
#         cards = soup.select("li.border-color--default__09f24__NPAKY")
#     if not cards:
#         cards = soup.select("div[class*='container'] h3")
#         if cards:
#             cards = [h3.find_parent("div", class_=re.compile("container")) for h3 in cards]
#             cards = [c for c in cards if c]

#     for card in cards:
#         biz = _parse_card(card)
#         if biz and biz.get("name"):
#             results.append(biz)

#     return results


# def _parse_card(card) -> dict:
#     name = ""
#     url = ""
#     rating = 0
#     review_count = 0
#     categories = ""
#     address = ""
#     phone = ""
#     price_range = ""

#     link = card.select_one("a[href*='/biz/']")
#     if link:
#         name = link.get_text(strip=True)
#         href = link.get("href", "")
#         if href.startswith("/"):
#             url = "https://www.yelp.com" + href
#         else:
#             url = href

#     if not name:
#         h3 = card.find("h3")
#         if h3:
#             name = h3.get_text(strip=True)
#     name = re.sub(r"^\d+\.\s*", "", name)

#     rating_el = card.select_one('[aria-label*="star rating"]')
#     if rating_el:
#         match = re.search(r"([\d.]+)\s*star", rating_el.get("aria-label", ""))
#         if match:
#             try:
#                 rating = float(match.group(1))
#             except ValueError:
#                 pass

#     review_el = card.find(string=re.compile(r"\d+\s*review"))
#     if review_el:
#         match = re.search(r"(\d+)", review_el)
#         if match:
#             review_count = int(match.group(1))

#     cat_spans = card.select("a[href*='cflt=']")
#     if cat_spans:
#         categories = "; ".join(s.get_text(strip=True) for s in cat_spans if s.get_text(strip=True))

#     price_el = card.find(string=re.compile(r"^\$+$"))
#     if price_el:
#         price_range = price_el.strip()

#     all_text = card.get_text(" ", strip=True)
#     phone_match = re.search(r"\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}", all_text)
#     if phone_match:
#         phone = phone_match.group(0)

#     return {
#         "name": name,
#         "phone": phone,
#         "rating": rating,
#         "review_count": review_count,
#         "address": address,
#         "city": "",
#         "state": "",
#         "zip_code": "",
#         "categories": categories,
#         "url": url,
#         "price_range": price_range,
#     }


# def _scrape_biz_page(url: str, session: requests.Session) -> dict:
#     """Scrape a single Yelp business page for phone, address, website."""
#     soup = _fetch(url, session)
#     if not soup:
#         return {}

#     info = {}

#     phone_link = soup.select_one('a[href^="tel:"]')
#     if phone_link:
#         info["phone"] = phone_link.get_text(strip=True)

#     for p_tag in soup.find_all("p"):
#         text = p_tag.get_text(strip=True)
#         phone_match = re.search(r"\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}", text)
#         if phone_match and "phone" not in info:
#             info["phone"] = phone_match.group(0)

#     addr_tag = soup.select_one("address")
#     if addr_tag:
#         info["full_address"] = addr_tag.get_text(" ", strip=True)

#     for a in soup.find_all("a", href=True):
#         href = a.get("href", "")
#         if "biz_redir" in href and "url=" in href:
#             match = re.search(r"url=([^&]+)", href)
#             if match:
#                 from urllib.parse import unquote
#                 info["website"] = unquote(match.group(1))
#                 break

#     return info


# def search_businesses(
#     location: str,
#     term: str = "",
#     limit: int = 20,
#     progress_callback=None,
# ) -> dict:
#     session = requests.Session()
#     all_results = []
#     pages_needed = (limit + 9) // 10

#     for page in range(pages_needed):
#         params = {"find_loc": location, "start": page * 10}
#         if term:
#             params["find_desc"] = term

#         url = "https://www.yelp.com/search?" + urlencode(params)
#         soup = _fetch(url, session)
#         if not soup:
#             break

#         page_results = _scrape_search_page(soup)
#         if not page_results:
#             break

#         all_results.extend(page_results)

#         if progress_callback:
#             progress_callback(min(len(all_results), limit), limit)

#         if len(all_results) >= limit:
#             break

#         if page < pages_needed - 1:
#             time.sleep(1.5)

#     all_results = all_results[:limit]

#     biz_urls = [r["url"] for r in all_results if r.get("url") and not r.get("phone")]
#     if biz_urls:
#         def _enrich(idx_url):
#             idx, burl = idx_url
#             time.sleep(0.8 * idx)
#             return idx, _scrape_biz_page(burl, session)

#         with ThreadPoolExecutor(max_workers=3) as pool:
#             futures = {pool.submit(_enrich, (i, u)): i for i, u in enumerate(biz_urls)}
#             for future in as_completed(futures):
#                 try:
#                     idx, extra = future.result()
#                     if extra:
#                         r = next((r for r in all_results if r["url"] == biz_urls[idx]), None)
#                         if r:
#                             if extra.get("phone") and not r.get("phone"):
#                                 r["phone"] = extra["phone"]
#                             if extra.get("full_address") and not r.get("address"):
#                                 r["address"] = extra["full_address"]
#                             if extra.get("website"):
#                                 r["website"] = extra["website"]
#                 except Exception:
#                     pass

#     return {"businesses": all_results, "total": len(all_results)}


# def parse_results(data: dict) -> list[dict]:
#     return data.get("businesses", [])
