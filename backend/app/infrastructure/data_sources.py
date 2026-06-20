"""Typed POI and geocoding adapters used by the deterministic planner."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.domain.models import POI


class DataSource(Protocol):
    """A searchable source of normalized points of interest."""

    def search_by_category(
        self, city: str, district: str | None, category: str
    ) -> AsyncIterator[POI]: ...

    def search_by_keyword(
        self, city: str, district: str | None, keyword: str
    ) -> AsyncIterator[POI]: ...


@dataclass(frozen=True)
class _MockPoi:
    poi: POI
    district: str


def _normalized(value: str | None) -> str:
    return (value or "").strip().casefold()


def _normalized_city(value: str | None) -> str:
    aliases = {"shanghai": "上海", "beijing": "北京"}
    normalized = _normalized(value)
    return aliases.get(normalized, normalized)


class MockDataSource:
    """Small, deterministic fixture dataset for local development and tests."""

    def __init__(self, pois: Sequence[_MockPoi] | None = None) -> None:
        self._pois = tuple(pois or _default_pois())

    async def search_by_category(
        self, city: str, district: str | None, category: str
    ) -> AsyncIterator[POI]:
        for item in self._matching(city, district):
            if _normalized(item.poi.category) == _normalized(category):
                yield item.poi

    async def search_by_keyword(
        self, city: str, district: str | None, keyword: str
    ) -> AsyncIterator[POI]:
        needle = _normalized(keyword)
        for item in self._matching(city, district):
            searchable = " ".join((item.poi.name, item.poi.category, *item.poi.tags))
            if needle in _normalized(searchable):
                yield item.poi

    def _matching(self, city: str, district: str | None) -> Iterator[_MockPoi]:
        """Centralize normalized city and optional district matching."""
        return (
            item
            for item in self._pois
            if _normalized_city(item.poi.city) == _normalized_city(city)
            and (district is None or _normalized(item.district) == _normalized(district))
        )


class DianpingDataSource:
    """Minimal Dianping HTTP adapter; callers decide when external search is enabled."""

    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.AsyncClient | None = None,
        base_url: str = "https://api.dianping.com",
        timeout_seconds: float = 5.0,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout_seconds),
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def search_by_category(
        self, city: str, district: str | None, category: str
    ) -> AsyncIterator[POI]:
        async for poi in self._search(city, district, category=category):
            yield poi

    async def search_by_keyword(
        self, city: str, district: str | None, keyword: str
    ) -> AsyncIterator[POI]:
        async for poi in self._search(city, district, keyword=keyword):
            yield poi

    async def _search(
        self,
        city: str,
        district: str | None,
        *,
        category: str | None = None,
        keyword: str | None = None,
    ) -> AsyncIterator[POI]:
        params = {"city": city, "district": district, "category": category, "keyword": keyword}
        response = await self._client.get(
            "/v1/businesses/search", params={key: value for key, value in params.items() if value}
        )
        response.raise_for_status()
        payload: Mapping[str, Any] = response.json()
        records = payload.get("businesses", payload.get("data", []))
        if not isinstance(records, list):
            return
        for record in records:
            if isinstance(record, Mapping):
                yield _poi_from_record(record, city=city, category=category)


@dataclass(frozen=True)
class GeocodeResult:
    longitude: float
    latitude: float


class GaodeGeoService:
    """Typed AMap geocoding client with an explicit finite network timeout."""

    def __init__(
        self,
        api_key: str,
        *,
        client: httpx.AsyncClient | None = None,
        base_url: str = "https://restapi.amap.com",
        timeout_seconds: float = 5.0,
    ) -> None:
        self._api_key = api_key
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url, timeout=httpx.Timeout(timeout_seconds)
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def geocode(
        self, city: str, district: str | None, keyword: str
    ) -> GeocodeResult | None:
        address = " ".join(part for part in (city, district, keyword) if part)
        response = await self._client.get(
            "/v3/geocode/geo", params={"key": self._api_key, "address": address, "city": city}
        )
        response.raise_for_status()
        payload: Mapping[str, Any] = response.json()
        geocodes = payload.get("geocodes", [])
        if not isinstance(geocodes, list) or not geocodes:
            return None
        location = geocodes[0].get("location") if isinstance(geocodes[0], Mapping) else None
        if not isinstance(location, str):
            return None
        try:
            longitude, latitude = (float(part) for part in location.split(",", maxsplit=1))
        except ValueError:
            return None
        return GeocodeResult(longitude=longitude, latitude=latitude)


def _poi_from_record(
    record: Mapping[str, Any], *, city: str, category: str | None
) -> POI:
    return POI(
        id=str(record.get("id", record.get("business_id", ""))),
        name=str(record.get("name", "")),
        category=str(record.get("category", category or "OTHER")),
        city=str(record.get("city", city)),
        rating=float(record.get("rating", 0) or 0),
        avgCost=float(record.get("avg_cost", record.get("avgCost", 0)) or 0),
        tags=[str(tag) for tag in record.get("tags", []) if tag],
        queueTime=float(record.get("queue_time", record.get("queueTime", 0)) or 0),
    )


def _default_pois() -> list[_MockPoi]:
    return [
        _MockPoi(
            POI(id="sh-rest-1", name="黄浦本帮菜", category="RESTAURANT", city="上海", rating=4.7, avgCost=120, tags=["本帮菜", "晚餐"]),
            "黄浦",
        ),
        _MockPoi(
            POI(id="sh-rest-2", name="静安面馆", category="RESTAURANT", city="上海", rating=4.3, avgCost=45, tags=["面食", "快捷"]),
            "静安",
        ),
        _MockPoi(
            POI(id="sh-attr-1", name="外滩漫步", category="ATTRACTION", city="上海", rating=4.8, avgCost=0, tags=["江景", "夜景"]),
            "黄浦",
        ),
        _MockPoi(
            POI(id="bj-rest-1", name="北京烤鸭", category="RESTAURANT", city="北京", rating=4.6, avgCost=160, tags=["烤鸭"]),
            "东城",
        ),
        _MockPoi(
            POI(id="bj-attr-1", name="故宫博物院", category="ATTRACTION", city="北京", rating=4.9, avgCost=60, tags=["历史"]),
            "东城",
        ),
    ]
