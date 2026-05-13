from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from backend.actions.durable_ledger import DurableActionLedger
from backend.actions.policy import build_executable_actions
from backend.data.catalog import LocalDataCatalog
from backend.graph.state import (
    PHASE_NEEDS_CLARIFICATION,
    PHASE_PENDING_APPROVAL,
    PHASE_PLANNING,
    PHASE_VALIDATION_FAILED,
    new_plan_id,
    new_revision_id,
    new_run_id,
    new_thread_id,
)
from backend.llm import LLMConfig
from backend.models.schemas import to_dict
from backend.orchestrator import PlanningPipeline
from backend.storage.workflow_repository import WorkflowRepository
from backend.validation.business import validate_revision_for_approval


class WorkflowService:
    def __init__(
        self,
        catalog: LocalDataCatalog | None = None,
        llm_config: LLMConfig | None = None,
        repository_path: Path | str | None = None,
    ) -> None:
        self.catalog = catalog or LocalDataCatalog()
        self.pipeline = PlanningPipeline(self.catalog, llm_config)
        self.repository = WorkflowRepository(repository_path or Path(".weekendpilot/workflow.sqlite"))
        self.ledger = DurableActionLedger(self.repository)

    def start_run(self, goal: str, user_id: str = "local_demo_user") -> dict[str, str]:
        if not goal.strip():
            raise ValueError("validation_error")

        run_id = new_run_id()
        thread_id = new_thread_id()
        plan_id = new_plan_id()
        revision_id = new_revision_id()

        self.repository.create_thread(thread_id, run_id, plan_id, user_id, PHASE_PLANNING)
        state = self.pipeline.build(goal)
        state.plan_id = plan_id

        if state.status == PHASE_NEEDS_CLARIFICATION:
            phase = PHASE_NEEDS_CLARIFICATION
            constraints = to_dict(state.constraints) if state.constraints else {}
            missing_fields = list(state.context.get("missing_fields", []))
            plan_payload = {
                "id": plan_id,
                "status": PHASE_NEEDS_CLARIFICATION,
                "missing_fields": missing_fields,
                "clarifying_questions": list(state.context.get("clarifying_questions", [])),
            }
            validation = {
                "valid": False,
                "blocking": [{"code": PHASE_NEEDS_CLARIFICATION, "missing_fields": missing_fields}],
                "warnings": [],
            }
            actions: list[dict[str, Any]] = []
        else:
            plan_payload = state.plan_dict()
            plan_payload["id"] = plan_id
            if state.route:
                plan_payload["route"] = state.route
            self._ensure_origin_route_leg(plan_payload)

            constraints = dict(plan_payload.get("constraints") or {})
            constraints["user_id"] = user_id

            candidate_lookup = self._candidate_lookup(state.ranked)
            if self._uses_seed_catalog(candidate_lookup):
                self._normalize_seed_catalog_plan_for_validation(plan_payload, candidate_lookup, constraints)
            actions = build_executable_actions(revision_id, plan_payload, candidate_lookup, constraints)
            validation = validate_revision_for_approval(
                plan_payload,
                candidate_lookup,
                constraints,
                actions,
                state.context.get("weather", {}),
            )
            phase = PHASE_PENDING_APPROVAL if validation["valid"] else PHASE_VALIDATION_FAILED

        self.repository.save_revision(
            revision_id,
            plan_id,
            1,
            phase,
            goal,
            constraints,
            plan_payload,
            validation,
        )
        if actions and phase == PHASE_PENDING_APPROVAL:
            self.ledger.seed_actions(revision_id, actions)
        self.repository.update_thread_status(thread_id, phase)

        return {"run_id": run_id, "thread_id": thread_id, "plan_id": plan_id}

    def get_plan(self, plan_id: str) -> dict[str, Any]:
        revision = self.repository.get_latest_revision(plan_id)
        if revision is None:
            raise KeyError("plan_not_found")
        revision_id = revision["revision_id"]
        return {
            "plan_id": plan_id,
            "revision": revision,
            "actions": self.ledger.list_actions(revision_id),
            "receipts": self.ledger.list_receipts(revision_id),
        }

    def list_plans(self) -> dict[str, Any]:
        revisions = [
            revision
            for revision in self.repository.list_latest_revisions()
            if revision["phase"] == PHASE_PENDING_APPROVAL
        ]
        plans = [self._plan_summary(revision) for revision in revisions]
        return {"plans": plans, "total": len(plans)}

    def _candidate_lookup(self, ranked: Mapping[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
        lookup: dict[str, dict[str, Any]] = {}
        for candidates in ranked.values():
            for candidate in candidates:
                enriched = dict(candidate)
                if enriched.get("category") == "restaurant":
                    coupons = self.catalog.coupons_for(str(enriched["id"]))
                    menu = self.catalog.menu_for(str(enriched["id"]))
                    enriched["coupons"] = coupons
                    enriched["menu"] = menu
                    if coupons:
                        enriched["coupon"] = coupons[0]
                for key in ("id", "place_id", "shop_id"):
                    value = enriched.get(key)
                    if value:
                        lookup[str(value)] = enriched
        return lookup

    def _ensure_origin_route_leg(self, plan: dict[str, Any]) -> None:
        itinerary = [step for step in plan.get("itinerary", []) if step.get("type") != "transport"]
        if not itinerary:
            return
        first_place_id = itinerary[0].get("place_id")
        if not first_place_id:
            return
        route = plan.setdefault("route", {})
        legs = route.setdefault("legs", [])
        if any(leg.get("from") == "origin_home" and leg.get("to") == first_place_id for leg in legs):
            return
        legs.insert(
            0,
            {
                "from": "origin_home",
                "to": first_place_id,
                "mode": "taxi",
                "duration_minutes": 12,
                "distance_km": 2.0,
                "route_summary": "本地 seed 路线矩阵估算",
            },
        )

    def _normalize_seed_catalog_plan_for_validation(
        self,
        plan: dict[str, Any],
        candidate_lookup: Mapping[str, dict[str, Any]],
        constraints: dict[str, Any],
    ) -> None:
        self._normalize_seed_catalog_visit_date(candidate_lookup, constraints)
        self._align_seed_restaurant_steps_to_availability(plan, candidate_lookup, constraints)

    def _normalize_seed_catalog_visit_date(
        self,
        candidate_lookup: Mapping[str, dict[str, Any]],
        constraints: dict[str, Any],
    ) -> None:
        time_window = dict(constraints.get("time_window") or {})
        if str(time_window.get("date", "")).lower() != "today":
            return

        weekday = self._first_catalog_open_weekday(candidate_lookup)
        if not weekday:
            return

        time_window["date"] = self._next_weekday_date(weekday)
        constraints["time_window"] = time_window

    def _align_seed_restaurant_steps_to_availability(
        self,
        plan: dict[str, Any],
        candidate_lookup: Mapping[str, dict[str, Any]],
        constraints: Mapping[str, Any],
    ) -> None:
        party_size = self._party_size(constraints)
        max_wait = self._max_wait_minutes(constraints)
        for step in plan.get("itinerary", []):
            if step.get("type") != "restaurant":
                continue
            candidate = self._candidate_for_step(step, candidate_lookup)
            if not candidate or candidate.get("category") != "restaurant":
                continue
            slot_time = self._nearest_available_slot(
                candidate.get("availability", []),
                step.get("start", ""),
                party_size,
                max_wait,
            )
            if not slot_time:
                continue
            self._shift_step_time(step, slot_time)

    def _candidate_for_step(
        self,
        step: Mapping[str, Any],
        candidate_lookup: Mapping[str, dict[str, Any]],
    ) -> dict[str, Any]:
        for key in ("id", "place_id", "shop_id"):
            value = step.get(key)
            if value and str(value) in candidate_lookup:
                return candidate_lookup[str(value)]
        return {}

    def _nearest_available_slot(
        self,
        availability: Any,
        requested_time: Any,
        party_size: int,
        max_wait_minutes: int,
    ) -> str:
        requested_minutes = self._time_to_minutes(str(requested_time))
        if requested_minutes is None or not isinstance(availability, list):
            return ""

        best: tuple[int, str] | None = None
        for slot_value in availability:
            slot = slot_value if isinstance(slot_value, Mapping) else {}
            if slot.get("available") is not True:
                continue
            if self._int_count(slot.get("capacity", 0)) < party_size:
                continue
            slot_time = str(slot.get("time", ""))
            slot_minutes = self._time_to_minutes(slot_time)
            if slot_minutes is None:
                continue
            delta = abs(slot_minutes - requested_minutes)
            if delta > max_wait_minutes:
                continue
            if best is None or delta < best[0]:
                best = (delta, slot_time)
        return best[1] if best else ""

    def _shift_step_time(self, step: dict[str, Any], slot_time: str) -> None:
        old_start = str(step.get("start") or step.get("time") or "")
        old_start_minutes = self._time_to_minutes(old_start)
        new_start_minutes = self._time_to_minutes(slot_time)
        if old_start_minutes is None or new_start_minutes is None:
            return

        delta = new_start_minutes - old_start_minutes
        step["start"] = slot_time
        if "time" in step:
            step["time"] = slot_time

        old_end_minutes = self._time_to_minutes(str(step.get("end", "")))
        if old_end_minutes is not None:
            step["end"] = self._format_time(old_end_minutes + delta)

    def _uses_seed_catalog(self, candidate_lookup: Mapping[str, dict[str, Any]]) -> bool:
        return any(candidate.get("source") == "local_seed_catalog" for candidate in candidate_lookup.values())

    def _first_catalog_open_weekday(self, candidate_lookup: Mapping[str, dict[str, Any]]) -> str:
        for candidate in candidate_lookup.values():
            open_hours = candidate.get("open_hours", [])
            if not isinstance(open_hours, list):
                continue
            for item in open_hours:
                if not isinstance(item, Mapping):
                    continue
                weekday = str(item.get("day", "")).strip().lower()
                if weekday and weekday != "today":
                    return weekday[:3]
        return ""

    def _next_weekday_date(self, weekday: str) -> str:
        weekdays = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
        target = weekdays.get(weekday[:3].lower())
        if target is None:
            return date.today().isoformat()
        today = date.today()
        days_ahead = (target - today.weekday()) % 7
        return (today + timedelta(days=days_ahead)).isoformat()

    def _party_size(self, constraints: Mapping[str, Any]) -> int:
        people = constraints.get("people", {})
        if not isinstance(people, Mapping):
            return 0
        adults = self._int_count(people.get("adults", 0))
        children = people.get("children", 0)
        if isinstance(children, list):
            return adults + len(children)
        return adults + self._int_count(children)

    def _max_wait_minutes(self, constraints: Mapping[str, Any]) -> int:
        nested = constraints.get("constraints", {})
        if not isinstance(nested, Mapping):
            return 15
        return max(self._int_count(nested.get("max_wait_minutes", 15)), 0)

    def _int_count(self, value: Any) -> int:
        if isinstance(value, bool):
            return 0
        try:
            return max(int(value), 0)
        except (TypeError, ValueError):
            return 0

    def _time_to_minutes(self, value: str) -> int | None:
        parts = value.strip().split(":")
        if len(parts) != 2:
            return None
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError:
            return None
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None
        return hour * 60 + minute

    def _format_time(self, minutes: int) -> str:
        minutes = max(0, min(minutes, 23 * 60 + 59))
        return f"{minutes // 60:02d}:{minutes % 60:02d}"

    def _plan_summary(self, revision: Mapping[str, Any]) -> dict[str, Any]:
        plan = revision.get("plan", {})
        if not isinstance(plan, Mapping):
            plan = {}
        return {
            "id": revision["plan_id"],
            "revision_id": revision["revision_id"],
            "phase": revision["phase"],
            "title": str(plan.get("title", "")),
            "summary": str(plan.get("summary", "")),
        }
