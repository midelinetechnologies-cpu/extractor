import os
import logging
import requests

logger = logging.getLogger(__name__)

PLACES_URL = "https://api.geoapify.com/v2/places"
GEOCODE_URL = "https://api.geoapify.com/v1/geocode/search"

CATEGORY_MAP = {
    "Restaurant": "catering.restaurant",
    "Cafe / Coffee Shop": "catering.cafe",
    "Fast Food": "catering.fast_food",
    "Bar / Pub": "catering.bar,catering.pub",
    "Bakery": "commercial.food_and_drink.bakery",
    "Butcher": "commercial.food_and_drink.butcher",
    "Supermarket": "commercial.supermarket",
    "Hotel": "accommodation.hotel",
    "Guest House": "accommodation.guest_house",
    "Doctor / Clinic": "healthcare.clinic_or_praxis",
    "Dentist": "healthcare.dentist",
    "Hospital": "healthcare.hospital",
    "Pharmacy": "healthcare.pharmacy",
    "Veterinary": "pet.veterinary",
    "Gym / Fitness": "sport.fitness",
    "Spa": "leisure.spa",
    "Hair Salon": "service.beauty.hairdresser",
    "Beauty / Massage": "service.beauty",
    "Lawyer": "office.lawyer",
    "Accountant": "office.accountant",
    "Real Estate Agent": "office.estate_agent",
    "Insurance": "office.insurance",
    "Bank / ATM": "service.financial",
    "Car Repair": "service.vehicle.repair",
    "Car Wash": "service.vehicle.car_wash",
    "Fuel Station": "service.vehicle.fuel",
    "EV Charging": "service.vehicle.charging_station",
    "Electrician": "service.electrician",
    "Plumber": "service.blacksmith",
    "Laundry / Dry Cleaning": "service.cleaning",
    "Tailor": "service.tailor",
    "School": "education.school",
    "University": "education.university",
    "Library": "education.library",
    "Shopping Mall": "commercial.shopping_mall",
    "Clothing Store": "commercial.clothing",
    "Electronics Store": "commercial.elektronics",
    "Florist": "commercial.florist",
    "Pet Shop": "commercial.pet",
    "Jewelry": "commercial.jewelry",
    "Museum": "entertainment.museum",
    "Cinema": "entertainment.cinema",
    "Theatre": "entertainment.culture.theatre",
    "Zoo": "entertainment.zoo",
    "Police Station": "service.police",
    "Fire Station": "service.fire_station",
    "Post Office": "service.post.office",
    "Travel Agency": "service.travel_agency",
    "Parking": "parking",
}


def _get_api_key() -> str:
    key = os.environ.get("GEOAPIFY_API_KEY", "7166a07eed0542fc9ef72480b7c53154")
    if not key:
        raise ValueError(
            "GEOAPIFY_API_KEY is not set. "
            "Get a free key at https://myprojects.geoapify.com/"
        )
    return key


def _geocode(location: str, api_key: str) -> tuple[float, float] | None:
    try:
        resp = requests.get(
            GEOCODE_URL,
            params={"text": location, "apiKey": api_key, "limit": 1},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        if not features:
            return None
        props = features[0]["properties"]
        return props["lat"], props["lon"]
    except Exception as e:
        logger.warning("Geocode failed for %r: %s", location, e)
        return None


def search_places(
    location: str,
    category_key: str,
    radius: int = 10000,
    limit: int = 100,
    progress_callback=None,
) -> dict:
    api_key = _get_api_key()

    coords = _geocode(location, api_key)
    if not coords:
        return {"results": [], "total": 0,
                "error": f"Could not find location '{location}'"}

    lat, lon = coords
    categories = CATEGORY_MAP.get(category_key, category_key)

    all_results = []
    offset = 0
    page_size = min(limit, 500)

    while len(all_results) < limit:
        params = {
            "categories": categories,
            "filter": f"circle:{lon},{lat},{radius}",
            "bias": f"proximity:{lon},{lat}",
            "limit": page_size,
            "offset": offset,
            "apiKey": api_key,
        }

        try:
            resp = requests.get(PLACES_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.warning("Geoapify request failed: %s", e)
            if all_results:
                break
            return {"results": [], "total": 0, "error": str(e)}

        features = data.get("features", [])
        if not features:
            break

        for feat in features:
            props = feat.get("properties", {})
            name = props.get("name", "").strip()
            if not name:
                continue

            cats = props.get("categories", [])
            cat_display = ", ".join(
                c.split(".")[-1].replace("_", " ").title()
                for c in cats
                if c != categories.split(",")[0].rsplit(".", 1)[0]
            )

            contact = props.get("contact") or {}
            if not isinstance(contact, dict):
                contact = {}

            all_results.append({
                "name": name,
                "phone": str(contact.get("phone") or "").strip(),
                "email": str(contact.get("email") or "").strip(),
                "website": str(props.get("website") or contact.get("website") or "").strip(),
                "address": str(props.get("formatted") or ""),
                "street": str(props.get("street") or ""),
                "city": str(props.get("city") or ""),
                "state": str(props.get("state") or ""),
                "postcode": str(props.get("postcode") or ""),
                "country": str(props.get("country") or ""),
                "categories": cat_display,
                "lat": props.get("lat", ""),
                "lon": props.get("lon", ""),
                "place_id": props.get("place_id", ""),
            })

            if progress_callback:
                progress_callback(len(all_results), limit)

            if len(all_results) >= limit:
                break

        offset += page_size
        if len(features) < page_size:
            break

    return {"results": all_results[:limit], "total": len(all_results)}
