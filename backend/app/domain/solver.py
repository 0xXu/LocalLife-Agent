"""Small deterministic graph-style route generator."""

from __future__ import annotations

from datetime import datetime, timedelta
from itertools import permutations

from .constraints import ConstraintEngine, route_cost
from .models import Constraint, POI, Route, RouteSegment, UserIntent, UserPreference
from .scoring import PreferenceScorer


class GraphSearchSolver:
    """Enumerates short candidate paths and only returns hard-feasible routes."""

    def __init__(
        self,
        constraint_engine: ConstraintEngine | None = None,
        preference_scorer: PreferenceScorer | None = None,
    ) -> None:
        self.constraint_engine = constraint_engine or ConstraintEngine()
        self.preference_scorer = preference_scorer or PreferenceScorer()

    def generate_plans(
        self,
        candidates: list[POI],
        constraints: list[Constraint],
        intent: UserIntent,
        limit: int = 3,
        preference: UserPreference | None = None,
    ) -> list[Route]:
        if limit <= 0:
            return []
        ordered = sorted(
            (poi for poi in candidates if poi.city == intent.city),
            key=lambda poi: (
                -self.preference_scorer.score_poi(poi, preference),
                -poi.rating,
                poi.avg_cost,
                poi.id,
            ),
        )
        feasible: list[Route] = []
        seen_sequences: set[tuple[str, ...]] = set()
        for length in range(1, min(3, len(ordered)) + 1):
            for sequence in permutations(ordered, length):
                sequence_ids = tuple(poi.id for poi in sequence)
                if sequence_ids in seen_sequences:
                    continue
                route = self._build_route(sequence, intent)
                validation = self.constraint_engine.validate(route, constraints)
                if validation.has_hard_violations:
                    continue
                route = route.model_copy(
                    update={
                        "violated_soft_constraints": validation.soft_violations,
                        "score": self.constraint_engine.score_route(route, constraints),
                    }
                )
                feasible.append(route)
                seen_sequences.add(sequence_ids)
        feasible.sort(
            key=lambda route: (
                -route.score,
                -self.preference_scorer.score_route(route, preference),
                -sum(segment.poi.rating for segment in route.segments),
                route.total_cost,
                tuple(segment.poi.id for segment in route.segments),
            )
        )
        return feasible[:limit]

    @staticmethod
    def _build_route(sequence: tuple[POI, ...], intent: UserIntent) -> Route:
        start = datetime.strptime(intent.start_time or "10:00", "%H:%M")
        segments: list[RouteSegment] = []
        for index, poi in enumerate(sequence):
            arrival = start + timedelta(hours=index)
            departure = arrival + timedelta(hours=1)
            segments.append(
                RouteSegment(
                    poi=poi,
                    arrivalTime=arrival.strftime("%H:%M"),
                    departureTime=departure.strftime("%H:%M"),
                    travelTimeFromPrevious=0 if index == 0 else 15,
                )
            )
        draft = Route(
            id="route-" + "-".join(poi.id for poi in sequence),
            name=" → ".join(poi.name for poi in sequence),
            segments=segments,
            totalCost=sum(poi.avg_cost for poi in sequence),
        )
        return draft.model_copy(update={"total_cost": route_cost(draft)})
