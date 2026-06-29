import copy
import csv
import json
import time
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

from .constants import (
    BOOLEAN_VALUES,
    DEFAULT_PROPERTY_TYPES,
    DEFAULT_SORT_BY,
    FIELDNAMES,
    FILTER_TYPE_OPTIONS,
    FRENCH_SLUG_TO_DB,
    HEADERS,
    MAX_LIMIT_VAL,
    NUMBER_VALUES,
    REVERSED_URL_PARAMETERS,
    ROOMS_PATTERN_MINUS,
    ROOMS_PATTERN_PLUS,
    ROOMS_PATTERN_RANGE,
    ROOMS_PATTERN_SINGLE,
)


API_URL = "https://www.bienici.com/realEstateAds.json"
SUGGEST_URL = "https://res.bienici.com/suggest.json"
PAGE_SIZE = 24
MAX_API_PAGE = 104
DEFAULT_TIMEOUT = 20
SLEEP_BETWEEN_PAGES = 2
SLEEP_ON_RATE_LIMIT = 30
SLEEP_ON_FORBIDDEN = 60


class ScraperError(RuntimeError):
    """Raised when Bien'ici cannot be scraped with the provided parameters."""


class BienIciScraper:
    def __init__(self, url: str, limit: int | None, output: str):
        if not url:
            raise ValueError("A Bien'ici search URL is required.")
        if not output:
            raise ValueError("An output CSV path is required.")
        if limit is not None and (limit < 1 or limit > MAX_LIMIT_VAL):
            raise ValueError(f"limit must be between 1 and {MAX_LIMIT_VAL}.")

        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.data: list[dict] = []
        self.total_scraped_results = 0
        self.page = 1
        self.limit = limit
        self.url = url
        self.output = output

    def convert_url_to_api_parameters(self, url: str) -> dict:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        path = parsed_url.path

        filters: dict = {
            "size": PAGE_SIZE,
            "from": None,
            "page": None,
            "onTheMarket": [True],
        }

        location_ids = self.get_location_ids(path)
        if location_ids:
            filters["zoneIdsByTypes"] = {"zoneIds": location_ids}

        for slug, value in FILTER_TYPE_OPTIONS.items():
            if slug in path:
                filters["filterType"] = value

        property_types = [value for slug, value in FRENCH_SLUG_TO_DB.items() if slug in path]
        filters["propertyType"] = property_types if property_types else DEFAULT_PROPERTY_TYPES

        min_rooms, max_rooms = self._extract_room_filters(path)
        if min_rooms:
            filters["minRooms"] = min_rooms
        if max_rooms:
            filters["maxRooms"] = max_rooms

        self._apply_query_parameters(filters, query_params)

        if "sortBy" not in filters:
            sort_by, sort_order = DEFAULT_SORT_BY
            filters["sortBy"] = sort_by
            filters["sortOrder"] = sort_order

        return {"filters": filters}

    def get_location_ids(self, path: str) -> list:
        path_parts = [part for part in path.split("/") if part]
        location_slugs = self._extract_location_slugs(path_parts)

        if not location_slugs:
            return []

        location_ids = []
        for location_slug in location_slugs:
            if location_slug == "france":
                continue

            print(f"searching location id for {location_slug}")
            try:
                response = self.session.get(
                    SUGGEST_URL,
                    params={"q": location_slug},
                    timeout=DEFAULT_TIMEOUT,
                )
                response.raise_for_status()
                suggestions = response.json()
            except requests.RequestException as exc:
                raise ScraperError(f"Unable to resolve Bien'ici location '{location_slug}': {exc}") from exc

            if not suggestions:
                raise ScraperError(f"No Bien'ici location found for '{location_slug}'.")

            zone_ids = suggestions[0].get("zoneIds", [])
            if not zone_ids:
                raise ScraperError(f"No Bien'ici zone id found for '{location_slug}'.")

            for zone_id in zone_ids:
                print(f"found {zone_id}")
                location_ids.append(zone_id)

        return location_ids

    def go_api_page(self, params: dict) -> requests.Response:
        print(f"going to page: {self.page}")
        time.sleep(SLEEP_BETWEEN_PAGES)

        for attempt in range(1, 4):
            try:
                response = self.session.get(
                    API_URL,
                    params=params,
                    timeout=DEFAULT_TIMEOUT,
                )
            except requests.RequestException as exc:
                if attempt == 3:
                    raise ScraperError(f"Network error while calling Bien'ici: {exc}") from exc
                print(f"network error, retry {attempt}/3")
                time.sleep(5 * attempt)
                continue

            print(f"status: {response.status_code}")

            if response.status_code == 200:
                return response
            if response.status_code == 429:
                print(f"rate limited (429), waiting {SLEEP_ON_RATE_LIMIT}s")
                time.sleep(SLEEP_ON_RATE_LIMIT)
                continue
            if response.status_code == 403:
                print(f"forbidden (403), waiting {SLEEP_ON_FORBIDDEN}s")
                time.sleep(SLEEP_ON_FORBIDDEN)
                continue
            if response.status_code == 400:
                raise ScraperError("Bien'ici rejected the request parameters (HTTP 400).")

            raise ScraperError(f"Unexpected Bien'ici HTTP status: {response.status_code}")

        raise ScraperError("Bien'ici kept rate-limiting or forbidding the request after 3 attempts.")

    def collect_results(self) -> None:
        params = self.convert_url_to_api_parameters(self.url)

        while True:
            if self.page > MAX_API_PAGE:
                print(f"API page limit reached ({MAX_API_PAGE}), stopping cleanly")
                break

            params["filters"]["page"] = self.page
            params["filters"]["from"] = (self.page - 1) * PAGE_SIZE

            request_params = copy.deepcopy(params)
            request_params["filters"] = json.dumps(request_params["filters"])

            response = self.go_api_page(request_params)
            payload = response.json()
            total_available_results = payload.get("total", 0)
            ads = payload.get("realEstateAds", [])

            if self.page == 1:
                total_to_scrape = min(total_available_results, MAX_LIMIT_VAL, self.limit or MAX_LIMIT_VAL)
                print(f"total results: {total_available_results}")
                print(f"total results to scrape: {total_to_scrape}")

            if not ads:
                print("no ads returned, stopping")
                break

            for ad in ads:
                self.data.append(self.parse_ad(ad))
                self.total_scraped_results += 1

                if self.limit and self.total_scraped_results >= self.limit:
                    print("limit reached")
                    self.write_to_csv()
                    return

            if self.total_scraped_results >= min(total_available_results, MAX_LIMIT_VAL):
                print("all available data collected")
                break

            self.page += 1

        self.write_to_csv()

    def parse_ad(self, ad: dict) -> dict:
        city = ad.get("city", "")
        postal_code = ad.get("postalCode", "")
        ad_type = ad.get("adType", "")
        property_type = ad.get("propertyType", "")
        reference = ad.get("reference", "")
        title = ad.get("title", "")
        publication_date = ad.get("publicationDate", "")
        modification_date = ad.get("modificationDate", "")
        new_property = ad.get("newProperty", "")
        rooms_quantity = ad.get("roomsQuantity", "")
        bedrooms_quantity = ad.get("bedroomsQuantity", "")
        price = ad.get("price", "")
        surface = ad.get("surfaceArea", "")
        url = ad.get("url") or self._build_ad_url(ad, city, property_type, rooms_quantity, ad_type)

        print(f"scraped: {title}")

        return dict(
            zip(
                FIELDNAMES,
                [
                    city,
                    postal_code,
                    ad_type,
                    property_type,
                    reference,
                    title,
                    publication_date,
                    modification_date,
                    new_property,
                    rooms_quantity,
                    bedrooms_quantity,
                    price,
                    surface,
                    url,
                ],
            )
        )

    def write_to_csv(self) -> None:
        output_path = Path(self.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(self.data)

        print(f"csv written: {output_path} ({len(self.data)} rows)")

    @staticmethod
    def _extract_location_slugs(path_parts: list[str]) -> list[str]:
        if len(path_parts) < 3:
            return []
        if path_parts[0] == "recherche" and path_parts[1] in FILTER_TYPE_OPTIONS:
            return path_parts[2].split(",")
        return []

    @staticmethod
    def _extract_room_filters(path: str) -> tuple[int | None, int | None]:
        if match := ROOMS_PATTERN_PLUS.search(path):
            return int(match.group(1)), None
        if match := ROOMS_PATTERN_MINUS.search(path):
            return None, int(match.group(1))
        if match := ROOMS_PATTERN_RANGE.search(path):
            return int(match.group(1)), int(match.group(2))
        if match := ROOMS_PATTERN_SINGLE.search(path):
            rooms = int(match.group(1))
            return rooms, rooms
        return None, None

    @staticmethod
    def _apply_query_parameters(filters: dict, query_params: dict) -> None:
        for key, values in query_params.items():
            if not values:
                continue

            value = values[0]
            internal_key = REVERSED_URL_PARAMETERS.get(key)

            if internal_key in NUMBER_VALUES:
                filters[internal_key] = int(value)
            elif internal_key in BOOLEAN_VALUES:
                filters[internal_key] = value.lower() not in {"non", "false", "0"}
            elif key == "classification-energetique":
                filters["energyClassification"] = value.split(",")
            elif key == "tri":
                sort_value = value.split("-", 1)
                if len(sort_value) == 2:
                    filters["sortBy"], filters["sortOrder"] = sort_value

    @staticmethod
    def _build_ad_url(
        ad: dict,
        city: str,
        property_type: str,
        rooms_quantity: str | int,
        ad_type: str,
    ) -> str:
        db_to_french_slug = {
            "house": "maison",
            "flat": "appartement",
            "parking": "parking",
            "terrain": "terrain",
            "building": "batiment",
            "castle": "chateau",
            "loft": "loft",
            "office": "bureau",
            "premises": "local",
            "shop": "commerce",
            "townhouse": "hotel",
            "annexe": "annexe",
            "others": "autres",
            "programme": "programme",
        }
        ad_type_fr = ad.get("adTypeFR") or {"buy": "vente", "rent": "location"}.get(ad_type, ad_type)
        city_slug = _slugify(city)
        property_type_slug = db_to_french_slug.get(property_type, property_type)
        rooms_slug = f"{rooms_quantity}pieces" if rooms_quantity else ""
        ad_id = ad.get("id", "")
        return f"https://www.bienici.com/annonce/{ad_type_fr}/{city_slug}/{property_type_slug}/{rooms_slug}/{ad_id}"


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_value.lower().replace(" ", "-").replace("'", "-")


def scrape(
    url: str = "https://www.bienici.com/recherche/achat/france/chateau",
    limit: int | None = 2500,
    output: str = "data_bienici_lobstr_io.csv",
) -> None:
    start = time.perf_counter()
    scraper = BienIciScraper(url=url, limit=limit, output=output)
    scraper.collect_results()

    elapsed = time.perf_counter() - start
    print(f"elapsed: {elapsed:.2f}s")
    print("success")
