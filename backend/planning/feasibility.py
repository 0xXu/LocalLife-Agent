from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ortools.sat.python import cp_model

from backend.domain.models import (
    Availability,
    FeasiblePlanCandidate,
    FeasiblePlanSet,
    FeasibleSelection,
    GoalContract,
    GroundedCandidateSet,
    InfeasibleReason,
    PlanObjectiveVector,
    PolicyTriggerKind,
    SupplyOption,
    TemporalConstraint,
)


def _minutes(value: str) -> int:
    parsed = datetime.strptime(value, "%H:%M")
    return parsed.hour * 60 + parsed.minute


def _clock(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


@dataclass(frozen=True)
class _Variant:
    capability_id: str
    option: SupplyOption
    starts_at: int
    ends_at: int
    consumes_user_time: bool
    trigger_kind: PolicyTriggerKind


class _SolutionCollector(cp_model.CpSolverSolutionCallback):
    def __init__(
        self,
        variables: list[cp_model.IntVar],
        variants: list[_Variant],
        limit: int,
    ) -> None:
        super().__init__()
        self.variables = variables
        self.variants = variants
        self.limit = limit
        self.solutions: list[tuple[int, ...]] = []

    def on_solution_callback(self) -> None:
        selected = tuple(
            index for index, variable in enumerate(self.variables) if self.value(variable)
        )
        self.solutions.append(selected)
        if len(self.solutions) >= self.limit:
            self.stop_search()


def _dominates(left: FeasiblePlanCandidate, right: FeasiblePlanCandidate) -> bool:
    left_vector = left.objectives
    right_vector = right.objectives
    no_worse = (
        left_vector.total_yuan <= right_vector.total_yuan
        and left_vector.completion_minute <= right_vector.completion_minute
        and left_vector.elapsed_minutes <= right_vector.elapsed_minutes
        and left_vector.movement_minutes <= right_vector.movement_minutes
        and left_vector.experience_milli >= right_vector.experience_milli
    )
    strictly_better = (
        left_vector.total_yuan < right_vector.total_yuan
        or left_vector.completion_minute < right_vector.completion_minute
        or left_vector.elapsed_minutes < right_vector.elapsed_minutes
        or left_vector.movement_minutes < right_vector.movement_minutes
        or left_vector.experience_milli > right_vector.experience_milli
    )
    return no_worse and strictly_better


class FeasibilitySolver:
    """Turns grounded supply into a Pareto plan space through one solve interface."""

    def solve(
        self,
        goal: GoalContract,
        candidate_sets: list[GroundedCandidateSet],
        temporal_constraints: list[TemporalConstraint],
        *,
        solution_limit: int = 200,
    ) -> FeasiblePlanSet:
        deadline = _minutes(goal.deadline)
        variants: list[_Variant] = []
        missing: list[str] = []
        capacity_conflicts: list[str] = []
        timing_conflicts: list[str] = []
        for candidate_set in candidate_sets:
            before = len(variants)
            has_available_supply = False
            has_capacity_supply = False
            for option in candidate_set.candidates:
                if option.availability == Availability.UNAVAILABLE:
                    continue
                has_available_supply = True
                party_capacity = option.metadata.get(
                    "party_capacity",
                    option.metadata.get("remaining"),
                )
                if isinstance(party_capacity, int) and party_capacity < goal.party_size:
                    continue
                has_capacity_supply = True
                time_slots = option.time_slots
                window_start = option.metadata.get("scheduling_window_start")
                window_end = option.metadata.get("scheduling_window_end")
                interval = option.metadata.get("scheduling_interval_minutes")
                if (
                    isinstance(window_start, str)
                    and isinstance(window_end, str)
                    and isinstance(interval, int)
                    and interval > 0
                ):
                    first = _minutes(window_start)
                    last = _minutes(window_end)
                    time_slots = [
                        _clock(value)
                        for value in range(first, last + 1, interval)
                    ]
                for starts_at in time_slots:
                    start = _minutes(starts_at)
                    variants.append(_Variant(
                        capability_id=candidate_set.capability_id,
                        option=option,
                        starts_at=start,
                        ends_at=start + option.duration_minutes,
                        consumes_user_time=candidate_set.consumes_user_time,
                        trigger_kind=candidate_set.trigger_kind,
                    ))
            if len(variants) == before and candidate_set.minimum_commitments > 0:
                if not has_available_supply:
                    missing.append(candidate_set.capability_id)
                elif not has_capacity_supply:
                    capacity_conflicts.append(candidate_set.capability_id)
                else:
                    timing_conflicts.append(candidate_set.capability_id)
        grounding_reasons: list[InfeasibleReason] = []
        if capacity_conflicts:
            grounding_reasons.append(InfeasibleReason(
                code="capacity_conflict",
                message=f"现有供给无法容纳 {goal.party_size} 人",
                capability_ids=capacity_conflicts,
            ))
        if timing_conflicts:
            grounding_reasons.append(InfeasibleReason(
                code="time_window_conflict",
                message="现有供给在要求的履约时间窗内没有可用时刻",
                capability_ids=timing_conflicts,
            ))
        if missing:
            grounding_reasons.append(InfeasibleReason(
                code="missing_supply",
                message="没有可履约的供给",
                capability_ids=missing,
            ))
        if grounding_reasons:
            return FeasiblePlanSet(
                status="infeasible",
                infeasible_reasons=grounding_reasons,
            )

        model = cp_model.CpModel()
        variables = [
            model.new_bool_var(f"choose_{index}_{variant.option.id}_{variant.starts_at}")
            for index, variant in enumerate(variants)
        ]
        by_capability: dict[str, list[int]] = {}
        by_option: dict[str, list[int]] = {}
        for index, variant in enumerate(variants):
            by_capability.setdefault(variant.capability_id, []).append(index)
            by_option.setdefault(variant.option.id, []).append(index)

        for candidate_set in candidate_sets:
            indices = by_capability.get(candidate_set.capability_id, [])
            expression = sum(variables[index] for index in indices)
            model.add(expression >= candidate_set.minimum_commitments)
            model.add(expression <= candidate_set.maximum_commitments)
        for indices in by_option.values():
            model.add(sum(variables[index] for index in indices) <= 1)

        candidate_semantics = {
            candidate_set.capability_id: candidate_set
            for candidate_set in candidate_sets
        }
        exact_times = {
            constraint.capability_id: _minutes(constraint.time)
            for constraint in temporal_constraints
            if constraint.relation == "exact_start"
            and constraint.time is not None
            and candidate_semantics.get(constraint.capability_id)
            and candidate_semantics[constraint.capability_id].location_bound
        }
        ordered_locations = sorted(exact_times, key=exact_times.get)
        transition_indices = [
            index
            for index, variant in enumerate(variants)
            if candidate_semantics[variant.capability_id].provides_transition_evidence
        ]
        for candidate_set in candidate_sets:
            if not candidate_set.provides_transition_evidence:
                continue
            required = min(
                candidate_set.maximum_commitments,
                max(candidate_set.minimum_commitments, len(ordered_locations) - 1),
            )
            model.add(
                sum(
                    variables[index]
                    for index in by_capability.get(candidate_set.capability_id, [])
                )
                == required
            )
        for left_capability, right_capability in zip(
            ordered_locations,
            ordered_locations[1:],
        ):
            for left_index in by_capability.get(left_capability, []):
                left = variants[left_index]
                for right_index in by_capability.get(right_capability, []):
                    right = variants[right_index]
                    fitting_transitions = [
                        index
                        for index in transition_indices
                        if variants[index].starts_at >= left.ends_at
                        and variants[index].ends_at <= right.starts_at
                    ]
                    model.add(
                        sum(variables[index] for index in fitting_transitions)
                        >= variables[left_index] + variables[right_index] - 1
                    )

        for left_index, left in enumerate(variants):
            if not left.consumes_user_time:
                continue
            for right_index in range(left_index + 1, len(variants)):
                right = variants[right_index]
                if not right.consumes_user_time:
                    continue
                overlaps = left.starts_at < right.ends_at and right.starts_at < left.ends_at
                if overlaps:
                    model.add(variables[left_index] + variables[right_index] <= 1)

        assumption_reasons: dict[int, InfeasibleReason] = {}
        assumption_variables: dict[int, cp_model.IntVar] = {}
        budget_assumption = model.new_bool_var("assume_budget")
        model.add(
            sum(
                variables[index] * variant.option.price_yuan
                for index, variant in enumerate(variants)
            )
            <= goal.budget_yuan
        ).only_enforce_if(budget_assumption)
        model.add_assumption(budget_assumption)
        assumption_variables[budget_assumption.index] = budget_assumption
        assumption_reasons[budget_assumption.index] = InfeasibleReason(
            code="budget_conflict",
            message=f"已核验供给无法同时满足 ¥{goal.budget_yuan} 的总预算",
            constraint_ids=[
                item.id for item in goal.constraints if item.kind.value == "budget" and item.hard
            ],
            capability_ids=[item.capability_id for item in candidate_sets],
        )

        deadline_assumption = model.new_bool_var("assume_deadline")
        for index, variant in enumerate(variants):
            if variant.ends_at > deadline:
                model.add(variables[index] == 0).only_enforce_if(deadline_assumption)
        model.add_assumption(deadline_assumption)
        assumption_variables[deadline_assumption.index] = deadline_assumption
        assumption_reasons[deadline_assumption.index] = InfeasibleReason(
            code="deadline_conflict",
            message=f"已核验供给无法在 {goal.deadline} 前完成",
            constraint_ids=[
                item.id for item in goal.constraints if item.kind.value == "deadline" and item.hard
            ],
            capability_ids=[item.capability_id for item in candidate_sets],
        )

        for constraint_index, constraint in enumerate(temporal_constraints):
            assumption = model.new_bool_var(f"assume_time_{constraint_index}")
            if constraint.relation == "starts_after":
                assert constraint.reference_capability_id is not None
                for subject_index in by_capability.get(constraint.capability_id, []):
                    subject = variants[subject_index]
                    for reference_index in by_capability.get(
                        constraint.reference_capability_id,
                        [],
                    ):
                        reference = variants[reference_index]
                        if subject.starts_at < (
                            reference.ends_at + constraint.minimum_gap_minutes
                        ):
                            model.add(
                                variables[subject_index] + variables[reference_index] <= 1
                            ).only_enforce_if(assumption)
                reason_message = "后续行程无法衔接前一项安排的结束时间"
                reason_capabilities = [
                    constraint.reference_capability_id,
                    constraint.capability_id,
                ]
            else:
                assert constraint.time is not None
                boundary = _minutes(constraint.time)
                for index in by_capability.get(constraint.capability_id, []):
                    variant = variants[index]
                    violates = (
                        constraint.relation == "exact_start" and variant.starts_at != boundary
                        or constraint.relation == "earliest_start" and variant.starts_at < boundary
                        or constraint.relation == "latest_end" and variant.ends_at > boundary
                    )
                    if violates:
                        model.add(variables[index] == 0).only_enforce_if(assumption)
                reason_message = f"对应供给无法满足 {constraint.time} 的指定时间要求"
                reason_capabilities = [constraint.capability_id]
            model.add_assumption(assumption)
            assumption_variables[assumption.index] = assumption
            assumption_reasons[assumption.index] = InfeasibleReason(
                code="time_window_conflict",
                message=reason_message,
                constraint_ids=(
                    [constraint.source_constraint_id]
                    if constraint.source_constraint_id
                    else []
                ),
                capability_ids=reason_capabilities,
            )

        solver = cp_model.CpSolver()
        solver.parameters.enumerate_all_solutions = True
        solver.parameters.max_time_in_seconds = 2.0
        solver.parameters.num_search_workers = 1
        collector = _SolutionCollector(variables, variants, solution_limit)
        status = solver.solve(model, collector)
        if status == cp_model.INFEASIBLE:
            core = list(solver.sufficient_assumptions_for_infeasibility())
            for literal in list(core):
                trial = [item for item in core if item != literal]
                model.clear_assumptions()
                model.add_assumptions([
                    assumption_variables[item]
                    for item in trial
                    if item in assumption_variables
                ])
                core_solver = cp_model.CpSolver()
                core_solver.parameters.max_time_in_seconds = 0.5
                if core_solver.solve(model) == cp_model.INFEASIBLE:
                    core = trial
            reasons = [
                assumption_reasons[index]
                for index in core
                if index in assumption_reasons
            ]
            return FeasiblePlanSet(
                status="infeasible",
                infeasible_reasons=reasons or [InfeasibleReason(
                    code="no_combination",
                    message="供给之间没有满足全部硬约束的组合",
                    capability_ids=[item.capability_id for item in candidate_sets],
                )],
            )
        if not collector.solutions:
            return FeasiblePlanSet(
                status="unknown",
                infeasible_reasons=[],
            )

        candidates: list[FeasiblePlanCandidate] = []
        seen: set[tuple[tuple[str, int], ...]] = set()
        for selected_indices in collector.solutions:
            selected = [variants[index] for index in selected_indices]
            signature = tuple(sorted((item.option.id, item.starts_at) for item in selected))
            if signature in seen:
                continue
            seen.add(signature)
            selected.sort(key=lambda item: (item.starts_at, item.capability_id, item.option.id))
            completion = max(item.ends_at for item in selected)
            first_start = min(item.starts_at for item in selected)
            total_yuan = sum(item.option.price_yuan for item in selected)
            movement = sum(
                value
                for item in selected
                for value in [
                    item.option.metadata.get("walk_minutes"),
                    item.option.metadata.get("eta_minutes"),
                ]
                if isinstance(value, int)
            )
            candidates.append(FeasiblePlanCandidate(
                id="pending",
                selections=[FeasibleSelection(
                    capability_id=item.capability_id,
                    option_id=item.option.id,
                    consumes_user_time=item.consumes_user_time,
                    trigger_kind=item.trigger_kind,
                    starts_at=_clock(item.starts_at),
                    ends_at=_clock(item.ends_at),
                    price_yuan=item.option.price_yuan,
                ) for item in selected],
                objectives=PlanObjectiveVector(
                    total_yuan=total_yuan,
                    completion_minute=completion,
                    elapsed_minutes=completion - first_start,
                    movement_minutes=movement,
                    experience_milli=sum(round(item.option.rating * 1000) for item in selected),
                ),
                slack_minutes=max(0, deadline - completion),
            ))

        candidates.sort(key=lambda item: (
            item.objectives.total_yuan,
            item.objectives.completion_minute,
            item.objectives.movement_minutes,
            -item.objectives.experience_milli,
            tuple(selection.option_id for selection in item.selections),
        ))
        candidates = [
            item.model_copy(update={"id": f"candidate_{index + 1}"}, deep=True)
            for index, item in enumerate(candidates)
        ]
        pareto_ids = [
            candidate.id
            for candidate in candidates
            if not any(
                other.id != candidate.id and _dominates(other, candidate)
                for other in candidates
            )
        ]
        return FeasiblePlanSet(
            status="feasible",
            candidates=candidates,
            pareto_candidate_ids=pareto_ids,
        )
