from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from backend.actions.durable_ledger import DurableActionLedger
from backend.actions.policy import build_executable_actions
from backend.data.catalog import LocalDataCatalog
from backend.graph.state import (
    PHASE_APPROVED,
    PHASE_CANCELLED,
    PHASE_COMPLETED,
    PHASE_EXECUTING,
    PHASE_NEEDS_CLARIFICATION,
    PHASE_PARTIALLY_COMPLETED,
    PHASE_PENDING_APPROVAL,
    PHASE_PLANNING,
    PHASE_READY,
    PHASE_VALIDATION_FAILED,
    new_plan_id,
    new_revision_id,
    new_run_id,
    new_thread_id,
    assert_transition_allowed,
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
            self._sync_route_totals(plan_payload)

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
            if validation["valid"]:
                phase = PHASE_PENDING_APPROVAL if actions else PHASE_READY
            else:
                phase = PHASE_VALIDATION_FAILED
            plan_payload["actions"] = actions if phase == PHASE_PENDING_APPROVAL else []

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
        actions = self.ledger.list_actions(revision_id)
        receipts = self.ledger.list_receipts(revision_id)
        current_phase = self._current_phase(plan_id, revision)
        revision = self._response_revision(revision, current_phase, actions)
        return {
            "plan_id": plan_id,
            "revision": revision,
            "actions": actions,
            "receipts": receipts,
        }

    def resume(self, plan_id: str, decision: dict[str, Any]) -> dict[str, Any]:
        revision = self.repository.get_latest_revision(plan_id)
        if revision is None:
            raise KeyError("plan_not_found")

        phase = self._current_phase(plan_id, revision)
        decision_value = decision.get("decision")
        if decision_value == "reject":
            if phase != PHASE_PENDING_APPROVAL:
                raise ValueError(phase)
            assert_transition_allowed(phase, PHASE_CANCELLED)
            self.repository.update_thread_status_for_plan(plan_id, PHASE_CANCELLED)
            return self.get_plan(plan_id)
        if decision_value != "approve":
            raise ValueError("unsupported_decision")
        if phase not in {PHASE_PENDING_APPROVAL, PHASE_PARTIALLY_COMPLETED}:
            raise ValueError(phase)

        selected_action_ids = [str(action_id) for action_id in decision.get("selected_action_ids", [])]
        if not selected_action_ids:
            raise ValueError("selected_action_ids_required")
        executable = self.ledger.mark_executing(revision["revision_id"], selected_action_ids)
        for action in executable:
            self.ledger.mark_succeeded(
                action["action_id"],
                _receipt_id_for(action),
                f"{action['tool']} completed",
                action["payload"],
            )

        actions = self.ledger.list_actions(revision["revision_id"])
        has_remaining = any(action["status"] not in {"succeeded", "skipped"} for action in actions)
        next_phase = PHASE_PARTIALLY_COMPLETED if has_remaining else PHASE_COMPLETED
        self._assert_execution_transition(phase, next_phase)
        self.repository.update_thread_status_for_plan(plan_id, next_phase)
        return self.get_plan(plan_id)

    def list_plans(self) -> dict[str, Any]:
        revisions = []
        for revision in self.repository.list_latest_revisions():
            phase = self._current_phase(revision["plan_id"], revision)
            if phase in {PHASE_READY, PHASE_PENDING_APPROVAL, PHASE_PARTIALLY_COMPLETED}:
                revisions.append(self._response_revision(revision, phase, []))
        plans = [self._plan_summary(revision) for revision in revisions]
        return {"plans": plans, "total": len(plans)}

    def stream_run_events(self, run_id: str) -> list[dict[str, Any]]:
        thread = self.repository.get_thread_by_run(run_id)
        if thread is None:
            raise KeyError("run_not_found")

        plan_id = str(thread["plan_id"])
        revision = self.repository.get_latest_revision(plan_id)
        if revision is None:
            raise KeyError("run_not_found")

        phase = self._current_phase(plan_id, revision)
        actions = self.ledger.list_actions(revision["revision_id"])
        revision = self._response_revision(revision, phase, actions)
        return [
            {
                "id": "evt_000001",
                "event": "graph_update",
                "data": {
                    "run_id": run_id,
                    "thread_id": thread["thread_id"],
                    "plan_id": plan_id,
                    "revision_id": revision["revision_id"],
                    "phase": phase,
                    "revision": revision,
                },
            }
        ]

    def _current_phase(self, plan_id: str, revision: Mapping[str, Any]) -> str:
        thread = self.repository.get_thread_by_plan(plan_id)
        if thread and thread.get("status"):
            return str(thread["status"])
        return str(revision["phase"])

    def _response_revision(
        self,
        revision: Mapping[str, Any],
        phase: str,
        actions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        response = dict(revision)
        plan_payload = dict(revision["plan"])
        if actions:
            plan_payload["actions"] = actions
        plan_payload["status"] = phase
        response["phase"] = phase
        response["plan"] = plan_payload
        return response

    def _assert_execution_transition(self, phase: str, next_phase: str) -> None:
        if phase == PHASE_PENDING_APPROVAL:
            assert_transition_allowed(phase, PHASE_APPROVED)
            assert_transition_allowed(PHASE_APPROVED, PHASE_EXECUTING)
        else:
            assert_transition_allowed(phase, PHASE_EXECUTING)
        assert_transition_allowed(PHASE_EXECUTING, next_phase)

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

    def _sync_route_totals(self, plan: dict[str, Any]) -> None:
        route = plan.get("route")
        if not isinstance(route, dict):
            return
        legs = route.get("legs", [])
        if not isinstance(legs, list):
            return

        total_minutes = sum(
            self._int_count(leg.get("duration_minutes", 0))
            for leg in legs
            if isinstance(leg, Mapping)
        )
        route["total_travel_minutes"] = total_minutes
        route["drive_time_minutes"] = total_minutes

        overview = plan.get("overview")
        if isinstance(overview, dict) and "driveTime" in overview:
            overview["driveTime"] = f"约 {total_minutes} 分钟"

    def _normalize_seed_catalog_plan_for_validation(
        self,
        plan: dict[str, Any],
        candidate_lookup: Mapping[str, dict[str, Any]],
        constraints: dict[str, Any],
    ) -> None:
        self._normalize_seed_catalog_visit_date(plan, candidate_lookup, constraints)
        self._align_seed_restaurant_steps_to_availability(plan, candidate_lookup, constraints)

    def _normalize_seed_catalog_visit_date(
        self,
        plan: dict[str, Any],
        candidate_lookup: Mapping[str, dict[str, Any]],
        constraints: dict[str, Any],
    ) -> None:
        time_window = dict(constraints.get("time_window") or {})
        if str(time_window.get("date", "")).lower() != "today":
            return

        weekday = self._first_catalog_open_weekday(candidate_lookup)
        if not weekday:
            return

        normalized_date = self._next_weekday_date(weekday)
        time_window["date"] = normalized_date
        constraints["time_window"] = time_window
        self._set_plan_time_window_date(plan, normalized_date)

    def _set_plan_time_window_date(self, plan: dict[str, Any], date_value: str) -> None:
        plan_constraints = plan.get("constraints")
        if not isinstance(plan_constraints, dict):
            return
        time_window = dict(plan_constraints.get("time_window") or {})
        time_window["date"] = date_value
        plan_constraints["time_window"] = time_window

    def _align_seed_restaurant_steps_to_availability(
        self,
        plan: dict[str, Any],
        candidate_lookup: Mapping[str, dict[str, Any]],
        constraints: Mapping[str, Any],
    ) -> None:
        party_size = self._party_size(constraints)
        max_wait = self._max_wait_minutes(constraints)
        self._align_seed_restaurant_steps(plan.get("itinerary", []), candidate_lookup, party_size, max_wait)
        adjusted_variants = []
        for variant in plan.get("variants", []):
            if not isinstance(variant, dict):
                continue
            if self._align_seed_restaurant_steps(variant.get("itinerary", []), candidate_lookup, party_size, max_wait):
                adjusted_variants.append(variant)
        plan["variants"] = adjusted_variants

    def _align_seed_restaurant_steps(
        self,
        itinerary: Any,
        candidate_lookup: Mapping[str, dict[str, Any]],
        party_size: int,
        max_wait: int,
    ) -> bool:
        if not isinstance(itinerary, list):
            return False
        aligned = True
        for index, step in enumerate(itinerary):
            if not isinstance(step, dict):
                continue
            if step.get("type") != "restaurant":
                continue
            candidate = self._candidate_for_step(step, candidate_lookup)
            if not candidate or candidate.get("category") != "restaurant":
                aligned = False
                continue
            slot_time = self._nearest_available_slot(
                candidate.get("availability", []),
                step.get("start", ""),
                party_size,
                max_wait,
            )
            if not slot_time:
                aligned = False
                continue
            delta = self._time_delta_to_slot(step, slot_time)
            if delta is None:
                aligned = False
                continue
            for later_step in itinerary[index:]:
                if isinstance(later_step, dict):
                    self._shift_step_by_delta(later_step, delta)
        return aligned

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

        best_within_wait: tuple[int, str] | None = None
        best_available: tuple[int, str] | None = None
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
            if best_available is None or delta < best_available[0]:
                best_available = (delta, slot_time)
            if delta <= max_wait_minutes and (best_within_wait is None or delta < best_within_wait[0]):
                best_within_wait = (delta, slot_time)
        best = best_within_wait or best_available
        return best[1] if best else ""

    def _shift_step_time(self, step: dict[str, Any], slot_time: str) -> None:
        old_start = str(step.get("start") or step.get("time") or "")
        old_start_minutes = self._time_to_minutes(old_start)
        new_start_minutes = self._time_to_minutes(slot_time)
        if old_start_minutes is None or new_start_minutes is None:
            return

        delta = new_start_minutes - old_start_minutes
        self._shift_step_by_delta(step, delta)

    def _time_delta_to_slot(self, step: Mapping[str, Any], slot_time: str) -> int | None:
        old_start = str(step.get("start") or step.get("time") or "")
        old_start_minutes = self._time_to_minutes(old_start)
        new_start_minutes = self._time_to_minutes(slot_time)
        if old_start_minutes is None or new_start_minutes is None:
            return None
        return new_start_minutes - old_start_minutes

    def _shift_step_by_delta(self, step: dict[str, Any], delta: int) -> None:
        old_start = str(step.get("start") or step.get("time") or "")
        old_start_minutes = self._time_to_minutes(old_start)
        if old_start_minutes is None:
            return

        slot_time = self._format_time(old_start_minutes + delta)
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
            "created_at": str(revision.get("created_at", "")),
            "updated_at": str(revision.get("created_at", "")),
            "tags": ["本地生活"],
            "title": str(plan.get("title", "")),
            "summary": str(plan.get("summary", "")),
        }


def _receipt_id_for(action: dict[str, Any]) -> str:
    prefix = {
        "reserve_activity": "TKT",
        "create_reservation": "RES",
        "claim_coupon": "CPN",
        "create_order": "ORD",
        "send_plan_message": "MSG",
        "create_calendar_event": "CAL",
    }.get(str(action["tool"]), "RCT")
    suffix = str(action["action_id"]).split("_", 1)[-1][:12].upper()
    return f"{prefix}-{suffix}"
