"""Preference-aware, deterministic ranking for candidate routes."""

from __future__ import annotations

from .models import POI, Route, UserPreference


class PreferenceScorer:
    """Scores optional POI tags without making tags a required data field."""

    def score_poi(self, poi: POI, preference: UserPreference | None) -> float:
        if preference is None or not preference.tags:
            return 0.0
        tags = getattr(poi, "tags", None) or []
        return sum(preference.tags.get(tag, 0.0) for tag in tags)

    def score_route(self, route: Route, preference: UserPreference | None) -> float:
        if not route.segments:
            return 0.0
        return sum(
            self.score_poi(segment.poi, preference) for segment in route.segments
        ) / len(route.segments)
