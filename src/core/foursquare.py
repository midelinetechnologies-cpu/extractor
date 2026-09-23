import os
import logging
import requests

logger = logging.getLogger(__name__)

SEARCH_URL = "https://api.foursquare.com/v3/places/search"
GEOCODE_URL = "https://api.geoapify.com/v1/geocode/search"

CATEGORY_MAP = {
    "Restaurant": "13065",
    "Cafe": "13032",
    "Coffee Shop": "13035",
    "Fast Food": "13145",
    "Bar": "13003",
    "Pub": "13025",
    "Bakery": "13002",
    "Butcher": "17069",
    "Supermarket": "17143",
    "Grocery Store": "17069",
    "Hotel": "19014",
    "Motel": "19018",
    "Guest House": "19009",
    "Doctor": "15014",
    "Dentist": "15008",
    "Hospital": "15015",
    "Pharmacy": "17108",
    "Veterinarian": "11134",
    "Gym / Fitness": "18021",
    "Yoga Studio": "18023",
    "Spa": "11098",
    "Hair Salon": "11050",
    "Barber": "11050",
    "Nail Salon": "11063",
    "Beauty Salon": "11007",
    "Lawyer": "12072",
    "Accountant": "12002",
    "Real Estate": "12083",
    "Insurance": "12065",
    "Bank": "11045",
    "ATM": "11044",
    "Car Repair": "17001",
    "Car Wash": "17003",
    "Gas Station": "19007",
    "EV Charging": "19006",
    "Electrician": "12034",
    "Plumber": "12080",
    "Laundry": "11059",
    "Tailor": "17125",
    "School": "12055",
    "University": "12058",
    "Library": "12060",
    "Shopping Mall": "17114",
    "Clothing Store": "17032",
    "Electronics Store": "17048",
    "Florist": "17053",
    "Pet Store": "17107",
    "Jewelry Store": "17073",
    "Museum": "10027",
    "Cinema": "10024",
    "Theater": "10025",
    "Zoo": "10057",
    "Park": "16032",
    "Police Station": "12079",
    "Fire Station": "12037",
    "Post Office": "12082",
    "Travel Agency": "12096",
    "Parking": "19020",
}


def _get_fsq_key() -> str:
    key = os.environ.get("FOURSQUARE_API_KEY", "MECIG5NKN2B51DBR4M3ALE2M2P4VSWTRHRBNWO5Y2FQXYEON")
    if not key:
        raise ValueError(
            "FOURSQUARE_API_KEY is not set. "
            "Get a free key at https://location.foursquare.com/"
        )
    return key


def _geocode(location: str) -> tuple[float, float] | None:
    geo_key = os.environ.get("GEOAPIFY_API_KEY", "")
    if geo_key:
        try:
            resp = requests.get(
                GEOCODE_URL,
                params={"text": location, "apiKey": geo_key, "limit": 1},
                timeout=15,
            )
            resp.raise_for_status()
            features = resp.json().get("features", [])
            if features:
                p = features[0]["properties"]
                return p["lat"], p["lon"]
        except Exception:
            pass

    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": location, "format": "json", "limit": 1},
            headers={"User-Agent": "MailExtractor/1.0 (mailextractor.in)"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        logger.warning("Geocode failed for %r: %s", location, e)

    return None


def search_places(
    location: str,
    category_key: str,
    radius: int = 10000,
    limit: int = 50,
    progress_callback=None,
) -> dict:
    api_key = _get_fsq_key()

    coords = _geocode(location)
    if not coords:
        return {"results": [], "total": 0,
                "error": f"Could not find location '{location}'"}

    lat, lon = coords
    categories = CATEGORY_MAP.get(category_key, category_key)

    headers = {
        "Authorization": api_key,
        "Accept": "application/json",
    }

    all_results = []
    page_limit = min(limit, 50)

    while len(all_results) < limit:
        params = {
            "ll": f"{lat},{lon}",
            "radius": radius,
            "categories": categories,
            "limit": page_limit,
        }

        try:
            resp = requests.get(
                SEARCH_URL, headers=headers, params=params, timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.HTTPError as e:
            msg = str(e)
            if resp.status_code == 401:
                msg = ("Foursquare API key is invalid or expired. "
                       "Get a new key at https://location.foursquare.com/")
            elif resp.status_code == 429:
                msg = "Foursquare rate limit reached. Try again later."
            logger.warning("Foursquare request failed: %s", msg)
            return {"results": [], "total": 0, "error": msg}
        except Exception as e:
            logger.warning("Foursquare request failed: %s", e)
            return {"results": [], "total": 0, "error": str(e)}

        results = data.get("results", [])
        if not results:
            break

        for place in results:
            loc = place.get("location", {})
            if not isinstance(loc, dict):
                loc = {}
            cats = place.get("categories", [])
            if not isinstance(cats, list):
                cats = []
            cat_names = ", ".join(str(c.get("name", "")) for c in cats if isinstance(c, dict) and c.get("name"))

            all_results.append({
                "name": str(place.get("name") or ""),
                "phone": str(place.get("tel") or ""),
                "email": str(place.get("email") or ""),
                "website": str(place.get("website") or ""),
                "address": str(loc.get("formatted_address") or loc.get("address") or ""),
                "city": str(loc.get("locality") or ""),
                "state": str(loc.get("region") or ""),
                "postcode": str(loc.get("postcode") or ""),
                "country": str(loc.get("country") or ""),
                "categories": cat_names,
                "fsq_id": str(place.get("fsq_id") or ""),
            })

            if progress_callback:
                progress_callback(len(all_results), limit)

            if len(all_results) >= limit:
                break

        break

    return {"results": all_results[:limit], "total": len(all_results)}
