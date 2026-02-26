# app/services/shipping_distance.py
import asyncio
import math
import os
from typing import Optional

import googlemaps
import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

GOOGLE_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
HAVERSINE_FACTOR = float(os.getenv("FRETE_HAVERSINE_FACTOR", "1.25"))

_gmaps_client: Optional[googlemaps.Client] = None
_http_timeout = httpx.Timeout(8.0, connect=5.0)


def _gmaps() -> googlemaps.Client:
    global _gmaps_client
    if _gmaps_client is None:
        if not GOOGLE_KEY:
            raise RuntimeError("Define GOOGLE_MAPS_API_KEY")
        _gmaps_client = googlemaps.Client(key=GOOGLE_KEY)
    return _gmaps_client


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


async def _geocode_with_nominatim(address: str) -> tuple[float, float] | None:
    query = (address or "").strip()
    if not query:
        return None
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": 1, "addressdetails": 0}
    headers = {
        # Required by Nominatim usage policy.
        "User-Agent": "roksell-backend/1.0 (shipping-distance-fallback)",
    }
    try:
        async with httpx.AsyncClient(timeout=_http_timeout, follow_redirects=True) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return None
    if not isinstance(payload, list) or not payload:
        return None
    item = payload[0]
    try:
        lat = float(item.get("lat"))
        lon = float(item.get("lon"))
    except (TypeError, ValueError):
        return None
    return lat, lon


GET_ACTIVE_STORE = text(
    """
SELECT lat, lon
FROM stores
WHERE is_active = TRUE AND tenant_id = :tenant_id
ORDER BY name ASC
LIMIT 1
"""
)

GET_STORE_BY_ID = text(
    """
SELECT lat, lon
FROM stores
WHERE is_active = TRUE AND tenant_id = :tenant_id AND id = :store_id
LIMIT 1
"""
)

GET_OVERRIDE = text(
    """
SELECT amount_cents
FROM shipping_overrides
WHERE tenant_id = :tenant_id AND postal_code = :postal
LIMIT 1
"""
)

GET_TIER = text(
    """
SELECT amount_cents
FROM shipping_distance_tiers
WHERE tenant_id = :tenant_id
  AND (:km BETWEEN km_min AND km_max)
  AND (store_id = :store_id OR store_id IS NULL)
ORDER BY CASE WHEN store_id = :store_id THEN 0 ELSE 1 END, km_min DESC
LIMIT 1
"""
)


async def distance_from_store(
    db: Session,
    tenant_id: str,
    store_id: str | None = None,
    dest_lat: float | None = None,
    dest_lon: float | None = None,
    dest_address: str | None = None,
) -> Optional[float]:
    params = {"tenant_id": tenant_id}
    if store_id:
        store = db.execute(GET_STORE_BY_ID, {"tenant_id": tenant_id, "store_id": store_id}).fetchone()
    else:
        store = db.execute(GET_ACTIVE_STORE, params).fetchone()
    if not store:
        return None
    store_lat, store_lon = store

    def _call_dm(origin: str, dest: str) -> Optional[float]:
        dm = _gmaps().distance_matrix(
            origins=[origin],
            destinations=[dest],
            mode="driving",
            units="metric",
            region="br",
        )
        element = dm["rows"][0]["elements"][0]
        if element.get("status") == "OK":
            return element["distance"]["value"] / 1000.0
        return None

    if dest_lat is not None and dest_lon is not None:
        try:
            km = await asyncio.to_thread(
                _call_dm,
                f"{store_lat},{store_lon}",
                f"{dest_lat},{dest_lon}",
            )
        except Exception:
            km = None
        if km is not None:
            return km
        return (
            _haversine(
                float(store_lat),
                float(store_lon),
                float(dest_lat),
                float(dest_lon),
            )
            * HAVERSINE_FACTOR
        )

    if dest_address:
        try:
            km = await asyncio.to_thread(
                _call_dm,
                f"{store_lat},{store_lon}",
                dest_address,
            )
            if km is not None:
                return km
        except Exception:
            pass

        fallback_geo = await _geocode_with_nominatim(dest_address)
        if fallback_geo is None:
            return None
        dest_lat_fallback, dest_lon_fallback = fallback_geo
        return (
            _haversine(
                float(store_lat),
                float(store_lon),
                float(dest_lat_fallback),
                float(dest_lon_fallback),
            )
            * HAVERSINE_FACTOR
        )

    return None


def tier_amount_for_km(db: Session, tenant_id: str, km: float, store_id: str | None = None) -> Optional[int]:
    row = db.execute(GET_TIER, {"tenant_id": tenant_id, "km": km, "store_id": store_id}).fetchone()
    return row[0] if row else None


def shipping_override_for_postal_code(db: Session, tenant_id: str, postal_code: str) -> Optional[int]:
    normalized = "".join(ch for ch in (postal_code or "") if ch.isdigit())[:8]
    row = db.execute(GET_OVERRIDE, {"tenant_id": tenant_id, "postal": normalized}).fetchone()
    return row[0] if row else None

