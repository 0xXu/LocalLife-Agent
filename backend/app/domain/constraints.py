"""Deterministic constraint construction, validation, and scoring."""

from __future__ import annotations

from datetime import time

from pydantic import BaseModel, Field

from .models import Constraint, Route, UserIntent


class ValidationResult(BaseModel):
    """Constraint violations split by enforcement level."""

    hard_violations: list[Constraint] = Field(default_factory=list)
    soft_violations: list[Constraint] = Field(default_factory=list)

    @property
    def has_hard_violations(self) -> bool:
        return bool(self.hard_violations)


def route_cost(route: Route) -> float:
    """Use an explicit route total, falling back to its POI costs for drafts."""

    return route.total_cost if route.total_cost > 0 else sum(
        segment.poi.avg_cost for segment in route.segments
    )


class ConstraintEngine:
    """Keeps route feasibility deterministic and independent of an LLM."""

    def build_constraints(self, intent: UserIntent) -> list[Constraint]:
        constraints: list[Constraint] = []
        if intent.start_time and intent.end_time:
            constraints.append(Constraint.time_window(intent.start_time, intent.end_time))
        constraints.extend(
            Constraint(id="category", value=category, weight=8, isHard=True)
            for category in intent.preferred_categories
        )
        if intent.budget > 0:
            constraints.append(Constraint.budget(intent.budget, weight=6))
        if intent.min_rating > 0:
            constraints.append(
                Constraint(id="min_rating", value=intent.min_rating, weight=5)
            )
        if intent.max_queue_minutes > 0:
            constraints.append(
                Constraint(id="max_queue", value=intent.max_queue_minutes, weight=4)
            )
        return constraints

    def validate(self, route: Route, constraints: list[Constraint]) -> ValidationResult:
        hard_violations: list[Constraint] = []
        soft_violations: list[Constraint] = []
        for constraint in constraints:
            if self._satisfies(route, constraint):
                continue
            (hard_violations if constraint.is_hard else soft_violations).append(constraint)
        return ValidationResult(
            hard_violations=hard_violations, soft_violations=soft_violations
        )

    def score_route(self, route: Route, constraints: list[Constraint]) -> float:
        soft_constraints = [constraint for constraint in constraints if not constraint.is_hard]
        if not soft_constraints:
            return 100.0
        total_weight = sum(constraint.weight for constraint in soft_constraints)
        weighted_score = sum(
            constraint.weight * self._soft_score(route, constraint)
            for constraint in soft_constraints
        )
        return max(0.0, min(100.0, 100.0 * weighted_score / total_weight))

    def relax_constraints(
        self, constraints: list[Constraint], preserve_budget: bool = False
    ) -> list[list[Constraint]]:
        """Return ordered alternatives, removing lower-priority soft constraints first."""

        levels = [list(constraints)]
        current = list(constraints)
        removable = sorted(
            (constraint for constraint in constraints if not constraint.is_hard and constraint.id != "budget"),
            key=lambda constraint: (constraint.weight, constraint.id),
        )
        for constraint in removable:
            current = [item for item in current if item != constraint]
            levels.append(list(current))
        if not preserve_budget and any(
            constraint.id == "budget" and not constraint.is_hard for constraint in current
        ):
            levels.append([constraint for constraint in current if constraint.id != "budget"])
        return levels

    def _satisfies(self, route: Route, constraint: Constraint) -> bool:
        if constraint.id == "time_window":
            return self._is_within_time_window(route, str(constraint.value))
        if constraint.id == "category":
            return any(segment.poi.category == str(constraint.value) for segment in route.segments)
        if constraint.id == "budget":
            return route_cost(route) <= float(constraint.value)
        if constraint.id == "min_rating":
            return self._average_rating(route) >= float(constraint.value)
        if constraint.id == "max_queue":
            return all(
                segment.poi.queue_time <= float(constraint.value)
                for segment in route.segments
            )
        return True

    def _soft_score(self, route: Route, constraint: Constraint) -> float:
        if constraint.id == "budget":
            budget = max(float(constraint.value), 1.0)
            return max(0.0, 1.0 - route_cost(route) / budget)
        if constraint.id == "min_rating":
            minimum = max(float(constraint.value), 0.01)
            return min(1.0, self._average_rating(route) / minimum)
        if constraint.id == "max_queue":
            maximum = max(float(constraint.value), 0.01)
            average_queue = sum(segment.poi.queue_time for segment in route.segments) / max(
                len(route.segments), 1
            )
            return max(0.0, 1.0 - average_queue / maximum)
        return 1.0

    @staticmethod
    def _average_rating(route: Route) -> float:
        return sum(segment.poi.rating for segment in route.segments) / max(
            len(route.segments), 1
        )

    @staticmethod
    def _is_within_time_window(route: Route, value: str) -> bool:
        try:
            start_text, end_text = value.split("-", maxsplit=1)
            window_start = time.fromisoformat(start_text)
            window_end = time.fromisoformat(end_text)
        except ValueError:
            return False
        return all(
            segment.arrival_time is not None
            and segment.departure_time is not None
            and window_start <= time.fromisoformat(segment.arrival_time) <= window_end
            and window_start <= time.fromisoformat(segment.departure_time) <= window_end
            for segment in route.segments
        )


def score_route(route: Route, constraints: list[Constraint]) -> float:
    """Convenience function for callers that do not need an engine instance."""

    return ConstraintEngine().score_route(route, constraints)
