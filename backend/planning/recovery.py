from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.domain.models import (
    ConstraintKind,
    FeasiblePlanSet,
    GoalContract,
    GroundedCandidateSet,
    TemporalConstraint,
)
from backend.planning.feasibility import FeasibilitySolver


def _minutes(value: str) -> int:
    parsed = datetime.strptime(value, "%H:%M")
    return parsed.hour * 60 + parsed.minute


def _clock(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


class RecoveryCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    impact: str
    goal: GoalContract
    temporal_constraints: list[TemporalConstraint]
    feasible_set: FeasiblePlanSet


class RecoveryEnumerator:
    """Derive minimal, solver-proved user boundary changes from an infeasible core."""

    def __init__(self, solver: FeasibilitySolver) -> None:
        self.solver = solver

    @staticmethod
    def _update_goal_constraint(
        goal: GoalContract,
        kind: ConstraintKind,
        value: str,
    ) -> GoalContract:
        updated = goal.model_copy(deep=True)
        for constraint in updated.constraints:
            if constraint.kind == kind:
                constraint.value = value
        return updated

    def enumerate(
        self,
        goal: GoalContract,
        candidate_sets: list[GroundedCandidateSet],
        temporal_constraints: list[TemporalConstraint],
        infeasible: FeasiblePlanSet,
        *,
        limit: int = 3,
    ) -> list[RecoveryCandidate]:
        codes = {reason.code for reason in infeasible.infeasible_reasons}
        candidates: list[RecoveryCandidate] = []

        if "budget_conflict" in codes:
            high_budget = sum(
                max((option.price_yuan for option in candidate_set.candidates), default=0)
                * max(1, candidate_set.maximum_commitments)
                for candidate_set in candidate_sets
            )
            if high_budget > goal.budget_yuan:
                relaxed = goal.model_copy(update={"budget_yuan": high_budget}, deep=True)
                result = self.solver.solve(relaxed, candidate_sets, temporal_constraints)
                if result.status == "feasible":
                    minimum = min(
                        item.objectives.total_yuan for item in result.candidates
                    )
                    minimal = self._update_goal_constraint(
                        goal.model_copy(update={"budget_yuan": minimum}, deep=True),
                        ConstraintKind.BUDGET,
                        f"{minimum} 元以内",
                    )
                    proved = self.solver.solve(
                        minimal,
                        candidate_sets,
                        temporal_constraints,
                    )
                    if proved.status == "feasible":
                        candidates.append(RecoveryCandidate(
                            label=f"总预算提高到 ¥{minimum}",
                            impact="这是当前已核验供给能够组合成功的最低总预算。",
                            goal=minimal,
                            temporal_constraints=temporal_constraints,
                            feasible_set=proved,
                        ))

        if "deadline_conflict" in codes:
            relaxed = goal.model_copy(update={"deadline": "23:59"}, deep=True)
            result = self.solver.solve(relaxed, candidate_sets, temporal_constraints)
            if result.status == "feasible":
                minute = min(
                    item.objectives.completion_minute for item in result.candidates
                )
                deadline = _clock(minute)
                minimal = self._update_goal_constraint(
                    goal.model_copy(update={"deadline": deadline}, deep=True),
                    ConstraintKind.DEADLINE,
                    deadline,
                )
                proved = self.solver.solve(
                    minimal,
                    candidate_sets,
                    temporal_constraints,
                )
                if proved.status == "feasible":
                    candidates.append(RecoveryCandidate(
                        label=f"最晚完成改到 {deadline}",
                        impact="这是保留当前供给组合所需的最早完成边界。",
                        goal=minimal,
                        temporal_constraints=temporal_constraints,
                        feasible_set=proved,
                    ))

        if "capacity_conflict" in codes:
            capacities = [
                value
                for candidate_set in candidate_sets
                for option in candidate_set.candidates
                for value in [option.metadata.get(
                    "party_capacity",
                    option.metadata.get("remaining"),
                )]
                if isinstance(value, int)
            ]
            supported = max(capacities, default=0)
            if 0 < supported < goal.party_size:
                minimal = self._update_goal_constraint(
                    goal.model_copy(update={"party_size": supported}, deep=True),
                    ConstraintKind.PARTY_SIZE,
                    f"{supported} 人",
                )
                proved = self.solver.solve(
                    minimal,
                    candidate_sets,
                    temporal_constraints,
                )
                if proved.status == "feasible":
                    candidates.append(RecoveryCandidate(
                        label=f"改为 {supported} 人参与",
                        impact="这是当前供给能够同时容纳的最多人数。",
                        goal=minimal,
                        temporal_constraints=temporal_constraints,
                        feasible_set=proved,
                    ))

        if "time_window_conflict" in codes:
            candidates.extend(self._time_recoveries(
                goal,
                candidate_sets,
                temporal_constraints,
                limit=max(1, limit - len(candidates)),
            ))

        unique: dict[tuple[str, tuple[tuple[str, str, str | None], ...]], RecoveryCandidate] = {}
        for candidate in candidates:
            key = (
                candidate.label,
                tuple(
                    (item.capability_id, item.relation, item.time)
                    for item in candidate.temporal_constraints
                ),
            )
            unique.setdefault(key, candidate)
        return list(unique.values())[:limit]

    def _time_recoveries(
        self,
        goal: GoalContract,
        candidate_sets: list[GroundedCandidateSet],
        temporal_constraints: list[TemporalConstraint],
        *,
        limit: int,
    ) -> list[RecoveryCandidate]:
        by_capability = {
            candidate_set.capability_id: candidate_set
            for candidate_set in candidate_sets
        }
        recoveries: list[RecoveryCandidate] = []
        for index, constraint in enumerate(temporal_constraints):
            if constraint.relation == "starts_after" or constraint.time is None:
                continue
            candidate_set = by_capability.get(constraint.capability_id)
            if candidate_set is None:
                continue
            original = _minutes(constraint.time)
            boundaries: set[int] = set()
            for option in candidate_set.candidates:
                for slot in option.time_slots:
                    start = _minutes(slot)
                    if constraint.relation == "latest_end":
                        boundaries.add(start + option.duration_minutes)
                    else:
                        boundaries.add(start)
            if constraint.relation == "earliest_start":
                ordered = sorted(
                    (value for value in boundaries if value < original),
                    reverse=True,
                )
            elif constraint.relation == "latest_end":
                ordered = sorted(value for value in boundaries if value > original)
            else:
                ordered = sorted(boundaries, key=lambda value: (abs(value - original), value))
            for boundary in ordered[:8]:
                changed = [item.model_copy(deep=True) for item in temporal_constraints]
                changed[index] = constraint.model_copy(update={"time": _clock(boundary)})
                proved = self.solver.solve(goal, candidate_sets, changed)
                if proved.status != "feasible":
                    continue
                clock = _clock(boundary)
                label_prefix = {
                    "exact_start": "指定时间改到",
                    "earliest_start": "最早开始改到",
                    "latest_end": "最晚结束改到",
                }[constraint.relation]
                recoveries.append(RecoveryCandidate(
                    label=f"{label_prefix} {clock}",
                    impact="这个时间来自当前已核验的可用时段。",
                    goal=goal.model_copy(deep=True),
                    temporal_constraints=changed,
                    feasible_set=proved,
                ))
                if len(recoveries) >= limit:
                    return recoveries
        return recoveries
