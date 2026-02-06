"""
JustWatch-based deep link fetcher.
Best-effort: returns provider links when available.
"""

import re
from functools import lru_cache

from justwatch import JustWatch


def _normalize_title(value):
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _extract_year(release_date):
    if not release_date or len(release_date) < 4:
        return None
    year = release_date[:4]
    return int(year) if year.isdigit() else None


@lru_cache(maxsize=16)
def _get_client(country):
    return JustWatch(country=country)


@lru_cache(maxsize=16)
def _get_provider_map(country):
    client = _get_client(country)
    providers = {}
    for provider in client.get_providers():
        provider_id = provider.get("id")
        if provider_id is not None:
            providers[provider_id] = provider
    return providers


def _pick_best_item(items, title, year):
    if not items:
        return None

    norm_title = _normalize_title(title)
    best = None
    best_score = -1

    for item in items:
        obj_type = (item.get("object_type") or item.get("content_type") or "").lower()
        if obj_type and obj_type != "movie":
            continue

        item_title = item.get("title") or ""
        item_year = (
            item.get("original_release_year")
            or item.get("cinema_release_year")
            or item.get("release_year")
        )
        score = 0

        if year and item_year and int(item_year) == int(year):
            score += 5

        norm_item_title = _normalize_title(item_title)
        if norm_item_title == norm_title:
            score += 5
        elif norm_title and (norm_title in norm_item_title or norm_item_title in norm_title):
            score += 3

        if score > best_score:
            best_score = score
            best = item

    return best


def _offer_link(offer):
    urls = offer.get("urls") or {}
    return (
        urls.get("deeplink_web")
        or urls.get("standard_web")
        or urls.get("deeplink_android_tv")
        or urls.get("deeplink_ios")
        or ""
    )


def _map_offer_type(monetization_type):
    mapping = {
        "free": "free",
        "flatrate": "subscription",
        "ads": "ads",
        "rent": "rent",
        "buy": "buy",
    }
    return mapping.get(monetization_type, monetization_type or "")


def fetch_justwatch_links(title, release_date=None, country="IN"):
    if not title:
        return {}

    client = _get_client(country)
    providers = _get_provider_map(country)
    year = _extract_year(release_date)

    try:
        results = client.search_for_item(query=title)
    except Exception:
        return {}

    items = results.get("items") if isinstance(results, dict) else None
    best_item = _pick_best_item(items or [], title, year)
    if not best_item:
        return {}

    offers = best_item.get("offers") or []
    if not offers:
        return {}

    priority = {"free": 5, "flatrate": 4, "ads": 3, "rent": 2, "buy": 1}
    output = {}

    for offer in offers:
        provider_id = offer.get("provider_id")
        provider = providers.get(provider_id, {})
        name = provider.get("clear_name") or provider.get("short_name") or "Unknown"
        link = _offer_link(offer)
        if not link:
            continue

        monetization_type = offer.get("monetization_type") or ""
        offer_type = _map_offer_type(monetization_type)
        is_free = monetization_type == "free"

        current = output.get(name)
        current_priority = priority.get(current.get("monetization_type"), 0) if current else 0
        new_priority = priority.get(monetization_type, 0)
        if current and new_priority < current_priority:
            continue

        output[name] = {
            "link": link,
            "type": offer_type,
            "is_free": is_free,
            "monetization_type": monetization_type,
            "logo": provider.get("icon_url", ""),
            "available_from": offer.get("available_from"),
        }

    return output
